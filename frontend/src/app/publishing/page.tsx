"use client";

import React, { useState, useEffect, useRef, useCallback } from "react";
import { PublishingSession } from "@/types/publishing";
import { publishingService } from "@/services/publishingService";
import { PublishingTable } from "@/components/publishing/PublishingTable";
import { PublishingPrepareModal } from "@/components/publishing/PublishingPrepareModal";
import { PublishingDetailModal } from "@/components/publishing/PublishingDetailModal";
import { JobDetailModal } from "@/components/jobs/JobDetailModal";
import { accountService } from "@/services/accountService";
import { runtimeService } from "@/services/runtimeService";
import { Account } from "@/types/account";
import { Runtime, formatApiError } from "@/types/runtime";
import {
  Rocket,
  Plus,
  RefreshCw,
  Sparkles,
  Search,
} from "lucide-react";

export default function PublishingPage() {
  const [sessions, setSessions] = useState<PublishingSession[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Filters
  const [statusFilter, setStatusFilter] = useState("all");
  const [search, setSearch] = useState("");

  // Modals
  const [isPrepareOpen, setIsPrepareOpen] = useState(false);
  const [selectedSessionForDetail, setSelectedSessionForDetail] =
    useState<PublishingSession | null>(null);
  const [inspectJobId, setInspectJobId] = useState<number | null>(null);
  const [accountsMap, setAccountsMap] = useState<Record<number, Account>>({});
  const [runtimesMap, setRuntimesMap] = useState<Record<number, Runtime>>({});

  // Bounded auto-polling timer for active sessions
  const pollTimerRef = useRef<NodeJS.Timeout | null>(null);

  const isTerminal = (status?: string) =>
    ["prepared", "rejected", "failed", "cancelled"].includes(status || "");

  const fetchSessions = useCallback(async (showLoading = true) => {
    try {
      if (showLoading) setIsLoading(true);
      setError(null);
      const res = await publishingService.getPublishingSessions({
        page: 1,
        page_size: 100,
        status: statusFilter !== "all" ? statusFilter : undefined,
      });
      setSessions(res.items);
    } catch (err: unknown) {
      setError(formatApiError(err));
    } finally {
      if (showLoading) setIsLoading(false);
    }
  }, [statusFilter]);

  useEffect(() => {
    let ignore = false;
    publishingService
      .getPublishingSessions({
        page: 1,
        page_size: 100,
        status: statusFilter !== "all" ? statusFilter : undefined,
      })
      .then((res) => {
        if (!ignore) setSessions(res.items);
      })
      .catch((err: unknown) => {
        if (!ignore) setError(formatApiError(err));
      })
      .finally(() => {
        if (!ignore) setIsLoading(false);
      });

    // Auto-poll every 3s if any active sessions exist
    pollTimerRef.current = setInterval(() => {
      fetchSessions(false);
    }, 3000);

    return () => {
      ignore = true;
      if (pollTimerRef.current) {
        clearInterval(pollTimerRef.current);
        pollTimerRef.current = null;
      }
    };
  }, [fetchSessions, statusFilter]);

  // Clean polling if all sessions are terminal
  useEffect(() => {
    const hasActiveSessions = sessions.some((s) => !isTerminal(s.status));
    if (!hasActiveSessions && pollTimerRef.current && sessions.length > 0) {
      clearInterval(pollTimerRef.current);
      pollTimerRef.current = null;
    }
  }, [sessions]);

  // Load account and runtime maps for job inspection
  useEffect(() => {
    let ignore = false;
    Promise.all([
      accountService.getAccounts({ page: 1, page_size: 100 }).catch(() => ({ items: [] })),
      runtimeService.getRuntimes({ page: 1, page_size: 100 }).catch(() => ({ items: [] })),
    ]).then(([accs, rts]) => {
      if (ignore) return;
      const accMap: Record<number, Account> = {};
      accs.items.forEach((a) => {
        accMap[a.id] = a;
      });
      setAccountsMap(accMap);

      const rtMap: Record<number, Runtime> = {};
      rts.items.forEach((r) => {
        rtMap[r.id] = r;
      });
      setRuntimesMap(rtMap);
    });

    return () => {
      ignore = true;
    };
  }, []);

  const displayedSessions = sessions.filter((s) => {
    if (search.trim()) {
      const q = search.trim().toLowerCase();
      const matchId = String(s.id).includes(q);
      const matchWf = String(s.workflow_id).includes(q);
      const matchAcc = String(s.account_id_snapshot).includes(q);
      const matchRt = String(s.runtime_id_snapshot).includes(q);
      if (!matchId && !matchWf && !matchAcc && !matchRt) return false;
    }
    return true;
  });

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-slate-200">
        <div>
          <h1 className="text-xl font-bold text-slate-900 flex items-center gap-2.5">
            <Rocket className="w-6 h-6 text-rose-600" />
            <span>Publishing Preparation</span>
          </h1>
          <p className="text-xs text-slate-500 mt-1">
            Server-owned publishing preparation workflows, staging environments, and operator approval boundaries.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => fetchSessions(true)}
            disabled={isLoading}
            className="p-2 text-slate-500 hover:text-slate-800 hover:bg-slate-100 rounded-lg border border-slate-200 transition-colors disabled:opacity-50"
            title="Refresh sessions"
          >
            <RefreshCw className={`w-4 h-4 ${isLoading ? "animate-spin" : ""}`} />
          </button>
          <button
            type="button"
            onClick={() => setIsPrepareOpen(true)}
            className="inline-flex items-center gap-1.5 px-3.5 py-2 text-xs font-semibold text-white bg-rose-600 hover:bg-rose-700 rounded-lg shadow-sm transition-colors"
          >
            <Plus className="w-4 h-4" />
            <span>Prepare Publishing</span>
          </button>
        </div>
      </div>

      {/* Prominent Safety Callout */}
      <div className="p-4 bg-gradient-to-r from-amber-50 to-orange-50 border border-amber-200/90 rounded-xl text-amber-950 flex items-start gap-3 shadow-2xs">
        <Sparkles className="w-5 h-5 text-amber-600 shrink-0 mt-0.5" />
        <div className="space-y-0.5 text-xs">
          <h3 className="font-bold text-amber-950">
            &ldquo;Prepared does not mean published.&rdquo;
          </h3>
          <p className="text-amber-800 leading-relaxed">
            Publishing sessions safely verify the device environment, ensure the correct managed app is active, deliver media assets, and launch the application. Operator approval confirms staging readiness only; no content is posted to TikTok.
          </p>
        </div>
      </div>

      {/* Toolbar / Filters */}
      <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3 bg-white p-3 rounded-xl border border-slate-200 shadow-2xs">
        <div className="relative flex-1 max-w-sm">
          <Search className="w-4 h-4 text-slate-400 absolute left-3 top-2.5" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search by session, workflow, account, or runtime ID..."
            className="w-full pl-9 pr-3 py-1.5 text-xs bg-slate-50 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-rose-500"
          />
        </div>

        <div className="flex items-center gap-2">
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="text-xs bg-slate-50 border border-slate-200 rounded-lg px-2.5 py-1.5 text-slate-700 focus:outline-none focus:ring-2 focus:ring-rose-500"
          >
            <option value="all">All Statuses</option>
            <option value="preparing">Preparing</option>
            <option value="waiting_approval">Waiting Approval</option>
            <option value="prepared">Prepared</option>
            <option value="rejected">Rejected</option>
            <option value="failed">Failed</option>
            <option value="cancelled">Cancelled</option>
          </select>
        </div>
      </div>

      {/* Main Sessions Table */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-2xs overflow-hidden">
        <PublishingTable
          sessions={displayedSessions}
          isLoading={isLoading}
          error={error}
          onRetry={() => fetchSessions(true)}
          onPreparePublishing={() => setIsPrepareOpen(true)}
          onViewSession={(sess) => setSelectedSessionForDetail(sess)}
        />
      </div>

      {/* Prepare Publishing Modal */}
      <PublishingPrepareModal
        isOpen={isPrepareOpen}
        onClose={() => setIsPrepareOpen(false)}
        onSuccess={() => {
          fetchSessions(true);
        }}
      />

      {/* Detail / Timeline Modal */}
      <PublishingDetailModal
        session={selectedSessionForDetail}
        isOpen={selectedSessionForDetail !== null}
        onClose={() => setSelectedSessionForDetail(null)}
        onViewJob={(jobId) => setInspectJobId(jobId)}
        onSessionUpdated={() => fetchSessions(false)}
      />

      {/* Job Detail Modal */}
      {inspectJobId !== null && (
        <JobDetailModal
          jobId={inspectJobId}
          accountsMap={accountsMap}
          runtimesMap={runtimesMap}
          onClose={() => setInspectJobId(null)}
          onQueueRefresh={() => fetchSessions(false)}
        />
      )}
    </div>
  );
}

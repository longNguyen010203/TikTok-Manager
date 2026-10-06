import React from "react";
import { PublishingSession } from "@/types/publishing";
import { PublishingStatusBadge } from "./PublishingStatusBadge";
import {
  Rocket,
  Calendar,
  RefreshCw,
  Plus,
  Clock,
  ExternalLink,
} from "lucide-react";

interface PublishingTableProps {
  sessions: PublishingSession[];
  isLoading: boolean;
  error: string | null;
  onRetry: () => void;
  onPreparePublishing: () => void;
  onViewSession: (session: PublishingSession) => void;
}

export function PublishingTable({
  sessions,
  isLoading,
  error,
  onRetry,
  onPreparePublishing,
  onViewSession,
}: PublishingTableProps) {
  const formatDate = (isoString?: string | null) => {
    if (!isoString) return "N/A";
    try {
      return new Intl.DateTimeFormat("en-US", {
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
        hour12: false,
      }).format(new Date(isoString));
    } catch {
      return isoString;
    }
  };

  if (isLoading) {
    return (
      <div className="py-16 flex flex-col items-center justify-center text-slate-400 gap-3">
        <RefreshCw className="w-6 h-6 animate-spin text-rose-500" />
        <span className="text-xs font-medium">Loading publishing sessions...</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-8 text-center bg-rose-50 border border-rose-200 rounded-xl space-y-3">
        <p className="text-xs font-medium text-rose-700">{error}</p>
        <button
          type="button"
          onClick={onRetry}
          className="px-4 py-1.5 text-xs font-semibold text-rose-700 bg-white border border-rose-300 rounded-lg hover:bg-rose-50"
        >
          Retry
        </button>
      </div>
    );
  }

  if (sessions.length === 0) {
    return (
      <div className="p-12 text-center bg-slate-50 border border-slate-200 rounded-xl space-y-4">
        <div className="w-12 h-12 rounded-xl bg-rose-100 text-rose-600 flex items-center justify-center mx-auto font-bold">
          <Rocket className="w-6 h-6" />
        </div>
        <div className="space-y-1">
          <h3 className="text-sm font-bold text-slate-800">No Publishing Sessions</h3>
          <p className="text-xs text-slate-500 max-w-md mx-auto">
            Publishing sessions prepare devices and staging environments for operator review. Click below to start preparation.
          </p>
        </div>
        <button
          type="button"
          onClick={onPreparePublishing}
          className="inline-flex items-center gap-1.5 px-4 py-2 text-xs font-semibold text-white bg-rose-600 hover:bg-rose-700 rounded-lg shadow-sm transition-colors"
        >
          <Plus className="w-3.5 h-3.5" />
          <span>Prepare Publishing</span>
        </button>
      </div>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left text-xs border-collapse">
        <thead>
          <tr className="bg-slate-50/70 border-b border-slate-200/80 text-slate-500 uppercase tracking-wider text-[11px] font-semibold">
            <th scope="col" className="py-3 px-6">
              Session &amp; Workflow
            </th>
            <th scope="col" className="py-3 px-6">
              Account
            </th>
            <th scope="col" className="py-3 px-6">
              Runtime
            </th>
            <th scope="col" className="py-3 px-6">
              Content Version
            </th>
            <th scope="col" className="py-3 px-6">
              App Version
            </th>
            <th scope="col" className="py-3 px-6">
              Status
            </th>
            <th scope="col" className="py-3 px-6">
              Created / Prepared
            </th>
            <th scope="col" className="py-3 px-6 text-right">
              Actions
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100 text-slate-700">
          {sessions.map((session) => (
            <tr
              key={session.id}
              onClick={() => onViewSession(session)}
              className="hover:bg-slate-50/70 transition-colors cursor-pointer group"
            >
              {/* Session / Workflow */}
              <td className="py-4 px-6">
                <div className="flex items-center gap-3">
                  <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-rose-100 to-orange-200 text-rose-700 flex items-center justify-center font-bold text-xs shrink-0 shadow-2xs">
                    <Rocket className="w-4 h-4" />
                  </div>
                  <div>
                    <p className="font-semibold text-slate-900">
                      Session #{session.id}
                    </p>
                    <p className="text-[11px] text-slate-400 font-mono">
                      Workflow #{session.workflow_id}
                    </p>
                  </div>
                </div>
              </td>

              {/* Account */}
              <td className="py-4 px-6 font-medium text-slate-800">
                Account #{session.account_id_snapshot}
              </td>

              {/* Runtime */}
              <td className="py-4 px-6 font-mono text-slate-700">
                Runtime #{session.runtime_id_snapshot}
              </td>

              {/* Content Version */}
              <td className="py-4 px-6 font-mono text-slate-700">
                Version #{session.content_asset_version_id}
              </td>

              {/* Managed App / Version */}
              <td className="py-4 px-6 font-mono text-slate-700">
                App #{session.managed_app_id} (v{session.managed_app_version_id})
              </td>

              {/* Status */}
              <td className="py-4 px-6">
                <PublishingStatusBadge status={session.status} />
              </td>

              {/* Created / Prepared */}
              <td className="py-4 px-6 text-slate-500 whitespace-nowrap">
                <div className="space-y-0.5">
                  <div className="flex items-center gap-1.5 text-[11px]">
                    <Clock className="w-3 h-3 text-slate-400" />
                    <span>Created: {formatDate(session.created_at)}</span>
                  </div>
                  {session.prepared_at && (
                    <div className="flex items-center gap-1.5 text-[11px] text-emerald-700 font-semibold">
                      <Calendar className="w-3 h-3 text-emerald-500" />
                      <span>Prepared: {formatDate(session.prepared_at)}</span>
                    </div>
                  )}
                </div>
              </td>

              {/* Actions */}
              <td className="py-4 px-6 text-right whitespace-nowrap">
                <button
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation();
                    onViewSession(session);
                  }}
                  className="inline-flex items-center gap-1 px-3 py-1.5 text-xs font-semibold text-rose-800 bg-rose-50 hover:bg-rose-100 border border-rose-200/80 rounded-lg transition-colors shadow-2xs"
                >
                  <ExternalLink className="w-3.5 h-3.5 text-rose-600" />
                  <span>Inspect Timeline</span>
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

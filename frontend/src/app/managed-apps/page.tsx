"use client";

import React, { useState, useEffect, useCallback } from "react";
import { ManagedApp } from "@/types/managedApp";
import { managedAppService } from "@/services/managedAppService";
import { formatApiError } from "@/types/runtime";
import { ManagedAppTable } from "@/components/managed-apps/ManagedAppTable";
import { ManagedAppCreateModal } from "@/components/managed-apps/ManagedAppCreateModal";
import { ManagedAppEditModal } from "@/components/managed-apps/ManagedAppEditModal";
import { ManagedAppDetailModal } from "@/components/managed-apps/ManagedAppDetailModal";
import { Package, Plus, RefreshCw, Search, ShieldCheck } from "lucide-react";

export default function ManagedAppsPage() {
  const [apps, setApps] = useState<ManagedApp[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Filters
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [policyFilter, setPolicyFilter] = useState("all");

  // Modals
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [editingApp, setEditingApp] = useState<ManagedApp | null>(null);
  const [selectedAppIdForDetail, setSelectedAppIdForDetail] = useState<number | null>(null);

  const fetchApps = useCallback(async () => {
    try {
      setIsLoading(true);
      setError(null);
      const res = await managedAppService.getManagedApps({ page: 1, page_size: 100 });
      setApps(res.items);
    } catch (err: unknown) {
      setError(formatApiError(err));
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    let ignore = false;
    managedAppService
      .getManagedApps({ page: 1, page_size: 100 })
      .then((res) => {
        if (!ignore) setApps(res.items);
      })
      .catch((err: unknown) => {
        if (!ignore) setError(formatApiError(err));
      })
      .finally(() => {
        if (!ignore) setIsLoading(false);
      });

    return () => {
      ignore = true;
    };
  }, []);

  const displayedApps = apps.filter((app) => {
    if (statusFilter !== "all" && app.status !== statusFilter) return false;
    if (policyFilter !== "all" && app.install_policy !== policyFilter) return false;
    if (search.trim()) {
      const q = search.trim().toLowerCase();
      const matchName = app.display_name.toLowerCase().includes(q);
      const matchKey = app.key.toLowerCase().includes(q);
      const matchPkg = app.android_package_name.toLowerCase().includes(q);
      if (!matchName && !matchKey && !matchPkg) return false;
    }
    return true;
  });

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-slate-200">
        <div>
          <h1 className="text-xl font-bold text-slate-900 flex items-center gap-2.5">
            <Package className="w-6 h-6 text-rose-600" />
            <span>Managed Apps</span>
          </h1>
          <p className="text-xs text-slate-500 mt-1">
            Authoritative Android applications, immutable APK versions, and automated runtime installation policies.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={fetchApps}
            disabled={isLoading}
            className="p-2 text-slate-500 hover:text-slate-800 hover:bg-slate-100 rounded-lg border border-slate-200 transition-colors disabled:opacity-50"
            title="Refresh apps"
          >
            <RefreshCw className={`w-4 h-4 ${isLoading ? "animate-spin" : ""}`} />
          </button>
          <button
            type="button"
            onClick={() => setIsCreateOpen(true)}
            className="inline-flex items-center gap-1.5 px-3.5 py-2 text-xs font-semibold text-white bg-rose-600 hover:bg-rose-700 rounded-lg shadow-sm transition-colors"
          >
            <Plus className="w-4 h-4" />
            <span>Add Managed App</span>
          </button>
        </div>
      </div>

      {/* Assurance Notice */}
      <div className="p-3.5 bg-slate-900 text-slate-200 rounded-xl flex items-center justify-between text-xs shadow-sm">
        <div className="flex items-center gap-2.5">
          <ShieldCheck className="w-4 h-4 text-emerald-400 shrink-0" />
          <span>
            <strong>Safe Package Deployment:</strong> Managed apps undergo SHA-256 integrity hashing and manifest validation. No raw ADB or arbitrary APKs can be pushed to managed devices.
          </span>
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
            placeholder="Search by name, key, or package..."
            className="w-full pl-9 pr-3 py-1.5 text-xs bg-slate-50 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-rose-500"
          />
        </div>

        <div className="flex items-center gap-2 flex-wrap">
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="text-xs bg-slate-50 border border-slate-200 rounded-lg px-2.5 py-1.5 text-slate-700 focus:outline-none focus:ring-2 focus:ring-rose-500"
          >
            <option value="all">All Statuses</option>
            <option value="active">Active</option>
            <option value="disabled">Disabled</option>
            <option value="archived">Archived</option>
          </select>

          <select
            value={policyFilter}
            onChange={(e) => setPolicyFilter(e.target.value)}
            className="text-xs bg-slate-50 border border-slate-200 rounded-lg px-2.5 py-1.5 text-slate-700 focus:outline-none focus:ring-2 focus:ring-rose-500"
          >
            <option value="all">All Policies</option>
            <option value="required">Required</option>
            <option value="optional">Optional</option>
            <option value="disabled">Disabled</option>
          </select>
        </div>
      </div>

      {/* Main Table */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-2xs overflow-hidden">
        <ManagedAppTable
          apps={displayedApps}
          isLoading={isLoading}
          error={error}
          onRetry={fetchApps}
          onCreateApp={() => setIsCreateOpen(true)}
          onEditApp={(app) => setEditingApp(app)}
          onViewVersions={(app) => setSelectedAppIdForDetail(app.id)}
        />
      </div>

      {/* Create Modal */}
      <ManagedAppCreateModal
        isOpen={isCreateOpen}
        onClose={() => setIsCreateOpen(false)}
        onSuccess={(newApp) => {
          fetchApps();
          setSelectedAppIdForDetail(newApp.id);
        }}
      />

      {/* Edit Modal */}
      <ManagedAppEditModal
        app={editingApp}
        isOpen={editingApp !== null}
        onClose={() => setEditingApp(null)}
        onSuccess={() => fetchApps()}
      />

      {/* Detail / Versions Modal */}
      <ManagedAppDetailModal
        appId={selectedAppIdForDetail}
        isOpen={selectedAppIdForDetail !== null}
        onClose={() => setSelectedAppIdForDetail(null)}
        onAppUpdated={() => fetchApps()}
      />
    </div>
  );
}

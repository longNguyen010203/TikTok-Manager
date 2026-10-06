import React from "react";
import { ManagedApp } from "@/types/managedApp";
import { AppStatusBadge, InstallPolicyBadge } from "./ManagedAppStatusBadge";
import { Package, Pencil, Layers, Calendar, Plus, RefreshCw } from "lucide-react";

interface ManagedAppTableProps {
  apps: ManagedApp[];
  isLoading: boolean;
  error: string | null;
  onRetry: () => void;
  onCreateApp: () => void;
  onEditApp: (app: ManagedApp) => void;
  onViewVersions: (app: ManagedApp) => void;
}

export function ManagedAppTable({
  apps,
  isLoading,
  error,
  onRetry,
  onCreateApp,
  onEditApp,
  onViewVersions,
}: ManagedAppTableProps) {
  const formatDate = (isoString?: string | null) => {
    if (!isoString) return "Never";
    try {
      return new Intl.DateTimeFormat("en-US", {
        month: "short",
        day: "numeric",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit",
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
        <span className="text-xs font-medium">Loading managed apps...</span>
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

  if (apps.length === 0) {
    return (
      <div className="p-12 text-center bg-slate-50 border border-slate-200 rounded-xl space-y-4">
        <div className="w-12 h-12 rounded-xl bg-rose-100 text-rose-600 flex items-center justify-center mx-auto font-bold">
          <Package className="w-6 h-6" />
        </div>
        <div className="space-y-1">
          <h3 className="text-sm font-bold text-slate-800">No Managed Apps Defined</h3>
          <p className="text-xs text-slate-500 max-w-md mx-auto">
            Managed applications provide immutable APK packages and version assurance for automated Runtime deployment.
          </p>
        </div>
        <button
          type="button"
          onClick={onCreateApp}
          className="inline-flex items-center gap-1.5 px-4 py-2 text-xs font-semibold text-white bg-rose-600 hover:bg-rose-700 rounded-lg shadow-sm transition-colors"
        >
          <Plus className="w-3.5 h-3.5" />
          <span>Add Managed App</span>
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
              Application
            </th>
            <th scope="col" className="py-3 px-6">
              Package Identity
            </th>
            <th scope="col" className="py-3 px-6">
              Install Policy
            </th>
            <th scope="col" className="py-3 px-6">
              Status
            </th>
            <th scope="col" className="py-3 px-6">
              Active Version
            </th>
            <th scope="col" className="py-3 px-6">
              Updated At
            </th>
            <th scope="col" className="py-3 px-6 text-right">
              Actions
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100 text-slate-700">
          {apps.map((app) => (
            <tr key={app.id} className="hover:bg-slate-50/60 transition-colors">
              <td className="py-4 px-6">
                <div className="flex items-center gap-3">
                  <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-rose-100 to-pink-200 text-rose-700 flex items-center justify-center font-bold text-xs shrink-0 shadow-2xs">
                    <Package className="w-4 h-4" />
                  </div>
                  <div>
                    <p className="font-semibold text-slate-900">{app.display_name}</p>
                    <p className="text-[11px] text-slate-400 font-mono">key: {app.key}</p>
                  </div>
                </div>
              </td>

              <td className="py-4 px-6 font-mono text-slate-700 text-xs">
                {app.android_package_name}
              </td>

              <td className="py-4 px-6">
                <InstallPolicyBadge policy={app.install_policy} />
              </td>

              <td className="py-4 px-6">
                <AppStatusBadge status={app.status} />
              </td>

              <td className="py-4 px-6">
                {app.current_version_id ? (
                  <span className="font-mono text-xs font-semibold text-indigo-700 bg-indigo-50 px-2 py-0.5 rounded-md border border-indigo-200">
                    Version #{app.current_version_id}
                  </span>
                ) : (
                  <span className="text-slate-400 italic text-[11px]">No active version</span>
                )}
              </td>

              <td className="py-4 px-6 text-slate-500 whitespace-nowrap">
                <div className="flex items-center gap-1.5">
                  <Calendar className="w-3.5 h-3.5 text-slate-400" />
                  <span>{formatDate(app.updated_at)}</span>
                </div>
              </td>

              <td className="py-4 px-6 text-right whitespace-nowrap">
                <div className="flex items-center justify-end gap-1.5">
                  <button
                    type="button"
                    onClick={() => onViewVersions(app)}
                    className="inline-flex items-center gap-1 px-2.5 py-1.5 text-xs font-semibold text-rose-800 bg-rose-50 hover:bg-rose-100 border border-rose-200/80 rounded-lg transition-colors shadow-2xs"
                    title={`Manage versions for ${app.display_name}`}
                  >
                    <Layers className="w-3.5 h-3.5 text-rose-600" />
                    <span>Versions</span>
                  </button>

                  <button
                    type="button"
                    onClick={() => onEditApp(app)}
                    className="p-1.5 rounded-lg text-slate-500 hover:text-indigo-600 hover:bg-indigo-50 transition-colors"
                    title={`Edit ${app.display_name}`}
                  >
                    <Pencil className="w-3.5 h-3.5" />
                  </button>
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

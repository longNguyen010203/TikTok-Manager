import React from "react";
import { Plus, RefreshCw, Search, SlidersHorizontal } from "lucide-react";
import { WorkflowStatus, WorkflowTemplate } from "@/types/workflow";
import { Runtime } from "@/types/runtime";
import { ContentAsset } from "@/types/content";
import { Device } from "@/types/device";

interface WorkflowToolbarProps {
  searchQuery: string;
  onSearchChange: (value: string) => void;
  statusFilter: WorkflowStatus | "all";
  onStatusChange: (status: WorkflowStatus | "all") => void;
  templateFilter: string;
  onTemplateChange: (template: string) => void;
  runtimeFilter: number | "all";
  onRuntimeChange: (runtimeId: number | "all") => void;
  contentFilter: number | "all";
  onContentChange: (contentId: number | "all") => void;
  templates: WorkflowTemplate[];
  runtimes: Runtime[];
  devicesMap: Record<number, Device>;
  contentAssets: ContentAsset[];
  onRefresh: () => void;
  onCreateOpen: () => void;
  isLoading: boolean;
}

export function WorkflowToolbar({
  searchQuery,
  onSearchChange,
  statusFilter,
  onStatusChange,
  templateFilter,
  onTemplateChange,
  runtimeFilter,
  onRuntimeChange,
  contentFilter,
  onContentChange,
  templates,
  runtimes,
  devicesMap,
  contentAssets,
  onRefresh,
  onCreateOpen,
  isLoading,
}: WorkflowToolbarProps) {
  const statuses: Array<{ value: WorkflowStatus | "all"; label: string }> = [
    { value: "all", label: "All Statuses" },
    { value: "pending", label: "Pending" },
    { value: "running", label: "Running" },
    { value: "waiting", label: "Waiting" },
    { value: "paused", label: "Paused" },
    { value: "succeeded", label: "Succeeded" },
    { value: "failed", label: "Failed" },
    { value: "cancelling", label: "Cancelling" },
    { value: "cancelled", label: "Cancelled" },
    { value: "draft", label: "Draft" },
  ];

  return (
    <div className="bg-white rounded-xl border border-slate-200 p-4 shadow-xs space-y-3">
      {/* Top row: search + action buttons */}
      <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3">
        {/* Search input */}
        <div className="relative flex-1 max-w-md">
          <Search className="absolute left-3 top-2.5 w-4 h-4 text-slate-400" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => onSearchChange(e.target.value)}
            placeholder="Search workflows by name..."
            className="w-full text-xs pl-9 pr-3 py-2 bg-slate-50 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-rose-500 focus:bg-white transition-all"
          />
        </div>

        {/* Buttons */}
        <div className="flex items-center gap-2 shrink-0">
          <button
            type="button"
            onClick={onRefresh}
            disabled={isLoading}
            className="inline-flex items-center gap-1.5 px-3 py-2 text-xs font-medium text-slate-700 bg-white border border-slate-300 hover:bg-slate-50 rounded-lg shadow-2xs transition-colors disabled:opacity-50"
          >
            <RefreshCw
              className={`w-3.5 h-3.5 text-slate-500 ${
                isLoading ? "animate-spin" : ""
              }`}
            />
            <span className="hidden sm:inline">Refresh</span>
          </button>

          <button
            type="button"
            onClick={onCreateOpen}
            className="inline-flex items-center gap-1.5 px-3.5 py-2 text-xs font-semibold text-white bg-rose-600 hover:bg-rose-700 rounded-lg shadow-sm transition-colors"
          >
            <Plus className="w-4 h-4" />
            <span>Create Workflow</span>
          </button>
        </div>
      </div>

      {/* Filter Row */}
      <div className="flex flex-wrap items-center gap-2 pt-2 border-t border-slate-100 text-xs">
        <div className="flex items-center gap-1 text-slate-500 mr-1">
          <SlidersHorizontal className="w-3.5 h-3.5" />
          <span className="text-[11px] font-medium uppercase tracking-wider">
            Filters:
          </span>
        </div>

        {/* Status Filter */}
        <select
          value={statusFilter}
          onChange={(e) =>
            onStatusChange(e.target.value as WorkflowStatus | "all")
          }
          className="text-xs px-2.5 py-1.5 bg-slate-50 border border-slate-200 rounded-md focus:outline-none focus:ring-1 focus:ring-rose-500"
        >
          {statuses.map((s) => (
            <option key={s.value} value={s.value}>
              {s.label}
            </option>
          ))}
        </select>

        {/* Template Filter */}
        <select
          value={templateFilter}
          onChange={(e) => onTemplateChange(e.target.value)}
          className="text-xs px-2.5 py-1.5 bg-slate-50 border border-slate-200 rounded-md focus:outline-none focus:ring-1 focus:ring-rose-500"
        >
          <option value="all">All Templates</option>
          {templates.map((tpl) => (
            <option key={tpl.key} value={tpl.key}>
              {tpl.label} (v{tpl.version})
            </option>
          ))}
        </select>

        {/* Runtime Filter */}
        <select
          value={runtimeFilter}
          onChange={(e) =>
            onRuntimeChange(
              e.target.value === "all" ? "all" : Number(e.target.value)
            )
          }
          className="text-xs px-2.5 py-1.5 bg-slate-50 border border-slate-200 rounded-md focus:outline-none focus:ring-1 focus:ring-rose-500"
        >
          <option value="all">All Runtimes</option>
          {runtimes.map((rt) => {
            const dev = devicesMap[rt.device_id];
            const name = dev?.name || `Runtime #${rt.id}`;
            return (
              <option key={rt.id} value={rt.id}>
                {name}
              </option>
            );
          })}
        </select>

        {/* Content Filter */}
        <select
          value={contentFilter}
          onChange={(e) =>
            onContentChange(
              e.target.value === "all" ? "all" : Number(e.target.value)
            )
          }
          className="text-xs px-2.5 py-1.5 bg-slate-50 border border-slate-200 rounded-md focus:outline-none focus:ring-1 focus:ring-rose-500"
        >
          <option value="all">All Content</option>
          {contentAssets.map((asset) => (
            <option key={asset.id} value={asset.id}>
              {asset.display_name}
            </option>
          ))}
        </select>
      </div>
    </div>
  );
}

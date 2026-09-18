import React from "react";
import { Search, Plus, X, Filter, Server } from "lucide-react";

interface RuntimeToolbarProps {
  search: string;
  onSearchChange: (value: string) => void;
  status: string;
  onStatusChange: (status: string) => void;
  onCreateClick: () => void;
  apiBaseUrl?: string;
}

export function RuntimeToolbar({
  search,
  onSearchChange,
  status,
  onStatusChange,
  onCreateClick,
  apiBaseUrl,
}: RuntimeToolbarProps) {
  return (
    <div className="p-4 sm:p-6 border-b border-slate-200/80 bg-white flex flex-col md:flex-row items-stretch md:items-center justify-between gap-3">
      {/* Search and Filters */}
      <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-3 flex-1">
        {/* Search input */}
        <div className="relative flex-1 max-w-md">
          <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
          <input
            type="text"
            value={search}
            onChange={(e) => onSearchChange(e.target.value)}
            placeholder="Search by runtime name, type, device..."
            className="w-full bg-slate-50 border border-slate-200 rounded-lg pl-9 pr-8 py-2 text-xs text-slate-800 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-rose-500/20 focus:border-rose-500 transition-all"
          />
          {search && (
            <button
              type="button"
              onClick={() => onSearchChange("")}
              className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 p-0.5"
              aria-label="Clear search"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          )}
        </div>

        {/* Status filter dropdown */}
        <div className="flex items-center gap-2">
          <div className="relative flex items-center">
            <Filter className="w-3.5 h-3.5 absolute left-2.5 text-slate-400 pointer-events-none" />
            <select
              value={status}
              onChange={(e) => onStatusChange(e.target.value)}
              className="bg-slate-50 border border-slate-200 rounded-lg pl-8 pr-7 py-2 text-xs text-slate-700 focus:outline-none focus:ring-2 focus:ring-rose-500/20 focus:border-rose-500 appearance-none font-medium"
              aria-label="Filter by runtime status"
            >
              <option value="all">All Statuses</option>
              <option value="running">Running</option>
              <option value="idle">Idle</option>
              <option value="stopped">Stopped</option>
              <option value="error">Error</option>
            </select>
          </div>
        </div>
      </div>

      {/* Action buttons & Backend Host Indicator */}
      <div className="flex items-center gap-2 self-end md:self-auto">
        {apiBaseUrl && (
          <div
            className="hidden xl:flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-slate-50 border border-slate-200 text-[11px] text-slate-500 font-mono"
            title={`Backend Base URL: ${apiBaseUrl}`}
          >
            <Server className="w-3 h-3 text-slate-400" />
            <span className="truncate max-w-[140px]">{apiBaseUrl.replace(/^https?:\/\//, "")}</span>
          </div>
        )}

        {/* Create runtime button */}
        <button
          type="button"
          onClick={onCreateClick}
          className="inline-flex items-center gap-1.5 px-4 py-2 bg-rose-600 text-white text-xs font-medium rounded-lg hover:bg-rose-700 transition-colors shadow-2xs cursor-pointer"
        >
          <Plus className="w-4 h-4" />
          <span>Create Runtime</span>
        </button>
      </div>
    </div>
  );
}

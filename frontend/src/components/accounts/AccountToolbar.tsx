"use client";

import React, { useState } from "react";
import {
  Search,
  Plus,
  X,
  Filter,
  Server,
  Archive,
  ChevronDown,
  ChevronUp,
  Cpu,
  Smartphone,
  Tag,
  Folder,
} from "lucide-react";
import { Runtime } from "@/types/runtime";
import { Device } from "@/types/device";

interface AccountToolbarProps {
  search: string;
  onSearchChange: (value: string) => void;
  status: string;
  onStatusChange: (status: string) => void;
  niche: string;
  onNicheChange: (niche: string) => void;
  tag: string;
  onTagChange: (tag: string) => void;
  runtimeId: string;
  onRuntimeIdChange: (runtimeId: string) => void;
  deviceId: string;
  onDeviceIdChange: (deviceId: string) => void;
  includeArchived: boolean;
  onIncludeArchivedChange: (includeArchived: boolean) => void;
  isFiltered: boolean;
  onClearFilters: () => void;
  onCreateClick: () => void;
  runtimes?: Runtime[];
  devicesMap?: Record<number, Device>;
  apiBaseUrl?: string;
}

export function AccountToolbar({
  search,
  onSearchChange,
  status,
  onStatusChange,
  niche,
  onNicheChange,
  tag,
  onTagChange,
  runtimeId,
  onRuntimeIdChange,
  deviceId,
  onDeviceIdChange,
  includeArchived,
  onIncludeArchivedChange,
  isFiltered,
  onClearFilters,
  onCreateClick,
  runtimes = [],
  devicesMap = {},
  apiBaseUrl,
}: AccountToolbarProps) {
  const [showAdvancedFilters, setShowAdvancedFilters] = useState(false);

  const hasAdvancedFilters =
    Boolean(niche.trim()) ||
    Boolean(tag.trim()) ||
    Boolean(runtimeId) ||
    Boolean(deviceId) ||
    includeArchived;

  return (
    <div className="p-4 sm:p-5 border-b border-slate-200/80 bg-white space-y-3">
      {/* Primary Row: Search, Status, Archived Checkbox, Actions */}
      <div className="flex flex-col lg:flex-row items-stretch lg:items-center justify-between gap-3">
        {/* Search input */}
        <div className="relative flex-1 max-w-md">
          <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
          <input
            type="text"
            value={search}
            onChange={(e) => onSearchChange(e.target.value)}
            placeholder="Search by name, @username, email, or niche..."
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

        {/* Filters and Controls */}
        <div className="flex flex-wrap items-center gap-2">
          {/* Status dropdown */}
          <div className="relative flex items-center">
            <Filter className="w-3.5 h-3.5 absolute left-2.5 text-slate-400 pointer-events-none" />
            <select
              value={status}
              onChange={(e) => onStatusChange(e.target.value)}
              className="bg-slate-50 border border-slate-200 rounded-lg pl-8 pr-7 py-2 text-xs text-slate-700 focus:outline-none focus:ring-2 focus:ring-rose-500/20 focus:border-rose-500 appearance-none font-medium"
              aria-label="Filter by account status"
            >
              <option value="all">All Statuses</option>
              <option value="active">Active</option>
              <option value="pending">Pending</option>
              <option value="inactive">Inactive</option>
              <option value="restricted">Restricted</option>
              <option value="suspended">Suspended</option>
              <option value="disabled">Disabled</option>
              <option value="archived">Archived</option>
            </select>
          </div>

          {/* Include Archived toggle */}
          <label className="inline-flex items-center gap-1.5 px-3 py-2 bg-slate-50 border border-slate-200 rounded-lg text-xs font-medium text-slate-700 hover:bg-slate-100 transition-colors cursor-pointer select-none">
            <input
              type="checkbox"
              checked={includeArchived}
              onChange={(e) => onIncludeArchivedChange(e.target.checked)}
              className="w-3.5 h-3.5 rounded text-purple-600 border-slate-300 focus:ring-purple-500"
            />
            <Archive className="w-3.5 h-3.5 text-purple-600" />
            <span>Include Archived</span>
          </label>

          {/* Toggle More Filters */}
          <button
            type="button"
            onClick={() => setShowAdvancedFilters((prev) => !prev)}
            className={`inline-flex items-center gap-1.5 px-3 py-2 border rounded-lg text-xs font-medium transition-colors cursor-pointer ${
              hasAdvancedFilters || showAdvancedFilters
                ? "bg-rose-50 border-rose-200 text-rose-700"
                : "bg-slate-50 border-slate-200 text-slate-700 hover:bg-slate-100"
            }`}
          >
            <span>Filters</span>
            {hasAdvancedFilters && (
              <span className="w-1.5 h-1.5 rounded-full bg-rose-600" />
            )}
            {showAdvancedFilters ? (
              <ChevronUp className="w-3.5 h-3.5" />
            ) : (
              <ChevronDown className="w-3.5 h-3.5" />
            )}
          </button>

          {/* Clear Filters */}
          {isFiltered && (
            <button
              type="button"
              onClick={onClearFilters}
              className="inline-flex items-center gap-1 px-2.5 py-2 text-xs font-medium text-slate-500 hover:text-rose-600 hover:bg-rose-50 rounded-lg transition-colors cursor-pointer"
              title="Reset all search and filter criteria"
            >
              <X className="w-3.5 h-3.5" />
              <span>Reset</span>
            </button>
          )}

          {/* Backend Host pill */}
          {apiBaseUrl && (
            <div
              className="hidden 2xl:flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-slate-50 border border-slate-200 text-[11px] text-slate-500 font-mono"
              title={`Backend Base URL: ${apiBaseUrl}`}
            >
              <Server className="w-3 h-3 text-slate-400" />
              <span className="truncate max-w-[130px]">
                {apiBaseUrl.replace(/^https?:\/\//, "")}
              </span>
            </div>
          )}

          {/* Create account button */}
          <button
            type="button"
            onClick={onCreateClick}
            className="inline-flex items-center gap-1.5 px-3.5 py-2 bg-rose-600 text-white text-xs font-medium rounded-lg hover:bg-rose-700 transition-colors shadow-2xs cursor-pointer ml-auto sm:ml-0"
          >
            <Plus className="w-4 h-4" />
            <span>Create Account</span>
          </button>
        </div>
      </div>

      {/* Advanced Filter Tray */}
      {showAdvancedFilters && (
        <div className="pt-3 border-t border-slate-100 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-2.5 animate-in fade-in slide-in-from-top-1 duration-100 text-xs">
          {/* Niche Filter */}
          <div className="relative">
            <Folder className="w-3.5 h-3.5 absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none" />
            <input
              type="text"
              value={niche}
              onChange={(e) => onNicheChange(e.target.value)}
              placeholder="Filter by niche..."
              className="w-full bg-slate-50 border border-slate-200 rounded-lg pl-8 pr-3 py-1.5 text-xs text-slate-800 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-rose-500/20"
            />
          </div>

          {/* Tag Filter */}
          <div className="relative">
            <Tag className="w-3.5 h-3.5 absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none" />
            <input
              type="text"
              value={tag}
              onChange={(e) => onTagChange(e.target.value)}
              placeholder="Filter by tag..."
              className="w-full bg-slate-50 border border-slate-200 rounded-lg pl-8 pr-3 py-1.5 text-xs text-slate-800 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-rose-500/20"
            />
          </div>

          {/* Runtime Filter */}
          <div className="relative">
            <Cpu className="w-3.5 h-3.5 absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none" />
            <select
              value={runtimeId}
              onChange={(e) => onRuntimeIdChange(e.target.value)}
              className="w-full bg-slate-50 border border-slate-200 rounded-lg pl-8 pr-3 py-1.5 text-xs text-slate-700 focus:outline-none focus:ring-2 focus:ring-rose-500/20 appearance-none font-medium"
            >
              <option value="">All Runtimes</option>
              {runtimes.map((rt) => (
                <option key={rt.id} value={rt.id}>
                  {rt.name} (#{rt.id})
                </option>
              ))}
            </select>
          </div>

          {/* Device Filter */}
          <div className="relative">
            <Smartphone className="w-3.5 h-3.5 absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none" />
            <select
              value={deviceId}
              onChange={(e) => onDeviceIdChange(e.target.value)}
              className="w-full bg-slate-50 border border-slate-200 rounded-lg pl-8 pr-3 py-1.5 text-xs text-slate-700 focus:outline-none focus:ring-2 focus:ring-rose-500/20 appearance-none font-medium"
            >
              <option value="">All Derived Devices</option>
              {Object.values(devicesMap).map((dev) => (
                <option key={dev.id} value={dev.id}>
                  {dev.name} (#{dev.id})
                </option>
              ))}
            </select>
          </div>
        </div>
      )}
    </div>
  );
}

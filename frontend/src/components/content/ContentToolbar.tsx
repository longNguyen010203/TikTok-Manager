import {
  Plus,
  RotateCcw,
  Search,
  X,
} from "lucide-react";
import { ContentAssetStatus, ContentAssetType } from "@/types/content";

interface ContentToolbarProps {
  searchQuery: string;
  onSearchChange: (value: string) => void;
  selectedType: ContentAssetType | "all";
  onTypeChange: (value: ContentAssetType | "all") => void;
  selectedStatus: ContentAssetStatus | "active";
  onStatusChange: (value: ContentAssetStatus | "active") => void;
  tagFilter: string;
  onTagFilterChange: (value: string) => void;
  onUploadClick: () => void;
  onRefresh: () => void;
  isLoading: boolean;
}

export function ContentToolbar({
  searchQuery,
  onSearchChange,
  selectedType,
  onTypeChange,
  selectedStatus,
  onStatusChange,
  tagFilter,
  onTagFilterChange,
  onUploadClick,
  onRefresh,
  isLoading,
}: ContentToolbarProps) {
  const hasActiveFilters =
    searchQuery ||
    selectedType !== "all" ||
    selectedStatus !== "active" ||
    tagFilter;

  const handleResetFilters = () => {
    onSearchChange("");
    onTypeChange("all");
    onStatusChange("active");
    onTagFilterChange("");
  };

  return (
    <div className="space-y-3 rounded-xl border border-slate-200 bg-white p-4 shadow-2xs">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        {/* Search bar */}
        <div className="relative flex-1">
          <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => onSearchChange(e.target.value)}
            placeholder="Search content by name or notes..."
            className="w-full rounded-lg border border-slate-200 bg-slate-50 pl-10 pr-4 py-2 text-sm text-slate-800 placeholder-slate-400 focus:border-blue-500 focus:bg-white focus:outline-hidden"
          />
          {searchQuery && (
            <button
              type="button"
              onClick={() => onSearchChange("")}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
            >
              <X className="w-4 h-4" />
            </button>
          )}
        </div>

        {/* Right side actions */}
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={onRefresh}
            disabled={isLoading}
            className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-50 transition-colors"
            title="Refresh library"
          >
            <RotateCcw
              className={`w-3.5 h-3.5 text-slate-500 ${
                isLoading ? "animate-spin" : ""
              }`}
            />
            <span>Refresh</span>
          </button>

          <button
            type="button"
            onClick={onUploadClick}
            className="inline-flex items-center gap-1.5 rounded-lg bg-blue-600 px-4 py-2 text-xs font-semibold text-white shadow-2xs hover:bg-blue-700 transition-colors"
          >
            <Plus className="w-4 h-4" />
            <span>Upload Content</span>
          </button>
        </div>
      </div>

      {/* Filter Row */}
      <div className="flex flex-wrap items-center gap-2 pt-2 border-t border-slate-100 text-xs">
        {/* Type Filter */}
        <div className="flex items-center gap-1.5">
          <span className="text-slate-400 font-medium">Type:</span>
          <select
            value={selectedType}
            onChange={(e) =>
              onTypeChange(e.target.value as ContentAssetType | "all")
            }
            className="rounded-lg border border-slate-200 bg-slate-50 px-2.5 py-1.5 text-xs text-slate-700 font-medium focus:border-blue-500 focus:outline-hidden"
          >
            <option value="all">All Types</option>
            <option value="video">Videos</option>
            <option value="image">Images</option>
            <option value="audio">Audio</option>
            <option value="other">Other</option>
          </select>
        </div>

        {/* Status Filter */}
        <div className="flex items-center gap-1.5">
          <span className="text-slate-400 font-medium">Status:</span>
          <select
            value={selectedStatus}
            onChange={(e) =>
              onStatusChange(e.target.value as ContentAssetStatus | "active")
            }
            className="rounded-lg border border-slate-200 bg-slate-50 px-2.5 py-1.5 text-xs text-slate-700 font-medium focus:border-blue-500 focus:outline-hidden"
          >
            <option value="active">Active (Ready &amp; Processing)</option>
            <option value="ready">Ready</option>
            <option value="processing">Processing</option>
            <option value="invalid">Invalid</option>
            <option value="archived">Archived</option>
            <option value="deleted">Deleted</option>
          </select>
        </div>

        {/* Tag Filter */}
        <div className="flex items-center gap-1.5">
          <span className="text-slate-400 font-medium">Tag:</span>
          <div className="relative">
            <input
              type="text"
              value={tagFilter}
              onChange={(e) => onTagFilterChange(e.target.value)}
              placeholder="Filter by tag..."
              className="w-32 sm:w-40 rounded-lg border border-slate-200 bg-slate-50 px-2.5 py-1.5 text-xs text-slate-700 placeholder-slate-400 focus:border-blue-500 focus:bg-white focus:outline-hidden"
            />
            {tagFilter && (
              <button
                type="button"
                onClick={() => onTagFilterChange("")}
                className="absolute right-2 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
              >
                <X className="w-3 h-3" />
              </button>
            )}
          </div>
        </div>

        {/* Clear Filters CTA */}
        {hasActiveFilters && (
          <button
            type="button"
            onClick={handleResetFilters}
            className="inline-flex items-center gap-1 text-xs text-slate-500 hover:text-rose-600 transition-colors ml-auto"
          >
            <X className="w-3.5 h-3.5" />
            <span>Clear filters</span>
          </button>
        )}
      </div>
    </div>
  );
}

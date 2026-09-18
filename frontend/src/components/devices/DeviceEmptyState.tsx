import React from "react";
import { Smartphone, Plus, RefreshCw } from "lucide-react";

interface DeviceEmptyStateProps {
  isFiltered: boolean;
  onClearFilters?: () => void;
  onCreateDevice?: () => void;
}

export function DeviceEmptyState({
  isFiltered,
  onClearFilters,
  onCreateDevice,
}: DeviceEmptyStateProps) {
  return (
    <div className="py-16 px-4 text-center max-w-md mx-auto">
      <div className="w-12 h-12 rounded-full bg-slate-100 text-slate-400 mx-auto flex items-center justify-center mb-3">
        <Smartphone className="w-6 h-6" />
      </div>
      <h3 className="text-sm font-semibold text-slate-900 mb-1">
        {isFiltered ? "No matching devices found" : "No devices registered yet"}
      </h3>
      <p className="text-xs text-slate-500 mb-5 leading-relaxed">
        {isFiltered
          ? "No devices match your current filter and search query. Try adjusting your search term or resetting the status filter."
          : "Add your first physical device, Android emulator, or cloud instance to host TikTok automation runtimes."}
      </p>
      <div className="flex items-center justify-center gap-2">
        {isFiltered && onClearFilters && (
          <button
            type="button"
            onClick={onClearFilters}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-slate-200 text-xs font-medium text-slate-700 hover:bg-slate-50 transition-colors"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            Reset filters
          </button>
        )}
        {onCreateDevice && (
          <button
            type="button"
            onClick={onCreateDevice}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-rose-600 text-xs font-medium text-white hover:bg-rose-700 transition-colors shadow-2xs"
          >
            <Plus className="w-3.5 h-3.5" />
            Add Device
          </button>
        )}
      </div>
    </div>
  );
}

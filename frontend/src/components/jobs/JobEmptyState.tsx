import { ListChecks, RotateCcw } from "lucide-react";

export function JobEmptyState({
  isFiltered,
  onClearFilters,
}: {
  isFiltered: boolean;
  onClearFilters: () => void;
}) {
  return (
    <div className="mx-auto max-w-md px-4 py-16 text-center">
      <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-slate-100 text-slate-400">
        <ListChecks className="h-6 w-6" />
      </div>
      <h3 className="mb-1 text-sm font-semibold text-slate-900">
        {isFiltered ? "No matching jobs" : "The job queue is empty"}
      </h3>
      <p className="mb-5 text-xs leading-relaxed text-slate-500">
        {isFiltered
          ? "No jobs match the current filters or search on this page. Adjust the criteria and try again."
          : "Jobs will appear here after they are submitted to the backend queue."}
      </p>
      {isFiltered && (
        <button
          type="button"
          onClick={onClearFilters}
          className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 px-3 py-1.5 text-xs font-medium text-slate-700 transition-colors hover:bg-slate-50"
        >
          <RotateCcw className="h-3.5 w-3.5" />
          Reset filters
        </button>
      )}
    </div>
  );
}

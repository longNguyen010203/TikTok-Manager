import React from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";

interface WorkflowPaginationProps {
  currentPage: number;
  pageSize: number;
  total: number;
  onPageChange: (page: number) => void;
  onPageSizeChange: (pageSize: number) => void;
}

export function WorkflowPagination({
  currentPage,
  pageSize,
  total,
  onPageChange,
  onPageSizeChange,
}: WorkflowPaginationProps) {
  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  const firstItem = total === 0 ? 0 : (currentPage - 1) * pageSize + 1;
  const lastItem = Math.min(total, currentPage * pageSize);
  const firstPageButton = Math.max(
    1,
    Math.min(currentPage - 2, totalPages - 4)
  );
  const pageNumbers = Array.from(
    { length: Math.min(5, totalPages) },
    (_, index) => firstPageButton + index
  );

  return (
    <div className="flex flex-col items-center justify-between gap-4 border-t border-slate-200/80 bg-slate-50/50 px-4 py-4 sm:flex-row sm:px-6 rounded-b-xl">
      <div className="flex items-center gap-3 text-xs text-slate-600">
        <span>
          Showing{" "}
          <strong className="font-semibold text-slate-900">{firstItem}</strong>{" "}
          to <strong className="font-semibold text-slate-900">{lastItem}</strong>{" "}
          of <strong className="font-semibold text-slate-900">{total}</strong>{" "}
          workflows
        </span>
        <div className="hidden items-center gap-1.5 border-l border-slate-200 pl-3 sm:flex">
          <label htmlFor="workflowPageSize" className="text-slate-500">
            Per page:
          </label>
          <select
            id="workflowPageSize"
            value={pageSize}
            onChange={(e) => onPageSizeChange(Number(e.target.value))}
            className="rounded border border-slate-200 bg-white px-2 py-0.5 text-xs text-slate-700 focus:outline-none focus:ring-1 focus:ring-rose-500"
          >
            <option value={10}>10</option>
            <option value={20}>20</option>
            <option value={50}>50</option>
            <option value={100}>100</option>
          </select>
        </div>
      </div>

      <div className="flex items-center gap-1">
        <button
          type="button"
          onClick={() => onPageChange(currentPage - 1)}
          disabled={currentPage <= 1}
          className="inline-flex items-center justify-center p-1.5 rounded-md border border-slate-200 bg-white text-slate-600 hover:bg-slate-50 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          aria-label="Previous Page"
        >
          <ChevronLeft className="w-4 h-4" />
        </button>

        {pageNumbers.map((num) => (
          <button
            key={num}
            type="button"
            onClick={() => onPageChange(num)}
            className={`min-w-8 h-8 px-2 text-xs font-semibold rounded-md border transition-colors ${
              num === currentPage
                ? "bg-rose-600 text-white border-rose-600 shadow-xs"
                : "bg-white text-slate-700 border-slate-200 hover:bg-slate-50"
            }`}
          >
            {num}
          </button>
        ))}

        <button
          type="button"
          onClick={() => onPageChange(currentPage + 1)}
          disabled={currentPage >= totalPages}
          className="inline-flex items-center justify-center p-1.5 rounded-md border border-slate-200 bg-white text-slate-600 hover:bg-slate-50 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          aria-label="Next Page"
        >
          <ChevronRight className="w-4 h-4" />
        </button>
      </div>
    </div>
  );
}

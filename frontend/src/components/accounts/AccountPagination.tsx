import React from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";

interface AccountPaginationProps {
  currentPage: number;
  pageSize: number;
  total: number;
  onPageChange: (page: number) => void;
  onPageSizeChange: (pageSize: number) => void;
}

export function AccountPagination({
  currentPage,
  pageSize,
  total,
  onPageChange,
  onPageSizeChange,
}: AccountPaginationProps) {
  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  const startItem = total === 0 ? 0 : (currentPage - 1) * pageSize + 1;
  const endItem = Math.min(total, currentPage * pageSize);

  // Generate page numbers to show
  const getPageNumbers = () => {
    const pages: number[] = [];
    const maxVisible = 5;
    let start = Math.max(1, currentPage - 2);
    const end = Math.min(totalPages, start + maxVisible - 1);

    if (end - start + 1 < maxVisible) {
      start = Math.max(1, end - maxVisible + 1);
    }

    for (let i = start; i <= end; i++) {
      pages.push(i);
    }
    return pages;
  };

  return (
    <div className="px-6 py-4 border-t border-slate-200/80 bg-slate-50/50 flex flex-col sm:flex-row items-center justify-between gap-4">
      {/* Total count / range */}
      <div className="flex items-center gap-3 text-xs text-slate-600">
        <span>
          Showing <strong className="font-semibold text-slate-900">{startItem}</strong> to{" "}
          <strong className="font-semibold text-slate-900">{endItem}</strong> of{" "}
          <strong className="font-semibold text-slate-900">{total}</strong> accounts
        </span>

        <div className="hidden sm:flex items-center gap-1.5 pl-3 border-l border-slate-200">
          <label htmlFor="pageSizeSelect" className="text-slate-500 text-xs">
            Per page:
          </label>
          <select
            id="pageSizeSelect"
            value={pageSize}
            onChange={(e) => onPageSizeChange(Number(e.target.value))}
            className="bg-white border border-slate-200 rounded px-1.5 py-0.5 text-xs text-slate-700 focus:outline-none focus:ring-1 focus:ring-rose-500"
          >
            <option value={5}>5</option>
            <option value={10}>10</option>
            <option value={20}>20</option>
          </select>
        </div>
      </div>

      {/* Page navigation controls */}
      <div className="flex items-center gap-1">
        <button
          type="button"
          onClick={() => onPageChange(currentPage - 1)}
          disabled={currentPage <= 1}
          className="p-1.5 rounded-lg border border-slate-200 text-slate-600 hover:bg-white disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          aria-label="Previous Page"
        >
          <ChevronLeft className="w-4 h-4" />
        </button>

        <div className="flex items-center gap-1">
          {getPageNumbers().map((pageNum) => (
            <button
              key={pageNum}
              type="button"
              onClick={() => onPageChange(pageNum)}
              className={`min-w-[32px] h-8 px-2 rounded-lg text-xs font-medium transition-colors ${
                currentPage === pageNum
                  ? "bg-rose-600 text-white shadow-2xs"
                  : "text-slate-600 hover:bg-white hover:text-slate-900 border border-transparent hover:border-slate-200"
              }`}
            >
              {pageNum}
            </button>
          ))}
        </div>

        <button
          type="button"
          onClick={() => onPageChange(currentPage + 1)}
          disabled={currentPage >= totalPages}
          className="p-1.5 rounded-lg border border-slate-200 text-slate-600 hover:bg-white disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          aria-label="Next Page"
        >
          <ChevronRight className="w-4 h-4" />
        </button>
      </div>
    </div>
  );
}

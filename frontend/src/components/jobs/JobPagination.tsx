import { ChevronLeft, ChevronRight } from "lucide-react";

interface JobPaginationProps {
  currentPage: number;
  pageSize: number;
  total: number;
  onPageChange: (page: number) => void;
  onPageSizeChange: (pageSize: number) => void;
}

export function JobPagination({
  currentPage,
  pageSize,
  total,
  onPageChange,
  onPageSizeChange,
}: JobPaginationProps) {
  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  const firstItem = total === 0 ? 0 : (currentPage - 1) * pageSize + 1;
  const lastItem = Math.min(total, currentPage * pageSize);
  const firstPageButton = Math.max(
    1,
    Math.min(currentPage - 2, totalPages - 4),
  );
  const pageNumbers = Array.from(
    { length: Math.min(5, totalPages) },
    (_, index) => firstPageButton + index,
  );

  return (
    <div className="flex flex-col items-center justify-between gap-4 border-t border-slate-200/80 bg-slate-50/50 px-4 py-4 sm:flex-row sm:px-6">
      <div className="flex items-center gap-3 text-xs text-slate-600">
        <span>
          Showing <strong className="font-semibold text-slate-900">{firstItem}</strong>{" "}
          to <strong className="font-semibold text-slate-900">{lastItem}</strong>{" "}
          of <strong className="font-semibold text-slate-900">{total}</strong> jobs
        </span>
        <div className="hidden items-center gap-1.5 border-l border-slate-200 pl-3 sm:flex">
          <label htmlFor="jobPageSize" className="text-slate-500">
            Per page:
          </label>
          <select
            id="jobPageSize"
            value={pageSize}
            onChange={(event) => onPageSizeChange(Number(event.target.value))}
            className="rounded border border-slate-200 bg-white px-1.5 py-0.5 text-xs text-slate-700 focus:outline-none focus:ring-1 focus:ring-rose-500"
          >
            <option value={5}>5</option>
            <option value={10}>10</option>
            <option value={20}>20</option>
            <option value={50}>50</option>
          </select>
        </div>
      </div>

      <div className="flex items-center gap-1">
        <button
          type="button"
          onClick={() => onPageChange(currentPage - 1)}
          disabled={currentPage <= 1}
          className="rounded-lg border border-slate-200 p-1.5 text-slate-600 transition-colors hover:bg-white disabled:cursor-not-allowed disabled:opacity-40"
          aria-label="Previous page"
        >
          <ChevronLeft className="h-4 w-4" />
        </button>
        {pageNumbers.map((page) => (
          <button
            key={page}
            type="button"
            onClick={() => onPageChange(page)}
            className={`h-8 min-w-8 rounded-lg px-2 text-xs font-medium transition-colors ${
              page === currentPage
                ? "bg-rose-600 text-white shadow-2xs"
                : "border border-transparent text-slate-600 hover:border-slate-200 hover:bg-white"
            }`}
          >
            {page}
          </button>
        ))}
        <button
          type="button"
          onClick={() => onPageChange(currentPage + 1)}
          disabled={currentPage >= totalPages}
          className="rounded-lg border border-slate-200 p-1.5 text-slate-600 transition-colors hover:bg-white disabled:cursor-not-allowed disabled:opacity-40"
          aria-label="Next page"
        >
          <ChevronRight className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
}

import { ChevronLeft, ChevronRight } from "lucide-react";

interface ContentPaginationProps {
  currentPage: number;
  pageSize: number;
  total: number;
  onPageChange: (page: number) => void;
  onPageSizeChange: (pageSize: number) => void;
}

export function ContentPagination({
  currentPage,
  pageSize,
  total,
  onPageChange,
  onPageSizeChange,
}: ContentPaginationProps) {
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
          Showing <strong className="font-semibold text-slate-900">{firstItem}</strong>{" "}
          to <strong className="font-semibold text-slate-900">{lastItem}</strong>{" "}
          of <strong className="font-semibold text-slate-900">{total}</strong> assets
        </span>
        <div className="hidden items-center gap-1.5 border-l border-slate-200 pl-3 sm:flex">
          <label htmlFor="contentPageSize" className="text-slate-500">
            Per page:
          </label>
          <select
            id="contentPageSize"
            value={pageSize}
            onChange={(event) => onPageSizeChange(Number(event.target.value))}
            className="rounded border border-slate-200 bg-white px-1.5 py-0.5 text-xs text-slate-700 focus:outline-hidden focus:ring-1 focus:ring-blue-500"
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
          className="inline-flex h-8 w-8 items-center justify-center rounded-lg border border-slate-200 bg-white text-slate-600 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-40 transition-colors"
          aria-label="Previous page"
        >
          <ChevronLeft className="h-4 w-4" />
        </button>

        {pageNumbers.map((pageNumber) => (
          <button
            key={pageNumber}
            type="button"
            onClick={() => onPageChange(pageNumber)}
            className={`inline-flex h-8 min-w-8 items-center justify-center rounded-lg px-2 text-xs font-semibold transition-colors ${
              pageNumber === currentPage
                ? "bg-blue-600 text-white"
                : "border border-slate-200 bg-white text-slate-700 hover:bg-slate-50"
            }`}
          >
            {pageNumber}
          </button>
        ))}

        <button
          type="button"
          onClick={() => onPageChange(currentPage + 1)}
          disabled={currentPage >= totalPages}
          className="inline-flex h-8 w-8 items-center justify-center rounded-lg border border-slate-200 bg-white text-slate-600 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-40 transition-colors"
          aria-label="Next page"
        >
          <ChevronRight className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
}

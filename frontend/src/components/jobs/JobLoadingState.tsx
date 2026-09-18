export function JobLoadingState({ rows = 6 }: { rows?: number }) {
  return (
    <div className="animate-pulse divide-y divide-slate-100">
      {Array.from({ length: rows }).map((_, index) => (
        <div
          key={index}
          className="flex items-center gap-5 px-5 py-4 sm:px-6"
        >
          <div className="h-4 w-10 rounded bg-slate-200" />
          <div className="min-w-[150px] flex-1 space-y-2">
            <div className="h-3.5 w-32 rounded bg-slate-200" />
            <div className="h-2.5 w-20 rounded bg-slate-100" />
          </div>
          <div className="hidden h-6 w-20 rounded-full bg-slate-200 sm:block" />
          <div className="hidden h-3 w-28 rounded bg-slate-200 lg:block" />
          <div className="hidden h-3 w-24 rounded bg-slate-200 xl:block" />
          <div className="h-3 w-20 rounded bg-slate-200" />
        </div>
      ))}
    </div>
  );
}

import React from "react";

export function AccountLoadingState({ rows = 5 }: { rows?: number }) {
  return (
    <div className="divide-y divide-slate-100 animate-pulse">
      {Array.from({ length: rows }).map((_, idx) => (
        <div
          key={idx}
          className="px-6 py-4 flex items-center justify-between gap-4"
        >
          <div className="flex items-center gap-3 min-w-[200px] flex-1">
            <div className="w-9 h-9 rounded-full bg-slate-200" />
            <div className="space-y-1.5 flex-1 max-w-[180px]">
              <div className="h-3.5 bg-slate-200 rounded w-3/4" />
              <div className="h-2.5 bg-slate-200 rounded w-1/2" />
            </div>
          </div>
          <div className="hidden sm:block w-32">
            <div className="h-3 bg-slate-200 rounded w-20" />
          </div>
          <div className="hidden md:block w-24">
            <div className="h-5 bg-slate-200 rounded-full w-16" />
          </div>
          <div className="w-24">
            <div className="h-5 bg-slate-200 rounded-full w-20" />
          </div>
          <div className="hidden lg:block w-36">
            <div className="h-3 bg-slate-200 rounded w-28" />
          </div>
        </div>
      ))}
    </div>
  );
}

"use client";

import React from "react";
import { Loader2 } from "lucide-react";

export function TopologyLoadingSkeleton() {
  return (
    <div className="space-y-6 animate-pulse">
      {/* Summary Skeleton */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
        {Array.from({ length: 6 }).map((_, i) => (
          <div
            key={i}
            className="p-3 rounded-xl border border-slate-200/80 bg-white h-18 flex items-center gap-3"
          >
            <div className="w-8 h-8 rounded-lg bg-slate-100" />
            <div className="space-y-1.5 flex-1">
              <div className="h-3 w-16 bg-slate-100 rounded" />
              <div className="h-5 w-8 bg-slate-200 rounded" />
            </div>
          </div>
        ))}
      </div>

      {/* Toolbar Skeleton */}
      <div className="h-14 bg-white border border-slate-200/90 rounded-xl" />

      {/* Canvas Skeleton */}
      <div className="w-full h-[620px] bg-slate-100/70 border border-slate-200 rounded-2xl flex flex-col items-center justify-center text-slate-400 gap-3">
        <Loader2 className="w-8 h-8 animate-spin text-rose-600" />
        <span className="text-xs font-medium text-slate-500">
          Loading system topology map...
        </span>
      </div>
    </div>
  );
}

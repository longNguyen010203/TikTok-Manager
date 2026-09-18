import React from "react";
import { Play, Pause, AlertTriangle, Square } from "lucide-react";
import { RuntimeStatus } from "@/types/runtime";

interface RuntimeStatusBadgeProps {
  status: RuntimeStatus;
}

export function RuntimeStatusBadge({ status }: RuntimeStatusBadgeProps) {
  const normalized = status.toLowerCase();

  if (normalized === "running") {
    return (
      <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-emerald-50 text-emerald-700 border border-emerald-200">
        <Play className="w-3 h-3 text-emerald-600 fill-emerald-600" />
        <span>Running</span>
      </span>
    );
  }

  if (normalized === "idle") {
    return (
      <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-blue-50 text-blue-700 border border-blue-200">
        <Pause className="w-3 h-3 text-blue-600" />
        <span>Idle</span>
      </span>
    );
  }

  if (normalized === "stopped") {
    return (
      <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-slate-100 text-slate-700 border border-slate-200">
        <Square className="w-2.5 h-2.5 text-slate-500 fill-slate-500" />
        <span>Stopped</span>
      </span>
    );
  }

  if (normalized === "error") {
    return (
      <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-rose-50 text-rose-700 border border-rose-200">
        <AlertTriangle className="w-3 h-3 text-rose-600" />
        <span>Error</span>
      </span>
    );
  }

  return (
    <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-slate-50 text-slate-600 border border-slate-200">
      <span className="w-1.5 h-1.5 rounded-full bg-slate-400" />
      <span>{status}</span>
    </span>
  );
}

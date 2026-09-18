import React from "react";
import { CheckCircle2, PauseCircle, Clock, AlertTriangle } from "lucide-react";
import { DeviceStatus } from "@/types/device";

interface DeviceStatusBadgeProps {
  status: DeviceStatus;
}

export function DeviceStatusBadge({ status }: DeviceStatusBadgeProps) {
  const normalized = status.toLowerCase();

  if (normalized === "online") {
    return (
      <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-emerald-50 text-emerald-700 border border-emerald-200">
        <CheckCircle2 className="w-3 h-3 text-emerald-600" />
        <span>Online</span>
      </span>
    );
  }

  if (normalized === "busy") {
    return (
      <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-amber-50 text-amber-700 border border-amber-200">
        <Clock className="w-3 h-3 text-amber-600" />
        <span>Busy</span>
      </span>
    );
  }

  if (normalized === "offline") {
    return (
      <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-slate-100 text-slate-700 border border-slate-200">
        <PauseCircle className="w-3 h-3 text-slate-500" />
        <span>Offline</span>
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

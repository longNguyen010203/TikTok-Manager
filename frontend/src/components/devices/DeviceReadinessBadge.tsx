import React from "react";
import {
  CheckCircle2,
  AlertCircle,
  AlertTriangle,
  Loader2,
  Square,
} from "lucide-react";

interface DeviceReadinessBadgeProps {
  ready: boolean;
  runtimeStatus?: string;
  size?: "sm" | "md";
  className?: string;
}

export function DeviceReadinessBadge({
  ready,
  runtimeStatus,
  size = "sm",
  className = "",
}: DeviceReadinessBadgeProps) {
  const normalizedRuntimeStatus = runtimeStatus?.toLowerCase();

  if (ready) {
    return (
      <span
        className={`inline-flex items-center gap-1 font-semibold rounded-full border bg-emerald-50 text-emerald-700 border-emerald-200/80 ${
          size === "md"
            ? "px-2.5 py-1 text-xs"
            : "px-2 py-0.5 text-[11px]"
        } ${className}`}
        title="Device is fully ready: container running, Android boot complete, ADB connected"
      >
        <CheckCircle2
          className={`shrink-0 text-emerald-600 ${
            size === "md" ? "w-3.5 h-3.5" : "w-3 h-3"
          }`}
        />
        <span>Ready</span>
      </span>
    );
  }

  // Transitional: Container is running, waiting for boot
  if (normalizedRuntimeStatus === "starting") {
    return (
      <span
        className={`inline-flex items-center gap-1 font-semibold rounded-full border bg-sky-50 text-sky-700 border-sky-200/80 ${
          size === "md"
            ? "px-2.5 py-1 text-xs"
            : "px-2 py-0.5 text-[11px]"
        } ${className}`}
        title="Transitional state: Container is running, Android OS boot in progress..."
      >
        <Loader2
          className={`shrink-0 text-sky-600 animate-spin ${
            size === "md" ? "w-3.5 h-3.5" : "w-3 h-3"
          }`}
        />
        <span>Starting</span>
      </span>
    );
  }

  // Transitional: Boot complete, but ADB offline / unavailable
  if (normalizedRuntimeStatus === "degraded") {
    return (
      <span
        className={`inline-flex items-center gap-1 font-semibold rounded-full border bg-amber-50 text-amber-700 border-amber-200/80 ${
          size === "md"
            ? "px-2.5 py-1 text-xs"
            : "px-2 py-0.5 text-[11px]"
        } ${className}`}
        title="Transitional state: Android OS booted, but ADB is offline or unavailable. Restart may be required."
      >
        <AlertTriangle
          className={`shrink-0 text-amber-600 ${
            size === "md" ? "w-3.5 h-3.5" : "w-3 h-3"
          }`}
        />
        <span>Degraded</span>
      </span>
    );
  }

  // Stopped: Container halted, data preserved
  if (normalizedRuntimeStatus === "stopped") {
    return (
      <span
        className={`inline-flex items-center gap-1 font-semibold rounded-full border bg-slate-100 text-slate-700 border-slate-300 ${
          size === "md"
            ? "px-2.5 py-1 text-xs"
            : "px-2 py-0.5 text-[11px]"
        } ${className}`}
        title="Container is stopped. Persistent container data is preserved."
      >
        <Square
          className={`shrink-0 text-slate-500 fill-slate-500 ${
            size === "md" ? "w-3 h-3" : "w-2.5 h-2.5"
          }`}
        />
        <span>Stopped</span>
      </span>
    );
  }

  // General not ready fallback
  return (
    <span
      className={`inline-flex items-center gap-1 font-semibold rounded-full border bg-rose-50 text-rose-700 border-rose-200/80 ${
        size === "md"
          ? "px-2.5 py-1 text-xs"
          : "px-2 py-0.5 text-[11px]"
      } ${className}`}
      title="Device is not ready for operations"
    >
      <AlertCircle
        className={`shrink-0 text-rose-600 ${
          size === "md" ? "w-3.5 h-3.5" : "w-3 h-3"
        }`}
      />
      <span>Not Ready</span>
    </span>
  );
}

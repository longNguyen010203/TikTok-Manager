import React from "react";
import { AlertTriangle, RotateCcw } from "lucide-react";

interface DeviceErrorStateProps {
  message: string;
  onRetry: () => void;
}

export function DeviceErrorState({ message, onRetry }: DeviceErrorStateProps) {
  return (
    <div className="py-12 px-4 text-center max-w-md mx-auto">
      <div className="w-12 h-12 rounded-full bg-rose-50 text-rose-600 border border-rose-100 mx-auto flex items-center justify-center mb-3">
        <AlertTriangle className="w-6 h-6" />
      </div>
      <h3 className="text-sm font-semibold text-slate-900 mb-1">
        Failed to load devices
      </h3>
      <p className="text-xs text-slate-500 mb-4 font-mono bg-slate-50 p-2 rounded border border-slate-200 break-words">
        {message}
      </p>
      <button
        type="button"
        onClick={onRetry}
        className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg bg-slate-900 text-xs font-medium text-white hover:bg-slate-800 transition-colors shadow-2xs"
      >
        <RotateCcw className="w-3.5 h-3.5" />
        Retry Request
      </button>
    </div>
  );
}

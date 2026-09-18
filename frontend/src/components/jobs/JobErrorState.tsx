import { AlertTriangle, RotateCcw } from "lucide-react";

export function JobErrorState({
  message,
  onRetry,
}: {
  message: string;
  onRetry: () => void;
}) {
  return (
    <div className="mx-auto max-w-md px-4 py-14 text-center">
      <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-full border border-rose-100 bg-rose-50 text-rose-600">
        <AlertTriangle className="h-6 w-6" />
      </div>
      <h3 className="mb-1 text-sm font-semibold text-slate-900">
        Failed to load the job queue
      </h3>
      <p className="mb-4 break-words rounded-lg border border-slate-200 bg-slate-50 p-2 font-mono text-xs text-slate-500">
        {message}
      </p>
      <button
        type="button"
        onClick={onRetry}
        className="inline-flex items-center gap-1.5 rounded-lg bg-slate-900 px-3.5 py-1.5 text-xs font-medium text-white shadow-2xs transition-colors hover:bg-slate-800"
      >
        <RotateCcw className="h-3.5 w-3.5" />
        Retry request
      </button>
    </div>
  );
}

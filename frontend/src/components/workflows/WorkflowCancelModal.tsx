import React from "react";
import { AlertTriangle, Loader2, OctagonX, X } from "lucide-react";
import { Workflow } from "@/types/workflow";

interface WorkflowCancelModalProps {
  workflow: Workflow | null;
  isOpen: boolean;
  isCancelling: boolean;
  onConfirm: () => void;
  onClose: () => void;
}

export function WorkflowCancelModal({
  workflow,
  isOpen,
  isCancelling,
  onConfirm,
  onClose,
}: WorkflowCancelModalProps) {
  if (!isOpen || !workflow) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-xs">
      <div className="relative w-full max-w-md bg-white rounded-xl shadow-2xl border border-slate-200 overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-200 bg-rose-50/50">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-lg bg-rose-100 text-rose-600 flex items-center justify-center font-bold">
              <OctagonX className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-base font-bold text-slate-900">
                Cancel Workflow
              </h3>
              <p className="text-xs text-slate-500 font-mono">
                Workflow #{workflow.id}
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            disabled={isCancelling}
            className="p-1 rounded-md text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        <div className="p-6 space-y-4 text-xs text-slate-600">
          <div className="p-3 bg-amber-50 border border-amber-200 rounded-lg flex items-start gap-2.5 text-amber-800">
            <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
            <div>
              <p className="font-semibold">Cancellation Notice</p>
              <p className="mt-0.5">
                If an underlying Android automation Job is actively running, it may require a few seconds to terminate safely.
              </p>
            </div>
          </div>

          <p>
            Are you sure you want to cancel{" "}
            <strong className="text-slate-900">&ldquo;{workflow.name}&rdquo;</strong>?
          </p>

          <p className="text-slate-500">
            The workflow status will transition to <strong className="text-slate-700">Cancelling...</strong> while cleanup is coordinated, before reaching terminal cancelled state.
          </p>
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end gap-3 px-6 py-4 border-t border-slate-200 bg-slate-50/50">
          <button
            type="button"
            onClick={onClose}
            disabled={isCancelling}
            className="px-4 py-2 text-xs font-medium text-slate-700 hover:bg-slate-100 rounded-lg transition-colors"
          >
            Keep Running
          </button>
          <button
            type="button"
            onClick={onConfirm}
            disabled={isCancelling}
            className="inline-flex items-center gap-1.5 px-4 py-2 text-xs font-semibold text-white bg-rose-600 hover:bg-rose-700 rounded-lg shadow-sm disabled:opacity-50 transition-colors"
          >
            {isCancelling ? (
              <>
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
                <span>Requesting Cancellation...</span>
              </>
            ) : (
              <span>Confirm Cancel</span>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}

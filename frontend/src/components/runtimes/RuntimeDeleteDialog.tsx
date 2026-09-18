"use client";

import React, { useState } from "react";
import { Trash2, AlertTriangle, Loader2 } from "lucide-react";
import { Runtime, formatApiError } from "@/types/runtime";

interface RuntimeDeleteDialogProps {
  runtime: Runtime | null;
  isOpen: boolean;
  onClose: () => void;
  onConfirm: (id: number) => Promise<void>;
}

export function RuntimeDeleteDialog({
  runtime,
  isOpen,
  onClose,
  onConfirm,
}: RuntimeDeleteDialogProps) {
  const [isDeleting, setIsDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  if (!isOpen || !runtime) return null;

  const handleDelete = async () => {
    setDeleteError(null);
    try {
      setIsDeleting(true);
      await onConfirm(runtime.id);
      onClose();
    } catch (err: unknown) {
      setDeleteError(formatApiError(err));
    } finally {
      setIsDeleting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-xs">
      <div
        className="bg-white rounded-2xl shadow-xl border border-slate-200 w-full max-w-md p-6 space-y-4 animate-in fade-in zoom-in-95 duration-150"
        role="alertdialog"
        aria-modal="true"
        aria-labelledby="runtime-delete-title"
        aria-describedby="runtime-delete-desc"
      >
        <div className="flex items-start gap-3.5">
          <div className="p-2.5 rounded-full bg-rose-100 text-rose-600 shrink-0">
            <AlertTriangle className="w-5 h-5" />
          </div>
          <div className="space-y-1">
            <h3
              id="runtime-delete-title"
              className="text-sm font-semibold text-slate-900"
            >
              Delete Runtime Confirmation
            </h3>
            <p id="runtime-delete-desc" className="text-xs text-slate-500 leading-relaxed">
              Are you sure you want to permanently delete runtime{" "}
              <strong className="text-slate-900 font-semibold">
                {runtime.name}
              </strong>{" "}
              (ID #{runtime.id}, Type: {runtime.runtime_type})? Deleting a runtime
              preserves any assigned TikTok Accounts and safely clears their runtime assignments.
            </p>
          </div>
        </div>

        {deleteError && (
          <div className="p-3 rounded-lg bg-rose-50 border border-rose-200 text-rose-700 text-xs break-words">
            {deleteError}
          </div>
        )}

        <div className="pt-2 flex items-center justify-end gap-2">
          <button
            type="button"
            onClick={onClose}
            disabled={isDeleting}
            className="px-3.5 py-2 border border-slate-200 rounded-lg text-slate-600 hover:bg-slate-50 text-xs font-medium transition-colors disabled:opacity-50"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={handleDelete}
            disabled={isDeleting}
            className="inline-flex items-center gap-1.5 px-4 py-2 bg-rose-600 text-white rounded-lg text-xs font-medium hover:bg-rose-700 transition-colors shadow-2xs disabled:opacity-70"
          >
            {isDeleting ? (
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
            ) : (
              <Trash2 className="w-3.5 h-3.5" />
            )}
            <span>Delete Runtime</span>
          </button>
        </div>
      </div>
    </div>
  );
}

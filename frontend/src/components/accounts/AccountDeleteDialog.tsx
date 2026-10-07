"use client";

import React, { useState } from "react";
import { Archive, Loader2 } from "lucide-react";
import { Account, formatApiError } from "@/types/account";

interface AccountDeleteDialogProps {
  account: Account | null;
  isOpen: boolean;
  onClose: () => void;
  onConfirm: (id: number) => Promise<void>;
}

export function AccountDeleteDialog({
  account,
  isOpen,
  onClose,
  onConfirm,
}: AccountDeleteDialogProps) {
  const [isDeleting, setIsDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  if (!isOpen || !account) return null;

  const handleArchive = async () => {
    setDeleteError(null);
    try {
      setIsDeleting(true);
      await onConfirm(account.id);
      onClose();
    } catch (err: unknown) {
      setDeleteError(formatApiError(err));
    } finally {
      setIsDeleting(false);
    }
  };

  const handleText = account.username ? `@${account.username}` : account.display_name;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-xs">
      <div
        className="bg-white rounded-2xl shadow-xl border border-slate-200 w-full max-w-md p-6 space-y-4 animate-in fade-in zoom-in-95 duration-150"
        role="alertdialog"
        aria-modal="true"
        aria-labelledby="archive-dialog-title"
        aria-describedby="archive-dialog-desc"
      >
        <div className="flex items-start gap-3.5">
          <div className="p-2.5 rounded-full bg-purple-100 text-purple-700 shrink-0">
            <Archive className="w-5 h-5" />
          </div>
          <div className="space-y-1">
            <h3
              id="archive-dialog-title"
              className="text-sm font-semibold text-slate-900"
            >
              Archive Account
            </h3>
            <p id="archive-dialog-desc" className="text-xs text-slate-600 leading-relaxed">
              Are you sure you want to archive account{" "}
              <strong className="text-slate-900 font-semibold font-mono">
                {handleText}
              </strong>{" "}
              ({account.display_name || account.name}, ID #{account.id})?
            </p>
            <p className="text-[11px] text-slate-500 leading-relaxed pt-1">
              Archiving hides the account from active registry views while preserving all historical jobs, workflows, content deliveries, and audit trails. You can restore this account at any time by updating its status.
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
            onClick={handleArchive}
            disabled={isDeleting}
            className="inline-flex items-center gap-1.5 px-4 py-2 bg-purple-700 text-white rounded-lg text-xs font-medium hover:bg-purple-800 transition-colors shadow-2xs disabled:opacity-70"
          >
            {isDeleting ? (
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
            ) : (
              <Archive className="w-3.5 h-3.5" />
            )}
            <span>Archive Account</span>
          </button>
        </div>
      </div>
    </div>
  );
}

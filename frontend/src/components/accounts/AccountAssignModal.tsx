"use client";

import React, { useState } from "react";
import { X, Loader2, Link2, AlertCircle, Cpu } from "lucide-react";
import { Account, formatApiError } from "@/types/account";
import { Runtime } from "@/types/runtime";
import { Device } from "@/types/device";

interface AccountAssignModalProps {
  account: Account | null;
  runtimes: Runtime[];
  devicesMap: Record<number, Device>;
  isOpen: boolean;
  onClose: () => void;
  onAssign: (accountId: number, runtimeId: number | null) => Promise<void>;
}

interface AccountAssignModalContentProps {
  account: Account;
  runtimes: Runtime[];
  devicesMap: Record<number, Device>;
  onClose: () => void;
  onAssign: (accountId: number, runtimeId: number | null) => Promise<void>;
}

function AccountAssignModalContent({
  account,
  runtimes,
  devicesMap,
  onClose,
  onAssign,
}: AccountAssignModalContentProps) {
  const [selectedRuntimeId, setSelectedRuntimeId] = useState<string>(
    account.runtime_id !== null ? String(account.runtime_id) : ""
  );
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const currentRuntime =
    account.runtime_id !== null
      ? runtimes.find((r) => r.id === account.runtime_id)
      : null;
  const isMissing = account.runtime_id !== null && !currentRuntime;

  const handleSave = async (idToSet: number | null) => {
    setFormError(null);
    try {
      setIsSubmitting(true);
      await onAssign(account.id, idToSet);
      onClose();
    } catch (err: unknown) {
      setFormError(formatApiError(err));
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-xs">
      <div
        className="bg-white rounded-2xl shadow-xl border border-slate-200 w-full max-w-md overflow-hidden transition-all animate-in fade-in zoom-in-95 duration-150"
        role="dialog"
        aria-modal="true"
        aria-labelledby="assign-modal-title"
      >
        {/* Header */}
        <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="p-1.5 rounded-lg bg-cyan-50 text-cyan-600">
              <Link2 className="w-4 h-4" />
            </div>
            <div>
              <h3
                id="assign-modal-title"
                className="text-sm font-semibold text-slate-900"
              >
                Assign Runtime to Account
              </h3>
              <p className="text-[11px] text-slate-400 font-mono">
                @{account.username} ({account.name})
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            disabled={isSubmitting}
            className="p-1 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition-colors disabled:opacity-50"
            aria-label="Close modal"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="p-6 space-y-4 text-xs">
          {formError && (
            <div className="p-3 rounded-lg bg-rose-50 border border-rose-200 text-rose-700 leading-relaxed break-words">
              {formError}
            </div>
          )}

          {/* Current Assignment Status */}
          <div className="p-3 rounded-lg bg-slate-50 border border-slate-200">
            <p className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider mb-1">
              Current Assignment
            </p>
            {account.runtime_id === null ? (
              <span className="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-medium bg-slate-200 text-slate-700">
                Unassigned
              </span>
            ) : currentRuntime ? (
              <div className="flex items-center gap-2 text-slate-800">
                <Cpu className="w-4 h-4 text-cyan-600 shrink-0" />
                <span className="font-semibold">{currentRuntime.name}</span>
                <span className="text-slate-500 text-[11px]">
                  ({devicesMap[currentRuntime.device_id]?.name || `Device #${currentRuntime.device_id}`})
                </span>
              </div>
            ) : (
              <div className="flex items-center gap-1.5 text-amber-700">
                <AlertCircle className="w-3.5 h-3.5 text-amber-500" />
                <span className="font-medium">
                  Missing Runtime ID #{account.runtime_id} (Referenced runtime not found)
                </span>
              </div>
            )}
          </div>

          {/* Missing runtime alert */}
          {isMissing && (
            <p className="text-[11px] text-amber-700 bg-amber-50 p-2.5 rounded border border-amber-200">
              The assigned runtime record was removed. You can reassign to an active runtime or clear the assignment.
            </p>
          )}

          {/* Runtime Dropdown */}
          <div className="space-y-1">
            <label
              htmlFor="assignRuntimeSelect"
              className="block font-medium text-slate-700"
            >
              Select Target Runtime
            </label>
            <select
              id="assignRuntimeSelect"
              value={selectedRuntimeId}
              onChange={(e) => setSelectedRuntimeId(e.target.value)}
              className="w-full bg-slate-50 border border-slate-200 rounded-lg px-2.5 py-2 text-slate-800 focus:outline-none focus:ring-2 focus:ring-cyan-500/20 focus:border-cyan-500 font-medium"
            >
              <option value="">Unassigned (No runtime)</option>
              {isMissing && (
                <option value={account.runtime_id!} disabled>
                  Runtime #{account.runtime_id} (Missing / Deleted)
                </option>
              )}
              {runtimes.map((rt) => {
                const dev = devicesMap[rt.device_id];
                const devLabel = dev ? dev.name : `Device #${rt.device_id}`;
                return (
                  <option key={rt.id} value={rt.id}>
                    {rt.name} ({devLabel} • {rt.status} • ID #{rt.id})
                  </option>
                );
              })}
            </select>
          </div>

          {/* Action Buttons */}
          <div className="pt-2 flex items-center justify-between gap-2 border-t border-slate-100">
            {account.runtime_id !== null ? (
              <button
                type="button"
                onClick={() => handleSave(null)}
                disabled={isSubmitting}
                className="px-3 py-2 text-rose-600 hover:bg-rose-50 rounded-lg font-medium transition-colors disabled:opacity-50"
              >
                Clear Assignment
              </button>
            ) : (
              <div />
            )}

            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={onClose}
                disabled={isSubmitting}
                className="px-3.5 py-2 border border-slate-200 rounded-lg text-slate-600 hover:bg-slate-50 font-medium transition-colors disabled:opacity-50"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={() => {
                  const targetId = selectedRuntimeId
                    ? parseInt(selectedRuntimeId, 10)
                    : null;
                  handleSave(targetId);
                }}
                disabled={isSubmitting}
                className="inline-flex items-center gap-1.5 px-4 py-2 bg-cyan-600 text-white rounded-lg font-medium hover:bg-cyan-700 transition-colors shadow-2xs disabled:opacity-70"
              >
                {isSubmitting && (
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                )}
                <span>Save Assignment</span>
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export function AccountAssignModal({
  account,
  runtimes = [],
  devicesMap = {},
  isOpen,
  onClose,
  onAssign,
}: AccountAssignModalProps) {
  if (!isOpen || !account) return null;

  return (
    <AccountAssignModalContent
      key={account.id}
      account={account}
      runtimes={runtimes}
      devicesMap={devicesMap}
      onClose={onClose}
      onAssign={onAssign}
    />
  );
}

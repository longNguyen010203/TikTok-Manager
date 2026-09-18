"use client";

import React, { useState } from "react";
import { X, Loader2, Edit3, AlertCircle } from "lucide-react";
import { Account, UpdateAccountInput, formatApiError } from "@/types/account";
import { Runtime } from "@/types/runtime";
import { Device } from "@/types/device";

interface AccountEditModalProps {
  account: Account | null;
  runtimes?: Runtime[];
  devicesMap?: Record<number, Device>;
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (id: number, input: UpdateAccountInput) => Promise<void>;
}

interface AccountEditModalContentProps {
  account: Account;
  runtimes: Runtime[];
  devicesMap: Record<number, Device>;
  onClose: () => void;
  onSubmit: (id: number, input: UpdateAccountInput) => Promise<void>;
}

function AccountEditModalContent({
  account,
  runtimes,
  devicesMap,
  onClose,
  onSubmit,
}: AccountEditModalContentProps) {
  const [name, setName] = useState(account.name);
  const [username, setUsername] = useState(account.username);
  const [platform, setPlatform] = useState(account.platform);
  const [status, setStatus] = useState(account.status);
  const [notes, setNotes] = useState(account.notes || "");
  const [runtimeId, setRuntimeId] = useState<string>(
    account.runtime_id !== null ? String(account.runtime_id) : ""
  );
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const isCurrentRuntimeMissing =
    account.runtime_id !== null &&
    !runtimes.some((r) => r.id === account.runtime_id);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormError(null);

    const trimmedName = name.trim();
    const trimmedUsername = username.trim().replace(/^@/, "");

    if (!trimmedName) {
      setFormError("Account name is required.");
      return;
    }

    if (!trimmedUsername) {
      setFormError("TikTok username is required.");
      return;
    }

    const parsedRuntimeId = runtimeId ? parseInt(runtimeId, 10) : null;

    try {
      setIsSubmitting(true);
      await onSubmit(account.id, {
        name: trimmedName,
        username: trimmedUsername,
        platform: platform.trim() || "tiktok",
        status,
        notes: notes.trim() || null,
        runtime_id: parsedRuntimeId,
      });
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
        aria-labelledby="edit-modal-title"
      >
        {/* Header */}
        <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="p-1.5 rounded-lg bg-indigo-50 text-indigo-600">
              <Edit3 className="w-4 h-4" />
            </div>
            <div>
              <h3
                id="edit-modal-title"
                className="text-sm font-semibold text-slate-900"
              >
                Edit Account Details
              </h3>
              <p className="text-[11px] text-slate-400 font-mono">
                ID #{account.id} • @{account.username}
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            disabled={isSubmitting}
            className="p-1 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition-colors disabled:opacity-50"
            aria-label="Close edit modal"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="p-6 space-y-4 text-xs">
          {formError && (
            <div className="p-3 rounded-lg bg-rose-50 border border-rose-200 text-rose-700 leading-relaxed break-words">
              {formError}
            </div>
          )}

          {/* Warning if currently assigned runtime is missing */}
          {isCurrentRuntimeMissing && (
            <div className="p-3 rounded-lg bg-amber-50 border border-amber-200 text-amber-800 flex items-start gap-2">
              <AlertCircle className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
              <div>
                <p className="font-semibold">Assigned Runtime Missing</p>
                <p className="mt-0.5 text-[11px]">
                  The previously assigned runtime (ID #{account.runtime_id}) was deleted or cannot be found. Select an active runtime below or leave Unassigned to clear.
                </p>
              </div>
            </div>
          )}

          {/* Name */}
          <div className="space-y-1">
            <label
              htmlFor="editAccName"
              className="block font-medium text-slate-700"
            >
              Account Display Name <span className="text-rose-500">*</span>
            </label>
            <input
              id="editAccName"
              type="text"
              required
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 text-slate-800 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500"
            />
          </div>

          {/* Username */}
          <div className="space-y-1">
            <label
              htmlFor="editAccUsername"
              className="block font-medium text-slate-700"
            >
              TikTok Username <span className="text-rose-500">*</span>
            </label>
            <div className="relative">
              <span className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 font-mono">
                @
              </span>
              <input
                id="editAccUsername"
                type="text"
                required
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                className="w-full bg-slate-50 border border-slate-200 rounded-lg pl-7 pr-3 py-2 text-slate-800 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500"
              />
            </div>
          </div>

          {/* Platform & Status */}
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <label
                htmlFor="editAccPlatform"
                className="block font-medium text-slate-700"
              >
                Platform
              </label>
              <select
                id="editAccPlatform"
                value={platform}
                onChange={(e) => setPlatform(e.target.value)}
                className="w-full bg-slate-50 border border-slate-200 rounded-lg px-2.5 py-2 text-slate-800 focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500"
              >
                <option value="tiktok">TikTok</option>
              </select>
            </div>

            <div className="space-y-1">
              <label
                htmlFor="editAccStatus"
                className="block font-medium text-slate-700"
              >
                Status
              </label>
              <select
                id="editAccStatus"
                value={status}
                onChange={(e) => setStatus(e.target.value)}
                className="w-full bg-slate-50 border border-slate-200 rounded-lg px-2.5 py-2 text-slate-800 focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500"
              >
                <option value="active">Active</option>
                <option value="inactive">Inactive</option>
                <option value="suspended">Suspended</option>
              </select>
            </div>
          </div>

          {/* Runtime Selector */}
          <div className="space-y-1">
            <label
              htmlFor="editAccRuntime"
              className="block font-medium text-slate-700"
            >
              Assigned Runtime
            </label>
            <select
              id="editAccRuntime"
              value={runtimeId}
              onChange={(e) => setRuntimeId(e.target.value)}
              className="w-full bg-slate-50 border border-slate-200 rounded-lg px-2.5 py-2 text-slate-800 focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500"
            >
              <option value="">Unassigned (No runtime)</option>
              {isCurrentRuntimeMissing && (
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
            <p className="text-[11px] text-slate-400">
              Select an execution runtime or leave unassigned.
            </p>
          </div>

          {/* Notes */}
          <div className="space-y-1">
            <label
              htmlFor="editAccNotes"
              className="block font-medium text-slate-700"
            >
              Operational Notes (Optional)
            </label>
            <textarea
              id="editAccNotes"
              rows={2}
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Operational notes, channel purpose..."
              className="w-full bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 text-slate-800 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 resize-none"
            />
          </div>

          {/* Actions */}
          <div className="pt-2 flex items-center justify-end gap-2">
            <button
              type="button"
              onClick={onClose}
              disabled={isSubmitting}
              className="px-4 py-2 border border-slate-200 rounded-lg text-slate-600 hover:bg-slate-50 font-medium transition-colors disabled:opacity-50"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isSubmitting}
              className="inline-flex items-center gap-1.5 px-4 py-2 bg-indigo-600 text-white rounded-lg font-medium hover:bg-indigo-700 transition-colors shadow-2xs disabled:opacity-70"
            >
              {isSubmitting && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
              <span>Update Account</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export function AccountEditModal({
  account,
  runtimes = [],
  devicesMap = {},
  isOpen,
  onClose,
  onSubmit,
}: AccountEditModalProps) {
  if (!isOpen || !account) return null;

  return (
    <AccountEditModalContent
      key={account.id}
      account={account}
      runtimes={runtimes}
      devicesMap={devicesMap}
      onClose={onClose}
      onSubmit={onSubmit}
    />
  );
}

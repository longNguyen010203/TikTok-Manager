"use client";

import React, { useState } from "react";
import { X, Loader2, Sparkles } from "lucide-react";
import { CreateAccountInput } from "@/types/account";

interface AccountCreateModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (input: CreateAccountInput) => Promise<void>;
}

export function AccountCreateModal({
  isOpen,
  onClose,
  onSubmit,
}: AccountCreateModalProps) {
  const [name, setName] = useState("");
  const [username, setUsername] = useState("");
  const [platform, setPlatform] = useState("tiktok");
  const [status, setStatus] = useState("active");
  const [notes, setNotes] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  if (!isOpen) return null;

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

    try {
      setIsSubmitting(true);
      await onSubmit({
        name: trimmedName,
        username: trimmedUsername,
        platform: platform.trim() || "tiktok",
        status,
        notes: notes.trim() || null,
      });

      // Reset form on success
      setName("");
      setUsername("");
      setPlatform("tiktok");
      setStatus("active");
      setNotes("");
      onClose();
    } catch (err: unknown) {
      const errorMsg =
        err instanceof Error ? err.message : "Failed to create account.";
      setFormError(errorMsg);
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
        aria-labelledby="modal-headline"
      >
        {/* Header */}
        <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="p-1.5 rounded-lg bg-rose-50 text-rose-600">
              <Sparkles className="w-4 h-4" />
            </div>
            <h3
              id="modal-headline"
              className="text-sm font-semibold text-slate-900"
            >
              Add New TikTok Account
            </h3>
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

        {/* Form */}
        <form onSubmit={handleSubmit} className="p-6 space-y-4 text-xs">
          {formError && (
            <div className="p-3 rounded-lg bg-rose-50 border border-rose-200 text-rose-700">
              {formError}
            </div>
          )}

          {/* Account Name */}
          <div className="space-y-1">
            <label
              htmlFor="accName"
              className="block font-medium text-slate-700"
            >
              Account Display Name <span className="text-rose-500">*</span>
            </label>
            <input
              id="accName"
              type="text"
              required
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Acme Brand Official"
              className="w-full bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 text-slate-800 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-rose-500/20 focus:border-rose-500"
            />
          </div>

          {/* Username */}
          <div className="space-y-1">
            <label
              htmlFor="accUsername"
              className="block font-medium text-slate-700"
            >
              TikTok Username <span className="text-rose-500">*</span>
            </label>
            <div className="relative">
              <span className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 font-mono">
                @
              </span>
              <input
                id="accUsername"
                type="text"
                required
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="handle_without_at"
                className="w-full bg-slate-50 border border-slate-200 rounded-lg pl-7 pr-3 py-2 text-slate-800 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-rose-500/20 focus:border-rose-500"
              />
            </div>
          </div>

          {/* Platform & Status */}
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <label
                htmlFor="accPlatform"
                className="block font-medium text-slate-700"
              >
                Platform
              </label>
              <select
                id="accPlatform"
                value={platform}
                onChange={(e) => setPlatform(e.target.value)}
                className="w-full bg-slate-50 border border-slate-200 rounded-lg px-2.5 py-2 text-slate-800 focus:outline-none focus:ring-2 focus:ring-rose-500/20 focus:border-rose-500"
              >
                <option value="tiktok">TikTok</option>
              </select>
            </div>

            <div className="space-y-1">
              <label
                htmlFor="accStatus"
                className="block font-medium text-slate-700"
              >
                Initial Status
              </label>
              <select
                id="accStatus"
                value={status}
                onChange={(e) => setStatus(e.target.value)}
                className="w-full bg-slate-50 border border-slate-200 rounded-lg px-2.5 py-2 text-slate-800 focus:outline-none focus:ring-2 focus:ring-rose-500/20 focus:border-rose-500"
              >
                <option value="active">Active</option>
                <option value="inactive">Inactive</option>
                <option value="suspended">Suspended</option>
              </select>
            </div>
          </div>

          {/* Notes */}
          <div className="space-y-1">
            <label
              htmlFor="accNotes"
              className="block font-medium text-slate-700"
            >
              Operational Notes (Optional)
            </label>
            <textarea
              id="accNotes"
              rows={3}
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="e.g. Channel purpose, assigned content creator, or campaign details..."
              className="w-full bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 text-slate-800 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-rose-500/20 focus:border-rose-500 resize-none"
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
              className="inline-flex items-center gap-1.5 px-4 py-2 bg-rose-600 text-white rounded-lg font-medium hover:bg-rose-700 transition-colors shadow-2xs disabled:opacity-70"
            >
              {isSubmitting && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
              <span>Save Account</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

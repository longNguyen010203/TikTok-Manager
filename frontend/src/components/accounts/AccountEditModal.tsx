"use client";

import React, { useState } from "react";
import {
  X,
  Loader2,
  Edit3,
  AlertCircle,
  KeyRound,
  Archive,
  ChevronDown,
  ChevronUp,
} from "lucide-react";
import {
  Account,
  AccountHealthStatus,
  AccountStatus,
  RegistrationState,
  UpdateAccountInput,
  formatApiError,
} from "@/types/account";
import { Runtime } from "@/types/runtime";
import { Device } from "@/types/device";

interface AccountEditModalProps {
  account: Account | null;
  runtimes?: Runtime[];
  devicesMap?: Record<number, Device>;
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (id: number, input: UpdateAccountInput) => Promise<void>;
  onOpenSecrets?: (account: Account) => void;
}

interface AccountEditModalContentProps {
  account: Account;
  runtimes: Runtime[];
  devicesMap: Record<number, Device>;
  onClose: () => void;
  onSubmit: (id: number, input: UpdateAccountInput) => Promise<void>;
  onOpenSecrets?: (account: Account) => void;
}

function AccountEditModalContent({
  account,
  runtimes,
  devicesMap,
  onClose,
  onSubmit,
  onOpenSecrets,
}: AccountEditModalContentProps) {
  const [displayName, setDisplayName] = useState(
    account.display_name || account.name || ""
  );
  const [username, setUsername] = useState(account.username || "");
  const [email, setEmail] = useState(account.email || "");
  const [phone, setPhone] = useState(account.phone || "");
  const [status, setStatus] = useState<AccountStatus>(account.status);
  const [registrationState, setRegistrationState] =
    useState<RegistrationState>(account.registration_state || "unknown");
  const [healthStatus, setHealthStatus] =
    useState<AccountHealthStatus>(account.health_status || "unknown");
  const [statusReason, setStatusReason] = useState(account.status_reason || "");
  const [niche, setNiche] = useState(account.niche || "");
  const [tagsInput, setTagsInput] = useState(account.tags?.join(", ") || "");
  const [notes, setNotes] = useState(account.notes || "");
  const [runtimeId, setRuntimeId] = useState<string>(
    account.runtime_id !== null ? String(account.runtime_id) : ""
  );

  // Metrics state
  const [showMetrics, setShowMetrics] = useState(
    account.follower_count !== null ||
      account.following_count !== null ||
      account.likes_count !== null ||
      account.video_count !== null
  );
  const [followerCount, setFollowerCount] = useState<string>(
    account.follower_count !== null && account.follower_count !== undefined
      ? String(account.follower_count)
      : ""
  );
  const [followingCount, setFollowingCount] = useState<string>(
    account.following_count !== null && account.following_count !== undefined
      ? String(account.following_count)
      : ""
  );
  const [likesCount, setLikesCount] = useState<string>(
    account.likes_count !== null && account.likes_count !== undefined
      ? String(account.likes_count)
      : ""
  );
  const [videoCount, setVideoCount] = useState<string>(
    account.video_count !== null && account.video_count !== undefined
      ? String(account.video_count)
      : ""
  );

  const [isSubmitting, setIsSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const isCurrentRuntimeMissing =
    account.runtime_id !== null &&
    !runtimes.some((r) => r.id === account.runtime_id);

  const isArchived = account.archived_at !== null || account.status === "archived";

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormError(null);

    const trimmedDisplayName = displayName.trim();
    if (!trimmedDisplayName) {
      setFormError("Display name is required.");
      return;
    }

    const trimmedUsername = username.trim().replace(/^@/, "");
    const trimmedEmail = email.trim();
    const trimmedPhone = phone.trim();
    const trimmedNiche = niche.trim();
    const trimmedStatusReason = statusReason.trim();
    const trimmedNotes = notes.trim();

    const parsedTags = tagsInput
      .split(",")
      .map((t) => t.trim().toLowerCase())
      .filter(Boolean);

    const parsedRuntimeId = runtimeId ? parseInt(runtimeId, 10) : null;

    const payload: UpdateAccountInput = {
      display_name: trimmedDisplayName,
      name: trimmedDisplayName,
      username: trimmedUsername || null,
      email: trimmedEmail || null,
      phone: trimmedPhone || null,
      status,
      registration_state: registrationState,
      health_status: healthStatus,
      status_reason: trimmedStatusReason || null,
      niche: trimmedNiche || null,
      notes: trimmedNotes || null,
      tags: parsedTags,
      runtime_id: parsedRuntimeId,
      follower_count: followerCount ? parseInt(followerCount, 10) : null,
      following_count: followingCount ? parseInt(followingCount, 10) : null,
      likes_count: likesCount ? parseInt(likesCount, 10) : null,
      video_count: videoCount ? parseInt(videoCount, 10) : null,
    };

    try {
      setIsSubmitting(true);
      await onSubmit(account.id, payload);
      onClose();
    } catch (err: unknown) {
      setFormError(formatApiError(err));
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-xs overflow-y-auto">
      <div
        className="bg-white rounded-2xl shadow-2xl border border-slate-200 w-full max-w-xl overflow-hidden transition-all animate-in fade-in zoom-in-95 duration-150 my-8 max-h-[92vh] flex flex-col"
        role="dialog"
        aria-modal="true"
        aria-labelledby="edit-modal-title"
      >
        {/* Header */}
        <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between shrink-0 bg-slate-50/50">
          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded-xl bg-indigo-50 text-indigo-600">
              <Edit3 className="w-4 h-4" />
            </div>
            <div>
              <h3
                id="edit-modal-title"
                className="text-sm font-bold text-slate-900 flex items-center gap-2"
              >
                <span>Edit Account #{account.id}</span>
                {account.username && (
                  <span className="font-mono text-xs text-slate-500 font-normal">
                    (@{account.username})
                  </span>
                )}
              </h3>
              <p className="text-xs text-slate-500">
                Update identity, metadata, status, metrics, and runtime configuration.
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            {onOpenSecrets && (
              <button
                type="button"
                onClick={() => {
                  onClose();
                  onOpenSecrets(account);
                }}
                className="inline-flex items-center gap-1.5 px-2.5 py-1 text-xs font-semibold text-emerald-800 bg-emerald-50 hover:bg-emerald-100 border border-emerald-200 rounded-lg transition-colors cursor-pointer"
                title="Manage credentials for this account"
              >
                <KeyRound className="w-3.5 h-3.5 text-emerald-600" />
                <span>Credentials</span>
              </button>
            )}
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
        </div>

        {/* Archived Banner Notice */}
        {isArchived && (
          <div className="px-6 py-2.5 bg-purple-50 border-b border-purple-200 text-purple-900 text-xs flex items-center gap-2 shrink-0">
            <Archive className="w-4 h-4 text-purple-600 shrink-0" />
            <span>
              This account is currently soft-archived. Changing status back to Active or Inactive will restore it to primary views.
            </span>
          </div>
        )}

        {/* Form Body */}
        <form onSubmit={handleSubmit} className="p-6 space-y-4 overflow-y-auto flex-1 text-xs">
          {formError && (
            <div className="p-3 bg-rose-50 border border-rose-200 rounded-xl text-rose-700 flex items-start gap-2">
              <AlertCircle className="w-4 h-4 text-rose-600 shrink-0 mt-0.5" />
              <span>{formError}</span>
            </div>
          )}

          {/* Primary Identity */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div className="space-y-1 sm:col-span-2">
              <label className="block font-semibold text-slate-700">
                Display Name <span className="text-rose-500">*</span>
              </label>
              <input
                type="text"
                value={displayName}
                onChange={(e) => setDisplayName(e.target.value)}
                required
                className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3 py-2 text-slate-800 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:bg-white font-medium"
              />
            </div>

            <div className="space-y-1">
              <label className="block font-medium text-slate-700">
                TikTok Username (@handle)
              </label>
              <div className="relative">
                <span className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 font-mono">
                  @
                </span>
                <input
                  type="text"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  placeholder="leave blank if unassigned"
                  className="w-full bg-slate-50 border border-slate-300 rounded-lg pl-7 pr-3 py-2 text-slate-800 font-mono focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:bg-white"
                />
              </div>
            </div>

            <div className="space-y-1">
              <label className="block font-medium text-slate-700">
                Niche / Category
              </label>
              <input
                type="text"
                value={niche}
                onChange={(e) => setNiche(e.target.value)}
                placeholder="e.g. fitness, humor, gaming"
                className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3 py-2 text-slate-800 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:bg-white"
              />
            </div>
          </div>

          {/* Contact Details */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div className="space-y-1">
              <label className="block font-medium text-slate-700">
                Email Address
              </label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="creator@example.com"
                className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3 py-2 text-slate-800 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:bg-white font-mono"
              />
            </div>

            <div className="space-y-1">
              <label className="block font-medium text-slate-700">
                Phone Number
              </label>
              <input
                type="tel"
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
                placeholder="+1 555-0199"
                className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3 py-2 text-slate-800 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:bg-white font-mono"
              />
            </div>
          </div>

          {/* Lifecycle, Registration & Health */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <div className="space-y-1">
              <label className="block font-medium text-slate-700">
                Lifecycle Status
              </label>
              <select
                value={status}
                onChange={(e) => setStatus(e.target.value as AccountStatus)}
                className="w-full bg-slate-50 border border-slate-300 rounded-lg px-2.5 py-2 text-slate-800 focus:outline-none focus:ring-2 focus:ring-indigo-500 font-medium"
              >
                <option value="active">Active</option>
                <option value="pending">Pending</option>
                <option value="inactive">Inactive</option>
                <option value="restricted">Restricted</option>
                <option value="suspended">Suspended</option>
                <option value="disabled">Disabled</option>
                <option value="archived">Archived</option>
              </select>
            </div>

            <div className="space-y-1">
              <label className="block font-medium text-slate-700">
                Registration State
              </label>
              <select
                value={registrationState}
                onChange={(e) => setRegistrationState(e.target.value as RegistrationState)}
                className="w-full bg-slate-50 border border-slate-300 rounded-lg px-2.5 py-2 text-slate-800 focus:outline-none focus:ring-2 focus:ring-indigo-500 font-medium"
              >
                <option value="unknown">Unknown</option>
                <option value="pending">Pending</option>
                <option value="registered">Registered</option>
                <option value="failed">Failed</option>
              </select>
            </div>

            <div className="space-y-1">
              <label className="block font-medium text-slate-700">
                Health Status
              </label>
              <select
                value={healthStatus}
                onChange={(e) => setHealthStatus(e.target.value as AccountHealthStatus)}
                className="w-full bg-slate-50 border border-slate-300 rounded-lg px-2.5 py-2 text-slate-800 focus:outline-none focus:ring-2 focus:ring-indigo-500 font-medium"
              >
                <option value="unknown">Unknown</option>
                <option value="healthy">Healthy</option>
                <option value="warning">Warning</option>
                <option value="unhealthy">Unhealthy</option>
              </select>
            </div>
          </div>

          {/* Status Reason & Tags */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div className="space-y-1">
              <label className="block font-medium text-slate-700">
                Status Reason (optional)
              </label>
              <input
                type="text"
                value={statusReason}
                onChange={(e) => setStatusReason(e.target.value)}
                placeholder="Reason for restriction, warning, or status"
                className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3 py-2 text-slate-800 focus:outline-none focus:ring-2 focus:ring-indigo-500"
              />
            </div>

            <div className="space-y-1">
              <label className="block font-medium text-slate-700">
                Tags (comma-separated)
              </label>
              <input
                type="text"
                value={tagsInput}
                onChange={(e) => setTagsInput(e.target.value)}
                placeholder="vip, tier1, usa"
                className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3 py-2 text-slate-800 focus:outline-none focus:ring-2 focus:ring-indigo-500 font-mono"
              />
            </div>
          </div>

          {/* Execution Runtime Assignment */}
          <div className="space-y-1">
            <label className="block font-medium text-slate-700">
              Execution Runtime Assignment
            </label>
            <select
              value={runtimeId}
              onChange={(e) => setRuntimeId(e.target.value)}
              className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3 py-2 text-slate-800 focus:outline-none focus:ring-2 focus:ring-indigo-500 font-medium"
            >
              <option value="">Unassigned (No runtime assigned)</option>
              {isCurrentRuntimeMissing && (
                <option value={account.runtime_id!} disabled>
                  Runtime #{account.runtime_id} (Referenced runtime not found)
                </option>
              )}
              {runtimes.map((rt) => {
                const dev = devicesMap[rt.device_id];
                const devLabel = dev ? dev.name : `Device #${rt.device_id}`;
                return (
                  <option key={rt.id} value={rt.id}>
                    {rt.name} — Runtime #{rt.id} ({devLabel} • {rt.status})
                  </option>
                );
              })}
            </select>
          </div>

          {/* Notes */}
          <div className="space-y-1">
            <label className="block font-medium text-slate-700">
              Internal Notes
            </label>
            <textarea
              rows={2}
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Operator notes, strategy, or background details..."
              className="w-full bg-slate-50 border border-slate-300 rounded-lg p-2.5 text-slate-800 focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
          </div>

          {/* Optional Metrics Snapshot Section */}
          <div className="border border-slate-200 rounded-xl overflow-hidden bg-slate-50/50">
            <button
              type="button"
              onClick={() => setShowMetrics((prev) => !prev)}
              className="w-full px-4 py-2.5 text-left flex items-center justify-between text-slate-700 hover:bg-slate-100/70 transition-colors font-medium"
            >
              <span>Follower &amp; Engagement Metrics (Snapshot)</span>
              {showMetrics ? (
                <ChevronUp className="w-4 h-4 text-slate-500" />
              ) : (
                <ChevronDown className="w-4 h-4 text-slate-500" />
              )}
            </button>
            {showMetrics && (
              <div className="p-4 pt-1 grid grid-cols-2 sm:grid-cols-4 gap-3 bg-white border-t border-slate-200 animate-in fade-in duration-100">
                <div className="space-y-1">
                  <label className="block text-[11px] font-medium text-slate-600">
                    Followers
                  </label>
                  <input
                    type="number"
                    min="0"
                    value={followerCount}
                    onChange={(e) => setFollowerCount(e.target.value)}
                    placeholder="0"
                    className="w-full bg-slate-50 border border-slate-300 rounded px-2.5 py-1.5 text-xs font-mono"
                  />
                </div>
                <div className="space-y-1">
                  <label className="block text-[11px] font-medium text-slate-600">
                    Following
                  </label>
                  <input
                    type="number"
                    min="0"
                    value={followingCount}
                    onChange={(e) => setFollowingCount(e.target.value)}
                    placeholder="0"
                    className="w-full bg-slate-50 border border-slate-300 rounded px-2.5 py-1.5 text-xs font-mono"
                  />
                </div>
                <div className="space-y-1">
                  <label className="block text-[11px] font-medium text-slate-600">
                    Likes
                  </label>
                  <input
                    type="number"
                    min="0"
                    value={likesCount}
                    onChange={(e) => setLikesCount(e.target.value)}
                    placeholder="0"
                    className="w-full bg-slate-50 border border-slate-300 rounded px-2.5 py-1.5 text-xs font-mono"
                  />
                </div>
                <div className="space-y-1">
                  <label className="block text-[11px] font-medium text-slate-600">
                    Videos
                  </label>
                  <input
                    type="number"
                    min="0"
                    value={videoCount}
                    onChange={(e) => setVideoCount(e.target.value)}
                    placeholder="0"
                    className="w-full bg-slate-50 border border-slate-300 rounded px-2.5 py-1.5 text-xs font-mono"
                  />
                </div>
              </div>
            )}
          </div>

          {/* Modal Footer */}
          <div className="pt-3 flex items-center justify-end gap-2 border-t border-slate-100">
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
              {isSubmitting ? (
                <>
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  <span>Saving...</span>
                </>
              ) : (
                <span>Save Changes</span>
              )}
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
  onOpenSecrets,
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
      onOpenSecrets={onOpenSecrets}
    />
  );
}

"use client";

import React, { useState } from "react";
import {
  X,
  CheckCircle2,
  AlertCircle,
  AlertTriangle,
  Cpu,
  KeyRound,
  RotateCcw,
  UserCheck,
  XCircle,
  Loader2,
  Monitor,
  Check,
  ShieldCheck,
  Link2,
} from "lucide-react";
import {
  Account,
  AccountRegistrationCompleteInput,
  formatApiError,
  getRegistrationUnreadyReasons,
} from "@/types/account";
import { Runtime } from "@/types/runtime";
import { Device } from "@/types/device";
import { accountService } from "@/services/accountService";
import { deviceService } from "@/services/deviceService";
import {
  RegistrationStateBadge,
  RegistrationReadyBadge,
  AccountSecretPresenceBadge,
} from "./AccountStatusBadge";

interface AccountRegistrationModalProps {
  account: Account | null;
  runtimesMap: Record<number, Runtime>;
  devicesMap: Record<number, Device>;
  isOpen: boolean;
  onClose: () => void;
  onAccountUpdated: () => void;
  onOpenAssignRuntime?: (account: Account) => void;
  onOpenSecrets?: (account: Account) => void;
}

export function AccountRegistrationModal({
  account,
  runtimesMap,
  devicesMap,
  isOpen,
  onClose,
  onAccountUpdated,
  onOpenAssignRuntime,
  onOpenSecrets,
}: AccountRegistrationModalProps) {
  if (!isOpen || !account) return null;

  return (
    <AccountRegistrationModalContent
      key={account.id}
      account={account}
      runtimesMap={runtimesMap}
      devicesMap={devicesMap}
      onClose={onClose}
      onAccountUpdated={onAccountUpdated}
      onOpenAssignRuntime={onOpenAssignRuntime}
      onOpenSecrets={onOpenSecrets}
    />
  );
}

interface AccountRegistrationModalContentProps {
  account: Account;
  runtimesMap: Record<number, Runtime>;
  devicesMap: Record<number, Device>;
  onClose: () => void;
  onAccountUpdated: () => void;
  onOpenAssignRuntime?: (account: Account) => void;
  onOpenSecrets?: (account: Account) => void;
}

function AccountRegistrationModalContent({
  account,
  runtimesMap,
  devicesMap,
  onClose,
  onAccountUpdated,
  onOpenAssignRuntime,
  onOpenSecrets,
}: AccountRegistrationModalContentProps) {
  // Completion form fields
  const [completeUsername, setCompleteUsername] = useState(
    account.username || ""
  );
  const [completeDisplayName, setCompleteDisplayName] = useState(
    account.display_name || account.name || ""
  );
  const [completeNotes, setCompleteNotes] = useState(account.notes || "");

  // Failure form fields
  const [failureReason, setFailureReason] = useState("");

  // Sub-action mode: "complete" | "fail" | "reopen"
  const [actionMode, setActionMode] = useState<"complete" | "fail" | "reopen">(
    "complete"
  );
  const [showReopenConfirm, setShowReopenConfirm] = useState(false);

  // Status & loading
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isLaunchingScreen, setIsLaunchingScreen] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [screenFeedback, setScreenFeedback] = useState<{
    type: "success" | "error";
    message: string;
  } | null>(null);

  const assignedRuntime =
    account.runtime_id !== null ? runtimesMap[account.runtime_id] : null;
  const assignedDevice =
    account.device_id !== null
      ? devicesMap[account.device_id]
      : assignedRuntime && assignedRuntime.device_id
      ? devicesMap[assignedRuntime.device_id]
      : null;

  const isArchived =
    Boolean(account.archived_at) || account.status === "archived";
  const unreadyReasons = getRegistrationUnreadyReasons(account);

  const canComplete =
    !isArchived && account.runtime_id !== null && Boolean(assignedRuntime);

  const canReopen =
    (account.registration_state === "registered" ||
      account.registration_state === "failed") &&
    !isArchived;

  // Handle launching screen viewer
  const handleOpenScreenViewer = async () => {
    if (!assignedDevice) {
      setScreenFeedback({
        type: "error",
        message: "No device associated with this runtime.",
      });
      return;
    }

    setIsLaunchingScreen(true);
    setScreenFeedback(null);
    try {
      const res = await deviceService.openDeviceScreen(assignedDevice.id);
      setScreenFeedback({
        type: "success",
        message: `Screen viewer launched (PID: ${
          res.process_id ?? "active"
        }) connected to ${res.adb_serial}.`,
      });
    } catch (err: unknown) {
      setScreenFeedback({
        type: "error",
        message: formatApiError(err),
      });
    } finally {
      setIsLaunchingScreen(false);
    }
  };

  // Handle Mark Complete
  const handleCompleteRegistration = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!canComplete) {
      if (isArchived) {
        setFormError("Archived accounts cannot be registered.");
      } else {
        setFormError(
          "An execution Runtime must be assigned before registration can be completed."
        );
      }
      return;
    }

    setFormError(null);
    try {
      setIsSubmitting(true);
      const input: AccountRegistrationCompleteInput = {
        username: completeUsername.trim().replace(/^@/, "") || undefined,
        display_name: completeDisplayName.trim() || undefined,
        notes: completeNotes.trim() || undefined,
      };
      await accountService.completeRegistration(account.id, input);
      onAccountUpdated();
      onClose();
    } catch (err: unknown) {
      setFormError(formatApiError(err));
    } finally {
      setIsSubmitting(false);
    }
  };

  // Handle Mark Failed
  const handleFailRegistration = async (e: React.FormEvent) => {
    e.preventDefault();
    const reasonTrimmed = failureReason.trim();
    if (!reasonTrimmed) {
      setFormError("Failure reason is required (1-500 characters).");
      return;
    }
    if (reasonTrimmed.length > 500) {
      setFormError("Failure reason cannot exceed 500 characters.");
      return;
    }

    setFormError(null);
    try {
      setIsSubmitting(true);
      await accountService.failRegistration(account.id, {
        reason: reasonTrimmed,
      });
      onAccountUpdated();
      onClose();
    } catch (err: unknown) {
      setFormError(formatApiError(err));
    } finally {
      setIsSubmitting(false);
    }
  };

  // Handle Reopen
  const handleReopenRegistration = async () => {
    setFormError(null);
    try {
      setIsSubmitting(true);
      await accountService.reopenRegistration(account.id);
      onAccountUpdated();
      setShowReopenConfirm(false);
      onClose();
    } catch (err: unknown) {
      setFormError(formatApiError(err));
    } finally {
      setIsSubmitting(false);
    }
  };

  // Operator workflow steps
  const steps = [
    {
      num: 1,
      title: "Create Account",
      desc: "Account metadata created",
      done: true,
    },
    {
      num: 2,
      title: "Assign Runtime",
      desc: assignedRuntime ? assignedRuntime.name : "Requires active runtime",
      done: Boolean(assignedRuntime),
    },
    {
      num: 3,
      title: "Screen & TikTok App",
      desc: "Register account on device",
      done: account.registration_state === "registered",
    },
    {
      num: 4,
      title: "Store Credentials",
      desc: account.secret_present
        ? `${account.secret_types.length} credentials stored`
        : "Encrypted at rest",
      done: account.secret_present,
    },
    {
      num: 5,
      title: "Mark Registered",
      desc:
        account.registration_state === "registered"
          ? "Eligible for automation"
          : "Enables workflow readiness",
      done: account.registration_state === "registered",
    },
  ];

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-xs overflow-y-auto">
      <div
        className="bg-white rounded-2xl shadow-2xl border border-slate-200 w-full max-w-3xl overflow-hidden transition-all animate-in fade-in zoom-in-95 duration-150 my-6 max-h-[94vh] flex flex-col"
        role="dialog"
        aria-modal="true"
        aria-labelledby="registration-modal-title"
      >
        {/* Header */}
        <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between shrink-0 bg-slate-50/70">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-xl bg-emerald-50 text-emerald-700 shadow-2xs">
              <UserCheck className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3
                  id="registration-modal-title"
                  className="text-base font-bold text-slate-900"
                >
                  Manual Registration Workflow
                </h3>
                <span className="font-mono text-xs text-slate-400">
                  #{account.id}
                </span>
                <RegistrationReadyBadge
                  ready={Boolean(account.registration_ready)}
                  reasons={unreadyReasons}
                />
              </div>
              <p className="text-xs text-slate-500">
                Operator-managed TikTok onboarding for{" "}
                <span className="font-semibold text-slate-700">
                  {account.display_name || account.name}
                </span>
                {account.username && (
                  <span className="font-mono ml-1 text-slate-600">
                    (@{account.username})
                  </span>
                )}
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-1.5 text-slate-400 hover:text-slate-600 rounded-lg hover:bg-slate-100 transition-colors"
            aria-label="Close modal"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Modal Body */}
        <div className="p-6 overflow-y-auto space-y-5 text-xs text-slate-600">
          {/* Top Status & Readiness Banner */}
          <div className="flex flex-wrap items-center justify-between gap-3 p-3.5 bg-slate-50 rounded-xl border border-slate-200/80">
            <div className="flex items-center gap-4 flex-wrap">
              <div>
                <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider block mb-1">
                  Registration State
                </span>
                <RegistrationStateBadge state={account.registration_state} />
              </div>
              <div>
                <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider block mb-1">
                  Automation Readiness
                </span>
                <RegistrationReadyBadge
                  ready={Boolean(account.registration_ready)}
                  reasons={unreadyReasons}
                />
              </div>
            </div>

            {account.registration_completed_at && (
              <div className="text-right">
                <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider block mb-1">
                  Completed At
                </span>
                <span className="font-mono text-[11px] text-slate-600">
                  {new Date(account.registration_completed_at).toLocaleString()}
                </span>
              </div>
            )}
          </div>

          {/* Prominent Readiness Banner */}
          {account.registration_ready ? (
            <div className="p-3 bg-emerald-50 border border-emerald-200 rounded-xl text-emerald-800 flex items-start gap-2.5">
              <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0 mt-0.5" />
              <div>
                <p className="font-semibold text-emerald-900">
                  Account is Ready for downstream automation
                </p>
                <p className="mt-0.5 text-[11px] text-emerald-700">
                  Registration is verified and execution runtime is actively assigned.
                </p>
              </div>
            </div>
          ) : (
            <div className="p-3 bg-amber-50 border border-amber-200 rounded-xl text-amber-800 flex items-start gap-2.5">
              <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
              <div>
                <p className="font-semibold text-amber-900">
                  Account is Not ready for downstream automation
                </p>
                {unreadyReasons.length > 0 && (
                  <ul className="list-disc list-inside mt-1 space-y-0.5 text-[11px] text-amber-700">
                    {unreadyReasons.map((reason, idx) => (
                      <li key={idx}>{reason}</li>
                    ))}
                  </ul>
                )}
              </div>
            </div>
          )}

          {/* Status Reason if present (e.g. Failure reason) */}
          {account.status_reason && (
            <div className="p-3 bg-rose-50 border border-rose-200 rounded-xl text-rose-800 flex items-start gap-2.5">
              <AlertCircle className="w-4 h-4 text-rose-600 shrink-0 mt-0.5" />
              <div>
                <p className="font-semibold text-rose-900">
                  Recorded Status Reason
                </p>
                <p className="mt-0.5 text-[11px] text-rose-700 font-mono">
                  {account.status_reason}
                </p>
              </div>
            </div>
          )}

          {/* Workflow Stepper Guide */}
          <div>
            <h4 className="text-[11px] font-bold text-slate-400 uppercase tracking-wider mb-2.5">
              Operator Registration Steps
            </h4>
            <div className="grid grid-cols-1 sm:grid-cols-5 gap-2">
              {steps.map((st) => (
                <div
                  key={st.num}
                  className={`p-2.5 rounded-xl border flex flex-col justify-between transition-colors ${
                    st.done
                      ? "bg-emerald-50/50 border-emerald-200/70 text-emerald-900"
                      : "bg-slate-50 border-slate-200 text-slate-600"
                  }`}
                >
                  <div className="flex items-center justify-between mb-1.5">
                    <span
                      className={`w-5 h-5 rounded-full flex items-center justify-center font-bold text-[10px] ${
                        st.done
                          ? "bg-emerald-600 text-white"
                          : "bg-slate-200 text-slate-600"
                      }`}
                    >
                      {st.done ? <Check className="w-3 h-3" /> : st.num}
                    </span>
                    <span className="text-[10px] font-medium text-slate-400">
                      Step {st.num}
                    </span>
                  </div>
                  <p className="font-semibold text-[11px] truncate">
                    {st.title}
                  </p>
                  <p className="text-[10px] text-slate-500 truncate mt-0.5">
                    {st.desc}
                  </p>
                </div>
              ))}
            </div>
          </div>

          {/* Step 2 & 3: Runtime and Screen Viewer */}
          <div className="p-4 bg-slate-50 rounded-xl border border-slate-200/80 space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Cpu className="w-4 h-4 text-cyan-600" />
                <h4 className="font-bold text-slate-900 text-xs">
                  Execution Runtime &amp; Screen Viewer
                </h4>
              </div>
              {onOpenAssignRuntime && (
                <button
                  type="button"
                  onClick={() => onOpenAssignRuntime(account)}
                  className="inline-flex items-center gap-1 text-[11px] font-medium text-cyan-700 hover:text-cyan-800 hover:underline"
                >
                  <Link2 className="w-3 h-3" />
                  <span>
                    {assignedRuntime ? "Change Runtime" : "Assign Runtime"}
                  </span>
                </button>
              )}
            </div>

            {assignedRuntime ? (
              <div className="space-y-2">
                <div className="flex flex-wrap items-center justify-between gap-2 p-2.5 bg-white rounded-lg border border-slate-200">
                  <div className="flex items-center gap-2.5">
                    <div className="p-1.5 rounded bg-cyan-50 text-cyan-700">
                      <Cpu className="w-4 h-4" />
                    </div>
                    <div>
                      <p className="font-semibold text-slate-800">
                        {assignedRuntime.name}
                      </p>
                      <p className="text-[10px] text-slate-400 font-mono">
                        Container: {assignedRuntime.docker_container_name} | ADB:{" "}
                        {assignedRuntime.adb_serial}
                      </p>
                    </div>
                  </div>

                  <div className="flex items-center gap-2">
                    {assignedDevice && (
                      <button
                        type="button"
                        onClick={handleOpenScreenViewer}
                        disabled={isLaunchingScreen}
                        className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-cyan-600 text-white hover:bg-cyan-700 transition-colors shadow-2xs disabled:opacity-50"
                      >
                        {isLaunchingScreen ? (
                          <Loader2 className="w-3.5 h-3.5 animate-spin" />
                        ) : (
                          <Monitor className="w-3.5 h-3.5" />
                        )}
                        <span>Open Screen Viewer</span>
                      </button>
                    )}
                  </div>
                </div>

                {screenFeedback && (
                  <div
                    className={`p-2.5 rounded-lg text-[11px] font-medium flex items-center gap-2 ${
                      screenFeedback.type === "success"
                        ? "bg-emerald-50 text-emerald-800 border border-emerald-200"
                        : "bg-rose-50 text-rose-800 border border-rose-200"
                    }`}
                  >
                    {screenFeedback.type === "success" ? (
                      <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600 shrink-0" />
                    ) : (
                      <AlertCircle className="w-3.5 h-3.5 text-rose-600 shrink-0" />
                    )}
                    <span>{screenFeedback.message}</span>
                  </div>
                )}
              </div>
            ) : (
              <div className="p-3 bg-amber-50 border border-amber-200 rounded-lg text-amber-800 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <AlertCircle className="w-4 h-4 text-amber-600 shrink-0" />
                  <span>
                    No runtime assigned. Registration completion requires an active
                    runtime.
                  </span>
                </div>
                {onOpenAssignRuntime && (
                  <button
                    type="button"
                    onClick={() => onOpenAssignRuntime(account)}
                    className="px-2.5 py-1 bg-amber-600 hover:bg-amber-700 text-white font-medium rounded-md shadow-2xs"
                  >
                    Assign Runtime Now
                  </button>
                )}
              </div>
            )}
          </div>

          {/* Step 4: Write-Only Credentials */}
          <div className="p-4 bg-slate-50 rounded-xl border border-slate-200/80 space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <KeyRound className="w-4 h-4 text-emerald-600" />
                <h4 className="font-bold text-slate-900 text-xs">
                  Account Credentials (Write-Only)
                </h4>
              </div>
              {onOpenSecrets && (
                <button
                  type="button"
                  onClick={() => onOpenSecrets(account)}
                  className="inline-flex items-center gap-1 text-[11px] font-medium text-emerald-700 hover:text-emerald-800 hover:underline"
                >
                  <KeyRound className="w-3 h-3" />
                  <span>Manage Credentials</span>
                </button>
              )}
            </div>

            <div className="flex flex-wrap items-center justify-between gap-2 p-2.5 bg-white rounded-lg border border-slate-200">
              <div className="flex items-center gap-2">
                <AccountSecretPresenceBadge
                  present={account.secret_present}
                  secretTypes={account.secret_types}
                  onClick={() => onOpenSecrets?.(account)}
                />
                <span className="text-[11px] text-slate-500">
                  {account.secret_present
                    ? "Credentials stored securely at rest."
                    : "No credentials stored yet."}
                </span>
              </div>
              <div className="flex items-center gap-1 text-[10px] text-slate-400">
                <ShieldCheck className="w-3 h-3 text-emerald-600" />
                <span>Encrypted at rest &amp; write-only</span>
              </div>
            </div>
          </div>

          {/* Step 5: Registration Actions */}
          <div className="border border-slate-200 rounded-xl overflow-hidden">
            {/* Tabs for Actions */}
            <div className="flex border-b border-slate-200 bg-slate-50/70 text-xs font-semibold">
              <button
                type="button"
                onClick={() => {
                  setActionMode("complete");
                  setFormError(null);
                }}
                className={`flex-1 py-2.5 px-4 text-center transition-colors flex items-center justify-center gap-1.5 ${
                  actionMode === "complete"
                    ? "bg-white text-emerald-700 border-b-2 border-emerald-600"
                    : "text-slate-500 hover:text-slate-800"
                }`}
              >
                <CheckCircle2 className="w-3.5 h-3.5" />
                <span>Mark Registered</span>
              </button>
              <button
                type="button"
                onClick={() => {
                  setActionMode("fail");
                  setFormError(null);
                }}
                className={`flex-1 py-2.5 px-4 text-center transition-colors flex items-center justify-center gap-1.5 ${
                  actionMode === "fail"
                    ? "bg-white text-rose-700 border-b-2 border-rose-600"
                    : "text-slate-500 hover:text-slate-800"
                }`}
              >
                <XCircle className="w-3.5 h-3.5" />
                <span>Report Registration Failure</span>
              </button>
              {canReopen && (
                <button
                  type="button"
                  onClick={() => {
                    setActionMode("reopen");
                    setFormError(null);
                  }}
                  className={`flex-1 py-2.5 px-4 text-center transition-colors flex items-center justify-center gap-1.5 ${
                    actionMode === "reopen"
                      ? "bg-white text-indigo-700 border-b-2 border-indigo-600"
                      : "text-slate-500 hover:text-slate-800"
                  }`}
                >
                  <RotateCcw className="w-3.5 h-3.5" />
                  <span>Reopen Registration</span>
                </button>
              )}
            </div>

            {/* Error Banner */}
            {formError && (
              <div className="m-4 p-3 rounded-lg bg-rose-50 border border-rose-200 text-rose-800 flex items-start gap-2">
                <AlertCircle className="w-4 h-4 text-rose-600 shrink-0 mt-0.5" />
                <div className="text-[11px]">{formError}</div>
              </div>
            )}

            {/* Complete Action Form */}
            {actionMode === "complete" && (
              <form onSubmit={handleCompleteRegistration} className="p-4 space-y-4">
                <div className="text-slate-600 text-xs">
                  <p>
                    Verify that registration on TikTok was completed. You can
                    update the handle, display name, and notes below.
                  </p>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
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
                        value={completeUsername}
                        onChange={(e) => setCompleteUsername(e.target.value)}
                        placeholder="creator_handle"
                        className="w-full bg-slate-50 border border-slate-300 rounded-lg pl-7 pr-3 py-2 text-slate-800 font-mono focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:bg-white transition-all text-xs"
                      />
                    </div>
                  </div>

                  <div className="space-y-1">
                    <label className="block font-medium text-slate-700">
                      Display Name
                    </label>
                    <input
                      type="text"
                      value={completeDisplayName}
                      onChange={(e) => setCompleteDisplayName(e.target.value)}
                      placeholder="Display Name"
                      className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3 py-2 text-slate-800 focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:bg-white transition-all text-xs"
                    />
                  </div>
                </div>

                <div className="space-y-1">
                  <label className="block font-medium text-slate-700">
                    Registration Notes
                  </label>
                  <textarea
                    rows={2}
                    value={completeNotes}
                    onChange={(e) => setCompleteNotes(e.target.value)}
                    placeholder="e.g. Registered via phone SMS, handle verified, bio populated"
                    className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3 py-2 text-slate-800 focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:bg-white transition-all text-xs"
                  />
                </div>

                {!canComplete && (
                  <div className="p-2.5 rounded-lg bg-amber-50 text-amber-800 border border-amber-200 text-[11px] flex items-center gap-2">
                    <AlertTriangle className="w-3.5 h-3.5 text-amber-600 shrink-0" />
                    <span>
                      {isArchived
                        ? "Archived accounts cannot be marked as registered."
                        : "An execution runtime must be assigned before marking as registered."}
                    </span>
                  </div>
                )}

                <div className="flex items-center justify-end gap-2 pt-2">
                  <button
                    type="button"
                    onClick={onClose}
                    className="px-3.5 py-2 rounded-lg text-slate-600 hover:bg-slate-100 font-medium"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={isSubmitting || !canComplete}
                    className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg bg-emerald-600 text-white font-semibold hover:bg-emerald-700 shadow-2xs transition-colors disabled:opacity-50"
                  >
                    {isSubmitting ? (
                      <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    ) : (
                      <CheckCircle2 className="w-3.5 h-3.5" />
                    )}
                    <span>Mark as Registered</span>
                  </button>
                </div>
              </form>
            )}

            {/* Fail Action Form */}
            {actionMode === "fail" && (
              <form onSubmit={handleFailRegistration} className="p-4 space-y-4">
                <div className="text-slate-600 text-xs">
                  <p>
                    Record a failure reason for this account. The account state
                    will change to <strong>Failed</strong> and will not be ready
                    for automation.
                  </p>
                </div>

                <div className="space-y-1">
                  <div className="flex items-center justify-between">
                    <label className="block font-medium text-slate-700">
                      Failure Reason <span className="text-rose-500">*</span>
                    </label>
                    <span className="text-[10px] text-slate-400 font-mono">
                      {failureReason.length}/500
                    </span>
                  </div>
                  <textarea
                    rows={3}
                    required
                    maxLength={500}
                    value={failureReason}
                    onChange={(e) => setFailureReason(e.target.value)}
                    placeholder="e.g. Phone number blocked by TikTok, CAPTCHA loop encountered, verification code expired"
                    className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3 py-2 text-slate-800 focus:outline-none focus:ring-2 focus:ring-rose-500 focus:bg-white transition-all text-xs"
                  />
                </div>

                <div className="flex items-center justify-end gap-2 pt-2">
                  <button
                    type="button"
                    onClick={onClose}
                    className="px-3.5 py-2 rounded-lg text-slate-600 hover:bg-slate-100 font-medium"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={isSubmitting || !failureReason.trim()}
                    className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg bg-rose-600 text-white font-semibold hover:bg-rose-700 shadow-2xs transition-colors disabled:opacity-50"
                  >
                    {isSubmitting ? (
                      <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    ) : (
                      <XCircle className="w-3.5 h-3.5" />
                    )}
                    <span>Mark Registration Failed</span>
                  </button>
                </div>
              </form>
            )}

            {/* Reopen Action Form */}
            {actionMode === "reopen" && (
              <div className="p-4 space-y-4">
                <div className="text-slate-600 text-xs">
                  <p>
                    Reopening registration will reset the account registration state
                    from <strong>{account.registration_state}</strong> to{" "}
                    <strong>Pending</strong>.
                  </p>
                  <p className="mt-1 text-slate-500">
                    The account will not be considered ready for automation until
                    registration is completed again.
                  </p>
                </div>

                {!showReopenConfirm ? (
                  <div className="pt-2 flex justify-end gap-2">
                    <button
                      type="button"
                      onClick={onClose}
                      className="px-3.5 py-2 rounded-lg text-slate-600 hover:bg-slate-100 font-medium"
                    >
                      Cancel
                    </button>
                    <button
                      type="button"
                      onClick={() => setShowReopenConfirm(true)}
                      className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg bg-indigo-600 text-white font-semibold hover:bg-indigo-700 shadow-2xs transition-colors"
                    >
                      <RotateCcw className="w-3.5 h-3.5" />
                      <span>Reopen Registration</span>
                    </button>
                  </div>
                ) : (
                  <div className="p-3 bg-amber-50 border border-amber-200 rounded-lg space-y-3">
                    <div className="flex items-start gap-2">
                      <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
                      <div>
                        <p className="font-semibold text-amber-900">
                          Are you sure you want to reopen registration?
                        </p>
                        <p className="text-[11px] text-amber-700 mt-0.5">
                          This will suspend automation eligibility until an operator
                          re-marks this account as Registered.
                        </p>
                      </div>
                    </div>
                    <div className="flex items-center justify-end gap-2">
                      <button
                        type="button"
                        onClick={() => setShowReopenConfirm(false)}
                        className="px-3 py-1.5 rounded-lg text-slate-600 hover:bg-white text-xs font-medium"
                      >
                        Nevermind
                      </button>
                      <button
                        type="button"
                        onClick={handleReopenRegistration}
                        disabled={isSubmitting}
                        className="inline-flex items-center gap-1 px-3.5 py-1.5 rounded-lg bg-indigo-600 text-white font-semibold hover:bg-indigo-700 text-xs shadow-2xs disabled:opacity-50"
                      >
                        {isSubmitting ? (
                          <Loader2 className="w-3.5 h-3.5 animate-spin" />
                        ) : (
                          <RotateCcw className="w-3.5 h-3.5" />
                        )}
                        <span>Yes, Reopen Registration</span>
                      </button>
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>

        {/* Footer */}
        <div className="px-6 py-3.5 border-t border-slate-100 bg-slate-50 flex items-center justify-between shrink-0">
          <div className="text-[11px] text-slate-400">
            Automations check{" "}
            <code className="text-slate-600 bg-slate-200/60 px-1 py-0.5 rounded font-mono">
              registration_ready == true
            </code>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-1.5 rounded-lg text-slate-600 hover:bg-slate-200/70 text-xs font-semibold"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}

"use client";

import React, { useState, useEffect, useRef } from "react";
import {
  X,
  Loader2,
  Smartphone,
  Server,
  Play,
  CheckCircle2,
  AlertCircle,
  RefreshCw,
  HardDrive,
  Network,
  Terminal,
  ShieldCheck,
  Cpu,
} from "lucide-react";
import {
  RedroidProvisioningStatus,
  ProvisioningState,
  ProvisioningApiError,
} from "@/types/provisioning";
import { provisioningService } from "@/services/provisioningService";
import { deviceService } from "@/services/deviceService";
import { formatApiError } from "@/types/device";

interface DeviceCreateModalProps {
  isOpen: boolean;
  onClose: () => void;
  onDeviceCreated?: (info: { name: string; device_id?: number }) => void;
}

const TERMINAL_SUCCESS_STATES: ProvisioningState[] = ["completed"];
const TERMINAL_FAILURE_STATES: ProvisioningState[] = [
  "rolled_back",
  "failed",
  "rollback_failed",
  "inconsistent",
];

const STATE_DESCRIPTIONS: Record<string, string> = {
  requested: "Request received by backend",
  preflighting: "Verifying host Docker & preflight dependencies",
  reserved: "Reserving dedicated device number & ports",
  data_created: "Creating isolated persistent data directory",
  network_created: "Creating dedicated Docker bridge network",
  container_created: "Creating Redroid container in stopped state",
  inspected: "Inspecting container isolation boundaries",
  completed: "Device infrastructure provisioned successfully (stopped)",
  rolling_back: "Rolling back provisioned resources due to failure...",
  rolled_back: "Provisioning rolled back cleanly",
  failed: "Provisioning failed",
  rollback_failed: "Rollback incomplete (manual recovery required)",
  inconsistent: "State inconsistent (manual recovery required)",
};

function generateUUID(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    const v = c === "x" ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
}

export function DeviceCreateModal({
  isOpen,
  onClose,
  onDeviceCreated,
}: DeviceCreateModalProps) {
  // Form input state
  const [name, setName] = useState("");
  const [notes, setNotes] = useState("");
  const [profile, setProfile] = useState("android-12-redroid");

  // Idempotency state: generated when user begins submission, reused on retry
  const [idempotencyKey, setIdempotencyKey] = useState<string | null>(null);

  // Provisioning lifecycle & polling states
  const [provisioningStatus, setProvisioningStatus] =
    useState<RedroidProvisioningStatus | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isPolling, setIsPolling] = useState(false);
  const [error, setError] = useState<{
    message: string;
    statusCode?: number;
    provisioningId?: string;
  } | null>(null);

  // Optional Start Device lifecycle action states
  const [isStartingDevice, setIsStartingDevice] = useState(false);
  const [deviceStarted, setDeviceStarted] = useState(false);
  const [startError, setStartError] = useState<string | null>(null);

  const pollTimerRef = useRef<NodeJS.Timeout | null>(null);
  const pollAttemptsRef = useRef<number>(0);
  const MAX_POLL_ATTEMPTS = 60; // 60 seconds bounded polling

  // Cleanup polling on unmount or modal close
  useEffect(() => {
    return () => {
      if (pollTimerRef.current) {
        clearInterval(pollTimerRef.current);
        pollTimerRef.current = null;
      }
    };
  }, []);

  // Clear poll timer when modal closes
  useEffect(() => {
    if (!isOpen && pollTimerRef.current) {
      clearInterval(pollTimerRef.current);
      pollTimerRef.current = null;
    }
  }, [isOpen]);

  if (!isOpen) return null;

  const stopPolling = () => {
    if (pollTimerRef.current) {
      clearInterval(pollTimerRef.current);
      pollTimerRef.current = null;
    }
    setIsPolling(false);
  };

  const startPolling = (provisioningId: string) => {
    stopPolling();
    setIsPolling(true);
    pollAttemptsRef.current = 0;

    pollTimerRef.current = setInterval(async () => {
      pollAttemptsRef.current += 1;
      if (pollAttemptsRef.current > MAX_POLL_ATTEMPTS) {
        stopPolling();
        setError({
          message:
            "Provisioning status check timed out. You can refresh status below.",
          provisioningId,
        });
        return;
      }

      try {
        const latest = await provisioningService.getProvisioning(provisioningId);
        setProvisioningStatus(latest);

        if (TERMINAL_SUCCESS_STATES.includes(latest.state as ProvisioningState)) {
          stopPolling();
          if (onDeviceCreated) {
            onDeviceCreated({
              name: name.trim() || latest.container_name || "New Device",
              device_id: latest.device_id ?? undefined,
            });
          }
        } else if (
          TERMINAL_FAILURE_STATES.includes(latest.state as ProvisioningState)
        ) {
          stopPolling();
          setError({
            message:
              latest.error_message ||
              STATE_DESCRIPTIONS[latest.state] ||
              "Provisioning failed.",
            provisioningId: latest.provisioning_id,
          });
        }
      } catch {
        // Transient polling errors do not cancel polling unless max attempts reached
      }
    }, 1000);
  };

  // Submit handler (reuses idempotency key on retry)
  const handleSubmit = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    setError(null);
    setStartError(null);

    const trimmedName = name.trim();
    if (!trimmedName) {
      setError({ message: "Device name is required." });
      return;
    }

    // Reuse existing key on retry, or generate one for a new attempt
    let activeKey = idempotencyKey;
    if (!activeKey) {
      activeKey = generateUUID();
      setIdempotencyKey(activeKey);
    }

    try {
      setIsSubmitting(true);
      const result = await provisioningService.provisionDevice(
        {
          name: trimmedName,
          notes: notes.trim() || null,
          profile: profile.trim(),
        },
        activeKey
      );

      setProvisioningStatus(result);

      if (result.state === "completed") {
        setIsSubmitting(false);
        if (onDeviceCreated) {
          onDeviceCreated({
            name: trimmedName,
            device_id: result.device_id ?? undefined,
          });
        }
      } else if (TERMINAL_FAILURE_STATES.includes(result.state as ProvisioningState)) {
        setIsSubmitting(false);
        setError({
          message:
            result.error_message ||
            STATE_DESCRIPTIONS[result.state] ||
            "Provisioning failed.",
          provisioningId: result.provisioning_id,
        });
      } else {
        // 202 Accepted or active state: start bounded polling
        setIsSubmitting(false);
        startPolling(result.provisioning_id);
      }
    } catch (err: unknown) {
      setIsSubmitting(false);
      let message = formatApiError(err);
      let statusCode: number | undefined;
      let provisioningId: string | undefined;

      if (err instanceof ProvisioningApiError) {
        statusCode = err.status;
        provisioningId = err.provisioningId;
        if (err.status === 409) {
          message =
            err.message ||
            "A resource conflict occurred. If this attempt was already submitted, check status.";
        } else if (err.status === 503) {
          message =
            "Host preflight check or provisioning configuration is unavailable. Verify Docker daemon is running.";
        }
      }

      setError({
        message,
        statusCode,
        provisioningId,
      });

      // If an existing provisioningId is known from the error, user can check status
      if (provisioningId) {
        handleRefreshStatus(provisioningId);
      }
    }
  };

  // Manual status refresh for an active or failed provisioning attempt
  const handleRefreshStatus = async (targetId?: string) => {
    const idToCheck =
      targetId || provisioningStatus?.provisioning_id || error?.provisioningId;
    if (!idToCheck) return;

    try {
      setIsPolling(true);
      const latest = await provisioningService.getProvisioning(idToCheck);
      setProvisioningStatus(latest);
      if (TERMINAL_SUCCESS_STATES.includes(latest.state as ProvisioningState)) {
        setError(null);
        if (onDeviceCreated) {
          onDeviceCreated({
            name: name.trim() || latest.container_name || "New Device",
            device_id: latest.device_id ?? undefined,
          });
        }
      } else if (
        TERMINAL_FAILURE_STATES.includes(latest.state as ProvisioningState)
      ) {
        setError({
          message:
            latest.error_message ||
            STATE_DESCRIPTIONS[latest.state] ||
            "Provisioning failed.",
          provisioningId: latest.provisioning_id,
        });
      } else {
        // Still in progress, start polling
        startPolling(idToCheck);
      }
    } catch (err: unknown) {
      setError({
        message: formatApiError(err),
        provisioningId: idToCheck,
      });
    } finally {
      setIsPolling(false);
    }
  };

  // Reset to form to make a genuinely new Create Device attempt
  const handleResetForNewAttempt = () => {
    stopPolling();
    setName("");
    setNotes("");
    setProfile("android-12-redroid");
    setIdempotencyKey(null);
    setProvisioningStatus(null);
    setError(null);
    setIsStartingDevice(false);
    setDeviceStarted(false);
    setStartError(null);
  };

  // Close modal and reset
  const handleClose = () => {
    stopPolling();
    handleResetForNewAttempt();
    onClose();
  };

  // Separate Lifecycle Action: Start Device after provisioning completed
  const handleStartDevice = async () => {
    if (!provisioningStatus?.device_id || isStartingDevice) return;
    setIsStartingDevice(true);
    setStartError(null);

    try {
      await deviceService.startDevice(provisioningStatus.device_id);
      setDeviceStarted(true);
      if (onDeviceCreated) {
        onDeviceCreated({
          name: name.trim() || "Managed Device",
          device_id: provisioningStatus.device_id,
        });
      }
    } catch (err: unknown) {
      setStartError(formatApiError(err));
    } finally {
      setIsStartingDevice(false);
    }
  };

  const isCompleted = provisioningStatus?.state === "completed";
  const isInProgress =
    isSubmitting ||
    isPolling ||
    (provisioningStatus &&
      !TERMINAL_SUCCESS_STATES.includes(
        provisioningStatus.state as ProvisioningState
      ) &&
      !TERMINAL_FAILURE_STATES.includes(
        provisioningStatus.state as ProvisioningState
      ));

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-xs animate-in fade-in duration-150">
      <div
        className="bg-white rounded-2xl shadow-2xl border border-slate-200 w-full max-w-lg overflow-hidden transition-all animate-in zoom-in-95 duration-150 flex flex-col max-h-[92vh]"
        role="dialog"
        aria-modal="true"
        aria-labelledby="device-create-title"
      >
        {/* Header */}
        <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between bg-slate-50/70">
          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded-xl bg-gradient-to-br from-rose-500 to-red-600 text-white shadow-2xs">
              <Smartphone className="w-4 h-4" />
            </div>
            <div>
              <h3
                id="device-create-title"
                className="text-sm font-bold text-slate-900"
              >
                Create Managed Redroid Device
              </h3>
              <p className="text-[11px] text-slate-500">
                Automated container, network, and storage provisioning
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={handleClose}
            disabled={isSubmitting || isPolling || isStartingDevice}
            className="p-1.5 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-200/60 transition-colors disabled:opacity-40"
            aria-label="Close dialog"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Modal Body */}
        <div className="p-6 space-y-4 overflow-y-auto flex-1 text-xs">
          {/* Safety Notice: Device is provisioned stopped */}
          {!isCompleted && (
            <div className="p-3.5 rounded-xl border border-slate-200/90 bg-slate-50/80 text-slate-700 flex items-start gap-2.5">
              <ShieldCheck className="w-4 h-4 text-slate-500 shrink-0 mt-0.5" />
              <div className="space-y-0.5">
                <p className="font-semibold text-slate-800 text-[11px]">
                  Safe Automated Provisioning
                </p>
                <p className="text-[11px] text-slate-500 leading-relaxed">
                  Allocates dedicated container, isolated network, and storage in a{" "}
                  <span className="font-semibold text-slate-700">stopped state</span>.
                  Android OS is not booted until you explicitly click Start Device.
                </p>
              </div>
            </div>
          )}

          {/* Error Banner */}
          {error && (
            <div className="p-3.5 rounded-xl border border-rose-200 bg-rose-50/90 text-rose-900 space-y-2 animate-in fade-in duration-150">
              <div className="flex items-start gap-2.5">
                <AlertCircle className="w-4 h-4 text-rose-600 shrink-0 mt-0.5" />
                <div className="space-y-1 flex-1">
                  <h4 className="font-semibold text-xs">
                    {error.statusCode === 409
                      ? "Provisioning Conflict (409)"
                      : error.statusCode === 422
                      ? "Validation Error (422)"
                      : error.statusCode === 503
                      ? "Service Unavailable (503)"
                      : "Provisioning Error"}
                  </h4>
                  <p className="text-xs text-rose-800 leading-relaxed">
                    {error.message}
                  </p>
                  {error.provisioningId && (
                    <p className="text-[11px] text-rose-700 font-mono pt-0.5">
                      Provisioning ID: {error.provisioningId}
                    </p>
                  )}
                </div>
              </div>
              <div className="flex items-center justify-end gap-2 pt-1">
                {error.provisioningId && (
                  <button
                    type="button"
                    onClick={() => handleRefreshStatus(error.provisioningId)}
                    disabled={isPolling}
                    className="inline-flex items-center gap-1 px-2.5 py-1 text-xs font-semibold rounded-lg text-rose-800 bg-white border border-rose-200 hover:bg-rose-100 transition-colors"
                  >
                    <RefreshCw
                      className={`w-3 h-3 ${isPolling ? "animate-spin" : ""}`}
                    />
                    <span>Check Status</span>
                  </button>
                )}
                <button
                  type="button"
                  onClick={() => handleSubmit()}
                  disabled={isSubmitting || isPolling}
                  className="inline-flex items-center gap-1 px-3 py-1 text-xs font-semibold rounded-lg text-white bg-rose-600 hover:bg-rose-700 transition-colors shadow-2xs"
                >
                  <RefreshCw className="w-3 h-3" />
                  <span>Retry Submission</span>
                </button>
              </div>
            </div>
          )}

          {/* Form View (Visible when not yet completed) */}
          {!isCompleted && !isInProgress && (
            <form onSubmit={handleSubmit} className="space-y-4">
              {/* Device Name */}
              <div className="space-y-1">
                <label
                  htmlFor="devProvisionName"
                  className="block font-medium text-slate-700"
                >
                  Device Name <span className="text-rose-500">*</span>
                </label>
                <input
                  id="devProvisionName"
                  type="text"
                  required
                  value={name}
                  onChange={(e) => {
                    setName(e.target.value);
                    // Clear error on edit
                    if (error) setError(null);
                  }}
                  placeholder="e.g. Redroid Device 04"
                  className="w-full bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 text-slate-800 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-rose-500/20 focus:border-rose-500"
                />
              </div>

              {/* Profile Selection */}
              <div className="space-y-1">
                <label
                  htmlFor="devProvisionProfile"
                  className="block font-medium text-slate-700"
                >
                  Redroid Profile <span className="text-rose-500">*</span>
                </label>
                <select
                  id="devProvisionProfile"
                  value={profile}
                  onChange={(e) => setProfile(e.target.value)}
                  className="w-full bg-slate-50 border border-slate-200 rounded-lg px-2.5 py-2 text-slate-800 font-mono text-xs focus:outline-none focus:ring-2 focus:ring-rose-500/20 focus:border-rose-500"
                >
                  <option value="android-12-redroid">
                    android-12-redroid (Android 12 64-bit)
                  </option>
                </select>
                <p className="text-[11px] text-slate-400 pt-0.5">
                  Pre-configured with immutable digest and isolated bridge network.
                </p>
              </div>

              {/* Notes (Optional) */}
              <div className="space-y-1">
                <label
                  htmlFor="devProvisionNotes"
                  className="block font-medium text-slate-700"
                >
                  Notes <span className="text-slate-400 font-normal">(optional)</span>
                </label>
                <textarea
                  id="devProvisionNotes"
                  rows={2}
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                  placeholder="e.g. Dedicated device for marketing campaign..."
                  className="w-full bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 text-slate-800 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-rose-500/20 focus:border-rose-500 resize-none"
                />
              </div>

              {/* Idempotency Key Notice if key already generated on retry */}
              {idempotencyKey && (
                <div className="p-2.5 rounded-lg bg-slate-100 text-[11px] font-mono text-slate-500 flex items-center justify-between">
                  <span>Key: {idempotencyKey.slice(0, 8)}...</span>
                  <span className="text-emerald-700 font-sans font-medium text-[10px]">
                    Idempotent Key Active
                  </span>
                </div>
              )}
            </form>
          )}

          {/* In-Progress State / Polling Display */}
          {isInProgress && !isCompleted && (
            <div className="p-5 rounded-xl border border-indigo-200 bg-indigo-50/70 space-y-4 animate-in fade-in duration-150">
              <div className="flex items-center gap-3">
                <Loader2 className="w-5 h-5 text-indigo-600 animate-spin shrink-0" />
                <div className="space-y-0.5">
                  <h4 className="font-bold text-xs text-indigo-950">
                    Provisioning in Progress...
                  </h4>
                  <p className="text-xs text-indigo-700">
                    {provisioningStatus
                      ? STATE_DESCRIPTIONS[provisioningStatus.state] ||
                        `State: ${provisioningStatus.state}`
                      : "Sending provisioning request to backend..."}
                  </p>
                </div>
              </div>

              {/* Progress status badge */}
              {provisioningStatus && (
                <div className="p-3 bg-white/90 rounded-lg border border-indigo-100 space-y-2 text-xs">
                  <div className="flex items-center justify-between">
                    <span className="text-slate-500">Current Phase:</span>
                    <span className="font-mono font-semibold px-2 py-0.5 rounded-md bg-indigo-100 text-indigo-800 text-[11px]">
                      {provisioningStatus.state}
                    </span>
                  </div>
                  {provisioningStatus.provisioning_id && (
                    <div className="flex items-center justify-between text-[11px] text-slate-400 font-mono">
                      <span>ID:</span>
                      <span className="truncate max-w-[200px]">
                        {provisioningStatus.provisioning_id}
                      </span>
                    </div>
                  )}
                </div>
              )}
            </div>
          )}

          {/* Success View: Provisioning Completed */}
          {isCompleted && provisioningStatus && (
            <div className="space-y-4 animate-in fade-in duration-200">
              {/* Success Banner */}
              <div className="p-4 rounded-xl border border-emerald-200 bg-emerald-50/90 text-emerald-950 flex items-start gap-3 shadow-2xs">
                <CheckCircle2 className="w-5 h-5 text-emerald-600 shrink-0 mt-0.5" />
                <div className="space-y-1">
                  <h4 className="font-bold text-sm text-emerald-950">
                    Device Provisioned Successfully
                  </h4>
                  <p className="text-xs text-emerald-800 leading-relaxed">
                    The managed Redroid container, dedicated network, and persistent
                    data storage are fully configured in a{" "}
                    <span className="font-semibold underline">stopped state</span>.
                  </p>
                </div>
              </div>

              {/* Allocated Resource Summary Card */}
              <div className="p-4 rounded-xl border border-slate-200 bg-slate-50/70 space-y-3">
                <div className="flex items-center justify-between border-b border-slate-200/80 pb-2">
                  <div className="flex items-center gap-2">
                    <Cpu className="w-4 h-4 text-slate-600" />
                    <span className="font-bold text-xs text-slate-800">
                      Allocated Resource Boundaries
                    </span>
                  </div>
                  <span className="font-mono font-bold text-xs text-indigo-700 bg-indigo-50 px-2 py-0.5 rounded-md border border-indigo-200/60">
                    Device #{provisioningStatus.device_number}
                  </span>
                </div>

                <div className="grid grid-cols-2 gap-2.5 text-xs">
                  <div className="p-2.5 rounded-lg bg-white border border-slate-200/80">
                    <span className="text-[10px] text-slate-400 uppercase font-semibold block flex items-center gap-1">
                      <Server className="w-3 h-3 text-slate-400" /> Container Name
                    </span>
                    <span className="font-mono font-semibold text-slate-800 truncate block pt-0.5">
                      {provisioningStatus.container_name || "N/A"}
                    </span>
                  </div>

                  <div className="p-2.5 rounded-lg bg-white border border-slate-200/80">
                    <span className="text-[10px] text-slate-400 uppercase font-semibold block flex items-center gap-1">
                      <Terminal className="w-3 h-3 text-slate-400" /> ADB Serial
                    </span>
                    <span className="font-mono font-semibold text-slate-800 truncate block pt-0.5">
                      {provisioningStatus.adb_serial || "N/A"}
                    </span>
                  </div>

                  <div className="p-2.5 rounded-lg bg-white border border-slate-200/80">
                    <span className="text-[10px] text-slate-400 uppercase font-semibold block flex items-center gap-1">
                      <Network className="w-3 h-3 text-slate-400" /> Network
                    </span>
                    <span className="font-mono font-semibold text-slate-800 truncate block pt-0.5">
                      {provisioningStatus.network_name || "N/A"}
                    </span>
                  </div>

                  <div className="p-2.5 rounded-lg bg-white border border-slate-200/80">
                    <span className="text-[10px] text-slate-400 uppercase font-semibold block flex items-center gap-1">
                      <HardDrive className="w-3 h-3 text-slate-400" /> Data Storage
                    </span>
                    <span
                      className="font-mono font-semibold text-slate-800 truncate block pt-0.5"
                      title={provisioningStatus.data_path || ""}
                    >
                      {provisioningStatus.data_path
                        ? provisioningStatus.data_path.split("/").pop()
                        : "N/A"}
                    </span>
                  </div>
                </div>

                <div className="flex items-center justify-between text-[11px] text-slate-500 pt-1 font-mono">
                  <span>Device ID: #{provisioningStatus.device_id}</span>
                  <span>Runtime ID: #{provisioningStatus.runtime_id}</span>
                </div>
              </div>

              {/* Start Device Lifecycle Section */}
              <div className="p-3.5 rounded-xl border border-slate-200 bg-white space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold text-slate-700">
                    Device Lifecycle Status:
                  </span>
                  {deviceStarted ? (
                    <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-100 text-emerald-800 border border-emerald-200">
                      <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
                      <span>Online &amp; Ready</span>
                    </span>
                  ) : (
                    <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-slate-100 text-slate-700 border border-slate-300">
                      <span className="w-1.5 h-1.5 rounded-full bg-slate-400" />
                      <span>Stopped (Offline)</span>
                    </span>
                  )}
                </div>

                {startError && (
                  <div className="p-2.5 rounded-lg bg-rose-50 border border-rose-200 text-rose-700 text-xs flex items-center justify-between">
                    <span>{startError}</span>
                    <button
                      type="button"
                      onClick={() => setStartError(null)}
                      className="text-slate-400 hover:text-slate-600"
                    >
                      &times;
                    </button>
                  </div>
                )}

                {isStartingDevice && (
                  <div className="p-2.5 rounded-lg bg-indigo-50 border border-indigo-200 text-indigo-800 text-xs flex items-center gap-2">
                    <Loader2 className="w-4 h-4 animate-spin text-indigo-600 shrink-0" />
                    <span>
                      Starting container, booting Android OS, and verifying ADB...
                    </span>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>

        {/* Modal Footer */}
        <div className="px-6 py-3.5 border-t border-slate-100 bg-slate-50/70 flex items-center justify-between">
          <div className="text-[11px] text-slate-400 font-mono">
            {isCompleted
              ? `Provisioning #${provisioningStatus?.provisioning_id.slice(0, 8)}`
              : "POST /redroid-provisionings"}
          </div>

          <div className="flex items-center gap-2">
            {/* If completed: offer Start Device and Done */}
            {isCompleted ? (
              <>
                {!deviceStarted && (
                  <button
                    type="button"
                    onClick={handleStartDevice}
                    disabled={isStartingDevice}
                    className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-lg text-xs font-semibold text-white bg-emerald-600 hover:bg-emerald-700 active:bg-emerald-800 transition-colors disabled:opacity-50 shadow-2xs"
                  >
                    {isStartingDevice ? (
                      <>
                        <Loader2 className="w-3.5 h-3.5 animate-spin" />
                        <span>Starting Device...</span>
                      </>
                    ) : (
                      <>
                        <Play className="w-3.5 h-3.5 fill-current" />
                        <span>Start Device Now</span>
                      </>
                    )}
                  </button>
                )}
                <button
                  type="button"
                  onClick={handleClose}
                  className="px-4 py-2 text-xs font-semibold text-slate-700 bg-slate-200/80 hover:bg-slate-300 rounded-lg transition-colors"
                >
                  Done
                </button>
              </>
            ) : isInProgress ? (
              /* If in progress: offer Cancel / Background check */
              <button
                type="button"
                onClick={handleClose}
                className="px-3.5 py-2 text-xs font-medium text-slate-600 hover:text-slate-800 rounded-lg"
              >
                Close (Keep Working)
              </button>
            ) : (
              /* If idle form view: Cancel and Create Device */
              <>
                <button
                  type="button"
                  onClick={handleClose}
                  disabled={isSubmitting}
                  className="px-3.5 py-2 text-xs font-medium text-slate-600 hover:text-slate-800 rounded-lg"
                >
                  Cancel
                </button>
                <button
                  type="button"
                  onClick={() => handleSubmit()}
                  disabled={isSubmitting || !name.trim()}
                  className="inline-flex items-center gap-1.5 px-4 py-2 bg-rose-600 text-white text-xs font-medium rounded-lg hover:bg-rose-700 transition-colors shadow-2xs disabled:opacity-50 cursor-pointer"
                >
                  {isSubmitting ? (
                    <>
                      <Loader2 className="w-3.5 h-3.5 animate-spin" />
                      <span>Provisioning...</span>
                    </>
                  ) : (
                    <span>Create Device</span>
                  )}
                </button>
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

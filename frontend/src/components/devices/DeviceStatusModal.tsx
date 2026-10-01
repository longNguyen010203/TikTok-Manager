"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import {
  X,
  RefreshCw,
  Activity,
  CheckCircle2,
  AlertCircle,
  AlertTriangle,
  Server,
  Smartphone,
  Terminal,
  Cpu,
  FileJson,
  ChevronDown,
  ChevronUp,
  Play,
  Square,
  RotateCcw,
  Power,
  Loader2,
  ExternalLink,
  Layers,
} from "lucide-react";
import {
  Device,
  DeviceLifecycleStatus,
  formatApiError,
  ApiError,
} from "@/types/device";
import { Runtime } from "@/types/runtime";
import { deviceService } from "@/services/deviceService";
import { runtimeService } from "@/services/runtimeService";
import { DeviceStatusBadge } from "./DeviceStatusBadge";
import { DeviceReadinessBadge } from "./DeviceReadinessBadge";

interface DeviceStatusModalProps {
  device: Device | null;
  isOpen: boolean;
  onClose: () => void;
  onStatusUpdated?: (status: DeviceLifecycleStatus) => void;
}

export function DeviceStatusModal({
  device,
  isOpen,
  onClose,
  onStatusUpdated,
}: DeviceStatusModalProps) {
  const [status, setStatus] = useState<DeviceLifecycleStatus | null>(null);
  const [runtime, setRuntime] = useState<Runtime | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [error, setError] = useState<{
    message: string;
    statusCode?: number;
  } | null>(null);
  const [lastCheckedAt, setLastCheckedAt] = useState<Date | null>(null);
  const [showRawJson, setShowRawJson] = useState(false);
  const [refreshTrigger, setRefreshTrigger] = useState(0);

  // Lifecycle mutation action states
  const [actionRunning, setActionRunning] = useState<
    "start" | "stop" | "restart" | null
  >(null);
  const [confirmingAction, setConfirmingAction] = useState<
    "stop" | "restart" | null
  >(null);
  const [actionFeedback, setActionFeedback] = useState<{
    type: "success" | "error";
    message: string;
    statusCode?: number;
  } | null>(null);

  const deviceId = device?.id;

  // Fetch lifecycle status from real backend
  useEffect(() => {
    if (!isOpen || !deviceId) {
      return;
    }

    let ignore = false;

    deviceService
      .getDeviceStatus(deviceId)
      .then((result) => {
        if (ignore) return;
        setStatus(result);
        setLastCheckedAt(new Date());
        setError(null);
        if (onStatusUpdated) {
          onStatusUpdated(result);
        }

        // Fetch associated runtime details
        if (result.runtime_id) {
          runtimeService
            .getRuntime(result.runtime_id)
            .then((rt) => {
              if (!ignore) {
                setRuntime(rt);
              }
            })
            .catch(() => {
              // Graceful fallback: Runtime record details optional
            });
        }
      })
      .catch((err: unknown) => {
        if (ignore) return;
        const message = formatApiError(err);
        const statusCode = err instanceof ApiError ? err.status : undefined;
        setError({ message, statusCode });
      })
      .finally(() => {
        if (!ignore) {
          setIsLoading(false);
          setIsRefreshing(false);
        }
      });

    return () => {
      ignore = true;
    };
  }, [isOpen, deviceId, refreshTrigger, onStatusUpdated]);

  // Handle escape key
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && isOpen && !actionRunning) {
        onClose();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, onClose, actionRunning]);

  if (!isOpen || !device) return null;

  const handleRefreshClick = () => {
    if (device && !isLoading && !isRefreshing && !actionRunning) {
      setIsRefreshing(true);
      setError(null);
      setActionFeedback(null);
      setRefreshTrigger((prev) => prev + 1);
    }
  };

  const handleExecuteAction = async (action: "start" | "stop" | "restart") => {
    if (!device || actionRunning) return;

    setActionRunning(action);
    setConfirmingAction(null);
    setActionFeedback(null);

    try {
      let result: DeviceLifecycleStatus;
      if (action === "start") {
        result = await deviceService.startDevice(device.id);
      } else if (action === "stop") {
        result = await deviceService.stopDevice(device.id);
      } else {
        result = await deviceService.restartDevice(device.id);
      }

      setStatus(result);
      setLastCheckedAt(new Date());
      setError(null);

      // Notify parent to reconcile device list and cached status
      if (onStatusUpdated) {
        onStatusUpdated(result);
      }

      // Re-fetch runtime details if needed
      if (result.runtime_id) {
        runtimeService
          .getRuntime(result.runtime_id)
          .then((rt) => setRuntime(rt))
          .catch(() => {});
      }

      const successMessages: Record<string, string> = {
        start: `Device "${device.name}" started successfully! Container is running and system readiness verified.`,
        stop: `Device "${device.name}" stopped successfully. Container halted and persistent data preserved.`,
        restart: `Device "${device.name}" restarted successfully! Android OS boot completed and ADB reconnected.`,
      };

      setActionFeedback({
        type: "success",
        message: successMessages[action],
      });
    } catch (err: unknown) {
      const message = formatApiError(err);
      const statusCode = err instanceof ApiError ? err.status : undefined;
      setActionFeedback({
        type: "error",
        message,
        statusCode,
      });
    } finally {
      setActionRunning(null);
    }
  };

  const formatLastChecked = (date: Date | null) => {
    if (!date) return "Not checked yet";
    return new Intl.DateTimeFormat("en-US", {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      hour12: false,
    }).format(date);
  };

  // Action validation rules based on lifecycle state
  const isActionDisabled = actionRunning !== null || isLoading || isRefreshing;

  const isContainerRunning = status?.container_status === "running";
  const isReady = status?.ready === true;

  // Start is invalid if container is already running or status is unknown
  const startDisabled =
    isActionDisabled || !status || isContainerRunning;

  const startDisabledReason = !status
    ? "Status must be checked first"
    : isActionDisabled
    ? "An action or check is currently in progress"
    : isReady
    ? "Device is already running and ready"
    : isContainerRunning
    ? "Container is already running. Use Restart to re-initialize."
    : undefined;

  // Stop is invalid if container is not running or status is unknown
  const stopDisabled =
    isActionDisabled || !status || !isContainerRunning;

  const stopDisabledReason = !status
    ? "Status must be checked first"
    : isActionDisabled
    ? "An action or check is currently in progress"
    : !isContainerRunning
    ? "Device is already stopped"
    : undefined;

  // Restart is invalid if container is not running or status is unknown
  const restartDisabled =
    isActionDisabled || !status || !isContainerRunning;

  const restartDisabledReason = !status
    ? "Status must be checked first"
    : isActionDisabled
    ? "An action or check is currently in progress"
    : !isContainerRunning
    ? "Container is not running; click Start to launch"
    : undefined;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-xs animate-in fade-in duration-150">
      <div
        className="bg-white rounded-2xl shadow-2xl border border-slate-200/80 w-full max-w-2xl max-h-[92vh] flex flex-col overflow-hidden animate-in zoom-in-95 duration-150"
        role="dialog"
        aria-modal="true"
        aria-labelledby="modal-status-title"
      >
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-100 bg-slate-50/60">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-indigo-500 to-purple-600 text-white flex items-center justify-center shadow-sm">
              <Activity className="w-5 h-5" />
            </div>
            <div>
              <h2
                id="modal-status-title"
                className="text-base font-bold text-slate-900"
              >
                Device Lifecycle Status &amp; Controls
              </h2>
              <div className="flex items-center gap-2 text-xs text-slate-500 mt-0.5">
                <span className="font-semibold text-slate-700">
                  {device.name}
                </span>
                <span>•</span>
                <span className="font-mono text-slate-400">ID #{device.id}</span>
                <span>•</span>
                <span className="capitalize">{device.platform}</span>
                <span>({device.device_type})</span>
              </div>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            disabled={actionRunning !== null}
            className="p-1.5 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-200/60 transition-colors disabled:opacity-40"
            aria-label="Close dialog"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Action & Info Subheader */}
        <div className="px-6 py-2.5 bg-slate-100/50 border-b border-slate-100 flex flex-wrap items-center justify-between gap-3 text-xs">
          <div className="flex items-center gap-2">
            <span className="text-slate-500">Current DB Status:</span>
            <DeviceStatusBadge
              status={status ? status.device_status : device.status}
            />
            {status && (
              <DeviceReadinessBadge
                ready={status.ready}
                runtimeStatus={status.runtime_status}
                size="md"
              />
            )}
          </div>

          <div className="flex items-center gap-3">
            <span className="text-slate-400 text-[11px]">
              Last checked:{" "}
              <span className="font-mono font-medium text-slate-600">
                {formatLastChecked(lastCheckedAt)}
              </span>
            </span>

            <button
              type="button"
              onClick={handleRefreshClick}
              disabled={isLoading || isRefreshing || actionRunning !== null}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold text-indigo-700 bg-indigo-50 border border-indigo-200/70 hover:bg-indigo-100 active:bg-indigo-200/80 transition-colors disabled:opacity-50 shadow-2xs"
            >
              <RefreshCw
                className={`w-3.5 h-3.5 ${
                  isLoading || isRefreshing ? "animate-spin text-indigo-600" : ""
                }`}
              />
              <span>
                {isLoading || isRefreshing ? "Checking..." : "Refresh Status"}
              </span>
            </button>
          </div>
        </div>

        {/* Modal Body */}
        <div className="p-6 overflow-y-auto space-y-5 flex-1">
          {/* Action Running Progress Banner */}
          {actionRunning && (
            <div className="p-4 rounded-xl border border-indigo-200 bg-indigo-50/90 text-indigo-900 flex items-start gap-3.5 shadow-sm animate-pulse">
              <Loader2 className="w-5 h-5 text-indigo-600 animate-spin shrink-0 mt-0.5" />
              <div className="space-y-1">
                <h4 className="text-sm font-bold text-indigo-900">
                  {actionRunning === "start" && "Starting Device..."}
                  {actionRunning === "stop" && "Stopping Device..."}
                  {actionRunning === "restart" && "Restarting Device..."}
                </h4>
                <p className="text-xs text-indigo-700 leading-relaxed">
                  {actionRunning === "start" &&
                    "Starting container, waiting for Android boot completion, and verifying ADB connectivity (this can take up to 2 minutes)..."}
                  {actionRunning === "stop" &&
                    "Stopping container and reconciling device database status. Persistent container data is preserved."}
                  {actionRunning === "restart" &&
                    "Restarting container, waiting for Android OS boot, and reconnecting ADB (this can take up to 2 minutes)..."}
                </p>
              </div>
            </div>
          )}

          {/* Action Feedback Banner (Success or Error) */}
          {actionFeedback && !actionRunning && (
            <div
              className={`p-4 rounded-xl border text-xs flex items-start justify-between gap-3 animate-in fade-in duration-200 ${
                actionFeedback.type === "success"
                  ? "bg-emerald-50 border-emerald-200 text-emerald-900"
                  : "bg-rose-50 border-rose-200 text-rose-900"
              }`}
            >
              <div className="flex items-start gap-2.5">
                {actionFeedback.type === "success" ? (
                  <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0 mt-0.5" />
                ) : (
                  <AlertCircle className="w-4 h-4 text-rose-600 shrink-0 mt-0.5" />
                )}
                <div className="space-y-1">
                  <h4 className="font-semibold text-xs">
                    {actionFeedback.type === "success"
                      ? "Operation Completed"
                      : actionFeedback.statusCode === 409
                      ? "Action Conflict (409)"
                      : actionFeedback.statusCode === 502
                      ? "Container / ADB Execution Error (502)"
                      : actionFeedback.statusCode === 504
                      ? "Android Boot Timeout (504)"
                      : "Action Failed"}
                  </h4>
                  <p className="leading-relaxed">{actionFeedback.message}</p>
                  {actionFeedback.type === "error" && (
                    <p className="text-[11px] opacity-85 pt-0.5">
                      {actionFeedback.statusCode === 504
                        ? "Android boot did not finish within the timeout limit. The container may still be starting up; refresh status to check again."
                        : actionFeedback.statusCode === 502
                        ? "Docker or ADB command failed. Check Docker daemon and container status."
                        : actionFeedback.statusCode === 409
                        ? "Ensure the device has an assigned Redroid runtime with valid container name and ADB serial."
                        : "You can retry the action or refresh status."}
                    </p>
                  )}
                </div>
              </div>
              <button
                type="button"
                onClick={() => setActionFeedback(null)}
                className="font-bold text-slate-400 hover:text-slate-600 text-sm px-1.5 py-0.5"
                aria-label="Dismiss feedback"
              >
                &times;
              </button>
            </div>
          )}

          {/* Initial Loading Skeleton */}
          {isLoading && !status && (
            <div className="space-y-4 animate-pulse">
              <div className="h-24 bg-slate-100 rounded-xl" />
              <div className="h-24 bg-slate-100 rounded-xl" />
              <div className="h-20 bg-slate-100 rounded-xl" />
              <div className="grid grid-cols-2 gap-4">
                <div className="h-24 bg-slate-100 rounded-xl" />
                <div className="h-24 bg-slate-100 rounded-xl" />
                <div className="h-24 bg-slate-100 rounded-xl" />
                <div className="h-24 bg-slate-100 rounded-xl" />
              </div>
            </div>
          )}

          {/* Initial Fetch Error State */}
          {!isLoading && error && (
            <div className="p-4 rounded-xl border border-rose-200 bg-rose-50/80 text-rose-900 space-y-3">
              <div className="flex items-start gap-3">
                <AlertCircle className="w-5 h-5 text-rose-600 shrink-0 mt-0.5" />
                <div className="space-y-1">
                  <h4 className="text-sm font-semibold">
                    {error.statusCode === 409
                      ? "Redroid Runtime Configuration Required"
                      : error.statusCode === 502
                      ? "Runtime Communication Error (502)"
                      : error.statusCode === 504
                      ? "Android Boot Timeout (504)"
                      : "Failed to Fetch Device Lifecycle Status"}
                  </h4>
                  <p className="text-xs text-rose-700 leading-relaxed">
                    {error.message}
                  </p>
                  {error.statusCode === 409 && (
                    <p className="text-xs text-rose-600/90 pt-1">
                      To inspect and control lifecycle, ensure this device has
                      exactly one assigned Redroid runtime configured with a
                      valid Docker container name and ADB serial endpoint.
                    </p>
                  )}
                </div>
              </div>
              <div className="pt-1 flex justify-end">
                <button
                  type="button"
                  onClick={handleRefreshClick}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold text-rose-700 bg-white border border-rose-200 hover:bg-rose-100 transition-colors shadow-2xs"
                >
                  <RefreshCw className="w-3.5 h-3.5" />
                  <span>Retry Check</span>
                </button>
              </div>
            </div>
          )}

          {/* Lifecycle Status Display & Controls */}
          {status && (
            <div className="space-y-5">
              {/* Associated Runtime Information Card */}
              <div className="p-4 rounded-xl border border-slate-200/90 bg-white shadow-2xs space-y-3">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                  <div className="flex items-center gap-2.5">
                    <div className="p-2 rounded-lg bg-cyan-50 text-cyan-700 shrink-0">
                      <Cpu className="w-4 h-4" />
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <h4 className="text-xs font-bold text-slate-900">
                          {runtime ? runtime.name : `Runtime #${status.runtime_id}`}
                        </h4>
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-slate-100 text-slate-700 text-[10px] font-semibold uppercase tracking-wider">
                          <Layers className="w-3 h-3 text-slate-500" />
                          {runtime ? runtime.runtime_type : "redroid"}
                        </span>
                      </div>
                      <p className="text-[11px] text-slate-400">
                        Linked Runtime Record #{status.runtime_id}
                      </p>
                    </div>
                  </div>

                  {/* Link to related /runtimes page */}
                  <Link
                    href="/runtimes"
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold text-indigo-700 bg-indigo-50 hover:bg-indigo-100 active:bg-indigo-200/80 border border-indigo-200/70 rounded-lg transition-colors shadow-2xs w-fit"
                    title="Open Runtimes management page"
                  >
                    <ExternalLink className="w-3.5 h-3.5" />
                    <span>Open Related Runtimes</span>
                  </Link>
                </div>

                {/* Runtime Metrics Grid */}
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5 pt-1 text-xs">
                  <div className="p-2.5 rounded-lg bg-slate-50/80 border border-slate-100">
                    <p className="text-[10px] text-slate-400 uppercase font-semibold">Runtime ID</p>
                    <p className="font-mono font-bold text-slate-800">#{status.runtime_id}</p>
                  </div>
                  <div className="p-2.5 rounded-lg bg-slate-50/80 border border-slate-100">
                    <p className="text-[10px] text-slate-400 uppercase font-semibold">Runtime Type</p>
                    <p className="font-semibold text-slate-800 capitalize">
                      {runtime ? runtime.runtime_type : "redroid"}
                    </p>
                  </div>
                  <div className="p-2.5 rounded-lg bg-slate-50/80 border border-slate-100">
                    <p className="text-[10px] text-slate-400 uppercase font-semibold">Docker Container</p>
                    <p className="font-mono font-semibold text-slate-800 truncate" title={status.docker_container_name}>
                      {status.docker_container_name}
                    </p>
                  </div>
                  <div className="p-2.5 rounded-lg bg-slate-50/80 border border-slate-100">
                    <p className="text-[10px] text-slate-400 uppercase font-semibold">ADB Serial</p>
                    <p className="font-mono font-semibold text-slate-800 truncate" title={status.adb_serial}>
                      {status.adb_serial}
                    </p>
                  </div>
                </div>
              </div>

              {/* Lifecycle Controls Panel */}
              <div className="p-4 rounded-xl border border-slate-200 bg-slate-50/70 space-y-3 shadow-2xs">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Power className="w-4 h-4 text-indigo-600" />
                    <h3 className="text-xs font-bold uppercase tracking-wider text-slate-700">
                      Lifecycle Controls
                    </h3>
                  </div>
                  <span className="text-[11px] text-slate-500">
                    Target: <code className="font-mono text-slate-700">{status.docker_container_name}</code>
                  </span>
                </div>

                {/* Inline Confirmation Card for Stop */}
                {confirmingAction === "stop" && (
                  <div className="p-3.5 rounded-xl border border-rose-300 bg-rose-50 text-rose-900 space-y-2 animate-in fade-in duration-150">
                    <div className="flex items-start gap-2.5">
                      <AlertTriangle className="w-4 h-4 text-rose-600 shrink-0 mt-0.5" />
                      <div className="space-y-1">
                        <h4 className="font-bold text-xs">
                          Confirm Stopping Device: {device.name}
                        </h4>
                        <p className="text-xs text-rose-800 leading-relaxed">
                          Stopping the Redroid container halts active operations.
                          <br />
                          <span className="font-semibold">
                            Data Safety:
                          </span>{" "}
                          Stopping does <span className="underline">not</span> delete
                          the container or persistent storage. Installed apps,
                          accounts, and settings are preserved.
                        </p>
                      </div>
                    </div>
                    <div className="flex items-center justify-end gap-2 pt-1">
                      <button
                        type="button"
                        onClick={() => setConfirmingAction(null)}
                        className="px-3 py-1.5 text-xs font-medium rounded-lg text-slate-700 bg-white border border-slate-300 hover:bg-slate-100 transition-colors"
                      >
                        Cancel
                      </button>
                      <button
                        type="button"
                        onClick={() => handleExecuteAction("stop")}
                        className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-lg text-white bg-rose-600 hover:bg-rose-700 transition-colors shadow-2xs"
                      >
                        <Square className="w-3.5 h-3.5" />
                        <span>Confirm Stop</span>
                      </button>
                    </div>
                  </div>
                )}

                {/* Inline Confirmation Card for Restart */}
                {confirmingAction === "restart" && (
                  <div className="p-3.5 rounded-xl border border-amber-300 bg-amber-50 text-amber-900 space-y-2 animate-in fade-in duration-150">
                    <div className="flex items-start gap-2.5">
                      <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
                      <div className="space-y-1">
                        <h4 className="font-bold text-xs">
                          Confirm Restarting Device: {device.name}
                        </h4>
                        <p className="text-xs text-amber-800 leading-relaxed">
                          This will restart the Redroid container, wait for Android
                          system boot completion, and re-establish the ADB
                          connection. This may take up to 2 minutes.
                        </p>
                      </div>
                    </div>
                    <div className="flex items-center justify-end gap-2 pt-1">
                      <button
                        type="button"
                        onClick={() => setConfirmingAction(null)}
                        className="px-3 py-1.5 text-xs font-medium rounded-lg text-slate-700 bg-white border border-slate-300 hover:bg-slate-100 transition-colors"
                      >
                        Cancel
                      </button>
                      <button
                        type="button"
                        onClick={() => handleExecuteAction("restart")}
                        className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-lg text-white bg-amber-600 hover:bg-amber-700 transition-colors shadow-2xs"
                      >
                        <RotateCcw className="w-3.5 h-3.5" />
                        <span>Confirm Restart</span>
                      </button>
                    </div>
                  </div>
                )}

                {/* Action Buttons Row */}
                {confirmingAction === null && (
                  <div className="flex flex-wrap items-center gap-2.5 pt-1">
                    {/* Start Button */}
                    <button
                      type="button"
                      onClick={() => handleExecuteAction("start")}
                      disabled={startDisabled}
                      title={startDisabledReason}
                      className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-lg text-xs font-semibold text-white bg-emerald-600 hover:bg-emerald-700 active:bg-emerald-800 transition-colors disabled:opacity-40 disabled:cursor-not-allowed shadow-2xs"
                    >
                      <Play className="w-3.5 h-3.5 fill-current" />
                      <span>Start Device</span>
                    </button>

                    {/* Stop Button */}
                    <button
                      type="button"
                      onClick={() => setConfirmingAction("stop")}
                      disabled={stopDisabled}
                      title={stopDisabledReason}
                      className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-lg text-xs font-semibold text-rose-700 bg-white border border-rose-300/80 hover:bg-rose-50 active:bg-rose-100 transition-colors disabled:opacity-40 disabled:cursor-not-allowed shadow-2xs"
                    >
                      <Square className="w-3.5 h-3.5 fill-current" />
                      <span>Stop Device</span>
                    </button>

                    {/* Restart Button */}
                    <button
                      type="button"
                      onClick={() => setConfirmingAction("restart")}
                      disabled={restartDisabled}
                      title={restartDisabledReason}
                      className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-lg text-xs font-semibold text-amber-800 bg-white border border-amber-300 hover:bg-amber-50 active:bg-amber-100 transition-colors disabled:opacity-40 disabled:cursor-not-allowed shadow-2xs"
                    >
                      <RotateCcw className="w-3.5 h-3.5" />
                      <span>Restart Device</span>
                    </button>

                    {startDisabledReason && !isActionDisabled && (
                      <span className="text-[11px] text-slate-400 italic ml-auto hidden sm:inline">
                        {isReady ? "Ready & running" : isContainerRunning ? "Container running" : ""}
                      </span>
                    )}
                  </div>
                )}
              </div>

              {/* Readiness Banner with Clear Transitional States */}
              {status.ready ? (
                <div className="p-4 rounded-xl border border-emerald-200 bg-emerald-50/90 text-emerald-900 flex items-start gap-3.5 shadow-2xs">
                  <CheckCircle2 className="w-5 h-5 text-emerald-600 shrink-0 mt-0.5" />
                  <div className="space-y-0.5">
                    <h4 className="text-sm font-bold text-emerald-900">
                      Device is Ready for Operations
                    </h4>
                    <p className="text-xs text-emerald-700 leading-relaxed">
                      All lifecycle criteria are satisfied: Docker container is
                      running, Android OS boot is complete, and ADB is verified in
                      &apos;device&apos; state.
                    </p>
                  </div>
                </div>
              ) : status.runtime_status === "starting" ? (
                <div className="p-4 rounded-xl border border-sky-200 bg-sky-50/90 text-sky-950 flex items-start gap-3.5 shadow-2xs">
                  <Loader2 className="w-5 h-5 text-sky-600 animate-spin shrink-0 mt-0.5" />
                  <div className="space-y-0.5">
                    <h4 className="text-sm font-bold text-sky-950">
                      Device is Starting (Transitional State)
                    </h4>
                    <p className="text-xs text-sky-800 leading-relaxed">
                      Docker container is running, and Android OS boot is in
                      progress (<code className="font-mono text-sky-900">sys.boot_completed = 0</code>). ADB connection will be verified once boot finishes. Click &apos;Refresh Status&apos; to update.
                    </p>
                  </div>
                </div>
              ) : status.runtime_status === "degraded" ? (
                <div className="p-4 rounded-xl border border-amber-200 bg-amber-50/90 text-amber-950 flex items-start gap-3.5 shadow-2xs">
                  <AlertTriangle className="w-5 h-5 text-amber-600 shrink-0 mt-0.5" />
                  <div className="space-y-0.5">
                    <h4 className="text-sm font-bold text-amber-950">
                      Device is Degraded (Transitional State)
                    </h4>
                    <p className="text-xs text-amber-800 leading-relaxed">
                      Docker container is running and Android OS boot is completed, but ADB is offline or unavailable (<code className="font-mono text-amber-900">{status.adb_state}</code>). Click &apos;Restart Device&apos; above to re-establish the ADB connection.
                    </p>
                  </div>
                </div>
              ) : status.runtime_status === "stopped" ? (
                <div className="p-4 rounded-xl border border-slate-300 bg-slate-100 text-slate-800 flex items-start gap-3.5 shadow-2xs">
                  <Square className="w-5 h-5 text-slate-600 fill-slate-600 shrink-0 mt-0.5" />
                  <div className="space-y-0.5">
                    <h4 className="text-sm font-bold text-slate-900">
                      Device is Stopped
                    </h4>
                    <p className="text-xs text-slate-600 leading-relaxed">
                      The Redroid container is halted. Persistent data (apps, settings, accounts) is preserved. Click &apos;Start Device&apos; above to launch the runtime.
                    </p>
                  </div>
                </div>
              ) : (
                <div className="p-4 rounded-xl border border-rose-200 bg-rose-50/90 text-rose-900 flex items-start gap-3.5 shadow-2xs">
                  <AlertCircle className="w-5 h-5 text-rose-600 shrink-0 mt-0.5" />
                  <div className="space-y-0.5">
                    <h4 className="text-sm font-bold text-rose-900">
                      Device is Not Ready
                    </h4>
                    <p className="text-xs text-rose-700 leading-relaxed">
                      {status.container_status !== "running"
                        ? `Docker container is "${status.container_status}" (expected "running"). Click "Start Device" above to launch.`
                        : !status.boot_completed
                        ? "Android OS boot is still pending or incomplete."
                        : status.adb_state !== "device"
                        ? `ADB state is "${status.adb_state}" (expected "device").`
                        : "One or more lifecycle conditions are not satisfied."}
                    </p>
                  </div>
                </div>
              )}

              {/* Diagnostic Cards Grid */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5">
                {/* 1. Docker Container State */}
                <div
                  className="p-4 rounded-xl border border-slate-200/90 bg-slate-50/50 space-y-2"
                  title="Docker container daemon inspection state"
                >
                  <div className="flex items-center justify-between">
                    <span className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider flex items-center gap-1.5">
                      <Server className="w-3.5 h-3.5 text-slate-400" />
                      Docker Container
                    </span>
                    <span
                      className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-semibold border ${
                        status.container_status === "running"
                          ? "bg-emerald-50 text-emerald-700 border-emerald-200"
                          : "bg-slate-100 text-slate-700 border-slate-300"
                      }`}
                    >
                      <span
                        className={`w-1.5 h-1.5 rounded-full ${
                          status.container_status === "running"
                            ? "bg-emerald-500"
                            : "bg-slate-400"
                        }`}
                      />
                      <span className="capitalize">{status.container_status}</span>
                    </span>
                  </div>
                  <div>
                    <p className="text-xs text-slate-400">Container Name</p>
                    <p className="font-mono text-xs font-semibold text-slate-800 truncate select-all">
                      {status.docker_container_name}
                    </p>
                  </div>
                </div>

                {/* 2. Android Boot State */}
                <div
                  className="p-4 rounded-xl border border-slate-200/90 bg-slate-50/50 space-y-2"
                  title="Android OS boot completion status from sys.boot_completed system property"
                >
                  <div className="flex items-center justify-between">
                    <span className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider flex items-center gap-1.5">
                      <Smartphone className="w-3.5 h-3.5 text-slate-400" />
                      Android Boot State
                    </span>
                    <span
                      className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-semibold border ${
                        status.boot_completed
                          ? "bg-emerald-50 text-emerald-700 border-emerald-200"
                          : "bg-amber-50 text-amber-700 border-amber-200"
                      }`}
                    >
                      {status.boot_completed ? (
                        <CheckCircle2 className="w-3 h-3 text-emerald-600" />
                      ) : (
                        <AlertCircle className="w-3 h-3 text-amber-600" />
                      )}
                      <span>
                        {status.boot_completed ? "Completed" : "Incomplete"}
                      </span>
                    </span>
                  </div>
                  <div>
                    <p className="text-xs text-slate-400">System Property</p>
                    <p className="font-mono text-xs font-semibold text-slate-800">
                      sys.boot_completed = {status.boot_completed ? "1" : "0"}
                    </p>
                  </div>
                </div>

                {/* 3. ADB State */}
                <div
                  className="p-4 rounded-xl border border-slate-200/90 bg-slate-50/50 space-y-2"
                  title="Android Debug Bridge connection status to Redroid runtime port"
                >
                  <div className="flex items-center justify-between">
                    <span className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider flex items-center gap-1.5">
                      <Terminal className="w-3.5 h-3.5 text-slate-400" />
                      ADB Connection
                    </span>
                    <span
                      className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-semibold border ${
                        status.adb_state === "device"
                          ? "bg-emerald-50 text-emerald-700 border-emerald-200"
                          : "bg-rose-50 text-rose-700 border-rose-200"
                      }`}
                    >
                      {status.adb_state === "device" ? (
                        <CheckCircle2 className="w-3 h-3 text-emerald-600" />
                      ) : (
                        <AlertCircle className="w-3 h-3 text-rose-600" />
                      )}
                      <span className="font-mono">{status.adb_state}</span>
                    </span>
                  </div>
                  <div>
                    <p className="text-xs text-slate-400">Serial Endpoint</p>
                    <p className="font-mono text-xs font-semibold text-slate-800 truncate select-all">
                      {status.adb_serial}
                    </p>
                  </div>
                </div>

                {/* 4. Reconciled System State */}
                <div
                  className="p-4 rounded-xl border border-slate-200/90 bg-slate-50/50 space-y-2"
                  title="Database reconciled device and runtime statuses"
                >
                  <div className="flex items-center justify-between">
                    <span className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider flex items-center gap-1.5">
                      <Cpu className="w-3.5 h-3.5 text-slate-400" />
                      Reconciled Database
                    </span>
                    <span className="text-[11px] font-mono font-medium text-slate-500">
                      Runtime #{status.runtime_id}
                    </span>
                  </div>
                  <div className="flex items-center justify-between gap-2 pt-0.5">
                    <div>
                      <p className="text-[10px] text-slate-400 uppercase">Device</p>
                      <p className="text-xs font-semibold text-slate-800 capitalize">
                        {status.device_status}
                      </p>
                    </div>
                    <div>
                      <p className="text-[10px] text-slate-400 uppercase">Runtime</p>
                      <p className="text-xs font-semibold text-slate-800 capitalize">
                        {status.runtime_status}
                      </p>
                    </div>
                    <div>
                      <p className="text-[10px] text-slate-400 uppercase">Readiness</p>
                      <DeviceReadinessBadge
                        ready={status.ready}
                        runtimeStatus={status.runtime_status}
                        size="sm"
                      />
                    </div>
                  </div>
                </div>
              </div>

              {/* Raw JSON Telemetry Collapsible */}
              <div className="border border-slate-200 rounded-xl overflow-hidden">
                <button
                  type="button"
                  onClick={() => setShowRawJson((prev) => !prev)}
                  className="w-full px-4 py-2.5 bg-slate-50 hover:bg-slate-100 flex items-center justify-between text-xs font-medium text-slate-700 transition-colors"
                >
                  <span className="flex items-center gap-2">
                    <FileJson className="w-4 h-4 text-slate-400" />
                    <span>Raw Lifecycle Status Payload</span>
                  </span>
                  {showRawJson ? (
                    <ChevronUp className="w-4 h-4 text-slate-400" />
                  ) : (
                    <ChevronDown className="w-4 h-4 text-slate-400" />
                  )}
                </button>
                {showRawJson && (
                  <pre className="p-3 bg-slate-900 text-slate-100 font-mono text-[11px] overflow-x-auto leading-relaxed">
                    {JSON.stringify(status, null, 2)}
                  </pre>
                )}
              </div>
            </div>
          )}
        </div>

        {/* Modal Footer */}
        <div className="flex items-center justify-between px-6 py-3.5 border-t border-slate-100 bg-slate-50/60">
          <div className="text-[11px] text-slate-400 font-mono">
            /devices/{device.id}/(status|start|stop|restart)
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={handleRefreshClick}
              disabled={isLoading || isRefreshing || actionRunning !== null}
              className="inline-flex items-center gap-1.5 px-3 py-2 border border-slate-200 text-xs font-semibold rounded-lg text-slate-700 bg-white hover:bg-slate-50 transition-colors shadow-2xs disabled:opacity-50"
            >
              <RefreshCw
                className={`w-3.5 h-3.5 ${
                  isLoading || isRefreshing ? "animate-spin text-slate-500" : ""
                }`}
              />
              <span>Refresh Status</span>
            </button>
            <button
              type="button"
              onClick={onClose}
              disabled={actionRunning !== null}
              className="px-4 py-2 text-xs font-semibold text-slate-700 bg-slate-200/80 hover:bg-slate-300 rounded-lg transition-colors disabled:opacity-40"
            >
              Close
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

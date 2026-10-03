"use client";

import React, { useState, useEffect, useRef } from "react";
import {
  AlertTriangle,
  Loader2,
  Trash2,
  CheckCircle2,
  ShieldCheck,
  FolderLock,
  Copy,
  Check,
  RefreshCw,
  X,
} from "lucide-react";
import { Device, formatApiError } from "@/types/device";
import {
  RedroidDeprovisioningStatus,
  RedroidProvisioningStatus,
  ProvisioningApiError,
} from "@/types/provisioning";
import { provisioningService } from "@/services/provisioningService";
import {
  provisioningRegistry,
  ManagedProvisioningRecord,
} from "@/services/provisioningRegistry";

interface DeviceDeprovisionModalProps {
  isOpen: boolean;
  onClose: () => void;
  device: Device | null;
  provisioningRecord?: ManagedProvisioningRecord | null;
  onDeprovisionComplete?: (summary: {
    name: string;
    deviceId: number;
    dataPath: string | null;
  }) => void;
}

export function DeviceDeprovisionModal({
  isOpen,
  onClose,
  device,
  provisioningRecord: initialRecord,
  onDeprovisionComplete,
}: DeviceDeprovisionModalProps) {
  // Current active provisioning record (either passed in or looked up from registry)
  const [record, setRecord] = useState<ManagedProvisioningRecord | null>(() => {
    if (!device) return null;
    return initialRecord || provisioningRegistry.getByDeviceId(device.id);
  });
  const [liveDetails, setLiveDetails] = useState<RedroidProvisioningStatus | null>(null);
  const [isLoadingDetails, setIsLoadingDetails] = useState(false);

  // Deprovisioning execution state
  const [isDeprovisioning, setIsDeprovisioning] = useState(false);
  const [isPolling, setIsPolling] = useState(false);
  const [deprovisionResult, setDeprovisionResult] =
    useState<RedroidDeprovisioningStatus | null>(null);
  const [error, setError] = useState<{
    message: string;
    statusCode?: number;
    provisioningId?: string;
  } | null>(null);

  // Safety confirmation check
  const [confirmedUnderstanding, setConfirmedUnderstanding] = useState(false);
  const [copiedDataPath, setCopiedDataPath] = useState(false);

  const pollTimerRef = useRef<NodeJS.Timeout | null>(null);
  const pollAttemptsRef = useRef<number>(0);
  const MAX_POLL_ATTEMPTS = 60; // 60 seconds bounded polling

  // Cleanup polling timer
  useEffect(() => {
    return () => {
      if (pollTimerRef.current) {
        clearInterval(pollTimerRef.current);
        pollTimerRef.current = null;
      }
    };
  }, []);

  // Fetch latest provisioning details on open
  useEffect(() => {
    if (!isOpen || !device) {
      if (pollTimerRef.current) {
        clearInterval(pollTimerRef.current);
        pollTimerRef.current = null;
      }
      return;
    }

    const foundRecord =
      initialRecord || provisioningRegistry.getByDeviceId(device.id);
    if (foundRecord) {
      provisioningService
        .getProvisioning(foundRecord.provisioningId)
        .then((status) => {
          setLiveDetails(status);
          const updated = provisioningRegistry.registerFromStatus(status, device.id);
          if (updated) {
            setRecord(updated);
          }
        })
        .catch(() => {
          // If 404 or network error, keep using foundRecord fields
        });
    }
  }, [isOpen, device, initialRecord]);

  if (!isOpen || !device) return null;

  const activeProvisioningId =
    record?.provisioningId || liveDetails?.provisioning_id || "";
  const activeContainerName =
    liveDetails?.container_name || record?.containerName || "redroid-device";
  const activeAdbSerial =
    liveDetails?.adb_serial || record?.adbSerial || "localhost:5555";
  const activeDataPath =
    liveDetails?.data_path || record?.dataPath || null;

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
            "Deprovisioning verification timed out. You can check status below.",
          provisioningId,
        });
        return;
      }

      try {
        const status = await provisioningService.getProvisioning(provisioningId);
        if (status.state === "deprovisioned") {
          stopPolling();
          // Finalize with full deprovisioning status
          const finalStatus: RedroidDeprovisioningStatus = {
            provisioning_id: status.provisioning_id,
            state: status.state,
            container_removed: status.container_removed ?? true,
            network_removed: status.network_removed ?? true,
            data_preserved: status.data_preserved ?? true,
            data_path: status.data_path,
            device_id: status.device_id,
            runtime_id: status.runtime_id,
            error_code: status.error_code,
            error_message: status.error_message,
            created_at: status.created_at,
            updated_at: status.updated_at,
          };
          setDeprovisionResult(finalStatus);
          provisioningRegistry.remove(provisioningId);
          if (device) provisioningRegistry.remove(device.id);
        } else if (status.state === "deprovision_failed") {
          stopPolling();
          setError({
            message:
              status.error_message ||
              "Managed Redroid deprovisioning requires recovery. Resources were preserved safely.",
            provisioningId: status.provisioning_id,
          });
        }
      } catch {
        // Transient check error
      }
    }, 1000);
  };

  const handleDeprovision = async () => {
    if (!activeProvisioningId) {
      setError({
        message:
          "No provisioning record found for this device. Deprovisioning requires a valid provisioning ID.",
      });
      return;
    }

    setError(null);
    setIsDeprovisioning(true);

    try {
      const result = await provisioningService.deprovisionDevice(
        activeProvisioningId
      );

      if (result.state === "deprovisioned") {
        setIsDeprovisioning(false);
        setDeprovisionResult(result);
        provisioningRegistry.remove(activeProvisioningId);
        provisioningRegistry.remove(device.id);
      } else if (result.state === "deprovision_failed") {
        setIsDeprovisioning(false);
        setError({
          message:
            result.error_message ||
            "Managed Redroid deprovisioning requires recovery. Resources were preserved safely.",
          provisioningId: activeProvisioningId,
        });
      } else {
        // 202 Accepted or deprovisioning in progress
        setIsDeprovisioning(false);
        startPolling(activeProvisioningId);
      }
    } catch (err: unknown) {
      setIsDeprovisioning(false);
      let message = formatApiError(err);
      let statusCode: number | undefined;
      let provId: string | undefined = activeProvisioningId;

      if (err instanceof ProvisioningApiError) {
        statusCode = err.status;
        if (err.provisioningId) provId = err.provisioningId;
        if (err.deprovisionStatus) {
          message =
            err.deprovisionStatus.error_message ||
            "Managed Redroid deprovisioning requires recovery. Resources were preserved safely.";
        }
      }

      // Safety: Never expose stack traces or raw docker command logs
      if (message.includes("Traceback") || message.includes("docker: Error")) {
        message = "Managed Redroid deprovisioning requires recovery";
      }

      setError({
        message,
        statusCode,
        provisioningId: provId,
      });
    }
  };

  const handleCheckStatus = async () => {
    if (!activeProvisioningId) return;
    setError(null);
    setIsLoadingDetails(true);
    try {
      const status = await provisioningService.getProvisioning(
        activeProvisioningId
      );
      setLiveDetails(status);
      if (status.state === "deprovisioned") {
        setDeprovisionResult({
          provisioning_id: status.provisioning_id,
          state: status.state,
          container_removed: status.container_removed ?? true,
          network_removed: status.network_removed ?? true,
          data_preserved: status.data_preserved ?? true,
          data_path: status.data_path,
          device_id: status.device_id,
          runtime_id: status.runtime_id,
          error_code: status.error_code,
          error_message: status.error_message,
          created_at: status.created_at,
          updated_at: status.updated_at,
        });
        provisioningRegistry.remove(activeProvisioningId);
        provisioningRegistry.remove(device.id);
      } else if (status.state === "deprovision_failed") {
        setError({
          message:
            status.error_message ||
            "Managed Redroid deprovisioning requires recovery. Resources were preserved safely.",
          provisioningId: activeProvisioningId,
        });
      }
    } catch (err: unknown) {
      setError({
        message: formatApiError(err),
        provisioningId: activeProvisioningId,
      });
    } finally {
      setIsLoadingDetails(false);
    }
  };

  const handleCopyPath = () => {
    if (activeDataPath && typeof navigator !== "undefined" && navigator.clipboard) {
      navigator.clipboard.writeText(activeDataPath);
      setCopiedDataPath(true);
      setTimeout(() => setCopiedDataPath(false), 2000);
    }
  };

  const handleDone = () => {
    onClose();
    if (onDeprovisionComplete) {
      onDeprovisionComplete({
        name: device.name,
        deviceId: device.id,
        dataPath: activeDataPath,
      });
    }
  };

  const isWorking = isDeprovisioning || isPolling || isLoadingDetails;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-xs">
      <div
        className="bg-white rounded-2xl shadow-2xl border border-slate-200 w-full max-w-xl overflow-hidden animate-in fade-in zoom-in-95 duration-150 flex flex-col max-h-[90vh]"
        role="dialog"
        aria-modal="true"
        aria-labelledby="deprovision-dialog-title"
      >
        {/* Header */}
        <div className="p-5 border-b border-slate-100 flex items-start justify-between bg-gradient-to-r from-rose-50/70 via-white to-amber-50/40">
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-xl bg-rose-100 text-rose-700 shadow-2xs">
              <AlertTriangle className="w-5 h-5" />
            </div>
            <div>
              <h3
                id="deprovision-dialog-title"
                className="text-base font-bold text-slate-900 flex items-center gap-2"
              >
                <span>Deprovision Device</span>
                <span className="text-xs px-2 py-0.5 rounded-full font-mono font-medium bg-rose-100/80 text-rose-800 border border-rose-200">
                  Managed Redroid
                </span>
              </h3>
              <p className="text-xs text-slate-500 mt-0.5">
                Teardown host container and bridge network while safely preserving persistent data.
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            disabled={isWorking && !deprovisionResult}
            className="p-1.5 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition-colors disabled:opacity-30"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Modal Body */}
        <div className="p-6 space-y-5 overflow-y-auto flex-1 text-xs">
          {/* SUCCESS STATE */}
          {deprovisionResult ? (
            <div className="space-y-4 animate-in fade-in duration-200">
              <div className="p-4 rounded-xl bg-emerald-50 border border-emerald-200 flex items-start gap-3">
                <CheckCircle2 className="w-5 h-5 text-emerald-600 shrink-0 mt-0.5" />
                <div className="space-y-1">
                  <h4 className="text-sm font-bold text-emerald-950">
                    Device Deprovisioned Successfully
                  </h4>
                  <p className="text-xs text-emerald-800 leading-relaxed">
                    Device <strong>{device.name}</strong> has been deprovisioned and removed from active management. All host container and network resources were cleanly destroyed.
                  </p>
                </div>
              </div>

              {/* Resource Teardown Summary */}
              <div className="p-4 rounded-xl bg-slate-50 border border-slate-200/90 space-y-3">
                <h5 className="font-semibold text-slate-800 text-[11px] uppercase tracking-wider">
                  Teardown Summary
                </h5>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
                  <div className="p-3 bg-white rounded-lg border border-slate-200/80 flex items-center justify-between">
                    <span className="text-slate-600 font-medium">Container Removed:</span>
                    <span className="font-semibold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded border border-emerald-200">
                      {deprovisionResult.container_removed ? "Yes (Destroyed)" : "No"}
                    </span>
                  </div>
                  <div className="p-3 bg-white rounded-lg border border-slate-200/80 flex items-center justify-between">
                    <span className="text-slate-600 font-medium">Network Removed:</span>
                    <span className="font-semibold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded border border-emerald-200">
                      {deprovisionResult.network_removed ? "Yes (Destroyed)" : "No"}
                    </span>
                  </div>
                </div>

                <div className="p-3.5 bg-emerald-50/60 rounded-lg border border-emerald-200 flex items-start gap-2.5">
                  <ShieldCheck className="w-4 h-4 text-emerald-600 shrink-0 mt-0.5" />
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <span className="font-bold text-emerald-900">
                        Persistent Data Preserved
                      </span>
                      <span className="text-[10px] px-1.5 py-0.2 rounded bg-emerald-100 text-emerald-800 font-semibold">
                        Safe
                      </span>
                    </div>
                    <p className="text-[11px] text-emerald-800">
                      Persistent `/data` is intact on host disk and was not deleted.
                    </p>
                    {deprovisionResult.data_path && (
                      <div className="mt-1 flex items-center gap-1.5 font-mono text-[11px] bg-white p-2 rounded border border-emerald-200 text-slate-800 break-all select-all">
                        <span className="flex-1">{deprovisionResult.data_path}</span>
                        <button
                          type="button"
                          onClick={handleCopyPath}
                          className="p-1 hover:bg-slate-100 rounded text-slate-500 hover:text-slate-700"
                          title="Copy path"
                        >
                          {copiedDataPath ? (
                            <Check className="w-3.5 h-3.5 text-emerald-600" />
                          ) : (
                            <Copy className="w-3.5 h-3.5" />
                          )}
                        </button>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            </div>
          ) : (
            /* NORMAL CONFIRMATION & IN-PROGRESS FLOW */
            <>
              {/* Context metadata block */}
              <div className="p-3.5 rounded-xl bg-slate-50 border border-slate-200/90 space-y-2">
                <div className="flex items-center justify-between pb-1.5 border-b border-slate-200/60">
                  <span className="text-slate-500 font-medium">Target Device:</span>
                  <span className="font-bold text-slate-900">
                    {device.name} (ID #{device.id})
                  </span>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-[11px]">
                  <div>
                    <span className="text-slate-500">Container Name: </span>
                    <code className="px-1.5 py-0.5 rounded bg-white border border-slate-200 font-mono text-slate-800">
                      {activeContainerName}
                    </code>
                  </div>
                  <div>
                    <span className="text-slate-500">ADB Serial: </span>
                    <code className="px-1.5 py-0.5 rounded bg-white border border-slate-200 font-mono text-slate-800">
                      {activeAdbSerial}
                    </code>
                  </div>
                </div>

                {activeProvisioningId && (
                  <div className="text-[11px] pt-1">
                    <span className="text-slate-500">Provisioning ID: </span>
                    <code className="px-1.5 py-0.5 rounded bg-white border border-slate-200 font-mono text-[10px] text-slate-700 select-all">
                      {activeProvisioningId}
                    </code>
                  </div>
                )}
              </div>

              {/* What will happen vs What will NOT happen */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {/* What WILL happen */}
                <div className="p-3.5 rounded-xl bg-rose-50/50 border border-rose-200 space-y-2">
                  <div className="flex items-center gap-1.5 font-bold text-rose-900 text-xs">
                    <Trash2 className="w-4 h-4 text-rose-600" />
                    <span>What WILL Happen</span>
                  </div>
                  <ul className="space-y-1.5 text-[11px] text-rose-800 list-disc list-inside">
                    <li>scrcpy screen window closed if open</li>
                    <li>Redroid container stopped if running</li>
                    <li>Docker container removed</li>
                    <li>Dedicated Docker network removed</li>
                    <li>Device & Runtime removed from active DB</li>
                  </ul>
                </div>

                {/* What will NOT happen */}
                <div className="p-3.5 rounded-xl bg-emerald-50/50 border border-emerald-200 space-y-2">
                  <div className="flex items-center gap-1.5 font-bold text-emerald-900 text-xs">
                    <ShieldCheck className="w-4 h-4 text-emerald-600" />
                    <span>What Will NOT Happen</span>
                  </div>
                  <ul className="space-y-1.5 text-[11px] text-emerald-800 list-disc list-inside">
                    <li>
                      <strong>Persistent /data is NOT deleted</strong>
                    </li>
                    <li>App data and system state remain preserved</li>
                    <li>Host directory left intact for safety</li>
                    <li>Device number reserved to avoid collisions</li>
                  </ul>
                </div>
              </div>

              {/* Persistent Data Path Notice */}
              {activeDataPath && (
                <div className="p-3 rounded-xl bg-slate-50 border border-slate-200 space-y-1.5">
                  <div className="flex items-center justify-between text-slate-600 font-medium text-[11px]">
                    <span className="flex items-center gap-1.5">
                      <FolderLock className="w-3.5 h-3.5 text-slate-500" />
                      Preserved Data Path (Intact on Host Disk):
                    </span>
                    <button
                      type="button"
                      onClick={handleCopyPath}
                      className="inline-flex items-center gap-1 text-[10px] text-indigo-600 hover:text-indigo-800 font-semibold"
                    >
                      {copiedDataPath ? (
                        <>
                          <Check className="w-3 h-3 text-emerald-600" />
                          <span>Copied</span>
                        </>
                      ) : (
                        <>
                          <Copy className="w-3 h-3" />
                          <span>Copy</span>
                        </>
                      )}
                    </button>
                  </div>
                  <div className="p-2 rounded bg-white border border-slate-200 font-mono text-[11px] text-slate-700 break-all select-all">
                    {activeDataPath}
                  </div>
                </div>
              )}

              {/* Error Alert */}
              {error && (
                <div className="p-3.5 rounded-xl bg-rose-50 border border-rose-200 text-rose-800 space-y-2">
                  <div className="flex items-start gap-2">
                    <AlertTriangle className="w-4 h-4 text-rose-600 shrink-0 mt-0.5" />
                    <div className="space-y-1 flex-1">
                      <span className="font-semibold block">Deprovisioning Error</span>
                      <p className="text-[11px] leading-relaxed">{error.message}</p>
                    </div>
                  </div>
                  <div className="text-[10px] text-rose-700 bg-white/60 p-2 rounded border border-rose-200 flex items-center justify-between">
                    <span>Resources were preserved safely to prevent data loss.</span>
                    <button
                      type="button"
                      onClick={handleCheckStatus}
                      className="inline-flex items-center gap-1 font-semibold text-rose-900 hover:underline"
                    >
                      <RefreshCw className="w-3 h-3" />
                      <span>Check Status</span>
                    </button>
                  </div>
                </div>
              )}

              {/* In-Progress Sequence Indicator */}
              {(isDeprovisioning || isPolling) && (
                <div className="p-3.5 rounded-xl bg-blue-50 border border-blue-200 text-blue-900 space-y-2 animate-in fade-in duration-150">
                  <div className="flex items-center gap-2 font-bold text-xs">
                    <Loader2 className="w-4 h-4 text-blue-600 animate-spin shrink-0" />
                    <span>Deprovisioning in progress...</span>
                  </div>
                  <p className="text-[11px] text-blue-800 leading-relaxed">
                    Executing teardown sequence: closing screen &rarr; stopping container &rarr; verifying resource ownership &rarr; removing container &rarr; removing bridge network &rarr; archiving active database records.
                  </p>
                </div>
              )}

              {/* User Confirmation Checkbox */}
              {!isWorking && (
                <label className="flex items-start gap-2.5 p-3 rounded-xl border border-slate-200 bg-slate-50/60 hover:bg-slate-50 cursor-pointer transition-colors">
                  <input
                    type="checkbox"
                    checked={confirmedUnderstanding}
                    onChange={(e) => setConfirmedUnderstanding(e.target.checked)}
                    className="mt-0.5 rounded border-slate-300 text-rose-600 focus:ring-rose-500 w-4 h-4"
                  />
                  <span className="text-[11px] text-slate-700 leading-normal select-none">
                    I understand that the container and network will be destroyed and active management records deleted, but persistent data at{" "}
                    <code className="px-1 py-0.2 rounded bg-white border border-slate-200 font-mono text-[10px]">
                      {activeDataPath || "allocated path"}
                    </code>{" "}
                    remains safely preserved on disk.
                  </span>
                </label>
              )}
            </>
          )}
        </div>

        {/* Footer */}
        <div className="p-4 border-t border-slate-100 bg-slate-50 flex items-center justify-between gap-3">
          {deprovisionResult ? (
            <div className="flex items-center justify-end w-full">
              <button
                type="button"
                onClick={handleDone}
                className="inline-flex items-center gap-1.5 px-4 py-2 bg-emerald-600 text-white rounded-lg text-xs font-semibold hover:bg-emerald-700 transition-colors shadow-2xs"
              >
                <Check className="w-3.5 h-3.5" />
                <span>Done</span>
              </button>
            </div>
          ) : (
            <>
              <button
                type="button"
                onClick={onClose}
                disabled={isWorking}
                className="px-3.5 py-2 border border-slate-200 rounded-lg text-slate-600 hover:bg-white text-xs font-medium transition-colors disabled:opacity-50"
              >
                Cancel
              </button>
              <div className="flex items-center gap-2">
                {error && (
                  <button
                    type="button"
                    onClick={handleCheckStatus}
                    disabled={isWorking}
                    className="px-3 py-2 border border-slate-200 bg-white rounded-lg text-slate-700 hover:bg-slate-100 text-xs font-medium transition-colors disabled:opacity-50 inline-flex items-center gap-1.5"
                  >
                    <RefreshCw className={`w-3.5 h-3.5 ${isLoadingDetails ? "animate-spin" : ""}`} />
                    <span>Check Status</span>
                  </button>
                )}
                <button
                  type="button"
                  onClick={handleDeprovision}
                  disabled={!confirmedUnderstanding || isWorking || !activeProvisioningId}
                  className="inline-flex items-center gap-1.5 px-4 py-2 bg-rose-600 text-white rounded-lg text-xs font-bold hover:bg-rose-700 transition-colors shadow-2xs disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {isWorking ? (
                    <>
                      <Loader2 className="w-3.5 h-3.5 animate-spin" />
                      <span>Deprovisioning...</span>
                    </>
                  ) : (
                    <>
                      <Trash2 className="w-3.5 h-3.5" />
                      <span>Deprovision Device</span>
                    </>
                  )}
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

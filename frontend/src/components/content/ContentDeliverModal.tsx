import { useState, useEffect, useRef, useCallback } from "react";
import {
  AlertCircle,
  AlertTriangle,
  CheckCircle2,
  Cpu,
  ExternalLink,
  Loader2,
  RefreshCw,
  Send,
  X,
} from "lucide-react";
import { contentService } from "@/services/contentService";
import { deviceService } from "@/services/deviceService";
import { runtimeService } from "@/services/runtimeService";
import {
  ContentAssetDetail,
  ContentDelivery,
  ContentDeliveryStatus,
  getContentErrorMessage,
} from "@/types/content";
import { Device } from "@/types/device";
import { Runtime } from "@/types/runtime";
import { ContentDeliveryBadge } from "./ContentDeliveryBadge";

interface ContentDeliverModalProps {
  isOpen: boolean;
  asset: ContentAssetDetail;
  onClose: () => void;
  onDeliveryComplete?: (delivery: ContentDelivery) => void;
  onOpenJob?: (jobId: number) => void;
}

export function ContentDeliverModal({
  isOpen,
  asset,
  onClose,
  onDeliveryComplete,
  onOpenJob,
}: ContentDeliverModalProps) {
  const [runtimes, setRuntimes] = useState<Runtime[]>([]);
  const [devicesMap, setDevicesMap] = useState<Record<number, Device>>({});
  const [loadingResources, setLoadingResources] = useState(true);
  const [selectedRuntimeId, setSelectedRuntimeId] = useState<number | null>(
    null
  );
  const [remoteFilename, setRemoteFilename] = useState(
    asset.current_version?.original_filename || ""
  );
  const [importMedia, setImportMedia] = useState(true);
  const [allowRepeat, setAllowRepeat] = useState(false);

  // Delivery state
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [activeDelivery, setActiveDelivery] = useState<ContentDelivery | null>(
    null
  );
  const [duplicateWarning, setDuplicateWarning] = useState<boolean>(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [screenWarning, setScreenWarning] = useState<string | null>(null);

  const pollTimerRef = useRef<NodeJS.Timeout | null>(null);

  const stopPolling = useCallback(() => {
    if (pollTimerRef.current) {
      clearInterval(pollTimerRef.current);
      pollTimerRef.current = null;
    }
  }, []);

  const currentVersion = asset.current_version;

  // Load runtimes and devices
  useEffect(() => {
    if (!isOpen) {
      stopPolling();
      return;
    }

    let ignore = false;
    Promise.all([
      runtimeService.getRuntimes({ page_size: 100 }),
      deviceService.getDevices({ page_size: 100 }),
    ])
      .then(([runtimesRes, devicesRes]) => {
        if (ignore) return;
        setRuntimes(
          runtimesRes.items.filter((r) => r.runtime_type === "redroid")
        );
        const devMap: Record<number, Device> = {};
        for (const d of devicesRes.items) {
          devMap[d.id] = d;
        }
        setDevicesMap(devMap);
      })
      .catch(() => {})
      .finally(() => {
        if (!ignore) setLoadingResources(false);
      });

    return () => {
      ignore = true;
    };
  }, [isOpen, stopPolling]);

  // Selected runtime details
  const selectedRuntime = runtimes.find((r) => r.id === selectedRuntimeId);
  const linkedDevice =
    selectedRuntime?.device_id !== null && selectedRuntime?.device_id !== undefined
      ? devicesMap[selectedRuntime.device_id]
      : undefined;

  // Check screen session status when runtime changes
  useEffect(() => {
    if (!linkedDevice) return;

    let ignore = false;
    deviceService
      .getDeviceScreenStatus(linkedDevice.id)
      .then((status) => {
        if (ignore) return;
        setScreenWarning(
          status.status === "open"
            ? "Device screen is currently open. Close screen before delivering content to avoid conflict."
            : null
        );
      })
      .catch(() => {
        if (!ignore) setScreenWarning(null);
      });

    return () => {
      ignore = true;
    };
  }, [linkedDevice]);

  // Poll active delivery
  const pollDelivery = useCallback(
    async (deliveryId: number) => {
      try {
        const updated = await contentService.getDelivery(deliveryId);
        setActiveDelivery(updated);

        const terminalStatuses: ContentDeliveryStatus[] = [
          "succeeded",
          "failed",
          "cancelled",
        ];
        if (terminalStatuses.includes(updated.status)) {
          stopPolling();
          if (onDeliveryComplete) {
            onDeliveryComplete(updated);
          }
        }
      } catch {
        // Continue next poll
      }
    },
    [stopPolling, onDeliveryComplete]
  );

  // Start polling when active delivery exists
  const activeDeliveryId = activeDelivery?.id;
  const activeDeliveryStatus = activeDelivery?.status;

  useEffect(() => {
    if (!activeDeliveryId || !activeDeliveryStatus) {
      stopPolling();
      return;
    }

    const terminalStatuses: ContentDeliveryStatus[] = [
      "succeeded",
      "failed",
      "cancelled",
    ];
    if (terminalStatuses.includes(activeDeliveryStatus)) {
      stopPolling();
      return;
    }

    stopPolling();
    pollTimerRef.current = setInterval(() => {
      pollDelivery(activeDeliveryId);
    }, 1500);

    return () => stopPolling();
  }, [activeDeliveryId, activeDeliveryStatus, pollDelivery, stopPolling]);

  const handleModalClose = useCallback(() => {
    stopPolling();
    onClose();
  }, [stopPolling, onClose]);

  // Escape key handler
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && isOpen && !isSubmitting) {
        handleModalClose();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, isSubmitting, handleModalClose]);

  // Submit delivery
  const handleDeliver = async (forceRepeat = false) => {
    if (!selectedRuntimeId) {
      setErrorMessage("Please select a target runtime.");
      return;
    }

    if (selectedRuntime?.status === "stopped") {
      setErrorMessage(
        "Device runtime is stopped. Start the device before delivering content."
      );
      return;
    }

    if (screenWarning) {
      setErrorMessage(
        "Close the device screen before delivering content."
      );
      return;
    }

    setIsSubmitting(true);
    setErrorMessage(null);
    setDuplicateWarning(false);

    try {
      const idempotencyKey =
        typeof crypto !== "undefined" && crypto.randomUUID
          ? crypto.randomUUID()
          : undefined;

      const result = await contentService.deliverContent(asset.id, {
        runtime_id: selectedRuntimeId,
        version_id: currentVersion?.id,
        filename: remoteFilename.trim() || undefined,
        import_media: importMedia,
        allow_repeat: forceRepeat || allowRepeat,
        idempotency_key: idempotencyKey,
      });

      setActiveDelivery(result.delivery);

      if (!result.created && !forceRepeat && !allowRepeat) {
        // Backend returned existing delivery because allow_repeat=false
        setDuplicateWarning(true);
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      setErrorMessage(getContentErrorMessage(null, msg));
    } finally {
      setIsSubmitting(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-xs animate-in fade-in duration-150">
      <div
        className="w-full max-w-xl rounded-2xl bg-white shadow-2xl border border-slate-200 overflow-hidden flex flex-col max-h-[92vh]"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between border-b border-slate-200 px-6 py-4 bg-slate-50/80">
          <div className="flex items-center gap-2.5">
            <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-blue-50 text-blue-600 border border-blue-200">
              <Send className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-base font-bold text-slate-900">
                Deliver to Runtime
              </h2>
              <p className="text-xs text-slate-500">
                Send media directly into an Android device&apos;s manager storage
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={handleModalClose}
            disabled={isSubmitting}
            className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-200 hover:text-slate-600 transition-colors disabled:opacity-50"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Modal Body */}
        <div className="overflow-y-auto p-6 space-y-5">
          {/* Asset Summary Banner */}
          <div className="rounded-xl border border-slate-200 bg-slate-50/70 p-3.5 flex items-center justify-between">
            <div>
              <span className="text-[10px] font-semibold uppercase tracking-wider text-slate-400 block">
                Selected Asset
              </span>
              <p className="text-xs font-bold text-slate-800 line-clamp-1">
                {asset.display_name}
              </p>
              <p className="text-[11px] text-slate-500 font-mono mt-0.5">
                Version v{currentVersion?.version_number || 1} •{" "}
                {currentVersion?.original_filename || "Ready Version"}
              </p>
            </div>
            <span className="px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200 text-xs font-semibold">
              Ready
            </span>
          </div>

          {/* Delivery Error Banner */}
          {errorMessage && (
            <div className="rounded-xl border border-rose-200 bg-rose-50/80 p-3.5 flex items-start gap-2.5 text-xs text-rose-800">
              <AlertCircle className="w-4 h-4 text-rose-600 shrink-0 mt-0.5" />
              <div className="flex-1">
                <span className="font-semibold block">Delivery Failed</span>
                <span>{errorMessage}</span>
              </div>
            </div>
          )}

          {/* Screen Conflict Warning */}
          {screenWarning && (
            <div className="rounded-xl border border-amber-200 bg-amber-50/80 p-3 flex items-start gap-2 text-xs text-amber-800">
              <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
              <span>{screenWarning}</span>
            </div>
          )}

          {/* Duplicate Delivery Banner (Requirement 16) */}
          {duplicateWarning && activeDelivery && (
            <div className="rounded-xl border border-amber-200 bg-amber-50/90 p-4 space-y-2.5 text-xs text-amber-900">
              <div className="flex items-start gap-2">
                <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
                <div>
                  <span className="font-bold block">
                    Already Delivered to this Runtime
                  </span>
                  <p className="text-[11px] text-amber-700 mt-0.5">
                    This content version was previously delivered to Runtime #
                    {activeDelivery.runtime_id_snapshot} on{" "}
                    {new Date(activeDelivery.created_at).toLocaleString()}. Accidental duplicate deliveries are blocked by default.
                  </p>
                </div>
              </div>
              <div className="flex justify-end gap-2 pt-1">
                <button
                  type="button"
                  onClick={() => handleDeliver(true)}
                  disabled={isSubmitting}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-amber-600 text-white font-semibold text-xs hover:bg-amber-700 transition-colors shadow-2xs"
                >
                  <RefreshCw className="w-3 h-3" />
                  <span>Deliver Again (Force Duplicate)</span>
                </button>
              </div>
            </div>
          )}

          {/* Active Delivery Progress & Result Card */}
          {activeDelivery && !duplicateWarning && (
            <div className="rounded-xl border border-slate-200 bg-slate-50/80 p-4 space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-slate-800 flex items-center gap-2">
                  <span>Delivery Status</span>
                  <ContentDeliveryBadge status={activeDelivery.status} />
                </span>
                <span className="font-mono text-[11px] text-slate-500">
                  Delivery #{activeDelivery.id}
                </span>
              </div>

              {activeDelivery.status === "succeeded" && (
                <div className="rounded-lg bg-emerald-50 border border-emerald-200 p-3 space-y-2 text-xs text-emerald-900">
                  <div className="flex items-center gap-1.5 font-bold text-emerald-800">
                    <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                    <span>Media Delivered Successfully</span>
                  </div>
                  <div className="grid grid-cols-2 gap-2 text-[11px]">
                    <div>
                      <span className="text-slate-400 block text-[10px] uppercase">
                        Remote Filename
                      </span>
                      <span className="font-mono text-slate-800 font-medium">
                        {activeDelivery.remote_filename}
                      </span>
                    </div>
                    <div>
                      <span className="text-slate-400 block text-[10px] uppercase">
                        Delivered At
                      </span>
                      <span className="text-slate-700 font-medium">
                        {activeDelivery.completed_at
                          ? new Date(activeDelivery.completed_at).toLocaleTimeString()
                          : "Just now"}
                      </span>
                    </div>
                  </div>
                  {activeDelivery.media_uri && (
                    <div className="pt-1 border-t border-emerald-100 text-[11px]">
                      <span className="text-emerald-700 font-semibold block text-[10px] uppercase">
                        Android MediaStore URI
                      </span>
                      <span className="font-mono text-slate-600 break-all">
                        {activeDelivery.media_uri}
                      </span>
                    </div>
                  )}
                  {onOpenJob && (
                    <button
                      type="button"
                      onClick={() => onOpenJob(activeDelivery.job_id)}
                      className="inline-flex items-center gap-1 text-[11px] text-blue-600 hover:underline pt-1"
                    >
                      <ExternalLink className="w-3 h-3" />
                      <span>View Automation Job #{activeDelivery.job_id}</span>
                    </button>
                  )}
                </div>
              )}

              {activeDelivery.status === "delivering" && (
                <div className="rounded-lg bg-blue-50 border border-blue-200 p-3 text-xs text-blue-800 flex items-center gap-2">
                  <Loader2 className="w-4 h-4 text-blue-600 animate-spin" />
                  <span>
                    Worker is transferring media and registering with Android MediaStore...
                  </span>
                </div>
              )}

              {activeDelivery.status === "failed" && (
                <div className="rounded-lg bg-rose-50 border border-rose-200 p-3 text-xs text-rose-800 space-y-1">
                  <span className="font-semibold block">Delivery Failed</span>
                  <p className="text-[11px] text-rose-700">
                    {getContentErrorMessage(
                      activeDelivery.error_code,
                      activeDelivery.error_message
                    )}
                  </p>
                  {onOpenJob && (
                    <button
                      type="button"
                      onClick={() => onOpenJob(activeDelivery.job_id)}
                      className="inline-flex items-center gap-1 text-[11px] text-blue-600 hover:underline pt-1"
                    >
                      <ExternalLink className="w-3 h-3" />
                      <span>Inspect Job #{activeDelivery.job_id}</span>
                    </button>
                  )}
                </div>
              )}
            </div>
          )}

          {/* Form Options (hidden or disabled if delivery in terminal success) */}
          {(!activeDelivery || activeDelivery.status !== "succeeded") && (
            <div className="space-y-4">
              {/* Exact Runtime Selector (Requirement 13) */}
              <div className="space-y-1.5">
                <label className="text-xs font-semibold text-slate-700 block">
                  Select Target Runtime <span className="text-rose-500">*</span>
                </label>
                {loadingResources ? (
                  <div className="animate-pulse h-10 rounded-lg bg-slate-100" />
                ) : runtimes.length === 0 ? (
                  <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-xs text-amber-800">
                    No active Redroid runtimes found. Please create or start a device first.
                  </div>
                ) : (
                  <select
                    value={selectedRuntimeId ?? ""}
                    onChange={(e) =>
                      setSelectedRuntimeId(
                        e.target.value ? parseInt(e.target.value, 10) : null
                      )
                    }
                    className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs text-slate-800 focus:border-blue-500 focus:outline-hidden"
                  >
                    <option value="">-- Choose an exact Redroid Runtime --</option>
                    {runtimes.map((r) => {
                      const dev =
                        r.device_id !== null ? devicesMap[r.device_id] : undefined;
                      const devLabel = dev ? dev.name : `Device #${r.device_id}`;
                      return (
                        <option key={r.id} value={r.id}>
                          Runtime #{r.id} — {devLabel} ({r.docker_container_name || "container"},{" "}
                          {r.adb_serial || "no-serial"}) [{r.status}]
                        </option>
                      );
                    })}
                  </select>
                )}

                {/* Selected Runtime Card */}
                {selectedRuntime && (
                  <div className="mt-2 rounded-lg border border-slate-200 bg-slate-50 p-3 text-[11px] space-y-1">
                    <div className="flex items-center justify-between">
                      <span className="font-semibold text-slate-800 flex items-center gap-1.5">
                        <Cpu className="w-3.5 h-3.5 text-blue-600" />
                        <span>Runtime #{selectedRuntime.id}</span>
                      </span>
                      <span
                        className={`px-1.5 py-0.5 rounded text-[10px] font-semibold uppercase ${
                          selectedRuntime.status === "running"
                            ? "bg-emerald-100 text-emerald-800"
                            : "bg-slate-200 text-slate-700"
                        }`}
                      >
                        {selectedRuntime.status}
                      </span>
                    </div>
                    <div className="grid grid-cols-2 gap-1 text-slate-600 font-mono text-[10px]">
                      <span>Container: {selectedRuntime.docker_container_name}</span>
                      <span>Serial: {selectedRuntime.adb_serial}</span>
                    </div>
                    {selectedRuntime.status === "stopped" && (
                      <p className="text-amber-700 font-semibold pt-1">
                        Warning: Device is stopped. Start it before delivering content.
                      </p>
                    )}
                  </div>
                )}
              </div>

              {/* Target Filename Input */}
              <div className="space-y-1.5">
                <label className="text-xs font-semibold text-slate-700 block">
                  Remote Destination Filename{" "}
                  <span className="text-slate-400 font-normal">
                    (saved under /sdcard/Download/TikTokManager/)
                  </span>
                </label>
                <input
                  type="text"
                  value={remoteFilename}
                  onChange={(e) => setRemoteFilename(e.target.value)}
                  placeholder="e.g. video-01.mp4"
                  maxLength={255}
                  className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-mono text-slate-800 focus:border-blue-500 focus:outline-hidden"
                />
              </div>

              {/* Toggles (Requirement 14) */}
              <div className="space-y-3 pt-1">
                {/* MediaStore Toggle */}
                <label className="flex items-start gap-2.5 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={importMedia}
                    onChange={(e) => setImportMedia(e.target.checked)}
                    className="mt-0.5 rounded border-slate-300 text-blue-600 focus:ring-blue-500"
                  />
                  <div>
                    <span className="text-xs font-semibold text-slate-800 block">
                      Register in Android MediaStore Gallery
                    </span>
                    <span className="text-[11px] text-slate-500 block">
                      Automatically triggers Android media scanner so the file appears immediately in the device Photos/Gallery app.
                    </span>
                  </div>
                </label>

                {/* Repeat Delivery Toggle */}
                <label className="flex items-start gap-2.5 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={allowRepeat}
                    onChange={(e) => setAllowRepeat(e.target.checked)}
                    className="mt-0.5 rounded border-slate-300 text-blue-600 focus:ring-blue-500"
                  />
                  <div>
                    <span className="text-xs font-semibold text-slate-800 block">
                      Allow Repeat Delivery
                    </span>
                    <span className="text-[11px] text-slate-500 block">
                      Permits redelivery even if this exact media version was already successfully delivered to this runtime.
                    </span>
                  </div>
                </label>
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="border-t border-slate-200 px-6 py-3.5 bg-slate-50 flex items-center justify-between">
          <div className="text-[11px] text-slate-500">
            {activeDelivery?.status === "succeeded"
              ? "Delivery finished"
              : isSubmitting
              ? "Executing delivery..."
              : "Ready to transfer"}
          </div>

          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={handleModalClose}
              disabled={isSubmitting}
              className="px-3.5 py-1.5 rounded-lg border border-slate-200 text-xs font-semibold text-slate-700 hover:bg-slate-100 disabled:opacity-50 transition-colors"
            >
              {activeDelivery?.status === "succeeded" ? "Close" : "Cancel"}
            </button>

            {(!activeDelivery || activeDelivery.status !== "succeeded") && (
              <button
                type="button"
                onClick={() => handleDeliver(false)}
                disabled={
                  isSubmitting ||
                  !selectedRuntimeId ||
                  selectedRuntime?.status === "stopped" ||
                  Boolean(screenWarning)
                }
                className="inline-flex items-center gap-1.5 px-4 py-1.5 rounded-lg bg-blue-600 text-xs font-semibold text-white shadow-2xs hover:bg-blue-700 disabled:opacity-50 transition-colors"
              >
                {isSubmitting ? (
                  <>
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    <span>Delivering...</span>
                  </>
                ) : (
                  <>
                    <Send className="w-3.5 h-3.5" />
                    <span>Deliver Content</span>
                  </>
                )}
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

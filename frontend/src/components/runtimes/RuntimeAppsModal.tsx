import React, { useState, useEffect, useRef, useCallback } from "react";
import { Runtime } from "@/types/runtime";
import { Device } from "@/types/device";
import { ManagedApp } from "@/types/managedApp";
import {
  PublishingReadiness,
  RuntimeAppInstallation,
  getRuntimeAppErrorMessage,
} from "@/types/runtimeApp";
import { runtimeAppService } from "@/services/runtimeAppService";
import { managedAppService } from "@/services/managedAppService";
import { formatApiError } from "@/types/runtime";
import {
  X,
  Package,
  ShieldCheck,
  CheckCircle2,
  AlertTriangle,
  RefreshCw,
  DownloadCloud,
  CheckCheck,
  AlertCircle,
  Loader2,
  Clock,
  Cpu,
} from "lucide-react";

interface RuntimeAppsModalProps {
  runtime: Runtime | null;
  device?: Device | null;
  isOpen: boolean;
  onClose: () => void;
}

export function RuntimeAppsModal({
  runtime,
  device,
  isOpen,
  onClose,
}: RuntimeAppsModalProps) {
  const [readiness, setReadiness] = useState<PublishingReadiness | null>(null);
  const [installations, setInstallations] = useState<RuntimeAppInstallation[]>([]);
  const [managedApps, setManagedApps] = useState<ManagedApp[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [actionSuccessMessage, setActionSuccessMessage] = useState<string | null>(null);
  const [operatingAppId, setOperatingAppId] = useState<number | null>(null);

  const pollTimerRef = useRef<NodeJS.Timeout | null>(null);

  const fetchData = useCallback(
    async (showLoading = true) => {
      if (!runtime) return;
      try {
        if (showLoading) setIsLoading(true);
        setErrorMessage(null);

        const [readinessRes, appsRes, managedAppsRes] = await Promise.all([
          runtimeAppService.getPublishingReadiness(runtime.id).catch(() => null),
          runtimeAppService.getRuntimeApps(runtime.id).catch(() => ({ runtime_id: runtime.id, items: [] })),
          managedAppService.getManagedApps({ page: 1, page_size: 100 }).catch(() => ({ items: [] })),
        ]);

        if (readinessRes) setReadiness(readinessRes);
        setInstallations(appsRes.items);
        setManagedApps(managedAppsRes.items);
      } catch (err: unknown) {
        setErrorMessage(formatApiError(err));
      } finally {
        if (showLoading) setIsLoading(false);
      }
    },
    [runtime]
  );

  useEffect(() => {
    if (!isOpen || !runtime) return;

    let ignore = false;
    Promise.all([
      runtimeAppService.getPublishingReadiness(runtime.id).catch(() => null),
      runtimeAppService.getRuntimeApps(runtime.id).catch(() => ({ runtime_id: runtime.id, items: [] })),
      managedAppService.getManagedApps({ page: 1, page_size: 100 }).catch(() => ({ items: [] })),
    ])
      .then(([readinessRes, appsRes, managedAppsRes]) => {
        if (ignore) return;
        if (readinessRes) setReadiness(readinessRes);
        setInstallations(appsRes.items);
        setManagedApps(managedAppsRes.items);
      })
      .catch((err: unknown) => {
        if (!ignore) setErrorMessage(formatApiError(err));
      })
      .finally(() => {
        if (!ignore) setIsLoading(false);
      });

    // Setup bounded auto-poll every 3s if any app is installing or pending
    pollTimerRef.current = setInterval(() => {
      fetchData(false);
    }, 3000);

    return () => {
      ignore = true;
      if (pollTimerRef.current) {
        clearInterval(pollTimerRef.current);
        pollTimerRef.current = null;
      }
    };
  }, [isOpen, runtime, fetchData]);

  if (!isOpen || !runtime) return null;

  const isRuntimeStopped = runtime.status !== "running";

  const handleInstall = async (appId: number) => {
    if (isRuntimeStopped || operatingAppId !== null) return;
    try {
      setOperatingAppId(appId);
      setErrorMessage(null);
      await runtimeAppService.installApp(runtime.id, appId);
      setActionSuccessMessage("Installation job queued successfully.");
      await fetchData(false);
    } catch (err: unknown) {
      setErrorMessage(formatApiError(err));
    } finally {
      setOperatingAppId(null);
    }
  };

  const handleVerify = async (appId: number) => {
    if (isRuntimeStopped || operatingAppId !== null) return;
    try {
      setOperatingAppId(appId);
      setErrorMessage(null);
      await runtimeAppService.verifyApp(runtime.id, appId);
      setActionSuccessMessage("Verification job queued successfully.");
      await fetchData(false);
    } catch (err: unknown) {
      setErrorMessage(formatApiError(err));
    } finally {
      setOperatingAppId(null);
    }
  };

  const formatDate = (isoString?: string | null) => {
    if (!isoString) return "Never";
    try {
      return new Intl.DateTimeFormat("en-US", {
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
        hour12: false,
      }).format(new Date(isoString));
    } catch {
      return isoString;
    }
  };

  const managedAppsMap = new Map<number, ManagedApp>();
  managedApps.forEach((app) => managedAppsMap.set(app.id, app));

  // Combine known managed apps with runtime installations
  const combinedAppRows = managedApps.map((mApp) => {
    const install = installations.find((i) => i.managed_app_id === mApp.id);
    return {
      app: mApp,
      installation: install,
    };
  });

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-xs overflow-y-auto">
      <div className="relative w-full max-w-4xl bg-white rounded-xl shadow-2xl border border-slate-200 overflow-hidden my-8 max-h-[92vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-200 bg-slate-50/50">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-lg bg-indigo-100 text-indigo-600 flex items-center justify-center font-bold">
              <Package className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-base font-bold text-slate-900 flex items-center gap-2">
                <span>Apps &amp; Publishing Readiness</span>
                <span className="text-xs px-2 py-0.5 rounded-full bg-slate-100 text-slate-700 font-mono">
                  Runtime #{runtime.id}
                </span>
              </h2>
              <p className="text-xs text-slate-500">
                {runtime.name} {device ? `(${device.name})` : ""} &bull;{" "}
                <span className="font-semibold capitalize text-slate-700">
                  {runtime.status}
                </span>
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-1 rounded-md text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        <div className="p-6 space-y-6 overflow-y-auto flex-1">
          {errorMessage && (
            <div className="p-3 bg-rose-50 border border-rose-200 rounded-lg text-xs text-rose-700 flex items-start gap-2">
              <AlertCircle className="w-4 h-4 text-rose-600 shrink-0 mt-0.5" />
              <span>{errorMessage}</span>
            </div>
          )}

          {actionSuccessMessage && (
            <div className="p-3 bg-emerald-50 border border-emerald-200 rounded-lg text-xs text-emerald-800 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                <span>{actionSuccessMessage}</span>
              </div>
              <button
                type="button"
                onClick={() => setActionSuccessMessage(null)}
                className="text-emerald-700 hover:text-emerald-900"
              >
                &times;
              </button>
            </div>
          )}

          {/* Section 1: Publishing Readiness Snapshot */}
          <div className="p-4 rounded-xl border border-slate-200 bg-slate-50/70 space-y-3">
            <div className="flex items-center justify-between">
              <h3 className="text-xs font-bold text-slate-800 uppercase tracking-wider flex items-center gap-1.5">
                <ShieldCheck className="w-4 h-4 text-emerald-600" />
                <span>Publishing Readiness Status</span>
              </h3>
              <button
                type="button"
                onClick={() => fetchData(false)}
                className="text-slate-400 hover:text-slate-600 p-1"
                title="Refresh readiness"
              >
                <RefreshCw className="w-3.5 h-3.5" />
              </button>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              {/* Runtime Ready */}
              <div className="p-3 rounded-lg bg-white border border-slate-200 shadow-2xs space-y-1">
                <span className="text-[11px] text-slate-500 font-medium block">
                  Runtime Lifecycle:
                </span>
                <div className="flex items-center gap-2">
                  {readiness?.runtime_ready ? (
                    <span className="inline-flex items-center gap-1 text-xs font-semibold text-emerald-700">
                      <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
                      <span>Ready (Booted &amp; ADB)</span>
                    </span>
                  ) : (
                    <span className="inline-flex items-center gap-1 text-xs font-semibold text-amber-700">
                      <AlertTriangle className="w-3.5 h-3.5 text-amber-600" />
                      <span>Not Ready ({runtime.status})</span>
                    </span>
                  )}
                </div>
              </div>

              {/* Required Apps Ready */}
              <div className="p-3 rounded-lg bg-white border border-slate-200 shadow-2xs space-y-1">
                <span className="text-[11px] text-slate-500 font-medium block">
                  Required Apps Preparation:
                </span>
                <div className="flex items-center gap-2">
                  {readiness?.required_apps_ready ? (
                    <span className="inline-flex items-center gap-1 text-xs font-semibold text-emerald-700">
                      <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
                      <span>All Required Ready</span>
                    </span>
                  ) : readiness && readiness.failed_count > 0 ? (
                    <span className="inline-flex items-center gap-1 text-xs font-semibold text-rose-700">
                      <AlertCircle className="w-3.5 h-3.5 text-rose-600" />
                      <span>Failed ({readiness.failed_count})</span>
                    </span>
                  ) : readiness && (readiness.pending_count > 0 || readiness.outdated_count > 0) ? (
                    <span className="inline-flex items-center gap-1 text-xs font-semibold text-sky-700">
                      <Clock className="w-3.5 h-3.5 text-sky-600" />
                      <span>Installing / Pending</span>
                    </span>
                  ) : (
                    <span className="inline-flex items-center gap-1 text-xs font-semibold text-slate-600">
                      <span>No Required Apps</span>
                    </span>
                  )}
                </div>
              </div>

              {/* Overall Publishing Ready */}
              <div className="p-3 rounded-lg bg-white border border-slate-200 shadow-2xs space-y-1">
                <span className="text-[11px] text-slate-500 font-medium block">
                  Overall Publishing Ready:
                </span>
                <div className="flex items-center gap-2">
                  {readiness?.publishing_ready ? (
                    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-bold bg-emerald-100 text-emerald-800">
                      <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
                      <span>Ready to Prepare</span>
                    </span>
                  ) : (
                    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold bg-slate-100 text-slate-600">
                      <span>Prerequisites Incomplete</span>
                    </span>
                  )}
                </div>
              </div>
            </div>

            {readiness && (
              <div className="flex items-center gap-4 text-[11px] text-slate-500 font-mono pt-1">
                <span>Required: {readiness.required_count}</span>
                <span>Installed: {readiness.installed_count}</span>
                <span>Pending: {readiness.pending_count}</span>
                <span>Failed: {readiness.failed_count}</span>
                <span>Outdated: {readiness.outdated_count}</span>
              </div>
            )}
          </div>

          {/* Section 2: App Installations List */}
          <div className="space-y-3">
            <h3 className="text-xs font-bold text-slate-800 uppercase tracking-wider flex items-center gap-1.5">
              <Cpu className="w-4 h-4 text-indigo-600" />
              <span>Installed &amp; Required Applications</span>
            </h3>

            {isRuntimeStopped && (
              <div className="p-3 bg-amber-50 border border-amber-200 rounded-lg text-xs text-amber-800 flex items-center gap-2">
                <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0" />
                <span>
                  Runtime is stopped. Actions are disabled until the runtime container is running.
                </span>
              </div>
            )}

            {isLoading ? (
              <div className="py-8 flex flex-col items-center justify-center text-slate-400 gap-2">
                <Loader2 className="w-5 h-5 animate-spin text-slate-500" />
                <span className="text-xs">Loading application status...</span>
              </div>
            ) : combinedAppRows.length === 0 ? (
              <div className="p-8 text-center bg-slate-50 border border-slate-200 rounded-xl text-xs text-slate-500">
                No managed applications configured in system.
              </div>
            ) : (
              <div className="space-y-3">
                {combinedAppRows.map(({ app, installation }) => {
                  const isOperating = operatingAppId === app.id;
                  const status = installation?.status || "pending";

                  const getStatusBadge = () => {
                    switch (status) {
                      case "installed":
                        return (
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
                            <CheckCircle2 className="w-3 h-3 text-emerald-600" />
                            <span>Installed</span>
                          </span>
                        );
                      case "installing":
                        return (
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-semibold bg-sky-50 text-sky-700 border border-sky-200">
                            <Loader2 className="w-3 h-3 animate-spin text-sky-600" />
                            <span>Installing...</span>
                          </span>
                        );
                      case "outdated":
                        return (
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-semibold bg-amber-50 text-amber-700 border border-amber-200">
                            <AlertTriangle className="w-3 h-3 text-amber-600" />
                            <span>Outdated</span>
                          </span>
                        );
                      case "failed":
                        return (
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-semibold bg-rose-50 text-rose-700 border border-rose-200">
                            <AlertCircle className="w-3 h-3 text-rose-600" />
                            <span>Failed</span>
                          </span>
                        );
                      case "removed":
                        return (
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-semibold bg-slate-100 text-slate-600 border border-slate-200">
                            <span>Removed</span>
                          </span>
                        );
                      default:
                        return (
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-semibold bg-slate-100 text-slate-600 border border-slate-200">
                            <span>Pending</span>
                          </span>
                        );
                    }
                  };

                  return (
                    <div
                      key={app.id}
                      className="p-4 rounded-xl border border-slate-200 bg-white hover:border-slate-300 transition-all space-y-3"
                    >
                      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-2 border-b border-slate-100">
                        <div className="flex items-center gap-2 flex-wrap">
                          <span className="font-semibold text-slate-900 text-xs">
                            {app.display_name}
                          </span>
                          <span className="text-[11px] text-slate-400 font-mono">
                            ({app.android_package_name})
                          </span>
                          {getStatusBadge()}
                          {app.install_policy === "required" && (
                            <span className="text-[10px] font-bold px-1.5 py-0.5 rounded-md bg-rose-50 text-rose-700 border border-rose-200">
                              Required
                            </span>
                          )}
                        </div>

                        <div className="flex items-center gap-2">
                          <button
                            type="button"
                            onClick={() => handleInstall(app.id)}
                            disabled={isRuntimeStopped || isOperating}
                            className="inline-flex items-center gap-1 px-2.5 py-1 text-xs font-semibold text-indigo-700 bg-indigo-50 hover:bg-indigo-100 border border-indigo-200 rounded-lg transition-colors disabled:opacity-40"
                          >
                            {isOperating ? (
                              <Loader2 className="w-3 h-3 animate-spin" />
                            ) : (
                              <DownloadCloud className="w-3 h-3 text-indigo-600" />
                            )}
                            <span>Install / Update</span>
                          </button>

                          <button
                            type="button"
                            onClick={() => handleVerify(app.id)}
                            disabled={isRuntimeStopped || isOperating}
                            className="inline-flex items-center gap-1 px-2.5 py-1 text-xs font-semibold text-emerald-700 bg-emerald-50 hover:bg-emerald-100 border border-emerald-200 rounded-lg transition-colors disabled:opacity-40"
                          >
                            {isOperating ? (
                              <Loader2 className="w-3 h-3 animate-spin" />
                            ) : (
                              <CheckCheck className="w-3 h-3 text-emerald-600" />
                            )}
                            <span>Verify</span>
                          </button>
                        </div>
                      </div>

                      {/* Detail row */}
                      <div className="grid grid-cols-1 sm:grid-cols-3 gap-2.5 text-xs">
                        <div>
                          <span className="text-[11px] text-slate-400 block">Desired Version:</span>
                          <span className="font-mono text-slate-700">
                            {installation
                              ? `Version #${installation.desired_managed_app_version_id}`
                              : app.current_version_id
                              ? `Version #${app.current_version_id}`
                              : "No version defined"}
                          </span>
                        </div>

                        <div>
                          <span className="text-[11px] text-slate-400 block">Observed Version:</span>
                          <span className="font-mono text-slate-700">
                            {installation?.observed_managed_app_version_id
                              ? `Version #${installation.observed_managed_app_version_id}`
                              : "Not observed"}
                            {installation?.observed_version_name &&
                              ` (v${installation.observed_version_name})`}
                          </span>
                        </div>

                        <div>
                          <span className="text-[11px] text-slate-400 block">Verified At:</span>
                          <span className="text-slate-600 font-mono">
                            {formatDate(installation?.verified_at)}
                          </span>
                        </div>

                        {installation?.error_message && (
                          <div className="col-span-full p-2.5 bg-rose-50 border border-rose-200 rounded-lg text-rose-700 text-xs">
                            <strong>Latest Error ({installation.error_code || "APP_ERROR"}):</strong>{" "}
                            {getRuntimeAppErrorMessage(
                              installation.error_code,
                              installation.error_message
                            )}
                          </div>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>

        {/* Footer */}
        <div className="px-6 py-3 border-t border-slate-200 bg-slate-50/50 flex justify-end">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 text-xs font-medium text-slate-700 hover:bg-slate-100 rounded-lg transition-colors"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}

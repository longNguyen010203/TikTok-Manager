"use client";

import React, { useState, useEffect, useCallback } from "react";
import {
  X,
  Globe,
  RefreshCw,
  CheckCircle2,
  AlertTriangle,
  AlertCircle,
  Loader2,
  ShieldCheck,
  Check,
  Cpu,
  Smartphone,
  Lock,
  Info,
  Server,
} from "lucide-react";
import { Runtime } from "@/types/runtime";
import { Device } from "@/types/device";
import {
  RuntimeNetworkResponse,
  RuntimeNetworkStatusResponse,
  NetworkMode,
  CheckStatus,
  RuntimeNetworkApiError,
} from "@/types/runtimeNetwork";
import { runtimeNetworkService } from "@/services/runtimeNetworkService";
import { formatApiError } from "@/types/runtime";

interface RuntimeNetworkModalProps {
  runtime: Runtime | null;
  device?: Device | null;
  isOpen: boolean;
  onClose: () => void;
  onNetworkUpdated?: (network: RuntimeNetworkResponse) => void;
}

export function RuntimeNetworkModal({
  runtime,
  device,
  isOpen,
  onClose,
  onNetworkUpdated,
}: RuntimeNetworkModalProps) {
  // Network configuration state
  const [network, setNetwork] = useState<RuntimeNetworkResponse | null>(null);
  const [networkStatus, setNetworkStatus] =
    useState<RuntimeNetworkStatusResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);

  // Form edit state (desired state)
  const [selectedMode, setSelectedMode] = useState<NetworkMode>("direct");
  const [proxyHost, setProxyHost] = useState("");
  const [proxyPort, setProxyPort] = useState<string>("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [confirmingClearAuth, setConfirmingClearAuth] = useState(false);

  // Operation states
  const [isSaving, setIsSaving] = useState(false);
  const [isApplying, setIsApplying] = useState(false);
  const [isClearing, setIsClearing] = useState(false);

  // Feedback notifications
  const [feedback, setFeedback] = useState<{
    type: "success" | "error" | "warning";
    message: string;
  } | null>(null);

  const runtimeId = runtime?.id;
  const isRuntimeStopped = runtime?.status === "stopped";

  const isWorking = isSaving || isApplying || isClearing || isRefreshing;
  const hasCredentials = Boolean(
    network?.credentials.username_configured ||
      network?.credentials.password_configured
  );

  const handleModalClose = useCallback(() => {
    if (isWorking) return;
    setUsername("");
    setPassword("");
    setConfirmingClearAuth(false);
    onClose();
  }, [isWorking, onClose]);

  // Initial load
  useEffect(() => {
    if (!isOpen || !runtimeId) {
      return;
    }

    let ignore = false;

    Promise.all([
      runtimeNetworkService.getNetwork(runtimeId),
      runtimeNetworkService.getNetworkStatus(runtimeId).catch(() => null),
    ])
      .then(([net, st]) => {
        if (ignore) return;
        setNetwork(net);
        setNetworkStatus(st);
        setSelectedMode((net.mode as NetworkMode) || "direct");
        setProxyHost(net.proxy_host || "");
        setProxyPort(net.proxy_port ? net.proxy_port.toString() : "");
        setUsername("");
        setPassword("");
        setConfirmingClearAuth(false);
        setIsLoading(false);
      })
      .catch((err: unknown) => {
        if (ignore) return;
        setFeedback({
          type: "error",
          message: formatApiError(err),
        });
        setIsLoading(false);
      });

    return () => {
      ignore = true;
    };
  }, [isOpen, runtimeId]);

  // Handle escape key
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && isOpen && !isWorking) {
        handleModalClose();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, isWorking, handleModalClose]);

  if (!isOpen || !runtime) return null;

  const handleRefresh = async () => {
    if (!runtimeId) return;
    setIsRefreshing(true);
    setFeedback(null);
    try {
      const [net, st] = await Promise.all([
        runtimeNetworkService.getNetwork(runtimeId),
        runtimeNetworkService.getNetworkStatus(runtimeId).catch(() => null),
      ]);
      setNetwork(net);
      setNetworkStatus(st);
      setSelectedMode((net.mode as NetworkMode) || "direct");
      setProxyHost(net.proxy_host || "");
      setProxyPort(net.proxy_port ? net.proxy_port.toString() : "");
      setUsername("");
      setPassword("");
      setConfirmingClearAuth(false);
      if (onNetworkUpdated) onNetworkUpdated(net);
    } catch (err: unknown) {
      setFeedback({
        type: "error",
        message: formatApiError(err),
      });
    } finally {
      setIsRefreshing(false);
    }
  };

  const handleSaveDesired = async (
    e?: React.FormEvent,
    clearCredentialsAction = false
  ) => {
    if (e) e.preventDefault();
    if (!runtimeId || !network) return;

    const u = username.trim();
    const p = password;
    const hasU = u.length > 0;
    const hasP = p.length > 0;

    if (!clearCredentialsAction && selectedMode === "http_proxy") {
      // If only one of username or password is entered:
      if ((hasU && !hasP) || (!hasU && hasP)) {
        setFeedback({
          type: "error",
          message: "Enter both username and password, or leave both blank.",
        });
        return;
      }
    }

    setFeedback(null);
    setIsSaving(true);

    try {
      const portNum = proxyPort.trim() ? parseInt(proxyPort.trim(), 10) : undefined;

      let credentialAction: "retain" | "replace" | "clear" | undefined = undefined;
      let sendUsername: string | undefined = undefined;
      let sendPassword: string | undefined = undefined;

      if (clearCredentialsAction) {
        credentialAction = "clear";
      } else if (hasU && hasP) {
        credentialAction = "replace";
        sendUsername = u;
        sendPassword = p;
      }

      const updated = await runtimeNetworkService.updateNetwork(runtimeId, {
        mode: selectedMode,
        proxy_host: selectedMode === "http_proxy" ? proxyHost.trim() : null,
        proxy_port: selectedMode === "http_proxy" ? portNum : null,
        credential_action: credentialAction,
        username: sendUsername,
        password: sendPassword,
        expected_revision: network.desired_revision,
      });

      setNetwork(updated);
      setUsername("");
      setPassword("");
      setConfirmingClearAuth(false);
      setFeedback({
        type: "success",
        message: clearCredentialsAction
          ? `Saved proxy credentials removed (rev ${updated.desired_revision}). Click "Apply Configuration" to activate on the runtime.`
          : `Desired configuration saved (rev ${updated.desired_revision}). Click "Apply Configuration" to activate on the runtime.`,
      });
      if (onNetworkUpdated) onNetworkUpdated(updated);
    } catch (err: unknown) {
      if (err instanceof RuntimeNetworkApiError && err.isRevisionConflict) {
        setFeedback({
          type: "warning",
          message:
            "Revision conflict: The network configuration was updated elsewhere. State refreshed with latest server data.",
        });
        await handleRefresh();
      } else {
        setFeedback({
          type: "error",
          message: formatApiError(err),
        });
      }
    } finally {
      setIsSaving(false);
    }
  };

  const handleApply = async () => {
    if (!runtimeId) return;

    if (isRuntimeStopped) {
      setFeedback({
        type: "warning",
        message:
          "Runtime is currently stopped. Configuration is saved and will be applied when the device is started.",
      });
      return;
    }

    setFeedback(null);
    setIsApplying(true);

    try {
      const applied = await runtimeNetworkService.applyNetwork(runtimeId);
      setNetwork(applied);
      // Refresh status checks
      const latestChecks = await runtimeNetworkService
        .getNetworkStatus(runtimeId)
        .catch(() => null);
      setNetworkStatus(latestChecks);

      setFeedback({
        type: "success",
        message: `Network configuration applied successfully (rev ${applied.applied_revision ?? applied.desired_revision})!`,
      });
      if (onNetworkUpdated) onNetworkUpdated(applied);
    } catch (err: unknown) {
      if (err instanceof RuntimeNetworkApiError && err.isRevisionConflict) {
        setFeedback({
          type: "warning",
          message:
            "Revision conflict: The configuration changed before apply could complete. Refreshed with latest server state.",
        });
        await handleRefresh();
      } else {
        setFeedback({
          type: "error",
          message: formatApiError(err),
        });
      }
    } finally {
      setIsApplying(false);
    }
  };

  const handleClearDirect = async () => {
    if (!runtimeId) return;
    setFeedback(null);
    setIsClearing(true);

    try {
      const cleared = await runtimeNetworkService.clearNetwork(runtimeId);
      setNetwork(cleared);
      setSelectedMode("direct");
      setProxyHost("");
      setProxyPort("");
      setUsername("");
      setPassword("");
      setConfirmingClearAuth(false);

      const latestChecks = await runtimeNetworkService
        .getNetworkStatus(runtimeId)
        .catch(() => null);
      setNetworkStatus(latestChecks);

      setFeedback({
        type: "success",
        message:
          cleared.status === "pending"
            ? "Switched to Direct mode. Will be finalized when device is started."
            : "Switched to Direct mode. Device proxy configuration removed cleanly.",
      });
      if (onNetworkUpdated) onNetworkUpdated(cleared);
    } catch (err: unknown) {
      setFeedback({
        type: "error",
        message: formatApiError(err),
      });
    } finally {
      setIsClearing(false);
    }
  };

  const isPendingApplication =
    network &&
    (network.applied_revision === null ||
      network.desired_revision !== network.applied_revision);

  // Badge color helper for health checks
  const getCheckBadge = (statusValue: CheckStatus) => {
    const raw = (statusValue || "").toLowerCase().trim();
    let label = "Not checked";
    let badgeClass = "bg-slate-100 text-slate-600 border-slate-200";
    let icon = null;

    if (raw === "ok" || raw === "ready") {
      label = "Ready";
      badgeClass = "bg-emerald-50 text-emerald-700 border-emerald-200";
      icon = <CheckCircle2 className="w-3 h-3 text-emerald-600" />;
    } else if (raw === "missing") {
      label = "Missing";
      badgeClass = "bg-amber-50 text-amber-700 border-amber-200";
      icon = <AlertTriangle className="w-3 h-3 text-amber-600" />;
    } else if (raw === "failed" || raw === "error") {
      label = "Failed";
      badgeClass = "bg-rose-50 text-rose-700 border-rose-200";
      icon = <AlertCircle className="w-3 h-3 text-rose-600" />;
    } else if (raw === "inactive" || raw === "stopped" || raw === "disabled") {
      label = "Inactive";
      badgeClass = "bg-slate-100 text-slate-600 border-slate-200";
    } else if (
      raw === "not_applicable" ||
      raw === "unmanaged" ||
      raw === "na" ||
      raw === "n/a"
    ) {
      label = "Not applicable";
      badgeClass = "bg-slate-100 text-slate-500 border-slate-200";
    } else if (raw === "not_run" || raw === "unknown" || !raw) {
      label = "Not checked";
      badgeClass = "bg-slate-100 text-slate-600 border-slate-200";
    } else {
      label = statusValue;
    }

    return (
      <span
        className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[10px] font-semibold border ${badgeClass}`}
      >
        {icon}
        <span>{label}</span>
      </span>
    );
  };

  // Badge color helper for network status
  const getStatusBadge = (st: string) => {
    const val = (st || "").toLowerCase();
    switch (val) {
      case "ready":
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
            <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
            <span className="capitalize">Ready</span>
          </span>
        );
      case "degraded":
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold bg-amber-50 text-amber-700 border border-amber-200">
            <AlertTriangle className="w-3.5 h-3.5 text-amber-600" />
            <span className="capitalize">Degraded</span>
          </span>
        );
      case "pending":
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold bg-sky-50 text-sky-700 border border-sky-200">
            <Loader2 className="w-3.5 h-3.5 animate-spin text-sky-600" />
            <span className="capitalize">Pending Apply</span>
          </span>
        );
      case "failed":
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold bg-rose-50 text-rose-700 border border-rose-200">
            <AlertCircle className="w-3.5 h-3.5 text-rose-600" />
            <span className="capitalize">Failed</span>
          </span>
        );
      case "disabled":
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold bg-slate-100 text-slate-600 border border-slate-200">
            <span className="capitalize">Disabled</span>
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold bg-slate-100 text-slate-700 border border-slate-200">
            <span className="capitalize">{st}</span>
          </span>
        );
    }
  };

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center p-4 bg-black/60 backdrop-blur-xs">
      <div
        className="bg-white rounded-2xl shadow-2xl border border-slate-200 w-full max-w-2xl overflow-hidden animate-in fade-in zoom-in-95 duration-150 flex flex-col max-h-[90vh]"
        role="dialog"
        aria-modal="true"
        aria-labelledby="runtime-network-title"
      >
        {/* Header */}
        <div className="p-5 border-b border-slate-100 flex items-start justify-between bg-gradient-to-r from-cyan-50/70 via-white to-indigo-50/40">
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-xl bg-cyan-100 text-cyan-700 shadow-2xs">
              <Globe className="w-5 h-5" />
            </div>
            <div>
              <h3
                id="runtime-network-title"
                className="text-base font-bold text-slate-900 flex items-center gap-2"
              >
                <span>Runtime Network Configuration</span>
                {network && getStatusBadge(network.status)}
              </h3>
              <p className="text-xs text-slate-500 mt-0.5">
                Configure isolated HTTP proxy settings for this specific Android runtime.
              </p>
            </div>
          </div>
          <div className="flex items-center gap-1.5">
            <button
              type="button"
              onClick={handleRefresh}
              disabled={isWorking}
              className="p-1.5 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition-colors disabled:opacity-40"
              title="Refresh network configuration & health status"
            >
              <RefreshCw className={`w-4 h-4 ${isRefreshing ? "animate-spin" : ""}`} />
            </button>
            <button
              type="button"
              onClick={handleModalClose}
              className="p-1.5 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition-colors"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Modal Body */}
        <div className="p-6 space-y-5 overflow-y-auto flex-1 text-xs">
          {/* Target Runtime & Device Isolation Banner */}
          <div className="p-3.5 rounded-xl bg-slate-50 border border-slate-200 space-y-2">
            <div className="flex items-center justify-between pb-1.5 border-b border-slate-200/60">
              <div className="flex items-center gap-2">
                <Cpu className="w-4 h-4 text-cyan-600" />
                <span className="font-bold text-slate-900">
                  {runtime.name} (Runtime #{runtime.id})
                </span>
                <span className="text-[10px] px-1.5 py-0.5 rounded bg-slate-200/80 text-slate-700 font-semibold uppercase">
                  {runtime.runtime_type}
                </span>
              </div>
              {device && (
                <div className="flex items-center gap-1.5 text-slate-600">
                  <Smartphone className="w-3.5 h-3.5 text-slate-400" />
                  <span className="font-medium">{device.name}</span>
                </div>
              )}
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 text-[11px]">
              <div>
                <span className="text-slate-500">Docker Container: </span>
                <code className="px-1.5 py-0.5 rounded bg-white border border-slate-200 font-mono text-slate-800">
                  {runtime.docker_container_name || "N/A"}
                </code>
              </div>
              <div>
                <span className="text-slate-500">ADB Serial: </span>
                <code className="px-1.5 py-0.5 rounded bg-white border border-slate-200 font-mono text-slate-800">
                  {runtime.adb_serial || "N/A"}
                </code>
              </div>
              <div>
                <span className="text-slate-500">Runtime Status: </span>
                <span
                  className={`font-semibold capitalize ${
                    runtime.status === "running"
                      ? "text-emerald-700"
                      : "text-slate-600"
                  }`}
                >
                  {runtime.status}
                </span>
              </div>
            </div>

            <p className="text-[10px] text-slate-400 italic pt-0.5">
              An isolated proxy connection is created for this device. Network settings apply exclusively to this runtime.
            </p>
          </div>

          {/* Initial Loading Indicator */}
          {isLoading && !network && (
            <div className="py-12 flex flex-col items-center justify-center gap-3 text-slate-400">
              <Loader2 className="w-6 h-6 animate-spin text-cyan-600" />
              <p className="text-xs text-slate-500">
                Loading runtime network configuration...
              </p>
            </div>
          )}

          {/* Feedback Banner */}
          {feedback && (
            <div
              className={`p-3.5 rounded-xl border text-xs flex items-start gap-2.5 animate-in fade-in duration-150 ${
                feedback.type === "success"
                  ? "bg-emerald-50 border-emerald-200 text-emerald-800"
                  : feedback.type === "warning"
                  ? "bg-amber-50 border-amber-200 text-amber-900"
                  : "bg-rose-50 border-rose-200 text-rose-800"
              }`}
            >
              {feedback.type === "success" ? (
                <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0 mt-0.5" />
              ) : feedback.type === "warning" ? (
                <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
              ) : (
                <AlertCircle className="w-4 h-4 text-rose-600 shrink-0 mt-0.5" />
              )}
              <div className="space-y-0.5 flex-1">
                <p className="font-semibold">{feedback.message}</p>
              </div>
              <button
                type="button"
                onClick={() => setFeedback(null)}
                className="font-bold hover:opacity-75"
              >
                &times;
              </button>
            </div>
          )}

          {/* Pending Application Warning */}
          {isPendingApplication && (
            <div className="p-3.5 rounded-xl bg-amber-50/80 border border-amber-200 text-amber-900 flex items-start gap-2.5 shadow-2xs">
              <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
              <div className="space-y-0.5 flex-1">
                <span className="font-bold block">
                  Network configuration is pending application
                </span>
                <p className="text-[11px] text-amber-800 leading-relaxed">
                  Desired configuration is at revision{" "}
                  <strong>rev {network?.desired_revision}</strong>, but applied
                  state is at{" "}
                  <strong>rev {network?.applied_revision ?? "none"}</strong>.
                  Traffic will not use the new configuration until it is applied.
                </p>
              </div>
              {!isRuntimeStopped && (
                <button
                  type="button"
                  onClick={handleApply}
                  disabled={isWorking}
                  className="px-2.5 py-1.5 rounded-lg bg-amber-600 hover:bg-amber-700 text-white font-semibold text-xs transition-colors shrink-0 shadow-2xs"
                >
                  Apply Now
                </button>
              )}
            </div>
          )}

          {/* Runtime Stopped Notice */}
          {isRuntimeStopped && (
            <div className="p-3.5 rounded-xl bg-sky-50 border border-sky-200 text-sky-900 flex items-start gap-2.5">
              <Info className="w-4 h-4 text-sky-600 shrink-0 mt-0.5" />
              <div className="space-y-0.5">
                <span className="font-bold block">Runtime is Stopped</span>
                <p className="text-[11px] text-sky-800 leading-relaxed">
                  You can edit and save the desired network configuration. It will be reconciled and applied automatically when the device starts. Live Apply is disabled while stopped.
                </p>
              </div>
            </div>
          )}

          {/* Mode Selection Cards */}
          <div className="space-y-2">
            <label className="text-xs font-bold text-slate-800 uppercase tracking-wider block">
              Network Mode
            </label>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {/* Direct Mode Option */}
              <div
                onClick={() => setSelectedMode("direct")}
                className={`p-4 rounded-xl border cursor-pointer transition-all ${
                  selectedMode === "direct"
                    ? "bg-cyan-50/50 border-cyan-500 shadow-2xs ring-1 ring-cyan-500"
                    : "bg-white border-slate-200 hover:border-slate-300"
                }`}
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <div
                      className={`w-4 h-4 rounded-full border flex items-center justify-center ${
                        selectedMode === "direct"
                          ? "border-cyan-600 bg-cyan-600"
                          : "border-slate-300"
                      }`}
                    >
                      {selectedMode === "direct" && (
                        <div className="w-1.5 h-1.5 rounded-full bg-white" />
                      )}
                    </div>
                    <span className="font-bold text-slate-900 text-xs">
                      Direct (No Proxy)
                    </span>
                  </div>
                  <span className="text-[10px] px-1.5 py-0.5 rounded font-semibold bg-slate-100 text-slate-600">
                    Default
                  </span>
                </div>
                <p className="text-[11px] text-slate-500 mt-2 leading-relaxed">
                  Direct outbound connection without a proxy. Clears proxy configuration for this device.
                </p>
              </div>

              {/* HTTP Proxy Mode Option */}
              <div
                onClick={() => setSelectedMode("http_proxy")}
                className={`p-4 rounded-xl border cursor-pointer transition-all ${
                  selectedMode === "http_proxy"
                    ? "bg-indigo-50/50 border-indigo-500 shadow-2xs ring-1 ring-indigo-500"
                    : "bg-white border-slate-200 hover:border-slate-300"
                }`}
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <div
                      className={`w-4 h-4 rounded-full border flex items-center justify-center ${
                        selectedMode === "http_proxy"
                          ? "border-indigo-600 bg-indigo-600"
                          : "border-slate-300"
                      }`}
                    >
                      {selectedMode === "http_proxy" && (
                        <div className="w-1.5 h-1.5 rounded-full bg-white" />
                      )}
                    </div>
                    <span className="font-bold text-slate-900 text-xs">
                      HTTP Proxy (Isolated)
                    </span>
                  </div>
                  <span className="text-[10px] px-1.5 py-0.5 rounded font-semibold bg-indigo-100 text-indigo-700">
                    Proxied
                  </span>
                </div>
                <p className="text-[11px] text-slate-500 mt-2 leading-relaxed">
                  Traffic from this device will use the configured HTTP proxy. Network settings are isolated to this device.
                </p>
              </div>
            </div>
          </div>

          {/* HTTP Proxy Form Fields */}
          {selectedMode === "http_proxy" ? (
            <div className="p-4 rounded-xl border border-slate-200 bg-slate-50/60 space-y-4">
              <h4 className="font-bold text-slate-800 text-xs uppercase tracking-wider flex items-center gap-1.5">
                <Globe className="w-3.5 h-3.5 text-indigo-600" />
                <span>Upstream Proxy Configuration</span>
              </h4>

              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                <div className="sm:col-span-2 space-y-1">
                  <label className="text-[11px] font-semibold text-slate-700">
                    Proxy Host <span className="text-rose-500">*</span>
                  </label>
                  <input
                    type="text"
                    value={proxyHost}
                    onChange={(e) => setProxyHost(e.target.value)}
                    placeholder="proxy.example.com or 192.168.1.10"
                    disabled={isWorking}
                    className="w-full px-3 py-2 text-xs border border-slate-200 rounded-lg focus:outline-hidden focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 bg-white"
                  />
                </div>

                <div className="space-y-1">
                  <label className="text-[11px] font-semibold text-slate-700">
                    Proxy Port <span className="text-rose-500">*</span>
                  </label>
                  <input
                    type="number"
                    min="1"
                    max="65535"
                    value={proxyPort}
                    onChange={(e) => setProxyPort(e.target.value)}
                    placeholder="8080"
                    disabled={isWorking}
                    className="w-full px-3 py-2 text-xs border border-slate-200 rounded-lg focus:outline-hidden focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 bg-white"
                  />
                </div>
              </div>

              {/* Proxy Authentication Section */}
              <div className="p-3.5 rounded-lg bg-white border border-slate-200/90 space-y-3">
                <div className="flex items-center justify-between pb-1 border-b border-slate-100">
                  <span className="font-semibold text-slate-800 flex items-center gap-1.5">
                    <Lock className="w-3.5 h-3.5 text-indigo-600" />
                    <span>Proxy Authentication</span>
                  </span>
                  <span className="text-[11px]">
                    {hasCredentials ? (
                      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
                        <CheckCircle2 className="w-3 h-3 text-emerald-600" />
                        <span>Configured</span>
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md font-semibold bg-slate-100 text-slate-500 border border-slate-200">
                        <span>None</span>
                      </span>
                    )}
                  </span>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-[11px]">
                  <div className="space-y-1">
                    <div className="flex items-center justify-between">
                      <label className="font-medium text-slate-700">
                        Username
                      </label>
                      {network?.credentials.username_configured && (
                        <span className="text-[10px] text-emerald-600 font-semibold">
                          Configured
                        </span>
                      )}
                    </div>
                    <input
                      type="text"
                      value={username}
                      onChange={(e) => setUsername(e.target.value)}
                      placeholder={
                        network?.credentials.username_configured
                          ? "Leave blank to keep existing"
                          : "Optional username"
                      }
                      disabled={isWorking}
                      autoComplete="off"
                      className="w-full px-2.5 py-1.5 text-xs border border-slate-200 rounded-md bg-white focus:outline-hidden focus:ring-1 focus:ring-indigo-500"
                    />
                  </div>

                  <div className="space-y-1">
                    <div className="flex items-center justify-between">
                      <label className="font-medium text-slate-700">
                        Password
                      </label>
                      {network?.credentials.password_configured && (
                        <span className="text-[10px] text-emerald-600 font-semibold">
                          Configured
                        </span>
                      )}
                    </div>
                    <input
                      type="password"
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      placeholder={
                        network?.credentials.password_configured
                          ? "Leave blank to keep existing"
                          : "Optional password"
                      }
                      disabled={isWorking}
                      autoComplete="new-password"
                      className="w-full px-2.5 py-1.5 text-xs border border-slate-200 rounded-md bg-white focus:outline-hidden focus:ring-1 focus:ring-indigo-500"
                    />
                  </div>
                </div>

                {hasCredentials && (
                  <div className="pt-1">
                    {!confirmingClearAuth ? (
                      <button
                        type="button"
                        onClick={() => setConfirmingClearAuth(true)}
                        disabled={isWorking}
                        className="text-[11px] text-rose-600 hover:text-rose-700 hover:underline font-medium inline-flex items-center gap-1 transition-colors"
                      >
                        <span>Remove saved authentication</span>
                      </button>
                    ) : (
                      <div className="p-2.5 rounded-lg bg-rose-50 border border-rose-200 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2 animate-in fade-in duration-150">
                        <span className="text-[11px] text-rose-900 font-medium">
                          Remove saved proxy username and password?
                        </span>
                        <div className="flex items-center gap-1.5 shrink-0">
                          <button
                            type="button"
                            onClick={() => setConfirmingClearAuth(false)}
                            disabled={isWorking}
                            className="px-2 py-1 text-[11px] font-medium rounded text-slate-600 bg-white border border-slate-200 hover:bg-slate-50 transition-colors"
                          >
                            Cancel
                          </button>
                          <button
                            type="button"
                            onClick={() => handleSaveDesired(undefined, true)}
                            disabled={isWorking}
                            className="px-2 py-1 text-[11px] font-semibold rounded text-white bg-rose-600 hover:bg-rose-700 transition-colors shadow-2xs"
                          >
                            Confirm Remove
                          </button>
                        </div>
                      </div>
                    )}
                  </div>
                )}

                <div className="p-2 rounded bg-slate-50 border border-slate-200/80 text-[10px] text-slate-500 leading-normal flex items-start gap-1.5">
                  <ShieldCheck className="w-3.5 h-3.5 text-slate-400 shrink-0 mt-0.5" />
                  <span>
                    Credentials are stored securely by TikTok Manager. Existing credentials are never displayed or stored in the browser.
                  </span>
                </div>
              </div>
            </div>
          ) : (
            /* Direct Mode Explanation */
            <div className="p-4 rounded-xl border border-slate-200 bg-slate-50/60 space-y-3">
              <div className="flex items-center justify-between">
                <span className="font-bold text-slate-800 text-xs flex items-center gap-1.5">
                  <Server className="w-3.5 h-3.5 text-cyan-600" />
                  <span>Direct Outbound Mode</span>
                </span>
                {network?.mode === "direct" && network.applied_revision !== null && (
                  <span className="text-emerald-700 font-semibold text-[10px] bg-emerald-50 px-2 py-0.5 rounded border border-emerald-200">
                    Active
                  </span>
                )}
              </div>
              <p className="text-[11px] text-slate-600 leading-relaxed">
                In Direct mode, all Android network traffic routes directly through the host network without an upstream proxy.
              </p>
              <div className="text-[11px] text-slate-500 space-y-1 bg-white p-3 rounded-lg border border-slate-200/80">
                <div className="font-semibold text-slate-700">When Direct mode is applied:</div>
                <ul className="list-disc list-inside space-y-0.5 text-[10px]">
                  <li>Device proxy settings are cleared</li>
                  <li>Proxy connection is inactive</li>
                  <li>The device itself remains running without interruption</li>
                </ul>
              </div>

              {network?.mode === "http_proxy" && (
                <div className="pt-1 flex items-center justify-end">
                  <button
                    type="button"
                    onClick={handleClearDirect}
                    disabled={isWorking}
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold text-rose-700 bg-rose-50 hover:bg-rose-100 border border-rose-200 rounded-lg transition-colors shadow-2xs disabled:opacity-50"
                  >
                    {isClearing ? (
                      <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    ) : (
                      <RefreshCw className="w-3.5 h-3.5" />
                    )}
                    <span>Revert to Direct &amp; Clear Proxy</span>
                  </button>
                </div>
              )}
            </div>
          )}

          {/* Health & Diagnostic Checks Panel */}
          {networkStatus && (
            <div className="p-4 rounded-xl border border-slate-200 bg-white space-y-3 shadow-2xs">
              <div className="flex items-center justify-between pb-1 border-b border-slate-100">
                <span className="font-bold text-slate-800 text-xs flex items-center gap-1.5">
                  <ShieldCheck className="w-3.5 h-3.5 text-indigo-600" />
                  <span>Network Health &amp; Diagnostics</span>
                </span>
                <span className="text-[10px] text-slate-400 font-mono">
                  Applied Rev: {networkStatus.applied_revision ?? "none"}
                </span>
              </div>

              <div className="grid grid-cols-2 sm:grid-cols-3 gap-2.5">
                <div className="p-2.5 rounded-lg bg-slate-50 border border-slate-100 flex items-center justify-between">
                  <span className="text-[11px] text-slate-600">Device Runtime:</span>
                  {getCheckBadge(networkStatus.checks.runtime)}
                </div>
                <div className="p-2.5 rounded-lg bg-slate-50 border border-slate-100 flex items-center justify-between">
                  <span className="text-[11px] text-slate-600">Device Connection:</span>
                  {getCheckBadge(networkStatus.checks.adb)}
                </div>
                <div className="p-2.5 rounded-lg bg-slate-50 border border-slate-100 flex items-center justify-between">
                  <span className="text-[11px] text-slate-600">Android Proxy:</span>
                  {getCheckBadge(networkStatus.checks.android_proxy)}
                </div>
                <div className="p-2.5 rounded-lg bg-slate-50 border border-slate-100 flex items-center justify-between">
                  <span className="text-[11px] text-slate-600">Device Proxy Link:</span>
                  {getCheckBadge(networkStatus.checks.adb_reverse)}
                </div>
                <div className="p-2.5 rounded-lg bg-slate-50 border border-slate-100 flex items-center justify-between">
                  <span className="text-[11px] text-slate-600">Proxy Connection:</span>
                  {getCheckBadge(networkStatus.checks.bridge)}
                </div>
                <div className="p-2.5 rounded-lg bg-slate-50 border border-slate-100 flex items-center justify-between">
                  <span className="text-[11px] text-slate-600">Internet Connectivity:</span>
                  {getCheckBadge(networkStatus.checks.connectivity)}
                </div>
              </div>

              {networkStatus.error_message && (
                <div className="p-2.5 rounded-lg bg-rose-50 border border-rose-200 text-rose-800 text-[11px]">
                  <strong>Diagnostic Details: </strong>
                  {networkStatus.error_message}
                </div>
              )}
            </div>
          )}
        </div>

        {/* Modal Footer */}
        <div className="p-4 border-t border-slate-100 bg-slate-50 flex items-center justify-between gap-3">
          <div className="flex items-center gap-2 text-slate-500 text-[11px] font-mono">
            <span>Desired: rev {network?.desired_revision ?? 0}</span>
            <span>•</span>
            <span>Applied: rev {network?.applied_revision ?? "none"}</span>
          </div>

          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={handleModalClose}
              disabled={isWorking}
              className="px-3.5 py-2 border border-slate-200 rounded-lg text-slate-600 hover:bg-white text-xs font-medium transition-colors disabled:opacity-50"
            >
              Close
            </button>

            {/* Save Desired Button */}
            <button
              type="button"
              onClick={handleSaveDesired}
              disabled={isWorking}
              className="inline-flex items-center gap-1.5 px-3.5 py-2 bg-white border border-slate-300 text-slate-700 hover:bg-slate-50 rounded-lg text-xs font-semibold transition-colors shadow-2xs disabled:opacity-50"
            >
              {isSaving ? (
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
              ) : (
                <Check className="w-3.5 h-3.5" />
              )}
              <span>Save Desired</span>
            </button>

            {/* Apply Button */}
            <button
              type="button"
              onClick={handleApply}
              disabled={isWorking || isRuntimeStopped}
              title={
                isRuntimeStopped
                  ? "Runtime is stopped. Configuration will be automatically applied when the device is started."
                  : "Apply current desired configuration to the live runtime"
              }
              className="inline-flex items-center gap-1.5 px-4 py-2 bg-indigo-600 text-white rounded-lg text-xs font-bold hover:bg-indigo-700 transition-colors shadow-2xs disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isApplying ? (
                <>
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  <span>Applying...</span>
                </>
              ) : (
                <>
                  <Globe className="w-3.5 h-3.5" />
                  <span>Apply Configuration</span>
                </>
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

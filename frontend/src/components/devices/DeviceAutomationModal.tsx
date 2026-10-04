"use client";

import React, { useState, useEffect, useRef, useCallback } from "react";
import {
  X,
  Bot,
  Camera,
  Search,
  Play,
  Square,
  UploadCloud,
  DownloadCloud,
  Image as ImageIcon,
  Loader2,
  CheckCircle2,
  AlertTriangle,
  AlertCircle,
  Clock,
  RotateCcw,
  Ban,
  Download,
  Smartphone,
  Cpu,
} from "lucide-react";
import { Runtime } from "@/types/runtime";
import { Device } from "@/types/device";
import {
  Job,
  JobLog,
  JobStatus,
  AUTOMATION_ACTION_TYPES,
  getJobActionLabel,
  getJobLogEventLabel,
  getAutomationErrorMessage,
  ScreenshotResult,
  PackageStateResult,
  FileTransferResult,
  MediaImportResult,
} from "@/types/job";
import { jobService } from "@/services/jobService";
import { JobStatusBadge } from "@/components/jobs/JobStatusBadge";
import { deviceService } from "@/services/deviceService";

interface DeviceAutomationModalProps {
  runtime: Runtime | null;
  device?: Device | null;
  isOpen: boolean;
  onClose: () => void;
  onJobCreated?: (job: Job) => void;
}

type AutomationAction =
  | "device.screenshot"
  | "device.package_state"
  | "device.launch_app"
  | "device.stop_app"
  | "device.push_file"
  | "device.pull_file"
  | "device.import_media";

const PACKAGE_NAME_REGEX = /^[a-zA-Z0-9_]+(\.[a-zA-Z0-9_]+)+$/;
const COMMON_PACKAGES = [
  "com.android.settings",
  "com.android.chrome",
  "com.android.calculator2",
];

function formatBytes(bytes: number | null | undefined): string {
  if (bytes === null || bytes === undefined || bytes === 0) return "0 B";
  const k = 1024;
  const sizes = ["B", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`;
}

function formatTimestamp(value: string | null | undefined): string {
  if (!value) return "—";
  try {
    const d = new Date(value);
    if (isNaN(d.getTime())) return value;
    return d.toLocaleTimeString([], {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });
  } catch {
    return value;
  }
}

export function DeviceAutomationModal({
  runtime,
  device,
  isOpen,
  onClose,
  onJobCreated,
}: DeviceAutomationModalProps) {
  // Action selection
  const [selectedAction, setSelectedAction] =
    useState<AutomationAction>("device.screenshot");

  // Form states
  const [packageName, setPackageName] = useState("com.android.settings");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [pullFilename, setPullFilename] = useState("");
  const [packageError, setPackageError] = useState<string | null>(null);

  // Screen session state
  const [isScreenOpen, setIsScreenOpen] = useState(false);
  const [screenWarning, setScreenWarning] = useState<string | null>(null);

  // Active Job execution & monitoring
  const [activeJob, setActiveJob] = useState<Job | null>(null);
  const [jobLogs, setJobLogs] = useState<JobLog[]>([]);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isCancelling, setIsCancelling] = useState(false);
  const [isRetrying, setIsRetrying] = useState(false);
  const [feedback, setFeedback] = useState<{
    type: "success" | "error" | "warning";
    message: string;
  } | null>(null);

  const pollingRef = useRef<NodeJS.Timeout | null>(null);
  const runtimeId = runtime?.id;
  const isRuntimeStopped = runtime?.status === "stopped";

  // Check screen session status on modal open
  useEffect(() => {
    if (!isOpen || !device?.id) return;

    let ignore = false;
    deviceService
      .getDeviceScreenStatus(device.id)
      .then((status) => {
        if (ignore) return;
        if (status.status === "open") {
          setIsScreenOpen(true);
          setScreenWarning(
            "Device screen is currently open. Close screen before running automation to avoid conflict."
          );
        } else {
          setIsScreenOpen(false);
          setScreenWarning(null);
        }
      })
      .catch(() => {
        // Non-blocking
      });

    return () => {
      ignore = true;
    };
  }, [isOpen, device?.id]);

  // Clean polling timer
  const stopPolling = useCallback(() => {
    if (pollingRef.current) {
      clearInterval(pollingRef.current);
      pollingRef.current = null;
    }
  }, []);

  // Poll active Job
  const pollJobState = useCallback(
    async (jobId: number) => {
      try {
        const [updatedJob, logs] = await Promise.all([
          jobService.getJob(jobId),
          jobService.getJobLogs(jobId).catch(() => []),
        ]);
        setActiveJob(updatedJob);
        setJobLogs(logs);

        const terminalStatuses: JobStatus[] = [
          "succeeded",
          "failed",
          "cancelled",
        ];
        if (terminalStatuses.includes(updatedJob.status)) {
          stopPolling();
          if (updatedJob.status === "succeeded") {
            setFeedback({
              type: "success",
              message: `${getJobActionLabel(updatedJob.job_type)} completed successfully!`,
            });
          } else if (updatedJob.status === "failed") {
            const err = getAutomationErrorMessage(
              updatedJob.error_code,
              updatedJob.error_message
            );
            setFeedback({
              type: "error",
              message: err,
            });
          } else if (updatedJob.status === "cancelled") {
            setFeedback({
              type: "warning",
              message: "Job was cancelled.",
            });
          }
        }
      } catch {
        // Handled on subsequent polls
      }
    },
    [stopPolling]
  );

  // Start polling when an active job is present
  useEffect(() => {
    if (!activeJob) {
      stopPolling();
      return;
    }

    const terminalStatuses: JobStatus[] = [
      "succeeded",
      "failed",
      "cancelled",
    ];
    if (terminalStatuses.includes(activeJob.status)) {
      stopPolling();
      return;
    }

    stopPolling();
    const targetJobId = activeJob.id;
    pollingRef.current = setInterval(() => {
      pollJobState(targetJobId);
    }, 1500);

    return () => stopPolling();
  }, [activeJob, pollJobState, stopPolling]);

  // Cleanup on modal close or unmount
  const handleModalClose = useCallback(() => {
    stopPolling();
    setActiveJob(null);
    setJobLogs([]);
    setFeedback(null);
    setSelectedFile(null);
    setPullFilename("");
    setPackageError(null);
    setIsScreenOpen(false);
    setScreenWarning(null);
    onClose();
  }, [stopPolling, onClose]);

  // Keyboard escape
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && isOpen && !isSubmitting) {
        handleModalClose();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, isSubmitting, handleModalClose]);

  if (!isOpen || !runtime) return null;

  // Validate package name
  const validatePackage = (val: string): boolean => {
    const trimmed = val.trim();
    if (!trimmed) {
      setPackageError("Package name is required.");
      return false;
    }
    if (!PACKAGE_NAME_REGEX.test(trimmed)) {
      setPackageError("Invalid package name (e.g. com.android.settings).");
      return false;
    }
    setPackageError(null);
    return true;
  };

  // Submit action
  const handleRunAction = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!runtimeId) return;

    if (isScreenOpen) {
      setFeedback({
        type: "error",
        message: "Close the device screen before running automation.",
      });
      return;
    }

    setFeedback(null);
    setIsSubmitting(true);

    try {
      let payload: Record<string, unknown> | null = null;

      // 1. Package Actions
      if (
        selectedAction === "device.package_state" ||
        selectedAction === "device.launch_app" ||
        selectedAction === "device.stop_app"
      ) {
        if (!validatePackage(packageName)) {
          setIsSubmitting(false);
          return;
        }
        payload = { package_name: packageName.trim() };
      }

      // 2. Push File Action
      else if (selectedAction === "device.push_file") {
        if (!selectedFile) {
          setFeedback({
            type: "error",
            message: "Please choose a file to push to the device.",
          });
          setIsSubmitting(false);
          return;
        }
        // Upload artifact first
        const artifact = await jobService.uploadArtifact(selectedFile);
        payload = {
          artifact_id: artifact.id,
          filename: selectedFile.name,
        };
      }

      // 3. Pull File Action
      else if (selectedAction === "device.pull_file") {
        const raw = pullFilename.trim();
        if (!raw) {
          setFeedback({
            type: "error",
            message: "Enter the file name to pull.",
          });
          setIsSubmitting(false);
          return;
        }
        // Safety: reject directory traversal or absolute root paths
        if (raw.includes("..") || raw.startsWith("/data") || raw.startsWith("/proc")) {
          setFeedback({
            type: "error",
            message: "Only files relative to the TikTok Manager folder can be pulled.",
          });
          setIsSubmitting(false);
          return;
        }
        // Strip leading manager folder if user typed it
        const cleanName = raw.replace(/^\/?(sdcard\/Download\/TikTokManager\/)?/, "");
        payload = {
          remote_path: `/sdcard/Download/TikTokManager/${cleanName}`,
        };
      }

      // 4. Import Media Action
      else if (selectedAction === "device.import_media") {
        if (!selectedFile) {
          setFeedback({
            type: "error",
            message: "Please choose an image or video to import.",
          });
          setIsSubmitting(false);
          return;
        }
        const artifact = await jobService.uploadArtifact(selectedFile);
        payload = {
          artifact_id: artifact.id,
          filename: selectedFile.name,
        };
      }

      // 5. Screenshot
      else if (selectedAction === "device.screenshot") {
        payload = {};
      }

      // Create Job
      const job = await jobService.createJob({
        job_type: selectedAction,
        runtime_id: runtimeId,
        payload,
      });

      setActiveJob(job);
      setJobLogs([]);
      if (onJobCreated) onJobCreated(job);

      // Start initial poll
      pollJobState(job.id);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to create automation job.";
      setFeedback({
        type: "error",
        message: msg,
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  // Cancel action
  const handleCancelJob = async () => {
    if (!activeJob) return;
    setIsCancelling(true);
    try {
      const cancelled = await jobService.cancelJob(activeJob.id);
      setActiveJob(cancelled);
      setFeedback({
        type: "warning",
        message: "Cancellation requested.",
      });
      pollJobState(cancelled.id);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to cancel job.";
      setFeedback({
        type: "error",
        message: msg,
      });
    } finally {
      setIsCancelling(false);
    }
  };

  // Retry action
  const handleRetryJob = async () => {
    if (!activeJob) return;
    setIsRetrying(true);
    setFeedback(null);
    try {
      const retried = await jobService.retryJob(activeJob.id);
      setActiveJob(retried);
      setFeedback({
        type: "success",
        message: "Job queued for retry.",
      });
      pollJobState(retried.id);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to retry job.";
      setFeedback({
        type: "error",
        message: msg,
      });
    } finally {
      setIsRetrying(false);
    }
  };

  // Reset to form
  const handleNewAction = () => {
    stopPolling();
    setActiveJob(null);
    setJobLogs([]);
    setFeedback(null);
    setSelectedFile(null);
    setPullFilename("");
  };

  const isTerminal =
    activeJob &&
    (activeJob.status === "succeeded" ||
      activeJob.status === "failed" ||
      activeJob.status === "cancelled");

  const canCancel =
    activeJob &&
    (activeJob.status === "pending" ||
      activeJob.status === "running" ||
      activeJob.status === "retrying");

  const canRetry =
    activeJob?.status === "failed" &&
    activeJob.attempt_count < activeJob.max_attempts;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-5 bg-black/60 backdrop-blur-xs">
      <div
        className="bg-white rounded-2xl shadow-2xl border border-slate-200 w-full max-w-3xl overflow-hidden animate-in fade-in zoom-in-95 duration-150 flex flex-col max-h-[92vh]"
        role="dialog"
        aria-modal="true"
        aria-labelledby="automation-modal-title"
      >
        {/* Header */}
        <div className="p-5 border-b border-slate-100 flex items-start justify-between bg-gradient-to-r from-purple-50/70 via-white to-indigo-50/40">
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-xl bg-purple-100 text-purple-700 shadow-2xs">
              <Bot className="w-5 h-5" />
            </div>
            <div>
              <h3
                id="automation-modal-title"
                className="text-base font-bold text-slate-900 flex items-center gap-2"
              >
                <span>Device Automation</span>
                {activeJob && <JobStatusBadge status={activeJob.status} />}
              </h3>
              <p className="text-xs text-slate-500 mt-0.5">
                Execute safe automation primitives against this Android runtime.
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={handleModalClose}
            className="p-1.5 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Modal Body */}
        <div className="p-6 space-y-5 overflow-y-auto flex-1 text-xs">
          {/* Target Runtime & Device Information */}
          <div className="p-3.5 rounded-xl bg-slate-50 border border-slate-200 space-y-2">
            <div className="flex items-center justify-between pb-1.5 border-b border-slate-200/60">
              <div className="flex items-center gap-2">
                <Cpu className="w-4 h-4 text-purple-600" />
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
                <span className="text-slate-500">Container: </span>
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
                <span className="text-slate-500">Runtime State: </span>
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
          </div>

          {/* Runtime Stopped Warning */}
          {isRuntimeStopped && (
            <div className="p-3.5 rounded-xl bg-amber-50 border border-amber-200 text-amber-900 flex items-start gap-2.5">
              <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
              <div className="space-y-0.5">
                <span className="font-bold block">This device is stopped</span>
                <p className="text-[11px] text-amber-800 leading-relaxed">
                  Automation will not start the device automatically. You must start the device from the Device page before jobs can execute.
                </p>
              </div>
            </div>
          )}

          {/* Screen Open Conflict Warning */}
          {screenWarning && (
            <div className="p-3.5 rounded-xl bg-rose-50 border border-rose-200 text-rose-900 flex items-start gap-2.5">
              <AlertCircle className="w-4 h-4 text-rose-600 shrink-0 mt-0.5" />
              <div className="space-y-0.5">
                <span className="font-bold block">Active Screen Session Detected</span>
                <p className="text-[11px] text-rose-800 leading-relaxed">
                  {screenWarning}
                </p>
              </div>
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

          {/* --- ACTIVE JOB MONITORING VIEW --- */}
          {activeJob ? (
            <div className="space-y-4 animate-in fade-in duration-200">
              {/* Job Header Card */}
              <div className="p-4 rounded-xl border border-slate-200 bg-slate-50/80 space-y-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="font-bold text-slate-900 text-sm">
                      {getJobActionLabel(activeJob.job_type)}
                    </span>
                    <JobStatusBadge status={activeJob.status} />
                  </div>
                  <span className="font-mono text-[11px] text-slate-500">
                    Job #{activeJob.id}
                  </span>
                </div>

                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-[11px]">
                  <div>
                    <span className="text-slate-400 block text-[10px] uppercase">
                      Attempts
                    </span>
                    <span className="font-semibold text-slate-800">
                      {activeJob.attempt_count} of {activeJob.max_attempts}
                    </span>
                  </div>
                  <div>
                    <span className="text-slate-400 block text-[10px] uppercase">
                      Created
                    </span>
                    <span className="font-medium text-slate-700">
                      {formatTimestamp(activeJob.created_at)}
                    </span>
                  </div>
                  <div>
                    <span className="text-slate-400 block text-[10px] uppercase">
                      Started
                    </span>
                    <span className="font-medium text-slate-700">
                      {formatTimestamp(activeJob.started_at)}
                    </span>
                  </div>
                  <div>
                    <span className="text-slate-400 block text-[10px] uppercase">
                      Completed
                    </span>
                    <span className="font-medium text-slate-700">
                      {formatTimestamp(activeJob.completed_at)}
                    </span>
                  </div>
                </div>

                {/* Retry info when retrying */}
                {activeJob.status === "retrying" && (
                  <div className="p-2.5 rounded-lg bg-indigo-50 border border-indigo-200 text-indigo-900 text-[11px] flex items-center gap-2">
                    <RotateCcw className="w-3.5 h-3.5 text-indigo-600 animate-spin" />
                    <span>
                      Retrying — attempt {activeJob.attempt_count + 1} of{" "}
                      {activeJob.max_attempts} scheduled.
                    </span>
                  </div>
                )}

                {/* Cancelling info */}
                {activeJob.status === "cancelling" && (
                  <div className="p-2.5 rounded-lg bg-purple-50 border border-purple-200 text-purple-900 text-[11px] flex items-center gap-2">
                    <Loader2 className="w-3.5 h-3.5 text-purple-600 animate-spin" />
                    <span>
                      Cancellation requested. Waiting for active operation to safely terminate...
                    </span>
                  </div>
                )}
              </div>

              {/* Execution Result Panel (when Succeeded) */}
              {activeJob.status === "succeeded" && Boolean(activeJob.result) && (
                <div className="p-4 rounded-xl border border-emerald-200 bg-emerald-50/40 space-y-3">
                  <div className="flex items-center gap-2 text-emerald-800 font-bold text-xs uppercase tracking-wide">
                    <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                    <span>Action Result</span>
                  </div>

                  {/* Screenshot Result */}
                  {activeJob.job_type === "device.screenshot" &&
                    (() => {
                      const res = activeJob.result as ScreenshotResult;
                      const downloadUrl = jobService.getArtifactDownloadUrl(
                        activeJob.id,
                        res.artifact_id
                      );
                      return (
                        <div className="space-y-3">
                          <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2 text-[11px] text-slate-600">
                            <div className="flex items-center gap-3">
                              <span>
                                Dimensions: <strong>{res.width} &times; {res.height} px</strong>
                              </span>
                              <span>•</span>
                              <span>
                                Size: <strong>{formatBytes(res.size_bytes)}</strong>
                              </span>
                            </div>
                            <a
                              href={downloadUrl}
                              download={res.filename}
                              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-white border border-slate-300 text-slate-700 hover:bg-slate-50 font-semibold text-xs shadow-2xs transition-colors"
                            >
                              <Download className="w-3.5 h-3.5" />
                              <span>Download Screenshot</span>
                            </a>
                          </div>

                          {/* Screenshot Image Preview */}
                          <div className="rounded-lg overflow-hidden border border-slate-200 bg-slate-900 flex justify-center p-2 max-h-72">
                            {/* eslint-disable-next-line @next/next/no-img-element */}
                            <img
                              src={downloadUrl}
                              alt="Captured device screenshot"
                              className="max-h-64 object-contain rounded"
                            />
                          </div>
                        </div>
                      );
                    })()}

                  {/* Package State Result */}
                  {(activeJob.job_type === "device.package_state" ||
                    activeJob.job_type === "device.launch_app" ||
                    activeJob.job_type === "device.stop_app") &&
                    (() => {
                      const res = activeJob.result as PackageStateResult;
                      return (
                        <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 text-[11px]">
                          <div className="p-2.5 rounded-lg bg-white border border-slate-200">
                            <span className="text-slate-400 block text-[10px]">Package</span>
                            <span className="font-semibold text-slate-800 break-all">
                              {res.package_name}
                            </span>
                          </div>
                          <div className="p-2.5 rounded-lg bg-white border border-slate-200">
                            <span className="text-slate-400 block text-[10px]">Installed</span>
                            <span
                              className={`font-semibold ${
                                res.installed ? "text-emerald-700" : "text-rose-700"
                              }`}
                            >
                              {res.installed ? "Installed" : "Not Installed"}
                            </span>
                          </div>
                          <div className="p-2.5 rounded-lg bg-white border border-slate-200">
                            <span className="text-slate-400 block text-[10px]">State</span>
                            <span
                              className={`font-semibold ${
                                res.running ? "text-emerald-700" : "text-slate-600"
                              }`}
                            >
                              {res.running ? `Running (PID ${res.pid})` : "Stopped"}
                            </span>
                          </div>
                        </div>
                      );
                    })()}

                  {/* Push File Result */}
                  {activeJob.job_type === "device.push_file" &&
                    (() => {
                      const res = activeJob.result as FileTransferResult;
                      return (
                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-[11px]">
                          <div className="p-2.5 rounded-lg bg-white border border-slate-200">
                            <span className="text-slate-400 block text-[10px]">Remote Path</span>
                            <code className="font-mono text-slate-800 break-all">
                              {res.remote_path}
                            </code>
                          </div>
                          <div className="p-2.5 rounded-lg bg-white border border-slate-200">
                            <span className="text-slate-400 block text-[10px]">File &amp; Size</span>
                            <span className="font-semibold text-slate-800">
                              {res.filename} ({formatBytes(res.size_bytes)})
                            </span>
                          </div>
                        </div>
                      );
                    })()}

                  {/* Pull File Result */}
                  {activeJob.job_type === "device.pull_file" &&
                    (() => {
                      const res = activeJob.result as ScreenshotResult;
                      const downloadUrl = jobService.getArtifactDownloadUrl(
                        activeJob.id,
                        res.artifact_id
                      );
                      return (
                        <div className="flex items-center justify-between p-3 rounded-lg bg-white border border-slate-200">
                          <div>
                            <span className="font-bold text-slate-800 block">
                              {res.filename}
                            </span>
                            <span className="text-[10px] text-slate-500">
                              Size: {formatBytes(res.size_bytes)} • MIME: {res.mime_type}
                            </span>
                          </div>
                          <a
                            href={downloadUrl}
                            download={res.filename}
                            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white font-semibold text-xs shadow-2xs transition-colors"
                          >
                            <Download className="w-3.5 h-3.5" />
                            <span>Download File</span>
                          </a>
                        </div>
                      );
                    })()}

                  {/* Import Media Result */}
                  {activeJob.job_type === "device.import_media" &&
                    (() => {
                      const res = activeJob.result as MediaImportResult;
                      return (
                        <div className="space-y-2 text-[11px]">
                          <div className="p-2.5 rounded-lg bg-white border border-slate-200 flex items-center justify-between">
                            <div>
                              <span className="text-slate-400 block text-[10px]">Import Status</span>
                              <span className="font-semibold text-emerald-700">
                                {res.media_imported ? "Registered in Android Gallery" : "Transferred"}
                              </span>
                            </div>
                            <span className="text-slate-500 font-medium">
                              {res.filename} ({formatBytes(res.size_bytes)})
                            </span>
                          </div>
                          {res.media_uri && (
                            <div className="p-2.5 rounded-lg bg-white border border-slate-200">
                              <span className="text-slate-400 block text-[10px]">Media Content URI</span>
                              <code className="font-mono text-slate-800 text-[10px] break-all">
                                {res.media_uri}
                              </code>
                            </div>
                          )}
                        </div>
                      );
                    })()}
                </div>
              )}

              {/* Structured JobLog Timeline */}
              <div className="p-4 rounded-xl border border-slate-200 bg-white space-y-3">
                <div className="flex items-center justify-between pb-1 border-b border-slate-100">
                  <span className="font-bold text-slate-800 text-xs flex items-center gap-1.5">
                    <Clock className="w-3.5 h-3.5 text-purple-600" />
                    <span>Execution Timeline &amp; Logs</span>
                  </span>
                  <span className="text-[10px] text-slate-400 font-mono">
                    {jobLogs.length} events
                  </span>
                </div>

                {jobLogs.length === 0 ? (
                  <div className="py-4 text-center text-slate-400 text-xs italic">
                    Waiting for worker to claim and log events...
                  </div>
                ) : (
                  <div className="relative pl-6 space-y-3 before:absolute before:left-2.5 before:top-2 before:bottom-2 before:w-0.5 before:bg-slate-200">
                    {jobLogs.map((log) => {
                      const isError = log.level.toLowerCase() === "error";
                      const isSuccess = log.event_type === "action_completed" || log.event_type === "succeeded";
                      return (
                        <div key={log.id} className="relative text-[11px] space-y-0.5">
                          {/* Dot marker */}
                          <div
                            className={`absolute -left-6 top-1 w-2.5 h-2.5 rounded-full ring-2 ring-white ${
                              isError
                                ? "bg-rose-500"
                                : isSuccess
                                ? "bg-emerald-500"
                                : "bg-purple-500"
                            }`}
                          />
                          <div className="flex items-center justify-between">
                            <span className="font-semibold text-slate-800">
                              {getJobLogEventLabel(log.event_type)}
                            </span>
                            <span className="text-[10px] text-slate-400 font-mono">
                              {formatTimestamp(log.created_at)}
                            </span>
                          </div>
                          <p className="text-slate-600 leading-relaxed">{log.message}</p>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>

              {/* Bottom Actions inside Monitor */}
              <div className="flex items-center justify-between pt-2">
                <div>
                  {isTerminal && (
                    <button
                      type="button"
                      onClick={handleNewAction}
                      className="px-3.5 py-2 rounded-lg bg-slate-100 hover:bg-slate-200 text-slate-700 font-semibold text-xs transition-colors"
                    >
                      Run Another Action
                    </button>
                  )}
                </div>

                <div className="flex items-center gap-2">
                  {canCancel && (
                    <button
                      type="button"
                      onClick={handleCancelJob}
                      disabled={isCancelling}
                      className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-lg bg-rose-50 border border-rose-200 text-rose-700 hover:bg-rose-100 font-semibold text-xs transition-colors disabled:opacity-50"
                    >
                      {isCancelling ? (
                        <Loader2 className="w-3.5 h-3.5 animate-spin" />
                      ) : (
                        <Ban className="w-3.5 h-3.5" />
                      )}
                      <span>
                        {activeJob.status === "running"
                          ? "Request Cancellation"
                          : "Cancel Job"}
                      </span>
                    </button>
                  )}

                  {canRetry && (
                    <button
                      type="button"
                      onClick={handleRetryJob}
                      disabled={isRetrying}
                      className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-lg bg-indigo-50 border border-indigo-200 text-indigo-700 hover:bg-indigo-100 font-semibold text-xs transition-colors disabled:opacity-50"
                    >
                      {isRetrying ? (
                        <Loader2 className="w-3.5 h-3.5 animate-spin" />
                      ) : (
                        <RotateCcw className="w-3.5 h-3.5" />
                      )}
                      <span>Retry Job</span>
                    </button>
                  )}
                </div>
              </div>
            </div>
          ) : (
            /* --- ACTION SELECTION & FORM VIEW --- */
            <form onSubmit={handleRunAction} className="space-y-5">
              {/* Action Selection Grid */}
              <div className="space-y-2">
                <label className="text-xs font-bold text-slate-800 uppercase tracking-wider block">
                  Select Automation Action
                </label>
                <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-2.5">
                  {AUTOMATION_ACTION_TYPES.map((act) => {
                    const isSelected = selectedAction === act.type;
                    const Icon =
                      act.type === "device.screenshot"
                        ? Camera
                        : act.type === "device.package_state"
                        ? Search
                        : act.type === "device.launch_app"
                        ? Play
                        : act.type === "device.stop_app"
                        ? Square
                        : act.type === "device.push_file"
                        ? UploadCloud
                        : act.type === "device.pull_file"
                        ? DownloadCloud
                        : ImageIcon;

                    return (
                      <div
                        key={act.type}
                        onClick={() => setSelectedAction(act.type as AutomationAction)}
                        className={`p-3 rounded-xl border cursor-pointer transition-all flex flex-col justify-between ${
                          isSelected
                            ? "bg-purple-50/50 border-purple-500 shadow-2xs ring-1 ring-purple-500"
                            : "bg-white border-slate-200 hover:border-slate-300"
                        }`}
                      >
                        <div className="flex items-center gap-2">
                          <div
                            className={`p-1.5 rounded-lg ${
                              isSelected
                                ? "bg-purple-600 text-white"
                                : "bg-slate-100 text-slate-600"
                            }`}
                          >
                            <Icon className="w-4 h-4" />
                          </div>
                          <span className="font-bold text-slate-900 text-xs">
                            {act.label}
                          </span>
                        </div>
                        <p className="text-[10px] text-slate-500 mt-2 leading-relaxed">
                          {act.description}
                        </p>
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* Dynamic Action Parameters Card */}
              <div className="p-4 rounded-xl border border-slate-200 bg-slate-50/60 space-y-4">
                {/* 1. Screenshot Action */}
                {selectedAction === "device.screenshot" && (
                  <div className="space-y-2">
                    <h4 className="font-bold text-slate-800 text-xs uppercase tracking-wider flex items-center gap-1.5">
                      <Camera className="w-3.5 h-3.5 text-purple-600" />
                      <span>Capture Screenshot</span>
                    </h4>
                    <p className="text-[11px] text-slate-600 leading-relaxed">
                      Captures the live display buffer of the device. The screenshot will be saved as an image artifact and rendered with dimension metadata.
                    </p>
                  </div>
                )}

                {/* 2. Package Actions (Check / Launch / Stop) */}
                {(selectedAction === "device.package_state" ||
                  selectedAction === "device.launch_app" ||
                  selectedAction === "device.stop_app") && (
                  <div className="space-y-3">
                    <h4 className="font-bold text-slate-800 text-xs uppercase tracking-wider flex items-center gap-1.5">
                      <Search className="w-3.5 h-3.5 text-purple-600" />
                      <span>Android Package Configuration</span>
                    </h4>

                    <div className="space-y-1">
                      <label className="text-[11px] font-semibold text-slate-700">
                        Package Name <span className="text-rose-500">*</span>
                      </label>
                      <input
                        type="text"
                        value={packageName}
                        onChange={(e) => {
                          setPackageName(e.target.value);
                          if (packageError) validatePackage(e.target.value);
                        }}
                        placeholder="com.android.settings"
                        disabled={isSubmitting}
                        className="w-full px-3 py-2 text-xs border border-slate-200 rounded-lg focus:outline-hidden focus:ring-2 focus:ring-purple-500/20 focus:border-purple-500 bg-white"
                      />
                      {packageError && (
                        <p className="text-[10px] text-rose-600 font-medium">
                          {packageError}
                        </p>
                      )}
                    </div>

                    <div className="flex items-center gap-1.5 text-[10px] text-slate-500 pt-1">
                      <span>Quick presets:</span>
                      {COMMON_PACKAGES.map((pkg) => (
                        <button
                          key={pkg}
                          type="button"
                          onClick={() => {
                            setPackageName(pkg);
                            setPackageError(null);
                          }}
                          className="px-2 py-0.5 rounded bg-white border border-slate-200 hover:bg-slate-100 font-mono text-[10px] text-slate-700 transition-colors"
                        >
                          {pkg}
                        </button>
                      ))}
                    </div>
                  </div>
                )}

                {/* 3. Push File Action */}
                {selectedAction === "device.push_file" && (
                  <div className="space-y-3">
                    <h4 className="font-bold text-slate-800 text-xs uppercase tracking-wider flex items-center gap-1.5">
                      <UploadCloud className="w-3.5 h-3.5 text-purple-600" />
                      <span>Push File to Device</span>
                    </h4>
                    <p className="text-[11px] text-slate-600 leading-relaxed">
                      Choose a file from your browser to transfer to the device. Files are placed safely into{" "}
                      <code className="font-mono text-purple-700 bg-purple-50 px-1 py-0.5 rounded">
                        /sdcard/Download/TikTokManager/
                      </code>.
                    </p>

                    <div className="space-y-1">
                      <label className="text-[11px] font-semibold text-slate-700">
                        Choose File <span className="text-rose-500">*</span>
                      </label>
                      <input
                        type="file"
                        onChange={(e) => {
                          const f = e.target.files?.[0] || null;
                          setSelectedFile(f);
                        }}
                        disabled={isSubmitting}
                        className="block w-full text-xs text-slate-500 file:mr-3 file:py-2 file:px-3 file:rounded-lg file:border-0 file:text-xs file:font-semibold file:bg-purple-50 file:text-purple-700 hover:file:bg-purple-100 cursor-pointer"
                      />
                      {selectedFile && (
                        <p className="text-[10px] text-slate-500 pt-1">
                          Selected: <strong>{selectedFile.name}</strong> ({formatBytes(selectedFile.size)})
                        </p>
                      )}
                    </div>
                  </div>
                )}

                {/* 4. Pull File Action */}
                {selectedAction === "device.pull_file" && (
                  <div className="space-y-3">
                    <h4 className="font-bold text-slate-800 text-xs uppercase tracking-wider flex items-center gap-1.5">
                      <DownloadCloud className="w-3.5 h-3.5 text-purple-600" />
                      <span>Pull File from Device</span>
                    </h4>
                    <p className="text-[11px] text-slate-600 leading-relaxed">
                      Retrieve a file from the managed device folder. Relative to{" "}
                      <code className="font-mono text-purple-700 bg-purple-50 px-1 py-0.5 rounded">
                        /sdcard/Download/TikTokManager/
                      </code>.
                    </p>

                    <div className="space-y-1">
                      <label className="text-[11px] font-semibold text-slate-700">
                        File Name <span className="text-rose-500">*</span>
                      </label>
                      <input
                        type="text"
                        value={pullFilename}
                        onChange={(e) => setPullFilename(e.target.value)}
                        placeholder="sample.txt or report.json"
                        disabled={isSubmitting}
                        className="w-full px-3 py-2 text-xs border border-slate-200 rounded-lg focus:outline-hidden focus:ring-2 focus:ring-purple-500/20 focus:border-purple-500 bg-white font-mono"
                      />
                      <p className="text-[10px] text-slate-400">
                        Do not enter system paths (like /data or /proc). Files are restricted to the TikTok Manager device folder.
                      </p>
                    </div>
                  </div>
                )}

                {/* 5. Import Media Action */}
                {selectedAction === "device.import_media" && (
                  <div className="space-y-3">
                    <h4 className="font-bold text-slate-800 text-xs uppercase tracking-wider flex items-center gap-1.5">
                      <ImageIcon className="w-3.5 h-3.5 text-purple-600" />
                      <span>Import Media to Android Gallery</span>
                    </h4>
                    <p className="text-[11px] text-slate-600 leading-relaxed">
                      Upload an image or video to the device and register it with the Android MediaStore scanner so it is immediately visible in photo apps.
                    </p>

                    <div className="space-y-1">
                      <label className="text-[11px] font-semibold text-slate-700">
                        Choose Image or Video <span className="text-rose-500">*</span>
                      </label>
                      <input
                        type="file"
                        accept="image/png,image/jpeg,video/mp4"
                        onChange={(e) => {
                          const f = e.target.files?.[0] || null;
                          setSelectedFile(f);
                        }}
                        disabled={isSubmitting}
                        className="block w-full text-xs text-slate-500 file:mr-3 file:py-2 file:px-3 file:rounded-lg file:border-0 file:text-xs file:font-semibold file:bg-purple-50 file:text-purple-700 hover:file:bg-purple-100 cursor-pointer"
                      />
                      {selectedFile && (
                        <p className="text-[10px] text-slate-500 pt-1">
                          Selected: <strong>{selectedFile.name}</strong> ({formatBytes(selectedFile.size)})
                        </p>
                      )}
                    </div>
                  </div>
                )}
              </div>

              {/* Form Submission Buttons */}
              <div className="flex items-center justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={handleModalClose}
                  disabled={isSubmitting}
                  className="px-3.5 py-2 border border-slate-200 rounded-lg text-slate-600 hover:bg-slate-50 text-xs font-medium transition-colors disabled:opacity-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isSubmitting || isScreenOpen}
                  className="inline-flex items-center gap-1.5 px-4 py-2 bg-purple-600 text-white rounded-lg text-xs font-bold hover:bg-purple-700 transition-colors shadow-2xs disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {isSubmitting ? (
                    <>
                      <Loader2 className="w-3.5 h-3.5 animate-spin" />
                      <span>Creating Job...</span>
                    </>
                  ) : (
                    <>
                      <Play className="w-3.5 h-3.5" />
                      <span>Run {getJobActionLabel(selectedAction)}</span>
                    </>
                  )}
                </button>
              </div>
            </form>
          )}
        </div>

        {/* Modal Footer */}
        <div className="p-4 border-t border-slate-100 bg-slate-50 flex items-center justify-between text-slate-500 text-[11px]">
          <span className="font-mono">
            Target: Runtime #{runtime.id} • {runtime.docker_container_name}
          </span>
          <button
            type="button"
            onClick={handleModalClose}
            className="px-3 py-1.5 border border-slate-200 rounded-lg text-slate-600 hover:bg-white text-xs font-medium transition-colors"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}

import { useEffect, useState } from "react";
import {
  AlertCircle,
  AlertTriangle,
  CalendarClock,
  CircleDot,
  Cpu,
  FileJson,
  History,
  OctagonX,
  RefreshCw,
  RotateCcw,
  UserRound,
  X,
} from "lucide-react";
import { jobService } from "@/services/jobService";
import { Account } from "@/types/account";
import { ApiError, Job, JobLog, formatApiError } from "@/types/job";
import { Runtime } from "@/types/runtime";
import { JobStatusBadge } from "./JobStatusBadge";

interface JobDetailModalProps {
  jobId: number;
  accountsMap: Record<number, Account>;
  runtimesMap: Record<number, Runtime>;
  onClose: () => void;
  onQueueRefresh: () => void;
}

function formatDate(value: string | null, emptyLabel = "Not set") {
  if (!value) return emptyLabel;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "long",
  }).format(date);
}

function formatJson(value: unknown) {
  if (value === null || value === undefined) return null;
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
}

function sortLogsChronologically(left: JobLog, right: JobLog) {
  const leftTimestamp = new Date(left.created_at).getTime();
  const rightTimestamp = new Date(right.created_at).getTime();

  if (!Number.isNaN(leftTimestamp) && !Number.isNaN(rightTimestamp)) {
    return leftTimestamp - rightTimestamp || left.id - right.id;
  }

  return left.id - right.id;
}

function DetailItem({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-slate-50/70 p-3">
      <dt className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-slate-400">
        {label}
      </dt>
      <dd className="text-xs font-medium text-slate-800">{value}</dd>
    </div>
  );
}

function JsonPanel({ label, value }: { label: string; value: unknown }) {
  const formatted = formatJson(value);
  return (
    <div className="min-w-0 rounded-xl border border-slate-200 bg-slate-950">
      <div className="flex items-center gap-2 border-b border-slate-800 px-3 py-2 text-[11px] font-semibold uppercase tracking-wider text-slate-400">
        <FileJson className="h-3.5 w-3.5" /> {label}
      </div>
      {formatted ? (
        <pre className="max-h-56 overflow-auto whitespace-pre-wrap break-words p-3 text-[11px] leading-relaxed text-slate-200">
          {formatted}
        </pre>
      ) : (
        <p className="p-3 text-xs italic text-slate-500">No {label.toLowerCase()} recorded.</p>
      )}
    </div>
  );
}

function LoadingBlock() {
  return (
    <div className="animate-pulse space-y-4 p-5 sm:p-6">
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        {Array.from({ length: 8 }).map((_, index) => (
          <div key={index} className="h-16 rounded-lg bg-slate-100" />
        ))}
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        <div className="h-36 rounded-xl bg-slate-100" />
        <div className="h-36 rounded-xl bg-slate-100" />
      </div>
    </div>
  );
}

function retryErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 409) {
      return `Retry rejected: ${formatApiError(error)}`;
    }
    if (error.status === 404) {
      return "This job no longer exists. Close the detail view and refresh the queue.";
    }
    if (error.status === 422) {
      return `The retry request was invalid: ${formatApiError(error)}`;
    }
  }

  return formatApiError(error);
}

function cancelErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 409) {
      return `Cancellation rejected: ${formatApiError(error)}`;
    }
    if (error.status === 404) {
      return "This job no longer exists. Close the detail view and refresh the queue.";
    }
    if (error.status === 422) {
      return `The cancellation request was invalid: ${formatApiError(error)}`;
    }
  }

  return formatApiError(error);
}

export function JobDetailModal({
  jobId,
  accountsMap,
  runtimesMap,
  onClose,
  onQueueRefresh,
}: JobDetailModalProps) {
  const [job, setJob] = useState<Job | null>(null);
  const [logs, setLogs] = useState<JobLog[]>([]);
  const [detailLoading, setDetailLoading] = useState(true);
  const [logsLoading, setLogsLoading] = useState(true);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [logsError, setLogsError] = useState<string | null>(null);
  const [isMissing, setIsMissing] = useState(false);
  const [detailRefresh, setDetailRefresh] = useState(0);
  const [logsRefresh, setLogsRefresh] = useState(0);
  const [retryScheduledAt, setRetryScheduledAt] = useState("");
  const [retryRunning, setRetryRunning] = useState(false);
  const [cancelConfirming, setCancelConfirming] = useState(false);
  const [cancelRunning, setCancelRunning] = useState(false);
  const [actionFeedback, setActionFeedback] = useState<{
    type: "success" | "error";
    message: string;
  } | null>(null);

  useEffect(() => {
    let ignore = false;
    jobService
      .getJob(jobId)
      .then((loadedJob) => {
        if (ignore) return;
        setJob(loadedJob);
        setDetailError(null);
        setIsMissing(false);
      })
      .catch((error: unknown) => {
        if (ignore) return;
        setJob(null);
        setIsMissing(error instanceof ApiError && error.status === 404);
        setDetailError(formatApiError(error));
      })
      .finally(() => {
        if (!ignore) setDetailLoading(false);
      });
    return () => {
      ignore = true;
    };
  }, [jobId, detailRefresh]);

  useEffect(() => {
    let ignore = false;
    jobService
      .getJobLogs(jobId)
      .then((loadedLogs) => {
        if (ignore) return;
        setLogs([...loadedLogs].sort(sortLogsChronologically));
        setLogsError(null);
      })
      .catch((error: unknown) => {
        if (ignore) return;
        setLogs([]);
        setLogsError(formatApiError(error));
      })
      .finally(() => {
        if (!ignore) setLogsLoading(false);
      });
    return () => {
      ignore = true;
    };
  }, [jobId, logsRefresh]);

  useEffect(() => {
    const handleEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handleEscape);
    return () => window.removeEventListener("keydown", handleEscape);
  }, [onClose]);

  async function handleRetry() {
    let scheduledAt: string | undefined;

    if (retryScheduledAt) {
      const parsedScheduledAt = new Date(retryScheduledAt);
      if (Number.isNaN(parsedScheduledAt.getTime())) {
        setActionFeedback({
          type: "error",
          message: "Enter a valid retry date and time.",
        });
        return;
      }
      scheduledAt = parsedScheduledAt.toISOString();
    }

    setRetryRunning(true);
    setActionFeedback(null);

    try {
      const retriedJob = await jobService.retryJob(jobId, scheduledAt);
      setJob(retriedJob);
      setRetryScheduledAt("");
      setActionFeedback({
        type: "success",
        message: scheduledAt ? "Retry scheduled successfully." : "Job queued for retry.",
      });
      setDetailRefresh((value) => value + 1);
      setLogsLoading(true);
      setLogsRefresh((value) => value + 1);
      onQueueRefresh();
    } catch (error) {
      setActionFeedback({ type: "error", message: retryErrorMessage(error) });
    } finally {
      setRetryRunning(false);
    }
  }

  async function handleCancel() {
    setCancelRunning(true);
    setActionFeedback(null);

    try {
      const cancelledJob = await jobService.cancelJob(jobId);
      setJob(cancelledJob);
      setCancelConfirming(false);
      setActionFeedback({ type: "success", message: "Job cancelled successfully." });
      setDetailRefresh((value) => value + 1);
      setLogsLoading(true);
      setLogsRefresh((value) => value + 1);
      onQueueRefresh();
    } catch (error) {
      setCancelConfirming(false);
      setActionFeedback({ type: "error", message: cancelErrorMessage(error) });
    } finally {
      setCancelRunning(false);
    }
  }

  const account = job?.account_id ? accountsMap[job.account_id] : undefined;
  const runtime = job?.runtime_id ? runtimesMap[job.runtime_id] : undefined;
  const canCancel =
    job?.status === "pending" ||
    job?.status === "running" ||
    job?.status === "retrying";

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/65 p-3 backdrop-blur-xs sm:p-6"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <section
        role="dialog"
        aria-modal="true"
        aria-labelledby="job-detail-title"
        className="flex max-h-[94vh] w-full max-w-6xl flex-col overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-2xl"
      >
        <header className="flex items-start justify-between gap-4 border-b border-slate-200 px-5 py-4 sm:px-6">
          <div className="min-w-0">
            <p className="font-mono text-[11px] font-semibold uppercase tracking-wider text-rose-600">
              Job #{jobId}
            </p>
            <h2 id="job-detail-title" className="truncate text-lg font-bold text-slate-900">
              {job?.job_type || "Job details"}
            </h2>
          </div>
          <div className="flex items-center gap-3">
            {job && <JobStatusBadge status={job.status} />}
            <button
              type="button"
              onClick={onClose}
              className="rounded-lg p-1.5 text-slate-400 transition-colors hover:bg-slate-100 hover:text-slate-700"
              aria-label="Close job details"
            >
              <X className="h-5 w-5" />
            </button>
          </div>
        </header>

        <div className="overflow-y-auto">
          {detailLoading ? (
            <LoadingBlock />
          ) : detailError ? (
            <div className="px-5 py-14 text-center sm:px-6">
              <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-rose-50 text-rose-600">
                {isMissing ? <AlertCircle className="h-6 w-6" /> : <AlertTriangle className="h-6 w-6" />}
              </div>
              <h3 className="text-sm font-semibold text-slate-900">
                {isMissing ? "Job no longer exists" : "Unable to load job details"}
              </h3>
              <p className="mx-auto mt-1 max-w-md text-xs text-slate-500">{detailError}</p>
              {!isMissing && (
                <button
                  type="button"
                  onClick={() => {
                    setDetailLoading(true);
                    setDetailRefresh((value) => value + 1);
                  }}
                  className="mt-4 inline-flex items-center gap-1.5 rounded-lg bg-slate-900 px-3 py-1.5 text-xs font-medium text-white"
                >
                  <RefreshCw className="h-3.5 w-3.5" /> Retry details
                </button>
              )}
            </div>
          ) : job ? (
            <div className="space-y-6 p-5 sm:p-6">
              {actionFeedback ? (
                <div
                  className={`rounded-xl border px-4 py-3 text-sm ${
                    actionFeedback.type === "success"
                      ? "border-emerald-200 bg-emerald-50 text-emerald-800"
                      : "border-rose-200 bg-rose-50 text-rose-800"
                  }`}
                  role="status"
                >
                  {actionFeedback.message}
                </div>
              ) : null}

              {job.status === "failed" ? (
                <section className="rounded-xl border border-amber-200 bg-amber-50/60 p-4">
                  <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
                    <div>
                      <h3 className="text-sm font-semibold text-slate-900">Retry job</h3>
                      <p className="mt-1 text-xs text-slate-500">
                        Leave the date empty to make the job eligible immediately.
                      </p>
                    </div>
                    <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
                      <label className="block text-[10px] font-semibold uppercase tracking-wider text-slate-500">
                        Retry at (optional)
                        <input
                          className="mt-2 min-h-10 w-full rounded-lg border border-slate-200 bg-white px-3 text-sm font-normal normal-case tracking-normal text-slate-800 outline-none transition focus:border-amber-400 sm:w-56"
                          disabled={retryRunning}
                          onChange={(event) => setRetryScheduledAt(event.target.value)}
                          type="datetime-local"
                          value={retryScheduledAt}
                        />
                      </label>
                      <button
                        className="inline-flex min-h-10 items-center justify-center gap-2 rounded-lg bg-amber-500 px-4 text-sm font-semibold text-white transition hover:bg-amber-600 disabled:cursor-not-allowed disabled:opacity-60"
                        disabled={retryRunning}
                        onClick={() => void handleRetry()}
                        type="button"
                      >
                        <RotateCcw className={`h-4 w-4 ${retryRunning ? "animate-spin" : ""}`} />
                        {retryRunning ? "Retrying..." : "Retry"}
                      </button>
                    </div>
                  </div>
                </section>
              ) : null}

              {canCancel ? (
                <section className="rounded-xl border border-rose-200 bg-rose-50/60 p-4">
                  <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
                    <div>
                      <h3 className="text-sm font-semibold text-slate-900">Cancel job</h3>
                      <p className="mt-1 text-xs text-slate-500">
                        Stop this job from continuing through the queue.
                      </p>
                    </div>
                    {cancelConfirming ? (
                      <div className="rounded-lg border border-rose-200 bg-white p-3 sm:max-w-md">
                        <p className="text-xs font-semibold text-slate-900">
                          Cancel job #{job.id}?
                        </p>
                        <p className="mt-1 text-[11px] text-slate-500">
                          This lifecycle action cannot be undone.
                        </p>
                        <div className="mt-3 flex flex-wrap justify-end gap-2">
                          <button
                            className="rounded-lg border border-slate-200 px-3 py-2 text-xs font-semibold text-slate-700 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60"
                            disabled={cancelRunning}
                            onClick={() => setCancelConfirming(false)}
                            type="button"
                          >
                            Keep job
                          </button>
                          <button
                            className="inline-flex items-center gap-2 rounded-lg bg-rose-600 px-3 py-2 text-xs font-semibold text-white transition hover:bg-rose-700 disabled:cursor-not-allowed disabled:opacity-60"
                            disabled={cancelRunning}
                            onClick={() => void handleCancel()}
                            type="button"
                          >
                            <OctagonX className={`h-3.5 w-3.5 ${cancelRunning ? "animate-pulse" : ""}`} />
                            {cancelRunning ? "Cancelling..." : "Confirm cancel"}
                          </button>
                        </div>
                      </div>
                    ) : (
                      <button
                        className="inline-flex min-h-10 items-center justify-center gap-2 rounded-lg bg-rose-600 px-4 text-sm font-semibold text-white transition hover:bg-rose-700"
                        onClick={() => {
                          setActionFeedback(null);
                          setCancelConfirming(true);
                        }}
                        type="button"
                      >
                        <OctagonX className="h-4 w-4" /> Cancel
                      </button>
                    )}
                  </div>
                </section>
              ) : null}

              <dl className="grid grid-cols-2 gap-3 lg:grid-cols-4">
                <DetailItem label="ID" value={`#${job.id}`} />
                <DetailItem label="Job type" value={job.job_type} />
                <DetailItem label="Status" value={<JobStatusBadge status={job.status} />} />
                <DetailItem label="Attempts" value={`${job.attempt_count} / ${job.max_attempts}`} />
                <DetailItem
                  label="Account"
                  value={
                    job.account_id === null ? (
                      "No account target"
                    ) : account ? (
                      <span className="inline-flex items-center gap-1.5"><UserRound className="h-3.5 w-3.5 text-slate-400" />{account.name} (@{account.username})</span>
                    ) : (
                      <span className="text-amber-700">Missing account #{job.account_id}</span>
                    )
                  }
                />
                <DetailItem
                  label="Runtime"
                  value={
                    job.runtime_id === null ? (
                      "No runtime target"
                    ) : runtime ? (
                      <span className="inline-flex items-center gap-1.5"><Cpu className="h-3.5 w-3.5 text-cyan-600" />{runtime.name}</span>
                    ) : (
                      <span className="text-amber-700">Missing runtime #{job.runtime_id}</span>
                    )
                  }
                />
                <DetailItem label="Scheduled" value={formatDate(job.scheduled_at, "Immediate")} />
                <DetailItem label="Started" value={formatDate(job.started_at)} />
                <DetailItem label="Completed" value={formatDate(job.completed_at)} />
                <DetailItem label="Created" value={formatDate(job.created_at)} />
                <DetailItem label="Updated" value={formatDate(job.updated_at)} />
                <DetailItem
                  label="Error message"
                  value={job.error_message ? <span className="text-rose-700">{job.error_message}</span> : "No error"}
                />
              </dl>

              <div className="grid gap-4 lg:grid-cols-2">
                <JsonPanel label="Payload" value={job.payload} />
                <JsonPanel label="Result" value={job.result} />
              </div>

              <section className="overflow-hidden rounded-xl border border-slate-200">
                <div className="flex items-center justify-between border-b border-slate-200 bg-slate-50/80 px-4 py-3">
                  <div>
                    <h3 className="flex items-center gap-2 text-sm font-semibold text-slate-900">
                      <History className="h-4 w-4 text-slate-500" /> Lifecycle logs
                    </h3>
                    <p className="mt-0.5 text-[11px] text-slate-500">Oldest event first</p>
                  </div>
                  {!logsLoading && !logsError && (
                    <span className="rounded-full bg-slate-200 px-2 py-0.5 text-[10px] font-semibold text-slate-600">
                      {logs.length} {logs.length === 1 ? "event" : "events"}
                    </span>
                  )}
                </div>

                {logsLoading ? (
                  <div className="animate-pulse space-y-3 p-4">
                    {Array.from({ length: 3 }).map((_, index) => (
                      <div key={index} className="h-16 rounded-lg bg-slate-100" />
                    ))}
                  </div>
                ) : logsError ? (
                  <div className="p-6 text-center">
                    <AlertTriangle className="mx-auto mb-2 h-6 w-6 text-rose-500" />
                    <p className="text-xs font-medium text-slate-800">Unable to load logs</p>
                    <p className="mt-1 text-[11px] text-slate-500">{logsError}</p>
                    <button
                      type="button"
                      onClick={() => {
                        setLogsLoading(true);
                        setLogsRefresh((value) => value + 1);
                      }}
                      className="mt-3 inline-flex items-center gap-1.5 rounded-lg border border-slate-200 px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50"
                    >
                      <RefreshCw className="h-3.5 w-3.5" /> Retry logs
                    </button>
                  </div>
                ) : logs.length === 0 ? (
                  <div className="p-8 text-center">
                    <History className="mx-auto mb-2 h-7 w-7 text-slate-300" />
                    <p className="text-xs font-medium text-slate-700">No lifecycle logs yet</p>
                    <p className="mt-1 text-[11px] text-slate-400">Events will appear after the job is claimed or transitioned.</p>
                  </div>
                ) : (
                  <ol className="divide-y divide-slate-100">
                    {logs.map((log) => {
                      const isError = log.level.toLowerCase() === "error";
                      const metadata = formatJson(log.metadata);
                      return (
                        <li key={log.id} className="flex gap-3 p-4">
                          <div className={`mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full ${isError ? "bg-rose-100 text-rose-600" : "bg-cyan-100 text-cyan-700"}`}>
                            {isError ? <AlertCircle className="h-3.5 w-3.5" /> : <CircleDot className="h-3.5 w-3.5" />}
                          </div>
                          <div className="min-w-0 flex-1">
                            <div className="flex flex-col justify-between gap-1 sm:flex-row sm:items-center">
                              <div className="flex items-center gap-2">
                                <span className={`rounded px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wider ${isError ? "bg-rose-50 text-rose-700" : "bg-cyan-50 text-cyan-700"}`}>
                                  {log.level}
                                </span>
                                <p className="text-xs font-semibold text-slate-900">{log.message}</p>
                              </div>
                              <time className="flex items-center gap-1 whitespace-nowrap text-[10px] text-slate-400">
                                <CalendarClock className="h-3 w-3" /> {formatDate(log.created_at)}
                              </time>
                            </div>
                            {metadata && (
                              <pre className={`mt-2 overflow-x-auto whitespace-pre-wrap break-words rounded-lg border p-2 text-[10px] leading-relaxed ${isError ? "border-rose-100 bg-rose-50/60 text-rose-800" : "border-slate-200 bg-slate-50 text-slate-600"}`}>
                                {metadata}
                              </pre>
                            )}
                          </div>
                        </li>
                      );
                    })}
                  </ol>
                )}
              </section>
            </div>
          ) : null}
        </div>
      </section>
    </div>
  );
}

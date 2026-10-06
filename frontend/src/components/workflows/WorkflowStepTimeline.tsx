import React, { useEffect, useState } from "react";
import {
  AlertCircle,
  CheckCircle2,
  Clock,
  ExternalLink,
  Hourglass,
  Loader2,
  ThumbsDown,
  ThumbsUp,
  UserCheck,
} from "lucide-react";
import {
  Workflow,
  getWorkflowErrorMessage,
  getWorkflowStepLabel,
} from "@/types/workflow";

interface WorkflowStepTimelineProps {
  workflow: Workflow;
  onViewJob?: (jobId: number) => void;
  onApprove?: (stepId: number, comment?: string) => Promise<void>;
  onReject?: (stepId: number, comment?: string) => Promise<void>;
  isActionInProgress?: boolean;
}

export function WorkflowStepTimeline({
  workflow,
  onViewJob,
  onApprove,
  onReject,
  isActionInProgress = false,
}: WorkflowStepTimelineProps) {
  const [approvalComment, setApprovalComment] = useState("");
  const [approvalSubmitting, setApprovalSubmitting] = useState<"approve" | "reject" | null>(null);
  const [approvalError, setApprovalError] = useState<string | null>(null);

  // Countdown timer for workflow.wait steps
  const [timeRemaining, setTimeRemaining] = useState<Record<number, number>>({});

  useEffect(() => {
    const activeWaitSteps = workflow.steps.filter(
      (s) => s.step_type === "workflow.wait" && s.status === "waiting" && s.resume_at
    );

    if (activeWaitSteps.length === 0) return;

    const calculateTimes = () => {
      const now = Date.now();
      const newTimes: Record<number, number> = {};
      activeWaitSteps.forEach((s) => {
        if (s.resume_at) {
          const diff = Math.max(
            0,
            Math.ceil((new Date(s.resume_at).getTime() - now) / 1000)
          );
          newTimes[s.id] = diff;
        }
      });
      setTimeRemaining(newTimes);
    };

    calculateTimes();
    const interval = setInterval(calculateTimes, 1000);
    return () => clearInterval(interval);
  }, [workflow.steps]);

  const handleApprove = async (stepId: number) => {
    if (!onApprove) return;
    try {
      setApprovalSubmitting("approve");
      setApprovalError(null);
      await onApprove(stepId, approvalComment.trim() || undefined);
      setApprovalComment("");
    } catch (err: unknown) {
      const message =
        err && typeof err === "object" && "message" in err
          ? String((err as { message: unknown }).message)
          : "Approval failed. The workflow state may have changed; refreshing...";
      setApprovalError(message);
    } finally {
      setApprovalSubmitting(null);
    }
  };

  const handleReject = async (stepId: number) => {
    if (!onReject) return;
    try {
      setApprovalSubmitting("reject");
      setApprovalError(null);
      await onReject(stepId, approvalComment.trim() || undefined);
      setApprovalComment("");
    } catch (err: unknown) {
      const message =
        err && typeof err === "object" && "message" in err
          ? String((err as { message: unknown }).message)
          : "Rejection failed. The workflow state may have changed; refreshing...";
      setApprovalError(message);
    } finally {
      setApprovalSubmitting(null);
    }
  };

  const sortedSteps = [...workflow.steps].sort(
    (a, b) => a.step_index - b.step_index
  );

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between pb-2 border-b border-slate-200">
        <h3 className="text-sm font-semibold text-slate-800 uppercase tracking-wider">
          Execution Steps ({sortedSteps.length})
        </h3>
        <span className="text-xs text-slate-500">
          Step {workflow.steps.findIndex((s) => s.id === workflow.current_step_id) + 1} of{" "}
          {sortedSteps.length} active
        </span>
      </div>

      <div className="relative pl-6 space-y-6 before:absolute before:left-2.5 before:top-3 before:bottom-3 before:w-0.5 before:bg-slate-200">
        {sortedSteps.map((step, index) => {
          const isCurrent = step.id === workflow.current_step_id;
          const isCompleted = step.status === "succeeded";
          const isFailed = step.status === "failed";
          const isWaiting = step.status === "waiting";
          const isRunning = step.status === "running";

          // Icon indicator styling
          let markerColor = "bg-slate-300 text-slate-600 ring-slate-100";
          if (isCompleted) {
            markerColor = "bg-emerald-600 text-white ring-emerald-100";
          } else if (isFailed) {
            markerColor = "bg-rose-600 text-white ring-rose-100";
          } else if (isRunning || isCurrent) {
            markerColor = "bg-sky-600 text-white ring-sky-100 animate-pulse";
          } else if (isWaiting) {
            markerColor = "bg-amber-500 text-white ring-amber-100";
          }

          // Step label
          const label = getWorkflowStepLabel(step.step_type, step.step_key);

          // Safe result summary
          let resultSummary: string | null = null;
          if (step.result_json) {
            if (typeof step.result_json.media_uri === "string") {
              resultSummary = `Registered in MediaStore: ${step.result_json.media_uri}`;
            } else if (typeof step.result_json.remote_filename === "string") {
              resultSummary = `Delivered as ${step.result_json.remote_filename}`;
            } else if (typeof step.result_json.status === "string") {
              resultSummary = `Completed: ${step.result_json.status}`;
            }
          }

          const secondsLeft = timeRemaining[step.id];

          return (
            <div key={step.id} className="relative group">
              {/* Step indicator node */}
              <div
                className={`absolute -left-6 top-1.5 w-5 h-5 rounded-full flex items-center justify-center text-xs font-semibold ring-4 ${markerColor}`}
              >
                {isCompleted ? (
                  <CheckCircle2 className="w-3.5 h-3.5" />
                ) : isFailed ? (
                  <AlertCircle className="w-3.5 h-3.5" />
                ) : isRunning ? (
                  <Loader2 className="w-3 h-3 animate-spin" />
                ) : isWaiting ? (
                  <Hourglass className="w-3 h-3" />
                ) : (
                  <span>{index + 1}</span>
                )}
              </div>

              {/* Step Card */}
              <div
                className={`rounded-lg border p-4 transition-all ${
                  isCurrent
                    ? "border-sky-300 bg-sky-50/40 shadow-xs ring-1 ring-sky-200"
                    : isCompleted
                    ? "border-slate-200 bg-white"
                    : isFailed
                    ? "border-rose-200 bg-rose-50/20"
                    : "border-slate-200 bg-slate-50/60 opacity-80"
                }`}
              >
                <div className="flex flex-wrap items-start justify-between gap-2 mb-2">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-mono text-slate-400">
                      #{index + 1}
                    </span>
                    <h4 className="font-semibold text-sm text-slate-900">
                      {label}
                    </h4>
                    <span className="text-[11px] px-2 py-0.5 rounded font-mono text-slate-500 bg-slate-100 border border-slate-200">
                      {step.step_type}
                    </span>
                  </div>

                  <div className="flex items-center gap-2">
                    {/* Status badge */}
                    <span
                      className={`text-xs px-2.5 py-0.5 rounded-full font-medium capitalize ${
                        isCompleted
                          ? "bg-emerald-100 text-emerald-800 border border-emerald-200"
                          : isFailed
                          ? "bg-rose-100 text-rose-800 border border-rose-200"
                          : isWaiting
                          ? "bg-amber-100 text-amber-800 border border-amber-200"
                          : isRunning
                          ? "bg-sky-100 text-sky-800 border border-sky-200"
                          : "bg-slate-100 text-slate-600 border border-slate-200"
                      }`}
                    >
                      {step.status}
                    </span>

                    {/* Job Link */}
                    {step.job_id && (
                      <button
                        type="button"
                        onClick={() => onViewJob?.(step.job_id!)}
                        className="inline-flex items-center gap-1 text-xs text-indigo-600 hover:text-indigo-800 font-medium px-2 py-0.5 rounded bg-indigo-50 hover:bg-indigo-100 border border-indigo-200 transition-colors"
                        title="View associated background Job details"
                      >
                        <span>Job #{step.job_id}</span>
                        <ExternalLink className="w-3 h-3" />
                      </button>
                    )}
                  </div>
                </div>

                {/* Timing & Attempt info */}
                <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-slate-500 mb-2">
                  {step.started_at && (
                    <span>
                      Started: {new Date(step.started_at).toLocaleTimeString()}
                    </span>
                  )}
                  {step.completed_at && (
                    <span>
                      Completed: {new Date(step.completed_at).toLocaleTimeString()}
                    </span>
                  )}
                  {step.attempt > 1 && (
                    <span className="text-amber-600 font-medium">
                      Attempt {step.attempt} / {step.max_attempts}
                    </span>
                  )}
                </div>

                {/* Safe Result Summary */}
                {resultSummary && (
                  <div className="text-xs text-emerald-800 bg-emerald-50/70 border border-emerald-200 rounded px-2.5 py-1.5 my-2">
                    {resultSummary}
                  </div>
                )}

                {/* Safe Error Summary */}
                {step.error_code && (
                  <div className="text-xs text-rose-800 bg-rose-50 border border-rose-200 rounded p-2.5 my-2 flex items-start gap-2">
                    <AlertCircle className="w-4 h-4 text-rose-600 shrink-0 mt-0.5" />
                    <div>
                      <span className="font-semibold block font-mono text-[11px]">
                        [{step.error_code}]
                      </span>
                      <span>
                        {getWorkflowErrorMessage(
                          step.error_code,
                          step.error_message
                        )}
                      </span>
                    </div>
                  </div>
                )}

                {/* Wait Countdown Box */}
                {step.step_type === "workflow.wait" && isWaiting && (
                  <div className="mt-3 p-3 bg-indigo-50/80 border border-indigo-200 rounded-lg">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2 text-indigo-900 font-medium text-xs">
                        <Clock className="w-4 h-4 text-indigo-600 animate-spin" />
                        <span>Timer active: Waiting duration</span>
                      </div>
                      <div className="font-mono text-sm font-bold text-indigo-700 bg-white px-2 py-0.5 rounded border border-indigo-200">
                        {secondsLeft !== undefined
                          ? secondsLeft > 0
                            ? `${secondsLeft}s remaining`
                            : "Elapsed (resuming...)"
                          : "Calculating..."}
                      </div>
                    </div>
                    {step.resume_at && (
                      <p className="text-[11px] text-indigo-600 mt-1">
                        Resume deadline:{" "}
                        {new Date(step.resume_at).toLocaleTimeString()}
                      </p>
                    )}
                  </div>
                )}

                {/* Approval Interactive UX */}
                {step.step_type === "workflow.approval" && isWaiting && (
                  <div className="mt-3 p-4 bg-amber-50 border border-amber-300 rounded-lg space-y-3">
                    <div className="flex items-start gap-2">
                      <UserCheck className="w-5 h-5 text-amber-600 shrink-0 mt-0.5" />
                      <div>
                        <h5 className="font-semibold text-xs text-amber-900">
                          {workflow.template_key === "publishing_prepare_review"
                            ? "Publishing Preparation Review"
                            : "Operator Approval Required"}
                        </h5>
                        <p className="text-xs text-amber-700 mt-0.5 font-medium leading-relaxed">
                          {workflow.template_key === "publishing_prepare_review" ? (
                            <>
                              &ldquo;Environment is prepared for publishing. Approval confirms preparation only. No content has been published.&rdquo;
                            </>
                          ) : (
                            "Content was delivered to the device. Inspect the preview and approve or reject the workflow to proceed."
                          )}
                        </p>
                      </div>
                    </div>

                    {approvalError && (
                      <div className="text-xs text-rose-800 bg-rose-50 border border-rose-200 rounded p-2 flex items-center gap-1.5">
                        <AlertCircle className="w-4 h-4 text-rose-600 shrink-0" />
                        <span>{approvalError}</span>
                      </div>
                    )}

                    <div className="space-y-1">
                      <label className="text-[11px] font-medium text-slate-700">
                        Reviewer Comment (optional)
                      </label>
                      <input
                        type="text"
                        value={approvalComment}
                        onChange={(e) => setApprovalComment(e.target.value)}
                        placeholder="e.g. Verified device screen layout looks great"
                        disabled={
                          approvalSubmitting !== null || isActionInProgress
                        }
                        className="w-full text-xs px-3 py-2 bg-white border border-slate-300 rounded-md focus:outline-none focus:ring-2 focus:ring-amber-500 disabled:bg-slate-100"
                      />
                    </div>

                    <div className="flex items-center gap-3 pt-1">
                      <button
                        type="button"
                        onClick={() => handleApprove(step.id)}
                        disabled={
                          approvalSubmitting !== null || isActionInProgress
                        }
                        className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-md text-xs font-semibold text-white bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50 transition-colors shadow-xs"
                      >
                        {approvalSubmitting === "approve" ? (
                          <Loader2 className="w-3.5 h-3.5 animate-spin" />
                        ) : (
                          <ThumbsUp className="w-3.5 h-3.5" />
                        )}
                        <span>
                          {workflow.template_key === "publishing_prepare_review"
                            ? "Approve Preparation"
                            : "Approve Step"}
                        </span>
                      </button>

                      <button
                        type="button"
                        onClick={() => handleReject(step.id)}
                        disabled={
                          approvalSubmitting !== null || isActionInProgress
                        }
                        className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-md text-xs font-semibold text-white bg-rose-600 hover:bg-rose-700 disabled:opacity-50 transition-colors shadow-xs"
                      >
                        {approvalSubmitting === "reject" ? (
                          <Loader2 className="w-3.5 h-3.5 animate-spin" />
                        ) : (
                          <ThumbsDown className="w-3.5 h-3.5" />
                        )}
                        <span>
                          {workflow.template_key === "publishing_prepare_review"
                            ? "Reject"
                            : "Reject Step"}
                        </span>
                      </button>
                    </div>
                  </div>
                )}

                {/* Completed Approval Decision info */}
                {step.step_type === "workflow.approval" &&
                  step.approval_decision && (
                    <div
                      className={`text-xs rounded p-2.5 my-2 border flex items-center justify-between ${
                        step.approval_decision === "approved"
                          ? "bg-emerald-50/70 border-emerald-200 text-emerald-800"
                          : "bg-rose-50/70 border-rose-200 text-rose-800"
                      }`}
                    >
                      <div className="flex items-center gap-2">
                        {step.approval_decision === "approved" ? (
                          <ThumbsUp className="w-4 h-4 text-emerald-600" />
                        ) : (
                          <ThumbsDown className="w-4 h-4 text-rose-600" />
                        )}
                        <span>
                          Decision:{" "}
                          <strong className="capitalize">
                            {step.approval_decision}
                          </strong>{" "}
                          by {step.approval_actor || "operator"}
                        </span>
                      </div>
                      {step.approval_comment && (
                        <span className="italic text-[11px] text-slate-600 truncate max-w-xs">
                          &ldquo;{step.approval_comment}&rdquo;
                        </span>
                      )}
                    </div>
                  )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

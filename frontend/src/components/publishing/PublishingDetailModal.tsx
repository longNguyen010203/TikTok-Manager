import React, { useEffect, useState, useRef, useCallback } from "react";
import { PublishingSession } from "@/types/publishing";
import {
  Workflow,
  canCancelWorkflow,
  canPauseWorkflow,
  canResumeWorkflow,
  canRetryWorkflow,
  formatWorkflowDuration,
} from "@/types/workflow";
import { workflowService } from "@/services/workflowService";
import { publishingService } from "@/services/publishingService";
import { PublishingStatusBadge } from "./PublishingStatusBadge";
import { formatApiError } from "@/types/runtime";
import {
  X,
  Rocket,
  AlertCircle,
  Clock,
  Loader2,
  PlayCircle,
  PauseCircle,
  RotateCcw,
  OctagonX,
  UserCheck,
  ThumbsUp,
  ThumbsDown,
  ExternalLink,
  Sparkles,
} from "lucide-react";

interface PublishingDetailModalProps {
  session: PublishingSession | null;
  isOpen: boolean;
  onClose: () => void;
  onViewJob?: (jobId: number) => void;
  onSessionUpdated?: () => void;
}

export function PublishingDetailModal({
  session,
  isOpen,
  onClose,
  onViewJob,
  onSessionUpdated,
}: PublishingDetailModalProps) {
  const [prevSessionId, setPrevSessionId] = useState<number | null>(session?.id ?? null);
  const [workflow, setWorkflow] = useState<Workflow | null>(null);
  const [currentSession, setCurrentSession] = useState<PublishingSession | null>(session);
  const [isLoading, setIsLoading] = useState(true);
  const [actionError, setActionError] = useState<string | null>(null);
  const [isActionInProgress, setIsActionInProgress] = useState(false);

  if (session && session.id !== prevSessionId) {
    setPrevSessionId(session.id);
    setCurrentSession(session);
  }

  // Approval form state
  const [approvalComment, setApprovalComment] = useState("");
  const [isSubmittingApproval, setIsSubmittingApproval] = useState<"approve" | "reject" | null>(null);

  // Auto-polling ref
  const pollTimerRef = useRef<NodeJS.Timeout | null>(null);

  const isTerminal = (status?: string) =>
    ["prepared", "rejected", "failed", "cancelled"].includes(status || "");

  const refreshState = useCallback(
    async (showLoading = false) => {
      if (!session) return;
      try {
        if (showLoading) setIsLoading(true);
        setActionError(null);

        const [wfRes, sessRes] = await Promise.all([
          workflowService.getWorkflow(session.workflow_id).catch(() => null),
          publishingService.getPublishingSession(session.id).catch(() => null),
        ]);

        if (wfRes) setWorkflow(wfRes);
        if (sessRes) {
          setCurrentSession(sessRes);
          onSessionUpdated?.();
        }
      } catch (err: unknown) {
        setActionError(formatApiError(err));
      } finally {
        if (showLoading) setIsLoading(false);
      }
    },
    [session, onSessionUpdated]
  );

  useEffect(() => {
    if (!isOpen || !session) return;

    let ignore = false;
    Promise.all([
      workflowService.getWorkflow(session.workflow_id).catch(() => null),
      publishingService.getPublishingSession(session.id).catch(() => null),
    ])
      .then(([wfRes, sessRes]) => {
        if (ignore) return;
        if (wfRes) setWorkflow(wfRes);
        if (sessRes) {
          setCurrentSession(sessRes);
          onSessionUpdated?.();
        }
      })
      .catch((err: unknown) => {
        if (!ignore) setActionError(formatApiError(err));
      })
      .finally(() => {
        if (!ignore) setIsLoading(false);
      });

    // Start bounded polling if not terminal
    if (!isTerminal(session.status)) {
      pollTimerRef.current = setInterval(() => {
        refreshState(false);
      }, 2500);
    }

    return () => {
      ignore = true;
      if (pollTimerRef.current) {
        clearInterval(pollTimerRef.current);
        pollTimerRef.current = null;
      }
    };
  }, [isOpen, session, refreshState, onSessionUpdated]);

  // Stop polling once session or workflow becomes terminal
  useEffect(() => {
    if (currentSession && isTerminal(currentSession.status) && pollTimerRef.current) {
      clearInterval(pollTimerRef.current);
      pollTimerRef.current = null;
    }
  }, [currentSession]);

  if (!isOpen || !session) return null;

  const handlePause = async () => {
    if (!workflow) return;
    try {
      setIsActionInProgress(true);
      setActionError(null);
      const updated = await workflowService.pauseWorkflow(workflow.id);
      setWorkflow(updated);
      await refreshState(false);
    } catch (err: unknown) {
      setActionError(formatApiError(err));
    } finally {
      setIsActionInProgress(false);
    }
  };

  const handleResume = async () => {
    if (!workflow) return;
    try {
      setIsActionInProgress(true);
      setActionError(null);
      const updated = await workflowService.resumeWorkflow(workflow.id);
      setWorkflow(updated);
      await refreshState(false);
    } catch (err: unknown) {
      setActionError(formatApiError(err));
    } finally {
      setIsActionInProgress(false);
    }
  };

  const handleCancel = async () => {
    if (!workflow) return;
    try {
      setIsActionInProgress(true);
      setActionError(null);
      const updated = await workflowService.cancelWorkflow(workflow.id);
      setWorkflow(updated);
      await refreshState(false);
    } catch (err: unknown) {
      setActionError(formatApiError(err));
    } finally {
      setIsActionInProgress(false);
    }
  };

  const handleRetry = async () => {
    if (!workflow) return;
    try {
      setIsActionInProgress(true);
      setActionError(null);
      const updated = await workflowService.retryWorkflow(workflow.id);
      setWorkflow(updated);
      await refreshState(false);
    } catch (err: unknown) {
      setActionError(formatApiError(err));
    } finally {
      setIsActionInProgress(false);
    }
  };

  const handleApprove = async (stepId: number) => {
    if (!workflow) return;
    try {
      setIsSubmittingApproval("approve");
      setActionError(null);
      const updated = await workflowService.approveStep(workflow.id, stepId, {
        actor: "operator",
        comment: approvalComment.trim() || undefined,
      });
      setWorkflow(updated);
      setApprovalComment("");
      await refreshState(false);
    } catch (err: unknown) {
      setActionError(formatApiError(err));
    } finally {
      setIsSubmittingApproval(null);
    }
  };

  const handleReject = async (stepId: number) => {
    if (!workflow) return;
    try {
      setIsSubmittingApproval("reject");
      setActionError(null);
      const updated = await workflowService.rejectStep(workflow.id, stepId, {
        actor: "operator",
        comment: approvalComment.trim() || undefined,
      });
      setWorkflow(updated);
      setApprovalComment("");
      await refreshState(false);
    } catch (err: unknown) {
      setActionError(formatApiError(err));
    } finally {
      setIsSubmittingApproval(null);
    }
  };

  const formatDate = (isoString?: string | null) => {
    if (!isoString) return "N/A";
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

  const activeApprovalStep = workflow?.steps.find(
    (s) => s.step_type === "workflow.approval" && s.status === "waiting"
  );

  const sortedSteps = workflow
    ? [...workflow.steps].sort((a, b) => a.step_index - b.step_index)
    : [];

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-xs overflow-y-auto">
      <div className="relative w-full max-w-4xl bg-white rounded-xl shadow-2xl border border-slate-200 overflow-hidden my-6 max-h-[92vh] flex flex-col">
        {/* Header */}
        <div className="flex items-start justify-between px-6 py-4 border-b border-slate-200 bg-slate-50/70 shrink-0">
          <div className="space-y-1">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="font-mono text-xs text-slate-500 font-semibold">
                Session #{session.id}
              </span>
              <span className="text-slate-300">&bull;</span>
              <span className="font-mono text-xs text-slate-500 font-semibold">
                Workflow #{session.workflow_id}
              </span>
              <PublishingStatusBadge status={currentSession?.status || session.status} />
            </div>
            <h2 className="text-base font-bold text-slate-900">
              {workflow?.name || "Publishing Preparation Session"}
            </h2>
          </div>

          <button
            type="button"
            onClick={onClose}
            className="p-1.5 text-slate-400 hover:text-slate-600 hover:bg-slate-200 rounded-lg transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Prominent Warning Callout */}
        <div className="px-6 py-2.5 bg-amber-50 border-b border-amber-200/80 text-amber-900 flex items-center gap-2.5 text-xs font-semibold shrink-0">
          <Sparkles className="w-4 h-4 text-amber-600 shrink-0" />
          <span>&ldquo;Prepared does not mean published.&rdquo; Execution verifies device, app, and content readiness only.</span>
        </div>

        {/* Global Error Notice */}
        {actionError && (
          <div className="mx-6 mt-4 p-3 bg-rose-50 border border-rose-200 rounded-lg text-xs text-rose-800 flex items-center gap-2 shrink-0">
            <AlertCircle className="w-4 h-4 text-rose-600 shrink-0" />
            <span>{actionError}</span>
          </div>
        )}

        {/* Controls Toolbar */}
        {workflow && (
          <div className="px-6 py-2.5 border-b border-slate-100 bg-white flex items-center justify-between gap-3 shrink-0 flex-wrap">
            <div className="flex items-center gap-2">
              {canPauseWorkflow(workflow.status, workflow.pause_requested_at) && (
                <button
                  type="button"
                  onClick={handlePause}
                  disabled={isActionInProgress}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold text-amber-800 bg-amber-50 hover:bg-amber-100 border border-amber-200 rounded-lg transition-colors disabled:opacity-50"
                >
                  <PauseCircle className="w-3.5 h-3.5" />
                  <span>Pause</span>
                </button>
              )}

              {canResumeWorkflow(workflow.status) && (
                <button
                  type="button"
                  onClick={handleResume}
                  disabled={isActionInProgress}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold text-emerald-800 bg-emerald-50 hover:bg-emerald-100 border border-emerald-200 rounded-lg transition-colors disabled:opacity-50"
                >
                  <PlayCircle className="w-3.5 h-3.5" />
                  <span>Resume</span>
                </button>
              )}

              {canCancelWorkflow(workflow.status, workflow.cancel_requested_at) && (
                <button
                  type="button"
                  onClick={handleCancel}
                  disabled={isActionInProgress}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold text-slate-700 bg-white hover:bg-slate-100 border border-slate-300 rounded-lg transition-colors disabled:opacity-50"
                >
                  <OctagonX className="w-3.5 h-3.5 text-slate-500" />
                  <span>Cancel</span>
                </button>
              )}

              {canRetryWorkflow(workflow.status) && (
                <button
                  type="button"
                  onClick={handleRetry}
                  disabled={isActionInProgress}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold text-indigo-700 bg-indigo-50 hover:bg-indigo-100 border border-indigo-200 rounded-lg transition-colors disabled:opacity-50"
                >
                  <RotateCcw className="w-3.5 h-3.5" />
                  <span>Retry Preparation</span>
                </button>
              )}
            </div>

            <div className="text-[11px] text-slate-400 font-mono flex items-center gap-2">
              <Clock className="w-3 h-3 text-slate-400" />
              <span>Duration: {formatWorkflowDuration(workflow.started_at, workflow.completed_at) || "Not started"}</span>
            </div>
          </div>
        )}

        {/* Body Content */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {isLoading && !workflow ? (
            <div className="py-16 flex flex-col items-center justify-center text-slate-400 gap-2">
              <Loader2 className="w-6 h-6 animate-spin text-rose-600" />
              <span className="text-xs">Loading preparation state...</span>
            </div>
          ) : (
            <>
              {/* Snapshot Cards */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
                <div className="p-3 bg-slate-50 border border-slate-200 rounded-lg">
                  <span className="text-[10px] text-slate-400 uppercase font-semibold block">Account</span>
                  <span className="font-semibold text-slate-800">Account #{session.account_id_snapshot}</span>
                </div>
                <div className="p-3 bg-slate-50 border border-slate-200 rounded-lg">
                  <span className="text-[10px] text-slate-400 uppercase font-semibold block">Runtime</span>
                  <span className="font-semibold text-slate-800 font-mono">Runtime #{session.runtime_id_snapshot}</span>
                </div>
                <div className="p-3 bg-slate-50 border border-slate-200 rounded-lg">
                  <span className="text-[10px] text-slate-400 uppercase font-semibold block">Content Version</span>
                  <span className="font-semibold text-slate-800 font-mono">Version #{session.content_asset_version_id}</span>
                </div>
                <div className="p-3 bg-slate-50 border border-slate-200 rounded-lg">
                  <span className="text-[10px] text-slate-400 uppercase font-semibold block">App Version</span>
                  <span className="font-semibold text-slate-800 font-mono">App #{session.managed_app_id} (v{session.managed_app_version_id})</span>
                </div>
              </div>

              {/* Approval Boundary Card if waiting approval */}
              {activeApprovalStep && (
                <div className="p-5 rounded-xl border border-amber-300 bg-amber-50/80 space-y-4 shadow-sm animate-in fade-in">
                  <div className="flex items-start gap-3">
                    <UserCheck className="w-6 h-6 text-amber-600 shrink-0 mt-0.5" />
                    <div className="space-y-1">
                      <h4 className="font-bold text-sm text-amber-950">
                        Approval Boundary: Ready for Review
                      </h4>
                      <p className="text-xs text-amber-800 font-medium leading-relaxed">
                        &ldquo;Environment is prepared for publishing. Approval confirms preparation only. No content has been published.&rdquo;
                      </p>
                    </div>
                  </div>

                  <div className="space-y-1">
                    <label className="text-[11px] font-semibold text-slate-700">
                      Operator Comment (optional)
                    </label>
                    <input
                      type="text"
                      value={approvalComment}
                      onChange={(e) => setApprovalComment(e.target.value)}
                      placeholder="e.g. Verified target app is open on device screen"
                      disabled={isSubmittingApproval !== null}
                      className="w-full text-xs px-3 py-2 bg-white border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-amber-500"
                    />
                  </div>

                  <div className="flex items-center gap-3 pt-1">
                    <button
                      type="button"
                      onClick={() => handleApprove(activeApprovalStep.id)}
                      disabled={isSubmittingApproval !== null}
                      className="inline-flex items-center gap-1.5 px-4 py-2 text-xs font-semibold text-white bg-emerald-600 hover:bg-emerald-700 rounded-lg shadow-sm transition-colors disabled:opacity-50"
                    >
                      {isSubmittingApproval === "approve" ? (
                        <Loader2 className="w-3.5 h-3.5 animate-spin" />
                      ) : (
                        <ThumbsUp className="w-3.5 h-3.5" />
                      )}
                      <span>Approve Preparation</span>
                    </button>

                    <button
                      type="button"
                      onClick={() => handleReject(activeApprovalStep.id)}
                      disabled={isSubmittingApproval !== null}
                      className="inline-flex items-center gap-1.5 px-4 py-2 text-xs font-semibold text-white bg-rose-600 hover:bg-rose-700 rounded-lg shadow-sm transition-colors disabled:opacity-50"
                    >
                      {isSubmittingApproval === "reject" ? (
                        <Loader2 className="w-3.5 h-3.5 animate-spin" />
                      ) : (
                        <ThumbsDown className="w-3.5 h-3.5" />
                      )}
                      <span>Reject</span>
                    </button>
                  </div>
                </div>
              )}

              {/* Preparation Timeline */}
              <div className="space-y-3">
                <h3 className="text-xs font-bold text-slate-800 uppercase tracking-wider flex items-center gap-1.5">
                  <Rocket className="w-3.5 h-3.5 text-rose-600" />
                  <span>Preparation Timeline</span>
                </h3>

                <div className="relative pl-6 space-y-4 before:absolute before:left-2.5 before:top-3 before:bottom-3 before:w-0.5 before:bg-slate-200">
                  {sortedSteps.map((step) => {
                    const isSuccess = step.status === "succeeded";
                    const isFailed = step.status === "failed";
                    const isWaiting = step.status === "waiting";
                    const isRunning = step.status === "running";

                    let stepColor = "bg-slate-300 text-slate-600";
                    if (isSuccess) stepColor = "bg-emerald-600 text-white";
                    else if (isFailed) stepColor = "bg-rose-600 text-white";
                    else if (isWaiting) stepColor = "bg-amber-500 text-white";
                    else if (isRunning) stepColor = "bg-sky-600 text-white animate-pulse";

                    const getStepDisplayName = () => {
                      switch (step.step_type) {
                        case "publishing.verify_runtime":
                          return "1. Verify Runtime (container, boot, ADB)";
                        case "publishing.verify_app":
                          return "2. Verify Managed App (package, version, signature)";
                        case "content.deliver":
                          return "3. Deliver Media Content (push, MediaStore index)";
                        case "device.launch_app":
                          return "4. Launch Application";
                        case "publishing.verify_app_state":
                          return "5. Verify App State (foreground active)";
                        case "workflow.approval":
                          return "6. Review & Approval Boundary";
                        default:
                          return step.step_key;
                      }
                    };

                    return (
                      <div key={step.id} className="relative group">
                        <div
                          className={`absolute -left-6 top-1 w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-bold ring-4 ring-white ${stepColor}`}
                        >
                          {step.step_index + 1}
                        </div>

                        <div className="p-3.5 rounded-xl border border-slate-200 bg-white hover:border-slate-300 transition-all space-y-1.5">
                          <div className="flex items-center justify-between gap-2">
                            <span className="font-semibold text-xs text-slate-900">
                              {getStepDisplayName()}
                            </span>
                            <span
                              className={`text-[10px] px-2 py-0.5 rounded-full font-semibold capitalize ${
                                isSuccess
                                  ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
                                  : isFailed
                                  ? "bg-rose-50 text-rose-700 border border-rose-200"
                                  : isWaiting
                                  ? "bg-amber-50 text-amber-700 border border-amber-200"
                                  : isRunning
                                  ? "bg-sky-50 text-sky-700 border border-sky-200"
                                  : "bg-slate-100 text-slate-600"
                              }`}
                            >
                              {step.status}
                            </span>
                          </div>

                          <div className="flex items-center gap-4 text-[11px] text-slate-400 font-mono">
                            {step.started_at && <span>Started: {formatDate(step.started_at)}</span>}
                            {step.completed_at && <span>Completed: {formatDate(step.completed_at)}</span>}
                            {step.job_id && (
                              <button
                                type="button"
                                onClick={() => onViewJob?.(step.job_id!)}
                                className="inline-flex items-center gap-1 text-indigo-600 hover:text-indigo-800 font-semibold"
                              >
                                <span>Job #{step.job_id}</span>
                                <ExternalLink className="w-3 h-3" />
                              </button>
                            )}
                          </div>

                          {step.error_message && (
                            <div className="p-2 bg-rose-50 border border-rose-200 rounded text-rose-700 text-xs">
                              <strong>Error ({step.error_code || "STEP_FAILED"}):</strong> {step.error_message}
                            </div>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            </>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-3 border-t border-slate-200 bg-slate-50/50 flex justify-end shrink-0">
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

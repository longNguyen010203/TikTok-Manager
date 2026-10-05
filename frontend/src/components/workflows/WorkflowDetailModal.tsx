import React, { useEffect, useState, useRef, useCallback } from "react";
import {
  AlertCircle,
  Clock,
  Cpu,
  FileBox,
  Info,
  Loader2,
  OctagonX,
  PauseCircle,
  PlayCircle,
  RefreshCw,
  RotateCcw,
  X,
} from "lucide-react";
import { workflowService } from "@/services/workflowService";
import {
  Workflow,
  canCancelWorkflow,
  canPauseWorkflow,
  canResumeWorkflow,
  canRetryWorkflow,
  canStartWorkflow,
  formatWorkflowDuration,
  getWorkflowErrorMessage,
  isWorkflowActive,
} from "@/types/workflow";
import { Runtime } from "@/types/runtime";
import { Device } from "@/types/device";
import { ContentAsset } from "@/types/content";
import { WorkflowStatusBadge } from "./WorkflowStatusBadge";
import { WorkflowStepTimeline } from "./WorkflowStepTimeline";
import { WorkflowEventTimeline } from "./WorkflowEventTimeline";
import { WorkflowCancelModal } from "./WorkflowCancelModal";

interface WorkflowDetailModalProps {
  workflowId: number | null;
  runtimesMap: Record<number, Runtime>;
  devicesMap: Record<number, Device>;
  contentAssetsMap: Record<number, ContentAsset>;
  onClose: () => void;
  onViewJob?: (jobId: number) => void;
  onWorkflowUpdated?: (updated: Workflow) => void;
}

export function WorkflowDetailModal({
  workflowId,
  runtimesMap,
  devicesMap,
  contentAssetsMap,
  onClose,
  onViewJob,
  onWorkflowUpdated,
}: WorkflowDetailModalProps) {
  const [workflow, setWorkflow] = useState<Workflow | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [actionError, setActionError] = useState<string | null>(null);
  const [isActionInProgress, setIsActionInProgress] = useState(false);
  const [activeTab, setActiveTab] = useState<"steps" | "events" | "config">("steps");

  // Cancel dialog
  const [isCancelOpen, setIsCancelOpen] = useState(false);
  const [isCancelling, setIsCancelling] = useState(false);

  // Poll timer
  const pollTimerRef = useRef<NodeJS.Timeout | null>(null);

  const stopPolling = useCallback(() => {
    if (pollTimerRef.current) {
      clearInterval(pollTimerRef.current);
      pollTimerRef.current = null;
    }
  }, []);

  const refreshWorkflow = useCallback(async () => {
    if (!workflowId) return;
    try {
      const wf = await workflowService.getWorkflow(workflowId);
      setWorkflow(wf);
      onWorkflowUpdated?.(wf);
      setActionError(null);
    } catch {
      // background polling error
    }
  }, [workflowId, onWorkflowUpdated]);

  // Initial load
  useEffect(() => {
    if (!workflowId) return;

    let ignore = false;

    workflowService
      .getWorkflow(workflowId)
      .then((wf) => {
        if (ignore) return;
        setWorkflow(wf);
        onWorkflowUpdated?.(wf);
        setActionError(null);
      })
      .catch((err: unknown) => {
        if (ignore) return;
        setActionError(
          err && typeof err === "object" && "message" in err
            ? String((err as { message: unknown }).message)
            : "Failed to load workflow details"
        );
      })
      .finally(() => {
        if (!ignore) setIsLoading(false);
      });

    return () => {
      ignore = true;
      stopPolling();
    };
  }, [workflowId, onWorkflowUpdated, stopPolling]);

  // Dynamic polling based on status
  useEffect(() => {
    if (!workflow) return;

    if (isWorkflowActive(workflow.status)) {
      if (!pollTimerRef.current) {
        pollTimerRef.current = setInterval(() => {
          refreshWorkflow();
        }, 2000);
      }
    } else {
      stopPolling();
    }

    return () => {
      stopPolling();
    };
  }, [workflow, refreshWorkflow, stopPolling]);

  if (!workflowId) return null;

  // Actions
  const handleStart = async () => {
    if (!workflow) return;
    try {
      setIsActionInProgress(true);
      setActionError(null);
      const updated = await workflowService.startWorkflow(workflow.id);
      setWorkflow(updated);
      onWorkflowUpdated?.(updated);
    } catch (err: unknown) {
      setActionError(
        err && typeof err === "object" && "message" in err
          ? String((err as { message: unknown }).message)
          : "Failed to start workflow"
      );
    } finally {
      setIsActionInProgress(false);
    }
  };

  const handlePause = async () => {
    if (!workflow) return;
    try {
      setIsActionInProgress(true);
      setActionError(null);
      const updated = await workflowService.pauseWorkflow(workflow.id);
      setWorkflow(updated);
      onWorkflowUpdated?.(updated);
    } catch (err: unknown) {
      setActionError(
        err && typeof err === "object" && "message" in err
          ? String((err as { message: unknown }).message)
          : "Failed to pause workflow"
      );
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
      onWorkflowUpdated?.(updated);
    } catch (err: unknown) {
      setActionError(
        err && typeof err === "object" && "message" in err
          ? String((err as { message: unknown }).message)
          : "Failed to resume workflow"
      );
    } finally {
      setIsActionInProgress(false);
    }
  };

  const handleConfirmCancel = async () => {
    if (!workflow) return;
    try {
      setIsCancelling(true);
      setActionError(null);
      const updated = await workflowService.cancelWorkflow(workflow.id);
      setWorkflow(updated);
      onWorkflowUpdated?.(updated);
      setIsCancelOpen(false);
    } catch (err: unknown) {
      setActionError(
        err && typeof err === "object" && "message" in err
          ? String((err as { message: unknown }).message)
          : "Failed to cancel workflow"
      );
    } finally {
      setIsCancelling(false);
    }
  };

  const handleRetry = async () => {
    if (!workflow) return;
    try {
      setIsActionInProgress(true);
      setActionError(null);
      const updated = await workflowService.retryWorkflow(workflow.id);
      setWorkflow(updated);
      onWorkflowUpdated?.(updated);
    } catch (err: unknown) {
      setActionError(
        err && typeof err === "object" && "message" in err
          ? String((err as { message: unknown }).message)
          : "Failed to retry workflow"
      );
    } finally {
      setIsActionInProgress(false);
    }
  };

  const handleApproveStep = async (stepId: number, comment?: string) => {
    if (!workflow) return;
    const updated = await workflowService.approveStep(workflow.id, stepId, {
      actor: "operator",
      comment,
    });
    setWorkflow(updated);
    onWorkflowUpdated?.(updated);
  };

  const handleRejectStep = async (stepId: number, comment?: string) => {
    if (!workflow) return;
    const updated = await workflowService.rejectStep(workflow.id, stepId, {
      actor: "operator",
      comment,
    });
    setWorkflow(updated);
    onWorkflowUpdated?.(updated);
  };

  const targetRuntime = workflow
    ? runtimesMap[workflow.runtime_id_snapshot]
    : null;
  const targetDevice = targetRuntime
    ? devicesMap[targetRuntime.device_id]
    : null;
  const targetContent = workflow
    ? contentAssetsMap[workflow.content_asset_id]
    : null;

  const currentStep = workflow?.steps.find(
    (s) => s.id === workflow.current_step_id
  );

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-xs overflow-y-auto">
      <div className="relative w-full max-w-4xl bg-white rounded-xl shadow-2xl border border-slate-200 overflow-hidden my-6 max-h-[92vh] flex flex-col">
        {/* Header */}
        <div className="flex items-start justify-between px-6 py-4 border-b border-slate-200 bg-slate-50/70 shrink-0">
          <div className="space-y-1">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="font-mono text-xs text-slate-500 font-semibold">
                Workflow #{workflow?.id ?? workflowId}
              </span>
              {workflow && (
                <>
                  <WorkflowStatusBadge
                    status={workflow.status}
                    waitingReason={currentStep?.waiting_reason}
                  />
                  <span className="text-xs px-2 py-0.5 rounded font-mono bg-slate-200 text-slate-700">
                    {workflow.template_key}:v{workflow.template_version}
                  </span>
                </>
              )}
            </div>

            <h2 className="text-base font-bold text-slate-900">
              {workflow?.name || "Loading Workflow..."}
            </h2>

            {workflow?.description && (
              <p className="text-xs text-slate-500 line-clamp-2">
                {workflow.description}
              </p>
            )}
          </div>

          <div className="flex items-center gap-2 shrink-0">
            <button
              type="button"
              onClick={refreshWorkflow}
              className="p-1.5 rounded-lg text-slate-500 hover:text-slate-800 hover:bg-slate-200 transition-colors"
              title="Refresh"
            >
              <RefreshCw className="w-4 h-4" />
            </button>
            <button
              type="button"
              onClick={onClose}
              className="p-1.5 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-200 transition-colors"
              title="Close"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Action Command Bar */}
        {workflow && (
          <div className="px-6 py-3 bg-white border-b border-slate-200 flex flex-wrap items-center justify-between gap-3 shrink-0">
            <div className="flex items-center gap-2">
              {/* Start */}
              {canStartWorkflow(workflow.status) && (
                <button
                  type="button"
                  onClick={handleStart}
                  disabled={isActionInProgress}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-semibold text-white bg-sky-600 hover:bg-sky-700 disabled:opacity-50 transition-colors shadow-xs"
                >
                  <PlayCircle className="w-3.5 h-3.5" />
                  <span>Start Workflow</span>
                </button>
              )}

              {/* Pause */}
              {canPauseWorkflow(workflow.status, workflow.pause_requested_at) && (
                <button
                  type="button"
                  onClick={handlePause}
                  disabled={isActionInProgress}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-semibold text-amber-900 bg-amber-100 hover:bg-amber-200 border border-amber-300 disabled:opacity-50 transition-colors"
                  title="Pause will take effect after current step finishes"
                >
                  <PauseCircle className="w-3.5 h-3.5 text-amber-700" />
                  <span>Pause</span>
                </button>
              )}

              {/* Resume */}
              {canResumeWorkflow(workflow.status) && (
                <button
                  type="button"
                  onClick={handleResume}
                  disabled={isActionInProgress}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-semibold text-white bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50 transition-colors shadow-xs"
                >
                  <PlayCircle className="w-3.5 h-3.5" />
                  <span>Resume Workflow</span>
                </button>
              )}

              {/* Retry */}
              {canRetryWorkflow(workflow.status) && (
                <button
                  type="button"
                  onClick={handleRetry}
                  disabled={isActionInProgress}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-semibold text-purple-900 bg-purple-100 hover:bg-purple-200 border border-purple-300 disabled:opacity-50 transition-colors"
                  title="Retry workflow with same pinned bindings"
                >
                  <RotateCcw className="w-3.5 h-3.5 text-purple-700" />
                  <span>Retry Workflow</span>
                </button>
              )}

              {/* Cancel */}
              {canCancelWorkflow(
                workflow.status,
                workflow.cancel_requested_at
              ) && (
                <button
                  type="button"
                  onClick={() => setIsCancelOpen(true)}
                  disabled={isActionInProgress}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-semibold text-rose-700 hover:text-rose-900 hover:bg-rose-50 border border-rose-200 rounded transition-colors"
                >
                  <OctagonX className="w-3.5 h-3.5 text-rose-600" />
                  <span>Cancel</span>
                </button>
              )}
            </div>

            {/* Explanatory notes on in-flight transitions */}
            {workflow.pause_requested_at && workflow.status === "running" && (
              <span className="text-xs text-amber-700 flex items-center gap-1">
                <Info className="w-3.5 h-3.5 shrink-0" />
                <span>Pause will take effect after current step finishes.</span>
              </span>
            )}

            {workflow.cancel_requested_at && workflow.status === "cancelling" && (
              <span className="text-xs text-orange-700 flex items-center gap-1">
                <Loader2 className="w-3.5 h-3.5 animate-spin shrink-0" />
                <span>Cancellation in progress...</span>
              </span>
            )}

            {canRetryWorkflow(workflow.status) && (
              <span className="text-[11px] text-slate-500">
                Retrying uses the same pinned Runtime & Content Version.
              </span>
            )}
          </div>
        )}

        {/* Global Error Banner */}
        {actionError && (
          <div className="mx-6 mt-4 p-3 bg-rose-50 border border-rose-200 rounded-lg text-xs text-rose-800 flex items-center gap-2 shrink-0">
            <AlertCircle className="w-4 h-4 text-rose-600 shrink-0" />
            <span>{actionError}</span>
          </div>
        )}

        {/* Body & Tabs */}
        <div className="flex-1 overflow-y-auto p-6 space-y-5">
          {isLoading && !workflow ? (
            <div className="py-16 flex flex-col items-center justify-center text-slate-400 gap-2">
              <Loader2 className="w-6 h-6 animate-spin text-rose-600" />
              <span className="text-xs">Loading workflow state...</span>
            </div>
          ) : workflow ? (
            <>
              {/* Failure Error Callout if workflow is in failed state */}
              {workflow.error_code && (
                <div className="p-4 bg-rose-50 border border-rose-200 rounded-lg text-xs text-rose-900 space-y-1">
                  <div className="flex items-center gap-2 font-bold text-rose-800">
                    <AlertCircle className="w-4 h-4 text-rose-600 shrink-0" />
                    <span>Workflow Failure: [{workflow.error_code}]</span>
                  </div>
                  <p className="text-rose-700">
                    {getWorkflowErrorMessage(
                      workflow.error_code,
                      workflow.error_message
                    )}
                  </p>
                </div>
              )}

              {/* Bound Metadata Summary Cards */}
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                {/* Target Runtime */}
                <div className="p-3 bg-slate-50 border border-slate-200 rounded-lg space-y-1">
                  <span className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider block">
                    Target Runtime
                  </span>
                  <div className="flex items-center gap-1.5 text-xs font-semibold text-slate-800">
                    <Cpu className="w-4 h-4 text-slate-500" />
                    <span>
                      {targetDevice?.name || `Runtime #${workflow.runtime_id_snapshot}`}
                    </span>
                  </div>
                  <div className="text-[11px] text-slate-500 font-mono">
                    ID #{workflow.runtime_id_snapshot}{" "}
                    {targetRuntime?.status ? `(${targetRuntime.status})` : ""}
                  </div>
                </div>

                {/* Pinned Content Asset */}
                <div className="p-3 bg-slate-50 border border-slate-200 rounded-lg space-y-1">
                  <span className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider block">
                    Pinned Content Version
                  </span>
                  <div className="flex items-center gap-1.5 text-xs font-semibold text-slate-800 truncate">
                    <FileBox className="w-4 h-4 text-purple-500 shrink-0" />
                    <span className="truncate">
                      {targetContent?.display_name || `Asset #${workflow.content_asset_id}`}
                    </span>
                  </div>
                  <div className="text-[11px] text-slate-500 font-mono">
                    Asset #{workflow.content_asset_id} • v{workflow.content_asset_version_id}
                  </div>
                </div>

                {/* Timings */}
                <div className="p-3 bg-slate-50 border border-slate-200 rounded-lg space-y-1">
                  <span className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider block">
                    Execution Time
                  </span>
                  <div className="flex items-center gap-1.5 text-xs font-semibold text-slate-800">
                    <Clock className="w-4 h-4 text-slate-500" />
                    <span>
                      {formatWorkflowDuration(
                        workflow.started_at,
                        workflow.completed_at
                      ) || "Not started"}
                    </span>
                  </div>
                  <div className="text-[11px] text-slate-500 font-mono">
                    Created {new Date(workflow.created_at).toLocaleTimeString()}
                  </div>
                </div>
              </div>

              {/* Tab Navigation */}
              <div className="flex items-center gap-4 border-b border-slate-200 text-xs font-medium">
                <button
                  type="button"
                  onClick={() => setActiveTab("steps")}
                  className={`pb-2 transition-colors border-b-2 ${
                    activeTab === "steps"
                      ? "border-rose-600 text-rose-600 font-semibold"
                      : "border-transparent text-slate-500 hover:text-slate-700"
                  }`}
                >
                  Execution Steps ({workflow.steps.length})
                </button>
                <button
                  type="button"
                  onClick={() => setActiveTab("events")}
                  className={`pb-2 transition-colors border-b-2 ${
                    activeTab === "events"
                      ? "border-rose-600 text-rose-600 font-semibold"
                      : "border-transparent text-slate-500 hover:text-slate-700"
                  }`}
                >
                  Event Audit History
                </button>
                <button
                  type="button"
                  onClick={() => setActiveTab("config")}
                  className={`pb-2 transition-colors border-b-2 ${
                    activeTab === "config"
                      ? "border-rose-600 text-rose-600 font-semibold"
                      : "border-transparent text-slate-500 hover:text-slate-700"
                  }`}
                >
                  Configuration & Parameters
                </button>
              </div>

              {/* Tab Content */}
              {activeTab === "steps" && (
                <WorkflowStepTimeline
                  workflow={workflow}
                  onViewJob={onViewJob}
                  onApprove={handleApproveStep}
                  onReject={handleRejectStep}
                  isActionInProgress={isActionInProgress}
                />
              )}

              {activeTab === "events" && (
                <WorkflowEventTimeline
                  workflowId={workflow.id}
                  onViewJob={onViewJob}
                />
              )}

              {activeTab === "config" && (
                <div className="p-4 bg-slate-50 border border-slate-200 rounded-lg space-y-4 text-xs">
                  <div>
                    <h4 className="font-semibold text-slate-800 mb-1">
                      Template & Version
                    </h4>
                    <p className="font-mono text-slate-600">
                      {workflow.template_key} (version {workflow.template_version})
                    </p>
                  </div>

                  <div>
                    <h4 className="font-semibold text-slate-800 mb-1">
                      Parameters
                    </h4>
                    <div className="bg-white border border-slate-200 rounded p-3 font-mono text-[11px] text-slate-700 space-y-1">
                      {Object.keys(workflow.parameters || {}).length > 0 ? (
                        Object.entries(workflow.parameters).map(([key, value]) => (
                          <div key={key} className="flex justify-between">
                            <span className="text-slate-500">{key}:</span>
                            <span className="font-semibold">{String(value)}</span>
                          </div>
                        ))
                      ) : (
                        <span className="text-slate-400">No custom parameters</span>
                      )}
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-4 pt-2 border-t border-slate-200">
                    <div>
                      <span className="text-slate-500 block">Created At:</span>
                      <span className="font-mono">
                        {new Date(workflow.created_at).toLocaleString()}
                      </span>
                    </div>
                    <div>
                      <span className="text-slate-500 block">Last Updated:</span>
                      <span className="font-mono">
                        {new Date(workflow.updated_at).toLocaleString()}
                      </span>
                    </div>
                    {workflow.started_at && (
                      <div>
                        <span className="text-slate-500 block">Started At:</span>
                        <span className="font-mono">
                          {new Date(workflow.started_at).toLocaleString()}
                        </span>
                      </div>
                    )}
                    {workflow.completed_at && (
                      <div>
                        <span className="text-slate-500 block">Completed At:</span>
                        <span className="font-mono">
                          {new Date(workflow.completed_at).toLocaleString()}
                        </span>
                      </div>
                    )}
                    {workflow.cancelled_at && (
                      <div>
                        <span className="text-slate-500 block">Cancelled At:</span>
                        <span className="font-mono">
                          {new Date(workflow.cancelled_at).toLocaleString()}
                        </span>
                      </div>
                    )}
                  </div>
                </div>
              )}
            </>
          ) : null}
        </div>
      </div>

      {/* Cancel Confirmation Modal */}
      <WorkflowCancelModal
        workflow={workflow}
        isOpen={isCancelOpen}
        isCancelling={isCancelling}
        onConfirm={handleConfirmCancel}
        onClose={() => setIsCancelOpen(false)}
      />
    </div>
  );
}

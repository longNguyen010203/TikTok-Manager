import React from "react";
import {
  Cpu,
  Eye,
  FileBox,
  OctagonX,
  PauseCircle,
  PlayCircle,
  RotateCcw,
  UserCheck,
} from "lucide-react";
import {
  Workflow,
  canCancelWorkflow,
  canPauseWorkflow,
  canResumeWorkflow,
  canRetryWorkflow,
  canStartWorkflow,
  getWorkflowStepLabel,
} from "@/types/workflow";
import { Runtime } from "@/types/runtime";
import { Device } from "@/types/device";
import { ContentAsset } from "@/types/content";
import { WorkflowStatusBadge } from "./WorkflowStatusBadge";

interface WorkflowTableProps {
  workflows: Workflow[];
  runtimesMap: Record<number, Runtime>;
  devicesMap: Record<number, Device>;
  contentAssetsMap: Record<number, ContentAsset>;
  onSelectWorkflow: (workflow: Workflow) => void;
  onStartWorkflow?: (workflow: Workflow) => void;
  onPauseWorkflow?: (workflow: Workflow) => void;
  onResumeWorkflow?: (workflow: Workflow) => void;
  onCancelWorkflow?: (workflow: Workflow) => void;
  onRetryWorkflow?: (workflow: Workflow) => void;
  isLoading: boolean;
}

export function WorkflowTable({
  workflows,
  runtimesMap,
  devicesMap,
  contentAssetsMap,
  onSelectWorkflow,
  onStartWorkflow,
  onPauseWorkflow,
  onResumeWorkflow,
  onCancelWorkflow,
  onRetryWorkflow,
  isLoading,
}: WorkflowTableProps) {
  if (workflows.length === 0 && !isLoading) {
    return null;
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left border-collapse">
        <thead>
          <tr className="border-b border-slate-200 bg-slate-50/80 text-[11px] font-semibold text-slate-500 uppercase tracking-wider">
            <th className="py-3 px-4">Workflow</th>
            <th className="py-3 px-4">Template</th>
            <th className="py-3 px-4">Status</th>
            <th className="py-3 px-4">Target Runtime</th>
            <th className="py-3 px-4">Pinned Content</th>
            <th className="py-3 px-4">Current Step</th>
            <th className="py-3 px-4">Created / Active</th>
            <th className="py-3 px-4 text-right">Actions</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100 text-xs">
          {workflows.map((wf) => {
            const rt = runtimesMap[wf.runtime_id_snapshot];
            const dev = rt ? devicesMap[rt.device_id] : null;
            const content = contentAssetsMap[wf.content_asset_id];

            const currentStep = wf.steps.find((s) => s.id === wf.current_step_id);
            const currentStepLabel = currentStep
              ? getWorkflowStepLabel(currentStep.step_type, currentStep.step_key)
              : wf.status === "succeeded"
              ? "All steps completed"
              : "Pending start";

            const isAwaitingApproval =
              currentStep?.step_type === "workflow.approval" &&
              currentStep?.status === "waiting";

            return (
              <tr
                key={wf.id}
                onClick={() => onSelectWorkflow(wf)}
                className={`group cursor-pointer transition-colors ${
                  isAwaitingApproval
                    ? "bg-amber-50/40 hover:bg-amber-50/70"
                    : "hover:bg-slate-50/80"
                }`}
              >
                {/* Workflow Name & ID */}
                <td className="py-3.5 px-4">
                  <div className="flex items-center gap-2">
                    <div>
                      <div className="font-semibold text-slate-900 group-hover:text-rose-600 transition-colors flex items-center gap-1.5">
                        <span>{wf.name}</span>
                        {isAwaitingApproval && (
                          <span className="inline-flex items-center gap-1 text-[10px] font-semibold px-2 py-0.5 rounded-full bg-amber-100 text-amber-800 border border-amber-300">
                            <UserCheck className="w-3 h-3 text-amber-600" />
                            <span>Needs Approval</span>
                          </span>
                        )}
                      </div>
                      <div className="text-[11px] font-mono text-slate-400 mt-0.5">
                        ID #{wf.id}
                      </div>
                    </div>
                  </div>
                </td>

                {/* Template */}
                <td className="py-3.5 px-4 font-mono text-[11px] text-slate-600">
                  <span className="px-2 py-0.5 rounded bg-slate-100 border border-slate-200">
                    {wf.template_key}:v{wf.template_version}
                  </span>
                </td>

                {/* Status Badge */}
                <td className="py-3.5 px-4 whitespace-nowrap">
                  <WorkflowStatusBadge
                    status={wf.status}
                    waitingReason={currentStep?.waiting_reason}
                    size="sm"
                  />
                </td>

                {/* Target Runtime */}
                <td className="py-3.5 px-4">
                  <div className="flex items-center gap-1.5">
                    <Cpu className="w-3.5 h-3.5 text-slate-400 shrink-0" />
                    <div>
                      <div className="font-medium text-slate-800">
                        {dev?.name || `Runtime #${wf.runtime_id_snapshot}`}
                      </div>
                      <div className="text-[11px] text-slate-500 font-mono">
                        {rt?.status || "offline"}{" "}
                        {rt?.adb_serial ? `• ${rt.adb_serial}` : ""}
                      </div>
                    </div>
                  </div>
                </td>

                {/* Pinned Content */}
                <td className="py-3.5 px-4">
                  <div className="flex items-center gap-1.5">
                    <FileBox className="w-3.5 h-3.5 text-purple-500 shrink-0" />
                    <div>
                      <div className="font-medium text-slate-800 truncate max-w-[140px]">
                        {content?.display_name || `Asset #${wf.content_asset_id}`}
                      </div>
                      <div className="text-[11px] text-slate-500 font-mono">
                        v{wf.content_asset_version_id} ({content?.asset_type || "media"})
                      </div>
                    </div>
                  </div>
                </td>

                {/* Current Step */}
                <td className="py-3.5 px-4">
                  <div>
                    <div className="font-medium text-slate-800 flex items-center gap-1.5">
                      <span>{currentStepLabel}</span>
                    </div>
                    {currentStep && (
                      <div className="text-[11px] text-slate-500 font-mono">
                        Step {currentStep.step_index + 1} of {wf.steps.length} • {currentStep.status}
                      </div>
                    )}
                  </div>
                </td>

                {/* Timings */}
                <td className="py-3.5 px-4 whitespace-nowrap">
                  <div className="text-slate-700">
                    {new Date(wf.created_at).toLocaleDateString()}
                  </div>
                  <div className="text-[11px] text-slate-400 font-mono">
                    {new Date(wf.created_at).toLocaleTimeString()}
                  </div>
                </td>

                {/* Actions */}
                <td
                  className="py-3.5 px-4 text-right whitespace-nowrap"
                  onClick={(e) => e.stopPropagation()}
                >
                  <div className="flex items-center justify-end gap-1.5">
                    {/* Start */}
                    {canStartWorkflow(wf.status) && onStartWorkflow && (
                      <button
                        type="button"
                        onClick={() => onStartWorkflow(wf)}
                        className="p-1.5 rounded-md text-sky-600 hover:bg-sky-50 transition-colors"
                        title="Start Workflow"
                      >
                        <PlayCircle className="w-4 h-4" />
                      </button>
                    )}

                    {/* Pause */}
                    {canPauseWorkflow(wf.status, wf.pause_requested_at) &&
                      onPauseWorkflow && (
                        <button
                          type="button"
                          onClick={() => onPauseWorkflow(wf)}
                          className="p-1.5 rounded-md text-amber-600 hover:bg-amber-50 transition-colors"
                          title="Pause Workflow"
                        >
                          <PauseCircle className="w-4 h-4" />
                        </button>
                      )}

                    {/* Resume */}
                    {canResumeWorkflow(wf.status) && onResumeWorkflow && (
                      <button
                        type="button"
                        onClick={() => onResumeWorkflow(wf)}
                        className="p-1.5 rounded-md text-emerald-600 hover:bg-emerald-50 transition-colors"
                        title="Resume Workflow"
                      >
                        <PlayCircle className="w-4 h-4" />
                      </button>
                    )}

                    {/* Retry */}
                    {canRetryWorkflow(wf.status) && onRetryWorkflow && (
                      <button
                        type="button"
                        onClick={() => onRetryWorkflow(wf)}
                        className="p-1.5 rounded-md text-purple-600 hover:bg-purple-50 transition-colors"
                        title="Retry Workflow"
                      >
                        <RotateCcw className="w-4 h-4" />
                      </button>
                    )}

                    {/* Cancel */}
                    {canCancelWorkflow(wf.status, wf.cancel_requested_at) &&
                      onCancelWorkflow && (
                        <button
                          type="button"
                          onClick={() => onCancelWorkflow(wf)}
                          className="p-1.5 rounded-md text-rose-500 hover:bg-rose-50 transition-colors"
                          title="Cancel Workflow"
                        >
                          <OctagonX className="w-4 h-4" />
                        </button>
                      )}

                    {/* Open Detail View */}
                    <button
                      type="button"
                      onClick={() => onSelectWorkflow(wf)}
                      className="p-1.5 rounded-md text-slate-500 hover:bg-slate-100 hover:text-slate-800 transition-colors"
                      title="View Details"
                    >
                      <Eye className="w-4 h-4" />
                    </button>
                  </div>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

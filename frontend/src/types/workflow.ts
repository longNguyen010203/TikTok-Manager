/**
 * Types for Workflows matching backend schemas and contracts (TIK-022).
 */

export type WorkflowStatus =
  | "draft"
  | "pending"
  | "running"
  | "waiting"
  | "paused"
  | "succeeded"
  | "failed"
  | "cancelling"
  | "cancelled";

export type WorkflowStepStatus =
  | "pending"
  | "running"
  | "waiting"
  | "succeeded"
  | "failed"
  | "cancelled";

export type WorkflowStepType =
  | "content.deliver"
  | "workflow.wait"
  | "workflow.approval"
  | string;

export interface WorkflowTemplate {
  key: string;
  version: number;
  label: string;
  description: string;
  required_bindings: string[];
  parameters_schema: {
    title?: string;
    type?: string;
    required?: string[];
    properties?: Record<
      string,
      {
        title?: string;
        type?: string;
        default?: unknown;
        minimum?: number;
        maximum?: number;
        description?: string;
      }
    >;
    additionalProperties?: boolean;
  };
}

export interface WorkflowStep {
  id: number;
  step_index: number;
  step_key: string;
  step_type: WorkflowStepType;
  status: WorkflowStepStatus;
  depends_on_step_id: number | null;
  job_id: number | null;
  attempt: number;
  max_attempts: number;
  result_json: Record<string, unknown> | null;
  resume_at: string | null;
  waiting_reason: string | null;
  approval_decision: "approved" | "rejected" | string | null;
  approval_at: string | null;
  approval_actor: string | null;
  approval_comment: string | null;
  started_at: string | null;
  completed_at: string | null;
  error_code: string | null;
  error_message: string | null;
}

export interface Workflow {
  id: number;
  name: string;
  description: string | null;
  template_key: string;
  template_version: number;
  status: WorkflowStatus;
  parameters: Record<string, unknown>;
  account_id: number | null;
  runtime_id: number | null;
  runtime_id_snapshot: number;
  content_asset_id: number;
  content_asset_version_id: number;
  current_step_id: number | null;
  pause_requested_at: string | null;
  cancel_requested_at: string | null;
  created_at: string;
  updated_at: string;
  started_at: string | null;
  completed_at: string | null;
  cancelled_at: string | null;
  error_code: string | null;
  error_message: string | null;
  steps: WorkflowStep[];
}

export interface WorkflowEvent {
  id: number;
  workflow_id: number;
  workflow_step_id: number | null;
  job_id: number | null;
  event_type: string;
  metadata: Record<string, unknown>;
  created_at: string;
}

export interface WorkflowCreateInput {
  template_key: string;
  template_version?: number | null;
  name: string;
  description?: string | null;
  runtime_id: number;
  content_asset_id: number;
  content_asset_version_id?: number | null;
  account_id?: number | null;
  parameters?: Record<string, unknown>;
  idempotency_key?: string | null;
}

export interface WorkflowApprovalInput {
  actor: string;
  comment?: string | null;
}

export interface WorkflowListParams {
  status?: string;
  template?: string;
  runtime_id?: number;
  account_id?: number;
  content_asset_id?: number;
  page?: number;
  page_size?: number;
}

export interface WorkflowListResponse {
  items: Workflow[];
  total: number;
  page: number;
  page_size: number;
}

export interface WorkflowEventListResponse {
  items: WorkflowEvent[];
  total: number;
  page: number;
  page_size: number;
}

/**
 * Friendly display labels for step types
 */
export function getWorkflowStepLabel(stepType: string, stepKey?: string): string {
  switch (stepType) {
    case "content.deliver":
      return "Deliver Content";
    case "workflow.wait":
      return "Wait";
    case "workflow.approval":
      return "Approval";
    default:
      if (stepKey) {
        return stepKey
          .split("_")
          .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
          .join(" ");
      }
      return stepType;
  }
}

/**
 * Friendly display labels for workflow events
 */
export function getWorkflowEventLabel(eventType: string): string {
  switch (eventType) {
    case "workflow_created":
      return "Workflow created";
    case "workflow_started":
      return "Workflow started";
    case "step_ready":
      return "Step ready";
    case "job_created":
      return "Job created";
    case "step_started":
      return "Step started";
    case "step_succeeded":
      return "Step succeeded";
    case "step_failed":
      return "Step failed";
    case "step_cancelled":
      return "Step cancelled";
    case "waiting":
      return "Waiting";
    case "waiting_for_approval":
      return "Waiting for approval";
    case "approved":
      return "Approved";
    case "rejected":
      return "Rejected";
    case "pause_requested":
      return "Pause requested";
    case "paused":
      return "Paused";
    case "resumed":
      return "Resumed";
    case "retry_requested":
      return "Retry requested";
    case "cancellation_requested":
      return "Cancellation requested";
    case "workflow_succeeded":
      return "Workflow succeeded";
    case "workflow_failed":
      return "Workflow failed";
    case "workflow_cancelled":
      return "Workflow cancelled";
    default:
      return eventType
        .split("_")
        .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
        .join(" ");
  }
}

/**
 * Friendly error messages mapping
 */
export const WORKFLOW_ERROR_MESSAGES: Record<string, string> = {
  WORKFLOW_RUNTIME_UNAVAILABLE: "Target runtime is unavailable or offline.",
  WORKFLOW_APPROVAL_REJECTED: "Workflow was rejected by operator.",
  WORKFLOW_JOB_CANCELLED: "Automation job was cancelled.",
  WORKFLOW_JOB_FAILED: "Underlying automation job failed.",
  WORKFLOW_BUSY: "Workflow is currently processing another operation. Please try again shortly.",
  RUNTIME_BUSY: "Target device is busy with another automation task.",
  RUNTIME_STOPPED: "Target runtime is currently stopped. Start the runtime before running workflow.",
  RUNTIME_SCREEN_ACTIVE: "A screen mirroring session is currently active on this device. Close the screen viewer before running workflow.",
  CONTENT_NOT_READY: "Selected content asset is not ready for delivery.",
  CONTENT_VERSION_NOT_READY: "Selected content version is not ready.",
  CONTENT_BLOB_MISSING: "Content media file is missing from storage.",
  CONTENT_BLOB_INVALID: "Content media file cannot be read or is invalid.",
  CONTENT_DELETED: "Selected content asset has been deleted.",
  CONTENT_NOT_FOUND: "Content asset not found.",
  RUNTIME_NOT_FOUND: "Target runtime was not found.",
  ACCOUNT_NOT_FOUND: "Associated account was not found.",
  ACCOUNT_RUNTIME_MISMATCH: "The selected account is not linked to this target runtime.",
  WORKFLOW_RETRY_UNAVAILABLE: "This workflow cannot be retried in its current state.",
  WORKFLOW_RETRY_EXHAUSTED: "Maximum retry attempts reached for this workflow.",
  WORKFLOW_APPROVAL_NOT_WAITING: "This workflow step is not currently awaiting approval.",
  WORKFLOW_IDEMPOTENCY_CONFLICT: "A submission conflict occurred with this request key. A fresh creation key has been generated; please review your settings and try again.",
  INVALID_WORKFLOW_COMMAND: "This action is not permitted for the workflow's current state.",
  INVALID_WORKFLOW_TRANSITION: "Invalid workflow state transition.",
  INVALID_WORKFLOW_PARAMETERS: "Provided workflow parameters do not match template schema.",
};

export function getWorkflowErrorMessage(
  code: string | null | undefined,
  fallback?: string | null
): string {
  if (code && WORKFLOW_ERROR_MESSAGES[code]) {
    return WORKFLOW_ERROR_MESSAGES[code];
  }
  if (fallback) {
    return fallback;
  }
  return "An unexpected workflow error occurred.";
}

/**
 * Check if workflow is in an active (non-terminal) state
 */
export function isWorkflowActive(status: WorkflowStatus): boolean {
  return (
    status === "pending" ||
    status === "running" ||
    status === "waiting" ||
    status === "cancelling"
  );
}

/**
 * Check if workflow can be started
 */
export function canStartWorkflow(status: WorkflowStatus): boolean {
  return status === "draft" || status === "pending";
}

/**
 * Check if workflow can be paused
 */
export function canPauseWorkflow(
  status: WorkflowStatus,
  pauseRequestedAt?: string | null
): boolean {
  if (pauseRequestedAt) return false;
  return status === "running" || status === "pending";
}

/**
 * Check if workflow can be resumed
 */
export function canResumeWorkflow(status: WorkflowStatus): boolean {
  return status === "paused";
}

/**
 * Check if workflow can be cancelled
 */
export function canCancelWorkflow(
  status: WorkflowStatus,
  cancelRequestedAt?: string | null
): boolean {
  if (cancelRequestedAt) return false;
  return (
    status === "draft" ||
    status === "pending" ||
    status === "running" ||
    status === "waiting" ||
    status === "paused"
  );
}

/**
 * Check if workflow can be retried
 */
export function canRetryWorkflow(status: WorkflowStatus): boolean {
  return status === "failed";
}

/**
 * Formats duration between two ISO timestamps
 */
export function formatWorkflowDuration(
  startedAt?: string | null,
  completedAt?: string | null
): string | null {
  if (!startedAt) return null;
  const start = new Date(startedAt).getTime();
  const end = completedAt ? new Date(completedAt).getTime() : Date.now();
  if (isNaN(start) || isNaN(end) || end < start) return null;
  const diffSec = Math.floor((end - start) / 1000);
  const minutes = Math.floor(diffSec / 60);
  const seconds = diffSec % 60;
  if (minutes === 0) return `${seconds}s`;
  return `${minutes}m ${seconds}s`;
}

import { ApiError, ValidationErrorDetail, formatApiError } from "./account";

export type JobStatus =
  | "pending"
  | "running"
  | "cancelling"
  | "succeeded"
  | "failed"
  | "retrying"
  | "cancelled";

export interface Job {
  id: number;
  job_type: string;
  status: JobStatus;
  account_id: number | null;
  runtime_id: number | null;
  payload: unknown | null;
  result: unknown | null;
  error_message: string | null;
  error_code?: string | null;
  error_retryable?: boolean | null;
  attempt_count: number;
  max_attempts: number;
  scheduled_at: string | null;
  started_at: string | null;
  completed_at: string | null;
  cancellation_requested_at?: string | null;
  execution_stage?: string | null;
  created_at: string;
  updated_at: string;
}

export interface JobListParams {
  page?: number;
  page_size?: number;
  status?: JobStatus;
  job_type?: string;
  account_id?: number;
  runtime_id?: number;
}

export interface JobListResponse {
  items: Job[];
  total: number;
  page: number;
  page_size: number;
}

export interface JobLog {
  id: number;
  job_id: number;
  level: string;
  event_type?: string | null;
  message: string;
  metadata: unknown | null;
  created_at: string;
}

export interface JobCreateInput {
  job_type: string;
  runtime_id?: number | null;
  account_id?: number | null;
  payload?: Record<string, unknown> | null;
}

export interface ArtifactMetadata {
  id: number;
  job_id?: number | null;
  kind: string;
  filename: string;
  mime_type: string;
  size_bytes: number;
  sha256: string;
}

export interface ScreenshotResult {
  runtime_id: number;
  artifact_id: number;
  kind: string;
  filename: string;
  mime_type: string;
  size_bytes: number;
  sha256: string;
  width: number;
  height: number;
}

export interface PackageStateResult {
  runtime_id: number;
  package_name: string;
  installed: boolean;
  running: boolean;
  pid?: number | null;
}

export interface FileTransferResult {
  runtime_id: number;
  artifact_id: number;
  remote_path: string;
  filename: string;
  size_bytes: number;
  sha256: string;
}

export interface MediaImportResult extends FileTransferResult {
  media_imported: boolean;
  media_uri?: string | null;
}

export const AUTOMATION_ACTION_TYPES = [
  {
    type: "device.screenshot",
    label: "Screenshot",
    description: "Capture the Android screen display to a PNG artifact",
  },
  {
    type: "device.package_state",
    label: "Check App State",
    description: "Inspect if an app package is installed and currently running",
  },
  {
    type: "device.launch_app",
    label: "Launch App",
    description: "Launch an Android app package and verify its running process",
  },
  {
    type: "device.stop_app",
    label: "Stop App",
    description: "Force-stop an active Android app package process",
  },
  {
    type: "device.push_file",
    label: "Push File",
    description: "Upload a file from your browser to the device manager folder",
  },
  {
    type: "device.pull_file",
    label: "Pull File",
    description: "Download a file from the device manager folder to your computer",
  },
  {
    type: "device.import_media",
    label: "Import Media",
    description: "Upload an image or video directly into the Android media library",
  },
] as const;

export function getJobActionLabel(jobType: string): string {
  const match = AUTOMATION_ACTION_TYPES.find((a) => a.type === jobType);
  if (match) return match.label;
  return jobType
    .replace(/[._]/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

export const AUTOMATION_ERROR_MESSAGES: Record<string, string> = {
  RUNTIME_NOT_FOUND: "Device runtime was not found.",
  RUNTIME_STOPPED: "This device is stopped. Automation will not start the device automatically.",
  RUNTIME_DEPROVISIONING: "Device runtime is being deprovisioned.",
  RUNTIME_BUSY: "This device is currently busy with another operation.",
  RUNTIME_SCREEN_ACTIVE: "Close the device screen before running automation.",
  DEVICE_NOT_READY: "Device is not ready for automation. Ensure it is fully booted.",
  ADB_UNAVAILABLE: "Android Debug Bridge connection is unavailable.",
  AUTOMATION_TIMEOUT: "The automation action timed out.",
  PACKAGE_NOT_FOUND: "The specified package is not installed on this device.",
  INVALID_AUTOMATION_PAYLOAD: "The automation parameters are invalid.",
  FILE_TRANSFER_FAILED: "File transfer operation failed.",
  MEDIA_IMPORT_FAILED: "Media import operation failed.",
  ARTIFACT_NOT_FOUND: "The requested artifact was not found.",
  ARTIFACT_POLICY_VIOLATION: "The file or path violates security policy.",
  AUTOMATION_CANCELLED: "Automation action was cancelled.",
};

export function getAutomationErrorMessage(
  code: string | null | undefined,
  fallback?: string | null
): string {
  if (code && AUTOMATION_ERROR_MESSAGES[code]) {
    return AUTOMATION_ERROR_MESSAGES[code];
  }
  return fallback || "An automation error occurred.";
}

export function getJobLogEventLabel(eventType: string | null | undefined): string {
  if (!eventType) return "Event";
  const map: Record<string, string> = {
    queued: "Queued",
    claim: "Worker claimed job",
    claim_acquired: "Worker claimed job",
    runtime_lock_acquired: "Device lock acquired",
    runtime_validated: "Runtime validated",
    adb_ready: "Device ready",
    device_ready: "Device ready",
    action_started: "Action started",
    artifact_created: "Artifact created",
    action_completed: "Action completed",
    retry_scheduled: "Retry scheduled",
    cancellation_requested: "Cancellation requested",
    cancelled: "Cancelled",
    failed: "Failed",
    succeeded: "Succeeded",
  };
  return (
    map[eventType] ||
    eventType.replace(/[._]/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())
  );
}

export { ApiError, formatApiError };
export type { ValidationErrorDetail };

/**
 * Runtime Managed Application & Readiness Types (TIK-023).
 */

export type RuntimeAppStatus =
  | "pending"
  | "installing"
  | "installed"
  | "failed"
  | "outdated"
  | "removed";

export interface RuntimeAppInstallation {
  id: number;
  runtime_id: number | null;
  runtime_id_snapshot: number;
  managed_app_id: number;
  desired_managed_app_version_id: number;
  observed_managed_app_version_id: number | null;
  status: RuntimeAppStatus;
  observed_package_name: string | null;
  observed_version_name: string | null;
  observed_version_code: number | null;
  observed_signer_fingerprint: string | null;
  latest_job_id: number | null;
  installed_at: string | null;
  verified_at: string | null;
  last_attempt_at: string | null;
  error_code: string | null;
  error_message: string | null;
  created_at: string;
  updated_at: string;
}

export interface RuntimeAppOperationRead {
  installation: RuntimeAppInstallation;
  job_id: number | null;
}

export interface RuntimeAppsRead {
  runtime_id: number;
  items: RuntimeAppInstallation[];
}

export interface PublishingReadiness {
  runtime_id: number;
  runtime_ready: boolean;
  required_apps_ready: boolean;
  publishing_ready: boolean;
  required_count: number;
  installed_count: number;
  pending_count: number;
  failed_count: number;
  outdated_count: number;
}

export interface RuntimeAppInstallRequest {
  managed_app_version_id?: number | null;
}

export const RUNTIME_APP_ERROR_MESSAGES: Record<string, string> = {
  RUNTIME_STOPPED: "Runtime is currently stopped. Start the runtime to install or verify applications.",
  RUNTIME_BUSY: "Runtime is currently busy with another operation.",
  APP_RUNTIME_UNAVAILABLE: "Runtime is unavailable for app management.",
  MANAGED_APP_NOT_FOUND: "Managed application was not found.",
  APP_NOT_INSTALLED: "Application is not installed on this runtime.",
  APP_VERSION_MISMATCH: "Observed app version differs from the desired version.",
  APP_PACKAGE_DISABLED: "Application package is disabled on the device.",
  APP_BASIC_UPDATE_REQUIRES_VERIFIED: "Updating this app requires a verified assurance level.",
};

export function getRuntimeAppErrorMessage(
  code: string | null | undefined,
  fallback?: string | null
): string {
  if (code && RUNTIME_APP_ERROR_MESSAGES[code]) {
    return RUNTIME_APP_ERROR_MESSAGES[code];
  }
  return fallback || "An unexpected error occurred while managing runtime applications.";
}

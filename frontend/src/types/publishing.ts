/**
 * Publishing Preparation Session Types (TIK-023).
 */

export type PublishingSessionStatus =
  | "preparing"
  | "waiting_approval"
  | "prepared"
  | "rejected"
  | "failed"
  | "cancelled";

export interface PublishingSession {
  id: number;
  workflow_id: number;
  account_id: number | null;
  account_id_snapshot: number;
  runtime_id: number | null;
  runtime_id_snapshot: number;
  content_asset_version_id: number;
  managed_app_id: number;
  managed_app_version_id: number;
  status: PublishingSessionStatus;
  created_at: string;
  updated_at: string;
  prepared_at: string | null;
  approved_at: string | null;
  error_code: string | null;
  error_message: string | null;
}

export interface PublishingSessionList {
  items: PublishingSession[];
  total: number;
  page: number;
  page_size: number;
}

export interface PublishingSessionListParams {
  status?: string;
  runtime_id?: number;
  account_id?: number;
  page?: number;
  page_size?: number;
}

export const PUBLISHING_SESSION_ERROR_MESSAGES: Record<string, string> = {
  PUBLISHING_SESSION_NOT_FOUND: "Publishing session was not found.",
  ACCOUNT_RUNTIME_MISMATCH: "Selected account is assigned to a different runtime.",
  ACCOUNT_REQUIRED: "Publishing preparation requires an account to be selected.",
  CONTENT_VERSION_REQUIRED: "Publishing preparation requires an exact content version.",
  MANAGED_APP_REQUIRED: "Publishing preparation requires an exact managed app version.",
  APP_NOT_FOUND: "The selected managed application was not found or is inactive.",
  APP_VERSION_NOT_READY: "The selected managed application version is not install-eligible.",
};

export function getPublishingSessionErrorMessage(
  code: string | null | undefined,
  fallback?: string | null
): string {
  if (code && PUBLISHING_SESSION_ERROR_MESSAGES[code]) {
    return PUBLISHING_SESSION_ERROR_MESSAGES[code];
  }
  return fallback || "An unexpected publishing preparation error occurred.";
}

/**
 * Runtime Network types matching docs/API_CONTRACT.md
 * and backend/app/schemas/runtime_network.py
 */

import { ApiError, ValidationErrorDetail } from "./runtime";

export type NetworkMode = "direct" | "http_proxy";

export type NetworkStatus =
  | "ready"
  | "degraded"
  | "failed"
  | "pending"
  | "disabled"
  | "applying"
  | string;

export type CheckStatus =
  | "ok"
  | "missing"
  | "failed"
  | "not_run"
  | "unknown"
  | "unmanaged"
  | "not_applicable"
  | string;

export interface NetworkCredentialsSummary {
  username_configured: boolean;
  password_configured: boolean;
}

export interface NetworkObservedSummary {
  mode: string;
  android_proxy_host: string | null;
  android_proxy_port: number | null;
  reverse_present: boolean | null;
  bridge_status: string;
  last_applied_at: string | null;
  last_verified_at: string | null;
}

export interface RuntimeNetworkResponse {
  runtime_id: number;
  managed: boolean;
  mode: NetworkMode | string;
  enabled: boolean;
  proxy_host: string | null;
  proxy_port: number | null;
  credentials: NetworkCredentialsSummary;
  desired_revision: number;
  applied_revision: number | null;
  status: NetworkStatus;
  observed: NetworkObservedSummary;
  error_code: string | null;
  error_message: string | null;
}

export interface NetworkChecks {
  runtime: CheckStatus;
  adb: CheckStatus;
  android_proxy: CheckStatus;
  adb_reverse: CheckStatus;
  bridge: CheckStatus;
  connectivity: CheckStatus;
}

export interface RuntimeNetworkStatusResponse {
  runtime_id: number;
  status: NetworkStatus;
  desired_revision: number;
  applied_revision: number | null;
  checks: NetworkChecks;
  last_applied_at: string | null;
  last_verified_at: string | null;
  error_code: string | null;
  error_message: string | null;
}

export interface RuntimeNetworkUpdateInput {
  mode: NetworkMode;
  proxy_host?: string | null;
  proxy_port?: number | null;
  proxy_username_secret_ref?: string | null;
  proxy_password_secret_ref?: string | null;
  expected_revision: number;
}

export class RuntimeNetworkApiError extends ApiError {
  isRevisionConflict?: boolean;
  isRuntimeStopped?: boolean;
  isLockBusy?: boolean;

  constructor(
    status: number,
    message: string,
    details?: ValidationErrorDetail[] | string
  ) {
    super(status, message, details);
    this.name = "RuntimeNetworkApiError";
    const lower = message.toLowerCase();
    this.isRevisionConflict = status === 409 && lower.includes("revision conflict");
    this.isRuntimeStopped =
      status === 409 && (lower.includes("stopped") || lower.includes("runtime is stopped"));
    this.isLockBusy = status === 409 && lower.includes("lock");
  }
}

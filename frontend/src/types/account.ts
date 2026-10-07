/**
 * Canonical Account Registry & Control Center Types (TIK-025).
 * Aligned with backend app/schemas/account.py and docs/TIK-025_ACCOUNT_REGISTRY.md.
 */

export type AccountStatus =
  | "pending"
  | "active"
  | "inactive"
  | "restricted"
  | "suspended"
  | "disabled"
  | "archived"
  | string;

export type RegistrationState = "unknown" | "pending" | "registered" | "failed";

export type AccountHealthStatus = "unknown" | "healthy" | "warning" | "unhealthy";

export type AccountSecretType =
  | "account_password"
  | "email_password"
  | "recovery_credential";

export interface AccountSecretMetadata {
  secret_type: AccountSecretType;
  present: boolean;
  updated_at: string | null;
}

export interface Account {
  id: number;
  name: string;
  display_name: string;
  username: string | null;
  email: string | null;
  phone: string | null;
  platform: string;
  status: AccountStatus;
  registration_state: RegistrationState;
  health_status: AccountHealthStatus;
  status_reason: string | null;
  niche: string | null;
  notes: string | null;
  tags: string[];
  runtime_id: number | null;
  device_id: number | null;
  follower_count: number | null;
  following_count: number | null;
  likes_count: number | null;
  video_count: number | null;
  metrics_updated_at: string | null;
  secret_present: boolean;
  secret_types: AccountSecretType[];
  created_at: string;
  updated_at: string;
  archived_at: string | null;
}

export interface AccountListParams {
  page?: number;
  page_size?: number;
  status?: string;
  niche?: string;
  runtime_id?: number;
  device_id?: number;
  tag?: string;
  query?: string;
  include_archived?: boolean;
  // Backward compatibility alias for query
  search?: string;
}

export interface AccountListResponse {
  items: Account[];
  total: number;
  page: number;
  page_size: number;
}

export interface CreateAccountInput {
  display_name: string;
  name?: string;
  username?: string | null;
  email?: string | null;
  phone?: string | null;
  platform?: string;
  status?: AccountStatus;
  registration_state?: RegistrationState;
  health_status?: AccountHealthStatus;
  status_reason?: string | null;
  niche?: string | null;
  notes?: string | null;
  tags?: string[];
  runtime_id?: number | null;
  follower_count?: number | null;
  following_count?: number | null;
  likes_count?: number | null;
  video_count?: number | null;
}

export interface UpdateAccountInput {
  display_name?: string;
  name?: string;
  username?: string | null;
  email?: string | null;
  phone?: string | null;
  platform?: string;
  status?: AccountStatus;
  registration_state?: RegistrationState;
  health_status?: AccountHealthStatus;
  status_reason?: string | null;
  niche?: string | null;
  notes?: string | null;
  tags?: string[];
  runtime_id?: number | null;
  follower_count?: number | null;
  following_count?: number | null;
  likes_count?: number | null;
  video_count?: number | null;
}

export interface ValidationErrorDetail {
  loc?: (string | number)[];
  msg?: string;
  type?: string;
}

export class ApiError extends Error {
  status: number;
  details?: ValidationErrorDetail[] | string;
  code?: string;

  constructor(
    status: number,
    message: string,
    details?: ValidationErrorDetail[] | string,
    code?: string
  ) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.details = details;
    this.code = code;
  }
}

export function formatApiError(err: unknown): string {
  if (err instanceof ApiError) {
    if (err.status === 422 && Array.isArray(err.details)) {
      return err.details
        .map((d) => {
          const loc = d.loc && d.loc.length > 1 ? d.loc.slice(1).join(".") : "field";
          return `${loc}: ${d.msg || "invalid value"}`;
        })
        .join("; ");
    }
    return err.message;
  }
  if (err instanceof Error) {
    return err.message;
  }
  return "An unexpected server error occurred.";
}

export function getSecretTypeLabel(type: AccountSecretType): string {
  switch (type) {
    case "account_password":
      return "Account Password";
    case "email_password":
      return "Email Password";
    case "recovery_credential":
      return "Recovery Credential";
    default:
      return type;
  }
}

export function getSecretTypeDescription(type: AccountSecretType): string {
  switch (type) {
    case "account_password":
      return "TikTok login password for automated or manual session sign-in.";
    case "email_password":
      return "Email account password used for recovery or 2FA verification inbox.";
    case "recovery_credential":
      return "Backup codes, recovery key, or phone PIN for security resets.";
    default:
      return "Encrypted security credential.";
  }
}

export function formatMetricNumber(num: number | null | undefined): string {
  if (num === null || num === undefined) return "—";
  if (num >= 1_000_000) {
    return `${(num / 1_000_000).toFixed(1).replace(/\.0$/, "")}M`;
  }
  if (num >= 1_000) {
    return `${(num / 1_000).toFixed(1).replace(/\.0$/, "")}K`;
  }
  return num.toLocaleString();
}

/**
 * Account types matching docs/API_CONTRACT.md
 */

export type AccountStatus = "active" | "inactive" | "suspended" | string;

export interface Account {
  id: number;
  name: string;
  username: string;
  platform: string;
  status: AccountStatus;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface AccountListParams {
  page?: number;
  page_size?: number;
  status?: string;
  search?: string;
}

export interface AccountListResponse {
  items: Account[];
  total: number;
  page: number;
  page_size: number;
}

export interface CreateAccountInput {
  name: string;
  username: string;
  platform: string;
  status: AccountStatus;
  notes?: string | null;
}

export interface UpdateAccountInput {
  name?: string;
  username?: string;
  platform?: string;
  status?: AccountStatus;
  notes?: string | null;
}

export interface ValidationErrorDetail {
  loc?: (string | number)[];
  msg?: string;
  type?: string;
}

export class ApiError extends Error {
  status: number;
  details?: ValidationErrorDetail[] | string;

  constructor(
    status: number,
    message: string,
    details?: ValidationErrorDetail[] | string
  ) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.details = details;
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

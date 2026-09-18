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

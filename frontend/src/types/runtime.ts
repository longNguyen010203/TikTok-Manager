/**
 * Runtime types matching docs/API_CONTRACT.md and backend/app/schemas/runtime.py
 */

import { ApiError, formatApiError, ValidationErrorDetail } from "./account";

export type RuntimeStatus = "running" | "idle" | "stopped" | "error" | string;
export type RuntimeType = "emulator" | "container" | "cloud" | string;

export interface Runtime {
  id: number;
  device_id: number;
  name: string;
  runtime_type: RuntimeType;
  status: RuntimeStatus;
  last_seen_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface RuntimeListParams {
  page?: number;
  page_size?: number;
}

export interface RuntimeListResponse {
  items: Runtime[];
  total: number;
  page: number;
  page_size: number;
}

export interface CreateRuntimeInput {
  device_id: number;
  name: string;
  runtime_type: string;
  status: string;
  last_seen_at?: string | null;
}

export interface UpdateRuntimeInput {
  device_id?: number;
  name?: string;
  runtime_type?: string;
  status?: string;
  last_seen_at?: string | null;
}

export { ApiError, formatApiError };
export type { ValidationErrorDetail };

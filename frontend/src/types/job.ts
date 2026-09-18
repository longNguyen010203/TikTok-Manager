import { ApiError, ValidationErrorDetail, formatApiError } from "./account";

export type JobStatus =
  | "pending"
  | "running"
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
  attempt_count: number;
  max_attempts: number;
  scheduled_at: string | null;
  started_at: string | null;
  completed_at: string | null;
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
  message: string;
  metadata: unknown | null;
  created_at: string;
}

export { ApiError, formatApiError };
export type { ValidationErrorDetail };

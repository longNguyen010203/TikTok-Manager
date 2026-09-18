import {
  ApiError,
  Job,
  JobLog,
  JobListParams,
  JobListResponse,
  ValidationErrorDetail,
} from "@/types/job";

export interface IJobService {
  getJobs(params?: JobListParams): Promise<JobListResponse>;
  getJob(id: number): Promise<Job>;
  getJobLogs(id: number): Promise<JobLog[]>;
  retryJob(id: number, scheduledAt?: string): Promise<Job>;
  cancelJob(id: number): Promise<Job>;
  getBaseUrl(): string;
}

export class FastApiJobService implements IJobService {
  private baseUrl: string;

  constructor(baseUrl?: string) {
    const rawUrl =
      baseUrl ||
      process.env.NEXT_PUBLIC_API_BASE_URL ||
      "http://127.0.0.1:8000";
    this.baseUrl = rawUrl.replace(/\/+$/, "");
  }

  public getBaseUrl(): string {
    return this.baseUrl;
  }

  private async parseError(response: Response): Promise<ApiError> {
    let detailData: { detail?: string | ValidationErrorDetail[] } | null = null;
    try {
      detailData = await response.json();
    } catch {
      // The response body is not JSON.
    }

    const detail = detailData?.detail;
    if (response.status === 422 && Array.isArray(detail)) {
      const formatted = detail
        .map((item) => {
          const location =
            item.loc && item.loc.length > 1
              ? item.loc.slice(1).join(".")
              : "field";
          return `${location}: ${item.msg || "Invalid value"}`;
        })
        .join("; ");
      return new ApiError(422, formatted || "Validation failed", detail);
    }

    const message =
      (typeof detail === "string" && detail) ||
      `Request failed with status ${response.status}: ${response.statusText}`;
    return new ApiError(response.status, message, detail);
  }

  async getJobs(params?: JobListParams): Promise<JobListResponse> {
    const url = new URL(`${this.baseUrl}/jobs`);
    const page = params?.page && params.page > 0 ? params.page : 1;
    const pageSize =
      params?.page_size && params.page_size > 0 ? params.page_size : 20;

    url.searchParams.set("page", page.toString());
    url.searchParams.set("page_size", pageSize.toString());

    if (params?.status) url.searchParams.set("status", params.status);
    if (params?.job_type?.trim()) {
      url.searchParams.set("job_type", params.job_type.trim());
    }
    if (params?.account_id) {
      url.searchParams.set("account_id", params.account_id.toString());
    }
    if (params?.runtime_id) {
      url.searchParams.set("runtime_id", params.runtime_id.toString());
    }

    const response = await fetch(url.toString(), {
      method: "GET",
      headers: { Accept: "application/json" },
    });

    if (!response.ok) throw await this.parseError(response);
    return (await response.json()) as JobListResponse;
  }

  async getJob(id: number): Promise<Job> {
    const response = await fetch(`${this.baseUrl}/jobs/${id}`, {
      method: "GET",
      headers: { Accept: "application/json" },
    });

    if (!response.ok) throw await this.parseError(response);
    return (await response.json()) as Job;
  }

  async getJobLogs(id: number): Promise<JobLog[]> {
    const response = await fetch(`${this.baseUrl}/jobs/${id}/logs`, {
      method: "GET",
      headers: { Accept: "application/json" },
    });

    if (!response.ok) throw await this.parseError(response);
    return (await response.json()) as JobLog[];
  }

  async retryJob(id: number, scheduledAt?: string): Promise<Job> {
    const response = await fetch(`${this.baseUrl}/jobs/${id}/retry`, {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
      },
      body: JSON.stringify(scheduledAt ? { scheduled_at: scheduledAt } : {}),
    });

    if (!response.ok) throw await this.parseError(response);
    return (await response.json()) as Job;
  }

  async cancelJob(id: number): Promise<Job> {
    const response = await fetch(`${this.baseUrl}/jobs/${id}/cancel`, {
      method: "POST",
      headers: { Accept: "application/json" },
    });

    if (!response.ok) throw await this.parseError(response);
    return (await response.json()) as Job;
  }
}

export const jobService: IJobService = new FastApiJobService();

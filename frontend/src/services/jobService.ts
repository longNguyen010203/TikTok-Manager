import {
  ApiError,
  ArtifactMetadata,
  Job,
  JobCreateInput,
  JobLog,
  JobListParams,
  JobListResponse,
  ValidationErrorDetail,
  getAutomationErrorMessage,
} from "@/types/job";

export interface IJobService {
  getJobs(params?: JobListParams): Promise<JobListResponse>;
  getJob(id: number): Promise<Job>;
  getJobLogs(id: number): Promise<JobLog[]>;
  createJob(input: JobCreateInput): Promise<Job>;
  retryJob(id: number, scheduledAt?: string): Promise<Job>;
  cancelJob(id: number): Promise<Job>;
  uploadArtifact(file: File): Promise<ArtifactMetadata>;
  getArtifactDownloadUrl(jobId: number, artifactId: number): string;
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
    let detailData: {
      detail?: string | ValidationErrorDetail[] | Record<string, unknown>;
    } | null = null;
    try {
      detailData = await response.json();
    } catch {
      // The response body is not JSON.
    }

    const detail = detailData?.detail;
    let message = "";
    let code: string | undefined = undefined;

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

    if (
      typeof detail === "object" &&
      detail !== null &&
      !Array.isArray(detail)
    ) {
      const obj = detail as Record<string, unknown>;
      if (typeof obj.code === "string") {
        code = obj.code;
      }
      if (typeof obj.message === "string") {
        message = obj.message;
      }
    } else if (typeof detail === "string" && detail) {
      message = detail;
    } else {
      message = `Request failed with status ${response.status}: ${response.statusText}`;
    }

    // Sanitize raw execution traces, internal lock paths, tokens
    if (
      message.includes("Traceback") ||
      message.includes("subprocess.CalledProcessError") ||
      message.includes("RuntimeOperationLock") ||
      message.includes("X-Job-Claim-Token") ||
      message.includes("ClaimToken")
    ) {
      message = "Automation operation failed unexpectedly";
    }

    // Map error code to product-friendly message if known
    if (code) {
      message = getAutomationErrorMessage(code, message);
    }

    return new ApiError(
      response.status,
      message,
      typeof detail === "string" ? detail : undefined
    );
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

  async createJob(input: JobCreateInput): Promise<Job> {
    const payload = {
      job_type: input.job_type,
      runtime_id: input.runtime_id ?? null,
      account_id: input.account_id ?? null,
      payload: input.payload ?? null,
    };

    const response = await fetch(`${this.baseUrl}/jobs`, {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
    });

    if (!response.ok) throw await this.parseError(response);
    return (await response.json()) as Job;
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

  async uploadArtifact(file: File): Promise<ArtifactMetadata> {
    const formData = new FormData();
    formData.append("file", file, file.name);

    const response = await fetch(`${this.baseUrl}/artifacts`, {
      method: "POST",
      body: formData,
    });

    if (!response.ok) throw await this.parseError(response);
    return (await response.json()) as ArtifactMetadata;
  }

  getArtifactDownloadUrl(jobId: number, artifactId: number): string {
    return `${this.baseUrl}/jobs/${jobId}/artifacts/${artifactId}`;
  }
}

export const jobService: IJobService = new FastApiJobService();

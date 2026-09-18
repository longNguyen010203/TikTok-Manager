import {
  Runtime,
  RuntimeListParams,
  RuntimeListResponse,
  CreateRuntimeInput,
  UpdateRuntimeInput,
  ApiError,
  ValidationErrorDetail,
} from "@/types/runtime";

export interface IRuntimeService {
  getRuntimes(params?: RuntimeListParams): Promise<RuntimeListResponse>;
  getRuntime(id: number): Promise<Runtime>;
  createRuntime(input: CreateRuntimeInput): Promise<Runtime>;
  updateRuntime(id: number, input: UpdateRuntimeInput): Promise<Runtime>;
  deleteRuntime(id: number): Promise<void>;
  getBaseUrl(): string;
}

/**
 * Real FastAPI backend client for Runtime endpoints (/runtimes)
 */
export class FastApiRuntimeService implements IRuntimeService {
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
      // Not JSON
    }

    const status = response.status;
    const detail = detailData?.detail;

    if (status === 404) {
      const msg = typeof detail === "string" ? detail : "Resource not found";
      return new ApiError(404, msg, detail);
    }

    if (status === 422) {
      if (Array.isArray(detail)) {
        const formatted = detail
          .map((item) => {
            const loc =
              item.loc && item.loc.length > 1
                ? item.loc.slice(1).join(".")
                : "field";
            return `${loc}: ${item.msg || "Invalid value"}`;
          })
          .join("; ");
        return new ApiError(422, formatted || "Validation failed", detail);
      }
      const msg = typeof detail === "string" ? detail : "Unprocessable entity";
      return new ApiError(422, msg, detail);
    }

    const fallbackMsg =
      (typeof detail === "string" && detail) ||
      `Request failed with status ${status}: ${response.statusText}`;
    return new ApiError(status, fallbackMsg, detail);
  }

  async getRuntimes(params?: RuntimeListParams): Promise<RuntimeListResponse> {
    const url = new URL(`${this.baseUrl}/runtimes`);

    const page = params?.page && params.page > 0 ? params.page : 1;
    const pageSize =
      params?.page_size && params.page_size > 0 ? params.page_size : 20;

    url.searchParams.set("page", page.toString());
    url.searchParams.set("page_size", pageSize.toString());

    const response = await fetch(url.toString(), {
      method: "GET",
      headers: {
        Accept: "application/json",
      },
    });

    if (!response.ok) {
      throw await this.parseError(response);
    }

    const data: RuntimeListResponse = await response.json();
    return data;
  }

  async getRuntime(id: number): Promise<Runtime> {
    const response = await fetch(`${this.baseUrl}/runtimes/${id}`, {
      method: "GET",
      headers: {
        Accept: "application/json",
      },
    });

    if (!response.ok) {
      throw await this.parseError(response);
    }

    const data: Runtime = await response.json();
    return data;
  }

  async createRuntime(input: CreateRuntimeInput): Promise<Runtime> {
    const payload = {
      device_id: Number(input.device_id),
      name: input.name.trim(),
      runtime_type: input.runtime_type.trim(),
      status: input.status.trim(),
      last_seen_at: input.last_seen_at || null,
    };

    const response = await fetch(`${this.baseUrl}/runtimes`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      throw await this.parseError(response);
    }

    const created: Runtime = await response.json();
    return created;
  }

  async updateRuntime(
    id: number,
    input: UpdateRuntimeInput
  ): Promise<Runtime> {
    const payload: Record<string, unknown> = {};

    if (input.device_id !== undefined)
      payload.device_id = Number(input.device_id);
    if (input.name !== undefined) payload.name = input.name.trim();
    if (input.runtime_type !== undefined)
      payload.runtime_type = input.runtime_type.trim();
    if (input.status !== undefined) payload.status = input.status.trim();
    if (input.last_seen_at !== undefined)
      payload.last_seen_at = input.last_seen_at;

    const response = await fetch(`${this.baseUrl}/runtimes/${id}`, {
      method: "PATCH",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      throw await this.parseError(response);
    }

    const updated: Runtime = await response.json();
    return updated;
  }

  async deleteRuntime(id: number): Promise<void> {
    const response = await fetch(`${this.baseUrl}/runtimes/${id}`, {
      method: "DELETE",
      headers: {
        Accept: "application/json",
      },
    });

    if (!response.ok) {
      throw await this.parseError(response);
    }
  }
}

export const runtimeService: IRuntimeService = new FastApiRuntimeService();

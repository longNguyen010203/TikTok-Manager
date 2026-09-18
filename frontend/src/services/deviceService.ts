import {
  Device,
  DeviceListParams,
  DeviceListResponse,
  CreateDeviceInput,
  UpdateDeviceInput,
  ApiError,
  ValidationErrorDetail,
} from "@/types/device";

export interface IDeviceService {
  getDevices(params?: DeviceListParams): Promise<DeviceListResponse>;
  getDevice(id: number): Promise<Device>;
  createDevice(input: CreateDeviceInput): Promise<Device>;
  updateDevice(id: number, input: UpdateDeviceInput): Promise<Device>;
  deleteDevice(id: number): Promise<void>;
  getBaseUrl(): string;
}

/**
 * Real FastAPI backend client for Device endpoints (/devices)
 */
export class FastApiDeviceService implements IDeviceService {
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
      const msg = typeof detail === "string" ? detail : "Device not found";
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

  async getDevices(params?: DeviceListParams): Promise<DeviceListResponse> {
    const url = new URL(`${this.baseUrl}/devices`);

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

    const data: DeviceListResponse = await response.json();
    return data;
  }

  async getDevice(id: number): Promise<Device> {
    const response = await fetch(`${this.baseUrl}/devices/${id}`, {
      method: "GET",
      headers: {
        Accept: "application/json",
      },
    });

    if (!response.ok) {
      throw await this.parseError(response);
    }

    const data: Device = await response.json();
    return data;
  }

  async createDevice(input: CreateDeviceInput): Promise<Device> {
    const payload = {
      name: input.name.trim(),
      device_type: input.device_type.trim(),
      platform: input.platform.trim(),
      os_version: input.os_version.trim(),
      status: input.status.trim(),
      notes: input.notes && input.notes.trim() ? input.notes.trim() : null,
    };

    const response = await fetch(`${this.baseUrl}/devices`, {
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

    const created: Device = await response.json();
    return created;
  }

  async updateDevice(
    id: number,
    input: UpdateDeviceInput
  ): Promise<Device> {
    const payload: Record<string, unknown> = {};

    if (input.name !== undefined) payload.name = input.name.trim();
    if (input.device_type !== undefined)
      payload.device_type = input.device_type.trim();
    if (input.platform !== undefined) payload.platform = input.platform.trim();
    if (input.os_version !== undefined)
      payload.os_version = input.os_version.trim();
    if (input.status !== undefined) payload.status = input.status.trim();
    if (input.notes !== undefined) {
      payload.notes =
        input.notes && input.notes.trim() ? input.notes.trim() : null;
    }

    const response = await fetch(`${this.baseUrl}/devices/${id}`, {
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

    const updated: Device = await response.json();
    return updated;
  }

  async deleteDevice(id: number): Promise<void> {
    const response = await fetch(`${this.baseUrl}/devices/${id}`, {
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

export const deviceService: IDeviceService = new FastApiDeviceService();

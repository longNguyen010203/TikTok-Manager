import { ApiError } from "@/types/account";
import {
  PublishingReadiness,
  RuntimeAppOperationRead,
  RuntimeAppsRead,
} from "@/types/runtimeApp";

class RuntimeAppService {
  private baseUrl: string;

  constructor() {
    this.baseUrl = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
  }

  getBaseUrl(): string {
    return this.baseUrl;
  }

  private async parseError(response: Response): Promise<ApiError> {
    let message = "";
    let code: string | undefined;

    try {
      const data = await response.json();
      const detail = data?.detail;

      if (typeof detail === "object" && detail !== null && !Array.isArray(detail)) {
        const obj = detail as Record<string, unknown>;
        if (typeof obj.code === "string") code = obj.code;
        if (typeof obj.message === "string") message = obj.message;
      } else if (typeof detail === "string") {
        message = detail;
      } else if (Array.isArray(detail)) {
        message = detail
          .map((item) => {
            const loc = item.loc && item.loc.length > 1 ? item.loc.slice(1).join(".") : "field";
            return `${loc}: ${item.msg || "Invalid value"}`;
          })
          .join("; ");
      }
    } catch {
      message = `Request failed with status ${response.status}: ${response.statusText}`;
    }

    if (!message) {
      message = `Request failed with status ${response.status}`;
    }

    return new ApiError(response.status, message, code);
  }

  async getRuntimeApps(runtimeId: number): Promise<RuntimeAppsRead> {
    const res = await fetch(`${this.baseUrl}/runtimes/${runtimeId}/apps`, {
      headers: { Accept: "application/json" },
    });
    if (!res.ok) throw await this.parseError(res);
    return res.json();
  }

  async getPublishingReadiness(runtimeId: number): Promise<PublishingReadiness> {
    const res = await fetch(`${this.baseUrl}/runtimes/${runtimeId}/publishing-readiness`, {
      headers: { Accept: "application/json" },
    });
    if (!res.ok) throw await this.parseError(res);
    return res.json();
  }

  async installApp(
    runtimeId: number,
    appId: number,
    versionId?: number | null
  ): Promise<RuntimeAppOperationRead> {
    const res = await fetch(`${this.baseUrl}/runtimes/${runtimeId}/apps/${appId}/install`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify({
        managed_app_version_id: versionId ?? null,
      }),
    });
    if (!res.ok) throw await this.parseError(res);
    return res.json();
  }

  async verifyApp(runtimeId: number, appId: number): Promise<RuntimeAppOperationRead> {
    const res = await fetch(`${this.baseUrl}/runtimes/${runtimeId}/apps/${appId}/verify`, {
      method: "POST",
      headers: { Accept: "application/json" },
    });
    if (!res.ok) throw await this.parseError(res);
    return res.json();
  }
}

export const runtimeAppService = new RuntimeAppService();

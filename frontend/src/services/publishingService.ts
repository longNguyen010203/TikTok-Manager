import { ApiError } from "@/types/account";
import {
  PublishingSession,
  PublishingSessionList,
  PublishingSessionListParams,
} from "@/types/publishing";

class PublishingService {
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

  async getPublishingSessions(
    params?: PublishingSessionListParams
  ): Promise<PublishingSessionList> {
    const query = new URLSearchParams();
    if (params?.status && params.status !== "all") query.set("status", params.status);
    if (params?.runtime_id) query.set("runtime_id", params.runtime_id.toString());
    if (params?.account_id) query.set("account_id", params.account_id.toString());
    if (params?.page) query.set("page", params.page.toString());
    if (params?.page_size) query.set("page_size", params.page_size.toString());

    const url = `${this.baseUrl}/publishing-sessions${
      query.toString() ? `?${query.toString()}` : ""
    }`;
    const res = await fetch(url, { headers: { Accept: "application/json" } });
    if (!res.ok) throw await this.parseError(res);
    return res.json();
  }

  async getPublishingSession(id: number): Promise<PublishingSession> {
    const res = await fetch(`${this.baseUrl}/publishing-sessions/${id}`, {
      headers: { Accept: "application/json" },
    });
    if (!res.ok) throw await this.parseError(res);
    return res.json();
  }
}

export const publishingService = new PublishingService();

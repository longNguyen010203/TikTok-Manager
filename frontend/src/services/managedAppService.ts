import { ApiError } from "@/types/account";
import {
  ManagedAppCreateInput,
  ManagedAppDetail,
  ManagedAppList,
  ManagedAppPatchInput,
  ManagedAppVersion,
  ManagedAppVersionList,
  ManagedAppVersionUploadResponse,
} from "@/types/managedApp";

class ManagedAppService {
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

  async getManagedApps(params?: { page?: number; page_size?: number }): Promise<ManagedAppList> {
    const query = new URLSearchParams();
    if (params?.page) query.set("page", params.page.toString());
    if (params?.page_size) query.set("page_size", params.page_size.toString());

    const url = `${this.baseUrl}/managed-apps${query.toString() ? `?${query.toString()}` : ""}`;
    const res = await fetch(url, { headers: { Accept: "application/json" } });
    if (!res.ok) throw await this.parseError(res);
    return res.json();
  }

  async getManagedApp(id: number): Promise<ManagedAppDetail> {
    const res = await fetch(`${this.baseUrl}/managed-apps/${id}`, {
      headers: { Accept: "application/json" },
    });
    if (!res.ok) throw await this.parseError(res);
    return res.json();
  }

  async createManagedApp(input: ManagedAppCreateInput): Promise<ManagedAppDetail> {
    const res = await fetch(`${this.baseUrl}/managed-apps`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify(input),
    });
    if (!res.ok) throw await this.parseError(res);
    return res.json();
  }

  async patchManagedApp(id: number, input: ManagedAppPatchInput): Promise<ManagedAppDetail> {
    const res = await fetch(`${this.baseUrl}/managed-apps/${id}`, {
      method: "PATCH",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify(input),
    });
    if (!res.ok) throw await this.parseError(res);
    return res.json();
  }

  async getVersions(
    appId: number,
    params?: { page?: number; page_size?: number }
  ): Promise<ManagedAppVersionList> {
    const query = new URLSearchParams();
    if (params?.page) query.set("page", params.page.toString());
    if (params?.page_size) query.set("page_size", params.page_size.toString());

    const url = `${this.baseUrl}/managed-apps/${appId}/versions${
      query.toString() ? `?${query.toString()}` : ""
    }`;
    const res = await fetch(url, { headers: { Accept: "application/json" } });
    if (!res.ok) throw await this.parseError(res);
    return res.json();
  }

  async getVersion(appId: number, versionId: number): Promise<ManagedAppVersion> {
    const res = await fetch(`${this.baseUrl}/managed-apps/${appId}/versions/${versionId}`, {
      headers: { Accept: "application/json" },
    });
    if (!res.ok) throw await this.parseError(res);
    return res.json();
  }

  async uploadVersion(
    appId: number,
    file: File,
    displayName?: string
  ): Promise<ManagedAppVersionUploadResponse> {
    const formData = new FormData();
    formData.append("file", file);
    if (displayName) formData.append("display_name", displayName);

    const res = await fetch(`${this.baseUrl}/managed-apps/${appId}/versions`, {
      method: "POST",
      body: formData,
    });
    if (!res.ok) throw await this.parseError(res);
    return res.json();
  }

  async approveBasic(appId: number, versionId: number): Promise<ManagedAppVersion> {
    const res = await fetch(
      `${this.baseUrl}/managed-apps/${appId}/versions/${versionId}/approve-basic`,
      {
        method: "POST",
        headers: { Accept: "application/json" },
      }
    );
    if (!res.ok) throw await this.parseError(res);
    return res.json();
  }

  async activateVersion(appId: number, versionId: number): Promise<ManagedAppDetail> {
    const res = await fetch(
      `${this.baseUrl}/managed-apps/${appId}/versions/${versionId}/activate`,
      {
        method: "POST",
        headers: { Accept: "application/json" },
      }
    );
    if (!res.ok) throw await this.parseError(res);
    return res.json();
  }

  async retireVersion(appId: number, versionId: number): Promise<ManagedAppVersion> {
    const res = await fetch(
      `${this.baseUrl}/managed-apps/${appId}/versions/${versionId}/retire`,
      {
        method: "POST",
        headers: { Accept: "application/json" },
      }
    );
    if (!res.ok) throw await this.parseError(res);
    return res.json();
  }
}

export const managedAppService = new ManagedAppService();

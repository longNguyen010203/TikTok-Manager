import {
  RuntimeNetworkResponse,
  RuntimeNetworkStatusResponse,
  RuntimeNetworkUpdateInput,
  RuntimeNetworkApiError,
} from "@/types/runtimeNetwork";
import { ValidationErrorDetail } from "@/types/runtime";

export interface IRuntimeNetworkService {
  getNetwork(runtimeId: number): Promise<RuntimeNetworkResponse>;
  updateNetwork(
    runtimeId: number,
    input: RuntimeNetworkUpdateInput
  ): Promise<RuntimeNetworkResponse>;
  applyNetwork(runtimeId: number): Promise<RuntimeNetworkResponse>;
  clearNetwork(runtimeId: number): Promise<RuntimeNetworkResponse>;
  getNetworkStatus(runtimeId: number): Promise<RuntimeNetworkStatusResponse>;
  getBaseUrl(): string;
}

export class FastApiRuntimeNetworkService implements IRuntimeNetworkService {
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

  private async parseError(response: Response): Promise<RuntimeNetworkApiError> {
    let rawData: Record<string, unknown> | null = null;
    try {
      rawData = await response.json();
    } catch {
      // Non-JSON response
    }

    const status = response.status;
    let message = `Request failed with status ${status}`;
    let validationDetails: ValidationErrorDetail[] | string | undefined = undefined;

    if (rawData && typeof rawData === "object") {
      const detail = rawData.detail;
      if (typeof detail === "string") {
        message = detail;
        validationDetails = detail;
      } else if (Array.isArray(detail)) {
        validationDetails = detail as ValidationErrorDetail[];
        message = (detail as ValidationErrorDetail[])
          .map((item) => {
            const loc =
              item.loc && item.loc.length > 1
                ? item.loc.slice(1).join(".")
                : "field";
            return `${loc}: ${item.msg || "Invalid value"}`;
          })
          .join("; ");
      } else if (detail && typeof detail === "object") {
        const detailObj = detail as Record<string, unknown>;
        if ("message" in detailObj && typeof detailObj.message === "string") {
          message = detailObj.message;
        }
      }
    }

    // Safety: sanitize raw execution traces, command outputs, or internal details
    if (
      message.includes("Traceback") ||
      message.includes("systemd:") ||
      message.includes("docker: Error") ||
      message.includes("subprocess.CalledProcessError") ||
      message.includes("Fernet") ||
      message.includes("ciphertext") ||
      message.includes("encrypted_password")
    ) {
      if (status === 502) {
        message = "Proxy bridge or ADB host network operation failed";
      } else if (status === 503) {
        message = "Proxy credential service or decryption failed";
      } else {
        message = "Network operation failed unexpectedly";
      }
    }

    return new RuntimeNetworkApiError(status, message, validationDetails);
  }

  async getNetwork(runtimeId: number): Promise<RuntimeNetworkResponse> {
    const response = await fetch(
      `${this.baseUrl}/runtimes/${runtimeId}/network`,
      {
        method: "GET",
        headers: {
          Accept: "application/json",
        },
      }
    );

    if (!response.ok) {
      throw await this.parseError(response);
    }

    return (await response.json()) as RuntimeNetworkResponse;
  }

  async updateNetwork(
    runtimeId: number,
    input: RuntimeNetworkUpdateInput
  ): Promise<RuntimeNetworkResponse> {
    const payload: Record<string, unknown> = {
      mode: input.mode,
      expected_revision: input.expected_revision,
    };

    if (input.mode === "http_proxy") {
      payload.proxy_host = input.proxy_host ? input.proxy_host.trim() : null;
      payload.proxy_port = input.proxy_port ? Number(input.proxy_port) : null;

      if (input.credential_action) {
        payload.credential_action = input.credential_action;
      }
      if (input.username) {
        payload.username = input.username;
      }
      if (input.password) {
        payload.password = input.password;
      }

      // Legacy references fallback
      if (input.proxy_username_secret_ref) {
        payload.proxy_username_secret_ref = input.proxy_username_secret_ref.trim();
      }
      if (input.proxy_password_secret_ref) {
        payload.proxy_password_secret_ref = input.proxy_password_secret_ref.trim();
      }
    } else {
      payload.proxy_host = null;
      payload.proxy_port = null;
    }

    const response = await fetch(
      `${this.baseUrl}/runtimes/${runtimeId}/network`,
      {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
          Accept: "application/json",
        },
        body: JSON.stringify(payload),
      }
    );

    if (!response.ok) {
      throw await this.parseError(response);
    }

    return (await response.json()) as RuntimeNetworkResponse;
  }

  async applyNetwork(runtimeId: number): Promise<RuntimeNetworkResponse> {
    const response = await fetch(
      `${this.baseUrl}/runtimes/${runtimeId}/network/apply`,
      {
        method: "POST",
        headers: {
          Accept: "application/json",
        },
      }
    );

    if (!response.ok) {
      throw await this.parseError(response);
    }

    return (await response.json()) as RuntimeNetworkResponse;
  }

  async clearNetwork(runtimeId: number): Promise<RuntimeNetworkResponse> {
    const response = await fetch(
      `${this.baseUrl}/runtimes/${runtimeId}/network/clear`,
      {
        method: "POST",
        headers: {
          Accept: "application/json",
        },
      }
    );

    if (!response.ok) {
      throw await this.parseError(response);
    }

    return (await response.json()) as RuntimeNetworkResponse;
  }

  async getNetworkStatus(
    runtimeId: number
  ): Promise<RuntimeNetworkStatusResponse> {
    const response = await fetch(
      `${this.baseUrl}/runtimes/${runtimeId}/network/status`,
      {
        method: "GET",
        headers: {
          Accept: "application/json",
        },
      }
    );

    if (!response.ok) {
      throw await this.parseError(response);
    }

    return (await response.json()) as RuntimeNetworkStatusResponse;
  }
}

export const runtimeNetworkService: IRuntimeNetworkService =
  new FastApiRuntimeNetworkService();

import {
  RedroidProvisionRequest,
  RedroidProvisioningStatus,
  ProvisioningApiError,
} from "@/types/provisioning";
import { ValidationErrorDetail } from "@/types/device";

export interface IProvisioningService {
  provisionDevice(
    input: RedroidProvisionRequest,
    idempotencyKey: string
  ): Promise<RedroidProvisioningStatus>;
  getProvisioning(provisioningId: string): Promise<RedroidProvisioningStatus>;
  getBaseUrl(): string;
}

export class FastApiProvisioningService implements IProvisioningService {
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

  private async parseError(response: Response): Promise<ProvisioningApiError> {
    let detailData: {
      detail?:
        | string
        | { message?: string; provisioning_id?: string }
        | ValidationErrorDetail[];
    } | null = null;
    try {
      detailData = await response.json();
    } catch {
      // Not JSON
    }

    const status = response.status;
    const detail = detailData?.detail;

    let message = `Request failed with status ${status}`;
    let provisioningId: string | undefined = undefined;

    if (typeof detail === "string") {
      message = detail;
    } else if (detail && typeof detail === "object") {
      if (Array.isArray(detail)) {
        message = detail
          .map((item) => {
            const loc =
              item.loc && item.loc.length > 1
                ? item.loc.slice(1).join(".")
                : "field";
            return `${loc}: ${item.msg || "Invalid value"}`;
          })
          .join("; ");
      } else {
        if ("message" in detail && typeof detail.message === "string") {
          message = detail.message;
        }
        if (
          "provisioning_id" in detail &&
          typeof detail.provisioning_id === "string"
        ) {
          provisioningId = detail.provisioning_id;
        }
      }
    }

    // Safety: Never expose stack traces or raw docker command logs
    if (message.includes("Traceback") || message.includes("docker: Error")) {
      message = "A required host provisioning operation failed";
    }

    return new ProvisioningApiError(
      status,
      message,
      provisioningId,
      typeof detail === "string" || Array.isArray(detail) ? detail : undefined
    );
  }

  async provisionDevice(
    input: RedroidProvisionRequest,
    idempotencyKey: string
  ): Promise<RedroidProvisioningStatus> {
    const payload = {
      name: input.name.trim(),
      notes: input.notes && input.notes.trim() ? input.notes.trim() : null,
      profile: input.profile.trim(),
    };

    const response = await fetch(`${this.baseUrl}/redroid-provisionings`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
        "Idempotency-Key": idempotencyKey.trim(),
      },
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      throw await this.parseError(response);
    }

    const data: RedroidProvisioningStatus = await response.json();
    return data;
  }

  async getProvisioning(
    provisioningId: string
  ): Promise<RedroidProvisioningStatus> {
    const response = await fetch(
      `${this.baseUrl}/redroid-provisionings/${encodeURIComponent(
        provisioningId.trim()
      )}`,
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

    const data: RedroidProvisioningStatus = await response.json();
    return data;
  }
}

export const provisioningService: IProvisioningService =
  new FastApiProvisioningService();

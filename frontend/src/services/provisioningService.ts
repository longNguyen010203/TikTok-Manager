import {
  RedroidProvisionRequest,
  RedroidProvisioningStatus,
  RedroidDeprovisioningStatus,
  ProvisioningApiError,
} from "@/types/provisioning";
import { ValidationErrorDetail } from "@/types/device";

export interface IProvisioningService {
  provisionDevice(
    input: RedroidProvisionRequest,
    idempotencyKey: string
  ): Promise<RedroidProvisioningStatus>;
  getProvisioning(provisioningId: string): Promise<RedroidProvisioningStatus>;
  deprovisionDevice(
    provisioningId: string
  ): Promise<RedroidDeprovisioningStatus>;
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
    let rawData: Record<string, unknown> | null = null;
    try {
      rawData = await response.json();
    } catch {
      // Not JSON
    }

    const status = response.status;
    let message = `Request failed with status ${status}`;
    let provisioningId: string | undefined = undefined;
    let deprovisionStatus: RedroidDeprovisioningStatus | undefined = undefined;
    let validationDetails: ValidationErrorDetail[] | string | undefined = undefined;

    if (rawData && typeof rawData === "object") {
      // Case 1: Backend returned RedroidDeprovisioningStatus directly on 409
      if (
        "provisioning_id" in rawData &&
        typeof rawData.provisioning_id === "string" &&
        ("container_removed" in rawData || "state" in rawData)
      ) {
        deprovisionStatus = rawData as unknown as RedroidDeprovisioningStatus;
        provisioningId = rawData.provisioning_id;
        if (
          "error_message" in rawData &&
          typeof rawData.error_message === "string" &&
          rawData.error_message
        ) {
          message = rawData.error_message;
        } else if (rawData.state === "deprovision_failed") {
          message = "Managed Redroid deprovisioning requires recovery";
        }
      }

      // Case 2: Standard FastAPI detail wrapper
      const detail = rawData.detail;
      if (typeof detail === "string") {
        message = detail;
        validationDetails = detail;
      } else if (detail && typeof detail === "object") {
        if (Array.isArray(detail)) {
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
        } else {
          const detailObj = detail as Record<string, unknown>;
          if ("message" in detailObj && typeof detailObj.message === "string") {
            message = detailObj.message;
          }
          if (
            "provisioning_id" in detailObj &&
            typeof detailObj.provisioning_id === "string"
          ) {
            provisioningId = detailObj.provisioning_id;
          }
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
      validationDetails,
      deprovisionStatus
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

  async deprovisionDevice(
    provisioningId: string
  ): Promise<RedroidDeprovisioningStatus> {
    const response = await fetch(
      `${this.baseUrl}/redroid-provisionings/${encodeURIComponent(
        provisioningId.trim()
      )}/deprovision`,
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

    const data: RedroidDeprovisioningStatus = await response.json();
    return data;
  }
}

export const provisioningService: IProvisioningService =
  new FastApiProvisioningService();


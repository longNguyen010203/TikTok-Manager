import { ApiError } from "@/types/account";
import {
  ContentAssetDetail,
  ContentAssetList,
  ContentAssetListParams,
  ContentAssetPatch,
  ContentDelivery,
  ContentDeliveryCreate,
  ContentDeliveryCreateResult,
  ContentDeliveryList,
  ContentUploadInput,
  ContentVersion,
  getContentErrorMessage,
} from "@/types/content";

class ContentService {
  private baseUrl: string;

  constructor() {
    this.baseUrl =
      process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
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

      if (
        typeof detail === "object" &&
        detail !== null &&
        !Array.isArray(detail)
      ) {
        const obj = detail as Record<string, unknown>;
        if (typeof obj.code === "string") code = obj.code;
        if (typeof obj.message === "string") message = obj.message;
      } else if (typeof detail === "string") {
        message = detail;
      } else if (Array.isArray(detail)) {
        message = detail
          .map((item) => {
            const loc =
              item.loc && item.loc.length > 1
                ? item.loc.slice(1).join(".")
                : "field";
            return `${loc}: ${item.msg || "Invalid value"}`;
          })
          .join("; ");
      }
    } catch {
      message = `Request failed with status ${response.status}: ${response.statusText}`;
    }

    if (!message) {
      message = `Request failed with status ${response.status}: ${response.statusText}`;
    }

    // Sanitize any raw execution traces or internal lock tokens
    if (
      message.includes("Traceback") ||
      message.includes("subprocess.CalledProcessError") ||
      message.includes("RuntimeOperationLock") ||
      message.includes("Pillow") ||
      message.includes("ffprobe")
    ) {
      message = "Content operation failed unexpectedly";
    }

    if (code) {
      message = getContentErrorMessage(code, message);
    }

    return new ApiError(
      response.status,
      message,
      code ? `code: ${code}` : undefined
    );
  }

  getDownloadUrl(contentId: number): string {
    return `${this.baseUrl}/content/${contentId}/download`;
  }

  getThumbnailUrl(contentId: number): string {
    return `${this.baseUrl}/content/${contentId}/thumbnail`;
  }

  async listContent(
    params?: ContentAssetListParams
  ): Promise<ContentAssetList> {
    const url = new URL(`${this.baseUrl}/content`);
    const page = params?.page && params.page > 0 ? params.page : 1;
    const pageSize =
      params?.page_size && params.page_size > 0 ? params.page_size : 20;

    url.searchParams.set("page", page.toString());
    url.searchParams.set("page_size", pageSize.toString());

    if (params?.query?.trim()) {
      url.searchParams.set("query", params.query.trim());
    }
    if (params?.asset_type) {
      url.searchParams.set("asset_type", params.asset_type);
    }
    if (params?.status) {
      url.searchParams.set("status", params.status);
    }
    if (params?.tag?.trim()) {
      url.searchParams.set("tag", params.tag.trim());
    }
    if (params?.source) {
      url.searchParams.set("source", params.source);
    }

    const response = await fetch(url.toString(), {
      method: "GET",
      headers: { Accept: "application/json" },
    });

    if (!response.ok) {
      throw await this.parseError(response);
    }

    return response.json();
  }

  async getContent(id: number): Promise<ContentAssetDetail> {
    const response = await fetch(`${this.baseUrl}/content/${id}`, {
      method: "GET",
      headers: { Accept: "application/json" },
    });

    if (!response.ok) {
      throw await this.parseError(response);
    }

    return response.json();
  }

  async uploadContent(
    input: ContentUploadInput
  ): Promise<ContentAssetDetail> {
    const formData = new FormData();
    formData.append("file", input.file);
    formData.append("display_name", input.display_name.trim());

    if (input.notes && input.notes.trim()) {
      formData.append("notes", input.notes.trim());
    }

    if (input.tags && input.tags.length > 0) {
      for (const tag of input.tags) {
        if (tag.trim()) {
          formData.append("tags", tag.trim());
        }
      }
    }

    const response = await fetch(`${this.baseUrl}/content`, {
      method: "POST",
      headers: { Accept: "application/json" },
      body: formData,
    });

    if (!response.ok) {
      throw await this.parseError(response);
    }

    return response.json();
  }

  async patchContent(
    id: number,
    data: ContentAssetPatch
  ): Promise<ContentAssetDetail> {
    const response = await fetch(`${this.baseUrl}/content/${id}`, {
      method: "PATCH",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify(data),
    });

    if (!response.ok) {
      throw await this.parseError(response);
    }

    return response.json();
  }

  async deleteContent(id: number): Promise<ContentAssetDetail> {
    const response = await fetch(`${this.baseUrl}/content/${id}`, {
      method: "DELETE",
      headers: { Accept: "application/json" },
    });

    if (!response.ok) {
      throw await this.parseError(response);
    }

    return response.json();
  }

  async listVersions(contentId: number): Promise<ContentVersion[]> {
    const response = await fetch(
      `${this.baseUrl}/content/${contentId}/versions`,
      {
        method: "GET",
        headers: { Accept: "application/json" },
      }
    );

    if (!response.ok) {
      throw await this.parseError(response);
    }

    return response.json();
  }

  async uploadVersion(
    contentId: number,
    file: File
  ): Promise<ContentAssetDetail> {
    const formData = new FormData();
    formData.append("file", file);

    const response = await fetch(
      `${this.baseUrl}/content/${contentId}/versions`,
      {
        method: "POST",
        headers: { Accept: "application/json" },
        body: formData,
      }
    );

    if (!response.ok) {
      throw await this.parseError(response);
    }

    return response.json();
  }

  async deliverContent(
    contentId: number,
    payload: ContentDeliveryCreate
  ): Promise<ContentDeliveryCreateResult> {
    const response = await fetch(
      `${this.baseUrl}/content/${contentId}/deliver`,
      {
        method: "POST",
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

    return response.json();
  }

  async listDeliveries(
    contentId: number,
    params?: {
      status?: string;
      runtime_id?: number;
      page?: number;
      page_size?: number;
    }
  ): Promise<ContentDeliveryList> {
    const url = new URL(`${this.baseUrl}/content/${contentId}/deliveries`);
    if (params?.page) url.searchParams.set("page", params.page.toString());
    if (params?.page_size)
      url.searchParams.set("page_size", params.page_size.toString());
    if (params?.status) url.searchParams.set("status", params.status);
    if (params?.runtime_id)
      url.searchParams.set("runtime_id", params.runtime_id.toString());

    const response = await fetch(url.toString(), {
      method: "GET",
      headers: { Accept: "application/json" },
    });

    if (!response.ok) {
      throw await this.parseError(response);
    }

    return response.json();
  }

  async getDelivery(deliveryId: number): Promise<ContentDelivery> {
    const response = await fetch(
      `${this.baseUrl}/content-deliveries/${deliveryId}`,
      {
        method: "GET",
        headers: { Accept: "application/json" },
      }
    );

    if (!response.ok) {
      throw await this.parseError(response);
    }

    return response.json();
  }
}

export const contentService = new ContentService();

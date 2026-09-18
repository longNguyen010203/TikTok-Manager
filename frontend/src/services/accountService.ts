import {
  Account,
  AccountListParams,
  AccountListResponse,
  CreateAccountInput,
  UpdateAccountInput,
  ApiError,
  ValidationErrorDetail,
} from "@/types/account";

export interface IAccountService {
  getAccounts(params?: AccountListParams): Promise<AccountListResponse>;
  getAccount(id: number): Promise<Account>;
  createAccount(input: CreateAccountInput): Promise<Account>;
  updateAccount(id: number, input: UpdateAccountInput): Promise<Account>;
  deleteAccount(id: number): Promise<void>;
  getBaseUrl(): string;
}

/**
 * Real FastAPI backend implementation connecting to NEXT_PUBLIC_API_BASE_URL
 */
export class FastApiAccountService implements IAccountService {
  private baseUrl: string;

  constructor(baseUrl?: string) {
    // Priority: parameter > env variable > default local backend
    const rawUrl =
      baseUrl ||
      process.env.NEXT_PUBLIC_API_BASE_URL ||
      "http://127.0.0.1:8000";
    // Remove trailing slash if present
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
      // Body is not JSON
    }

    const status = response.status;
    const detail = detailData?.detail;

    if (status === 404) {
      const msg = typeof detail === "string" ? detail : "Account not found";
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

  async getAccounts(params?: AccountListParams): Promise<AccountListResponse> {
    const url = new URL(`${this.baseUrl}/accounts`);

    const page = params?.page && params.page > 0 ? params.page : 1;
    const pageSize =
      params?.page_size && params.page_size > 0 ? params.page_size : 20;

    url.searchParams.set("page", page.toString());
    url.searchParams.set("page_size", pageSize.toString());

    if (params?.status && params.status !== "all") {
      url.searchParams.set("status", params.status);
    }

    const response = await fetch(url.toString(), {
      method: "GET",
      headers: {
        Accept: "application/json",
      },
    });

    if (!response.ok) {
      throw await this.parseError(response);
    }

    const data: AccountListResponse = await response.json();
    return data;
  }

  async getAccount(id: number): Promise<Account> {
    const response = await fetch(`${this.baseUrl}/accounts/${id}`, {
      method: "GET",
      headers: {
        Accept: "application/json",
      },
    });

    if (!response.ok) {
      throw await this.parseError(response);
    }

    const data: Account = await response.json();
    return data;
  }

  async createAccount(input: CreateAccountInput): Promise<Account> {
    const payload = {
      name: input.name.trim(),
      username: input.username.replace(/^@/, "").trim(),
      platform: input.platform.trim() || "tiktok",
      status: input.status,
      notes: input.notes && input.notes.trim() ? input.notes.trim() : null,
    };

    const response = await fetch(`${this.baseUrl}/accounts`, {
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

    const created: Account = await response.json();
    return created;
  }

  async updateAccount(
    id: number,
    input: UpdateAccountInput
  ): Promise<Account> {
    const payload: Record<string, unknown> = {};

    if (input.name !== undefined) payload.name = input.name.trim();
    if (input.username !== undefined)
      payload.username = input.username.replace(/^@/, "").trim();
    if (input.platform !== undefined) payload.platform = input.platform.trim();
    if (input.status !== undefined) payload.status = input.status;
    if (input.notes !== undefined) {
      payload.notes =
        input.notes && input.notes.trim() ? input.notes.trim() : null;
    }

    const response = await fetch(`${this.baseUrl}/accounts/${id}`, {
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

    const updated: Account = await response.json();
    return updated;
  }

  async deleteAccount(id: number): Promise<void> {
    const response = await fetch(`${this.baseUrl}/accounts/${id}`, {
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

// Active default service instance pointing to FastAPI backend
export const accountService: IAccountService = new FastApiAccountService();

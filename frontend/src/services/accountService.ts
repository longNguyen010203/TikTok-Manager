import {
  Account,
  AccountListParams,
  AccountListResponse,
  AccountRegistrationCompleteInput,
  AccountRegistrationFailureInput,
  AccountSecretMetadata,
  AccountSecretType,
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
  assignRuntime(id: number, runtimeId: number): Promise<Account>;
  unassignRuntime(id: number): Promise<Account>;
  completeRegistration(
    id: number,
    payload?: AccountRegistrationCompleteInput
  ): Promise<Account>;
  failRegistration(
    id: number,
    payload: AccountRegistrationFailureInput
  ): Promise<Account>;
  reopenRegistration(id: number): Promise<Account>;
  getAccountSecrets(id: number): Promise<AccountSecretMetadata[]>;
  putAccountSecret(
    id: number,
    secretType: AccountSecretType,
    value: string
  ): Promise<AccountSecretMetadata>;
  deleteAccountSecret(
    id: number,
    secretType: AccountSecretType
  ): Promise<void>;
  getBaseUrl(): string;
}

/**
 * Real FastAPI backend implementation connecting to NEXT_PUBLIC_API_BASE_URL.
 */
export class FastApiAccountService implements IAccountService {
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
      // Body is not JSON
    }

    const status = response.status;
    const detail = detailData?.detail;

    if (status === 404) {
      const msg = typeof detail === "string" ? detail : "Account not found";
      return new ApiError(404, msg, detail);
    }

    if (status === 409) {
      const msg =
        typeof detail === "string" ? detail : "Account lifecycle conflict";
      return new ApiError(409, msg, detail);
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

    if (params?.niche && params.niche.trim()) {
      url.searchParams.set("niche", params.niche.trim());
    }

    if (params?.runtime_id && params.runtime_id > 0) {
      url.searchParams.set("runtime_id", params.runtime_id.toString());
    }

    if (params?.device_id && params.device_id > 0) {
      url.searchParams.set("device_id", params.device_id.toString());
    }

    if (params?.tag && params.tag.trim()) {
      url.searchParams.set("tag", params.tag.trim());
    }

    const queryTerm = params?.query || params?.search;
    if (queryTerm && queryTerm.trim()) {
      url.searchParams.set("query", queryTerm.trim());
    }

    if (params?.include_archived) {
      url.searchParams.set("include_archived", "true");
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
    const displayName = (input.display_name || input.name || "").trim();
    const rawUsername = input.username?.replace(/^@/, "").trim() || "";
    const rawEmail = input.email?.trim() || "";
    const rawPhone = input.phone?.trim() || "";
    const rawNiche = input.niche?.trim() || "";
    const rawNotes = input.notes?.trim() || "";
    const rawStatusReason = input.status_reason?.trim() || "";

    const payload: Record<string, unknown> = {
      display_name: displayName,
      name: displayName,
      username: rawUsername ? rawUsername : null,
      email: rawEmail ? rawEmail : null,
      phone: rawPhone ? rawPhone : null,
      platform: input.platform?.trim() || "tiktok",
      status: input.status || "active",
      registration_state: input.registration_state || "unknown",
      health_status: input.health_status || "unknown",
      status_reason: rawStatusReason ? rawStatusReason : null,
      niche: rawNiche ? rawNiche : null,
      notes: rawNotes ? rawNotes : null,
      tags: Array.isArray(input.tags)
        ? input.tags.map((t) => t.trim()).filter(Boolean)
        : [],
      runtime_id: input.runtime_id ? Number(input.runtime_id) : null,
    };

    if (input.follower_count !== undefined && input.follower_count !== null) {
      payload.follower_count = Number(input.follower_count);
    }
    if (input.following_count !== undefined && input.following_count !== null) {
      payload.following_count = Number(input.following_count);
    }
    if (input.likes_count !== undefined && input.likes_count !== null) {
      payload.likes_count = Number(input.likes_count);
    }
    if (input.video_count !== undefined && input.video_count !== null) {
      payload.video_count = Number(input.video_count);
    }

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

    if (input.display_name !== undefined || input.name !== undefined) {
      const nameVal = (input.display_name ?? input.name ?? "").trim();
      payload.display_name = nameVal;
      payload.name = nameVal;
    }

    if (input.username !== undefined) {
      const u = input.username?.replace(/^@/, "").trim() || "";
      payload.username = u ? u : null;
    }

    if (input.email !== undefined) {
      const em = input.email?.trim() || "";
      payload.email = em ? em : null;
    }

    if (input.phone !== undefined) {
      const ph = input.phone?.trim() || "";
      payload.phone = ph ? ph : null;
    }

    if (input.platform !== undefined) {
      payload.platform = input.platform.trim() || "tiktok";
    }

    if (input.status !== undefined) {
      payload.status = input.status;
    }

    if (input.registration_state !== undefined) {
      payload.registration_state = input.registration_state;
    }

    if (input.health_status !== undefined) {
      payload.health_status = input.health_status;
    }

    if (input.status_reason !== undefined) {
      const sr = input.status_reason?.trim() || "";
      payload.status_reason = sr ? sr : null;
    }

    if (input.niche !== undefined) {
      const nc = input.niche?.trim() || "";
      payload.niche = nc ? nc : null;
    }

    if (input.notes !== undefined) {
      const nt = input.notes?.trim() || "";
      payload.notes = nt ? nt : null;
    }

    if (input.tags !== undefined) {
      payload.tags = Array.isArray(input.tags)
        ? input.tags.map((t) => t.trim()).filter(Boolean)
        : [];
    }

    if (input.runtime_id !== undefined) {
      payload.runtime_id = input.runtime_id ? Number(input.runtime_id) : null;
    }

    if (input.follower_count !== undefined) {
      payload.follower_count =
        input.follower_count !== null ? Number(input.follower_count) : null;
    }

    if (input.following_count !== undefined) {
      payload.following_count =
        input.following_count !== null ? Number(input.following_count) : null;
    }

    if (input.likes_count !== undefined) {
      payload.likes_count =
        input.likes_count !== null ? Number(input.likes_count) : null;
    }

    if (input.video_count !== undefined) {
      payload.video_count =
        input.video_count !== null ? Number(input.video_count) : null;
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

  async assignRuntime(id: number, runtimeId: number): Promise<Account> {
    const response = await fetch(`${this.baseUrl}/accounts/${id}/runtime`, {
      method: "PUT",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify({ runtime_id: runtimeId }),
    });

    if (!response.ok) {
      throw await this.parseError(response);
    }

    return response.json();
  }

  async unassignRuntime(id: number): Promise<Account> {
    const response = await fetch(`${this.baseUrl}/accounts/${id}/runtime`, {
      method: "DELETE",
      headers: {
        Accept: "application/json",
      },
    });

    if (!response.ok) {
      throw await this.parseError(response);
    }

    return response.json();
  }

  async completeRegistration(
    id: number,
    payload?: AccountRegistrationCompleteInput
  ): Promise<Account> {
    const body: Record<string, unknown> = {};
    if (payload?.username !== undefined) {
      body.username = payload.username
        ? payload.username.trim().replace(/^@/, "")
        : null;
    }
    if (payload?.display_name !== undefined) {
      body.display_name = payload.display_name
        ? payload.display_name.trim()
        : null;
    }
    if (payload?.notes !== undefined) {
      body.notes = payload.notes ? payload.notes.trim() : null;
    }

    const response = await fetch(
      `${this.baseUrl}/accounts/${id}/registration/complete`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Accept: "application/json",
        },
        body: JSON.stringify(body),
      }
    );

    if (!response.ok) {
      throw await this.parseError(response);
    }

    return response.json();
  }

  async failRegistration(
    id: number,
    payload: AccountRegistrationFailureInput
  ): Promise<Account> {
    const response = await fetch(
      `${this.baseUrl}/accounts/${id}/registration/fail`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Accept: "application/json",
        },
        body: JSON.stringify({ reason: payload.reason.trim() }),
      }
    );

    if (!response.ok) {
      throw await this.parseError(response);
    }

    return response.json();
  }

  async reopenRegistration(id: number): Promise<Account> {
    const response = await fetch(
      `${this.baseUrl}/accounts/${id}/registration/reopen`,
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

    return response.json();
  }

  async getAccountSecrets(id: number): Promise<AccountSecretMetadata[]> {
    const response = await fetch(`${this.baseUrl}/accounts/${id}/secrets`, {
      method: "GET",
      headers: {
        Accept: "application/json",
      },
    });

    if (!response.ok) {
      throw await this.parseError(response);
    }

    return response.json();
  }

  async putAccountSecret(
    id: number,
    secretType: AccountSecretType,
    value: string
  ): Promise<AccountSecretMetadata> {
    const response = await fetch(
      `${this.baseUrl}/accounts/${id}/secrets/${secretType}`,
      {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
          Accept: "application/json",
        },
        body: JSON.stringify({ value }),
      }
    );

    if (!response.ok) {
      throw await this.parseError(response);
    }

    return response.json();
  }

  async deleteAccountSecret(
    id: number,
    secretType: AccountSecretType
  ): Promise<void> {
    const response = await fetch(
      `${this.baseUrl}/accounts/${id}/secrets/${secretType}`,
      {
        method: "DELETE",
        headers: {
          Accept: "application/json",
        },
      }
    );

    if (!response.ok) {
      throw await this.parseError(response);
    }
  }
}

// Active default service instance pointing to FastAPI backend
export const accountService: IAccountService = new FastApiAccountService();

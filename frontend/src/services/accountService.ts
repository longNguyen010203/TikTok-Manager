import {
  Account,
  AccountListParams,
  AccountListResponse,
  CreateAccountInput,
} from "@/types/account";

export interface IAccountService {
  getAccounts(params?: AccountListParams): Promise<AccountListResponse>;
  createAccount(input: CreateAccountInput): Promise<Account>;
}

const INITIAL_MOCK_ACCOUNTS: Account[] = [
  {
    id: 1,
    name: "Primary Brand Hub",
    username: "brand_official",
    platform: "tiktok",
    status: "active",
    notes: "Main verified TikTok business channel",
    created_at: "2026-09-01T08:00:00Z",
    updated_at: "2026-09-18T09:30:00Z",
  },
  {
    id: 2,
    name: "Product Demos Lab",
    username: "product_demos",
    platform: "tiktok",
    status: "active",
    notes: "Weekly product unveilings and short reviews",
    created_at: "2026-09-02T10:15:00Z",
    updated_at: "2026-09-17T14:20:00Z",
  },
  {
    id: 3,
    name: "Daily Creator Clips",
    username: "creator_daily",
    platform: "tiktok",
    status: "inactive",
    notes: "Paused pending new creator onboarding",
    created_at: "2026-09-05T12:00:00Z",
    updated_at: "2026-09-15T11:45:00Z",
  },
  {
    id: 4,
    name: "Global Tech Trends",
    username: "global_tech",
    platform: "tiktok",
    status: "active",
    notes: "Curated AI and gadget updates",
    created_at: "2026-09-08T09:00:00Z",
    updated_at: "2026-09-18T07:10:00Z",
  },
  {
    id: 5,
    name: "Viral Shorts Studio",
    username: "shorts_studio",
    platform: "tiktok",
    status: "suspended",
    notes: "Temporary verification appeal in review",
    created_at: "2026-09-09T16:45:00Z",
    updated_at: "2026-09-16T18:00:00Z",
  },
  {
    id: 6,
    name: "Lifestyle & Fitness",
    username: "fit_lifestyle",
    platform: "tiktok",
    status: "active",
    notes: "Community fitness challenges",
    created_at: "2026-09-10T11:20:00Z",
    updated_at: "2026-09-18T08:50:00Z",
  },
  {
    id: 7,
    name: "Gaming Highlights",
    username: "play_stream",
    platform: "tiktok",
    status: "inactive",
    notes: "Seasonal gaming streams and clip highlights",
    created_at: "2026-09-11T13:10:00Z",
    updated_at: "2026-09-14T10:05:00Z",
  },
  {
    id: 8,
    name: "Kitchen & Cooking",
    username: "quick_recipes",
    platform: "tiktok",
    status: "active",
    notes: "60-second dinner recipe ideas",
    created_at: "2026-09-12T15:30:00Z",
    updated_at: "2026-09-17T19:40:00Z",
  },
];

export class MockAccountService implements IAccountService {
  private accounts: Account[] = [...INITIAL_MOCK_ACCOUNTS];
  private shouldSimulateError = false;

  public setSimulateError(value: boolean) {
    this.shouldSimulateError = value;
  }

  public getSimulateError(): boolean {
    return this.shouldSimulateError;
  }

  async getAccounts(params?: AccountListParams): Promise<AccountListResponse> {
    // Simulate network delay
    await new Promise((resolve) => setTimeout(resolve, 350));

    if (this.shouldSimulateError) {
      throw new Error("Simulated network error: Failed to fetch accounts from server.");
    }

    const page = params?.page && params.page > 0 ? params.page : 1;
    const pageSize = params?.page_size && params.page_size > 0 ? params.page_size : 5;
    const statusFilter = params?.status?.trim().toLowerCase();
    const searchQuery = params?.search?.trim().toLowerCase();

    let filtered = [...this.accounts];

    // Filter by status if specified
    if (statusFilter && statusFilter !== "all") {
      filtered = filtered.filter(
        (acc) => acc.status.toLowerCase() === statusFilter
      );
    }

    // Filter by search query (name or username)
    if (searchQuery) {
      filtered = filtered.filter(
        (acc) =>
          acc.name.toLowerCase().includes(searchQuery) ||
          acc.username.toLowerCase().includes(searchQuery)
      );
    }

    const total = filtered.length;
    const startIndex = (page - 1) * pageSize;
    const paginatedItems = filtered.slice(startIndex, startIndex + pageSize);

    return {
      items: paginatedItems,
      total,
      page,
      page_size: pageSize,
    };
  }

  async createAccount(input: CreateAccountInput): Promise<Account> {
    await new Promise((resolve) => setTimeout(resolve, 350));

    if (this.shouldSimulateError) {
      throw new Error("Failed to create account: Server unreachable.");
    }

    const newId =
      this.accounts.length > 0
        ? Math.max(...this.accounts.map((a) => a.id)) + 1
        : 1;

    const now = new Date().toISOString();
    const newAccount: Account = {
      id: newId,
      name: input.name.trim(),
      username: input.username.replace(/^@/, "").trim(),
      platform: input.platform.trim() || "tiktok",
      status: input.status,
      notes: input.notes?.trim() || null,
      created_at: now,
      updated_at: now,
    };

    // Prepend new account
    this.accounts.unshift(newAccount);
    return newAccount;
  }
}

// Default singleton instance
export const accountService = new MockAccountService();

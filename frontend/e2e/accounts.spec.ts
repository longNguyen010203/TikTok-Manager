import { expect, Page, test } from "@playwright/test";

const now = "2026-10-06T12:00:00Z";

interface MockDevice {
  id: number;
  name: string;
  device_type: string;
  platform: string;
  os_version: string;
  status: string;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

interface MockRuntime {
  id: number;
  device_id: number;
  name: string;
  runtime_type: string;
  status: string;
  adb_serial: string;
  docker_container_name: string;
  last_seen_at: string;
  created_at: string;
  updated_at: string;
}

interface MockAccount {
  id: number;
  name: string;
  display_name: string;
  username: string | null;
  email: string | null;
  phone: string | null;
  platform: string;
  status: string;
  registration_state: string;
  health_status: string;
  status_reason: string | null;
  niche: string | null;
  notes: string | null;
  tags: string[];
  runtime_id: number | null;
  device_id: number | null;
  follower_count: number | null;
  following_count: number | null;
  likes_count: number | null;
  video_count: number | null;
  metrics_updated_at: string | null;
  secret_present: boolean;
  secret_types: string[];
  created_at: string;
  updated_at: string;
  archived_at: string | null;
}

interface MockSecretEntry {
  secret_type: string;
  present: boolean;
  updated_at: string;
}

const mockDevices: MockDevice[] = [
  {
    id: 10,
    name: "Pixel 6 Device 10",
    device_type: "emulator",
    platform: "android",
    os_version: "12",
    status: "online",
    notes: null,
    created_at: now,
    updated_at: now,
  },
  {
    id: 20,
    name: "Galaxy S21 Device 20",
    device_type: "emulator",
    platform: "android",
    os_version: "12",
    status: "online",
    notes: null,
    created_at: now,
    updated_at: now,
  },
];

const mockRuntimes: MockRuntime[] = [
  {
    id: 1,
    device_id: 10,
    name: "Redroid 01",
    runtime_type: "redroid",
    status: "running",
    adb_serial: "localhost:5555",
    docker_container_name: "redroid-1",
    last_seen_at: now,
    created_at: now,
    updated_at: now,
  },
  {
    id: 2,
    device_id: 20,
    name: "Redroid 02",
    runtime_type: "redroid",
    status: "running",
    adb_serial: "localhost:5557",
    docker_container_name: "redroid-2",
    last_seen_at: now,
    created_at: now,
    updated_at: now,
  },
];

let accountsList: MockAccount[] = [];
let accountSecretsMap: Map<number, Map<string, MockSecretEntry>> = new Map();
let simulateListError = false;

function initMockData() {
  simulateListError = false;
  accountSecretsMap = new Map();

  // Initial accounts
  accountsList = [
    {
      id: 1,
      name: "Dance Star Studio",
      display_name: "Dance Star Studio",
      username: "dancestar",
      email: "dance@example.com",
      phone: "+1234567890",
      platform: "tiktok",
      status: "active",
      registration_state: "registered",
      health_status: "healthy",
      status_reason: null,
      niche: "dance",
      notes: "Main dance channel for TikTok",
      tags: ["vip", "us-east"],
      runtime_id: 1,
      device_id: 10,
      follower_count: 1250000,
      following_count: 120,
      likes_count: 4500000,
      video_count: 85,
      metrics_updated_at: now,
      secret_present: true,
      secret_types: ["account_password", "email_password"],
      created_at: "2026-10-01T00:00:00Z",
      updated_at: "2026-10-06T12:00:00Z",
      archived_at: null,
    },
    {
      id: 2,
      name: "Gaming Highlights",
      display_name: "Gaming Highlights",
      username: null,
      email: "gaming@example.com",
      phone: null,
      platform: "tiktok",
      status: "pending",
      registration_state: "pending",
      health_status: "unknown",
      status_reason: "Awaiting phone verification",
      niche: "gaming",
      notes: null,
      tags: ["esports"],
      runtime_id: null,
      device_id: null,
      follower_count: 0,
      following_count: 0,
      likes_count: 0,
      video_count: 0,
      metrics_updated_at: null,
      secret_present: false,
      secret_types: [],
      created_at: "2026-10-02T00:00:00Z",
      updated_at: "2026-10-02T00:00:00Z",
      archived_at: null,
    },
    {
      id: 3,
      name: "Tech Reviews Daily",
      display_name: "Tech Reviews Daily",
      username: "techdaily",
      email: "tech@example.com",
      phone: null,
      platform: "tiktok",
      status: "restricted",
      registration_state: "registered",
      health_status: "warning",
      status_reason: "Shadowban risk detected",
      niche: "tech",
      notes: "Review content carefully",
      tags: ["tech", "gadgets"],
      runtime_id: 2,
      device_id: 20,
      follower_count: 45000,
      following_count: 230,
      likes_count: 120000,
      video_count: 42,
      metrics_updated_at: "2026-10-05T08:00:00Z",
      secret_present: true,
      secret_types: ["account_password"],
      created_at: "2026-10-03T00:00:00Z",
      updated_at: "2026-10-05T08:00:00Z",
      archived_at: null,
    },
    {
      id: 4,
      name: "Old Abandoned Brand",
      display_name: "Old Abandoned Brand",
      username: "oldbrand",
      email: "old@example.com",
      phone: null,
      platform: "tiktok",
      status: "archived",
      registration_state: "registered",
      health_status: "unhealthy",
      status_reason: "Decommissioned by user",
      niche: "lifestyle",
      notes: "Archived account",
      tags: ["legacy"],
      runtime_id: null,
      device_id: null,
      follower_count: 1200,
      following_count: 10,
      likes_count: 5000,
      video_count: 10,
      metrics_updated_at: "2026-09-01T00:00:00Z",
      secret_present: false,
      secret_types: [],
      created_at: "2026-08-01T00:00:00Z",
      updated_at: "2026-09-15T00:00:00Z",
      archived_at: "2026-09-15T00:00:00Z",
    },
  ];

  // Secrets store for account 1
  const sec1 = new Map<string, MockSecretEntry>();
  sec1.set("account_password", {
    secret_type: "account_password",
    present: true,
    updated_at: now,
  });
  sec1.set("email_password", {
    secret_type: "email_password",
    present: true,
    updated_at: now,
  });
  accountSecretsMap.set(1, sec1);

  // Secrets store for account 3
  const sec3 = new Map<string, MockSecretEntry>();
  sec3.set("account_password", {
    secret_type: "account_password",
    present: true,
    updated_at: "2026-10-05T08:00:00Z",
  });
  accountSecretsMap.set(3, sec3);
}

async function installApi(page: Page) {
  await page.route("http://127.0.0.1:8000/**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname;
    const method = request.method();
    const json = (body: unknown, status = 200) =>
      route.fulfill({
        status,
        contentType: "application/json",
        body: JSON.stringify(body),
      });

    // Devices & Runtimes
    if (path === "/devices") {
      return json({
        items: mockDevices,
        total: mockDevices.length,
        page: 1,
        page_size: 100,
      });
    }

    if (path === "/runtimes") {
      return json({
        items: mockRuntimes,
        total: mockRuntimes.length,
        page: 1,
        page_size: 100,
      });
    }

    // Secrets endpoints
    const secretsMatch = path.match(/^\/accounts\/(\d+)\/secrets(?:\/([^/]+))?$/);
    if (secretsMatch) {
      const accountId = Number(secretsMatch[1]);
      const secretType = secretsMatch[2];
      let accountSecs = accountSecretsMap.get(accountId);
      if (!accountSecs) {
        accountSecs = new Map<string, MockSecretEntry>();
        accountSecretsMap.set(accountId, accountSecs);
      }

      if (method === "GET" && !secretType) {
        const list = Array.from(accountSecs.values());
        return json(list);
      }

      if (method === "PUT" && secretType) {
        const body = request.postDataJSON() as { value?: string };
        if (!body || !body.value) {
          return json({ detail: "Value cannot be empty" }, 422);
        }
        const updatedEntry: MockSecretEntry = {
          secret_type: secretType,
          present: true,
          updated_at: now,
        };
        accountSecs.set(secretType, updatedEntry);

        // Update account record
        const acc = accountsList.find((a) => a.id === accountId);
        if (acc) {
          if (!acc.secret_types.includes(secretType)) {
            acc.secret_types.push(secretType);
          }
          acc.secret_present = true;
          acc.updated_at = now;
        }

        return json(updatedEntry);
      }

      if (method === "DELETE" && secretType) {
        accountSecs.delete(secretType);
        const acc = accountsList.find((a) => a.id === accountId);
        if (acc) {
          acc.secret_types = acc.secret_types.filter((t) => t !== secretType);
          acc.secret_present = acc.secret_types.length > 0;
          acc.updated_at = now;
        }
        return route.fulfill({ status: 204 });
      }
    }

    // Runtime assignment endpoints
    const runtimeAssignMatch = path.match(/^\/accounts\/(\d+)\/runtime$/);
    if (runtimeAssignMatch) {
      const accountId = Number(runtimeAssignMatch[1]);
      const acc = accountsList.find((a) => a.id === accountId);
      if (!acc) return json({ detail: "Account not found" }, 404);

      if (method === "PUT") {
        const body = request.postDataJSON() as { runtime_id: number };
        const rt = mockRuntimes.find((r) => r.id === body.runtime_id);
        if (!rt) return json({ detail: "Runtime not found" }, 404);
        acc.runtime_id = rt.id;
        acc.device_id = rt.device_id;
        acc.updated_at = now;
        return json(acc);
      }

      if (method === "DELETE") {
        acc.runtime_id = null;
        acc.device_id = null;
        acc.updated_at = now;
        return json(acc);
      }
    }

    // Single account CRUD
    const singleAccountMatch = path.match(/^\/accounts\/(\d+)$/);
    if (singleAccountMatch) {
      const accountId = Number(singleAccountMatch[1]);
      const acc = accountsList.find((a) => a.id === accountId);
      if (!acc) return json({ detail: "Account not found" }, 404);

      if (method === "GET") {
        return json(acc);
      }

      if (method === "PATCH") {
        const body = request.postDataJSON() as Partial<MockAccount>;
        Object.assign(acc, body);
        if (body.status && body.status !== "archived") {
          acc.archived_at = null;
        }
        if (body.runtime_id !== undefined) {
          if (body.runtime_id === null) {
            acc.runtime_id = null;
            acc.device_id = null;
          } else {
            const rt = mockRuntimes.find((r) => r.id === body.runtime_id);
            if (rt) {
              acc.runtime_id = rt.id;
              acc.device_id = rt.device_id;
            }
          }
        }
        acc.updated_at = now;
        return json(acc);
      }

      if (method === "DELETE") {
        // Soft archive
        acc.status = "archived";
        acc.archived_at = now;
        acc.updated_at = now;
        return route.fulfill({ status: 204 });
      }
    }

    // Accounts list & create
    if (path === "/accounts") {
      if (method === "GET") {
        if (simulateListError) {
          return json({ detail: "Internal Server Error in Account Registry" }, 500);
        }

        const page = parseInt(url.searchParams.get("page") || "1", 10);
        const pageSize = parseInt(url.searchParams.get("page_size") || "20", 10);
        const query = url.searchParams.get("query")?.toLowerCase() || "";
        const status = url.searchParams.get("status");
        const niche = url.searchParams.get("niche")?.toLowerCase();
        const tag = url.searchParams.get("tag")?.toLowerCase();
        const runtimeId = url.searchParams.get("runtime_id");
        const deviceId = url.searchParams.get("device_id");
        const includeArchived = url.searchParams.get("include_archived") === "true";

        let filtered = [...accountsList];

        // Archive visibility filter
        if (!includeArchived) {
          filtered = filtered.filter(
            (a) => a.status !== "archived" && a.archived_at === null
          );
        }

        // Query search
        if (query) {
          filtered = filtered.filter(
            (a) =>
              a.display_name.toLowerCase().includes(query) ||
              (a.username && a.username.toLowerCase().includes(query)) ||
              (a.email && a.email.toLowerCase().includes(query)) ||
              (a.notes && a.notes.toLowerCase().includes(query))
          );
        }

        // Status filter
        if (status && status !== "all") {
          filtered = filtered.filter((a) => a.status === status);
        }

        // Niche filter
        if (niche) {
          filtered = filtered.filter((a) => a.niche && a.niche.toLowerCase() === niche);
        }

        // Tag filter
        if (tag) {
          filtered = filtered.filter((a) =>
            a.tags.some((t) => t.toLowerCase().includes(tag))
          );
        }

        // Runtime filter
        if (runtimeId) {
          filtered = filtered.filter((a) => a.runtime_id === Number(runtimeId));
        }

        // Device filter
        if (deviceId) {
          filtered = filtered.filter((a) => a.device_id === Number(deviceId));
        }

        const startIndex = (page - 1) * pageSize;
        const pagedItems = filtered.slice(startIndex, startIndex + pageSize);

        return json({
          items: pagedItems,
          total: filtered.length,
          page,
          page_size: pageSize,
        });
      }

      if (method === "POST") {
        const body = request.postDataJSON() as Record<string, unknown>;
        if (!body.display_name && !body.name) {
          return json({ detail: "display_name is required" }, 422);
        }

        const newId = accountsList.length + 1;
        const displayName = String(body.display_name || body.name);
        const username = body.username ? String(body.username).replace(/^@/, "").toLowerCase() : null;
        let deviceId: number | null = null;
        let runtimeId: number | null = null;

        if (body.runtime_id) {
          runtimeId = Number(body.runtime_id);
          const rt = mockRuntimes.find((r) => r.id === runtimeId);
          if (rt) {
            deviceId = rt.device_id;
          }
        }

        const newAccount: MockAccount = {
          id: newId,
          name: displayName,
          display_name: displayName,
          username,
          email: body.email ? String(body.email) : null,
          phone: body.phone ? String(body.phone) : null,
          platform: "tiktok",
          status: (body.status as string) || "active",
          registration_state: (body.registration_state as string) || "registered",
          health_status: (body.health_status as string) || "healthy",
          status_reason: (body.status_reason as string) || null,
          niche: (body.niche as string) || null,
          notes: (body.notes as string) || null,
          tags: Array.isArray(body.tags) ? (body.tags as string[]) : [],
          runtime_id: runtimeId,
          device_id: deviceId,
          follower_count: body.follower_count !== undefined ? Number(body.follower_count) : null,
          following_count: body.following_count !== undefined ? Number(body.following_count) : null,
          likes_count: body.likes_count !== undefined ? Number(body.likes_count) : null,
          video_count: body.video_count !== undefined ? Number(body.video_count) : null,
          metrics_updated_at: null,
          secret_present: false,
          secret_types: [],
          created_at: now,
          updated_at: now,
          archived_at: null,
        };

        accountsList.unshift(newAccount);
        return json(newAccount, 201);
      }
    }

    return json({ detail: `Route not mocked: ${method} ${path}` }, 404);
  });
}

test.describe("TIK-025 Phase 2: Account Control Center", () => {
  test.beforeEach(async ({ page }) => {
    initMockData();
    await installApi(page);
  });

  test("1. Renders accounts table, metrics, nullable handle, and excludes archived by default", async ({
    page,
  }) => {
    await page.goto("/accounts");

    // Header title and stats
    await expect(page.getByRole("heading", { name: "Account Control Center" })).toBeVisible();
    await expect(page.getByText("Active Listed")).toBeVisible();
    await expect(page.getByText("Assigned Runtime")).toBeVisible();
    await expect(page.getByText("With Credentials")).toBeVisible();

    // Table column headers
    await expect(page.getByRole("columnheader", { name: "Account" })).toBeVisible();
    await expect(page.getByRole("columnheader", { name: "Username" })).toBeVisible();
    await expect(page.getByRole("columnheader", { name: "Status" })).toBeVisible();
    await expect(page.getByRole("columnheader", { name: "Reg / Health" })).toBeVisible();
    await expect(page.getByRole("columnheader", { name: "Niche" })).toBeVisible();
    await expect(page.getByRole("columnheader", { name: "Metrics" })).toBeVisible();
    await expect(page.getByRole("columnheader", { name: "Runtime & Device" })).toBeVisible();
    await expect(page.getByRole("columnheader", { name: "Credentials" })).toBeVisible();

    // Active listed accounts
    await expect(page.getByText("Dance Star Studio")).toBeVisible();
    await expect(page.getByText("@dancestar")).toBeVisible();
    await expect(page.getByText("1.3M")).toBeVisible();
    await expect(page.getByText("4.5M")).toBeVisible();

    // Nullable handle
    await expect(page.getByText("Gaming Highlights")).toBeVisible();
    await expect(page.getByText("No handle")).toBeVisible();

    // Restricted account
    await expect(page.getByText("Tech Reviews Daily")).toBeVisible();

    // Archived account must NOT be visible by default
    await expect(page.getByText("Old Abandoned Brand")).not.toBeVisible();
  });

  test("2. Performs server-driven search query", async ({ page }) => {
    await page.goto("/accounts");

    const searchInput = page.getByPlaceholder("Search by name, @username, email, or niche...");
    await searchInput.fill("Dance");

    // Should show Dance Star Studio and hide others
    await expect(page.getByText("Dance Star Studio")).toBeVisible();
    await expect(page.getByText("Gaming Highlights")).not.toBeVisible();
    await expect(page.getByText("Tech Reviews Daily")).not.toBeVisible();

    // Clear search
    await page.getByRole("button", { name: "Clear search" }).click();
    await expect(page.getByText("Gaming Highlights")).toBeVisible();
  });

  test("3. Filters by status and advanced filters (niche, runtime)", async ({ page }) => {
    await page.goto("/accounts");

    // Filter by status: pending
    const statusSelect = page.getByLabel("Filter by account status");
    await statusSelect.selectOption("pending");

    await expect(page.getByText("Gaming Highlights")).toBeVisible();
    await expect(page.getByText("Dance Star Studio")).not.toBeVisible();

    // Reset filters
    await page.getByRole("button", { name: "Reset" }).click();
    await expect(page.getByText("Dance Star Studio")).toBeVisible();

    // Open advanced filters tray
    await page.getByRole("button", { name: /Filters/i }).click();

    // Filter by niche: dance
    const nicheInput = page.getByPlaceholder("Filter by niche...");
    await nicheInput.fill("dance");

    await expect(page.getByText("Dance Star Studio")).toBeVisible();
    await expect(page.getByText("Tech Reviews Daily")).not.toBeVisible();

    // Clear and filter by runtime: Redroid 02
    await nicheInput.fill("");
    const runtimeSelect = page.locator("select").filter({ hasText: "All Runtimes" });
    await runtimeSelect.selectOption("2");

    await expect(page.getByText("Tech Reviews Daily")).toBeVisible();
    await expect(page.getByText("Dance Star Studio")).not.toBeVisible();
  });

  test("4. Toggles archived accounts visibility and soft-archives an account", async ({ page }) => {
    await page.goto("/accounts");

    // Default: Old Abandoned Brand is hidden
    await expect(page.getByText("Old Abandoned Brand")).not.toBeVisible();

    // Check "Include Archived"
    const archivedCheckbox = page.getByRole("checkbox", { name: /Include Archived/i });
    await archivedCheckbox.check();

    // Now Old Abandoned Brand is displayed with Archived badge
    await expect(page.getByText("Old Abandoned Brand")).toBeVisible();
    await expect(page.getByText("Archived Mode")).toBeVisible();

    // Uncheck and verify it hides again
    await archivedCheckbox.uncheck();
    await expect(page.getByText("Old Abandoned Brand")).not.toBeVisible();

    // Now soft-archive "Gaming Highlights"
    const archiveButton = page.getByRole("button", { name: "Archive account Gaming Highlights" });
    await archiveButton.click();

    // Archive confirmation dialog appears
    const dialog = page.getByRole("alertdialog");
    await expect(dialog).toBeVisible();
    await expect(dialog.getByRole("heading", { name: "Archive Account" })).toBeVisible();
    await expect(dialog.getByText("Archiving hides the account from active registry views")).toBeVisible();

    // Confirm archive
    await dialog.getByRole("button", { name: "Archive Account" }).click();

    // Dialog closes and account is no longer in active table
    await expect(dialog).not.toBeVisible();
    await expect(page.getByText("Gaming Highlights")).not.toBeVisible();
  });

  test("5. Creates a new canonical account with metadata, metrics snapshot, and runtime", async ({
    page,
  }) => {
    await page.goto("/accounts");

    await page.getByRole("button", { name: "Create Account" }).click();

    const modal = page.getByRole("dialog");
    await expect(modal).toBeVisible();
    await expect(modal.getByRole("heading", { name: "Register New Account" })).toBeVisible();

    // Fill form
    await page.getByPlaceholder("e.g. Creator Alpha").fill("Fitness Daily Pro");
    await page.getByPlaceholder("creator_alpha").fill("fitnesspro");
    await page.getByPlaceholder("creator@example.com").fill("fit@example.com");
    await page.getByPlaceholder("e.g. fitness, humor, beauty").fill("fitness");
    await page.getByPlaceholder("vip, tier1, usa").fill("workout, cardio");

    // Select Runtime (which also derives device)
    await page.locator("select").filter({ hasText: "Unassigned" }).selectOption("1");
    await expect(page.getByText("Pixel 6 Device 10")).toBeVisible();

    // Open metrics snapshot
    await page.getByRole("button", { name: /Follower & Engagement Metrics/i }).click();
    await page.getByPlaceholder("0", { exact: false }).nth(0).fill("5200");
    await page.getByPlaceholder("0", { exact: false }).nth(2).fill("18500");

    // Submit
    await modal.getByRole("button", { name: "Register Account" }).click();

    // Modal closes and new account appears in table
    await expect(modal).not.toBeVisible();
    const row = page.locator("tr", { hasText: "Fitness Daily Pro" });
    await expect(row.getByText("@fitnesspro")).toBeVisible();
    await expect(row.getByText("Redroid 01")).toBeVisible();
  });

  test("6. Edits an existing account and unarchives an account", async ({ page }) => {
    await page.goto("/accounts");

    // Edit Dance Star Studio
    await page.getByRole("button", { name: "Edit account Dance Star Studio" }).click();

    const editModal = page.getByRole("dialog");
    await expect(editModal).toBeVisible();
    await expect(editModal.getByRole("heading", { name: /Edit Account/i })).toBeVisible();

    // Modify niche and notes
    const nicheInput = editModal.locator('input[placeholder="e.g. fitness, humor, gaming"]');
    await nicheInput.fill("hiphop-dance");

    await editModal.getByRole("button", { name: "Save Changes" }).click();
    await expect(editModal).not.toBeVisible();

    await expect(page.getByText("hiphop-dance")).toBeVisible();

    // Now test restoring an archived account
    await page.getByRole("checkbox", { name: /Include Archived/i }).check();
    await expect(page.getByText("Old Abandoned Brand", { exact: true })).toBeVisible();

    await page.getByRole("button", { name: "Edit account Old Abandoned Brand" }).click();
    await expect(editModal).toBeVisible();
    await expect(page.getByText("This account is currently soft-archived")).toBeVisible();

    // Change status from Archived to Active
    await editModal.locator("select").first().selectOption("active");
    await editModal.getByRole("button", { name: "Save Changes" }).click();
    await expect(editModal).not.toBeVisible();

    // Old Abandoned Brand now has Active badge
    await expect(page.getByText("Old Abandoned Brand", { exact: true })).toBeVisible();
  });

  test("7. Assigns and unassigns runtime with visual hierarchy Account -> Runtime -> Device", async ({
    page,
  }) => {
    await page.goto("/accounts");

    // Gaming Highlights is unassigned
    await page.getByRole("button", { name: "Assign Runtime for Gaming Highlights" }).click();

    const assignModal = page.getByRole("dialog");
    await expect(assignModal).toBeVisible();
    await expect(assignModal.getByRole("heading", { name: "Runtime & Device Assignment" })).toBeVisible();

    // Hierarchy breadcrumb shows unassigned
    await expect(assignModal.getByText("Authoritative Hierarchy")).toBeVisible();
    await expect(assignModal.getByText("No Runtime")).toBeVisible();

    // Select Redroid 02
    await page.locator("#assignRuntimeSelect").selectOption("2");
    await expect(assignModal.locator("strong", { hasText: "Galaxy S21 Device 20" })).toBeVisible();

    // Confirm assignment
    await assignModal.getByRole("button", { name: "Assign Runtime" }).click();
    await expect(assignModal).not.toBeVisible();

    // Table now shows Redroid 02 for Gaming Highlights
    const row = page.locator("tr", { hasText: "Gaming Highlights" });
    await expect(row.getByText("Redroid 02")).toBeVisible();
    await expect(row.getByText("Galaxy S21 Device 20")).toBeVisible();

    // Now test unassign
    await row.getByRole("button", { name: "Assign Runtime for Gaming Highlights" }).click();
    await expect(assignModal).toBeVisible();
    await assignModal.getByRole("button", { name: "Unassign Runtime" }).click();
    await expect(assignModal).not.toBeVisible();

    // Table reflects Unassigned
    await expect(row.getByText("Unassigned")).toBeVisible();
  });

  test("8. Manages write-only credentials: never reveals values, clears input, allows replace & delete", async ({
    page,
  }) => {
    await page.goto("/accounts");

    // Open secrets modal for Dance Star Studio
    await page.getByRole("button", { name: "Manage credentials for Dance Star Studio" }).click();

    const secretsModal = page.getByRole("dialog");
    await expect(secretsModal).toBeVisible();
    await expect(secretsModal.getByRole("heading", { name: /Credentials & Secrets Control/i })).toBeVisible();

    // Encryption guarantee banner is visible
    await expect(
      secretsModal.getByText(
        "Credentials are encrypted at rest and are never returned by the API."
      ).first()
    ).toBeVisible();

    // Verify Secret Types listed
    await expect(secretsModal.getByText("Account Password", { exact: true })).toBeVisible();
    await expect(secretsModal.getByText("Email Password", { exact: true })).toBeVisible();
    await expect(secretsModal.getByText("Recovery Credential", { exact: true })).toBeVisible();

    // Account Password and Email Password are Configured; Recovery Credential is Not Set
    const recoveryCard = secretsModal.locator("div.rounded-xl", { hasText: "Recovery Credential" });
    await expect(recoveryCard.getByText("Not Set")).toBeVisible();

    // Configure Recovery Credential
    await recoveryCard.getByRole("button", { name: "Configure" }).click();

    const secretInput = secretsModal.locator('input[type="password"]');
    await expect(secretInput).toBeVisible();
    await secretInput.fill("super-recovery-key-999");

    // Toggle reveal character
    await secretsModal.getByTitle("Show characters").click();
    await expect(secretsModal.locator('input[type="text"]')).toBeVisible();

    // Save credential
    await secretsModal.getByRole("button", { name: "Save Credential" }).click();

    // Success notification
    await expect(secretsModal.getByText("Recovery Credential saved securely.")).toBeVisible();

    // Input must be completely cleared and closed from the DOM
    await expect(secretInput).not.toBeVisible();

    // Recovery Credential is now Configured
    await expect(recoveryCard.getByText("Configured")).toBeVisible();

    // Delete a credential: delete Email Password
    const emailCard = secretsModal.locator("div.rounded-xl", { hasText: "Email Password" });
    await emailCard.getByRole("button", { name: "Delete Email Password" }).click();

    // Inline confirmation appears
    await expect(
      secretsModal.getByText("Are you sure you want to delete Email Password?")
    ).toBeVisible();

    // Confirm deletion
    await secretsModal.getByRole("button", { name: "Confirm Delete" }).click();
    await expect(secretsModal.getByText("Email Password removed.")).toBeVisible();
    await expect(emailCard.getByText("Not Set")).toBeVisible();

    // Close modal
    await secretsModal.getByRole("button", { name: "Done" }).click();
    await expect(secretsModal).not.toBeVisible();
  });

  test("9. Handles backend API failure gracefully with Retry button", async ({ page }) => {
    simulateListError = true;
    await page.goto("/accounts");

    // Shows error banner
    await expect(page.getByText(/Failed to load accounts/i)).toBeVisible();
    await expect(page.getByRole("button", { name: "Retry" })).toBeVisible();

    // Turn off error simulation and click Retry
    simulateListError = false;
    await page.getByRole("button", { name: "Retry" }).click();

    // Table reloads successfully
    await expect(page.getByText("Dance Star Studio")).toBeVisible();
  });
});

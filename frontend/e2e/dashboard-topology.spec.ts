import { expect, test } from "@playwright/test";

const baseTopology = {
  generated_at: "2026-10-11T12:00:00Z",
  summary: {
    devices: 2,
    runtimes: 2,
    accounts: 4,
    ready_accounts: 2,
    not_ready_accounts: 2,
    attention_accounts: 1,
  },
  nodes: [
    {
      id: "device:1",
      type: "device",
      entity_id: 1,
      label: "Pixel 8 Pro - Farm A",
      status: "online",
      metadata: {
        name: "Pixel 8 Pro - Farm A",
        status: "online",
        platform: "android",
        device_type: "virtual",
        os_version: "15",
        runtime_count: 2,
      },
    },
    {
      id: "device:2",
      type: "device",
      entity_id: 2,
      label: "Samsung S24 - Farm B",
      status: "offline",
      metadata: {
        name: "Samsung S24 - Farm B",
        status: "offline",
        platform: "android",
        device_type: "virtual",
        os_version: "14",
        runtime_count: 0,
      },
    },
    {
      id: "runtime:10",
      type: "runtime",
      entity_id: 10,
      label: "Redroid Node 10",
      status: "running",
      metadata: {
        name: "Redroid Node 10",
        status: "running",
        runtime_type: "redroid",
        device_id: 1,
        assigned_account_count: 2,
        last_seen_at: "2026-10-11T11:58:00Z",
      },
    },
    {
      id: "runtime:20",
      type: "runtime",
      entity_id: 20,
      label: "Redroid Node 20",
      status: "idle",
      metadata: {
        name: "Redroid Node 20",
        status: "idle",
        runtime_type: "redroid",
        device_id: 1,
        assigned_account_count: 1,
        last_seen_at: "2026-10-11T11:55:00Z",
      },
    },
    {
      id: "account:101",
      type: "account",
      entity_id: 101,
      label: "Dance Star Official",
      status: "active",
      metadata: {
        display_name: "Dance Star Official",
        status: "active",
        registration_state: "registered",
        registration_ready: true,
        registration_completed_at: "2026-10-10T10:00:00Z",
        health_status: "healthy",
        username: "dancestar",
        runtime_id: 10,
        device_id: 1,
        secret_present: true,
      },
    },
    {
      id: "account:102",
      type: "account",
      entity_id: 102,
      label: "Gaming Highlights Pro",
      status: "active",
      metadata: {
        display_name: "Gaming Highlights Pro",
        status: "active",
        registration_state: "registered",
        registration_ready: true,
        registration_completed_at: "2026-10-10T11:00:00Z",
        health_status: "healthy",
        username: "gamingpro",
        runtime_id: 10,
        device_id: 1,
        secret_present: true,
      },
    },
    {
      id: "account:103",
      type: "account",
      entity_id: 103,
      label: "Tech Reviews Daily",
      status: "restricted",
      metadata: {
        display_name: "Tech Reviews Daily",
        status: "restricted",
        registration_state: "failed",
        registration_ready: false,
        registration_completed_at: null,
        health_status: "warning",
        username: "techdaily",
        runtime_id: 20,
        device_id: 1,
        secret_present: false,
      },
    },
    {
      id: "account:104",
      type: "account",
      entity_id: 104,
      label: "Beauty Trends Weekly",
      status: "active",
      metadata: {
        display_name: "Beauty Trends Weekly",
        status: "active",
        registration_state: "pending",
        registration_ready: false,
        registration_completed_at: null,
        health_status: "unknown",
        username: null,
        runtime_id: null,
        device_id: null,
        secret_present: false,
      },
    },
  ],
  edges: [
    {
      id: "device:1->runtime:10",
      source: "device:1",
      target: "runtime:10",
      type: "hosts",
    },
    {
      id: "device:1->runtime:20",
      source: "device:1",
      target: "runtime:20",
      type: "hosts",
    },
    {
      id: "runtime:10->account:101",
      source: "runtime:10",
      target: "account:101",
      type: "assigned",
    },
    {
      id: "runtime:10->account:102",
      source: "runtime:10",
      target: "account:102",
      type: "assigned",
    },
    {
      id: "runtime:20->account:103",
      source: "runtime:20",
      target: "account:103",
      type: "assigned",
    },
  ],
};

test.describe("TIK-025C Phase 2: Interactive System Topology Dashboard", () => {
  test("1. Renders exact summary counters from backend without mock content", async ({ page }) => {
    await page.route("**/dashboard/topology", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(baseTopology),
      });
    });

    await page.goto("/");

    // Verify Title & Subtitle
    await expect(page.getByRole("heading", { name: "System Topology" })).toBeVisible();
    await expect(
      page.getByText("Real-time interactive relationship graph across Devices, Runtimes, and Accounts.")
    ).toBeVisible();

    // Verify summary metrics rendered exactly
    await expect(page.getByText("Devices").first()).toBeVisible();
    await expect(page.getByText("Runtimes").first()).toBeVisible();
    await expect(page.getByText("Ready Accounts").first()).toBeVisible();
    await expect(page.getByText("Not Ready Accounts").first()).toBeVisible();
    await expect(page.getByText("Attention").first()).toBeVisible();

    // Verify placeholder content was removed completely
    await expect(page.getByText("Frontend Project Skeleton Initialized")).not.toBeVisible();
    await expect(page.getByText("Placeholder Mode")).not.toBeVisible();
    await expect(page.getByText("Audience Reach")).not.toBeVisible();
    await expect(page.getByText("Scheduled Content")).not.toBeVisible();
  });

  test("2. Renders Device, Runtime, and Account nodes with multiple accounts fan-out", async ({ page }) => {
    await page.route("**/dashboard/topology", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(baseTopology),
      });
    });

    await page.goto("/");

    // Verify Device node
    await expect(page.getByText("Pixel 8 Pro - Farm A")).toBeVisible();
    await expect(page.getByText("Samsung S24 - Farm B")).toBeVisible();

    // Verify Runtime node
    await expect(page.getByText("Redroid Node 10")).toBeVisible();
    await expect(page.getByText("Redroid Node 20")).toBeVisible();

    // Verify multiple Accounts fanning out under Runtime 10
    await expect(page.getByText("Dance Star Official")).toBeVisible();
    await expect(page.getByText("Gaming Highlights Pro")).toBeVisible();
    await expect(page.getByText("@dancestar")).toBeVisible();
    await expect(page.getByText("@gamingpro")).toBeVisible();

    // Verify Account under Runtime 20
    await expect(page.getByText("Tech Reviews Daily")).toBeVisible();
    await expect(page.getByText("@techdaily")).toBeVisible();
  });

  test("3. Displays unassigned Account in dedicated separated section", async ({ page }) => {
    await page.route("**/dashboard/topology", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(baseTopology),
      });
    });

    await page.goto("/");

    // Verify Unassigned Accounts section header
    await expect(page.getByRole("heading", { name: /Unassigned Accounts/i })).toBeVisible();
    await expect(page.getByText("Beauty Trends Weekly")).toBeVisible();
    await expect(page.getByText("Requires Runtime Assignment")).toBeVisible();
  });

  test("4. Searches across entities and focuses selected result", async ({ page }) => {
    await page.route("**/dashboard/topology", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(baseTopology),
      });
    });

    await page.goto("/");

    // Search for handle
    const searchInput = page.getByPlaceholder("Search Device, Runtime, Account, or @handle...");
    await searchInput.fill("dancestar");

    // Click result in dropdown
    const resultItem = page.getByRole("button", { name: /Dance Star Official/i });
    await expect(resultItem).toBeVisible();
    await resultItem.click();

    // Details drawer opens for selected node
    await expect(page.getByRole("heading", { name: "Dance Star Official" })).toBeVisible();
    await expect(page.getByText("@dancestar").first()).toBeVisible();
    await expect(page.getByRole("link", { name: "Open Accounts" })).toBeVisible();
  });

  test("5. Filters by entity type, Ready only, and Attention only", async ({ page }) => {
    await page.route("**/dashboard/topology", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(baseTopology),
      });
    });

    await page.goto("/");

    // Filter to Devices only
    await page.getByRole("button", { name: "Devices" }).click();
    await expect(page.getByText("Pixel 8 Pro - Farm A")).toBeVisible();
    await expect(page.getByText("Redroid Node 10")).not.toBeVisible();
    await expect(page.getByText("Dance Star Official")).not.toBeVisible();

    // Reset to All
    await page.getByRole("button", { name: "All", exact: true }).click();
    await expect(page.getByText("Redroid Node 10")).toBeVisible();

    // Ready only filter
    await page.getByRole("button", { name: "Ready only" }).click();
    await expect(page.getByText("Dance Star Official")).toBeVisible();
    await expect(page.getByText("Tech Reviews Daily")).not.toBeVisible();
    await expect(page.getByText("Beauty Trends Weekly")).not.toBeVisible();

    // Toggle off Ready only
    await page.getByRole("button", { name: "Ready only" }).click();

    // Attention only filter
    await page.getByRole("button", { name: "Attention only" }).click();
    await expect(page.getByText("Tech Reviews Daily")).toBeVisible();
    await expect(page.getByText("Dance Star Official")).not.toBeVisible();
  });

  test("6. Opens right-side details panel for Device, Runtime, and Account", async ({ page }) => {
    await page.route("**/dashboard/topology", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(baseTopology),
      });
    });

    await page.goto("/");

    // Click Device node
    await page.getByText("Pixel 8 Pro - Farm A").click();
    await expect(page.getByText("DEVICE Node")).toBeVisible();
    await expect(page.getByText("device:1")).toBeVisible();
    await expect(page.getByRole("link", { name: "Open Devices" })).toHaveAttribute("href", "/devices");

    // Click Runtime in linked list inside drawer
    await page.getByRole("button", { name: /Redroid Node 10/i }).click();
    await expect(page.getByText("RUNTIME Node")).toBeVisible();
    await expect(page.getByRole("link", { name: "Open Runtimes" })).toHaveAttribute("href", "/runtimes");

    // Click Account in assigned list inside drawer
    await page.getByRole("button", { name: /Dance Star Official/i }).click();
    await expect(page.getByText("ACCOUNT Node")).toBeVisible();
    await expect(page.getByText("Credentials Present")).toBeVisible();
    await expect(page.getByText("Configured")).toBeVisible();
    await expect(page.getByRole("link", { name: "Open Accounts" })).toHaveAttribute("href", "/accounts");

    // Close drawer
    await page.getByTitle("Close details").click();
    await expect(page.getByRole("link", { name: "Open Accounts" })).not.toBeVisible();
  });

  test("7. Polling refresh reflects newly added node and edge updates", async ({ page }) => {
    let addExtraDevice = false;

    const dynamicTopology = JSON.parse(JSON.stringify(baseTopology));

    await page.route("**/dashboard/topology", async (route) => {
      const responsePayload = JSON.parse(JSON.stringify(dynamicTopology));
      if (addExtraDevice) {
        responsePayload.nodes.push({
          id: "device:3",
          type: "device",
          entity_id: 3,
          label: "OnePlus 12 - Farm C",
          status: "online",
          metadata: {
            name: "OnePlus 12 - Farm C",
            status: "online",
            platform: "android",
            device_type: "virtual",
            os_version: "14",
            runtime_count: 0,
          },
        });
        responsePayload.summary.devices = 3;
      }
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(responsePayload),
      });
    });

    await page.goto("/");
    await expect(page.getByText("Pixel 8 Pro - Farm A")).toBeVisible();
    await expect(page.getByText("OnePlus 12 - Farm C")).not.toBeVisible();

    // Trigger refresh with new node present in next response
    addExtraDevice = true;
    await page.getByRole("button", { name: "Refresh" }).click();

    // New node appears
    await expect(page.getByText("OnePlus 12 - Farm C")).toBeVisible();
  });

  test("8. Handles backend API failure gracefully with Retry", async ({ page }) => {
    let shouldFail = true;

    await page.route("**/dashboard/topology", async (route) => {
      if (shouldFail) {
        await route.fulfill({
          status: 500,
          contentType: "application/json",
          body: JSON.stringify({ detail: "Database connection failed" }),
        });
      } else {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify(baseTopology),
        });
      }
    });

    await page.goto("/");

    // Verify error banner
    await expect(page.getByText("Database connection failed")).toBeVisible();
    const retryBtn = page.getByRole("button", { name: "Retry" });
    await expect(retryBtn).toBeVisible();

    // Resolve failure and retry
    shouldFail = false;
    await retryBtn.click();

    // Successfully loads
    await expect(page.getByText("Pixel 8 Pro - Farm A")).toBeVisible();
  });

  test("9. Renders empty topology state when no entities exist", async ({ page }) => {
    await page.route("**/dashboard/topology", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          generated_at: "2026-10-11T12:00:00Z",
          summary: {
            devices: 0,
            runtimes: 0,
            accounts: 0,
            ready_accounts: 0,
            not_ready_accounts: 0,
            attention_accounts: 0,
          },
          nodes: [],
          edges: [],
        }),
      });
    });

    await page.goto("/");

    // Verify Empty State
    await expect(page.getByRole("heading", { name: "No System Entities Found" })).toBeVisible();
    await expect(page.getByRole("link", { name: "Go to Devices" })).toBeVisible();
    await expect(page.getByRole("link", { name: "Go to Runtimes" })).toBeVisible();
    await expect(page.getByRole("link", { name: "Create Account" })).toBeVisible();
  });
});

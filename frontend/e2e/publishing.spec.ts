import { expect, Page, test } from "@playwright/test";

const now = "2026-10-06T10:00:00Z";

const device = {
  id: 31,
  name: "Redroid Device 31",
  device_type: "emulator",
  platform: "android",
  os_version: "12",
  status: "online",
  notes: null,
  created_at: now,
  updated_at: now,
};

const runtime41 = {
  id: 41,
  device_id: 31,
  name: "Managed Runtime 41",
  runtime_type: "redroid",
  status: "running",
  adb_serial: "localhost:5599",
  docker_container_name: "redroid-device-41",
  last_seen_at: now,
  created_at: now,
  updated_at: now,
};

const runtime99 = {
  id: 99,
  device_id: 31,
  name: "Managed Runtime 99",
  runtime_type: "redroid",
  status: "running",
  adb_serial: "localhost:5598",
  docker_container_name: "redroid-device-99",
  last_seen_at: now,
  created_at: now,
  updated_at: now,
};

const account1 = {
  id: 101,
  username: "@creator_alpha",
  display_name: "Creator Alpha",
  status: "active",
  runtime_id: 41,
  created_at: now,
  updated_at: now,
};

const account2 = {
  id: 102,
  username: "@creator_beta",
  display_name: "Creator Beta",
  status: "active",
  runtime_id: 99, // Mismatched with Runtime 41
  created_at: now,
  updated_at: now,
};

const contentVersion = {
  id: 71,
  version_number: 1,
  original_filename: "promo_alpha.mp4",
  detected_mime_type: "video/mp4",
  canonical_extension: ".mp4",
  processing_status: "ready",
  size_bytes: 5242880,
  sha256: "b".repeat(64),
  width: 1080,
  height: 1920,
  duration_ms: 15000,
  codec: "h264",
  container: "mp4",
  frame_rate_numerator: 30,
  frame_rate_denominator: 1,
  audio_present: true,
  bitrate: 2800000,
  sample_rate: 44100,
  channels: 2,
  orientation: "portrait",
  created_at: now,
  processed_at: now,
  metadata: {},
};

const contentAsset = {
  id: 51,
  asset_type: "video",
  display_name: "Promo Video Alpha",
  notes: null,
  source: "upload",
  status: "ready",
  tags: ["promo"],
  current_version: contentVersion,
  current_version_id: 71,
  thumbnail_available: true,
  created_at: now,
  updated_at: now,
  archived_at: null,
  deleted_at: null,
  total_deliveries: 1,
  latest_delivery_status: "succeeded",
  last_successful_delivery_at: now,
  versions: [contentVersion],
};

const templates = [
  {
    key: "publishing_prepare_review",
    version: 1,
    label: "Publishing Preparation & Review",
    description: "Verify runtime and managed app, stage content, launch app, and request operator approval.",
    required_bindings: [
      "account",
      "runtime",
      "content_asset_version",
      "managed_app",
      "managed_app_version",
    ],
    parameters_schema: {
      type: "object",
      properties: {
        import_media: { type: "boolean", default: true },
      },
    },
  },
];

interface MockAppVersion {
  id: number;
  managed_app_id: number;
  version_number: number;
  version_code: number;
  version_name: string;
  file_size_bytes: number;
  sha256: string;
  min_sdk: number | null;
  target_sdk: number | null;
  status: string;
  admission_status: string;
  basic_approved: boolean;
  basic_approved_at: string | null;
  basic_approved_by: string | null;
  inspection_level: string;
  package_verification: string;
  is_current: boolean;
  created_at: string;
  updated_at: string;
}

interface MockManagedApp {
  id: number;
  key: string;
  display_name: string;
  android_package_name: string;
  install_policy: "required" | "optional" | "disabled";
  status: "active" | "deprecated" | "disabled";
  description: string | null;
  current_version_id: number | null;
  version_count: number;
  created_at: string;
  updated_at: string;
}

let appVersions: MockAppVersion[] = [];
let managedAppsList: MockManagedApp[] = [];
let sessionsList: Record<string, unknown>[] = [];
let workflowsList: Record<string, unknown>[] = [];
let submittedWorkflowRequests: Record<string, unknown>[] = [];

function initMockData() {
  appVersions = [
    {
      id: 201,
      managed_app_id: 1,
      version_number: 1,
      version_code: 320400,
      version_name: "32.4.0",
      file_size_bytes: 85000000,
      sha256: "1111111111111111111111111111111111111111111111111111111111111111",
      min_sdk: 26,
      target_sdk: 34,
      status: "ready",
      admission_status: "admitted",
      basic_approved: true,
      basic_approved_at: now,
      basic_approved_by: "operator",
      inspection_level: "verified",
      package_verification: "verified",
      is_current: false,
      created_at: now,
      updated_at: now,
    },
    {
      id: 202,
      managed_app_id: 1,
      version_number: 2,
      version_code: 320504,
      version_name: "32.5.4",
      file_size_bytes: 88000000,
      sha256: "2222222222222222222222222222222222222222222222222222222222222222",
      min_sdk: 26,
      target_sdk: 34,
      status: "ready",
      admission_status: "uploaded",
      basic_approved: false,
      basic_approved_at: null,
      basic_approved_by: null,
      inspection_level: "basic",
      package_verification: "pending",
      is_current: true,
      created_at: now,
      updated_at: now,
    },
  ];

  managedAppsList = [
    {
      id: 1,
      key: "tiktok",
      display_name: "TikTok Global",
      android_package_name: "com.zhiliaoapp.musically",
      install_policy: "required",
      status: "active",
      description: "Official TikTok client",
      current_version_id: 202,
      version_count: 2,
      created_at: now,
      updated_at: now,
    },
  ];

  const wfSteps = [
    {
      id: 301,
      step_index: 0,
      step_key: "verify_runtime",
      step_type: "publishing.verify_runtime",
      status: "succeeded",
      depends_on_step_id: null,
      job_id: 501,
      attempt: 1,
      max_attempts: 1,
      result_json: { runtime_ready: true },
      waiting_reason: null,
      approval_decision: null,
      started_at: now,
      completed_at: now,
    },
    {
      id: 302,
      step_index: 1,
      step_key: "verify_app",
      step_type: "publishing.verify_app",
      status: "succeeded",
      depends_on_step_id: 301,
      job_id: 502,
      attempt: 1,
      max_attempts: 1,
      result_json: { app_ready: true },
      waiting_reason: null,
      approval_decision: null,
      started_at: now,
      completed_at: now,
    },
    {
      id: 303,
      step_index: 2,
      step_key: "deliver_media",
      step_type: "content.deliver",
      status: "succeeded",
      depends_on_step_id: 302,
      job_id: 503,
      attempt: 1,
      max_attempts: 1,
      result_json: { delivery_id: 10 },
      waiting_reason: null,
      approval_decision: null,
      started_at: now,
      completed_at: now,
    },
    {
      id: 304,
      step_index: 3,
      step_key: "launch_app",
      step_type: "device.launch_app",
      status: "succeeded",
      depends_on_step_id: 303,
      job_id: 504,
      attempt: 1,
      max_attempts: 1,
      result_json: { launched: true },
      waiting_reason: null,
      approval_decision: null,
      started_at: now,
      completed_at: now,
    },
    {
      id: 305,
      step_index: 4,
      step_key: "verify_app_state",
      step_type: "publishing.verify_app_state",
      status: "succeeded",
      depends_on_step_id: 304,
      job_id: 505,
      attempt: 1,
      max_attempts: 1,
      result_json: { foreground: true },
      waiting_reason: null,
      approval_decision: null,
      started_at: now,
      completed_at: now,
    },
    {
      id: 306,
      step_index: 5,
      step_key: "operator_approval",
      step_type: "workflow.approval",
      status: "waiting",
      depends_on_step_id: 305,
      job_id: null,
      attempt: 1,
      max_attempts: 1,
      result_json: null,
      waiting_reason: "waiting_for_approval",
      approval_decision: null,
      started_at: now,
      completed_at: null,
    },
  ];

  workflowsList = [
    {
      id: 201,
      name: "TikTok Preparation Workflow",
      description: "Auto-generated workflow for publishing session #1",
      template_key: "publishing_prepare_review",
      template_version: 1,
      status: "waiting",
      parameters: { import_media: true },
      account_id: 101,
      runtime_id: 41,
      runtime_id_snapshot: 41,
      content_asset_id: 51,
      content_asset_version_id: 71,
      managed_app_id: 1,
      managed_app_version_id: 202,
      current_step_id: 306,
      pause_requested_at: null,
      cancel_requested_at: null,
      created_at: now,
      updated_at: now,
      started_at: now,
      completed_at: null,
      cancelled_at: null,
      error_code: null,
      error_message: null,
      steps: wfSteps,
    },
  ];

  sessionsList = [
    {
      id: 1,
      workflow_id: 201,
      account_id_snapshot: 101,
      runtime_id_snapshot: 41,
      content_asset_id: 51,
      content_asset_version_id: 71,
      managed_app_id: 1,
      managed_app_version_id: 202,
      status: "waiting_approval",
      created_at: now,
      started_at: now,
      completed_at: null,
      error_code: null,
      error_message: null,
      workflow: workflowsList[0],
    },
  ];

  submittedWorkflowRequests = [];
}

async function installApi(page: Page) {
  await page.route("http://127.0.0.1:8000/**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname;
    const json = (body: unknown, status = 200) =>
      route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });

    // Workflow templates
    if (path === "/workflow-templates") return json(templates);

    // Runtimes & Devices
    if (path === "/runtimes") return json({ items: [runtime41, runtime99], total: 2, page: 1, page_size: 100 });
    if (path === "/runtimes/41") return json(runtime41);
    if (path === "/runtimes/99") return json(runtime99);
    if (path === "/devices") return json({ items: [device], total: 1, page: 1, page_size: 100 });

    // Accounts
    if (path === "/accounts") return json({ items: [account1, account2], total: 2, page: 1, page_size: 100 });

    // Content
    if (path === "/content") return json({ items: [contentAsset], total: 1, page: 1, page_size: 100 });
    if (path === "/content/51") return json(contentAsset);

    // Managed Apps CRUD
    if (path === "/managed-apps" && request.method() === "GET") {
      return json({ items: managedAppsList, total: managedAppsList.length, page: 1, page_size: 100 });
    }
    if (path === "/managed-apps" && request.method() === "POST") {
      const body = request.postDataJSON() as Record<string, unknown>;
      const newApp: MockManagedApp = {
        id: managedAppsList.length + 1,
        key: String(body.key),
        display_name: String(body.display_name),
        android_package_name: String(body.android_package_name),
        install_policy: (body.install_policy as "required" | "optional" | "disabled") || "optional",
        status: "active",
        description: (body.description as string) || null,
        current_version_id: null,
        version_count: 0,
        created_at: now,
        updated_at: now,
      };
      managedAppsList.push(newApp);
      return json({ ...newApp, versions: [] }, 201);
    }

    const appMatch = path.match(/^\/managed-apps\/(\d+)$/);
    if (appMatch) {
      const appId = Number(appMatch[1]);
      const app = managedAppsList.find((a) => a.id === appId);
      if (!app) return json({ detail: "App not found" }, 404);

      if (request.method() === "GET") {
        return json({ ...app, versions: appVersions.filter((v) => v.managed_app_id === appId) });
      }
      if (request.method() === "PATCH") {
        const body = request.postDataJSON() as Record<string, unknown>;
        if (body.display_name) app.display_name = String(body.display_name);
        if (body.install_policy) app.install_policy = body.install_policy as "required" | "optional" | "disabled";
        if (body.status) app.status = body.status as "active" | "deprecated" | "disabled";
        return json({ ...app, versions: appVersions.filter((v) => v.managed_app_id === appId) });
      }
    }

    // App versions
    const versionsMatch = path.match(/^\/managed-apps\/(\d+)\/versions$/);
    if (versionsMatch) {
      const appId = Number(versionsMatch[1]);
      const versions = appVersions.filter((v) => v.managed_app_id === appId);
      return json({ items: versions, total: versions.length, page: 1, page_size: 100 });
    }

    // Basic Approval
    const approveBasicMatch = path.match(/^\/managed-apps\/(\d+)\/versions\/(\d+)\/approve-basic$/);
    if (approveBasicMatch && request.method() === "POST") {
      const versionId = Number(approveBasicMatch[2]);
      const ver = appVersions.find((v) => v.id === versionId);
      if (ver) {
        ver.basic_approved = true;
        ver.basic_approved_at = now;
        ver.admission_status = "admitted";
      }
      return json(ver);
    }

    // Version Activation
    const activateMatch = path.match(/^\/managed-apps\/(\d+)\/versions\/(\d+)\/activate$/);
    if (activateMatch && request.method() === "POST") {
      const appId = Number(activateMatch[1]);
      const versionId = Number(activateMatch[2]);
      appVersions.forEach((v) => {
        if (v.managed_app_id === appId) v.is_current = v.id === versionId;
      });
      const app = managedAppsList.find((a) => a.id === appId);
      if (app) app.current_version_id = versionId;
      return json({ ...app, versions: appVersions.filter((v) => v.managed_app_id === appId) });
    }

    // Version Retirement
    const retireMatch = path.match(/^\/managed-apps\/(\d+)\/versions\/(\d+)\/retire$/);
    if (retireMatch && request.method() === "POST") {
      const versionId = Number(retireMatch[2]);
      const ver = appVersions.find((v) => v.id === versionId);
      if (ver) ver.status = "retired";
      return json(ver);
    }

    // Runtime Apps & Publishing Readiness
    if (path === "/runtimes/41/publishing-readiness") {
      return json({
        runtime_ready: true,
        required_apps_ready: true,
        publishing_ready: true,
        required_count: 1,
        installed_count: 1,
        pending_count: 0,
        failed_count: 0,
        outdated_count: 0,
      });
    }

    if (path === "/runtimes/41/apps" && request.method() === "GET") {
      return json({
        runtime_id: 41,
        items: [
          {
            id: 1,
            runtime_id: 41,
            runtime_id_snapshot: 41,
            managed_app_id: 1,
            desired_managed_app_version_id: 202,
            observed_managed_app_version_id: 202,
            status: "installed",
            observed_version_name: "32.5.4",
            observed_version_code: 320504,
            observed_package_name: "com.zhiliaoapp.musically",
            observed_signer_fingerprint: "aa".repeat(32),
            latest_job_id: 501,
            installed_at: now,
            verified_at: now,
            last_attempt_at: now,
            error_code: null,
            error_message: null,
            created_at: now,
            updated_at: now,
          },
        ],
      });
    }

    if (path === "/runtimes/41/apps/1/install" && request.method() === "POST") {
      return json({ job_id: 506, status: "pending" });
    }

    if (path === "/runtimes/41/apps/1/verify" && request.method() === "POST") {
      return json({ job_id: 507, status: "pending" });
    }

    // Publishing Sessions
    if (path === "/publishing-sessions" && request.method() === "GET") {
      return json({ items: sessionsList, total: sessionsList.length, page: 1, page_size: 100 });
    }

    const sessionMatch = path.match(/^\/publishing-sessions\/(\d+)$/);
    if (sessionMatch) {
      const sessId = Number(sessionMatch[1]);
      const sess = sessionsList.find((s) => (s as { id: number }).id === sessId);
      if (sess) return json(sess);
      return json({ detail: "Session not found" }, 404);
    }

    // Workflows
    if (path === "/workflows" && request.method() === "GET") {
      return json({ items: workflowsList, total: workflowsList.length, page: 1, page_size: 20 });
    }

    if (path === "/workflows" && request.method() === "POST") {
      const input = request.postDataJSON() as Record<string, unknown>;
      submittedWorkflowRequests.push(input);

      const newWfId = workflowsList.length + 201;
      const newSessionId = sessionsList.length + 1;

      const createdWorkflow = {
        id: newWfId,
        name: String(input.name || "Publishing Workflow"),
        description: String(input.description || ""),
        template_key: String(input.template_key),
        template_version: Number(input.template_version || 1),
        status: "running",
        parameters: (input.parameters as Record<string, unknown>) || {},
        account_id: Number(input.account_id),
        runtime_id: Number(input.runtime_id),
        runtime_id_snapshot: Number(input.runtime_id),
        content_asset_id: Number(input.content_asset_id),
        content_asset_version_id: Number(input.content_asset_version_id),
        managed_app_id: Number(input.managed_app_id),
        managed_app_version_id: Number(input.managed_app_version_id),
        current_step_id: 401,
        pause_requested_at: null,
        cancel_requested_at: null,
        created_at: now,
        updated_at: now,
        started_at: now,
        completed_at: null,
        cancelled_at: null,
        error_code: null,
        error_message: null,
        steps: [
          {
            id: 401,
            step_index: 0,
            step_key: "verify_runtime",
            step_type: "publishing.verify_runtime",
            status: "running",
            depends_on_step_id: null,
            job_id: 601,
            attempt: 1,
            max_attempts: 1,
            result_json: null,
            waiting_reason: null,
            approval_decision: null,
            started_at: now,
            completed_at: null,
          },
        ],
      };

      workflowsList.unshift(createdWorkflow);

      const createdSession = {
        id: newSessionId,
        workflow_id: newWfId,
        account_id_snapshot: Number(input.account_id),
        runtime_id_snapshot: Number(input.runtime_id),
        content_asset_id: Number(input.content_asset_id),
        content_asset_version_id: Number(input.content_asset_version_id),
        managed_app_id: Number(input.managed_app_id),
        managed_app_version_id: Number(input.managed_app_version_id),
        status: "running",
        created_at: now,
        started_at: now,
        completed_at: null,
        error_code: null,
        error_message: null,
        workflow: createdWorkflow,
      };

      sessionsList.unshift(createdSession);

      return json(createdWorkflow, 201);
    }

    const wfDetailMatch = path.match(/^\/workflows\/(\d+)$/);
    if (wfDetailMatch) {
      const wfId = Number(wfDetailMatch[1]);
      const wf = workflowsList.find((w) => (w as { id: number }).id === wfId);
      if (wf) return json(wf);
      return json({ detail: "Workflow not found" }, 404);
    }

    const wfEventsMatch = path.match(/^\/workflows\/(\d+)\/events$/);
    if (wfEventsMatch) {
      return json({
        items: [
          {
            id: 1,
            workflow_id: 201,
            workflow_step_id: 301,
            job_id: 501,
            event_type: "step_succeeded",
            metadata: {},
            created_at: now,
          },
        ],
        total: 1,
        page: 1,
        page_size: 100,
      });
    }

    // Step approval
    const stepApprovalMatch = path.match(/^\/workflows\/(\d+)\/steps\/(\d+)\/(approve|reject)$/);
    if (stepApprovalMatch && request.method() === "POST") {
      const wfId = Number(stepApprovalMatch[1]);
      const stepId = Number(stepApprovalMatch[2]);
      const action = stepApprovalMatch[3];

      const wf = workflowsList.find((w) => (w as { id: number }).id === wfId) as Record<string, unknown> | undefined;
      if (wf) {
        const steps = wf.steps as Record<string, unknown>[];
        const targetStep = steps.find((s) => s.id === stepId);
        if (targetStep) {
          targetStep.status = action === "approve" ? "succeeded" : "failed";
          targetStep.approval_decision = action === "approve" ? "approved" : "rejected";
        }
        wf.status = action === "approve" ? "succeeded" : "failed";
        wf.current_step_id = null;
      }

      const sess = sessionsList.find((s) => (s as { workflow_id: number }).workflow_id === wfId) as
        | Record<string, unknown>
        | undefined;
      if (sess) {
        sess.status = action === "approve" ? "prepared" : "rejected";
        sess.completed_at = now;
      }

      return json(wf);
    }

    // Workflow actions: pause/resume/cancel/retry
    const wfActionMatch = path.match(/^\/workflows\/(\d+)\/(start|pause|resume|cancel|retry)$/);
    if (wfActionMatch && request.method() === "POST") {
      const wfId = Number(wfActionMatch[1]);
      const action = wfActionMatch[2];
      const wf = workflowsList.find((w) => (w as { id: number }).id === wfId) as Record<string, unknown> | undefined;
      if (wf) {
        if (action === "pause") wf.status = "paused";
        if (action === "resume") wf.status = "running";
        if (action === "cancel") wf.status = "cancelled";
        if (action === "retry") wf.status = "pending";
        return json(wf);
      }
    }

    // Jobs
    if (path === "/jobs/501") {
      return json({
        id: 501,
        device_id: 31,
        runtime_id: 41,
        job_type: "device.package_state",
        status: "succeeded",
        priority: 10,
        payload_json: { package: "com.zhiliaoapp.musically" },
        result_json: { is_installed: true },
        created_at: now,
        started_at: now,
        completed_at: now,
        job_logs: [],
        artifacts: [],
      });
    }

    if (path === "/jobs/501/logs") {
      return json({ items: [], total: 0 });
    }

    return json({ detail: "not mocked" }, 404);
  });
}

test.beforeEach(async ({ page }) => {
  initMockData();
  await installApi(page);
});

test("sidebar contains Managed Apps and Publishing navigation links", async ({ page }) => {
  await page.goto("/managed-apps");
  await expect(page.getByRole("link", { name: "Managed Apps" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Publishing" })).toBeVisible();

  // Test navigation to Publishing
  await page.getByRole("link", { name: "Publishing" }).click();
  await expect(page).toHaveURL(/.*\/publishing/);
  await expect(page.getByRole("heading", { name: "Publishing Preparation" })).toBeVisible();

  // Test navigation back to Managed Apps
  await page.getByRole("link", { name: "Managed Apps" }).click();
  await expect(page).toHaveURL(/.*\/managed-apps/);
  await expect(page.getByRole("heading", { name: "Managed Apps" })).toBeVisible();
});

test("managed apps page displays apps list and assurance notice", async ({ page }) => {
  await page.goto("/managed-apps");

  // Assurance banner
  await expect(page.getByText("Safe Package Deployment:")).toBeVisible();
  await expect(page.getByText("Managed apps undergo SHA-256 integrity hashing and manifest validation.")).toBeVisible();

  // Apps table
  await expect(page.getByText("TikTok Global")).toBeVisible();
  await expect(page.getByText("com.zhiliaoapp.musically")).toBeVisible();
  await expect(page.locator("table").getByText("Required")).toBeVisible();
  await expect(page.locator("table").getByText("Active").first()).toBeVisible();
});

test("registers a new managed app via modal", async ({ page }) => {
  await page.goto("/managed-apps");

  await page.getByRole("button", { name: "Add Managed App" }).click();
  await expect(page.getByRole("heading", { name: "Add Managed App" })).toBeVisible();

  await page.getByPlaceholder("e.g. tiktok", { exact: true }).fill("capcut");
  await page.getByPlaceholder("e.g. TikTok Global").fill("CapCut Video Editor");
  await page.getByPlaceholder("e.g. com.zhiliaoapp.musically").fill("com.lemon.lvoverseas");

  await page.getByRole("button", { name: "Create Managed App" }).click();

  // Modal closes and new app appears
  await expect(page.getByText("CapCut Video Editor")).toBeVisible();
  await expect(page.getByText("com.lemon.lvoverseas")).toBeVisible();
});

test("edits a managed app preserving immutable key and package name", async ({ page }) => {
  await page.goto("/managed-apps");

  // Click edit button on the TikTok row
  await page.getByTitle(/Edit /).first().click();
  await expect(page.getByRole("heading", { name: "Edit Managed App" })).toBeVisible();

  // Verify key and package name are disabled / immutable
  const keyInput = page.locator('input[value="tiktok"]');
  await expect(keyInput).toBeDisabled();
  await expect(page.getByText("App key identity is immutable.")).toBeVisible();

  const pkgInput = page.locator('input[value="com.zhiliaoapp.musically"]');
  await expect(pkgInput).toBeDisabled();
  await expect(page.getByText("Package identity cannot be changed after creation.")).toBeVisible();

  // Edit display name
  const nameInput = page.locator('input[value="TikTok Global"]');
  await nameInput.fill("TikTok Global Official");

  await page.getByRole("button", { name: "Save Changes" }).click();

  // Verified updated name in table
  await expect(page.getByText("TikTok Global Official")).toBeVisible();
});

test("inspects app versions and performs basic approval with safety warning", async ({ page }) => {
  await page.goto("/managed-apps");

  // Click Versions on TikTok app
  await page.getByRole("button", { name: "Versions" }).first().click();
  await expect(page.getByRole("heading", { name: "TikTok Global" })).toBeVisible();

  // Verify both versions exist
  await expect(page.getByText("v32.5.4")).toBeVisible();
  await expect(page.getByText("v32.4.0")).toBeVisible();

  // Version 2 has an "Approve Basic" button because it is uploaded/pending
  await page.getByRole("button", { name: "Approve Basic" }).click();

  // Explicit safety warning banner in Basic Approval modal
  await expect(page.getByRole("heading", { name: "Approve Basic Assurance" })).toBeVisible();
  await expect(
    page.getByText("Basic approval means the APK was admitted and hashed, but package/signature assurance is verified after installation.")
  ).toBeVisible();

  // Confirm basic approval
  await page.getByRole("button", { name: "Confirm Basic Approval" }).click();

  // Modal closes and version shows Basic Approved badge
  await expect(page.getByText("Basic Approved").first()).toBeVisible();
  await expect(page.getByText("Version #202 basic assurance approved.")).toBeVisible();
});

test("activates and retires app versions", async ({ page }) => {
  await page.goto("/managed-apps");

  // Open versions modal
  await page.getByRole("button", { name: "Versions" }).first().click();

  // Activate Version 1
  await page.getByRole("button", { name: "Activate" }).click();
  await expect(page.getByText("Version #201 is now active.")).toBeVisible();

  // Retire Version 2
  await page.getByRole("button", { name: "Retire" }).first().click();
  await expect(page.getByText("Retired").first()).toBeVisible();
});

test("opens runtime apps modal and displays publishing readiness breakdown", async ({ page }) => {
  await page.goto("/runtimes");

  // Click Apps button on Runtime 41 row
  await page.getByRole("button", { name: /View apps for/ }).first().click();

  // Runtime Apps modal opens
  await expect(page.getByRole("heading", { name: "Apps & Publishing Readiness" })).toBeVisible();
  await expect(page.getByText("Runtime #41", { exact: false })).toBeVisible();

  // Readiness Status Section
  await expect(page.getByText("Publishing Readiness Status")).toBeVisible();
  await expect(page.getByText("Runtime Lifecycle:")).toBeVisible();
  await expect(page.getByText("Ready (Booted & ADB)")).toBeVisible();
  await expect(page.getByText("All Required Ready")).toBeVisible();
  await expect(page.getByText("Ready to Prepare")).toBeVisible();

  // App Installation row
  await expect(page.getByText("com.zhiliaoapp.musically")).toBeVisible();
  await expect(page.getByText("Installed", { exact: true })).toBeVisible();
  await expect(page.getByText("Verified At:")).toBeVisible();

  // Test Install and Verify actions
  await page.getByRole("button", { name: "Install / Update" }).click();
  await expect(page.getByText("Installation job queued successfully.")).toBeVisible();

  await page.getByRole("button", { name: "Verify" }).click();
  await expect(page.getByText("Verification job queued successfully.")).toBeVisible();
});

test("displays publishing page with safety disclaimer banner", async ({ page }) => {
  await page.goto("/publishing");

  // Prominent Safety Callout
  await expect(page.getByText("Prepared does not mean published.")).toBeVisible();
  await expect(
    page.getByText("Publishing sessions safely verify the device environment, ensure the correct managed app is active, deliver media assets, and launch the application.")
  ).toBeVisible();

  // Session table
  await expect(page.getByText("Session #1")).toBeVisible();
  await expect(page.locator("table").getByText("Waiting Approval")).toBeVisible();
  await expect(page.getByText("Runtime #41")).toBeVisible();
});

test("validates account-runtime mismatch in prepare modal", async ({ page }) => {
  await page.goto("/publishing");

  await page.getByRole("button", { name: "Prepare Publishing" }).click();
  await expect(page.getByRole("heading", { name: "Prepare Publishing Session" })).toBeVisible();

  const form = page.locator("form");

  // Select Account 2 (@creator_beta), which is bound to Runtime 99
  await form.locator("select").first().selectOption("102");

  // Ensure Runtime 41 is selected in the runtime dropdown
  const runtimeSelect = form.locator("select").nth(1);
  await runtimeSelect.selectOption("41");

  // Expect client-side mismatch warning in the form
  await expect(form.getByText(/Selected account is assigned to Runtime #99, but Runtime #41 is selected/)).toBeVisible();

  // Submit button is disabled while mismatch is unresolved
  await expect(form.getByRole("button", { name: "Prepare Publishing" })).toBeDisabled();
});

test("prepares publishing workflow with pinned bindings and idempotency key", async ({ page }) => {
  await page.goto("/publishing");

  await page.getByRole("button", { name: "Prepare Publishing" }).click();

  const form = page.locator("form");

  // Select matching Account (@creator_alpha bound to Runtime 41)
  await form.locator("select").first().selectOption("101");

  // Select Runtime 41
  await form.locator("select").nth(1).selectOption("41");

  // Fill custom name
  await page.getByPlaceholder(/Summer Promo/).fill("Summer Collection Launch");

  // Submit
  await form.getByRole("button", { name: "Prepare Publishing" }).click();

  // Verifies request was sent
  expect(submittedWorkflowRequests.length).toBe(1);
  const req = submittedWorkflowRequests[0];
  expect(req.template_key).toBe("publishing_prepare_review");
  expect(req.runtime_id).toBe(41);
  expect(req.account_id).toBe(101);
  expect(req.content_asset_id).toBe(51);
  expect(req.content_asset_version_id).toBe(71);
  expect(req.managed_app_id).toBe(1);
  expect(req.managed_app_version_id).toBe(201);
  expect(typeof req.idempotency_key).toBe("string");
  expect((req.idempotency_key as string).length).toBeGreaterThan(0);

  // New session appears
  await expect(page.getByText("Session #2")).toBeVisible();
});

test("publishing session detail displays 6-step timeline and boundary notice", async ({ page }) => {
  await page.goto("/publishing");

  // Open detail for Session #1
  await page.getByText("Session #1").click();

  // Detail modal open
  await expect(page.getByRole("heading", { name: "TikTok Preparation Workflow" })).toBeVisible();

  // Prominent header disclaimer
  await expect(page.locator("div.fixed").getByText(/Prepared does not mean published/)).toBeVisible();

  // Bound Metadata Summary Cards
  const modal = page.locator("div.fixed");
  await expect(modal.getByText("Runtime #41", { exact: false })).toBeVisible();
  await expect(modal.getByText("Account #101", { exact: false })).toBeVisible();
  await expect(modal.getByText("Version #71", { exact: false })).toBeVisible();
  await expect(modal.getByText("App #1 (v202)", { exact: false })).toBeVisible();

  // 6-step timeline verification
  await expect(page.getByText("1. Verify Runtime (container, boot, ADB)")).toBeVisible();
  await expect(page.getByText("2. Verify Managed App (package, version, signature)")).toBeVisible();
  await expect(page.getByText("3. Deliver Media Content (push, MediaStore index)")).toBeVisible();
  await expect(page.getByText("4. Launch Application")).toBeVisible();
  await expect(page.getByText("5. Verify App State (foreground active)")).toBeVisible();
  await expect(page.getByText("6. Review & Approval Boundary")).toBeVisible();

  // Prominent Approval Boundary Card
  await expect(page.getByText("Approval Boundary: Ready for Review")).toBeVisible();
  await expect(
    page.getByText("Environment is prepared for publishing. Approval confirms preparation only. No content has been published.")
  ).toBeVisible();
  await expect(page.getByRole("button", { name: "Approve Preparation" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Reject" })).toBeVisible();
});

test("approves publishing preparation transition to prepared state", async ({ page }) => {
  await page.goto("/publishing");

  await page.getByText("Session #1").click();

  // Add operator comment
  await page.getByPlaceholder("e.g. Verified target app is open on device screen").fill("Confirmed TikTok is open and media is visible in album");

  // Click Approve Preparation
  await page.getByRole("button", { name: "Approve Preparation" }).click();

  // Verifies status transitions to Prepared in the modal
  await expect(page.locator("div.fixed").getByText("Prepared", { exact: true })).toBeVisible();

  // Approval boundary card is now resolved
  await expect(page.getByText("Approval Boundary: Ready for Review")).not.toBeVisible();
});

test("rejects publishing preparation transition to rejected state", async ({ page }) => {
  await page.goto("/publishing");

  await page.getByText("Session #1").click();

  // Click Reject
  await page.getByRole("button", { name: "Reject" }).click();

  // Verifies status transitions to Rejected in the modal
  await expect(page.locator("div.fixed").getByText("Rejected", { exact: true })).toBeVisible();
});

test("inspects step job details from publishing timeline", async ({ page }) => {
  await page.goto("/publishing");

  await page.getByText("Session #1").click();

  // Step 1 has job_id 501
  await page.getByRole("button", { name: "Job #501" }).click();

  // Job details modal opens
  const jobModal = page.locator("section[role='dialog']");
  await expect(jobModal.getByText("Job #501")).toBeVisible();
  await expect(jobModal.getByText("device.package_state")).toBeVisible();
});

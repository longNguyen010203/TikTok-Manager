import { expect, Page, test } from "@playwright/test";

type WorkflowStatus =
  | "draft" | "pending" | "running" | "waiting" | "paused"
  | "succeeded" | "failed" | "cancelling" | "cancelled";

interface FixtureStep {
  id: number;
  step_index: number;
  step_key: string;
  step_type: string;
  status: string;
  depends_on_step_id: number | null;
  job_id: number | null;
  attempt: number;
  max_attempts: number;
  result_json: Record<string, unknown> | null;
  resume_at: string | null;
  waiting_reason: string | null;
  approval_decision: string | null;
  approval_at: string | null;
  approval_actor: string | null;
  approval_comment: string | null;
  started_at: string | null;
  completed_at: string | null;
  error_code: string | null;
  error_message: string | null;
}

const now = "2026-10-05T09:00:00Z";
const runtime = {
  id: 41, device_id: 31, name: "Managed Runtime 41", runtime_type: "redroid",
  status: "running", adb_serial: "localhost:5599", docker_container_name: "redroid-device-41",
  last_seen_at: now, created_at: now, updated_at: now,
};
const device = {
  id: 31, name: "Workflow Fixture Device", device_type: "emulator", platform: "android",
  os_version: "12", status: "online", notes: null, created_at: now, updated_at: now,
};
const version = {
  id: 71, version_number: 1, original_filename: "fixture.png", detected_mime_type: "image/png",
  canonical_extension: ".png", processing_status: "ready", size_bytes: 1024,
  sha256: "a".repeat(64), width: 32, height: 32, duration_ms: null, codec: null,
  container: null, frame_rate_numerator: null, frame_rate_denominator: null,
  audio_present: false, bitrate: null, sample_rate: null, channels: null,
  orientation: null, metadata: {}, created_at: now, processed_at: now,
  error_code: null, error_message: null,
};
const asset = {
  id: 51, asset_type: "image", display_name: "Workflow Fixture Image", notes: null,
  source: "upload", status: "ready", tags: ["fixture"], current_version: version,
  thumbnail_available: true, created_at: now, updated_at: now, archived_at: null,
  deleted_at: null, total_deliveries: 1, latest_delivery_status: "succeeded",
  last_successful_delivery_at: now, versions: [version],
};
const templates = [
  {
    key: "content_delivery_review", version: 1, label: "Content Delivery Review",
    description: "Deliver and request approval.", required_bindings: ["runtime", "content"],
    parameters_schema: { type: "object", properties: { import_media: { type: "boolean", default: true } } },
  },
  {
    key: "content_delivery_wait_review", version: 1, label: "Content Delivery, Wait, and Review",
    description: "Deliver, wait, and request approval.", required_bindings: ["runtime", "content"],
    parameters_schema: { type: "object", properties: { wait_duration_seconds: { type: "integer", minimum: 1, maximum: 86400 } } },
  },
];

function step(
  id: number,
  index: number,
  type: string,
  status: string,
  jobId: number | null = null,
): FixtureStep {
  return {
    id, step_index: index, step_key: type.replace(".", "_"), step_type: type, status,
    depends_on_step_id: index ? id - 1 : null, job_id: jobId, attempt: 1, max_attempts: 1,
    result_json: jobId && status === "succeeded" ? { job_id: jobId, delivery_id: 9, remote_filename: "fixture.png" } : null,
    resume_at: null, waiting_reason: type === "workflow.approval" && status === "waiting" ? "waiting_for_approval" : null,
    approval_decision: null, approval_at: null, approval_actor: null, approval_comment: null,
    started_at: now, completed_at: status === "succeeded" ? now : null,
    error_code: null, error_message: null,
  };
}

function workflow(id: number, name: string, status: WorkflowStatus, steps: FixtureStep[]) {
  return {
    id, name, description: `${name} description`, template_key: steps.length === 3
      ? "content_delivery_wait_review" : "content_delivery_review", template_version: 1,
    status, parameters: { import_media: false }, account_id: null, runtime_id: 41,
    runtime_id_snapshot: 41, content_asset_id: 51, content_asset_version_id: 71,
    current_step_id: steps.find((item) => ["running", "waiting", "ready"].includes(item.status))?.id ?? null,
    pause_requested_at: null, cancel_requested_at: null, created_at: now, updated_at: now,
    started_at: status === "draft" ? null : now,
    completed_at: ["succeeded", "failed", "cancelled"].includes(status) ? now : null,
    cancelled_at: status === "cancelled" ? now : null,
    error_code: status === "failed" ? "RUNTIME_STOPPED" : null,
    error_message: status === "failed" ? "Runtime is stopped" : null,
    steps,
  };
}

async function installApi(page: Page) {
  const waitStep = step(103, 1, "workflow.wait", "waiting");
  waitStep.resume_at = new Date(Date.now() + 60_000).toISOString();
  waitStep.waiting_reason = "waiting_until_resume_at";
  const screenConflict = workflow(5, "Screen conflict fixture", "failed", [
    step(109, 0, "content.deliver", "failed", 905),
    step(110, 1, "workflow.approval", "pending"),
  ]);
  screenConflict.error_code = "RUNTIME_SCREEN_ACTIVE";
  screenConflict.error_message = "A managed screen session is active";
  const workflows = [
    workflow(1, "Approval fixture", "waiting", [step(101, 0, "content.deliver", "succeeded", 901), step(102, 1, "workflow.approval", "waiting")]),
    workflow(2, "Wait fixture", "waiting", [step(102, 0, "content.deliver", "succeeded", 902), waitStep, step(104, 2, "workflow.approval", "pending")]),
    workflow(3, "Paused fixture", "paused", [step(105, 0, "content.deliver", "succeeded", 903), step(106, 1, "workflow.approval", "pending")]),
    workflow(4, "Failed fixture", "failed", [step(107, 0, "content.deliver", "failed", 904), step(108, 1, "workflow.approval", "pending")]),
    screenConflict,
    workflow(6, "Reject fixture", "waiting", [step(111, 0, "content.deliver", "succeeded", 906), step(112, 1, "workflow.approval", "waiting")]),
  ];
  const events = [
    { id: 1, workflow_id: 1, workflow_step_id: null, job_id: null, event_type: "workflow_created", metadata: {}, created_at: now },
    { id: 2, workflow_id: 1, workflow_step_id: 101, job_id: 901, event_type: "job_created", metadata: {}, created_at: now },
    { id: 3, workflow_id: 1, workflow_step_id: 101, job_id: 901, event_type: "step_succeeded", metadata: {}, created_at: now },
    { id: 4, workflow_id: 1, workflow_step_id: 102, job_id: null, event_type: "waiting_for_approval", metadata: {}, created_at: now },
  ];
  let nextId = 10;

  await page.route("http://127.0.0.1:8000/**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname;
    const json = (body: unknown, status = 200) => route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });
    if (path === "/workflow-templates") return json(templates);
    if (path === "/runtimes") return json({ items: [runtime], total: 1, page: 1, page_size: 100 });
    if (path === "/devices") return json({ items: [device], total: 1, page: 1, page_size: 100 });
    if (path === "/accounts") return json({ items: [], total: 0, page: 1, page_size: 100 });
    if (path === "/content") return json({ items: [asset], total: 1, page: 1, page_size: 100 });
    if (path === "/content/51") return json(asset);
    if (path === "/workflows" && request.method() === "GET") return json({ items: workflows, total: workflows.length, page: 1, page_size: 20 });
    if (path === "/workflows" && request.method() === "POST") {
      const input = request.postDataJSON();
      const isWait = input.template_key === "content_delivery_wait_review";
      const created = workflow(nextId++, input.name, "draft", isWait
        ? [step(nextId * 10, 0, "content.deliver", "pending"), step(nextId * 10 + 1, 1, "workflow.wait", "pending"), step(nextId * 10 + 2, 2, "workflow.approval", "pending")]
        : [step(nextId * 10, 0, "content.deliver", "pending"), step(nextId * 10 + 1, 1, "workflow.approval", "pending")]);
      workflows.unshift(created);
      return json(created, 201);
    }
    const eventMatch = path.match(/^\/workflows\/(\d+)\/events$/);
    if (eventMatch) return json({ items: events, total: events.length, page: 1, page_size: 100 });
    const actionMatch = path.match(/^\/workflows\/(\d+)\/(start|pause|resume|cancel|retry)$/);
    if (actionMatch) {
      const item = workflows.find((entry) => entry.id === Number(actionMatch[1]))!;
      const states: Record<string, WorkflowStatus> = { start: "running", pause: "paused", resume: "pending", cancel: "cancelled", retry: "pending" };
      item.status = states[actionMatch[2]];
      item.error_code = null; item.error_message = null;
      return json(item);
    }
    const decisionMatch = path.match(/^\/workflows\/(\d+)\/steps\/(\d+)\/(approve|reject)$/);
    if (decisionMatch) {
      const item = workflows.find((entry) => entry.id === Number(decisionMatch[1]))!;
      const target = item.steps.find((entry) => entry.id === Number(decisionMatch[2]))!;
      target.status = decisionMatch[3] === "approve" ? "succeeded" : "failed";
      target.approval_decision = decisionMatch[3] === "approve" ? "approved" : "rejected";
      item.status = decisionMatch[3] === "approve" ? "succeeded" : "failed";
      item.current_step_id = null;
      return json(item);
    }
    const workflowMatch = path.match(/^\/workflows\/(\d+)$/);
    if (workflowMatch) return json(workflows.find((entry) => entry.id === Number(workflowMatch[1])));
    if (path.match(/^\/jobs\/\d+$/)) return json({ id: 901, job_type: "content.deliver", status: "succeeded", logs: [] });
    return json({ detail: "not mocked" }, 404);
  });
}

test.beforeEach(async ({ page }) => {
  await installApi(page);
  await page.goto("/workflows");
  await expect(page.getByRole("heading", { name: "Workflows", exact: true })).toBeVisible();
});

test("list, wait countdown, event timeline, job link, and approval", async ({ page }) => {
  await expect(page.getByText("Approval fixture")).toBeVisible();
  await page.getByText("Wait fixture").click();
  await expect(page.getByText("Timer active: Waiting duration")).toBeVisible();
  await expect(page.getByText(/remaining/)).toBeVisible();
  await page.getByTitle("Close").click();

  await page.getByText("Approval fixture").click();
  await page.getByRole("button", { name: "Event Audit History" }).click();
  await expect(page.getByText("Event Audit Log (4)")).toBeVisible();
  await expect(page.getByText("Job #901").first()).toBeVisible();
  await page.getByRole("button", { name: "Execution Steps (2)" }).click();
  await page.getByRole("button", { name: "Approve Step" }).click();
  await expect(page.getByText("Succeeded").first()).toBeVisible();
  await page.getByTitle("Close").click();

  await page.getByText("Reject fixture").click();
  await page.getByRole("button", { name: "Reject Step" }).click();
  await expect(page.getByText("Failed", { exact: true }).last()).toBeVisible();
});

test("creates both server-owned workflow templates", async ({ page }) => {
  await page.getByRole("button", { name: "Create Workflow" }).first().click();
  await page.getByPlaceholder("e.g. Autumn Promo Delivery & Review").fill("Created review fixture");
  await page.getByRole("button", { name: "Create Workflow" }).last().click();
  await expect(page.getByRole("heading", { name: "Created review fixture" })).toBeVisible();
  await page.getByTitle("Close").click();

  await page.getByRole("button", { name: "Create Workflow" }).first().click();
  await page.getByRole("heading", { name: "Content Delivery, Wait, and Review" }).click();
  await page.getByPlaceholder("e.g. Autumn Promo Delivery & Review").fill("Created wait fixture");
  await page.getByRole("spinbutton").fill("15");
  await page.getByRole("button", { name: "Create Workflow" }).last().click();
  await expect(page.getByRole("heading", { name: "Created wait fixture" })).toBeVisible();
});

test("pause, resume, cancel, retry, and reject refresh backend truth", async ({ page }) => {
  await page.getByText("Paused fixture").click();
  await page.getByRole("button", { name: "Resume Workflow", exact: true }).last().click();
  await expect(page.getByRole("button", { name: "Pause", exact: true })).toBeVisible();
  await page.getByTitle("Close").click();

  await page.getByText("Failed fixture").click();
  await expect(page.getByText("Target runtime is currently stopped", { exact: false })).toBeVisible();
  await page.getByRole("button", { name: "Retry Workflow", exact: true }).last().click();
  await expect(page.getByRole("button", { name: "Pause", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Cancel", exact: true }).click();
  await page.getByRole("button", { name: "Confirm Cancel" }).click();
  await expect(page.getByText("Cancelled", { exact: true }).last()).toBeVisible();
  await page.getByTitle("Close").click();

  await page.getByText("Screen conflict fixture").click();
  await expect(page.getByText("Close the screen viewer before running workflow", { exact: false })).toBeVisible();
});

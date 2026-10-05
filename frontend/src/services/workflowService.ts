import { ApiError } from "@/types/account";
import {
  Workflow,
  WorkflowApprovalInput,
  WorkflowCreateInput,
  WorkflowEventListResponse,
  WorkflowListParams,
  WorkflowListResponse,
  WorkflowTemplate,
  getWorkflowErrorMessage,
} from "@/types/workflow";

class WorkflowService {
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
      message = `Request failed with status ${response.status}`;
    }

    // Friendly error enrichment if code is present
    if (code) {
      message = getWorkflowErrorMessage(code, message);
    }

    return new ApiError(
      response.status,
      message,
      code ? `code: ${code}` : undefined
    );
  }

  /**
   * List available server-owned workflow templates
   */
  async getTemplates(): Promise<WorkflowTemplate[]> {
    const res = await fetch(`${this.baseUrl}/workflow-templates`, {
      method: "GET",
      headers: { Accept: "application/json" },
    });

    if (!res.ok) {
      throw await this.parseError(res);
    }

    return res.json();
  }

  /**
   * List workflows with backend filtering and pagination
   */
  async listWorkflows(params?: WorkflowListParams): Promise<WorkflowListResponse> {
    const searchParams = new URLSearchParams();
    if (params?.page) searchParams.set("page", String(params.page));
    if (params?.page_size) searchParams.set("page_size", String(params.page_size));
    if (params?.status && params.status !== "all") {
      searchParams.set("status", params.status);
    }
    if (params?.template && params.template !== "all") {
      searchParams.set("template", params.template);
    }
    if (params?.runtime_id) {
      searchParams.set("runtime_id", String(params.runtime_id));
    }
    if (params?.account_id) {
      searchParams.set("account_id", String(params.account_id));
    }
    if (params?.content_asset_id) {
      searchParams.set("content_asset_id", String(params.content_asset_id));
    }

    const query = searchParams.toString();
    const url = `${this.baseUrl}/workflows${query ? `?${query}` : ""}`;

    const res = await fetch(url, {
      method: "GET",
      headers: { Accept: "application/json" },
    });

    if (!res.ok) {
      throw await this.parseError(res);
    }

    return res.json();
  }

  /**
   * Get single workflow with steps
   */
  async getWorkflow(workflowId: number): Promise<Workflow> {
    const res = await fetch(`${this.baseUrl}/workflows/${workflowId}`, {
      method: "GET",
      headers: { Accept: "application/json" },
    });

    if (!res.ok) {
      throw await this.parseError(res);
    }

    return res.json();
  }

  /**
   * Create workflow
   */
  async createWorkflow(
    input: WorkflowCreateInput
  ): Promise<{ workflow: Workflow; created: boolean }> {
    const res = await fetch(`${this.baseUrl}/workflows`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify(input),
    });

    if (!res.ok) {
      throw await this.parseError(res);
    }

    const workflow = await res.json();
    return {
      workflow,
      created: res.status === 201,
    };
  }

  /**
   * Start workflow
   */
  async startWorkflow(workflowId: number): Promise<Workflow> {
    const res = await fetch(`${this.baseUrl}/workflows/${workflowId}/start`, {
      method: "POST",
      headers: { Accept: "application/json" },
    });

    if (!res.ok) {
      throw await this.parseError(res);
    }

    return res.json();
  }

  /**
   * Pause workflow
   */
  async pauseWorkflow(workflowId: number): Promise<Workflow> {
    const res = await fetch(`${this.baseUrl}/workflows/${workflowId}/pause`, {
      method: "POST",
      headers: { Accept: "application/json" },
    });

    if (!res.ok) {
      throw await this.parseError(res);
    }

    return res.json();
  }

  /**
   * Resume workflow
   */
  async resumeWorkflow(workflowId: number): Promise<Workflow> {
    const res = await fetch(`${this.baseUrl}/workflows/${workflowId}/resume`, {
      method: "POST",
      headers: { Accept: "application/json" },
    });

    if (!res.ok) {
      throw await this.parseError(res);
    }

    return res.json();
  }

  /**
   * Cancel workflow
   */
  async cancelWorkflow(workflowId: number): Promise<Workflow> {
    const res = await fetch(`${this.baseUrl}/workflows/${workflowId}/cancel`, {
      method: "POST",
      headers: { Accept: "application/json" },
    });

    if (!res.ok) {
      throw await this.parseError(res);
    }

    return res.json();
  }

  /**
   * Retry failed workflow
   */
  async retryWorkflow(workflowId: number): Promise<Workflow> {
    const res = await fetch(`${this.baseUrl}/workflows/${workflowId}/retry`, {
      method: "POST",
      headers: { Accept: "application/json" },
    });

    if (!res.ok) {
      throw await this.parseError(res);
    }

    return res.json();
  }

  /**
   * Approve waiting workflow step
   */
  async approveStep(
    workflowId: number,
    stepId: number,
    input: WorkflowApprovalInput
  ): Promise<Workflow> {
    const res = await fetch(
      `${this.baseUrl}/workflows/${workflowId}/steps/${stepId}/approve`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Accept: "application/json",
        },
        body: JSON.stringify(input),
      }
    );

    if (!res.ok) {
      throw await this.parseError(res);
    }

    return res.json();
  }

  /**
   * Reject waiting workflow step
   */
  async rejectStep(
    workflowId: number,
    stepId: number,
    input: WorkflowApprovalInput
  ): Promise<Workflow> {
    const res = await fetch(
      `${this.baseUrl}/workflows/${workflowId}/steps/${stepId}/reject`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Accept: "application/json",
        },
        body: JSON.stringify(input),
      }
    );

    if (!res.ok) {
      throw await this.parseError(res);
    }

    return res.json();
  }

  /**
   * Fetch chronological workflow events
   */
  async getEvents(
    workflowId: number,
    page: number = 1,
    pageSize: number = 50
  ): Promise<WorkflowEventListResponse> {
    const searchParams = new URLSearchParams({
      page: String(page),
      page_size: String(pageSize),
    });

    const res = await fetch(
      `${this.baseUrl}/workflows/${workflowId}/events?${searchParams.toString()}`,
      {
        method: "GET",
        headers: { Accept: "application/json" },
      }
    );

    if (!res.ok) {
      throw await this.parseError(res);
    }

    return res.json();
  }
}

export const workflowService = new WorkflowService();

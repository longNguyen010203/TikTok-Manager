"use client";

import { useEffect, useState, useRef, useCallback, useMemo } from "react";
import {
  AlertCircle,
  CheckCircle2,
  Layers,
  Loader2,
  PlayCircle,
  Plus,
  UserCheck,
  Workflow as WorkflowIcon,
} from "lucide-react";
import { workflowService } from "@/services/workflowService";
import { runtimeService } from "@/services/runtimeService";
import { deviceService } from "@/services/deviceService";
import { contentService } from "@/services/contentService";
import { accountService } from "@/services/accountService";
import {
  Workflow,
  WorkflowStatus,
  WorkflowTemplate,
  isWorkflowActive,
} from "@/types/workflow";
import { Runtime } from "@/types/runtime";
import { Device } from "@/types/device";
import { ContentAsset } from "@/types/content";
import { Account } from "@/types/account";
import { WorkflowTable } from "@/components/workflows/WorkflowTable";
import { WorkflowToolbar } from "@/components/workflows/WorkflowToolbar";
import { WorkflowPagination } from "@/components/workflows/WorkflowPagination";
import { WorkflowCreateModal } from "@/components/workflows/WorkflowCreateModal";
import { WorkflowDetailModal } from "@/components/workflows/WorkflowDetailModal";
import { WorkflowCancelModal } from "@/components/workflows/WorkflowCancelModal";
import { JobDetailModal } from "@/components/jobs/JobDetailModal";

export default function WorkflowsPage() {
  // Primary state
  const [workflows, setWorkflows] = useState<Workflow[]>([]);
  const [total, setTotal] = useState(0);
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Filters
  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<WorkflowStatus | "all">("all");
  const [templateFilter, setTemplateFilter] = useState("all");
  const [runtimeFilter, setRuntimeFilter] = useState<number | "all">("all");
  const [contentFilter, setContentFilter] = useState<number | "all">("all");

  // References
  const [templates, setTemplates] = useState<WorkflowTemplate[]>([]);
  const [runtimes, setRuntimes] = useState<Runtime[]>([]);
  const [devicesMap, setDevicesMap] = useState<Record<number, Device>>({});
  const [runtimesMap, setRuntimesMap] = useState<Record<number, Runtime>>({});
  const [contentAssets, setContentAssets] = useState<ContentAsset[]>([]);
  const [contentAssetsMap, setContentAssetsMap] = useState<Record<number, ContentAsset>>({});
  const [accountsMap, setAccountsMap] = useState<Record<number, Account>>({});

  // Modals
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [selectedWorkflowId, setSelectedWorkflowId] = useState<number | null>(null);
  const [workflowToCancel, setWorkflowToCancel] = useState<Workflow | null>(null);
  const [isCancelling, setIsCancelling] = useState(false);
  const [selectedJobId, setSelectedJobId] = useState<number | null>(null);

  // Polling
  const pollTimerRef = useRef<NodeJS.Timeout | null>(null);

  const stopPolling = useCallback(() => {
    if (pollTimerRef.current) {
      clearInterval(pollTimerRef.current);
      pollTimerRef.current = null;
    }
  }, []);

  // Fetch reference metadata
  useEffect(() => {
    let ignore = false;

    Promise.all([
      workflowService.getTemplates(),
      runtimeService.getRuntimes({ page: 1, page_size: 100 }),
      deviceService.getDevices({ page: 1, page_size: 100 }),
      contentService.listContent({ page: 1, page_size: 100 }),
      accountService.getAccounts({ page: 1, page_size: 100 }),
    ])
      .then(([tpls, rts, devs, assets, accs]) => {
        if (ignore) return;
        setTemplates(tpls);
        setRuntimes(rts.items);

        const rMap: Record<number, Runtime> = {};
        rts.items.forEach((r) => {
          rMap[r.id] = r;
        });
        setRuntimesMap(rMap);

        const dMap: Record<number, Device> = {};
        devs.items.forEach((d) => {
          dMap[d.id] = d;
        });
        setDevicesMap(dMap);

        setContentAssets(assets.items);
        const cMap: Record<number, ContentAsset> = {};
        assets.items.forEach((a) => {
          cMap[a.id] = a;
        });
        setContentAssetsMap(cMap);

        const aMap: Record<number, Account> = {};
        accs.items.forEach((a) => {
          aMap[a.id] = a;
        });
        setAccountsMap(aMap);
      })
      .catch((err) => {
        console.error("Failed to load reference mappings:", err);
      });

    return () => {
      ignore = true;
    };
  }, []);

  // Load Workflows
  // Load Workflows
  useEffect(() => {
    let ignore = false;

    workflowService
      .listWorkflows({
        page: currentPage,
        page_size: pageSize,
        status: statusFilter !== "all" ? statusFilter : undefined,
        template: templateFilter !== "all" ? templateFilter : undefined,
        runtime_id: runtimeFilter !== "all" ? runtimeFilter : undefined,
        content_asset_id: contentFilter !== "all" ? contentFilter : undefined,
      })
      .then((result) => {
        if (ignore) return;
        setWorkflows(result.items);
        setTotal(result.total);
        setError(null);
      })
      .catch((err: unknown) => {
        if (ignore) return;
        setError(
          err && typeof err === "object" && "message" in err
            ? String((err as { message: unknown }).message)
            : "Failed to connect to backend workflow service"
        );
      })
      .finally(() => {
        if (!ignore) setIsLoading(false);
      });

    return () => {
      ignore = true;
    };
  }, [
    currentPage,
    pageSize,
    statusFilter,
    templateFilter,
    runtimeFilter,
    contentFilter,
  ]);

  const refreshWorkflows = useCallback(async () => {
    try {
      const result = await workflowService.listWorkflows({
        page: currentPage,
        page_size: pageSize,
        status: statusFilter !== "all" ? statusFilter : undefined,
        template: templateFilter !== "all" ? templateFilter : undefined,
        runtime_id: runtimeFilter !== "all" ? runtimeFilter : undefined,
        content_asset_id: contentFilter !== "all" ? contentFilter : undefined,
      });
      setWorkflows(result.items);
      setTotal(result.total);
      setError(null);
    } catch {
      // background polling or refresh error
    }
  }, [
    currentPage,
    pageSize,
    statusFilter,
    templateFilter,
    runtimeFilter,
    contentFilter,
  ]);

  // Adaptive background polling: only poll when any item on the page is active
  useEffect(() => {
    const hasActiveWorkflow = workflows.some((wf) => isWorkflowActive(wf.status));

    if (hasActiveWorkflow) {
      if (!pollTimerRef.current) {
        pollTimerRef.current = setInterval(() => {
          refreshWorkflows();
        }, 2500);
      }
    } else {
      stopPolling();
    }

    return () => {
      stopPolling();
    };
  }, [workflows, refreshWorkflows, stopPolling]);

  // Filtered workflows by local search query if provided
  const visibleWorkflows = useMemo(() => {
    if (!searchQuery.trim()) return workflows;
    const query = searchQuery.toLowerCase().trim();
    return workflows.filter(
      (wf) =>
        wf.name.toLowerCase().includes(query) ||
        (wf.description && wf.description.toLowerCase().includes(query)) ||
        wf.template_key.toLowerCase().includes(query)
    );
  }, [workflows, searchQuery]);

  // Header quick statistics
  const stats = useMemo(() => {
    let active = 0;
    let awaitingApproval = 0;
    let succeeded = 0;
    let failed = 0;

    workflows.forEach((wf) => {
      if (isWorkflowActive(wf.status)) active++;
      if (wf.status === "succeeded") succeeded++;
      if (wf.status === "failed") failed++;

      const step = wf.steps.find((s) => s.id === wf.current_step_id);
      if (
        step?.step_type === "workflow.approval" &&
        step.status === "waiting"
      ) {
        awaitingApproval++;
      }
    });

    return { active, awaitingApproval, succeeded, failed };
  }, [workflows]);

  // Quick Action Handlers
  const handleStartWorkflow = async (workflow: Workflow) => {
    try {
      const updated = await workflowService.startWorkflow(workflow.id);
      setWorkflows((prev) =>
        prev.map((w) => (w.id === updated.id ? updated : w))
      );
    } catch (err: unknown) {
      alert(
        err && typeof err === "object" && "message" in err
          ? String((err as { message: unknown }).message)
          : "Failed to start workflow"
      );
    }
  };

  const handlePauseWorkflow = async (workflow: Workflow) => {
    try {
      const updated = await workflowService.pauseWorkflow(workflow.id);
      setWorkflows((prev) =>
        prev.map((w) => (w.id === updated.id ? updated : w))
      );
    } catch (err: unknown) {
      alert(
        err && typeof err === "object" && "message" in err
          ? String((err as { message: unknown }).message)
          : "Failed to pause workflow"
      );
    }
  };

  const handleResumeWorkflow = async (workflow: Workflow) => {
    try {
      const updated = await workflowService.resumeWorkflow(workflow.id);
      setWorkflows((prev) =>
        prev.map((w) => (w.id === updated.id ? updated : w))
      );
    } catch (err: unknown) {
      alert(
        err && typeof err === "object" && "message" in err
          ? String((err as { message: unknown }).message)
          : "Failed to resume workflow"
      );
    }
  };

  const handleConfirmCancel = async () => {
    if (!workflowToCancel) return;
    try {
      setIsCancelling(true);
      const updated = await workflowService.cancelWorkflow(workflowToCancel.id);
      setWorkflows((prev) =>
        prev.map((w) => (w.id === updated.id ? updated : w))
      );
      setWorkflowToCancel(null);
    } catch (err: unknown) {
      alert(
        err && typeof err === "object" && "message" in err
          ? String((err as { message: unknown }).message)
          : "Failed to cancel workflow"
      );
    } finally {
      setIsCancelling(false);
    }
  };

  const handleRetryWorkflow = async (workflow: Workflow) => {
    try {
      const updated = await workflowService.retryWorkflow(workflow.id);
      setWorkflows((prev) =>
        prev.map((w) => (w.id === updated.id ? updated : w))
      );
    } catch (err: unknown) {
      alert(
        err && typeof err === "object" && "message" in err
          ? String((err as { message: unknown }).message)
          : "Failed to retry workflow"
      );
    }
  };

  const handleWorkflowCreated = (created: Workflow) => {
    setWorkflows((prev) => [created, ...prev]);
    setTotal((prev) => prev + 1);
    setSelectedWorkflowId(created.id);
  };

  const handleWorkflowUpdated = (updated: Workflow) => {
    setWorkflows((prev) =>
      prev.map((w) => (w.id === updated.id ? updated : w))
    );
  };

  const clearFilters = () => {
    setSearchQuery("");
    setStatusFilter("all");
    setTemplateFilter("all");
    setRuntimeFilter("all");
    setContentFilter("all");
    setCurrentPage(1);
  };

  return (
    <div className="space-y-6">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl sm:text-2xl font-bold text-slate-900 flex items-center gap-2.5">
            <WorkflowIcon className="w-6 h-6 text-rose-600" />
            <span>Workflows</span>
          </h1>
          <p className="text-xs sm:text-sm text-slate-500 mt-1">
            Orchestrate automated content delivery, timed wait states, and operator approval reviews.
          </p>
        </div>

        <button
          type="button"
          onClick={() => setIsCreateOpen(true)}
          className="inline-flex items-center gap-2 px-4 py-2 text-xs sm:text-sm font-semibold text-white bg-rose-600 hover:bg-rose-700 rounded-lg shadow-sm transition-colors self-start sm:self-auto"
        >
          <Plus className="w-4 h-4" />
          <span>New Workflow</span>
        </button>
      </div>

      {/* KPI Stats Summary Bar */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <div className="bg-white border border-slate-200 rounded-xl p-3.5 shadow-2xs">
          <div className="flex items-center justify-between text-slate-500">
            <span className="text-xs font-medium">Total Workflows</span>
            <Layers className="w-4 h-4 text-slate-400" />
          </div>
          <div className="text-xl font-bold text-slate-900 mt-1">{total}</div>
        </div>

        <div className="bg-white border border-slate-200 rounded-xl p-3.5 shadow-2xs">
          <div className="flex items-center justify-between text-slate-500">
            <span className="text-xs font-medium">Running / Active</span>
            <PlayCircle className="w-4 h-4 text-sky-500" />
          </div>
          <div className="text-xl font-bold text-sky-600 mt-1">
            {stats.active}
          </div>
        </div>

        <div className="bg-white border border-slate-200 rounded-xl p-3.5 shadow-2xs">
          <div className="flex items-center justify-between text-slate-500">
            <span className="text-xs font-medium">Awaiting Approval</span>
            <UserCheck className="w-4 h-4 text-amber-500" />
          </div>
          <div className="text-xl font-bold text-amber-600 mt-1">
            {stats.awaitingApproval}
          </div>
        </div>

        <div className="bg-white border border-slate-200 rounded-xl p-3.5 shadow-2xs">
          <div className="flex items-center justify-between text-slate-500">
            <span className="text-xs font-medium">Succeeded / Failed</span>
            <CheckCircle2 className="w-4 h-4 text-emerald-500" />
          </div>
          <div className="text-xl font-bold text-slate-900 mt-1">
            <span className="text-emerald-600">{stats.succeeded}</span>
            <span className="text-slate-300 font-normal mx-1.5">/</span>
            <span className="text-rose-600">{stats.failed}</span>
          </div>
        </div>
      </div>

      {/* Toolbar & Filters */}
      <WorkflowToolbar
        searchQuery={searchQuery}
        onSearchChange={setSearchQuery}
        statusFilter={statusFilter}
        onStatusChange={(st) => {
          setStatusFilter(st);
          setCurrentPage(1);
        }}
        templateFilter={templateFilter}
        onTemplateChange={(tpl) => {
          setTemplateFilter(tpl);
          setCurrentPage(1);
        }}
        runtimeFilter={runtimeFilter}
        onRuntimeChange={(rt) => {
          setRuntimeFilter(rt);
          setCurrentPage(1);
        }}
        contentFilter={contentFilter}
        onContentChange={(cnt) => {
          setContentFilter(cnt);
          setCurrentPage(1);
        }}
        templates={templates}
        runtimes={runtimes}
        devicesMap={devicesMap}
        contentAssets={contentAssets}
        onRefresh={refreshWorkflows}
        onCreateOpen={() => setIsCreateOpen(true)}
        isLoading={isLoading}
      />

      {/* Error Callout */}
      {error && (
        <div className="p-4 bg-rose-50 border border-rose-200 rounded-xl text-xs text-rose-800 flex items-center justify-between gap-3 shadow-xs">
          <div className="flex items-center gap-2">
            <AlertCircle className="w-4 h-4 text-rose-600 shrink-0" />
            <span>{error}</span>
          </div>
          <button
            type="button"
            onClick={refreshWorkflows}
            className="px-3 py-1 bg-white border border-rose-200 text-rose-700 hover:bg-rose-100/50 rounded-md font-medium transition-colors"
          >
            Retry
          </button>
        </div>
      )}

      {/* Table Container */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-xs overflow-hidden">
        {isLoading && workflows.length === 0 ? (
          <div className="py-20 flex flex-col items-center justify-center text-slate-400 gap-3">
            <Loader2 className="w-7 h-7 animate-spin text-rose-600" />
            <span className="text-xs font-medium">Loading workflows...</span>
          </div>
        ) : workflows.length === 0 ? (
          <div className="py-20 flex flex-col items-center justify-center text-center px-4">
            <div className="w-12 h-12 rounded-full bg-slate-100 text-slate-400 flex items-center justify-center mb-3">
              <WorkflowIcon className="w-6 h-6" />
            </div>
            <h3 className="text-sm font-bold text-slate-800">
              No Workflows Found
            </h3>
            <p className="text-xs text-slate-500 max-w-sm mt-1 mb-4">
              {statusFilter !== "all" || templateFilter !== "all" || runtimeFilter !== "all" || contentFilter !== "all"
                ? "No workflows match your active filter criteria. Try resetting filters."
                : "Create your first workflow to automate content delivery and review."}
            </p>
            {statusFilter !== "all" || templateFilter !== "all" || runtimeFilter !== "all" || contentFilter !== "all" ? (
              <button
                type="button"
                onClick={clearFilters}
                className="px-3.5 py-1.5 text-xs font-semibold text-slate-700 bg-slate-100 hover:bg-slate-200 rounded-lg transition-colors"
              >
                Clear Filters
              </button>
            ) : (
              <button
                type="button"
                onClick={() => setIsCreateOpen(true)}
                className="inline-flex items-center gap-1.5 px-4 py-2 text-xs font-semibold text-white bg-rose-600 hover:bg-rose-700 rounded-lg shadow-sm transition-colors"
              >
                <Plus className="w-4 h-4" />
                <span>Create Workflow</span>
              </button>
            )}
          </div>
        ) : visibleWorkflows.length === 0 ? (
          <div className="py-16 text-center text-slate-500 text-xs">
            No workflows matching &ldquo;{searchQuery}&rdquo;.
          </div>
        ) : (
          <>
            <WorkflowTable
              workflows={visibleWorkflows}
              runtimesMap={runtimesMap}
              devicesMap={devicesMap}
              contentAssetsMap={contentAssetsMap}
              onSelectWorkflow={(wf) => setSelectedWorkflowId(wf.id)}
              onStartWorkflow={handleStartWorkflow}
              onPauseWorkflow={handlePauseWorkflow}
              onResumeWorkflow={handleResumeWorkflow}
              onCancelWorkflow={(wf) => setWorkflowToCancel(wf)}
              onRetryWorkflow={handleRetryWorkflow}
              isLoading={isLoading}
            />

            <WorkflowPagination
              currentPage={currentPage}
              pageSize={pageSize}
              total={total}
              onPageChange={setCurrentPage}
              onPageSizeChange={(newSize) => {
                setPageSize(newSize);
                setCurrentPage(1);
              }}
            />
          </>
        )}
      </div>

      {/* Workflow Create Modal */}
      <WorkflowCreateModal
        isOpen={isCreateOpen}
        onClose={() => setIsCreateOpen(false)}
        onSuccess={handleWorkflowCreated}
      />

      {/* Workflow Detail Modal */}
      <WorkflowDetailModal
        workflowId={selectedWorkflowId}
        runtimesMap={runtimesMap}
        devicesMap={devicesMap}
        contentAssetsMap={contentAssetsMap}
        onClose={() => setSelectedWorkflowId(null)}
        onViewJob={(jobId) => setSelectedJobId(jobId)}
        onWorkflowUpdated={handleWorkflowUpdated}
      />

      {/* Workflow Cancel Modal */}
      <WorkflowCancelModal
        workflow={workflowToCancel}
        isOpen={workflowToCancel !== null}
        isCancelling={isCancelling}
        onConfirm={handleConfirmCancel}
        onClose={() => setWorkflowToCancel(null)}
      />

      {/* Job Detail Modal Integration */}
      {selectedJobId !== null && (
        <JobDetailModal
          jobId={selectedJobId}
          accountsMap={accountsMap}
          runtimesMap={runtimesMap}
          onClose={() => setSelectedJobId(null)}
          onQueueRefresh={refreshWorkflows}
        />
      )}
    </div>
  );
}

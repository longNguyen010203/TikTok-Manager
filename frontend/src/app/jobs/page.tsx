"use client";

import { useEffect, useMemo, useState } from "react";
import {
  AlertCircle,
  CheckCircle2,
  Clock3,
  ListChecks,
  LoaderCircle,
  RefreshCw,
  Server,
} from "lucide-react";
import { JobPagination } from "@/components/jobs/JobPagination";
import { JobDetailModal } from "@/components/jobs/JobDetailModal";
import { JobTable } from "@/components/jobs/JobTable";
import { JobToolbar } from "@/components/jobs/JobToolbar";
import { accountService } from "@/services/accountService";
import { jobService } from "@/services/jobService";
import { runtimeService } from "@/services/runtimeService";
import { Account, formatApiError } from "@/types/account";
import { Job, JobStatus } from "@/types/job";
import { Runtime } from "@/types/runtime";

async function loadAllAccounts(): Promise<Account[]> {
  const firstPage = await accountService.getAccounts({ page: 1, page_size: 100 });
  const pageCount = Math.ceil(firstPage.total / 100);
  if (pageCount <= 1) return firstPage.items;

  const remainingPages = await Promise.all(
    Array.from({ length: pageCount - 1 }, (_, index) =>
      accountService.getAccounts({ page: index + 2, page_size: 100 }),
    ),
  );
  return [firstPage, ...remainingPages].flatMap((page) => page.items);
}

async function loadAllRuntimes(): Promise<Runtime[]> {
  const firstPage = await runtimeService.getRuntimes({ page: 1, page_size: 100 });
  const pageCount = Math.ceil(firstPage.total / 100);
  if (pageCount <= 1) return firstPage.items;

  const remainingPages = await Promise.all(
    Array.from({ length: pageCount - 1 }, (_, index) =>
      runtimeService.getRuntimes({ page: index + 2, page_size: 100 }),
    ),
  );
  return [firstPage, ...remainingPages].flatMap((page) => page.items);
}

function connectionError(error: unknown, apiBaseUrl: string) {
  const message = formatApiError(error);
  if (
    message.toLowerCase().includes("failed to fetch") ||
    message.toLowerCase().includes("networkerror")
  ) {
    return `Unable to connect to FastAPI backend at ${apiBaseUrl}. Ensure the backend server is running.`;
  }
  return message;
}

export default function JobsPage() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [runtimes, setRuntimes] = useState<Runtime[]>([]);
  const [total, setTotal] = useState(0);
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState<"all" | JobStatus>("all");
  const [jobType, setJobType] = useState("");
  const [accountId, setAccountId] = useState("all");
  const [runtimeId, setRuntimeId] = useState("all");
  const [jobsLoading, setJobsLoading] = useState(true);
  const [referencesLoading, setReferencesLoading] = useState(true);
  const [jobsError, setJobsError] = useState<string | null>(null);
  const [referencesError, setReferencesError] = useState<string | null>(null);
  const [refreshIndex, setRefreshIndex] = useState(0);
  const [selectedJobId, setSelectedJobId] = useState<number | null>(null);
  const apiBaseUrl = jobService.getBaseUrl();

  useEffect(() => {
    let ignore = false;

    Promise.all([loadAllAccounts(), loadAllRuntimes()])
      .then(([loadedAccounts, loadedRuntimes]) => {
        if (ignore) return;
        setAccounts(
          loadedAccounts.sort((left, right) => left.name.localeCompare(right.name)),
        );
        setRuntimes(
          loadedRuntimes.sort((left, right) => left.name.localeCompare(right.name)),
        );
        setReferencesError(null);
      })
      .catch((error: unknown) => {
        if (ignore) return;
        setAccounts([]);
        setRuntimes([]);
        setReferencesError(connectionError(error, apiBaseUrl));
      })
      .finally(() => {
        if (!ignore) setReferencesLoading(false);
      });

    return () => {
      ignore = true;
    };
  }, [refreshIndex, apiBaseUrl]);

  useEffect(() => {
    let ignore = false;

    jobService
      .getJobs({
        page: currentPage,
        page_size: pageSize,
        status: status === "all" ? undefined : status,
        job_type: jobType.trim() || undefined,
        account_id: accountId === "all" ? undefined : Number(accountId),
        runtime_id: runtimeId === "all" ? undefined : Number(runtimeId),
      })
      .then((response) => {
        if (ignore) return;
        setJobs(response.items);
        setTotal(response.total);
        setJobsError(null);
      })
      .catch((error: unknown) => {
        if (ignore) return;
        setJobs([]);
        setTotal(0);
        setJobsError(connectionError(error, apiBaseUrl));
      })
      .finally(() => {
        if (!ignore) setJobsLoading(false);
      });

    return () => {
      ignore = true;
    };
  }, [
    currentPage,
    pageSize,
    status,
    jobType,
    accountId,
    runtimeId,
    refreshIndex,
    apiBaseUrl,
  ]);

  const accountsMap = useMemo(
    () => Object.fromEntries(accounts.map((account) => [account.id, account])),
    [accounts],
  );
  const runtimesMap = useMemo(
    () => Object.fromEntries(runtimes.map((runtime) => [runtime.id, runtime])),
    [runtimes],
  );

  const displayedJobs = useMemo(() => {
    const query = search.trim().toLowerCase();
    if (!query) return jobs;
    return jobs.filter((job) => {
      const account = job.account_id ? accountsMap[job.account_id] : undefined;
      const runtime = job.runtime_id ? runtimesMap[job.runtime_id] : undefined;
      return [
        job.id.toString(),
        job.job_type,
        job.status,
        account?.name,
        account?.username,
        runtime?.name,
        runtime?.runtime_type,
      ].some((value) => value?.toLowerCase().includes(query));
    });
  }, [jobs, search, accountsMap, runtimesMap]);

  const isLoading = jobsLoading || referencesLoading;
  const error = jobsError || referencesError;
  const isFiltered =
    search.trim().length > 0 ||
    status !== "all" ||
    jobType.trim().length > 0 ||
    accountId !== "all" ||
    runtimeId !== "all";

  const refresh = () => {
    setJobsLoading(true);
    setReferencesLoading(true);
    setRefreshIndex((value) => value + 1);
  };

  const resetPage = () => setCurrentPage(1);
  const clearFilters = () => {
    setJobsLoading(true);
    setSearch("");
    setStatus("all");
    setJobType("");
    setAccountId("all");
    setRuntimeId("all");
    setCurrentPage(1);
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
        <div>
          <h2 className="flex items-center gap-2.5 text-2xl font-bold tracking-tight text-slate-900">
            <ListChecks className="h-6 w-6 text-rose-600" />
            Job Queue
          </h2>
          <p className="mt-1 text-sm text-slate-500">
            Monitor scheduled work, execution targets, attempts, and queue state.
          </p>
        </div>
        <button
          type="button"
          onClick={refresh}
          disabled={isLoading}
          className="inline-flex self-start items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-medium text-slate-700 shadow-2xs transition-colors hover:bg-slate-50 disabled:opacity-50 sm:self-auto"
        >
          <RefreshCw className={`h-3.5 w-3.5 ${isLoading ? "animate-spin" : ""}`} />
          Refresh
        </button>
      </div>

      <div className="flex flex-col justify-between gap-2 rounded-xl border border-slate-200/80 bg-slate-100/60 p-3.5 text-xs text-slate-700 shadow-2xs sm:flex-row sm:items-center">
        <div className="flex items-center gap-2">
          <Server className="h-4 w-4 shrink-0 text-slate-500" />
          <span className="font-medium text-slate-800">Backend endpoint:</span>
          <code className="rounded border border-slate-200 bg-white px-1.5 py-0.5 font-mono text-[11px]">
            {apiBaseUrl}/jobs
          </code>
        </div>
        <span className="text-[11px] text-slate-500">
          {accounts.length} accounts · {runtimes.length} runtimes available for resolution
        </span>
      </div>

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        {[
          { label: "Matching jobs", value: total, icon: ListChecks, color: "text-slate-600 bg-slate-100" },
          { label: "Running on page", value: jobs.filter((job) => job.status === "running").length, icon: LoaderCircle, color: "text-cyan-600 bg-cyan-50" },
          { label: "Pending on page", value: jobs.filter((job) => job.status === "pending").length, icon: Clock3, color: "text-amber-600 bg-amber-50" },
          { label: "Failed on page", value: jobs.filter((job) => job.status === "failed").length, icon: AlertCircle, color: "text-rose-600 bg-rose-50" },
        ].map(({ label, value, icon: Icon, color }) => (
          <div key={label} className="flex items-center gap-3 rounded-xl border border-slate-200/80 bg-white p-3.5 shadow-2xs">
            <div className={`rounded-lg p-2 ${color}`}><Icon className="h-4 w-4" /></div>
            <div>
              <p className="text-[11px] font-medium text-slate-500">{label}</p>
              <p className="text-lg font-bold text-slate-900">{value}</p>
            </div>
          </div>
        ))}
      </div>

      <div className="overflow-hidden rounded-xl border border-slate-200/80 bg-white shadow-2xs">
        <JobToolbar
          search={search}
          status={status}
          jobType={jobType}
          accountId={accountId}
          runtimeId={runtimeId}
          accounts={accounts}
          runtimes={runtimes}
          onSearchChange={setSearch}
          onStatusChange={(value) => {
            setJobsLoading(true);
            setStatus(value);
            resetPage();
          }}
          onJobTypeChange={(value) => {
            setJobsLoading(true);
            setJobType(value);
            resetPage();
          }}
          onAccountChange={(value) => {
            setJobsLoading(true);
            setAccountId(value);
            resetPage();
          }}
          onRuntimeChange={(value) => {
            setJobsLoading(true);
            setRuntimeId(value);
            resetPage();
          }}
        />
        <JobTable
          jobs={displayedJobs}
          accountsMap={accountsMap}
          runtimesMap={runtimesMap}
          isLoading={isLoading}
          error={error}
          isFiltered={isFiltered}
          onRetry={refresh}
          onClearFilters={clearFilters}
          onOpenJob={setSelectedJobId}
        />
        {!isLoading && !error && total > 0 && (
          <JobPagination
            currentPage={currentPage}
            pageSize={pageSize}
            total={total}
            onPageChange={(page) => {
              setJobsLoading(true);
              setCurrentPage(page);
            }}
            onPageSizeChange={(size) => {
              setJobsLoading(true);
              setPageSize(size);
              setCurrentPage(1);
            }}
          />
        )}
      </div>

      {!isLoading && !error && jobs.length > 0 && displayedJobs.length === 0 && (
        <div className="flex items-center gap-2 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">
          <CheckCircle2 className="h-3.5 w-3.5" />
          The backend page loaded successfully; the local search matched no rows.
        </div>
      )}

      {selectedJobId !== null && (
        <JobDetailModal
          key={selectedJobId}
          jobId={selectedJobId}
          accountsMap={accountsMap}
          runtimesMap={runtimesMap}
          onClose={() => setSelectedJobId(null)}
          onQueueRefresh={refresh}
        />
      )}
    </div>
  );
}

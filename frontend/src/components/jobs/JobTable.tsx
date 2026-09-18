import {
  AlertCircle,
  CalendarClock,
  Cpu,
  Eye,
  Hash,
  UserRound,
} from "lucide-react";
import { Account } from "@/types/account";
import { Job } from "@/types/job";
import { Runtime } from "@/types/runtime";
import { JobEmptyState } from "./JobEmptyState";
import { JobErrorState } from "./JobErrorState";
import { JobLoadingState } from "./JobLoadingState";
import { JobStatusBadge } from "./JobStatusBadge";

interface JobTableProps {
  jobs: Job[];
  accountsMap: Record<number, Account>;
  runtimesMap: Record<number, Runtime>;
  isLoading: boolean;
  error: string | null;
  isFiltered: boolean;
  onRetry: () => void;
  onClearFilters: () => void;
  onOpenJob: (jobId: number) => void;
}

function formatDate(value: string | null, emptyLabel = "—") {
  if (!value) return emptyLabel;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

function AccountTarget({
  accountId,
  accountsMap,
}: {
  accountId: number | null;
  accountsMap: Record<number, Account>;
}) {
  if (accountId === null) {
    return <span className="text-slate-400">No account</span>;
  }
  const account = accountsMap[accountId];
  if (!account) {
    return (
      <span
        className="inline-flex items-center gap-1 text-amber-700"
        title={`Account #${accountId} is no longer available`}
      >
        <AlertCircle className="h-3.5 w-3.5" /> Missing account #{accountId}
      </span>
    );
  }
  return (
    <div className="flex items-center gap-2">
      <UserRound className="h-3.5 w-3.5 shrink-0 text-slate-400" />
      <div className="min-w-0">
        <p className="max-w-40 truncate font-medium text-slate-800">
          {account.name}
        </p>
        <p className="max-w-40 truncate text-[10px] text-slate-400">
          @{account.username} · #{accountId}
        </p>
      </div>
    </div>
  );
}

function RuntimeTarget({
  runtimeId,
  runtimesMap,
}: {
  runtimeId: number | null;
  runtimesMap: Record<number, Runtime>;
}) {
  if (runtimeId === null) {
    return <span className="text-slate-400">No runtime</span>;
  }
  const runtime = runtimesMap[runtimeId];
  if (!runtime) {
    return (
      <span
        className="inline-flex items-center gap-1 text-amber-700"
        title={`Runtime #${runtimeId} is no longer available`}
      >
        <AlertCircle className="h-3.5 w-3.5" /> Missing runtime #{runtimeId}
      </span>
    );
  }
  return (
    <div className="flex items-center gap-2">
      <Cpu className="h-3.5 w-3.5 shrink-0 text-cyan-600" />
      <div className="min-w-0">
        <p className="max-w-40 truncate font-medium text-slate-800">
          {runtime.name}
        </p>
        <p className="max-w-40 truncate text-[10px] text-slate-400">
          {runtime.runtime_type} · #{runtimeId}
        </p>
      </div>
    </div>
  );
}

function AttemptCount({ job }: { job: Job }) {
  const exhausted = job.attempt_count >= job.max_attempts;
  return (
    <span
      className={`inline-flex rounded-md px-2 py-1 font-mono text-[11px] font-semibold ${
        exhausted
          ? "bg-rose-50 text-rose-700"
          : "bg-slate-100 text-slate-700"
      }`}
      title={`${job.attempt_count} attempts used out of ${job.max_attempts}`}
    >
      {job.attempt_count} / {job.max_attempts}
    </span>
  );
}

export function JobTable({
  jobs,
  accountsMap,
  runtimesMap,
  isLoading,
  error,
  isFiltered,
  onRetry,
  onClearFilters,
  onOpenJob,
}: JobTableProps) {
  if (isLoading) return <JobLoadingState />;
  if (error) return <JobErrorState message={error} onRetry={onRetry} />;
  if (jobs.length === 0) {
    return (
      <JobEmptyState
        isFiltered={isFiltered}
        onClearFilters={onClearFilters}
      />
    );
  }

  return (
    <>
      <div className="divide-y divide-slate-100 md:hidden">
        {jobs.map((job) => (
          <article key={job.id} className="space-y-4 p-4">
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <div className="flex items-center gap-1 font-mono text-[11px] text-slate-400">
                  <Hash className="h-3 w-3" /> {job.id}
                </div>
                <h3 className="truncate font-semibold text-slate-900">
                  {job.job_type}
                </h3>
              </div>
              <JobStatusBadge status={job.status} />
            </div>
            <div className="grid grid-cols-2 gap-4 text-xs">
              <div>
                <p className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-slate-400">
                  Account
                </p>
                <AccountTarget accountId={job.account_id} accountsMap={accountsMap} />
              </div>
              <div>
                <p className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-slate-400">
                  Runtime
                </p>
                <RuntimeTarget runtimeId={job.runtime_id} runtimesMap={runtimesMap} />
              </div>
              <div>
                <p className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-slate-400">
                  Attempts
                </p>
                <AttemptCount job={job} />
              </div>
              <div>
                <p className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-slate-400">
                  Scheduled
                </p>
                <p className="text-slate-600">
                  {formatDate(job.scheduled_at, "Immediate")}
                </p>
              </div>
            </div>
            <div className="flex items-center justify-between gap-3 border-t border-slate-100 pt-3">
              <p className="text-[11px] text-slate-400">
                Updated {formatDate(job.updated_at)}
              </p>
              <button
                type="button"
                onClick={() => onOpenJob(job.id)}
                className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 px-2.5 py-1.5 text-[11px] font-semibold text-slate-700 transition-colors hover:border-rose-200 hover:bg-rose-50 hover:text-rose-700"
              >
                <Eye className="h-3.5 w-3.5" /> View details
              </button>
            </div>
          </article>
        ))}
      </div>

      <div className="hidden overflow-x-auto md:block">
        <table className="w-full min-w-[1120px] border-collapse text-left text-xs">
          <thead>
            <tr className="border-b border-slate-200/80 bg-slate-50/70 text-[10px] font-semibold uppercase tracking-wider text-slate-500">
              <th className="px-5 py-3" scope="col">ID</th>
              <th className="px-5 py-3" scope="col">Job type</th>
              <th className="px-5 py-3" scope="col">Status</th>
              <th className="px-5 py-3" scope="col">Account</th>
              <th className="px-5 py-3" scope="col">Runtime</th>
              <th className="px-5 py-3" scope="col">Attempts</th>
              <th className="px-5 py-3" scope="col">Scheduled</th>
              <th className="px-5 py-3" scope="col">Updated</th>
              <th className="px-5 py-3 text-right" scope="col">Details</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 text-slate-700">
            {jobs.map((job) => (
              <tr key={job.id} className="transition-colors hover:bg-slate-50/60">
                <td className="px-5 py-4 font-mono font-semibold text-slate-500">
                  #{job.id}
                </td>
                <td className="px-5 py-4">
                  <p className="max-w-48 truncate font-semibold text-slate-900">
                    {job.job_type}
                  </p>
                </td>
                <td className="px-5 py-4"><JobStatusBadge status={job.status} /></td>
                <td className="px-5 py-4">
                  <AccountTarget accountId={job.account_id} accountsMap={accountsMap} />
                </td>
                <td className="px-5 py-4">
                  <RuntimeTarget runtimeId={job.runtime_id} runtimesMap={runtimesMap} />
                </td>
                <td className="px-5 py-4"><AttemptCount job={job} /></td>
                <td className="whitespace-nowrap px-5 py-4 text-slate-500">
                  <span className="inline-flex items-center gap-1.5">
                    <CalendarClock className="h-3.5 w-3.5 text-slate-400" />
                    {formatDate(job.scheduled_at, "Immediate")}
                  </span>
                </td>
                <td className="whitespace-nowrap px-5 py-4 text-slate-500">
                  {formatDate(job.updated_at)}
                </td>
                <td className="px-5 py-4 text-right">
                  <button
                    type="button"
                    onClick={() => onOpenJob(job.id)}
                    className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 px-2.5 py-1.5 text-[11px] font-semibold text-slate-700 transition-colors hover:border-rose-200 hover:bg-rose-50 hover:text-rose-700"
                    aria-label={`View details for job ${job.id}`}
                  >
                    <Eye className="h-3.5 w-3.5" /> View
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}

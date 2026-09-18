import { Filter, Search, X } from "lucide-react";
import { Account } from "@/types/account";
import { JobStatus } from "@/types/job";
import { Runtime } from "@/types/runtime";

interface JobToolbarProps {
  search: string;
  status: "all" | JobStatus;
  jobType: string;
  accountId: string;
  runtimeId: string;
  accounts: Account[];
  runtimes: Runtime[];
  onSearchChange: (value: string) => void;
  onStatusChange: (value: "all" | JobStatus) => void;
  onJobTypeChange: (value: string) => void;
  onAccountChange: (value: string) => void;
  onRuntimeChange: (value: string) => void;
}

const inputClassName =
  "rounded-lg border border-slate-200 bg-slate-50 py-2 text-xs text-slate-700 focus:border-rose-500 focus:outline-none focus:ring-2 focus:ring-rose-500/20";

export function JobToolbar({
  search,
  status,
  jobType,
  accountId,
  runtimeId,
  accounts,
  runtimes,
  onSearchChange,
  onStatusChange,
  onJobTypeChange,
  onAccountChange,
  onRuntimeChange,
}: JobToolbarProps) {
  return (
    <div className="space-y-3 border-b border-slate-200/80 bg-white p-4 sm:p-5">
      <div className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-wider text-slate-500">
        <Filter className="h-3.5 w-3.5" />
        Queue filters
      </div>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-5">
        <div className="relative sm:col-span-2 xl:col-span-1">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
          <input
            type="search"
            value={search}
            onChange={(event) => onSearchChange(event.target.value)}
            placeholder="Search this page..."
            className={`${inputClassName} w-full pl-9 pr-8`}
            aria-label="Search jobs on this page"
          />
          {search && (
            <button
              type="button"
              onClick={() => onSearchChange("")}
              className="absolute right-2.5 top-1/2 -translate-y-1/2 p-0.5 text-slate-400 hover:text-slate-600"
              aria-label="Clear search"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          )}
        </div>

        <select
          value={status}
          onChange={(event) =>
            onStatusChange(event.target.value as "all" | JobStatus)
          }
          className={`${inputClassName} px-3`}
          aria-label="Filter jobs by status"
        >
          <option value="all">All statuses</option>
          <option value="pending">Pending</option>
          <option value="running">Running</option>
          <option value="succeeded">Succeeded</option>
          <option value="failed">Failed</option>
          <option value="retrying">Retrying</option>
          <option value="cancelled">Cancelled</option>
        </select>

        <input
          type="text"
          value={jobType}
          onChange={(event) => onJobTypeChange(event.target.value)}
          placeholder="Exact job type"
          maxLength={100}
          className={`${inputClassName} px-3`}
          aria-label="Filter by exact job type"
        />

        <select
          value={accountId}
          onChange={(event) => onAccountChange(event.target.value)}
          className={`${inputClassName} px-3`}
          aria-label="Filter jobs by account"
        >
          <option value="all">All accounts</option>
          {accounts.map((account) => (
            <option key={account.id} value={account.id}>
              {account.name} (@{account.username})
            </option>
          ))}
        </select>

        <select
          value={runtimeId}
          onChange={(event) => onRuntimeChange(event.target.value)}
          className={`${inputClassName} px-3`}
          aria-label="Filter jobs by runtime"
        >
          <option value="all">All runtimes</option>
          {runtimes.map((runtime) => (
            <option key={runtime.id} value={runtime.id}>
              {runtime.name}
            </option>
          ))}
        </select>
      </div>
      <p className="text-[11px] text-slate-400">
        Status, job type, account, and runtime filters query the backend. Search
        refines the currently loaded page.
      </p>
    </div>
  );
}

import React from "react";
import { Account } from "@/types/account";
import { Runtime } from "@/types/runtime";
import { Device } from "@/types/device";
import { AccountStatusBadge } from "./AccountStatusBadge";
import { AccountLoadingState } from "./AccountLoadingState";
import { AccountEmptyState } from "./AccountEmptyState";
import { AccountErrorState } from "./AccountErrorState";
import {
  User,
  Calendar,
  Sparkles,
  Pencil,
  Trash2,
  Cpu,
  Link2,
  AlertCircle,
} from "lucide-react";

interface AccountTableProps {
  accounts: Account[];
  runtimesMap?: Record<number, Runtime>;
  devicesMap?: Record<number, Device>;
  isLoading: boolean;
  error: string | null;
  onRetry: () => void;
  isFiltered: boolean;
  onClearFilters: () => void;
  onCreateAccount: () => void;
  onEditAccount?: (account: Account) => void;
  onDeleteAccount?: (account: Account) => void;
  onAssignRuntime?: (account: Account) => void;
}

export function AccountTable({
  accounts,
  runtimesMap = {},
  devicesMap = {},
  isLoading,
  error,
  onRetry,
  isFiltered,
  onClearFilters,
  onCreateAccount,
  onEditAccount,
  onDeleteAccount,
  onAssignRuntime,
}: AccountTableProps) {
  // Format ISO date string
  const formatDate = (isoString: string) => {
    try {
      const date = new Date(isoString);
      if (isNaN(date.getTime())) return isoString;
      return new Intl.DateTimeFormat("en-US", {
        month: "short",
        day: "numeric",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit",
        hour12: false,
      }).format(date);
    } catch {
      return isoString;
    }
  };

  return (
    <div className="overflow-x-auto">
      {isLoading ? (
        <AccountLoadingState rows={5} />
      ) : error ? (
        <AccountErrorState message={error} onRetry={onRetry} />
      ) : accounts.length === 0 ? (
        <AccountEmptyState
          isFiltered={isFiltered}
          onClearFilters={onClearFilters}
          onCreateAccount={onCreateAccount}
        />
      ) : (
        <table className="w-full text-left text-xs border-collapse">
          <thead>
            <tr className="bg-slate-50/70 border-b border-slate-200/80 text-slate-500 uppercase tracking-wider text-[11px] font-semibold">
              <th scope="col" className="py-3 px-6">
                Name
              </th>
              <th scope="col" className="py-3 px-6">
                Username
              </th>
              <th scope="col" className="py-3 px-6">
                Platform
              </th>
              <th scope="col" className="py-3 px-6">
                Status
              </th>
              <th scope="col" className="py-3 px-6">
                Runtime
              </th>
              <th scope="col" className="py-3 px-6">
                Updated At
              </th>
              <th scope="col" className="py-3 px-6 text-right">
                Actions
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 text-slate-700">
            {accounts.map((acc) => {
              const assignedRuntime =
                acc.runtime_id !== null ? runtimesMap[acc.runtime_id] : null;
              const assignedDevice =
                assignedRuntime && assignedRuntime.device_id
                  ? devicesMap[assignedRuntime.device_id]
                  : null;

              return (
                <tr
                  key={acc.id}
                  className="hover:bg-slate-50/60 transition-colors group"
                >
                  {/* Name */}
                  <td className="py-4 px-6">
                    <div className="flex items-center gap-3">
                      <div className="w-8 h-8 rounded-full bg-gradient-to-br from-rose-100 to-pink-200 text-rose-700 flex items-center justify-center font-bold text-xs shrink-0 shadow-2xs">
                        {acc.name ? (
                          acc.name.charAt(0).toUpperCase()
                        ) : (
                          <User className="w-4 h-4" />
                        )}
                      </div>
                      <div className="min-w-0">
                        <p className="font-semibold text-slate-900 truncate">
                          {acc.name}
                        </p>
                        {acc.notes && (
                          <p
                            className="text-[11px] text-slate-400 truncate max-w-xs"
                            title={acc.notes}
                          >
                            {acc.notes}
                          </p>
                        )}
                      </div>
                    </div>
                  </td>

                  {/* Username */}
                  <td className="py-4 px-6 font-mono text-slate-600 font-medium">
                    @{acc.username}
                  </td>

                  {/* Platform */}
                  <td className="py-4 px-6">
                    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-slate-100 text-slate-700 text-[11px] font-medium uppercase tracking-wider">
                      <Sparkles className="w-3 h-3 text-rose-500" />
                      {acc.platform}
                    </span>
                  </td>

                  {/* Status */}
                  <td className="py-4 px-6">
                    <AccountStatusBadge status={acc.status} />
                  </td>

                  {/* Runtime Assignment */}
                  <td className="py-4 px-6">
                    {acc.runtime_id === null ? (
                      <span className="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-medium bg-slate-100 text-slate-500">
                        Unassigned
                      </span>
                    ) : assignedRuntime ? (
                      <div className="flex items-center gap-2">
                        <div className="p-1 rounded bg-cyan-50 text-cyan-700 shrink-0">
                          <Cpu className="w-3.5 h-3.5" />
                        </div>
                        <div className="min-w-0">
                          <p className="font-medium text-slate-900 truncate max-w-[150px]">
                            {assignedRuntime.name}
                          </p>
                          <p className="text-[10px] text-slate-400 truncate max-w-[150px]">
                            {assignedDevice ? assignedDevice.name : `Device #${assignedRuntime.device_id}`}
                          </p>
                        </div>
                      </div>
                    ) : (
                      <div
                        className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-[11px] font-medium bg-amber-50 text-amber-700 border border-amber-200"
                        title={`Assigned runtime ID #${acc.runtime_id} was not found on server`}
                      >
                        <AlertCircle className="w-3 h-3 text-amber-500 shrink-0" />
                        <span>Missing Runtime (#{acc.runtime_id})</span>
                      </div>
                    )}
                  </td>

                  {/* Updated At */}
                  <td className="py-4 px-6 text-slate-500 whitespace-nowrap">
                    <div className="flex items-center gap-1.5">
                      <Calendar className="w-3.5 h-3.5 text-slate-400" />
                      <span>{formatDate(acc.updated_at)}</span>
                    </div>
                  </td>

                  {/* Actions: Quick Assign, Edit, and Delete */}
                  <td className="py-4 px-6 text-right whitespace-nowrap">
                    <div className="flex items-center justify-end gap-1.5">
                      {onAssignRuntime && (
                        <button
                          type="button"
                          onClick={() => onAssignRuntime(acc)}
                          className="p-1.5 rounded-lg text-slate-500 hover:text-cyan-600 hover:bg-cyan-50 transition-colors"
                          title={`Assign Runtime for @${acc.username}`}
                          aria-label={`Assign Runtime for @${acc.username}`}
                        >
                          <Link2 className="w-3.5 h-3.5" />
                        </button>
                      )}
                      {onEditAccount && (
                        <button
                          type="button"
                          onClick={() => onEditAccount(acc)}
                          className="p-1.5 rounded-lg text-slate-500 hover:text-indigo-600 hover:bg-indigo-50 transition-colors"
                          title={`Edit account @${acc.username}`}
                          aria-label={`Edit account @${acc.username}`}
                        >
                          <Pencil className="w-3.5 h-3.5" />
                        </button>
                      )}
                      {onDeleteAccount && (
                        <button
                          type="button"
                          onClick={() => onDeleteAccount(acc)}
                          className="p-1.5 rounded-lg text-slate-500 hover:text-rose-600 hover:bg-rose-50 transition-colors"
                          title={`Delete account @${acc.username}`}
                          aria-label={`Delete account @${acc.username}`}
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
    </div>
  );
}

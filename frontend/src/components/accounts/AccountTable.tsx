"use client";

import React from "react";
import {
  Account,
  formatMetricNumber,
} from "@/types/account";
import { Runtime } from "@/types/runtime";
import { Device } from "@/types/device";
import {
  AccountStatusBadge,
  RegistrationStateBadge,
  AccountHealthBadge,
  AccountSecretPresenceBadge,
} from "./AccountStatusBadge";
import { AccountLoadingState } from "./AccountLoadingState";
import { AccountEmptyState } from "./AccountEmptyState";
import { AccountErrorState } from "./AccountErrorState";
import {
  User,
  Calendar,
  Pencil,
  Archive,
  Cpu,
  Link2,
  KeyRound,
  AlertCircle,
  Smartphone,
  Heart,
  Users,
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
  onManageSecrets?: (account: Account) => void;
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
  onManageSecrets,
}: AccountTableProps) {
  // Format ISO date string
  const formatDate = (isoString?: string | null) => {
    if (!isoString) return "—";
    try {
      const date = new Date(isoString);
      if (isNaN(date.getTime())) return isoString;
      return new Intl.DateTimeFormat("en-US", {
        month: "short",
        day: "numeric",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit",
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
              <th scope="col" className="py-3 px-5">
                Account
              </th>
              <th scope="col" className="py-3 px-4">
                Username
              </th>
              <th scope="col" className="py-3 px-3">
                Status
              </th>
              <th scope="col" className="py-3 px-3">
                Reg / Health
              </th>
              <th scope="col" className="py-3 px-3">
                Niche
              </th>
              <th scope="col" className="py-3 px-3">
                Metrics
              </th>
              <th scope="col" className="py-3 px-4">
                Runtime &amp; Device
              </th>
              <th scope="col" className="py-3 px-3">
                Credentials
              </th>
              <th scope="col" className="py-3 px-4">
                Updated
              </th>
              <th scope="col" className="py-3 px-4 text-right">
                Actions
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 text-slate-700">
            {accounts.map((acc) => {
              const assignedRuntime =
                acc.runtime_id !== null ? runtimesMap[acc.runtime_id] : null;
              const assignedDevice =
                acc.device_id !== null
                  ? devicesMap[acc.device_id]
                  : assignedRuntime && assignedRuntime.device_id
                  ? devicesMap[assignedRuntime.device_id]
                  : null;

              const isArchived = Boolean(acc.archived_at) || acc.status === "archived";

              return (
                <tr
                  key={acc.id}
                  className={`hover:bg-slate-50/60 transition-colors group ${
                    isArchived ? "bg-slate-50/40 opacity-80" : ""
                  }`}
                >
                  {/* Account / Display Name */}
                  <td className="py-3.5 px-5">
                    <div className="flex items-center gap-2.5">
                      <div className="w-8 h-8 rounded-full bg-gradient-to-br from-rose-100 to-pink-200 text-rose-700 flex items-center justify-center font-bold text-xs shrink-0 shadow-2xs">
                        {acc.display_name ? (
                          acc.display_name.charAt(0).toUpperCase()
                        ) : acc.name ? (
                          acc.name.charAt(0).toUpperCase()
                        ) : (
                          <User className="w-4 h-4" />
                        )}
                      </div>
                      <div className="min-w-0">
                        <div className="flex items-center gap-1.5 flex-wrap">
                          <p className="font-semibold text-slate-900 truncate max-w-[170px]">
                            {acc.display_name || acc.name}
                          </p>
                          <span className="font-mono text-[10px] text-slate-400">
                            #{acc.id}
                          </span>
                        </div>
                        {acc.tags && acc.tags.length > 0 && (
                          <div className="flex items-center gap-1 mt-0.5 flex-wrap">
                            {acc.tags.slice(0, 2).map((t) => (
                              <span
                                key={t}
                                className="px-1.5 py-0.2 rounded bg-slate-100 text-[10px] text-slate-600 font-mono"
                              >
                                {t}
                              </span>
                            ))}
                            {acc.tags.length > 2 && (
                              <span className="text-[10px] text-slate-400">
                                +{acc.tags.length - 2}
                              </span>
                            )}
                          </div>
                        )}
                      </div>
                    </div>
                  </td>

                  {/* Username / Handle */}
                  <td className="py-3.5 px-4 font-mono">
                    {acc.username ? (
                      <span className="font-medium text-slate-800">
                        @{acc.username}
                      </span>
                    ) : (
                      <span className="text-slate-400 italic text-[11px]">
                        No handle
                      </span>
                    )}
                  </td>

                  {/* Lifecycle Status */}
                  <td className="py-3.5 px-3">
                    <AccountStatusBadge status={acc.status} />
                  </td>

                  {/* Registration State & Health */}
                  <td className="py-3.5 px-3">
                    <div className="space-y-1">
                      <div>
                        <RegistrationStateBadge state={acc.registration_state} />
                      </div>
                      <div>
                        <AccountHealthBadge status={acc.health_status} />
                      </div>
                    </div>
                  </td>

                  {/* Niche */}
                  <td className="py-3.5 px-3">
                    {acc.niche ? (
                      <span className="inline-block px-2 py-0.5 rounded text-[11px] font-medium bg-slate-100 text-slate-700 capitalize max-w-[110px] truncate" title={acc.niche}>
                        {acc.niche}
                      </span>
                    ) : (
                      <span className="text-slate-300 font-mono text-xs">—</span>
                    )}
                  </td>

                  {/* Metrics */}
                  <td className="py-3.5 px-3 whitespace-nowrap">
                    <div className="space-y-0.5 text-[11px]">
                      <div className="flex items-center gap-1 text-slate-700">
                        <Users className="w-3 h-3 text-slate-400 shrink-0" />
                        <span className="font-semibold">
                          {formatMetricNumber(acc.follower_count)}
                        </span>
                        <span className="text-[10px] text-slate-400">fol</span>
                      </div>
                      <div className="flex items-center gap-1 text-slate-600">
                        <Heart className="w-3 h-3 text-rose-400 shrink-0" />
                        <span>{formatMetricNumber(acc.likes_count)}</span>
                        <span className="text-[10px] text-slate-400">likes</span>
                      </div>
                    </div>
                  </td>

                  {/* Runtime & Derived Device */}
                  <td className="py-3.5 px-4">
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
                          <p className="font-medium text-slate-900 truncate max-w-[130px]">
                            {assignedRuntime.name}
                          </p>
                          <div className="flex items-center gap-1 text-[10px] text-slate-500 truncate max-w-[130px]">
                            <Smartphone className="w-2.5 h-2.5 text-slate-400 shrink-0" />
                            <span className="truncate">
                              {assignedDevice
                                ? assignedDevice.name
                                : `Device #${acc.device_id || assignedRuntime.device_id}`}
                            </span>
                          </div>
                        </div>
                      </div>
                    ) : (
                      <div
                        className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[11px] font-medium bg-amber-50 text-amber-700 border border-amber-200"
                        title={`Runtime ID #${acc.runtime_id} not found in cache`}
                      >
                        <AlertCircle className="w-3 h-3 text-amber-500 shrink-0" />
                        <span>Runtime #{acc.runtime_id}</span>
                      </div>
                    )}
                  </td>

                  {/* Credentials / Secrets */}
                  <td className="py-3.5 px-3 whitespace-nowrap">
                    <AccountSecretPresenceBadge
                      present={acc.secret_present}
                      secretTypes={acc.secret_types}
                      onClick={() => onManageSecrets?.(acc)}
                    />
                  </td>

                  {/* Updated At */}
                  <td className="py-3.5 px-4 text-slate-500 whitespace-nowrap font-mono text-[11px]">
                    <div className="flex items-center gap-1">
                      <Calendar className="w-3 h-3 text-slate-400" />
                      <span>{formatDate(acc.updated_at)}</span>
                    </div>
                  </td>

                  {/* Actions */}
                  <td className="py-3.5 px-4 text-right whitespace-nowrap">
                    <div className="flex items-center justify-end gap-1">
                      {onManageSecrets && (
                        <button
                          type="button"
                          onClick={() => onManageSecrets(acc)}
                          className="p-1.5 rounded-lg text-slate-400 hover:text-emerald-700 hover:bg-emerald-50 transition-colors"
                          title="Manage write-only credentials"
                          aria-label={`Manage credentials for ${acc.display_name}`}
                        >
                          <KeyRound className="w-3.5 h-3.5" />
                        </button>
                      )}
                      {onAssignRuntime && (
                        <button
                          type="button"
                          onClick={() => onAssignRuntime(acc)}
                          className="p-1.5 rounded-lg text-slate-400 hover:text-cyan-700 hover:bg-cyan-50 transition-colors"
                          title="Assign or change execution runtime"
                          aria-label={`Assign Runtime for ${acc.display_name}`}
                        >
                          <Link2 className="w-3.5 h-3.5" />
                        </button>
                      )}
                      {onEditAccount && (
                        <button
                          type="button"
                          onClick={() => onEditAccount(acc)}
                          className="p-1.5 rounded-lg text-slate-400 hover:text-indigo-700 hover:bg-indigo-50 transition-colors"
                          title="Edit account details"
                          aria-label={`Edit account ${acc.display_name}`}
                        >
                          <Pencil className="w-3.5 h-3.5" />
                        </button>
                      )}
                      {onDeleteAccount && (
                        <button
                          type="button"
                          onClick={() => onDeleteAccount(acc)}
                          className="p-1.5 rounded-lg text-slate-400 hover:text-purple-700 hover:bg-purple-50 transition-colors"
                          title="Archive account"
                          aria-label={`Archive account ${acc.display_name}`}
                        >
                          <Archive className="w-3.5 h-3.5" />
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

import React from "react";
import { Account } from "@/types/account";
import { AccountStatusBadge } from "./AccountStatusBadge";
import { AccountLoadingState } from "./AccountLoadingState";
import { AccountEmptyState } from "./AccountEmptyState";
import { AccountErrorState } from "./AccountErrorState";
import { User, Calendar, Sparkles, Pencil, Trash2 } from "lucide-react";

interface AccountTableProps {
  accounts: Account[];
  isLoading: boolean;
  error: string | null;
  onRetry: () => void;
  isFiltered: boolean;
  onClearFilters: () => void;
  onCreateAccount: () => void;
  onEditAccount?: (account: Account) => void;
  onDeleteAccount?: (account: Account) => void;
}

export function AccountTable({
  accounts,
  isLoading,
  error,
  onRetry,
  isFiltered,
  onClearFilters,
  onCreateAccount,
  onEditAccount,
  onDeleteAccount,
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
                Updated At
              </th>
              <th scope="col" className="py-3 px-6 text-right">
                Actions
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 text-slate-700">
            {accounts.map((acc) => (
              <tr
                key={acc.id}
                className="hover:bg-slate-50/60 transition-colors group"
              >
                {/* Name */}
                <td className="py-4 px-6">
                  <div className="flex items-center gap-3">
                    <div className="w-8 h-8 rounded-full bg-gradient-to-br from-rose-100 to-pink-200 text-rose-700 flex items-center justify-center font-bold text-xs shrink-0 shadow-2xs">
                      {acc.name ? acc.name.charAt(0).toUpperCase() : <User className="w-4 h-4" />}
                    </div>
                    <div className="min-w-0">
                      <p className="font-semibold text-slate-900 truncate">
                        {acc.name}
                      </p>
                      {acc.notes && (
                        <p className="text-[11px] text-slate-400 truncate max-w-xs" title={acc.notes}>
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

                {/* Updated At */}
                <td className="py-4 px-6 text-slate-500 whitespace-nowrap">
                  <div className="flex items-center gap-1.5">
                    <Calendar className="w-3.5 h-3.5 text-slate-400" />
                    <span>{formatDate(acc.updated_at)}</span>
                  </div>
                </td>

                {/* Actions: Edit and Delete */}
                <td className="py-4 px-6 text-right whitespace-nowrap">
                  <div className="flex items-center justify-end gap-1.5">
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
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

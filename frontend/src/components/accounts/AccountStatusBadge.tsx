import React from "react";
import { CheckCircle2, AlertCircle, PauseCircle } from "lucide-react";
import { AccountStatus } from "@/types/account";

interface AccountStatusBadgeProps {
  status: AccountStatus;
}

export function AccountStatusBadge({ status }: AccountStatusBadgeProps) {
  const normalized = status.toLowerCase();

  if (normalized === "active") {
    return (
      <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-emerald-50 text-emerald-700 border border-emerald-200">
        <CheckCircle2 className="w-3 h-3 text-emerald-600" />
        <span>Active</span>
      </span>
    );
  }

  if (normalized === "suspended") {
    return (
      <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-rose-50 text-rose-700 border border-rose-200">
        <AlertCircle className="w-3 h-3 text-rose-600" />
        <span>Suspended</span>
      </span>
    );
  }

  if (normalized === "inactive") {
    return (
      <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-slate-100 text-slate-700 border border-slate-200">
        <PauseCircle className="w-3 h-3 text-slate-500" />
        <span>Inactive</span>
      </span>
    );
  }

  return (
    <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-slate-50 text-slate-600 border border-slate-200">
      <span className="w-1.5 h-1.5 rounded-full bg-slate-400" />
      <span>{status}</span>
    </span>
  );
}

import React from "react";
import { PublishingSessionStatus } from "@/types/publishing";
import {
  CheckCircle2,
  Clock,
  UserCheck,
  XCircle,
  AlertOctagon,
  Ban,
} from "lucide-react";

export function PublishingStatusBadge({
  status,
}: {
  status: PublishingSessionStatus | string;
}) {
  switch (status) {
    case "prepared":
      return (
        <span
          className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-100 text-emerald-800 border border-emerald-200"
          title="Environment prepared and approved. Prepared does not mean published."
        >
          <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
          <span>Prepared</span>
        </span>
      );
    case "waiting_approval":
      return (
        <span
          className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-100 text-amber-900 border border-amber-300 animate-pulse"
          title="App launched and content delivered. Waiting for operator review."
        >
          <UserCheck className="w-3.5 h-3.5 text-amber-700" />
          <span>Waiting Approval</span>
        </span>
      );
    case "preparing":
      return (
        <span
          className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-sky-100 text-sky-800 border border-sky-200"
          title="Preparation workflow running (runtime verification, app check, media delivery)."
        >
          <Clock className="w-3.5 h-3.5 text-sky-600 animate-spin" />
          <span>Preparing...</span>
        </span>
      );
    case "rejected":
      return (
        <span
          className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-rose-100 text-rose-800 border border-rose-200"
          title="Preparation rejected by operator."
        >
          <Ban className="w-3.5 h-3.5 text-rose-600" />
          <span>Rejected</span>
        </span>
      );
    case "failed":
      return (
        <span
          className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-rose-50 text-rose-700 border border-rose-200"
          title="Preparation workflow failed."
        >
          <XCircle className="w-3.5 h-3.5 text-rose-600" />
          <span>Failed</span>
        </span>
      );
    case "cancelled":
      return (
        <span
          className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-slate-100 text-slate-700 border border-slate-300"
          title="Preparation was cancelled."
        >
          <AlertOctagon className="w-3.5 h-3.5 text-slate-500" />
          <span>Cancelled</span>
        </span>
      );
    default:
      return (
        <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-slate-100 text-slate-600">
          <span>{status}</span>
        </span>
      );
  }
}

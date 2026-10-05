import React from "react";
import {
  AlertCircle,
  CheckCircle2,
  Clock,
  Loader2,
  OctagonX,
  PauseCircle,
  UserCheck,
  XCircle,
} from "lucide-react";
import { WorkflowStatus } from "@/types/workflow";

interface WorkflowStatusBadgeProps {
  status: WorkflowStatus;
  waitingReason?: string | null;
  className?: string;
  size?: "sm" | "md" | "lg";
}

export function WorkflowStatusBadge({
  status,
  waitingReason,
  className = "",
  size = "md",
}: WorkflowStatusBadgeProps) {
  const sizeClasses = {
    sm: "px-2 py-0.5 text-xs gap-1",
    md: "px-2.5 py-1 text-xs gap-1.5",
    lg: "px-3 py-1.5 text-sm gap-2",
  }[size];

  const iconSizes = {
    sm: "w-3 h-3",
    md: "w-3.5 h-3.5",
    lg: "w-4 h-4",
  }[size];

  switch (status) {
    case "draft":
      return (
        <span
          className={`inline-flex items-center font-medium rounded-full bg-slate-100 text-slate-700 border border-slate-200 ${sizeClasses} ${className}`}
        >
          <Clock className={`${iconSizes} text-slate-500`} />
          <span>Draft</span>
        </span>
      );

    case "pending":
      return (
        <span
          className={`inline-flex items-center font-medium rounded-full bg-blue-50 text-blue-700 border border-blue-200 ${sizeClasses} ${className}`}
        >
          <Clock className={`${iconSizes} text-blue-500`} />
          <span>Pending</span>
        </span>
      );

    case "running":
      return (
        <span
          className={`inline-flex items-center font-medium rounded-full bg-sky-50 text-sky-700 border border-sky-200 animate-pulse ${sizeClasses} ${className}`}
        >
          <Loader2 className={`${iconSizes} animate-spin text-sky-600`} />
          <span>Running</span>
        </span>
      );

    case "waiting":
      if (
        waitingReason === "waiting_for_approval" ||
        waitingReason === "approval"
      ) {
        return (
          <span
            className={`inline-flex items-center font-medium rounded-full bg-amber-50 text-amber-800 border border-amber-300 ${sizeClasses} ${className}`}
          >
            <UserCheck className={`${iconSizes} text-amber-600`} />
            <span>Awaiting Approval</span>
          </span>
        );
      }
      return (
        <span
          className={`inline-flex items-center font-medium rounded-full bg-indigo-50 text-indigo-700 border border-indigo-200 ${sizeClasses} ${className}`}
        >
          <Clock className={`${iconSizes} text-indigo-500`} />
          <span>Waiting</span>
        </span>
      );

    case "paused":
      return (
        <span
          className={`inline-flex items-center font-medium rounded-full bg-amber-100 text-amber-900 border border-amber-300 ${sizeClasses} ${className}`}
        >
          <PauseCircle className={`${iconSizes} text-amber-700`} />
          <span>Paused</span>
        </span>
      );

    case "cancelling":
      return (
        <span
          className={`inline-flex items-center font-medium rounded-full bg-orange-50 text-orange-800 border border-orange-200 animate-pulse ${sizeClasses} ${className}`}
        >
          <Loader2 className={`${iconSizes} animate-spin text-orange-600`} />
          <span>Cancelling...</span>
        </span>
      );

    case "cancelled":
      return (
        <span
          className={`inline-flex items-center font-medium rounded-full bg-slate-100 text-slate-600 border border-slate-300 ${sizeClasses} ${className}`}
        >
          <OctagonX className={`${iconSizes} text-slate-500`} />
          <span>Cancelled</span>
        </span>
      );

    case "succeeded":
      return (
        <span
          className={`inline-flex items-center font-medium rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200 ${sizeClasses} ${className}`}
        >
          <CheckCircle2 className={`${iconSizes} text-emerald-600`} />
          <span>Succeeded</span>
        </span>
      );

    case "failed":
      return (
        <span
          className={`inline-flex items-center font-medium rounded-full bg-rose-50 text-rose-700 border border-rose-200 ${sizeClasses} ${className}`}
        >
          <AlertCircle className={`${iconSizes} text-rose-600`} />
          <span>Failed</span>
        </span>
      );

    default:
      return (
        <span
          className={`inline-flex items-center font-medium rounded-full bg-slate-100 text-slate-700 border border-slate-200 ${sizeClasses} ${className}`}
        >
          <XCircle className={`${iconSizes} text-slate-400`} />
          <span className="capitalize">{status}</span>
        </span>
      );
  }
}

import {
  Ban,
  CheckCircle2,
  Clock,
  Loader2,
  XCircle,
} from "lucide-react";
import { ContentDeliveryStatus } from "@/types/content";

interface ContentDeliveryBadgeProps {
  status: ContentDeliveryStatus;
  size?: "sm" | "md";
}

export function ContentDeliveryBadge({
  status,
  size = "md",
}: ContentDeliveryBadgeProps) {
  const sizeClasses =
    size === "sm" ? "px-2 py-0.5 text-[10px]" : "px-2.5 py-1 text-xs";

  switch (status) {
    case "succeeded":
      return (
        <span
          className={`inline-flex items-center gap-1.5 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200/80 font-medium ${sizeClasses}`}
        >
          <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
          <span>Delivered</span>
        </span>
      );

    case "delivering":
      return (
        <span
          className={`inline-flex items-center gap-1.5 rounded-full bg-blue-50 text-blue-700 border border-blue-200/80 font-medium ${sizeClasses}`}
        >
          <Loader2 className="w-3.5 h-3.5 text-blue-600 animate-spin" />
          <span>Delivering</span>
        </span>
      );

    case "pending":
      return (
        <span
          className={`inline-flex items-center gap-1.5 rounded-full bg-slate-100 text-slate-700 border border-slate-200 font-medium ${sizeClasses}`}
        >
          <Clock className="w-3.5 h-3.5 text-slate-500" />
          <span>Pending</span>
        </span>
      );

    case "failed":
      return (
        <span
          className={`inline-flex items-center gap-1.5 rounded-full bg-rose-50 text-rose-700 border border-rose-200/80 font-medium ${sizeClasses}`}
        >
          <XCircle className="w-3.5 h-3.5 text-rose-600" />
          <span>Failed</span>
        </span>
      );

    case "cancelled":
      return (
        <span
          className={`inline-flex items-center gap-1.5 rounded-full bg-purple-50 text-purple-700 border border-purple-200/80 font-medium ${sizeClasses}`}
        >
          <Ban className="w-3.5 h-3.5 text-purple-600" />
          <span>Cancelled</span>
        </span>
      );

    default:
      return (
        <span
          className={`inline-flex items-center gap-1.5 rounded-full bg-slate-100 text-slate-700 border border-slate-200 font-medium ${sizeClasses}`}
        >
          <span>{status}</span>
        </span>
      );
  }
}

import {
  AlertCircle,
  Archive,
  CheckCircle2,
  Loader2,
  Trash2,
} from "lucide-react";
import { ContentAssetStatus, ContentVersionProcessingStatus } from "@/types/content";

interface ContentStatusBadgeProps {
  status: ContentAssetStatus | ContentVersionProcessingStatus;
  size?: "sm" | "md";
}

export function ContentStatusBadge({
  status,
  size = "md",
}: ContentStatusBadgeProps) {
  const sizeClasses =
    size === "sm" ? "px-2 py-0.5 text-[10px]" : "px-2.5 py-1 text-xs";

  switch (status) {
    case "ready":
      return (
        <span
          className={`inline-flex items-center gap-1.5 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200/80 font-medium ${sizeClasses}`}
        >
          <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
          <span>Ready</span>
        </span>
      );

    case "processing":
      return (
        <span
          className={`inline-flex items-center gap-1.5 rounded-full bg-amber-50 text-amber-700 border border-amber-200/80 font-medium ${sizeClasses}`}
        >
          <Loader2 className="w-3.5 h-3.5 text-amber-600 animate-spin" />
          <span>Processing</span>
        </span>
      );

    case "invalid":
      return (
        <span
          className={`inline-flex items-center gap-1.5 rounded-full bg-rose-50 text-rose-700 border border-rose-200/80 font-medium ${sizeClasses}`}
        >
          <AlertCircle className="w-3.5 h-3.5 text-rose-600" />
          <span>Invalid</span>
        </span>
      );

    case "archived":
      return (
        <span
          className={`inline-flex items-center gap-1.5 rounded-full bg-slate-100 text-slate-700 border border-slate-300 font-medium ${sizeClasses}`}
        >
          <Archive className="w-3.5 h-3.5 text-slate-500" />
          <span>Archived</span>
        </span>
      );

    case "deleted":
      return (
        <span
          className={`inline-flex items-center gap-1.5 rounded-full bg-slate-200 text-slate-600 border border-slate-300 font-medium ${sizeClasses}`}
        >
          <Trash2 className="w-3.5 h-3.5 text-slate-500" />
          <span>Deleted</span>
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

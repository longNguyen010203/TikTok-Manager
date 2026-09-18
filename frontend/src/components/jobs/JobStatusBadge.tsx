import {
  Ban,
  CheckCircle2,
  CircleDashed,
  Clock3,
  LoaderCircle,
  XCircle,
} from "lucide-react";
import { JobStatus } from "@/types/job";

const statusStyles: Record<
  JobStatus,
  { label: string; className: string; icon: typeof Clock3 }
> = {
  pending: {
    label: "Pending",
    className: "bg-amber-50 text-amber-700 border-amber-200",
    icon: Clock3,
  },
  running: {
    label: "Running",
    className: "bg-cyan-50 text-cyan-700 border-cyan-200",
    icon: LoaderCircle,
  },
  succeeded: {
    label: "Succeeded",
    className: "bg-emerald-50 text-emerald-700 border-emerald-200",
    icon: CheckCircle2,
  },
  failed: {
    label: "Failed",
    className: "bg-rose-50 text-rose-700 border-rose-200",
    icon: XCircle,
  },
  retrying: {
    label: "Retrying",
    className: "bg-indigo-50 text-indigo-700 border-indigo-200",
    icon: CircleDashed,
  },
  cancelled: {
    label: "Cancelled",
    className: "bg-slate-100 text-slate-600 border-slate-200",
    icon: Ban,
  },
};

export function JobStatusBadge({ status }: { status: JobStatus }) {
  const style = statusStyles[status] ?? statusStyles.pending;
  const Icon = style.icon;

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[11px] font-semibold ${style.className}`}
    >
      <Icon
        className={`h-3 w-3 ${status === "running" ? "animate-spin" : ""}`}
      />
      {style.label}
    </span>
  );
}

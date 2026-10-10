import React from "react";
import {
  CheckCircle2,
  AlertCircle,
  PauseCircle,
  Clock,
  Ban,
  Archive,
  AlertTriangle,
  HelpCircle,
  ShieldCheck,
  ShieldAlert,
  KeyRound,
  Shield,
} from "lucide-react";
import {
  AccountHealthStatus,
  AccountSecretType,
  AccountStatus,
  RegistrationState,
} from "@/types/account";

interface AccountStatusBadgeProps {
  status: AccountStatus;
}

export function AccountStatusBadge({ status }: AccountStatusBadgeProps) {
  const normalized = status.toLowerCase();

  switch (normalized) {
    case "active":
      return (
        <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
          <CheckCircle2 className="w-3 h-3 text-emerald-600" />
          <span>Active</span>
        </span>
      );
    case "pending":
      return (
        <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-50 text-amber-700 border border-amber-200">
          <Clock className="w-3 h-3 text-amber-600" />
          <span>Pending</span>
        </span>
      );
    case "inactive":
      return (
        <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium bg-slate-100 text-slate-700 border border-slate-200">
          <PauseCircle className="w-3 h-3 text-slate-500" />
          <span>Inactive</span>
        </span>
      );
    case "restricted":
      return (
        <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-orange-50 text-orange-700 border border-orange-200">
          <AlertTriangle className="w-3 h-3 text-orange-600" />
          <span>Restricted</span>
        </span>
      );
    case "suspended":
      return (
        <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-rose-50 text-rose-700 border border-rose-200">
          <AlertCircle className="w-3 h-3 text-rose-600" />
          <span>Suspended</span>
        </span>
      );
    case "disabled":
      return (
        <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium bg-zinc-100 text-zinc-600 border border-zinc-300">
          <Ban className="w-3 h-3 text-zinc-500" />
          <span>Disabled</span>
        </span>
      );
    case "archived":
      return (
        <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium bg-purple-50 text-purple-700 border border-purple-200">
          <Archive className="w-3 h-3 text-purple-500" />
          <span>Archived</span>
        </span>
      );
    default:
      return (
        <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium bg-slate-50 text-slate-600 border border-slate-200">
          <span className="w-1.5 h-1.5 rounded-full bg-slate-400" />
          <span className="capitalize">{status}</span>
        </span>
      );
  }
}

export function RegistrationStateBadge({
  state,
  compact = false,
}: {
  state: RegistrationState;
  compact?: boolean;
}) {
  switch (state) {
    case "registered":
      return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
          <CheckCircle2 className="w-3 h-3 text-emerald-600 shrink-0" />
          <span>Registered</span>
        </span>
      );
    case "pending":
      return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-medium bg-amber-50 text-amber-700 border border-amber-200">
          <Clock className="w-3 h-3 text-amber-600 shrink-0" />
          <span>{compact ? "Pending" : "Pending registration"}</span>
        </span>
      );
    case "failed":
      return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-medium bg-rose-50 text-rose-700 border border-rose-200">
          <AlertCircle className="w-3 h-3 text-rose-600 shrink-0" />
          <span>{compact ? "Failed" : "Registration failed"}</span>
        </span>
      );
    case "unknown":
    default:
      return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-medium bg-slate-100 text-slate-500 border border-slate-200">
          <HelpCircle className="w-3 h-3 text-slate-400 shrink-0" />
          <span>Unknown</span>
        </span>
      );
  }
}

export function RegistrationReadyBadge({
  ready,
  reasons = [],
}: {
  ready?: boolean;
  reasons?: string[];
}) {
  if (ready) {
    return (
      <span
        className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200"
        title="Ready for automation"
      >
        <CheckCircle2 className="w-3 h-3 text-emerald-600" />
        <span>Ready</span>
      </span>
    );
  }

  const tooltip =
    reasons.length > 0
      ? `Not ready: ${reasons.join(", ")}`
      : "Not ready for automation";

  return (
    <span
      className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-medium bg-slate-100 text-slate-600 border border-slate-200"
      title={tooltip}
    >
      <Clock className="w-3 h-3 text-slate-400" />
      <span>Not ready</span>
    </span>
  );
}

export function AccountHealthSubtle({ status }: { status: AccountHealthStatus }) {
  const dotColor =
    {
      healthy: "bg-emerald-500",
      warning: "bg-amber-500",
      unhealthy: "bg-rose-500",
      unknown: "bg-slate-400",
    }[status] || "bg-slate-400";

  return (
    <span className="inline-flex items-center gap-1.5 text-[11px] text-slate-500 font-medium">
      <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${dotColor}`} />
      <span className="capitalize">{status}</span>
    </span>
  );
}

export function AccountHealthBadge({
  status,
  variant = "badge",
}: {
  status: AccountHealthStatus;
  variant?: "badge" | "subtle" | "compact";
}) {
  if (variant === "subtle") {
    return <AccountHealthSubtle status={status} />;
  }

  if (variant === "compact") {
    const dotColor =
      {
        healthy: "bg-emerald-500",
        warning: "bg-amber-500",
        unhealthy: "bg-rose-500",
        unknown: "bg-slate-400",
      }[status] || "bg-slate-400";

    const textColor =
      {
        healthy: "text-emerald-700",
        warning: "text-amber-700",
        unhealthy: "text-rose-700",
        unknown: "text-slate-600",
      }[status] || "text-slate-600";

    const label =
      {
        healthy: "Healthy",
        warning: "Warning",
        unhealthy: "Unhealthy",
        unknown: "Unknown",
      }[status] || "Unknown";

    return (
      <span
        className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-medium bg-slate-50 border border-slate-200/90 ${textColor}`}
        title={`Health: ${label}`}
      >
        <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${dotColor}`} />
        <span>{label}</span>
      </span>
    );
  }

  switch (status) {
    case "healthy":
      return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-medium bg-emerald-50 text-emerald-700 border border-emerald-200">
          <ShieldCheck className="w-3 h-3 text-emerald-600" />
          <span>Healthy</span>
        </span>
      );
    case "warning":
      return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-medium bg-amber-50 text-amber-700 border border-amber-200">
          <AlertTriangle className="w-3 h-3 text-amber-600" />
          <span>Warning</span>
        </span>
      );
    case "unhealthy":
      return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-medium bg-rose-50 text-rose-700 border border-rose-200">
          <ShieldAlert className="w-3 h-3 text-rose-600" />
          <span>Unhealthy</span>
        </span>
      );
    case "unknown":
    default:
      return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-medium bg-slate-100 text-slate-500 border border-slate-200">
          <Shield className="w-3 h-3 text-slate-400" />
          <span>Unknown</span>
        </span>
      );
  }
}

export function AccountSecretPresenceBadge({
  present,
  secretTypes,
  onClick,
}: {
  present: boolean;
  secretTypes?: AccountSecretType[];
  onClick?: () => void;
}) {
  const count = secretTypes?.length ?? (present ? 1 : 0);

  if (!present || count === 0) {
    return (
      <button
        type="button"
        onClick={onClick}
        className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-[11px] font-medium text-slate-500 bg-slate-50 hover:bg-slate-100 border border-slate-200 transition-colors cursor-pointer"
        title="No write-only credentials configured. Click to configure."
      >
        <KeyRound className="w-3 h-3 text-slate-400" />
        <span>None</span>
      </button>
    );
  }

  return (
    <button
      type="button"
      onClick={onClick}
      className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-[11px] font-semibold text-emerald-800 bg-emerald-50 hover:bg-emerald-100 border border-emerald-200 transition-colors cursor-pointer"
      title={`Configured credentials: ${secretTypes?.join(", ") || "present"}. Click to manage.`}
    >
      <KeyRound className="w-3 h-3 text-emerald-600" />
      <span>{count} Secret{count > 1 ? "s" : ""}</span>
    </button>
  );
}

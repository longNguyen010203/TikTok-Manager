import React from "react";
import {
  ManagedAppPolicy,
  ManagedAppStatus,
  ManagedAppVersionStatus,
  InspectionLevel,
} from "@/types/managedApp";
import { CheckCircle2, Shield, ShieldCheck, XCircle, Clock } from "lucide-react";

export function AppStatusBadge({ status }: { status: ManagedAppStatus }) {
  switch (status) {
    case "active":
      return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
          <CheckCircle2 className="w-3 h-3 text-emerald-600" />
          <span>Active</span>
        </span>
      );
    case "disabled":
      return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-semibold bg-slate-100 text-slate-700 border border-slate-300">
          <span>Disabled</span>
        </span>
      );
    case "archived":
      return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-semibold bg-amber-50 text-amber-700 border border-amber-200">
          <span>Archived</span>
        </span>
      );
  }
}

export function InstallPolicyBadge({ policy }: { policy: ManagedAppPolicy }) {
  switch (policy) {
    case "required":
      return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[11px] font-semibold bg-rose-50 text-rose-700 border border-rose-200">
          <span>Required</span>
        </span>
      );
    case "optional":
      return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[11px] font-semibold bg-blue-50 text-blue-700 border border-blue-200">
          <span>Optional</span>
        </span>
      );
    case "disabled":
      return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[11px] font-medium bg-slate-100 text-slate-600 border border-slate-200">
          <span>Disabled</span>
        </span>
      );
  }
}

export function AssuranceLevelBadge({ level }: { level: InspectionLevel }) {
  if (level === "verified") {
    return (
      <span
        className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[11px] font-semibold bg-emerald-50 text-emerald-800 border border-emerald-200"
        title="Verified assurance: pre-and-post-install verification with discovered package and signature check"
      >
        <ShieldCheck className="w-3 h-3 text-emerald-600" />
        <span>Verified</span>
      </span>
    );
  }
  return (
    <span
      className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[11px] font-semibold bg-amber-50 text-amber-800 border border-amber-200"
      title="Basic assurance: APK admitted and hashed. Package and signature assurance verified post-installation."
    >
      <Shield className="w-3 h-3 text-amber-600" />
      <span>Basic</span>
    </span>
  );
}

export function VersionStatusBadge({ status }: { status: ManagedAppVersionStatus }) {
  switch (status) {
    case "ready":
      return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
          <CheckCircle2 className="w-3 h-3 text-emerald-600" />
          <span>Ready</span>
        </span>
      );
    case "inspecting":
    case "uploaded":
      return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-semibold bg-sky-50 text-sky-700 border border-sky-200">
          <Clock className="w-3 h-3 text-sky-600" />
          <span>Inspecting</span>
        </span>
      );
    case "invalid":
      return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-semibold bg-rose-50 text-rose-700 border border-rose-200">
          <XCircle className="w-3 h-3 text-rose-600" />
          <span>Invalid</span>
        </span>
      );
    case "retired":
      return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-semibold bg-slate-100 text-slate-600 border border-slate-200">
          <span>Retired</span>
        </span>
      );
  }
}

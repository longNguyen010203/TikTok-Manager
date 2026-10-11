"use client";

import React from "react";
import { Handle, Position, NodeProps } from "@xyflow/react";
import { User, KeyRound, CheckCircle2, Clock, AlertCircle } from "lucide-react";
import { AccountNodeMetadata } from "@/types/topology";

export interface AccountNodeData {
  entity_id: number;
  label: string;
  status: string;
  metadata: AccountNodeMetadata;
  isHighlighted?: boolean;
  isNew?: boolean;
}

export function AccountNode({ data, selected }: NodeProps) {
  const nodeData = data as unknown as AccountNodeData;
  const isSelected = selected || nodeData.isHighlighted;
  const meta = nodeData.metadata;

  const isReady = meta.registration_ready;

  const healthDotColor =
    {
      healthy: "bg-emerald-500",
      warning: "bg-amber-500",
      unhealthy: "bg-rose-500",
      unknown: "bg-slate-300",
    }[meta.health_status] || "bg-slate-300";

  return (
    <div
      className={`relative bg-white rounded-xl border-2 transition-all duration-150 p-3 shadow-2xs w-[250px] ${
        isSelected
          ? "border-rose-500 ring-2 ring-rose-400/40 shadow-md"
          : nodeData.isNew
          ? "border-emerald-400 ring-2 ring-emerald-300/30"
          : meta.runtime_id === null
          ? "border-amber-300/90 bg-amber-50/20"
          : "border-slate-200/90 hover:border-slate-300 hover:shadow-xs"
      }`}
    >
      {/* Incoming edge handle from Runtime (if assigned) */}
      <Handle
        type="target"
        position={Position.Left}
        id="in"
        className="!w-2.5 !h-2.5 !bg-rose-500 !border-2 !border-white !-left-1.5"
      />

      {/* Top Header Tag */}
      <div className="flex items-center justify-between gap-1 mb-1.5">
        <div className="flex items-center gap-1.5 min-w-0">
          <div className="p-1 rounded-md bg-rose-50 text-rose-700 shrink-0">
            <User className="w-3.5 h-3.5" />
          </div>
          <span className="text-[10px] font-bold uppercase tracking-wider text-rose-700">
            Account
          </span>
          {meta.secret_present && (
            <span
              className="inline-flex items-center p-0.5 rounded text-emerald-700 bg-emerald-50 border border-emerald-200"
              title="Credentials configured"
            >
              <KeyRound className="w-2.5 h-2.5" />
            </span>
          )}
        </div>

        <div className="flex items-center gap-1 shrink-0">
          {nodeData.isNew && (
            <span className="px-1.5 py-0.2 rounded text-[9px] font-bold bg-emerald-100 text-emerald-800">
              NEW
            </span>
          )}
          <span className="text-[10px] font-mono text-slate-400">
            #{nodeData.entity_id}
          </span>
        </div>
      </div>

      {/* Account Display Name & Username */}
      <div className="mb-2">
        <p
          className="text-xs font-bold text-slate-900 truncate"
          title={meta.display_name}
        >
          {meta.display_name}
        </p>
        <p className="text-[11px] font-mono text-slate-500 truncate">
          {meta.username ? `@${meta.username}` : <span className="italic text-slate-400">No handle</span>}
        </p>
      </div>

      {/* Badges Row: Registration, Ready, Health */}
      <div className="flex items-center gap-1 flex-wrap pt-2 border-t border-slate-100 text-[10px]">
        {/* Registration State */}
        <span
          className={`inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded font-medium border ${
            meta.registration_state === "registered"
              ? "bg-emerald-50 text-emerald-700 border-emerald-200"
              : meta.registration_state === "pending"
              ? "bg-amber-50 text-amber-700 border-amber-200"
              : meta.registration_state === "failed"
              ? "bg-rose-50 text-rose-700 border-rose-200"
              : "bg-slate-50 text-slate-600 border-slate-200"
          }`}
          title={`Registration: ${meta.registration_state}`}
        >
          {meta.registration_state === "registered" ? (
            <CheckCircle2 className="w-2.5 h-2.5 text-emerald-600" />
          ) : meta.registration_state === "pending" ? (
            <Clock className="w-2.5 h-2.5 text-amber-600" />
          ) : meta.registration_state === "failed" ? (
            <AlertCircle className="w-2.5 h-2.5 text-rose-600" />
          ) : null}
          <span className="capitalize">{meta.registration_state}</span>
        </span>

        {/* Readiness */}
        <span
          className={`inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded font-medium border ${
            isReady
              ? "bg-emerald-50 text-emerald-700 border-emerald-200 font-semibold"
              : "bg-slate-100 text-slate-600 border-slate-200"
          }`}
          title={isReady ? "Ready for automation" : "Not ready for automation"}
        >
          {isReady ? (
            <CheckCircle2 className="w-2.5 h-2.5 text-emerald-600" />
          ) : (
            <Clock className="w-2.5 h-2.5 text-slate-400" />
          )}
          <span>{isReady ? "Ready" : "Not ready"}</span>
        </span>

        {/* Health */}
        <span
          className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded font-medium bg-slate-50 text-slate-600 border border-slate-200/80"
          title={`Health: ${meta.health_status}`}
        >
          <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${healthDotColor}`} />
          <span className="capitalize">{meta.health_status}</span>
        </span>
      </div>

      {/* Unassigned Warning Banner (if detached) */}
      {meta.runtime_id === null && (
        <div className="mt-1.5 text-[9px] font-semibold text-amber-700 bg-amber-50 px-1.5 py-0.5 rounded border border-amber-200 flex items-center gap-1">
          <AlertCircle className="w-2.5 h-2.5 text-amber-600 shrink-0" />
          <span>Unassigned Account</span>
        </div>
      )}
    </div>
  );
}

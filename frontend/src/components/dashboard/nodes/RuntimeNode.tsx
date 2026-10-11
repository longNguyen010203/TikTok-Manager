"use client";

import React from "react";
import { Handle, Position, NodeProps } from "@xyflow/react";
import { Cpu, Users, Play, Pause, AlertCircle } from "lucide-react";
import { RuntimeNodeMetadata } from "@/types/topology";

export interface RuntimeNodeData {
  entity_id: number;
  label: string;
  status: string;
  metadata: RuntimeNodeMetadata;
  isHighlighted?: boolean;
  isNew?: boolean;
}

export function RuntimeNode({ data, selected }: NodeProps) {
  const nodeData = data as unknown as RuntimeNodeData;
  const isSelected = selected || nodeData.isHighlighted;

  const statusLower = nodeData.status.toLowerCase();
  const isRunning = statusLower === "running";
  const isIdle = statusLower === "idle";

  return (
    <div
      className={`relative bg-white rounded-xl border-2 transition-all duration-150 p-3 shadow-2xs w-[240px] ${
        isSelected
          ? "border-sky-500 ring-2 ring-sky-400/40 shadow-md"
          : nodeData.isNew
          ? "border-emerald-400 ring-2 ring-emerald-300/30"
          : "border-slate-200/90 hover:border-slate-300 hover:shadow-xs"
      }`}
    >
      {/* Incoming edge handle from Device */}
      <Handle
        type="target"
        position={Position.Left}
        id="in"
        className="!w-2.5 !h-2.5 !bg-sky-500 !border-2 !border-white !-left-1.5"
      />

      {/* Top Header Tag */}
      <div className="flex items-center justify-between gap-1 mb-2">
        <div className="flex items-center gap-1.5">
          <div className="p-1 rounded-md bg-sky-50 text-sky-700">
            <Cpu className="w-3.5 h-3.5" />
          </div>
          <span className="text-[10px] font-bold uppercase tracking-wider text-sky-700">
            Runtime
          </span>
        </div>
        <div className="flex items-center gap-1">
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

      {/* Runtime Name & Host Device Relationship */}
      <div className="mb-2">
        <p
          className="text-xs font-bold text-slate-900 truncate"
          title={nodeData.metadata.name}
        >
          {nodeData.metadata.name}
        </p>
        <p className="text-[10px] text-slate-500 truncate">
          {nodeData.metadata.runtime_type} &bull; Hosted by Device #{nodeData.metadata.device_id}
        </p>
      </div>

      {/* Status & Assigned Account Count */}
      <div className="flex items-center justify-between pt-2 border-t border-slate-100 text-[11px]">
        <div className="flex items-center gap-1">
          {isRunning ? (
            <Play className="w-2.5 h-2.5 fill-emerald-600 text-emerald-600" />
          ) : isIdle ? (
            <Pause className="w-2.5 h-2.5 text-blue-500" />
          ) : (
            <AlertCircle className="w-2.5 h-2.5 text-slate-400" />
          )}
          <span
            className={`font-semibold capitalize text-[10px] ${
              isRunning
                ? "text-emerald-700"
                : isIdle
                ? "text-blue-700"
                : "text-slate-500"
            }`}
          >
            {nodeData.status}
          </span>
        </div>

        <div className="flex items-center gap-1 px-1.5 py-0.5 rounded bg-sky-50/70 border border-sky-100 text-sky-700 text-[10px] font-semibold">
          <Users className="w-2.5 h-2.5 text-sky-500" />
          <span>
            {nodeData.metadata.assigned_account_count} Account{nodeData.metadata.assigned_account_count === 1 ? "" : "s"}
          </span>
        </div>
      </div>

      {/* Outgoing edge handle to Accounts */}
      <Handle
        type="source"
        position={Position.Right}
        id="out"
        className="!w-2.5 !h-2.5 !bg-sky-500 !border-2 !border-white !-right-1.5"
      />
    </div>
  );
}

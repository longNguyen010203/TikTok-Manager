"use client";

import React from "react";
import { Handle, Position, NodeProps } from "@xyflow/react";
import { Smartphone, Server, CheckCircle2, AlertCircle } from "lucide-react";
import { DeviceNodeMetadata } from "@/types/topology";

export interface DeviceNodeData {
  entity_id: number;
  label: string;
  status: string;
  metadata: DeviceNodeMetadata;
  isHighlighted?: boolean;
  isNew?: boolean;
}

export function DeviceNode({ data, selected }: NodeProps) {
  const nodeData = data as unknown as DeviceNodeData;
  const isOnline = nodeData.status.toLowerCase() === "online";
  const isSelected = selected || nodeData.isHighlighted;

  return (
    <div
      className={`relative bg-white rounded-xl border-2 transition-all duration-150 p-3 shadow-2xs w-[240px] ${
        isSelected
          ? "border-indigo-500 ring-2 ring-indigo-400/40 shadow-md"
          : nodeData.isNew
          ? "border-emerald-400 ring-2 ring-emerald-300/30"
          : "border-slate-200/90 hover:border-slate-300 hover:shadow-xs"
      }`}
    >
      {/* Node Type Banner Tag */}
      <div className="flex items-center justify-between gap-1 mb-2">
        <div className="flex items-center gap-1.5">
          <div className="p-1 rounded-md bg-indigo-50 text-indigo-700">
            <Smartphone className="w-3.5 h-3.5" />
          </div>
          <span className="text-[10px] font-bold uppercase tracking-wider text-indigo-700">
            Device
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

      {/* Device Name */}
      <div className="mb-2">
        <p
          className="text-xs font-bold text-slate-900 truncate"
          title={nodeData.metadata.name}
        >
          {nodeData.metadata.name}
        </p>
        <p className="text-[10px] text-slate-500 capitalize">
          {nodeData.metadata.platform} {nodeData.metadata.os_version && `v${nodeData.metadata.os_version}`} &bull; {nodeData.metadata.device_type}
        </p>
      </div>

      {/* Status & Runtimes Hosted Count */}
      <div className="flex items-center justify-between pt-2 border-t border-slate-100 text-[11px]">
        <div className="flex items-center gap-1">
          {isOnline ? (
            <CheckCircle2 className="w-3 h-3 text-emerald-600" />
          ) : (
            <AlertCircle className="w-3 h-3 text-slate-400" />
          )}
          <span
            className={`font-semibold capitalize text-[10px] ${
              isOnline ? "text-emerald-700" : "text-slate-500"
            }`}
          >
            {nodeData.status}
          </span>
        </div>

        <div className="flex items-center gap-1 px-1.5 py-0.5 rounded bg-indigo-50/70 border border-indigo-100 text-indigo-700 text-[10px] font-semibold">
          <Server className="w-2.5 h-2.5 text-indigo-500" />
          <span>
            {nodeData.metadata.runtime_count} Runtime{nodeData.metadata.runtime_count === 1 ? "" : "s"}
          </span>
        </div>
      </div>

      {/* Target/Source Handles */}
      <Handle
        type="source"
        position={Position.Right}
        id="out"
        className="!w-2.5 !h-2.5 !bg-indigo-500 !border-2 !border-white !-right-1.5"
      />
    </div>
  );
}

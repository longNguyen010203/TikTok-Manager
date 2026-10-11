"use client";

import React from "react";
import Link from "next/link";
import {
  X,
  ExternalLink,
  Smartphone,
  Cpu,
  User,
  AlertCircle,
  KeyRound,
  ArrowRight,
} from "lucide-react";
import {
  DashboardTopology,
  DeviceTopologyNode,
  RuntimeTopologyNode,
  AccountTopologyNode,
} from "@/types/topology";

interface TopologyDetailsDrawerProps {
  selectedNodeId: string | null;
  topology: DashboardTopology | null;
  onClose: () => void;
  onSelectNode: (nodeId: string) => void;
}

export function TopologyDetailsDrawer({
  selectedNodeId,
  topology,
  onClose,
  onSelectNode,
}: TopologyDetailsDrawerProps) {
  if (!selectedNodeId || !topology) return null;

  const node = topology.nodes.find((n) => n.id === selectedNodeId);
  if (!node) return null;

  // Find relationships for this node
  const hostedRuntimes = topology.edges
    .filter((e) => e.type === "hosts" && e.source === node.id)
    .map((e) => topology.nodes.find((n) => n.id === e.target))
    .filter(Boolean) as RuntimeTopologyNode[];

  const assignedAccounts = topology.edges
    .filter((e) => e.type === "assigned" && e.source === node.id)
    .map((e) => topology.nodes.find((n) => n.id === e.target))
    .filter(Boolean) as AccountTopologyNode[];

  const hostDeviceEdge = topology.edges.find(
    (e) => e.type === "hosts" && e.target === node.id
  );
  const hostDevice = hostDeviceEdge
    ? (topology.nodes.find((n) => n.id === hostDeviceEdge.source) as DeviceTopologyNode)
    : null;

  const assignedRuntimeEdge = topology.edges.find(
    (e) => e.type === "assigned" && e.target === node.id
  );
  const assignedRuntime = assignedRuntimeEdge
    ? (topology.nodes.find((n) => n.id === assignedRuntimeEdge.source) as RuntimeTopologyNode)
    : null;

  const hostDeviceForAccount = assignedRuntime
    ? (topology.nodes.find(
        (n) => n.id === `device:${assignedRuntime.metadata.device_id}`
      ) as DeviceTopologyNode)
    : null;

  return (
    <div className="absolute right-3 top-3 bottom-3 w-80 sm:w-96 bg-white/95 backdrop-blur-md rounded-2xl border border-slate-200/90 shadow-xl z-40 flex flex-col overflow-hidden animate-in fade-in slide-in-from-right-4 duration-200">
      {/* Drawer Header */}
      <div className="p-4 border-b border-slate-200/80 flex items-center justify-between gap-3 bg-slate-50/50">
        <div className="flex items-center gap-2 min-w-0">
          <div
            className={`p-2 rounded-xl shrink-0 ${
              node.type === "device"
                ? "bg-indigo-50 text-indigo-700"
                : node.type === "runtime"
                ? "bg-sky-50 text-sky-700"
                : "bg-rose-50 text-rose-700"
            }`}
          >
            {node.type === "device" ? (
              <Smartphone className="w-4 h-4" />
            ) : node.type === "runtime" ? (
              <Cpu className="w-4 h-4" />
            ) : (
              <User className="w-4 h-4" />
            )}
          </div>
          <div className="min-w-0">
            <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500">
              {node.type} Node
            </span>
            <h3 className="text-sm font-bold text-slate-900 truncate">
              {node.label}
            </h3>
          </div>
        </div>

        <button
          type="button"
          onClick={onClose}
          className="p-1.5 rounded-lg text-slate-400 hover:text-slate-700 hover:bg-slate-100 transition-colors cursor-pointer"
          title="Close details"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      {/* Drawer Body */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4 text-xs text-slate-700">
        {/* Entity ID & Status Chip */}
        <div className="flex items-center justify-between bg-slate-50 p-2.5 rounded-xl border border-slate-200/80">
          <div>
            <span className="text-[10px] text-slate-500 font-medium">Node ID</span>
            <p className="font-mono text-slate-800 text-[11px] font-semibold">
              {node.id}
            </p>
          </div>
          <span className="px-2 py-0.5 rounded-full text-[11px] font-semibold capitalize bg-white border border-slate-200 text-slate-800">
            {node.status}
          </span>
        </div>

        {/* DEVICE DETAILS */}
        {node.type === "device" && (
          <div className="space-y-3">
            <div>
              <h4 className="text-[11px] font-bold text-slate-900 uppercase tracking-wider mb-2">
                Hardware &amp; Platform
              </h4>
              <div className="grid grid-cols-2 gap-2">
                <div className="p-2 rounded-lg bg-slate-50 border border-slate-100">
                  <span className="text-[10px] text-slate-500">Platform</span>
                  <p className="font-semibold text-slate-800 capitalize">
                    {node.metadata.platform}
                  </p>
                </div>
                <div className="p-2 rounded-lg bg-slate-50 border border-slate-100">
                  <span className="text-[10px] text-slate-500">OS Version</span>
                  <p className="font-semibold text-slate-800 font-mono">
                    {node.metadata.os_version || "—"}
                  </p>
                </div>
                <div className="p-2 rounded-lg bg-slate-50 border border-slate-100">
                  <span className="text-[10px] text-slate-500">Device Type</span>
                  <p className="font-semibold text-slate-800 capitalize">
                    {node.metadata.device_type}
                  </p>
                </div>
                <div className="p-2 rounded-lg bg-slate-50 border border-slate-100">
                  <span className="text-[10px] text-slate-500">Hosted Runtimes</span>
                  <p className="font-semibold text-indigo-700 font-mono">
                    {node.metadata.runtime_count}
                  </p>
                </div>
              </div>
            </div>

            {/* Hosted Runtimes List */}
            <div>
              <h4 className="text-[11px] font-bold text-slate-900 uppercase tracking-wider mb-2">
                Linked Runtimes ({hostedRuntimes.length})
              </h4>
              {hostedRuntimes.length === 0 ? (
                <p className="text-slate-400 italic">No runtimes hosted by this device.</p>
              ) : (
                <div className="space-y-1.5">
                  {hostedRuntimes.map((rt) => (
                    <button
                      key={rt.id}
                      type="button"
                      onClick={() => onSelectNode(rt.id)}
                      className="w-full text-left p-2 rounded-lg border border-slate-200 bg-white hover:bg-sky-50/50 hover:border-sky-300 transition-colors flex items-center justify-between cursor-pointer"
                    >
                      <div className="flex items-center gap-2">
                        <Cpu className="w-3.5 h-3.5 text-sky-600" />
                        <span className="font-medium text-slate-800">{rt.label}</span>
                      </div>
                      <ArrowRight className="w-3.5 h-3.5 text-slate-400" />
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}

        {/* RUNTIME DETAILS */}
        {node.type === "runtime" && (
          <div className="space-y-3">
            <div>
              <h4 className="text-[11px] font-bold text-slate-900 uppercase tracking-wider mb-2">
                Execution Configuration
              </h4>
              <div className="grid grid-cols-2 gap-2">
                <div className="p-2 rounded-lg bg-slate-50 border border-slate-100">
                  <span className="text-[10px] text-slate-500">Runtime Type</span>
                  <p className="font-semibold text-slate-800 uppercase font-mono">
                    {node.metadata.runtime_type}
                  </p>
                </div>
                <div className="p-2 rounded-lg bg-slate-50 border border-slate-100">
                  <span className="text-[10px] text-slate-500">Assigned Accounts</span>
                  <p className="font-semibold text-sky-700 font-mono">
                    {node.metadata.assigned_account_count}
                  </p>
                </div>
                <div className="col-span-2 p-2 rounded-lg bg-slate-50 border border-slate-100">
                  <span className="text-[10px] text-slate-500">Last Seen</span>
                  <p className="font-mono text-slate-800">
                    {node.metadata.last_seen_at
                      ? new Date(node.metadata.last_seen_at).toLocaleString()
                      : "Never"}
                  </p>
                </div>
              </div>
            </div>

            {/* Host Device */}
            {hostDevice && (
              <div>
                <h4 className="text-[11px] font-bold text-slate-900 uppercase tracking-wider mb-1.5">
                  Host Device
                </h4>
                <button
                  type="button"
                  onClick={() => onSelectNode(hostDevice.id)}
                  className="w-full text-left p-2 rounded-lg border border-indigo-200 bg-indigo-50/40 hover:bg-indigo-50 transition-colors flex items-center justify-between cursor-pointer"
                >
                  <div className="flex items-center gap-2">
                    <Smartphone className="w-3.5 h-3.5 text-indigo-600" />
                    <span className="font-semibold text-indigo-900">{hostDevice.label}</span>
                  </div>
                  <ArrowRight className="w-3.5 h-3.5 text-indigo-400" />
                </button>
              </div>
            )}

            {/* Assigned Accounts List */}
            <div>
              <h4 className="text-[11px] font-bold text-slate-900 uppercase tracking-wider mb-2">
                Assigned Accounts ({assignedAccounts.length})
              </h4>
              {assignedAccounts.length === 0 ? (
                <p className="text-slate-400 italic">No accounts currently assigned to this runtime.</p>
              ) : (
                <div className="space-y-1.5">
                  {assignedAccounts.map((acc) => (
                    <button
                      key={acc.id}
                      type="button"
                      onClick={() => onSelectNode(acc.id)}
                      className="w-full text-left p-2 rounded-lg border border-slate-200 bg-white hover:bg-rose-50/50 hover:border-rose-300 transition-colors flex items-center justify-between cursor-pointer"
                    >
                      <div className="flex items-center gap-2">
                        <User className="w-3.5 h-3.5 text-rose-600" />
                        <span className="font-medium text-slate-800">{acc.label}</span>
                      </div>
                      <ArrowRight className="w-3.5 h-3.5 text-slate-400" />
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}

        {/* ACCOUNT DETAILS */}
        {node.type === "account" && (
          <div className="space-y-3">
            <div>
              <h4 className="text-[11px] font-bold text-slate-900 uppercase tracking-wider mb-2">
                Identity &amp; Governance
              </h4>
              <div className="space-y-2">
                <div className="p-2 rounded-lg bg-slate-50 border border-slate-100 flex items-center justify-between">
                  <span className="text-[10px] text-slate-500">TikTok Handle</span>
                  <span className="font-mono font-semibold text-slate-900">
                    {node.metadata.username ? `@${node.metadata.username}` : "None"}
                  </span>
                </div>
                <div className="p-2 rounded-lg bg-slate-50 border border-slate-100 flex items-center justify-between">
                  <span className="text-[10px] text-slate-500">Registration State</span>
                  <span className="font-semibold capitalize text-slate-800">
                    {node.metadata.registration_state}
                  </span>
                </div>
                <div className="p-2 rounded-lg bg-slate-50 border border-slate-100 flex items-center justify-between">
                  <span className="text-[10px] text-slate-500">Automation Readiness</span>
                  <span
                    className={`font-semibold ${
                      node.metadata.registration_ready
                        ? "text-emerald-700"
                        : "text-slate-500"
                    }`}
                  >
                    {node.metadata.registration_ready ? "Ready" : "Not ready"}
                  </span>
                </div>
                <div className="p-2 rounded-lg bg-slate-50 border border-slate-100 flex items-center justify-between">
                  <span className="text-[10px] text-slate-500">Health Status</span>
                  <span className="font-semibold capitalize text-slate-800">
                    {node.metadata.health_status}
                  </span>
                </div>
                <div className="p-2 rounded-lg bg-slate-50 border border-slate-100 flex items-center justify-between">
                  <span className="text-[10px] text-slate-500">Credentials Present</span>
                  <span
                    className={`font-semibold inline-flex items-center gap-1 ${
                      node.metadata.secret_present
                        ? "text-emerald-700"
                        : "text-slate-500"
                    }`}
                  >
                    {node.metadata.secret_present ? (
                      <>
                        <KeyRound className="w-3 h-3 text-emerald-600" />
                        <span>Configured</span>
                      </>
                    ) : (
                      <span>None</span>
                    )}
                  </span>
                </div>
                {node.metadata.registration_completed_at && (
                  <div className="p-2 rounded-lg bg-slate-50 border border-slate-100 flex items-center justify-between">
                    <span className="text-[10px] text-slate-500">Registration Completed</span>
                    <span className="font-mono text-[10px] text-slate-600">
                      {new Date(node.metadata.registration_completed_at).toLocaleDateString()}
                    </span>
                  </div>
                )}
              </div>
            </div>

            {/* Runtime & Device Links */}
            <div>
              <h4 className="text-[11px] font-bold text-slate-900 uppercase tracking-wider mb-2">
                Execution Binding
              </h4>
              {assignedRuntime ? (
                <div className="space-y-1.5">
                  <button
                    type="button"
                    onClick={() => onSelectNode(assignedRuntime.id)}
                    className="w-full text-left p-2 rounded-lg border border-sky-200 bg-sky-50/40 hover:bg-sky-50 transition-colors flex items-center justify-between cursor-pointer"
                  >
                    <div className="flex items-center gap-2">
                      <Cpu className="w-3.5 h-3.5 text-sky-600" />
                      <span className="font-semibold text-sky-900">{assignedRuntime.label}</span>
                    </div>
                    <ArrowRight className="w-3.5 h-3.5 text-sky-400" />
                  </button>

                  {hostDeviceForAccount && (
                    <button
                      type="button"
                      onClick={() => onSelectNode(hostDeviceForAccount.id)}
                      className="w-full text-left p-2 rounded-lg border border-slate-200 bg-white hover:bg-slate-50 transition-colors flex items-center justify-between cursor-pointer"
                    >
                      <div className="flex items-center gap-2">
                        <Smartphone className="w-3.5 h-3.5 text-slate-600" />
                        <span className="text-slate-700 font-medium">{hostDeviceForAccount.label}</span>
                      </div>
                      <ArrowRight className="w-3.5 h-3.5 text-slate-400" />
                    </button>
                  )}
                </div>
              ) : (
                <div className="p-3 bg-amber-50 border border-amber-200 rounded-xl text-amber-900 flex items-start gap-2">
                  <AlertCircle className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
                  <div>
                    <p className="font-semibold">Unassigned Account</p>
                    <p className="text-[11px] text-amber-800/80 mt-0.5">
                      Assign a Runtime on the Accounts page to enable dispatch.
                    </p>
                  </div>
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Drawer Footer Actions */}
      <div className="p-3 border-t border-slate-200/80 bg-slate-50/50">
        {node.type === "device" && (
          <Link
            href="/devices"
            className="w-full inline-flex items-center justify-center gap-1.5 py-2 px-3 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white font-semibold text-xs shadow-2xs transition-colors"
          >
            <span>Open Devices</span>
            <ExternalLink className="w-3.5 h-3.5" />
          </Link>
        )}
        {node.type === "runtime" && (
          <Link
            href="/runtimes"
            className="w-full inline-flex items-center justify-center gap-1.5 py-2 px-3 rounded-xl bg-sky-600 hover:bg-sky-700 text-white font-semibold text-xs shadow-2xs transition-colors"
          >
            <span>Open Runtimes</span>
            <ExternalLink className="w-3.5 h-3.5" />
          </Link>
        )}
        {node.type === "account" && (
          <Link
            href="/accounts"
            className="w-full inline-flex items-center justify-center gap-1.5 py-2 px-3 rounded-xl bg-rose-600 hover:bg-rose-700 text-white font-semibold text-xs shadow-2xs transition-colors"
          >
            <span>Open Accounts</span>
            <ExternalLink className="w-3.5 h-3.5" />
          </Link>
        )}
      </div>
    </div>
  );
}

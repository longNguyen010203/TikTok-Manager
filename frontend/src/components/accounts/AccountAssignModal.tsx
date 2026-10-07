"use client";

import React, { useState } from "react";
import {
  X,
  Loader2,
  Link2,
  AlertCircle,
  Cpu,
  ArrowRight,
  Users,
  Smartphone,
  Unlink,
} from "lucide-react";
import { Account, formatApiError } from "@/types/account";
import { Runtime } from "@/types/runtime";
import { Device } from "@/types/device";

interface AccountAssignModalProps {
  account: Account | null;
  runtimes: Runtime[];
  devicesMap: Record<number, Device>;
  isOpen: boolean;
  onClose: () => void;
  onAssignRuntime: (accountId: number, runtimeId: number) => Promise<void>;
  onUnassignRuntime: (accountId: number) => Promise<void>;
}

interface AccountAssignModalContentProps {
  account: Account;
  runtimes: Runtime[];
  devicesMap: Record<number, Device>;
  onClose: () => void;
  onAssignRuntime: (accountId: number, runtimeId: number) => Promise<void>;
  onUnassignRuntime: (accountId: number) => Promise<void>;
}

function AccountAssignModalContent({
  account,
  runtimes,
  devicesMap,
  onClose,
  onAssignRuntime,
  onUnassignRuntime,
}: AccountAssignModalContentProps) {
  const [selectedRuntimeId, setSelectedRuntimeId] = useState<string>(
    account.runtime_id !== null ? String(account.runtime_id) : ""
  );
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const currentRuntime =
    account.runtime_id !== null
      ? runtimes.find((r) => r.id === account.runtime_id)
      : null;
  const currentDevice =
    currentRuntime && currentRuntime.device_id
      ? devicesMap[currentRuntime.device_id]
      : null;

  const targetRuntime = selectedRuntimeId
    ? runtimes.find((r) => r.id === parseInt(selectedRuntimeId, 10))
    : null;
  const targetDevice =
    targetRuntime && targetRuntime.device_id
      ? devicesMap[targetRuntime.device_id]
      : null;

  const handleAssign = async () => {
    if (!selectedRuntimeId) {
      setFormError("Please select a valid execution Runtime.");
      return;
    }

    setFormError(null);
    try {
      setIsSubmitting(true);
      await onAssignRuntime(account.id, parseInt(selectedRuntimeId, 10));
      onClose();
    } catch (err: unknown) {
      setFormError(formatApiError(err));
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleUnassign = async () => {
    setFormError(null);
    try {
      setIsSubmitting(true);
      await onUnassignRuntime(account.id);
      onClose();
    } catch (err: unknown) {
      setFormError(formatApiError(err));
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-xs">
      <div
        className="bg-white rounded-2xl shadow-xl border border-slate-200 w-full max-w-lg overflow-hidden transition-all animate-in fade-in zoom-in-95 duration-150"
        role="dialog"
        aria-modal="true"
        aria-labelledby="assign-modal-title"
      >
        {/* Header */}
        <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="p-1.5 rounded-lg bg-cyan-50 text-cyan-600">
              <Link2 className="w-4 h-4" />
            </div>
            <div>
              <h3
                id="assign-modal-title"
                className="text-sm font-semibold text-slate-900"
              >
                Runtime &amp; Device Assignment
              </h3>
              <p className="text-[11px] text-slate-400 font-mono">
                @{account.username || "no-handle"} ({account.display_name || account.name})
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            disabled={isSubmitting}
            className="p-1 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition-colors disabled:opacity-50"
            aria-label="Close modal"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="p-6 space-y-4 text-xs">
          {formError && (
            <div className="p-3 rounded-lg bg-rose-50 border border-rose-200 text-rose-700 leading-relaxed break-words flex items-start gap-2">
              <AlertCircle className="w-4 h-4 text-rose-600 shrink-0 mt-0.5" />
              <span>{formError}</span>
            </div>
          )}

          {/* Breadcrumb Hierarchy Display */}
          <div className="space-y-1.5">
            <p className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider">
              Authoritative Hierarchy
            </p>
            <div className="flex items-center gap-2 p-3 bg-slate-50 border border-slate-200 rounded-xl flex-wrap">
              <div className="flex items-center gap-1.5 font-semibold text-slate-800">
                <Users className="w-3.5 h-3.5 text-rose-600" />
                <span className="font-mono">
                  {account.username ? `@${account.username}` : account.display_name}
                </span>
              </div>
              <ArrowRight className="w-3.5 h-3.5 text-slate-400 shrink-0" />
              <div className="flex items-center gap-1.5 font-medium text-slate-700">
                <Cpu className="w-3.5 h-3.5 text-cyan-600" />
                <span>
                  {currentRuntime
                    ? `${currentRuntime.name} (#${currentRuntime.id})`
                    : "No Runtime"}
                </span>
              </div>
              <ArrowRight className="w-3.5 h-3.5 text-slate-400 shrink-0" />
              <div className="flex items-center gap-1.5 text-slate-600">
                <Smartphone className="w-3.5 h-3.5 text-indigo-600" />
                <span className="text-[11px]">
                  {currentDevice
                    ? `${currentDevice.name} (#${currentDevice.id})`
                    : currentRuntime?.device_id
                    ? `Device #${currentRuntime.device_id}`
                    : "Derived Device None"}
                </span>
              </div>
            </div>
          </div>

          {/* Target Runtime Selector */}
          <div className="space-y-1.5 pt-1">
            <label
              htmlFor="assignRuntimeSelect"
              className="block font-medium text-slate-700"
            >
              Target Execution Runtime
            </label>
            <select
              id="assignRuntimeSelect"
              value={selectedRuntimeId}
              onChange={(e) => setSelectedRuntimeId(e.target.value)}
              className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3 py-2 text-slate-800 focus:outline-none focus:ring-2 focus:ring-cyan-500 font-medium"
            >
              <option value="">Select Runtime...</option>
              {runtimes.map((rt) => {
                const dev = devicesMap[rt.device_id];
                const devLabel = dev ? dev.name : `Device #${rt.device_id}`;
                return (
                  <option key={rt.id} value={rt.id}>
                    {rt.name} — Runtime #{rt.id} ({devLabel} • {rt.status})
                  </option>
                );
              })}
            </select>
            {targetDevice && (
              <p className="text-[11px] text-slate-500 pt-0.5">
                Target device derived from selected runtime:{" "}
                <strong className="text-slate-700">{targetDevice.name}</strong>{" "}
                ({targetDevice.platform} • {targetDevice.status})
              </p>
            )}
          </div>

          {/* Action Buttons */}
          <div className="pt-3 flex items-center justify-between gap-2 border-t border-slate-100">
            {account.runtime_id !== null ? (
              <button
                type="button"
                onClick={handleUnassign}
                disabled={isSubmitting}
                className="inline-flex items-center gap-1 px-3 py-2 text-rose-600 hover:bg-rose-50 rounded-lg font-medium transition-colors disabled:opacity-50"
              >
                <Unlink className="w-3.5 h-3.5" />
                <span>Unassign Runtime</span>
              </button>
            ) : (
              <div />
            )}

            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={onClose}
                disabled={isSubmitting}
                className="px-3.5 py-2 border border-slate-200 rounded-lg text-slate-600 hover:bg-slate-50 font-medium transition-colors disabled:opacity-50"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleAssign}
                disabled={isSubmitting || !selectedRuntimeId}
                className="inline-flex items-center gap-1.5 px-4 py-2 bg-cyan-600 text-white rounded-lg font-medium hover:bg-cyan-700 transition-colors shadow-2xs disabled:opacity-50"
              >
                {isSubmitting && (
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                )}
                <span>
                  {account.runtime_id !== null ? "Change Assignment" : "Assign Runtime"}
                </span>
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export function AccountAssignModal({
  account,
  runtimes = [],
  devicesMap = {},
  isOpen,
  onClose,
  onAssignRuntime,
  onUnassignRuntime,
}: AccountAssignModalProps) {
  if (!isOpen || !account) return null;

  return (
    <AccountAssignModalContent
      key={account.id}
      account={account}
      runtimes={runtimes}
      devicesMap={devicesMap}
      onClose={onClose}
      onAssignRuntime={onAssignRuntime}
      onUnassignRuntime={onUnassignRuntime}
    />
  );
}

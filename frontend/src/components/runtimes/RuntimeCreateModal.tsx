"use client";

import React, { useState } from "react";
import Link from "next/link";
import { X, Loader2, Cpu, AlertCircle } from "lucide-react";
import { CreateRuntimeInput, formatApiError } from "@/types/runtime";
import { Device } from "@/types/device";

interface RuntimeCreateModalProps {
  isOpen: boolean;
  devices: Device[];
  isLoadingDevices: boolean;
  onClose: () => void;
  onSubmit: (input: CreateRuntimeInput) => Promise<void>;
}

export function RuntimeCreateModal({
  isOpen,
  devices,
  isLoadingDevices,
  onClose,
  onSubmit,
}: RuntimeCreateModalProps) {
  const [name, setName] = useState("");
  const [deviceId, setDeviceId] = useState<string>(
    devices.length > 0 ? String(devices[0].id) : ""
  );
  const [runtimeType, setRuntimeType] = useState("emulator");
  const [status, setStatus] = useState("running");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormError(null);

    const trimmedName = name.trim();
    const parsedDeviceId = parseInt(deviceId, 10);

    if (!trimmedName) {
      setFormError("Runtime name is required.");
      return;
    }

    if (isNaN(parsedDeviceId) || parsedDeviceId <= 0) {
      setFormError("A valid host device must be selected.");
      return;
    }

    try {
      setIsSubmitting(true);
      await onSubmit({
        name: trimmedName,
        device_id: parsedDeviceId,
        runtime_type: runtimeType.trim(),
        status: status.trim(),
        last_seen_at: null,
      });

      // Reset form on success
      setName("");
      setDeviceId(devices.length > 0 ? String(devices[0].id) : "");
      setRuntimeType("emulator");
      setStatus("running");
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
        className="bg-white rounded-2xl shadow-xl border border-slate-200 w-full max-w-md overflow-hidden transition-all animate-in fade-in zoom-in-95 duration-150"
        role="dialog"
        aria-modal="true"
        aria-labelledby="runtime-create-title"
      >
        {/* Header */}
        <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="p-1.5 rounded-lg bg-cyan-50 text-cyan-600">
              <Cpu className="w-4 h-4" />
            </div>
            <h3
              id="runtime-create-title"
              className="text-sm font-semibold text-slate-900"
            >
              Provision New Runtime
            </h3>
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

        {/* Form */}
        <form onSubmit={handleSubmit} className="p-6 space-y-4 text-xs">
          {formError && (
            <div className="p-3 rounded-lg bg-rose-50 border border-rose-200 text-rose-700 leading-relaxed break-words">
              {formError}
            </div>
          )}

          {/* Host Device Warning if none exist */}
          {!isLoadingDevices && devices.length === 0 && (
            <div className="p-3 rounded-lg bg-amber-50 border border-amber-200 text-amber-800 flex items-start gap-2">
              <AlertCircle className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
              <div>
                <p className="font-semibold">No devices found</p>
                <p className="mt-0.5">
                  You must add a device first.{" "}
                  <Link href="/devices" className="underline font-semibold text-amber-900">
                    Go to Device Management &rarr;
                  </Link>
                </p>
              </div>
            </div>
          )}

          {/* Runtime Name */}
          <div className="space-y-1">
            <label
              htmlFor="rtName"
              className="block font-medium text-slate-700"
            >
              Runtime Name <span className="text-rose-500">*</span>
            </label>
            <input
              id="rtName"
              type="text"
              required
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. TikTok Runner #1"
              className="w-full bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 text-slate-800 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-cyan-500/20 focus:border-cyan-500"
            />
          </div>

          {/* Host Device Selector */}
          <div className="space-y-1">
            <label
              htmlFor="rtDevice"
              className="block font-medium text-slate-700"
            >
              Host Device <span className="text-rose-500">*</span>
            </label>
            <select
              id="rtDevice"
              required
              disabled={isLoadingDevices || devices.length === 0}
              value={deviceId}
              onChange={(e) => setDeviceId(e.target.value)}
              className="w-full bg-slate-50 border border-slate-200 rounded-lg px-2.5 py-2 text-slate-800 focus:outline-none focus:ring-2 focus:ring-cyan-500/20 focus:border-cyan-500 disabled:opacity-50"
            >
              {isLoadingDevices ? (
                <option value="">Loading devices from server...</option>
              ) : devices.length === 0 ? (
                <option value="">No devices available</option>
              ) : (
                <>
                  <option value="">Select a host device...</option>
                  {devices.map((d) => (
                    <option key={d.id} value={d.id}>
                      {d.name} ({d.platform} • {d.device_type} • ID #{d.id})
                    </option>
                  ))}
                </>
              )}
            </select>
            <p className="text-[11px] text-slate-400">
              Loaded dynamically from registered devices.
            </p>
          </div>

          {/* Runtime Type & Initial Status */}
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <label
                htmlFor="rtType"
                className="block font-medium text-slate-700"
              >
                Runtime Type <span className="text-rose-500">*</span>
              </label>
              <select
                id="rtType"
                value={runtimeType}
                onChange={(e) => setRuntimeType(e.target.value)}
                className="w-full bg-slate-50 border border-slate-200 rounded-lg px-2.5 py-2 text-slate-800 focus:outline-none focus:ring-2 focus:ring-cyan-500/20 focus:border-cyan-500"
              >
                <option value="emulator">Emulator</option>
                <option value="container">Container</option>
                <option value="cloud">Cloud Instance</option>
              </select>
            </div>

            <div className="space-y-1">
              <label
                htmlFor="rtStatus"
                className="block font-medium text-slate-700"
              >
                Initial Status <span className="text-rose-500">*</span>
              </label>
              <select
                id="rtStatus"
                value={status}
                onChange={(e) => setStatus(e.target.value)}
                className="w-full bg-slate-50 border border-slate-200 rounded-lg px-2.5 py-2 text-slate-800 focus:outline-none focus:ring-2 focus:ring-cyan-500/20 focus:border-cyan-500"
              >
                <option value="running">Running</option>
                <option value="idle">Idle</option>
                <option value="stopped">Stopped</option>
                <option value="error">Error</option>
              </select>
            </div>
          </div>

          {/* Actions */}
          <div className="pt-2 flex items-center justify-end gap-2">
            <button
              type="button"
              onClick={onClose}
              disabled={isSubmitting}
              className="px-4 py-2 border border-slate-200 rounded-lg text-slate-600 hover:bg-slate-50 font-medium transition-colors disabled:opacity-50"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isSubmitting || devices.length === 0}
              className="inline-flex items-center gap-1.5 px-4 py-2 bg-rose-600 text-white rounded-lg font-medium hover:bg-rose-700 transition-colors shadow-2xs disabled:opacity-70"
            >
              {isSubmitting && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
              <span>Save Runtime</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

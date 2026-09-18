"use client";

import React, { useState } from "react";
import { X, Loader2, Edit3, AlertCircle } from "lucide-react";
import { Runtime, UpdateRuntimeInput, formatApiError } from "@/types/runtime";
import { Device } from "@/types/device";

interface RuntimeEditModalProps {
  runtime: Runtime | null;
  devices: Device[];
  isLoadingDevices: boolean;
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (id: number, input: UpdateRuntimeInput) => Promise<void>;
}

interface RuntimeEditModalContentProps {
  runtime: Runtime;
  devices: Device[];
  isLoadingDevices: boolean;
  onClose: () => void;
  onSubmit: (id: number, input: UpdateRuntimeInput) => Promise<void>;
}

function RuntimeEditModalContent({
  runtime,
  devices,
  isLoadingDevices,
  onClose,
  onSubmit,
}: RuntimeEditModalContentProps) {
  const [name, setName] = useState(runtime.name);
  const [deviceId, setDeviceId] = useState<string>(String(runtime.device_id));
  const [runtimeType, setRuntimeType] = useState(runtime.runtime_type);
  const [status, setStatus] = useState(runtime.status);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const isCurrentDeviceMissing =
    !isLoadingDevices &&
    devices.length > 0 &&
    !devices.some((d) => d.id === runtime.device_id);

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
      await onSubmit(runtime.id, {
        name: trimmedName,
        device_id: parsedDeviceId,
        runtime_type: runtimeType.trim(),
        status: status.trim(),
      });
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
        aria-labelledby="runtime-edit-title"
      >
        {/* Header */}
        <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="p-1.5 rounded-lg bg-indigo-50 text-indigo-600">
              <Edit3 className="w-4 h-4" />
            </div>
            <div>
              <h3
                id="runtime-edit-title"
                className="text-sm font-semibold text-slate-900"
              >
                Edit Runtime Configuration
              </h3>
              <p className="text-[11px] text-slate-400 font-mono">
                ID #{runtime.id} • {runtime.name}
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

        {/* Form */}
        <form onSubmit={handleSubmit} className="p-6 space-y-4 text-xs">
          {formError && (
            <div className="p-3 rounded-lg bg-rose-50 border border-rose-200 text-rose-700 leading-relaxed break-words">
              {formError}
            </div>
          )}

          {/* Host Device Missing Alert */}
          {isCurrentDeviceMissing && (
            <div className="p-3 rounded-lg bg-amber-50 border border-amber-200 text-amber-800 flex items-start gap-2">
              <AlertCircle className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
              <div>
                <p className="font-semibold">Host Device Missing</p>
                <p className="mt-0.5 text-[11px]">
                  The previously configured host device (ID #{runtime.device_id}) was deleted or cannot be found. Please select an active host device below.
                </p>
              </div>
            </div>
          )}

          {/* Runtime Name */}
          <div className="space-y-1">
            <label
              htmlFor="editRtName"
              className="block font-medium text-slate-700"
            >
              Runtime Name <span className="text-rose-500">*</span>
            </label>
            <input
              id="editRtName"
              type="text"
              required
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 text-slate-800 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500"
            />
          </div>

          {/* Host Device Selector */}
          <div className="space-y-1">
            <label
              htmlFor="editRtDevice"
              className="block font-medium text-slate-700"
            >
              Host Device <span className="text-rose-500">*</span>
            </label>
            <select
              id="editRtDevice"
              required
              disabled={isLoadingDevices || devices.length === 0}
              value={deviceId}
              onChange={(e) => setDeviceId(e.target.value)}
              className="w-full bg-slate-50 border border-slate-200 rounded-lg px-2.5 py-2 text-slate-800 focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 disabled:opacity-50"
            >
              {isLoadingDevices ? (
                <option value="">Loading devices...</option>
              ) : (
                <>
                  <option value="">Select a host device...</option>
                  {isCurrentDeviceMissing && (
                    <option value={runtime.device_id} disabled>
                      Device #{runtime.device_id} (Missing / Deleted)
                    </option>
                  )}
                  {devices.map((d) => (
                    <option key={d.id} value={d.id}>
                      {d.name} ({d.platform} • {d.device_type} • ID #{d.id})
                    </option>
                  ))}
                </>
              )}
            </select>
          </div>

          {/* Runtime Type & Status */}
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <label
                htmlFor="editRtType"
                className="block font-medium text-slate-700"
              >
                Runtime Type <span className="text-rose-500">*</span>
              </label>
              <select
                id="editRtType"
                value={runtimeType}
                onChange={(e) => setRuntimeType(e.target.value)}
                className="w-full bg-slate-50 border border-slate-200 rounded-lg px-2.5 py-2 text-slate-800 focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500"
              >
                <option value="emulator">Emulator</option>
                <option value="container">Container</option>
                <option value="cloud">Cloud Instance</option>
              </select>
            </div>

            <div className="space-y-1">
              <label
                htmlFor="editRtStatus"
                className="block font-medium text-slate-700"
              >
                Status <span className="text-rose-500">*</span>
              </label>
              <select
                id="editRtStatus"
                value={status}
                onChange={(e) => setStatus(e.target.value)}
                className="w-full bg-slate-50 border border-slate-200 rounded-lg px-2.5 py-2 text-slate-800 focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500"
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
              disabled={isSubmitting}
              className="inline-flex items-center gap-1.5 px-4 py-2 bg-indigo-600 text-white rounded-lg font-medium hover:bg-indigo-700 transition-colors shadow-2xs disabled:opacity-70"
            >
              {isSubmitting && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
              <span>Update Runtime</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export function RuntimeEditModal({
  runtime,
  devices,
  isLoadingDevices,
  isOpen,
  onClose,
  onSubmit,
}: RuntimeEditModalProps) {
  if (!isOpen || !runtime) return null;

  return (
    <RuntimeEditModalContent
      key={runtime.id}
      runtime={runtime}
      devices={devices}
      isLoadingDevices={isLoadingDevices}
      onClose={onClose}
      onSubmit={onSubmit}
    />
  );
}

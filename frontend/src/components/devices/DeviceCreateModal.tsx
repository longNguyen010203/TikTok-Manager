"use client";

import React, { useState } from "react";
import { X, Loader2, Smartphone } from "lucide-react";
import { CreateDeviceInput, formatApiError } from "@/types/device";

interface DeviceCreateModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (input: CreateDeviceInput) => Promise<void>;
}

export function DeviceCreateModal({
  isOpen,
  onClose,
  onSubmit,
}: DeviceCreateModalProps) {
  const [name, setName] = useState("");
  const [deviceType, setDeviceType] = useState("emulator");
  const [platform, setPlatform] = useState("android");
  const [osVersion, setOsVersion] = useState("15");
  const [status, setStatus] = useState("online");
  const [notes, setNotes] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormError(null);

    const trimmedName = name.trim();
    const trimmedOsVersion = osVersion.trim();

    if (!trimmedName) {
      setFormError("Device name is required.");
      return;
    }

    if (!trimmedOsVersion) {
      setFormError("OS version is required.");
      return;
    }

    try {
      setIsSubmitting(true);
      await onSubmit({
        name: trimmedName,
        device_type: deviceType.trim(),
        platform: platform.trim(),
        os_version: trimmedOsVersion,
        status: status.trim(),
        notes: notes.trim() || null,
      });

      // Reset form on success
      setName("");
      setDeviceType("emulator");
      setPlatform("android");
      setOsVersion("15");
      setStatus("online");
      setNotes("");
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
        aria-labelledby="device-create-title"
      >
        {/* Header */}
        <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="p-1.5 rounded-lg bg-rose-50 text-rose-600">
              <Smartphone className="w-4 h-4" />
            </div>
            <h3
              id="device-create-title"
              className="text-sm font-semibold text-slate-900"
            >
              Add New Device
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

          {/* Device Name */}
          <div className="space-y-1">
            <label
              htmlFor="devName"
              className="block font-medium text-slate-700"
            >
              Device Name <span className="text-rose-500">*</span>
            </label>
            <input
              id="devName"
              type="text"
              required
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Pixel 8 Emulator #1"
              className="w-full bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 text-slate-800 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-rose-500/20 focus:border-rose-500"
            />
          </div>

          {/* Device Type & Platform */}
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <label
                htmlFor="devType"
                className="block font-medium text-slate-700"
              >
                Device Type <span className="text-rose-500">*</span>
              </label>
              <select
                id="devType"
                value={deviceType}
                onChange={(e) => setDeviceType(e.target.value)}
                className="w-full bg-slate-50 border border-slate-200 rounded-lg px-2.5 py-2 text-slate-800 focus:outline-none focus:ring-2 focus:ring-rose-500/20 focus:border-rose-500"
              >
                <option value="emulator">Emulator</option>
                <option value="physical">Physical</option>
                <option value="cloud">Cloud Instance</option>
              </select>
            </div>

            <div className="space-y-1">
              <label
                htmlFor="devPlatform"
                className="block font-medium text-slate-700"
              >
                Platform <span className="text-rose-500">*</span>
              </label>
              <select
                id="devPlatform"
                value={platform}
                onChange={(e) => setPlatform(e.target.value)}
                className="w-full bg-slate-50 border border-slate-200 rounded-lg px-2.5 py-2 text-slate-800 focus:outline-none focus:ring-2 focus:ring-rose-500/20 focus:border-rose-500"
              >
                <option value="android">Android</option>
                <option value="ios">iOS</option>
              </select>
            </div>
          </div>

          {/* OS Version & Initial Status */}
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <label
                htmlFor="devOsVersion"
                className="block font-medium text-slate-700"
              >
                OS Version <span className="text-rose-500">*</span>
              </label>
              <input
                id="devOsVersion"
                type="text"
                required
                value={osVersion}
                onChange={(e) => setOsVersion(e.target.value)}
                placeholder="e.g. 15, 14.0"
                className="w-full bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 text-slate-800 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-rose-500/20 focus:border-rose-500"
              />
            </div>

            <div className="space-y-1">
              <label
                htmlFor="devStatus"
                className="block font-medium text-slate-700"
              >
                Status <span className="text-rose-500">*</span>
              </label>
              <select
                id="devStatus"
                value={status}
                onChange={(e) => setStatus(e.target.value)}
                className="w-full bg-slate-50 border border-slate-200 rounded-lg px-2.5 py-2 text-slate-800 focus:outline-none focus:ring-2 focus:ring-rose-500/20 focus:border-rose-500"
              >
                <option value="online">Online</option>
                <option value="offline">Offline</option>
                <option value="busy">Busy</option>
                <option value="error">Error</option>
              </select>
            </div>
          </div>

          {/* Notes */}
          <div className="space-y-1">
            <label
              htmlFor="devNotes"
              className="block font-medium text-slate-700"
            >
              Notes (Optional)
            </label>
            <textarea
              id="devNotes"
              rows={3}
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="e.g. Hardware specs, serial number, assigned automation profile..."
              className="w-full bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 text-slate-800 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-rose-500/20 focus:border-rose-500 resize-none"
            />
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
              className="inline-flex items-center gap-1.5 px-4 py-2 bg-rose-600 text-white rounded-lg font-medium hover:bg-rose-700 transition-colors shadow-2xs disabled:opacity-70"
            >
              {isSubmitting && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
              <span>Save Device</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

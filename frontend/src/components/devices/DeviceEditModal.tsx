"use client";

import React, { useState } from "react";
import { X, Loader2, Edit3 } from "lucide-react";
import { Device, UpdateDeviceInput, formatApiError } from "@/types/device";

interface DeviceEditModalProps {
  device: Device | null;
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (id: number, input: UpdateDeviceInput) => Promise<void>;
}

interface DeviceEditModalContentProps {
  device: Device;
  onClose: () => void;
  onSubmit: (id: number, input: UpdateDeviceInput) => Promise<void>;
}

function DeviceEditModalContent({
  device,
  onClose,
  onSubmit,
}: DeviceEditModalContentProps) {
  const [name, setName] = useState(device.name);
  const [deviceType, setDeviceType] = useState(device.device_type);
  const [platform, setPlatform] = useState(device.platform);
  const [osVersion, setOsVersion] = useState(device.os_version);
  const [status, setStatus] = useState(device.status);
  const [notes, setNotes] = useState(device.notes || "");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

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
      await onSubmit(device.id, {
        name: trimmedName,
        device_type: deviceType.trim(),
        platform: platform.trim(),
        os_version: trimmedOsVersion,
        status: status.trim(),
        notes: notes.trim() || null,
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
        aria-labelledby="device-edit-title"
      >
        {/* Header */}
        <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="p-1.5 rounded-lg bg-indigo-50 text-indigo-600">
              <Edit3 className="w-4 h-4" />
            </div>
            <div>
              <h3
                id="device-edit-title"
                className="text-sm font-semibold text-slate-900"
              >
                Edit Device Details
              </h3>
              <p className="text-[11px] text-slate-400 font-mono">
                ID #{device.id} • {device.name}
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            disabled={isSubmitting}
            className="p-1 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition-colors disabled:opacity-50"
            aria-label="Close edit modal"
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
              htmlFor="editDevName"
              className="block font-medium text-slate-700"
            >
              Device Name <span className="text-rose-500">*</span>
            </label>
            <input
              id="editDevName"
              type="text"
              required
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 text-slate-800 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500"
            />
          </div>

          {/* Device Type & Platform */}
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <label
                htmlFor="editDevType"
                className="block font-medium text-slate-700"
              >
                Device Type <span className="text-rose-500">*</span>
              </label>
              <select
                id="editDevType"
                value={deviceType}
                onChange={(e) => setDeviceType(e.target.value)}
                className="w-full bg-slate-50 border border-slate-200 rounded-lg px-2.5 py-2 text-slate-800 focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500"
              >
                <option value="emulator">Emulator</option>
                <option value="physical">Physical</option>
                <option value="cloud">Cloud Instance</option>
              </select>
            </div>

            <div className="space-y-1">
              <label
                htmlFor="editDevPlatform"
                className="block font-medium text-slate-700"
              >
                Platform <span className="text-rose-500">*</span>
              </label>
              <select
                id="editDevPlatform"
                value={platform}
                onChange={(e) => setPlatform(e.target.value)}
                className="w-full bg-slate-50 border border-slate-200 rounded-lg px-2.5 py-2 text-slate-800 focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500"
              >
                <option value="android">Android</option>
                <option value="ios">iOS</option>
              </select>
            </div>
          </div>

          {/* OS Version & Status */}
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <label
                htmlFor="editDevOsVersion"
                className="block font-medium text-slate-700"
              >
                OS Version <span className="text-rose-500">*</span>
              </label>
              <input
                id="editDevOsVersion"
                type="text"
                required
                value={osVersion}
                onChange={(e) => setOsVersion(e.target.value)}
                className="w-full bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 text-slate-800 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500"
              />
            </div>

            <div className="space-y-1">
              <label
                htmlFor="editDevStatus"
                className="block font-medium text-slate-700"
              >
                Status <span className="text-rose-500">*</span>
              </label>
              <select
                id="editDevStatus"
                value={status}
                onChange={(e) => setStatus(e.target.value)}
                className="w-full bg-slate-50 border border-slate-200 rounded-lg px-2.5 py-2 text-slate-800 focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500"
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
              htmlFor="editDevNotes"
              className="block font-medium text-slate-700"
            >
              Notes (Optional)
            </label>
            <textarea
              id="editDevNotes"
              rows={3}
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Hardware specs, location, automation configuration..."
              className="w-full bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 text-slate-800 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 resize-none"
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
              className="inline-flex items-center gap-1.5 px-4 py-2 bg-indigo-600 text-white rounded-lg font-medium hover:bg-indigo-700 transition-colors shadow-2xs disabled:opacity-70"
            >
              {isSubmitting && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
              <span>Update Device</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export function DeviceEditModal({
  device,
  isOpen,
  onClose,
  onSubmit,
}: DeviceEditModalProps) {
  if (!isOpen || !device) return null;

  return (
    <DeviceEditModalContent
      key={device.id}
      device={device}
      onClose={onClose}
      onSubmit={onSubmit}
    />
  );
}

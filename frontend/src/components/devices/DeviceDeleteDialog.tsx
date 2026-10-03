"use client";

import React, { useState } from "react";
import { Trash2, AlertTriangle, Loader2, ArrowRight } from "lucide-react";
import { Device, formatApiError } from "@/types/device";
import {
  provisioningRegistry,
  ManagedProvisioningRecord,
} from "@/services/provisioningRegistry";
import { provisioningService } from "@/services/provisioningService";

interface DeviceDeleteDialogProps {
  device: Device | null;
  isOpen: boolean;
  onClose: () => void;
  onConfirm: (id: number) => Promise<void>;
  onOpenDeprovision?: (
    device: Device,
    record?: ManagedProvisioningRecord | null
  ) => void;
}

export function DeviceDeleteDialog({
  device,
  isOpen,
  onClose,
  onConfirm,
  onOpenDeprovision,
}: DeviceDeleteDialogProps) {
  const [isDeleting, setIsDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [managedConflict, setManagedConflict] = useState<{
    provisioningId: string;
    record?: ManagedProvisioningRecord | null;
  } | null>(() => {
    if (!device) return null;
    const existing = provisioningRegistry.getByDeviceId(device.id);
    return existing
      ? { provisioningId: existing.provisioningId, record: existing }
      : null;
  });

  if (!isOpen || !device) return null;

  const handleDelete = async () => {
    setDeleteError(null);
    try {
      setIsDeleting(true);
      await onConfirm(device.id);
      onClose();
    } catch (err: unknown) {
      const msg = formatApiError(err);
      // Check if backend rejected because this is a provisioned managed device
      const provId = provisioningRegistry.extractProvisioningIdFromConflict(msg);
      if (provId) {
        // Fetch real provisioning status to populate registry
        try {
          const status = await provisioningService.getProvisioning(provId);
          const saved = provisioningRegistry.registerFromStatus(status, device.id);
          setManagedConflict({
            provisioningId: provId,
            record: saved,
          });
        } catch {
          setManagedConflict({
            provisioningId: provId,
          });
        }
      } else {
        setDeleteError(msg);
      }
    } finally {
      setIsDeleting(false);
    }
  };

  const handleSwitchToDeprovision = () => {
    onClose();
    if (onOpenDeprovision && device) {
      onOpenDeprovision(device, managedConflict?.record);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-xs">
      <div
        className="bg-white rounded-2xl shadow-xl border border-slate-200 w-full max-w-md p-6 space-y-4 animate-in fade-in zoom-in-95 duration-150"
        role="alertdialog"
        aria-modal="true"
        aria-labelledby="device-delete-title"
        aria-describedby="device-delete-desc"
      >
        <div className="flex items-start gap-3.5">
          <div className="p-2.5 rounded-full bg-rose-100 text-rose-600 shrink-0">
            <AlertTriangle className="w-5 h-5" />
          </div>
          <div className="space-y-1">
            <h3
              id="device-delete-title"
              className="text-sm font-semibold text-slate-900"
            >
              {managedConflict ? "Managed Device — Generic Delete Blocked" : "Delete Device Confirmation"}
            </h3>
            <p id="device-delete-desc" className="text-xs text-slate-500 leading-relaxed">
              {managedConflict ? (
                <>
                  Device <strong className="text-slate-900 font-semibold">{device.name}</strong> is managed by Redroid provisioning. Generic delete is blocked to avoid leaving orphaned containers and networks.
                </>
              ) : (
                <>
                  Are you sure you want to permanently delete device{" "}
                  <strong className="text-slate-900 font-semibold">
                    {device.name}
                  </strong>{" "}
                  (ID #{device.id}, {device.platform} {device.device_type})? Deleting
                  a device also deletes any associated Runtime records.
                </>
              )}
            </p>
          </div>
        </div>

        {/* Managed Device Deprovision Guidance Banner */}
        {managedConflict ? (
          <div className="p-4 rounded-xl bg-amber-50 border border-amber-200 text-amber-900 space-y-3 text-xs">
            <p className="leading-relaxed">
              Please use the dedicated <strong>Deprovision Device</strong> flow instead. Deprovisioning will cleanly stop and remove the container and bridge network while preserving your persistent /data directory on disk.
            </p>
            {managedConflict.provisioningId && (
              <div className="text-[11px] font-mono bg-white p-2 rounded border border-amber-200/80 text-slate-700 break-all">
                Provisioning ID: {managedConflict.provisioningId}
              </div>
            )}
            <button
              type="button"
              onClick={handleSwitchToDeprovision}
              className="w-full inline-flex items-center justify-center gap-1.5 px-4 py-2.5 bg-rose-600 text-white rounded-lg text-xs font-semibold hover:bg-rose-700 transition-colors shadow-2xs"
            >
              <span>Open Deprovision Flow</span>
              <ArrowRight className="w-4 h-4" />
            </button>
          </div>
        ) : null}

        {deleteError && (
          <div className="p-3 rounded-lg bg-rose-50 border border-rose-200 text-rose-700 text-xs break-words">
            {deleteError}
          </div>
        )}

        <div className="pt-2 flex items-center justify-end gap-2">
          <button
            type="button"
            onClick={onClose}
            disabled={isDeleting}
            className="px-3.5 py-2 border border-slate-200 rounded-lg text-slate-600 hover:bg-slate-50 text-xs font-medium transition-colors disabled:opacity-50"
          >
            Cancel
          </button>
          {!managedConflict && (
            <button
              type="button"
              onClick={handleDelete}
              disabled={isDeleting}
              className="inline-flex items-center gap-1.5 px-4 py-2 bg-rose-600 text-white rounded-lg text-xs font-medium hover:bg-rose-700 transition-colors shadow-2xs disabled:opacity-70"
            >
              {isDeleting ? (
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
              ) : (
                <Trash2 className="w-3.5 h-3.5" />
              )}
              <span>Delete Device</span>
            </button>
          )}
        </div>
      </div>
    </div>
  );
}


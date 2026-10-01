import React from "react";
import { Device, DeviceLifecycleStatus } from "@/types/device";
import { DeviceStatusBadge } from "./DeviceStatusBadge";
import { DeviceReadinessBadge } from "./DeviceReadinessBadge";
import { DeviceLoadingState } from "./DeviceLoadingState";
import { DeviceEmptyState } from "./DeviceEmptyState";
import { DeviceErrorState } from "./DeviceErrorState";
import { Smartphone, Calendar, Pencil, Trash2, Cpu, Layers, Activity } from "lucide-react";

interface DeviceTableProps {
  devices: Device[];
  isLoading: boolean;
  error: string | null;
  onRetry: () => void;
  isFiltered: boolean;
  onClearFilters: () => void;
  onCreateDevice: () => void;
  onEditDevice?: (device: Device) => void;
  onDeleteDevice?: (device: Device) => void;
  onViewStatus?: (device: Device) => void;
  lifecycleStatuses?: Record<number, DeviceLifecycleStatus>;
}

export function DeviceTable({
  devices,
  isLoading,
  error,
  onRetry,
  isFiltered,
  onClearFilters,
  onCreateDevice,
  onEditDevice,
  onDeleteDevice,
  onViewStatus,
  lifecycleStatuses,
}: DeviceTableProps) {
  // Format ISO date string
  const formatDate = (isoString: string) => {
    try {
      const date = new Date(isoString);
      if (isNaN(date.getTime())) return isoString;
      return new Intl.DateTimeFormat("en-US", {
        month: "short",
        day: "numeric",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit",
        hour12: false,
      }).format(date);
    } catch {
      return isoString;
    }
  };

  return (
    <div className="overflow-x-auto">
      {isLoading ? (
        <DeviceLoadingState rows={5} />
      ) : error ? (
        <DeviceErrorState message={error} onRetry={onRetry} />
      ) : devices.length === 0 ? (
        <DeviceEmptyState
          isFiltered={isFiltered}
          onClearFilters={onClearFilters}
          onCreateDevice={onCreateDevice}
        />
      ) : (
        <table className="w-full text-left text-xs border-collapse">
          <thead>
            <tr className="bg-slate-50/70 border-b border-slate-200/80 text-slate-500 uppercase tracking-wider text-[11px] font-semibold">
              <th scope="col" className="py-3 px-6">
                Name
              </th>
              <th scope="col" className="py-3 px-6">
                Device Type
              </th>
              <th scope="col" className="py-3 px-6">
                Platform
              </th>
              <th scope="col" className="py-3 px-6">
                OS Version
              </th>
              <th scope="col" className="py-3 px-6">
                Status
              </th>
              <th scope="col" className="py-3 px-6">
                Updated At
              </th>
              <th scope="col" className="py-3 px-6 text-right">
                Actions
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 text-slate-700">
            {devices.map((dev) => (
              <tr
                key={dev.id}
                className="hover:bg-slate-50/60 transition-colors group"
              >
                {/* Name */}
                <td className="py-4 px-6">
                  <div className="flex items-center gap-3">
                    <div className="w-8 h-8 rounded-full bg-gradient-to-br from-indigo-100 to-purple-200 text-indigo-700 flex items-center justify-center font-bold text-xs shrink-0 shadow-2xs">
                      <Smartphone className="w-4 h-4" />
                    </div>
                    <div className="min-w-0">
                      <p className="font-semibold text-slate-900 truncate">
                        {dev.name}
                      </p>
                      {dev.notes ? (
                        <p
                          className="text-[11px] text-slate-400 truncate max-w-xs"
                          title={dev.notes}
                        >
                          {dev.notes}
                        </p>
                      ) : (
                        <p className="text-[11px] text-slate-400 font-mono">
                          ID #{dev.id}
                        </p>
                      )}
                    </div>
                  </div>
                </td>

                {/* Device Type */}
                <td className="py-4 px-6">
                  <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-slate-100 text-slate-700 text-xs font-medium capitalize">
                    <Layers className="w-3.5 h-3.5 text-slate-500" />
                    {dev.device_type}
                  </span>
                </td>

                {/* Platform */}
                <td className="py-4 px-6">
                  <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-blue-50 text-blue-700 text-xs font-medium uppercase tracking-wider border border-blue-200/60">
                    <Cpu className="w-3.5 h-3.5 text-blue-600" />
                    {dev.platform}
                  </span>
                </td>

                {/* OS Version */}
                <td className="py-4 px-6 font-mono text-slate-600 font-medium">
                  v{dev.os_version}
                </td>

                {/* Status */}
                <td className="py-4 px-6">
                  {(() => {
                    const cachedStatus = lifecycleStatuses?.[dev.id];
                    return (
                      <div className="flex flex-col items-start gap-1.5">
                        <DeviceStatusBadge status={dev.status} />
                        {cachedStatus ? (
                          <div className="flex flex-col gap-1">
                            <DeviceReadinessBadge
                              ready={cachedStatus.ready}
                              runtimeStatus={cachedStatus.runtime_status}
                              size="sm"
                            />
                            <div
                              className="text-[10px] text-slate-400 font-mono flex items-center gap-1.5"
                              title={`Container: ${cachedStatus.docker_container_name} (${cachedStatus.container_status}) | Boot: ${cachedStatus.boot_completed ? "1" : "0"} | ADB: ${cachedStatus.adb_state}`}
                            >
                              <span
                                className={`w-1.5 h-1.5 rounded-full shrink-0 ${
                                  cachedStatus.container_status === "running"
                                    ? "bg-emerald-500"
                                    : "bg-slate-400"
                                }`}
                              />
                              <span className="truncate max-w-[130px]">
                                {cachedStatus.docker_container_name}
                              </span>
                            </div>
                          </div>
                        ) : (
                          <span className="text-[10px] text-slate-400 italic">
                            Uninspected
                          </span>
                        )}
                      </div>
                    );
                  })()}
                </td>

                {/* Updated At */}
                <td className="py-4 px-6 text-slate-500 whitespace-nowrap">
                  <div className="flex items-center gap-1.5">
                    <Calendar className="w-3.5 h-3.5 text-slate-400" />
                    <span>{formatDate(dev.updated_at)}</span>
                  </div>
                </td>

                {/* Actions: Status, Edit, and Delete */}
                <td className="py-4 px-6 text-right whitespace-nowrap">
                  <div className="flex items-center justify-end gap-1.5">
                    {onViewStatus && (() => {
                      const cachedStatus = lifecycleStatuses?.[dev.id];
                      return (
                        <button
                          type="button"
                          onClick={() => onViewStatus(dev)}
                          className={`inline-flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-xs font-semibold transition-colors shadow-2xs border ${
                            cachedStatus?.ready
                              ? "text-emerald-700 bg-emerald-50 border-emerald-200/70 hover:bg-emerald-100"
                              : cachedStatus
                              ? "text-amber-700 bg-amber-50 border-amber-200/70 hover:bg-amber-100"
                              : "text-indigo-700 bg-indigo-50 border border-indigo-200/60 hover:bg-indigo-100"
                          }`}
                          title={
                            cachedStatus
                              ? `Lifecycle: ${cachedStatus.runtime_status} (Ready: ${
                                  cachedStatus.ready ? "Yes" : "No"
                                }) - Click to inspect and manage`
                              : `Inspect lifecycle status for ${dev.name}`
                          }
                          aria-label={`View lifecycle status for ${dev.name}`}
                        >
                          <Activity className="w-3.5 h-3.5" />
                          <span>Status</span>
                        </button>
                      );
                    })()}
                    {onEditDevice && (
                      <button
                        type="button"
                        onClick={() => onEditDevice(dev)}
                        className="p-1.5 rounded-lg text-slate-500 hover:text-indigo-600 hover:bg-indigo-50 transition-colors"
                        title={`Edit device ${dev.name}`}
                        aria-label={`Edit device ${dev.name}`}
                      >
                        <Pencil className="w-3.5 h-3.5" />
                      </button>
                    )}
                    {onDeleteDevice && (
                      <button
                        type="button"
                        onClick={() => onDeleteDevice(dev)}
                        className="p-1.5 rounded-lg text-slate-500 hover:text-rose-600 hover:bg-rose-50 transition-colors"
                        title={`Delete device ${dev.name}`}
                        aria-label={`Delete device ${dev.name}`}
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    )}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

import React from "react";
import { Runtime } from "@/types/runtime";
import { Device } from "@/types/device";
import { RuntimeStatusBadge } from "./RuntimeStatusBadge";
import { RuntimeLoadingState } from "./RuntimeLoadingState";
import { RuntimeEmptyState } from "./RuntimeEmptyState";
import { RuntimeErrorState } from "./RuntimeErrorState";
import { Cpu, Calendar, Pencil, Trash2, Smartphone, AlertCircle, Layers } from "lucide-react";

interface RuntimeTableProps {
  runtimes: Runtime[];
  devicesMap: Record<number, Device>;
  isLoading: boolean;
  error: string | null;
  onRetry: () => void;
  isFiltered: boolean;
  onClearFilters: () => void;
  onCreateRuntime: () => void;
  onEditRuntime?: (runtime: Runtime) => void;
  onDeleteRuntime?: (runtime: Runtime) => void;
}

export function RuntimeTable({
  runtimes,
  devicesMap,
  isLoading,
  error,
  onRetry,
  isFiltered,
  onClearFilters,
  onCreateRuntime,
  onEditRuntime,
  onDeleteRuntime,
}: RuntimeTableProps) {
  // Format ISO date string
  const formatDate = (isoString: string | null) => {
    if (!isoString) return "Never";
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
        <RuntimeLoadingState rows={5} />
      ) : error ? (
        <RuntimeErrorState message={error} onRetry={onRetry} />
      ) : runtimes.length === 0 ? (
        <RuntimeEmptyState
          isFiltered={isFiltered}
          onClearFilters={onClearFilters}
          onCreateRuntime={onCreateRuntime}
        />
      ) : (
        <table className="w-full text-left text-xs border-collapse">
          <thead>
            <tr className="bg-slate-50/70 border-b border-slate-200/80 text-slate-500 uppercase tracking-wider text-[11px] font-semibold">
              <th scope="col" className="py-3 px-6">
                Name
              </th>
              <th scope="col" className="py-3 px-6">
                Device
              </th>
              <th scope="col" className="py-3 px-6">
                Runtime Type
              </th>
              <th scope="col" className="py-3 px-6">
                Status
              </th>
              <th scope="col" className="py-3 px-6">
                Last Seen
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
            {runtimes.map((rt) => {
              const matchedDevice = devicesMap[rt.device_id];

              return (
                <tr
                  key={rt.id}
                  className="hover:bg-slate-50/60 transition-colors group"
                >
                  {/* Name */}
                  <td className="py-4 px-6">
                    <div className="flex items-center gap-3">
                      <div className="w-8 h-8 rounded-full bg-gradient-to-br from-cyan-100 to-blue-200 text-cyan-700 flex items-center justify-center font-bold text-xs shrink-0 shadow-2xs">
                        <Cpu className="w-4 h-4" />
                      </div>
                      <div className="min-w-0">
                        <p className="font-semibold text-slate-900 truncate">
                          {rt.name}
                        </p>
                        <p className="text-[11px] text-slate-400 font-mono">
                          ID #{rt.id}
                        </p>
                      </div>
                    </div>
                  </td>

                  {/* Device (Name & Type or Clean Missing Fallback) */}
                  <td className="py-4 px-6">
                    {matchedDevice ? (
                      <div className="flex items-center gap-2">
                        <Smartphone className="w-3.5 h-3.5 text-slate-400 shrink-0" />
                        <div>
                          <p className="font-medium text-slate-900 truncate">
                            {matchedDevice.name}
                          </p>
                          <p className="text-[10px] text-slate-400 capitalize">
                            {matchedDevice.platform} • {matchedDevice.device_type} (ID #{rt.device_id})
                          </p>
                        </div>
                      </div>
                    ) : (
                      <div className="flex items-center gap-1.5 text-slate-400">
                        <AlertCircle className="w-3.5 h-3.5 text-amber-500 shrink-0" />
                        <span className="italic text-[11px]">
                          Device #{rt.device_id} (Missing)
                        </span>
                      </div>
                    )}
                  </td>

                  {/* Runtime Type */}
                  <td className="py-4 px-6">
                    <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-slate-100 text-slate-700 text-xs font-medium capitalize">
                      <Layers className="w-3.5 h-3.5 text-slate-500" />
                      {rt.runtime_type}
                    </span>
                  </td>

                  {/* Status */}
                  <td className="py-4 px-6">
                    <RuntimeStatusBadge status={rt.status} />
                  </td>

                  {/* Last Seen At */}
                  <td className="py-4 px-6 text-slate-500 whitespace-nowrap">
                    <div className="flex items-center gap-1.5">
                      <Calendar className="w-3.5 h-3.5 text-slate-400" />
                      <span>{formatDate(rt.last_seen_at)}</span>
                    </div>
                  </td>

                  {/* Updated At */}
                  <td className="py-4 px-6 text-slate-500 whitespace-nowrap">
                    <div className="flex items-center gap-1.5">
                      <Calendar className="w-3.5 h-3.5 text-slate-400" />
                      <span>{formatDate(rt.updated_at)}</span>
                    </div>
                  </td>

                  {/* Actions: Edit and Delete */}
                  <td className="py-4 px-6 text-right whitespace-nowrap">
                    <div className="flex items-center justify-end gap-1.5">
                      {onEditRuntime && (
                        <button
                          type="button"
                          onClick={() => onEditRuntime(rt)}
                          className="p-1.5 rounded-lg text-slate-500 hover:text-indigo-600 hover:bg-indigo-50 transition-colors"
                          title={`Edit runtime ${rt.name}`}
                          aria-label={`Edit runtime ${rt.name}`}
                        >
                          <Pencil className="w-3.5 h-3.5" />
                        </button>
                      )}
                      {onDeleteRuntime && (
                        <button
                          type="button"
                          onClick={() => onDeleteRuntime(rt)}
                          className="p-1.5 rounded-lg text-slate-500 hover:text-rose-600 hover:bg-rose-50 transition-colors"
                          title={`Delete runtime ${rt.name}`}
                          aria-label={`Delete runtime ${rt.name}`}
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
    </div>
  );
}

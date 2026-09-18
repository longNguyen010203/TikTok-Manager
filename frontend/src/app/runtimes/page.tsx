"use client";

import React, { useState, useEffect } from "react";
import {
  Runtime,
  CreateRuntimeInput,
  UpdateRuntimeInput,
  formatApiError,
} from "@/types/runtime";
import { Device } from "@/types/device";
import { runtimeService } from "@/services/runtimeService";
import { deviceService } from "@/services/deviceService";
import { RuntimeToolbar } from "@/components/runtimes/RuntimeToolbar";
import { RuntimeTable } from "@/components/runtimes/RuntimeTable";
import { RuntimePagination } from "@/components/runtimes/RuntimePagination";
import { RuntimeCreateModal } from "@/components/runtimes/RuntimeCreateModal";
import { RuntimeEditModal } from "@/components/runtimes/RuntimeEditModal";
import { RuntimeDeleteDialog } from "@/components/runtimes/RuntimeDeleteDialog";
import {
  Cpu,
  CheckCircle2,
  AlertCircle,
  RefreshCw,
  Server,
  Play,
  Pause,
} from "lucide-react";

export default function RuntimesPage() {
  const [runtimes, setRuntimes] = useState<Runtime[]>([]);
  const [total, setTotal] = useState(0);
  const [devices, setDevices] = useState<Device[]>([]);
  const [devicesMap, setDevicesMap] = useState<Record<number, Device>>({});
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("all");
  const [isLoading, setIsLoading] = useState(true);
  const [isLoadingDevices, setIsLoadingDevices] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Modals & Dialogs state
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [editingRuntime, setEditingRuntime] = useState<Runtime | null>(null);
  const [deletingRuntime, setDeletingRuntime] = useState<Runtime | null>(null);

  // Banner notifications
  const [bannerMessage, setBannerMessage] = useState<{
    type: "success" | "error";
    text: string;
  } | null>(null);

  const [refreshIndex, setRefreshIndex] = useState(0);
  const apiBaseUrl = runtimeService.getBaseUrl();

  // Fetch runtimes and devices from real FastAPI backend
  useEffect(() => {
    let ignore = false;

    Promise.all([
      runtimeService.getRuntimes({
        page: currentPage,
        page_size: pageSize,
      }),
      deviceService.getDevices({
        page: 1,
        page_size: 100,
      }),
    ])
      .then(([runtimeRes, deviceRes]) => {
        if (!ignore) {
          setRuntimes(runtimeRes.items);
          setTotal(runtimeRes.total);
          setDevices(deviceRes.items);

          const dMap: Record<number, Device> = {};
          deviceRes.items.forEach((d) => {
            dMap[d.id] = d;
          });
          setDevicesMap(dMap);

          setError(null);
          setIsLoading(false);
          setIsLoadingDevices(false);
        }
      })
      .catch((err: unknown) => {
        if (!ignore) {
          let msg = formatApiError(err);
          if (
            msg.toLowerCase().includes("failed to fetch") ||
            msg.toLowerCase().includes("networkerror")
          ) {
            msg = `Unable to connect to FastAPI backend at ${apiBaseUrl}. Ensure the backend server is running.`;
          }
          setError(msg);
          setRuntimes([]);
          setTotal(0);
          setIsLoading(false);
          setIsLoadingDevices(false);
        }
      });

    return () => {
      ignore = true;
    };
  }, [currentPage, pageSize, refreshIndex, apiBaseUrl]);

  const handleRefresh = () => {
    setIsLoading(true);
    setRefreshIndex((idx) => idx + 1);
  };

  // Filter & pagination handlers
  const handleSearchChange = (value: string) => {
    setSearch(value);
  };

  const handleStatusChange = (newStatus: string) => {
    setStatus(newStatus);
  };

  const handlePageChange = (newPage: number) => {
    setIsLoading(true);
    setCurrentPage(newPage);
  };

  const handlePageSizeChange = (newPageSize: number) => {
    setIsLoading(true);
    setPageSize(newPageSize);
    setCurrentPage(1);
  };

  const handleClearFilters = () => {
    setSearch("");
    setStatus("all");
  };

  // CRUD handlers
  const handleCreateRuntime = async (input: CreateRuntimeInput) => {
    try {
      const created = await runtimeService.createRuntime(input);
      setBannerMessage({
        type: "success",
        text: `Runtime "${created.name}" created successfully!`,
      });
      setTimeout(() => setBannerMessage(null), 5000);
      setCurrentPage(1);
      handleRefresh();
    } catch (err: unknown) {
      throw err;
    }
  };

  const handleUpdateRuntime = async (
    id: number,
    input: UpdateRuntimeInput
  ) => {
    try {
      const updated = await runtimeService.updateRuntime(id, input);
      setBannerMessage({
        type: "success",
        text: `Runtime "${updated.name}" updated successfully!`,
      });
      setTimeout(() => setBannerMessage(null), 5000);
      handleRefresh();
    } catch (err: unknown) {
      throw err;
    }
  };

  const handleDeleteRuntime = async (id: number) => {
    try {
      await runtimeService.deleteRuntime(id);
      setBannerMessage({
        type: "success",
        text: `Runtime ID #${id} deleted successfully.`,
      });
      setTimeout(() => setBannerMessage(null), 5000);
      handleRefresh();
    } catch (err: unknown) {
      throw err;
    }
  };

  // Client-side filtering by status and search text (including device name)
  const displayedRuntimes = runtimes.filter((rt) => {
    const matchesStatus =
      status === "all" || rt.status.toLowerCase() === status.toLowerCase();

    if (!matchesStatus) return false;

    if (!search.trim()) return true;

    const q = search.trim().toLowerCase();
    const deviceName = devicesMap[rt.device_id]?.name.toLowerCase() || "";
    return (
      rt.name.toLowerCase().includes(q) ||
      rt.runtime_type.toLowerCase().includes(q) ||
      rt.status.toLowerCase().includes(q) ||
      deviceName.includes(q) ||
      String(rt.device_id).includes(q)
    );
  });

  const isFiltered = search.trim().length > 0 || status !== "all";

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-2xl font-bold text-slate-900 tracking-tight flex items-center gap-2.5">
            <Cpu className="w-6 h-6 text-rose-600" />
            <span>Runtime Management</span>
          </h2>
          <p className="text-sm text-slate-500 mt-1">
            Provision, monitor, and configure TikTok execution runtimes linked to host devices.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={handleRefresh}
            disabled={isLoading}
            className="inline-flex items-center gap-1.5 px-3 py-2 border border-slate-200 text-xs font-medium rounded-lg text-slate-700 bg-white hover:bg-slate-50 transition-colors shadow-2xs disabled:opacity-50"
          >
            <RefreshCw
              className={`w-3.5 h-3.5 ${isLoading ? "animate-spin" : ""}`}
            />
            <span>Refresh</span>
          </button>
        </div>
      </div>

      {/* Banner Notifications */}
      {bannerMessage && (
        <div
          className={`p-3.5 rounded-xl border text-xs flex items-center justify-between animate-in fade-in slide-in-from-top-2 duration-200 ${
            bannerMessage.type === "success"
              ? "bg-emerald-50 border-emerald-200 text-emerald-800"
              : "bg-rose-50 border-rose-200 text-rose-800"
          }`}
        >
          <div className="flex items-center gap-2">
            {bannerMessage.type === "success" ? (
              <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
            ) : (
              <AlertCircle className="w-4 h-4 text-rose-600 shrink-0" />
            )}
            <span className="font-medium">{bannerMessage.text}</span>
          </div>
          <button
            type="button"
            onClick={() => setBannerMessage(null)}
            className="font-bold ml-2 hover:opacity-75"
          >
            &times;
          </button>
        </div>
      )}

      {/* Backend Connection Status Banner */}
      <div className="p-3.5 rounded-xl border border-slate-200/80 bg-slate-100/60 text-slate-700 text-xs flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2 shadow-2xs">
        <div className="flex items-center gap-2">
          <Server className="w-4 h-4 text-slate-500 shrink-0" />
          <span className="font-medium text-slate-800">
            Backend Endpoint:
          </span>
          <code className="px-1.5 py-0.5 rounded bg-white border border-slate-200 font-mono text-[11px] text-slate-700">
            {apiBaseUrl}/runtimes
          </code>
        </div>
        <span className="text-[11px] text-slate-500">
          Host Devices loaded: <strong className="font-semibold text-slate-800">{devices.length}</strong>
        </span>
      </div>

      {/* Overview Stat Chips */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <div className="bg-white p-3.5 rounded-xl border border-slate-200/80 shadow-2xs flex items-center gap-3">
          <div className="p-2 rounded-lg bg-slate-100 text-slate-600">
            <Cpu className="w-4 h-4" />
          </div>
          <div>
            <p className="text-[11px] font-medium text-slate-500">Total Runtimes</p>
            <p className="text-lg font-bold text-slate-900">{total}</p>
          </div>
        </div>

        <div className="bg-white p-3.5 rounded-xl border border-slate-200/80 shadow-2xs flex items-center gap-3">
          <div className="p-2 rounded-lg bg-emerald-50 text-emerald-600">
            <Play className="w-4 h-4 fill-emerald-600" />
          </div>
          <div>
            <p className="text-[11px] font-medium text-slate-500">Running</p>
            <p className="text-lg font-bold text-slate-900">
              {runtimes.filter((r) => r.status.toLowerCase() === "running").length}
            </p>
          </div>
        </div>

        <div className="bg-white p-3.5 rounded-xl border border-slate-200/80 shadow-2xs flex items-center gap-3">
          <div className="p-2 rounded-lg bg-blue-50 text-blue-600">
            <Pause className="w-4 h-4" />
          </div>
          <div>
            <p className="text-[11px] font-medium text-slate-500">Idle</p>
            <p className="text-lg font-bold text-slate-900">
              {runtimes.filter((r) => r.status.toLowerCase() === "idle").length}
            </p>
          </div>
        </div>

        <div className="bg-white p-3.5 rounded-xl border border-slate-200/80 shadow-2xs flex items-center gap-3">
          <div className="p-2 rounded-lg bg-rose-50 text-rose-600">
            <AlertCircle className="w-4 h-4" />
          </div>
          <div>
            <p className="text-[11px] font-medium text-slate-500">Stopped / Error</p>
            <p className="text-lg font-bold text-slate-900">
              {
                runtimes.filter(
                  (r) =>
                    r.status.toLowerCase() === "stopped" ||
                    r.status.toLowerCase() === "error"
                ).length
              }
            </p>
          </div>
        </div>
      </div>

      {/* Main Table Card */}
      <div className="bg-white rounded-xl border border-slate-200/80 shadow-2xs overflow-hidden">
        {/* Toolbar: Search, Status Filter, Create Button */}
        <RuntimeToolbar
          search={search}
          onSearchChange={handleSearchChange}
          status={status}
          onStatusChange={handleStatusChange}
          onCreateClick={() => setIsCreateModalOpen(true)}
          apiBaseUrl={apiBaseUrl}
        />

        {/* Runtime Table */}
        <RuntimeTable
          runtimes={displayedRuntimes}
          devicesMap={devicesMap}
          isLoading={isLoading}
          error={error}
          onRetry={handleRefresh}
          isFiltered={isFiltered}
          onClearFilters={handleClearFilters}
          onCreateRuntime={() => setIsCreateModalOpen(true)}
          onEditRuntime={(rt) => setEditingRuntime(rt)}
          onDeleteRuntime={(rt) => setDeletingRuntime(rt)}
        />

        {/* Pagination UI */}
        {!isLoading && !error && runtimes.length > 0 && (
          <RuntimePagination
            currentPage={currentPage}
            pageSize={pageSize}
            total={total}
            onPageChange={handlePageChange}
            onPageSizeChange={handlePageSizeChange}
          />
        )}
      </div>

      {/* Create Runtime Modal */}
      <RuntimeCreateModal
        isOpen={isCreateModalOpen}
        devices={devices}
        isLoadingDevices={isLoadingDevices}
        onClose={() => setIsCreateModalOpen(false)}
        onSubmit={handleCreateRuntime}
      />

      {/* Edit Runtime Modal */}
      <RuntimeEditModal
        runtime={editingRuntime}
        devices={devices}
        isLoadingDevices={isLoadingDevices}
        isOpen={editingRuntime !== null}
        onClose={() => setEditingRuntime(null)}
        onSubmit={handleUpdateRuntime}
      />

      {/* Delete Confirmation Dialog */}
      <RuntimeDeleteDialog
        runtime={deletingRuntime}
        isOpen={deletingRuntime !== null}
        onClose={() => setDeletingRuntime(null)}
        onConfirm={handleDeleteRuntime}
      />
    </div>
  );
}

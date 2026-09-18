"use client";

import React, { useState, useEffect } from "react";
import {
  Device,
  CreateDeviceInput,
  UpdateDeviceInput,
  formatApiError,
} from "@/types/device";
import { deviceService } from "@/services/deviceService";
import { DeviceToolbar } from "@/components/devices/DeviceToolbar";
import { DeviceTable } from "@/components/devices/DeviceTable";
import { DevicePagination } from "@/components/devices/DevicePagination";
import { DeviceCreateModal } from "@/components/devices/DeviceCreateModal";
import { DeviceEditModal } from "@/components/devices/DeviceEditModal";
import { DeviceDeleteDialog } from "@/components/devices/DeviceDeleteDialog";
import {
  Smartphone,
  CheckCircle2,
  AlertCircle,
  RefreshCw,
  Server,
  Clock,
} from "lucide-react";

export default function DevicesPage() {
  const [devices, setDevices] = useState<Device[]>([]);
  const [total, setTotal] = useState(0);
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("all");
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Modals & Dialogs state
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [editingDevice, setEditingDevice] = useState<Device | null>(null);
  const [deletingDevice, setDeletingDevice] = useState<Device | null>(null);

  // Banner notifications
  const [bannerMessage, setBannerMessage] = useState<{
    type: "success" | "error";
    text: string;
  } | null>(null);

  const [refreshIndex, setRefreshIndex] = useState(0);
  const apiBaseUrl = deviceService.getBaseUrl();

  // Fetch devices from real FastAPI backend
  useEffect(() => {
    let ignore = false;

    deviceService
      .getDevices({
        page: currentPage,
        page_size: pageSize,
      })
      .then((res) => {
        if (!ignore) {
          setDevices(res.items);
          setTotal(res.total);
          setError(null);
          setIsLoading(false);
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
          setDevices([]);
          setTotal(0);
          setIsLoading(false);
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
  const handleCreateDevice = async (input: CreateDeviceInput) => {
    try {
      const created = await deviceService.createDevice(input);
      setBannerMessage({
        type: "success",
        text: `Device "${created.name}" created successfully!`,
      });
      setTimeout(() => setBannerMessage(null), 5000);
      setCurrentPage(1);
      handleRefresh();
    } catch (err: unknown) {
      throw err;
    }
  };

  const handleUpdateDevice = async (
    id: number,
    input: UpdateDeviceInput
  ) => {
    try {
      const updated = await deviceService.updateDevice(id, input);
      setBannerMessage({
        type: "success",
        text: `Device "${updated.name}" updated successfully!`,
      });
      setTimeout(() => setBannerMessage(null), 5000);
      handleRefresh();
    } catch (err: unknown) {
      throw err;
    }
  };

  const handleDeleteDevice = async (id: number) => {
    try {
      await deviceService.deleteDevice(id);
      setBannerMessage({
        type: "success",
        text: `Device ID #${id} deleted successfully.`,
      });
      setTimeout(() => setBannerMessage(null), 5000);
      handleRefresh();
    } catch (err: unknown) {
      throw err;
    }
  };

  // Client-side filtering by status and search text
  const displayedDevices = devices.filter((dev) => {
    const matchesStatus =
      status === "all" || dev.status.toLowerCase() === status.toLowerCase();

    if (!matchesStatus) return false;

    if (!search.trim()) return true;

    const q = search.trim().toLowerCase();
    return (
      dev.name.toLowerCase().includes(q) ||
      dev.device_type.toLowerCase().includes(q) ||
      dev.platform.toLowerCase().includes(q) ||
      dev.os_version.toLowerCase().includes(q) ||
      (dev.notes && dev.notes.toLowerCase().includes(q))
    );
  });

  const isFiltered = search.trim().length > 0 || status !== "all";

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-2xl font-bold text-slate-900 tracking-tight flex items-center gap-2.5">
            <Smartphone className="w-6 h-6 text-rose-600" />
            <span>Device Management</span>
          </h2>
          <p className="text-sm text-slate-500 mt-1">
            Provision and inspect Android/iOS physical devices, emulators, and cloud instances.
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
            {apiBaseUrl}/devices
          </code>
        </div>
        <span className="text-[11px] text-slate-500">
          Configured via <code className="font-mono">NEXT_PUBLIC_API_BASE_URL</code>
        </span>
      </div>

      {/* Overview Stat Chips */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <div className="bg-white p-3.5 rounded-xl border border-slate-200/80 shadow-2xs flex items-center gap-3">
          <div className="p-2 rounded-lg bg-slate-100 text-slate-600">
            <Smartphone className="w-4 h-4" />
          </div>
          <div>
            <p className="text-[11px] font-medium text-slate-500">Total Devices</p>
            <p className="text-lg font-bold text-slate-900">{total}</p>
          </div>
        </div>

        <div className="bg-white p-3.5 rounded-xl border border-slate-200/80 shadow-2xs flex items-center gap-3">
          <div className="p-2 rounded-lg bg-emerald-50 text-emerald-600">
            <CheckCircle2 className="w-4 h-4" />
          </div>
          <div>
            <p className="text-[11px] font-medium text-slate-500">Online</p>
            <p className="text-lg font-bold text-slate-900">
              {devices.filter((d) => d.status.toLowerCase() === "online").length}
            </p>
          </div>
        </div>

        <div className="bg-white p-3.5 rounded-xl border border-slate-200/80 shadow-2xs flex items-center gap-3">
          <div className="p-2 rounded-lg bg-amber-50 text-amber-600">
            <Clock className="w-4 h-4" />
          </div>
          <div>
            <p className="text-[11px] font-medium text-slate-500">Busy</p>
            <p className="text-lg font-bold text-slate-900">
              {devices.filter((d) => d.status.toLowerCase() === "busy").length}
            </p>
          </div>
        </div>

        <div className="bg-white p-3.5 rounded-xl border border-slate-200/80 shadow-2xs flex items-center gap-3">
          <div className="p-2 rounded-lg bg-rose-50 text-rose-600">
            <AlertCircle className="w-4 h-4" />
          </div>
          <div>
            <p className="text-[11px] font-medium text-slate-500">Offline / Error</p>
            <p className="text-lg font-bold text-slate-900">
              {
                devices.filter(
                  (d) =>
                    d.status.toLowerCase() === "offline" ||
                    d.status.toLowerCase() === "error"
                ).length
              }
            </p>
          </div>
        </div>
      </div>

      {/* Main Table Card */}
      <div className="bg-white rounded-xl border border-slate-200/80 shadow-2xs overflow-hidden">
        {/* Toolbar: Search, Status Filter, Create Button */}
        <DeviceToolbar
          search={search}
          onSearchChange={handleSearchChange}
          status={status}
          onStatusChange={handleStatusChange}
          onCreateClick={() => setIsCreateModalOpen(true)}
          apiBaseUrl={apiBaseUrl}
        />

        {/* Device Table */}
        <DeviceTable
          devices={displayedDevices}
          isLoading={isLoading}
          error={error}
          onRetry={handleRefresh}
          isFiltered={isFiltered}
          onClearFilters={handleClearFilters}
          onCreateDevice={() => setIsCreateModalOpen(true)}
          onEditDevice={(dev) => setEditingDevice(dev)}
          onDeleteDevice={(dev) => setDeletingDevice(dev)}
        />

        {/* Pagination UI */}
        {!isLoading && !error && devices.length > 0 && (
          <DevicePagination
            currentPage={currentPage}
            pageSize={pageSize}
            total={total}
            onPageChange={handlePageChange}
            onPageSizeChange={handlePageSizeChange}
          />
        )}
      </div>

      {/* Create Device Modal */}
      <DeviceCreateModal
        isOpen={isCreateModalOpen}
        onClose={() => setIsCreateModalOpen(false)}
        onSubmit={handleCreateDevice}
      />

      {/* Edit Device Modal */}
      <DeviceEditModal
        device={editingDevice}
        isOpen={editingDevice !== null}
        onClose={() => setEditingDevice(null)}
        onSubmit={handleUpdateDevice}
      />

      {/* Delete Confirmation Dialog */}
      <DeviceDeleteDialog
        device={deletingDevice}
        isOpen={deletingDevice !== null}
        onClose={() => setDeletingDevice(null)}
        onConfirm={handleDeleteDevice}
      />
    </div>
  );
}

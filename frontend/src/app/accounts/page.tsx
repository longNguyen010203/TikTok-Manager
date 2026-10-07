"use client";

import React, { useState, useEffect } from "react";
import {
  Account,
  CreateAccountInput,
  UpdateAccountInput,
  formatApiError,
} from "@/types/account";
import { Runtime } from "@/types/runtime";
import { Device } from "@/types/device";
import { accountService } from "@/services/accountService";
import { runtimeService } from "@/services/runtimeService";
import { deviceService } from "@/services/deviceService";
import { AccountToolbar } from "@/components/accounts/AccountToolbar";
import { AccountTable } from "@/components/accounts/AccountTable";
import { AccountPagination } from "@/components/accounts/AccountPagination";
import { AccountCreateModal } from "@/components/accounts/AccountCreateModal";
import { AccountEditModal } from "@/components/accounts/AccountEditModal";
import { AccountDeleteDialog } from "@/components/accounts/AccountDeleteDialog";
import { AccountAssignModal } from "@/components/accounts/AccountAssignModal";
import { AccountSecretsModal } from "@/components/accounts/AccountSecretsModal";
import {
  Users,
  CheckCircle2,
  AlertCircle,
  RefreshCw,
  Server,
  Cpu,
  KeyRound,
  Archive,
} from "lucide-react";

export default function AccountsPage() {
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [total, setTotal] = useState(0);
  const [runtimes, setRuntimes] = useState<Runtime[]>([]);
  const [runtimesMap, setRuntimesMap] = useState<Record<number, Runtime>>({});
  const [devicesMap, setDevicesMap] = useState<Record<number, Device>>({});

  // Backend-driven query parameters
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("all");
  const [niche, setNiche] = useState("");
  const [tag, setTag] = useState("");
  const [runtimeId, setRuntimeId] = useState("");
  const [deviceId, setDeviceId] = useState("");
  const [includeArchived, setIncludeArchived] = useState(false);

  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Modals state
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [editingAccount, setEditingAccount] = useState<Account | null>(null);
  const [assigningAccount, setAssigningAccount] = useState<Account | null>(null);
  const [deletingAccount, setDeletingAccount] = useState<Account | null>(null);
  const [managingSecretsAccount, setManagingSecretsAccount] =
    useState<Account | null>(null);

  // Banner notifications
  const [bannerMessage, setBannerMessage] = useState<{
    type: "success" | "error";
    text: string;
  } | null>(null);

  const [refreshIndex, setRefreshIndex] = useState(0);
  const apiBaseUrl = accountService.getBaseUrl();

  // Load accounts based strictly on backend queries
  // Main data fetch effect
  useEffect(() => {
    let ignore = false;

    accountService
      .getAccounts({
        page: currentPage,
        page_size: pageSize,
        status: status === "all" ? undefined : status,
        niche: niche.trim() || undefined,
        tag: tag.trim() || undefined,
        runtime_id: runtimeId ? parseInt(runtimeId, 10) : undefined,
        device_id: deviceId ? parseInt(deviceId, 10) : undefined,
        query: search.trim() || undefined,
        include_archived: includeArchived,
      })
      .then((accountsRes) => {
        if (!ignore) {
          setAccounts(accountsRes.items);
          setTotal(accountsRes.total);
          setError(null);
        }
      })
      .catch((err: unknown) => {
        if (!ignore) {
          let msg = formatApiError(err);
          if (
            msg.toLowerCase().includes("failed to fetch") ||
            msg.toLowerCase().includes("networkerror")
          ) {
            msg = `Unable to connect to FastAPI backend at ${apiBaseUrl}. Ensure the backend service is active.`;
          }
          setError(msg);
          setAccounts([]);
          setTotal(0);
        }
      })
      .finally(() => {
        if (!ignore) {
          setIsLoading(false);
        }
      });

    return () => {
      ignore = true;
    };
  }, [
    currentPage,
    pageSize,
    status,
    niche,
    tag,
    runtimeId,
    deviceId,
    search,
    includeArchived,
    apiBaseUrl,
    refreshIndex,
  ]);

  // Initial & peripheral data load: Runtimes & Devices
  useEffect(() => {
    let ignore = false;

    Promise.all([
      runtimeService.getRuntimes({ page: 1, page_size: 100 }),
      deviceService.getDevices({ page: 1, page_size: 100 }),
    ])
      .then(([runtimesRes, devicesRes]) => {
        if (!ignore) {
          setRuntimes(runtimesRes.items);

          const rMap: Record<number, Runtime> = {};
          runtimesRes.items.forEach((rt) => {
            rMap[rt.id] = rt;
          });
          setRuntimesMap(rMap);

          const dMap: Record<number, Device> = {};
          devicesRes.items.forEach((dev) => {
            dMap[dev.id] = dev;
          });
          setDevicesMap(dMap);
        }
      })
      .catch(() => {
        // Soft fail for peripheral resources
      });

    return () => {
      ignore = true;
    };
  }, []);

  const handleRefresh = () => {
    setIsLoading(true);
    setRefreshIndex((idx) => idx + 1);
  };

  // Reset to page 1 on filter changes
  const handleSearchChange = (value: string) => {
    setSearch(value);
    setCurrentPage(1);
  };

  const handleStatusChange = (newStatus: string) => {
    setStatus(newStatus);
    setCurrentPage(1);
  };

  const handleNicheChange = (newNiche: string) => {
    setNiche(newNiche);
    setCurrentPage(1);
  };

  const handleTagChange = (newTag: string) => {
    setTag(newTag);
    setCurrentPage(1);
  };

  const handleRuntimeIdChange = (newRtId: string) => {
    setRuntimeId(newRtId);
    setCurrentPage(1);
  };

  const handleDeviceIdChange = (newDevId: string) => {
    setDeviceId(newDevId);
    setCurrentPage(1);
  };

  const handleIncludeArchivedChange = (newInclude: boolean) => {
    setIncludeArchived(newInclude);
    setCurrentPage(1);
  };

  const handleClearFilters = () => {
    setSearch("");
    setStatus("all");
    setNiche("");
    setTag("");
    setRuntimeId("");
    setDeviceId("");
    setIncludeArchived(false);
    setCurrentPage(1);
  };

  const handlePageChange = (newPage: number) => {
    setCurrentPage(newPage);
  };

  const handlePageSizeChange = (newPageSize: number) => {
    setPageSize(newPageSize);
    setCurrentPage(1);
  };

  // CRUD actions
  const handleCreateAccount = async (input: CreateAccountInput) => {
    try {
      const created = await accountService.createAccount(input);
      setBannerMessage({
        type: "success",
        text: `Account "${created.display_name}" created successfully!`,
      });
      setTimeout(() => setBannerMessage(null), 5000);
      setCurrentPage(1);
      handleRefresh();
    } catch (err: unknown) {
      throw err;
    }
  };

  const handleUpdateAccount = async (id: number, input: UpdateAccountInput) => {
    try {
      const updated = await accountService.updateAccount(id, input);
      setBannerMessage({
        type: "success",
        text: `Account "${updated.display_name}" updated successfully!`,
      });
      setTimeout(() => setBannerMessage(null), 5000);
      handleRefresh();
    } catch (err: unknown) {
      throw err;
    }
  };

  const handleArchiveAccount = async (id: number) => {
    try {
      await accountService.deleteAccount(id);
      setBannerMessage({
        type: "success",
        text: `Account ID #${id} archived successfully. Historical records preserved.`,
      });
      setTimeout(() => setBannerMessage(null), 5000);
      handleRefresh();
    } catch (err: unknown) {
      throw err;
    }
  };

  const handleAssignRuntime = async (accountId: number, rtId: number) => {
    try {
      await accountService.assignRuntime(accountId, rtId);
      setBannerMessage({
        type: "success",
        text: `Runtime #${rtId} assigned to Account #${accountId}.`,
      });
      setTimeout(() => setBannerMessage(null), 5000);
      handleRefresh();
    } catch (err: unknown) {
      throw err;
    }
  };

  const handleUnassignRuntime = async (accountId: number) => {
    try {
      await accountService.unassignRuntime(accountId);
      setBannerMessage({
        type: "success",
        text: `Runtime unassigned from Account #${accountId}.`,
      });
      setTimeout(() => setBannerMessage(null), 5000);
      handleRefresh();
    } catch (err: unknown) {
      throw err;
    }
  };

  const isFiltered =
    search.trim().length > 0 ||
    status !== "all" ||
    niche.trim().length > 0 ||
    tag.trim().length > 0 ||
    runtimeId !== "" ||
    deviceId !== "" ||
    includeArchived;

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-2xl font-bold text-slate-900 tracking-tight flex items-center gap-2.5">
            <Users className="w-6 h-6 text-rose-600" />
            <span>Account Control Center</span>
          </h2>
          <p className="text-sm text-slate-500 mt-1">
            Authoritative account registry, write-only credentials, execution assignments, and lifecycle governance.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={handleRefresh}
            disabled={isLoading}
            className="inline-flex items-center gap-1.5 px-3 py-2 border border-slate-200 text-xs font-medium rounded-lg text-slate-700 bg-white hover:bg-slate-50 transition-colors shadow-2xs disabled:opacity-50 cursor-pointer"
            title="Refresh accounts"
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
            Canonical Backend Endpoint:
          </span>
          <code className="px-1.5 py-0.5 rounded bg-white border border-slate-200 font-mono text-[11px] text-slate-700">
            {apiBaseUrl}
          </code>
        </div>
        <div className="flex items-center gap-3 text-[11px] text-slate-500">
          <span>
            Available Runtimes: <strong className="font-semibold text-slate-800">{runtimes.length}</strong>
          </span>
          <span>&bull;</span>
          <span>
            Derived Devices: <strong className="font-semibold text-slate-800">{Object.keys(devicesMap).length}</strong>
          </span>
        </div>
      </div>

      {/* Overview Stat Chips */}
      <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
        <div className="bg-white p-3.5 rounded-xl border border-slate-200/80 shadow-2xs flex items-center gap-3">
          <div className="p-2 rounded-lg bg-slate-100 text-slate-600">
            <Users className="w-4 h-4" />
          </div>
          <div>
            <p className="text-[11px] font-medium text-slate-500">Registry Total</p>
            <p className="text-lg font-bold text-slate-900">{total}</p>
          </div>
        </div>

        <div className="bg-white p-3.5 rounded-xl border border-slate-200/80 shadow-2xs flex items-center gap-3">
          <div className="p-2 rounded-lg bg-emerald-50 text-emerald-600">
            <CheckCircle2 className="w-4 h-4" />
          </div>
          <div>
            <p className="text-[11px] font-medium text-slate-500">Active Listed</p>
            <p className="text-lg font-bold text-slate-900">
              {accounts.filter((a) => a.status === "active").length}
            </p>
          </div>
        </div>

        <div className="bg-white p-3.5 rounded-xl border border-slate-200/80 shadow-2xs flex items-center gap-3">
          <div className="p-2 rounded-lg bg-cyan-50 text-cyan-600">
            <Cpu className="w-4 h-4" />
          </div>
          <div>
            <p className="text-[11px] font-medium text-slate-500">Assigned Runtime</p>
            <p className="text-lg font-bold text-slate-900">
              {accounts.filter((a) => a.runtime_id !== null).length}
            </p>
          </div>
        </div>

        <div className="bg-white p-3.5 rounded-xl border border-slate-200/80 shadow-2xs flex items-center gap-3">
          <div className="p-2 rounded-lg bg-emerald-50 text-emerald-700">
            <KeyRound className="w-4 h-4" />
          </div>
          <div>
            <p className="text-[11px] font-medium text-slate-500">With Credentials</p>
            <p className="text-lg font-bold text-slate-900">
              {accounts.filter((a) => a.secret_present).length}
            </p>
          </div>
        </div>

        <div className="bg-white p-3.5 rounded-xl border border-slate-200/80 shadow-2xs flex items-center gap-3">
          <div className="p-2 rounded-lg bg-purple-50 text-purple-600">
            <Archive className="w-4 h-4" />
          </div>
          <div>
            <p className="text-[11px] font-medium text-slate-500">Archived Mode</p>
            <p className="text-xs font-bold text-slate-900 mt-1">
              {includeArchived ? "Included" : "Hidden"}
            </p>
          </div>
        </div>
      </div>

      {/* Main Table Card */}
      <div className="bg-white rounded-xl border border-slate-200/80 shadow-2xs overflow-hidden">
        {/* Toolbar: Search, Filters, Create Account Button */}
        <AccountToolbar
          search={search}
          onSearchChange={handleSearchChange}
          status={status}
          onStatusChange={handleStatusChange}
          niche={niche}
          onNicheChange={handleNicheChange}
          tag={tag}
          onTagChange={handleTagChange}
          runtimeId={runtimeId}
          onRuntimeIdChange={handleRuntimeIdChange}
          deviceId={deviceId}
          onDeviceIdChange={handleDeviceIdChange}
          includeArchived={includeArchived}
          onIncludeArchivedChange={handleIncludeArchivedChange}
          isFiltered={isFiltered}
          onClearFilters={handleClearFilters}
          onCreateClick={() => setIsCreateModalOpen(true)}
          runtimes={runtimes}
          devicesMap={devicesMap}
          apiBaseUrl={apiBaseUrl}
        />

        {/* Server-Driven Account Table */}
        <AccountTable
          accounts={accounts}
          runtimesMap={runtimesMap}
          devicesMap={devicesMap}
          isLoading={isLoading}
          error={error}
          onRetry={handleRefresh}
          isFiltered={isFiltered}
          onClearFilters={handleClearFilters}
          onCreateAccount={() => setIsCreateModalOpen(true)}
          onEditAccount={(acc) => setEditingAccount(acc)}
          onDeleteAccount={(acc) => setDeletingAccount(acc)}
          onAssignRuntime={(acc) => setAssigningAccount(acc)}
          onManageSecrets={(acc) => setManagingSecretsAccount(acc)}
        />

        {/* Pagination UI */}
        {!isLoading && !error && accounts.length > 0 && (
          <AccountPagination
            currentPage={currentPage}
            pageSize={pageSize}
            total={total}
            onPageChange={handlePageChange}
            onPageSizeChange={handlePageSizeChange}
          />
        )}
      </div>

      {/* Create Account Modal */}
      <AccountCreateModal
        isOpen={isCreateModalOpen}
        runtimes={runtimes}
        onClose={() => setIsCreateModalOpen(false)}
        onSubmit={handleCreateAccount}
      />

      {/* Edit Account Modal */}
      <AccountEditModal
        account={editingAccount}
        runtimes={runtimes}
        devicesMap={devicesMap}
        isOpen={editingAccount !== null}
        onClose={() => setEditingAccount(null)}
        onSubmit={handleUpdateAccount}
        onOpenSecrets={(acc) => setManagingSecretsAccount(acc)}
      />

      {/* Quick Assign Runtime Modal */}
      <AccountAssignModal
        account={assigningAccount}
        runtimes={runtimes}
        devicesMap={devicesMap}
        isOpen={assigningAccount !== null}
        onClose={() => setAssigningAccount(null)}
        onAssignRuntime={handleAssignRuntime}
        onUnassignRuntime={handleUnassignRuntime}
      />

      {/* Archive Account Dialog */}
      <AccountDeleteDialog
        account={deletingAccount}
        isOpen={deletingAccount !== null}
        onClose={() => setDeletingAccount(null)}
        onConfirm={handleArchiveAccount}
      />

      {/* Write-Only Secrets Modal */}
      <AccountSecretsModal
        account={managingSecretsAccount}
        isOpen={managingSecretsAccount !== null}
        onClose={() => setManagingSecretsAccount(null)}
        onAccountUpdated={handleRefresh}
      />
    </div>
  );
}

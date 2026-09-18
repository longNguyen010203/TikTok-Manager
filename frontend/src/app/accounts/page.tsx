"use client";

import React, { useState, useEffect } from "react";
import {
  Account,
  CreateAccountInput,
  UpdateAccountInput,
  formatApiError,
} from "@/types/account";
import { accountService } from "@/services/accountService";
import { AccountToolbar } from "@/components/accounts/AccountToolbar";
import { AccountTable } from "@/components/accounts/AccountTable";
import { AccountPagination } from "@/components/accounts/AccountPagination";
import { AccountCreateModal } from "@/components/accounts/AccountCreateModal";
import { AccountEditModal } from "@/components/accounts/AccountEditModal";
import { AccountDeleteDialog } from "@/components/accounts/AccountDeleteDialog";
import {
  Users,
  CheckCircle2,
  PauseCircle,
  AlertCircle,
  RefreshCw,
  Server,
} from "lucide-react";

export default function AccountsPage() {
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [total, setTotal] = useState(0);
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("all");
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Modals & Dialogs state
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [editingAccount, setEditingAccount] = useState<Account | null>(null);
  const [deletingAccount, setDeletingAccount] = useState<Account | null>(null);

  // Notifications
  const [bannerMessage, setBannerMessage] = useState<{
    type: "success" | "error";
    text: string;
  } | null>(null);

  const [refreshIndex, setRefreshIndex] = useState(0);
  const apiBaseUrl = accountService.getBaseUrl();

  // Fetch accounts from FastAPI backend
  useEffect(() => {
    let ignore = false;

    accountService
      .getAccounts({
        page: currentPage,
        page_size: pageSize,
        status: status === "all" ? undefined : status,
      })
      .then((res) => {
        if (!ignore) {
          setAccounts(res.items);
          setTotal(res.total);
          setError(null);
          setIsLoading(false);
        }
      })
      .catch((err: unknown) => {
        if (!ignore) {
          let msg = formatApiError(err);
          // Helpful guidance if connection refused
          if (
            msg.toLowerCase().includes("failed to fetch") ||
            msg.toLowerCase().includes("networkerror")
          ) {
            msg = `Unable to connect to FastAPI backend at ${apiBaseUrl}. Ensure the backend server is running.`;
          }
          setError(msg);
          setAccounts([]);
          setTotal(0);
          setIsLoading(false);
        }
      });

    return () => {
      ignore = true;
    };
  }, [currentPage, pageSize, status, refreshIndex, apiBaseUrl]);

  const handleRefresh = () => {
    setIsLoading(true);
    setRefreshIndex((idx) => idx + 1);
  };

  // Reset page when search or status filter changes
  const handleSearchChange = (value: string) => {
    setSearch(value);
    setCurrentPage(1);
  };

  const handleStatusChange = (newStatus: string) => {
    setIsLoading(true);
    setStatus(newStatus);
    setCurrentPage(1);
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
    setIsLoading(true);
    setSearch("");
    setStatus("all");
    setCurrentPage(1);
  };

  // CRUD actions
  const handleCreateAccount = async (input: CreateAccountInput) => {
    try {
      const created = await accountService.createAccount(input);
      setBannerMessage({
        type: "success",
        text: `Account "@${created.username}" created successfully!`,
      });
      setTimeout(() => setBannerMessage(null), 5000);
      setCurrentPage(1);
      handleRefresh();
    } catch (err: unknown) {
      throw err; // Re-throw to be handled by modal
    }
  };

  const handleUpdateAccount = async (
    id: number,
    input: UpdateAccountInput
  ) => {
    try {
      const updated = await accountService.updateAccount(id, input);
      setBannerMessage({
        type: "success",
        text: `Account "@${updated.username}" updated successfully!`,
      });
      setTimeout(() => setBannerMessage(null), 5000);
      handleRefresh();
    } catch (err: unknown) {
      throw err; // Re-throw to be handled by modal
    }
  };

  const handleDeleteAccount = async (id: number) => {
    try {
      await accountService.deleteAccount(id);
      setBannerMessage({
        type: "success",
        text: `Account ID #${id} deleted successfully.`,
      });
      setTimeout(() => setBannerMessage(null), 5000);
      handleRefresh();
    } catch (err: unknown) {
      throw err; // Re-throw to be handled by dialog
    }
  };

  // Client-side search filtering across current items
  const displayedAccounts = search.trim()
    ? accounts.filter((acc) => {
        const q = search.trim().toLowerCase();
        return (
          acc.name.toLowerCase().includes(q) ||
          acc.username.toLowerCase().includes(q)
        );
      })
    : accounts;

  const isFiltered = search.trim().length > 0 || status !== "all";

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-2xl font-bold text-slate-900 tracking-tight flex items-center gap-2.5">
            <Users className="w-6 h-6 text-rose-600" />
            <span>Account Management</span>
          </h2>
          <p className="text-sm text-slate-500 mt-1">
            Connected to FastAPI backend • Real-time CRUD and state synchronization.
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
            {apiBaseUrl}
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
            <Users className="w-4 h-4" />
          </div>
          <div>
            <p className="text-[11px] font-medium text-slate-500">Total Accounts</p>
            <p className="text-lg font-bold text-slate-900">{total}</p>
          </div>
        </div>

        <div className="bg-white p-3.5 rounded-xl border border-slate-200/80 shadow-2xs flex items-center gap-3">
          <div className="p-2 rounded-lg bg-emerald-50 text-emerald-600">
            <CheckCircle2 className="w-4 h-4" />
          </div>
          <div>
            <p className="text-[11px] font-medium text-slate-500">Active</p>
            <p className="text-lg font-bold text-slate-900">
              {accounts.filter((a) => a.status === "active").length}
            </p>
          </div>
        </div>

        <div className="bg-white p-3.5 rounded-xl border border-slate-200/80 shadow-2xs flex items-center gap-3">
          <div className="p-2 rounded-lg bg-slate-100 text-slate-500">
            <PauseCircle className="w-4 h-4" />
          </div>
          <div>
            <p className="text-[11px] font-medium text-slate-500">Inactive</p>
            <p className="text-lg font-bold text-slate-900">
              {accounts.filter((a) => a.status === "inactive").length}
            </p>
          </div>
        </div>

        <div className="bg-white p-3.5 rounded-xl border border-slate-200/80 shadow-2xs flex items-center gap-3">
          <div className="p-2 rounded-lg bg-rose-50 text-rose-600">
            <AlertCircle className="w-4 h-4" />
          </div>
          <div>
            <p className="text-[11px] font-medium text-slate-500">Suspended</p>
            <p className="text-lg font-bold text-slate-900">
              {accounts.filter((a) => a.status === "suspended").length}
            </p>
          </div>
        </div>
      </div>

      {/* Main Table Card */}
      <div className="bg-white rounded-xl border border-slate-200/80 shadow-2xs overflow-hidden">
        {/* Toolbar: Search, Status Filter, Create Account Button */}
        <AccountToolbar
          search={search}
          onSearchChange={handleSearchChange}
          status={status}
          onStatusChange={handleStatusChange}
          onCreateClick={() => setIsCreateModalOpen(true)}
          apiBaseUrl={apiBaseUrl}
        />

        {/* Account Table with Edit and Delete actions */}
        <AccountTable
          accounts={displayedAccounts}
          isLoading={isLoading}
          error={error}
          onRetry={handleRefresh}
          isFiltered={isFiltered}
          onClearFilters={handleClearFilters}
          onCreateAccount={() => setIsCreateModalOpen(true)}
          onEditAccount={(acc) => setEditingAccount(acc)}
          onDeleteAccount={(acc) => setDeletingAccount(acc)}
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
        onClose={() => setIsCreateModalOpen(false)}
        onSubmit={handleCreateAccount}
      />

      {/* Edit Account Modal */}
      <AccountEditModal
        account={editingAccount}
        isOpen={editingAccount !== null}
        onClose={() => setEditingAccount(null)}
        onSubmit={handleUpdateAccount}
      />

      {/* Delete Confirmation Dialog */}
      <AccountDeleteDialog
        account={deletingAccount}
        isOpen={deletingAccount !== null}
        onClose={() => setDeletingAccount(null)}
        onConfirm={handleDeleteAccount}
      />
    </div>
  );
}

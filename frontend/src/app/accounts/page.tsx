"use client";

import React, { useState, useEffect } from "react";
import { Account, CreateAccountInput } from "@/types/account";
import { accountService, MockAccountService } from "@/services/accountService";
import { AccountToolbar } from "@/components/accounts/AccountToolbar";
import { AccountTable } from "@/components/accounts/AccountTable";
import { AccountPagination } from "@/components/accounts/AccountPagination";
import { AccountCreateModal } from "@/components/accounts/AccountCreateModal";
import { Users, CheckCircle2, PauseCircle, AlertCircle, RefreshCw } from "lucide-react";

export default function AccountsPage() {
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [total, setTotal] = useState(0);
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(5);
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("all");
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [simulateError, setSimulateError] = useState(false);
  const [successBanner, setSuccessBanner] = useState<string | null>(null);

  const [refreshIndex, setRefreshIndex] = useState(0);

  // Fetch accounts from accountService
  useEffect(() => {
    let ignore = false;

    accountService
      .getAccounts({
        page: currentPage,
        page_size: pageSize,
        status: status === "all" ? undefined : status,
        search: search || undefined,
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
          const msg =
            err instanceof Error
              ? err.message
              : "An unexpected error occurred while loading accounts.";
          setError(msg);
          setAccounts([]);
          setTotal(0);
          setIsLoading(false);
        }
      });

    return () => {
      ignore = true;
    };
  }, [currentPage, pageSize, status, search, refreshIndex]);

  const handleRefresh = () => {
    setIsLoading(true);
    setRefreshIndex((idx) => idx + 1);
  };

  // Reset page when search or status filter changes
  const handleSearchChange = (value: string) => {
    setIsLoading(true);
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

  const handleToggleSimulateError = () => {
    const nextState = !simulateError;
    setSimulateError(nextState);
    if (accountService instanceof MockAccountService) {
      accountService.setSimulateError(nextState);
    }
    handleRefresh();
  };

  const handleCreateAccount = async (input: CreateAccountInput) => {
    await accountService.createAccount(input);
    setSuccessBanner(`Account "@${input.username}" successfully added!`);
    setTimeout(() => setSuccessBanner(null), 4000);
    // Reset to page 1 and refresh
    setIsLoading(true);
    setCurrentPage(1);
    setRefreshIndex((idx) => idx + 1);
  };

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
            Monitor registered TikTok profiles, view sync health, and configure account credentials.
          </p>
        </div>

        <button
          type="button"
          onClick={handleRefresh}
          disabled={isLoading}
          className="inline-flex items-center gap-1.5 px-3 py-2 border border-slate-200 text-xs font-medium rounded-lg text-slate-700 bg-white hover:bg-slate-50 transition-colors shadow-2xs self-start sm:self-auto disabled:opacity-50"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? "animate-spin" : ""}`} />
          <span>Refresh</span>
        </button>
      </div>

      {/* Success Banner */}
      {successBanner && (
        <div className="p-3.5 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs flex items-center justify-between animate-in fade-in slide-in-from-top-2 duration-200">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
            <span className="font-medium">{successBanner}</span>
          </div>
          <button
            type="button"
            onClick={() => setSuccessBanner(null)}
            className="text-emerald-700 hover:text-emerald-900 font-bold ml-2"
          >
            &times;
          </button>
        </div>
      )}

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
        {/* Toolbar: Search, Status Filter, Create Account Button, Simulated Error */}
        <AccountToolbar
          search={search}
          onSearchChange={handleSearchChange}
          status={status}
          onStatusChange={handleStatusChange}
          onCreateClick={() => setIsCreateModalOpen(true)}
          simulateError={simulateError}
          onToggleSimulateError={handleToggleSimulateError}
        />

        {/* Account Table */}
        <AccountTable
          accounts={accounts}
          isLoading={isLoading}
          error={error}
          onRetry={handleRefresh}
          isFiltered={isFiltered}
          onClearFilters={handleClearFilters}
          onCreateAccount={() => setIsCreateModalOpen(true)}
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
    </div>
  );
}

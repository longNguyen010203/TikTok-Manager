"use client";
import { useEffect, useState, useRef, useCallback } from "react";
import {
  AlertCircle,
  FileUp,
  FolderOpen,
  Layers,
  Loader2,
  Plus,
  Search,
} from "lucide-react";
import { ContentCard } from "@/components/content/ContentCard";
import { ContentToolbar } from "@/components/content/ContentToolbar";
import { ContentPagination } from "@/components/content/ContentPagination";
import { ContentUploadModal } from "@/components/content/ContentUploadModal";
import { ContentDetailModal } from "@/components/content/ContentDetailModal";
import { ContentDeliverModal } from "@/components/content/ContentDeliverModal";
import { ContentDeleteModal } from "@/components/content/ContentDeleteModal";
import { JobDetailModal } from "@/components/jobs/JobDetailModal";
import { contentService } from "@/services/contentService";
import { accountService } from "@/services/accountService";
import { runtimeService } from "@/services/runtimeService";
import {
  ContentAsset,
  ContentAssetDetail,
  ContentAssetStatus,
  ContentAssetType,
} from "@/types/content";
import { Account, formatApiError } from "@/types/account";
import { Runtime } from "@/types/runtime";

export default function ContentPage() {
  const [assets, setAssets] = useState<ContentAsset[]>([]);
  const [total, setTotal] = useState(0);
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Filters
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedType, setSelectedType] = useState<ContentAssetType | "all">("all");
  const [selectedStatus, setSelectedStatus] = useState<ContentAssetStatus | "active">("active");
  const [tagFilter, setTagFilter] = useState("");
  const [refreshIndex, setRefreshIndex] = useState(0);

  // Modal States
  const [isUploadOpen, setIsUploadOpen] = useState(false);
  const [selectedAssetId, setSelectedAssetId] = useState<number | null>(null);
  const [assetForDelivery, setAssetForDelivery] = useState<ContentAssetDetail | null>(null);
  const [assetForDelete, setAssetForDelete] = useState<ContentAssetDetail | null>(null);
  const [inspectJobId, setInspectJobId] = useState<number | null>(null);

  // References for JobDetailModal
  const [accountsMap, setAccountsMap] = useState<Record<number, Account>>({});
  const [runtimesMap, setRuntimesMap] = useState<Record<number, Runtime>>({});

  // Background polling for processing assets
  const pollTimerRef = useRef<NodeJS.Timeout | null>(null);

  const stopPolling = useCallback(() => {
    if (pollTimerRef.current) {
      clearInterval(pollTimerRef.current);
      pollTimerRef.current = null;
    }
  }, []);

  // Load content assets
  useEffect(() => {
    let ignore = false;
    contentService
      .listContent({
        page: currentPage,
        page_size: pageSize,
        query: searchQuery.trim() || undefined,
        asset_type: selectedType !== "all" ? selectedType : undefined,
        status: selectedStatus !== "active" ? selectedStatus : undefined,
        tag: tagFilter.trim() || undefined,
      })
      .then((result) => {
        if (ignore) return;
        setAssets(result.items);
        setTotal(result.total);
        setError(null);
      })
      .catch((err) => {
        if (ignore) return;
        setError(formatApiError(err));
      })
      .finally(() => {
        if (!ignore) setIsLoading(false);
      });

    return () => {
      ignore = true;
    };
  }, [
    currentPage,
    pageSize,
    searchQuery,
    selectedType,
    selectedStatus,
    tagFilter,
    refreshIndex,
  ]);

  // Load account/runtime maps for JobDetailModal when a job is inspected
  useEffect(() => {
    if (inspectJobId) {
      Promise.all([
        accountService.getAccounts({ page_size: 100 }),
        runtimeService.getRuntimes({ page_size: 100 }),
      ])
        .then(([accRes, runRes]) => {
          const accs: Record<number, Account> = {};
          for (const a of accRes.items) accs[a.id] = a;
          setAccountsMap(accs);

          const runs: Record<number, Runtime> = {};
          for (const r of runRes.items) runs[r.id] = r;
          setRuntimesMap(runs);
        })
        .catch(() => {});
    }
  }, [inspectJobId]);

  // Auto-polling when any asset on current page is processing
  useEffect(() => {
    const hasProcessing = assets.some((a) => a.status === "processing");

    if (hasProcessing) {
      stopPolling();
      pollTimerRef.current = setInterval(async () => {
        try {
          const result = await contentService.listContent({
            page: currentPage,
            page_size: pageSize,
            query: searchQuery.trim() || undefined,
            asset_type: selectedType !== "all" ? selectedType : undefined,
            status: selectedStatus !== "active" ? selectedStatus : undefined,
            tag: tagFilter.trim() || undefined,
          });
          setAssets(result.items);
          setTotal(result.total);

          const stillProcessing = result.items.some(
            (a) => a.status === "processing"
          );
          if (!stillProcessing) {
            stopPolling();
          }
        } catch {
          // ignore background poll errors
        }
      }, 2000);
    } else {
      stopPolling();
    }

    return () => stopPolling();
  }, [assets, currentPage, pageSize, searchQuery, selectedType, selectedStatus, tagFilter, stopPolling]);

  // Handlers
  const handleUploadSuccess = (newAsset: ContentAssetDetail) => {
    setIsUploadOpen(false);
    setRefreshIndex((v) => v + 1);
    setSelectedAssetId(newAsset.id);
  };

  const handleDeliverRequested = async (asset: ContentAsset | ContentAssetDetail) => {
    try {
      const detail = await contentService.getContent(asset.id);
      setAssetForDelivery(detail);
    } catch {
      // fallback
    }
  };

  const handleDeleteRequested = (asset: ContentAssetDetail) => {
    setAssetForDelete(asset);
  };

  const handleDeleteSuccess = () => {
    setSelectedAssetId(null);
    setAssetForDelete(null);
    setRefreshIndex((v) => v + 1);
  };

  // Stats calculation
  const readyCount = assets.filter((a) => a.status === "ready").length;
  const processingCount = assets.filter((a) => a.status === "processing").length;
  const archivedCount = assets.filter((a) => a.status === "archived").length;

  return (
    <div className="space-y-6">
        {/* Page Header */}
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h1 className="text-2xl font-bold tracking-tight text-slate-900">
              Content Library
            </h1>
            <p className="mt-1 text-sm text-slate-500">
              Manage, inspect, and deliver reusable media assets across Redroid devices
            </p>
          </div>

          {/* Quick Header Stats */}
          <div className="flex flex-wrap items-center gap-2">
            <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl border border-slate-200 bg-white text-xs font-semibold text-slate-700 shadow-2xs">
              <Layers className="w-3.5 h-3.5 text-blue-600" />
              <span>{total} Total Assets</span>
            </span>

            {readyCount > 0 && (
              <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl border border-emerald-200 bg-emerald-50 text-xs font-semibold text-emerald-800 shadow-2xs">
                <span>{readyCount} Ready</span>
              </span>
            )}

            {processingCount > 0 && (
              <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl border border-amber-200 bg-amber-50 text-xs font-semibold text-amber-800 shadow-2xs">
                <Loader2 className="w-3.5 h-3.5 text-amber-600 animate-spin" />
                <span>{processingCount} Processing</span>
              </span>
            )}

            {archivedCount > 0 && (
              <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl border border-slate-200 bg-slate-100 text-xs font-semibold text-slate-700 shadow-2xs">
                <span>{archivedCount} Archived</span>
              </span>
            )}

            <button
              type="button"
              onClick={() => setIsUploadOpen(true)}
              className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl bg-blue-600 text-xs font-semibold text-white shadow-2xs hover:bg-blue-700 transition-colors ml-auto sm:ml-0"
            >
              <Plus className="w-4 h-4" />
              <span>Upload Content</span>
            </button>
          </div>
        </div>

        {/* Search & Filters Toolbar */}
        <ContentToolbar
          searchQuery={searchQuery}
          onSearchChange={(val) => {
            setSearchQuery(val);
            setCurrentPage(1);
          }}
          selectedType={selectedType}
          onTypeChange={(val) => {
            setSelectedType(val);
            setCurrentPage(1);
          }}
          selectedStatus={selectedStatus}
          onStatusChange={(val) => {
            setSelectedStatus(val);
            setCurrentPage(1);
          }}
          tagFilter={tagFilter}
          onTagFilterChange={(val) => {
            setTagFilter(val);
            setCurrentPage(1);
          }}
          onUploadClick={() => setIsUploadOpen(true)}
          onRefresh={() => setRefreshIndex((v) => v + 1)}
          isLoading={isLoading}
        />

        {/* Error Banner */}
        {error && (
          <div className="rounded-xl border border-rose-200 bg-rose-50/80 p-4 flex items-start gap-3 text-xs text-rose-800">
            <AlertCircle className="w-5 h-5 text-rose-600 shrink-0 mt-0.5" />
            <div className="flex-1">
              <h4 className="font-bold text-sm">Failed to Load Content</h4>
              <p className="mt-0.5">{error}</p>
            </div>
            <button
              type="button"
              onClick={() => setRefreshIndex((v) => v + 1)}
              className="px-3 py-1.5 rounded-lg border border-rose-300 bg-white font-semibold text-rose-700 hover:bg-rose-50 transition-colors"
            >
              Retry
            </button>
          </div>
        )}

        {/* Content Assets Grid / States */}
        {isLoading ? (
          /* Loading Skeletons */
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
            {Array.from({ length: 8 }).map((_, i) => (
              <div
                key={i}
                className="animate-pulse rounded-xl border border-slate-200 bg-white overflow-hidden space-y-3 p-3 shadow-2xs"
              >
                <div className="aspect-video w-full rounded-lg bg-slate-100" />
                <div className="h-4 w-3/4 rounded bg-slate-100" />
                <div className="h-3 w-1/2 rounded bg-slate-100" />
                <div className="h-3 w-1/4 rounded bg-slate-100" />
              </div>
            ))}
          </div>
        ) : assets.length === 0 ? (
          /* Empty / No Results State */
          <div className="rounded-2xl border border-dashed border-slate-300 bg-white p-12 text-center shadow-2xs">
            {searchQuery ||
            selectedType !== "all" ||
            selectedStatus !== "active" ||
            tagFilter ? (
              <div className="space-y-3 max-w-sm mx-auto">
                <Search className="w-10 h-10 text-slate-300 mx-auto" />
                <h3 className="text-sm font-bold text-slate-800">
                  No matching content found
                </h3>
                <p className="text-xs text-slate-500">
                  Try adjusting your search query, type, status, or tag filters.
                </p>
                <button
                  type="button"
                  onClick={() => {
                    setSearchQuery("");
                    setSelectedType("all");
                    setSelectedStatus("active");
                    setTagFilter("");
                  }}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-slate-200 text-xs font-semibold text-slate-700 hover:bg-slate-50"
                >
                  Clear all filters
                </button>
              </div>
            ) : (
              <div className="space-y-4 max-w-sm mx-auto">
                <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-blue-50 text-blue-600 mx-auto border border-blue-200">
                  <FolderOpen className="w-7 h-7" />
                </div>
                <div>
                  <h3 className="text-base font-bold text-slate-900">
                    Your Content Library is Empty
                  </h3>
                  <p className="text-xs text-slate-500 mt-1">
                    Upload images, videos, or audio to inspect their metadata and deliver them directly into Android device galleries.
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => setIsUploadOpen(true)}
                  className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl bg-blue-600 text-xs font-semibold text-white shadow-2xs hover:bg-blue-700 transition-colors"
                >
                  <FileUp className="w-4 h-4" />
                  <span>Upload First Media Asset</span>
                </button>
              </div>
            )}
          </div>
        ) : (
          /* Cards Grid & Pagination */
          <div className="space-y-4">
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
              {assets.map((asset) => (
                <ContentCard
                  key={asset.id}
                  asset={asset}
                  onSelect={(a) => setSelectedAssetId(a.id)}
                  onDeliver={(a) => handleDeliverRequested(a)}
                />
              ))}
            </div>

            {/* Pagination Controls */}
            {total > pageSize && (
              <div className="rounded-xl border border-slate-200 bg-white overflow-hidden shadow-2xs">
                <ContentPagination
                  currentPage={currentPage}
                  pageSize={pageSize}
                  total={total}
                  onPageChange={(p) => setCurrentPage(p)}
                  onPageSizeChange={(s) => {
                    setPageSize(s);
                    setCurrentPage(1);
                  }}
                />
              </div>
            )}
          </div>
        )}

        {/* Upload Modal */}
        <ContentUploadModal
          isOpen={isUploadOpen}
          onClose={() => setIsUploadOpen(false)}
          onUploadSuccess={handleUploadSuccess}
        />

        {/* Content Detail Modal */}
        {selectedAssetId !== null && (
          <ContentDetailModal
            contentId={selectedAssetId}
            isOpen={selectedAssetId !== null}
            onClose={() => setSelectedAssetId(null)}
            onAssetUpdated={() => setRefreshIndex((v) => v + 1)}
            onDeliver={(a) => setAssetForDelivery(a)}
            onDeleteRequested={(a) => handleDeleteRequested(a)}
            onOpenJob={(jobId) => setInspectJobId(jobId)}
          />
        )}

        {/* Deliver to Runtime Modal */}
        {assetForDelivery && (
          <ContentDeliverModal
            isOpen={Boolean(assetForDelivery)}
            asset={assetForDelivery}
            onClose={() => setAssetForDelivery(null)}
            onDeliveryComplete={() => setRefreshIndex((v) => v + 1)}
            onOpenJob={(jobId) => setInspectJobId(jobId)}
          />
        )}

        {/* Delete Confirmation Modal */}
        {assetForDelete && (
          <ContentDeleteModal
            isOpen={Boolean(assetForDelete)}
            asset={assetForDelete}
            onClose={() => setAssetForDelete(null)}
            onDeleteSuccess={handleDeleteSuccess}
          />
        )}

        {/* Job Detail Modal (Integration when clicking job link) */}
        {inspectJobId !== null && (
          <JobDetailModal
            jobId={inspectJobId}
            accountsMap={accountsMap}
            runtimesMap={runtimesMap}
            onClose={() => setInspectJobId(null)}
            onQueueRefresh={() => {}}
          />
        )}
    </div>
  );
}

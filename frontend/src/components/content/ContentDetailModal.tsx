import { useState, useEffect, useRef, useCallback } from "react";
import {
  AlertCircle,
  Archive,
  ArchiveRestore,
  ChevronDown,
  ChevronRight,
  Cpu,
  Download,
  Edit2,
  ExternalLink,
  FileCode,
  FileUp,
  Film,
  Image as ImageIcon,
  Loader2,
  Music,
  RefreshCw,
  Send,
  Sparkles,
  Tag,
  Trash2,
  X,
} from "lucide-react";
import { contentService } from "@/services/contentService";
import {
  ContentAssetDetail,
  ContentDelivery,
  formatDuration,
  formatFileSize,
  getContentErrorMessage,
} from "@/types/content";
import { ContentStatusBadge } from "./ContentStatusBadge";
import { ContentDeliveryBadge } from "./ContentDeliveryBadge";

interface ContentDetailModalProps {
  contentId: number;
  isOpen: boolean;
  onClose: () => void;
  onAssetUpdated: (updated: ContentAssetDetail) => void;
  onDeliver: (asset: ContentAssetDetail) => void;
  onDeleteRequested: (asset: ContentAssetDetail) => void;
  onOpenJob?: (jobId: number) => void;
}

export function ContentDetailModal({
  contentId,
  isOpen,
  onClose,
  onAssetUpdated,
  onDeliver,
  onDeleteRequested,
  onOpenJob,
}: ContentDetailModalProps) {
  const [asset, setAsset] = useState<ContentAssetDetail | null>(null);
  const [deliveries, setDeliveries] = useState<ContentDelivery[]>([]);
  const [loading, setLoading] = useState(true);
  const [deliveriesLoading, setDeliveriesLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<"overview" | "versions" | "deliveries">("overview");

  // Expandable technical metadata
  const [showTechnicalDetails, setShowTechnicalDetails] = useState(false);

  // Edit metadata state
  const [isEditing, setIsEditing] = useState(false);
  const [editName, setEditName] = useState("");
  const [editNotes, setEditNotes] = useState("");
  const [editTagInput, setEditTagInput] = useState("");
  const [editTags, setEditTags] = useState<string[]>([]);
  const [isSavingEdit, setIsSavingEdit] = useState(false);

  // Replacement version upload state
  const [isUploadingVersion, setIsUploadingVersion] = useState(false);
  const [versionUploadError, setVersionUploadError] = useState<string | null>(null);
  const versionFileInputRef = useRef<HTMLInputElement | null>(null);

  // Polling ref for processing assets
  const pollTimerRef = useRef<NodeJS.Timeout | null>(null);

  const stopPolling = useCallback(() => {
    if (pollTimerRef.current) {
      clearInterval(pollTimerRef.current);
      pollTimerRef.current = null;
    }
  }, []);

  const loadDeliveries = useCallback(async (id: number) => {
    setDeliveriesLoading(true);
    try {
      const res = await contentService.listDeliveries(id, { page_size: 50 });
      setDeliveries(res.items);
    } catch {
      // deliveries fallback to empty
    } finally {
      setDeliveriesLoading(false);
    }
  }, []);

  // Initial load
  useEffect(() => {
    if (!isOpen || !contentId) {
      stopPolling();
      return;
    }

    let ignore = false;
    contentService
      .getContent(contentId)
      .then((loaded) => {
        if (ignore) return;
        setAsset(loaded);
        setError(null);
        setEditName(loaded.display_name);
        setEditNotes(loaded.notes || "");
        setEditTags(loaded.tags || []);
      })
      .catch((err) => {
        if (ignore) return;
        setError(err instanceof Error ? err.message : String(err));
      })
      .finally(() => {
        if (!ignore) setLoading(false);
      });

    contentService
      .listDeliveries(contentId, { page_size: 50 })
      .then((res) => {
        if (ignore) return;
        setDeliveries(res.items);
      })
      .catch(() => {})
      .finally(() => {
        if (!ignore) setDeliveriesLoading(false);
      });

    return () => {
      ignore = true;
    };
  }, [isOpen, contentId, stopPolling]);

  // Polling when asset or any version is in "processing" state
  const isProcessing =
    asset?.status === "processing" ||
    Boolean(asset?.versions.some((v) => v.processing_status === "processing"));

  useEffect(() => {
    if (!isOpen || !contentId || !isProcessing) {
      stopPolling();
      return;
    }

    stopPolling();
    pollTimerRef.current = setInterval(() => {
      contentService
        .getContent(contentId)
        .then((refreshed) => {
          setAsset(refreshed);
          onAssetUpdated(refreshed);
          const stillProcessing =
            refreshed.status === "processing" ||
            refreshed.versions.some((v) => v.processing_status === "processing");
          if (!stillProcessing) {
            stopPolling();
          }
        })
        .catch(() => {});
    }, 2000);

    return () => stopPolling();
  }, [isOpen, contentId, isProcessing, onAssetUpdated, stopPolling]);

  // Escape key handler
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && isOpen && !isSavingEdit && !isUploadingVersion) {
        stopPolling();
        onClose();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, isSavingEdit, isUploadingVersion, onClose, stopPolling]);

  if (!isOpen) return null;

  const currentVersion = asset?.current_version;
  const isReady =
    asset?.status === "ready" && currentVersion?.processing_status === "ready";
  const downloadUrl = asset ? contentService.getDownloadUrl(asset.id) : "";

  // Archive / Restore toggle
  const handleToggleArchive = async () => {
    if (!asset) return;
    const newArchived = asset.status !== "archived";
    try {
      const updated = await contentService.patchContent(asset.id, {
        archived: newArchived,
      });
      setAsset(updated);
      onAssetUpdated(updated);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  };

  // Save metadata edit
  const handleSaveEdit = async () => {
    if (!asset || !editName.trim()) return;
    setIsSavingEdit(true);
    try {
      const updated = await contentService.patchContent(asset.id, {
        display_name: editName.trim(),
        notes: editNotes.trim() || null,
        tags: editTags,
      });
      setAsset(updated);
      setIsEditing(false);
      onAssetUpdated(updated);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setIsSavingEdit(false);
    }
  };

  const handleAddEditTag = () => {
    const cleaned = editTagInput.trim().toLowerCase().replace(/[^a-z0-9_-]/g, "");
    if (cleaned && !editTags.includes(cleaned)) {
      setEditTags([...editTags, cleaned]);
      setEditTagInput("");
    }
  };

  const handleRemoveEditTag = (tagToRemove: string) => {
    setEditTags(editTags.filter((t) => t !== tagToRemove));
  };

  // Upload replacement media version (Requirement 12)
  const handleVersionFileSelected = async (file: File) => {
    if (!asset) return;
    setIsUploadingVersion(true);
    setVersionUploadError(null);

    try {
      const updated = await contentService.uploadVersion(asset.id, file);
      setAsset(updated);
      onAssetUpdated(updated);
      setActiveTab("versions");
    } catch (err) {
      setVersionUploadError(err instanceof Error ? err.message : String(err));
    } finally {
      setIsUploadingVersion(false);
      if (versionFileInputRef.current) {
        versionFileInputRef.current.value = "";
      }
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-xs animate-in fade-in duration-150">
      <div
        className="w-full max-w-4xl rounded-2xl bg-white shadow-2xl border border-slate-200 overflow-hidden flex flex-col max-h-[92vh]"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between border-b border-slate-200 px-6 py-4 bg-slate-50/80">
          <div className="flex items-center gap-3 min-w-0">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-blue-50 text-blue-600 border border-blue-200">
              {asset?.asset_type === "video" ? (
                <Film className="w-5 h-5" />
              ) : asset?.asset_type === "audio" ? (
                <Music className="w-5 h-5" />
              ) : (
                <ImageIcon className="w-5 h-5" />
              )}
            </div>
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <h2 className="text-base font-bold text-slate-900 truncate">
                  {asset?.display_name || "Content Asset Details"}
                </h2>
                {asset && <ContentStatusBadge status={asset.status} size="sm" />}
              </div>
              <p className="text-xs text-slate-500 font-mono mt-0.5 truncate">
                Asset #{asset?.id} • {asset?.asset_type.toUpperCase()} • v
                {currentVersion?.version_number || 1}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={onClose}
              className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-200 hover:text-slate-600 transition-colors"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Action Toolbar */}
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-200 px-6 py-2.5 bg-white text-xs">
          <div className="flex items-center gap-2">
            {/* Deliver CTA */}
            {asset && isReady && (
              <button
                type="button"
                onClick={() => onDeliver(asset)}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-blue-600 text-white font-semibold shadow-2xs hover:bg-blue-700 transition-colors"
              >
                <Send className="w-3.5 h-3.5" />
                <span>Deliver to Runtime</span>
              </button>
            )}

            {/* Download CTA (Requirement 7) */}
            {isReady ? (
              <a
                href={downloadUrl}
                download={currentVersion?.original_filename || "content-file"}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-slate-200 bg-white text-slate-700 font-semibold hover:bg-slate-50 transition-colors"
              >
                <Download className="w-3.5 h-3.5 text-slate-500" />
                <span>Download Media</span>
              </a>
            ) : (
              <button
                type="button"
                disabled
                title="Download is only available when the asset has a ready version"
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-slate-200 bg-slate-100 text-slate-400 font-medium cursor-not-allowed opacity-60"
              >
                <Download className="w-3.5 h-3.5" />
                <span>Download Unavailable</span>
              </button>
            )}

            {/* Edit Metadata CTA */}
            {asset && !isEditing && asset.status !== "deleted" && (
              <button
                type="button"
                onClick={() => setIsEditing(true)}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-slate-200 bg-white text-slate-700 font-semibold hover:bg-slate-50 transition-colors"
              >
                <Edit2 className="w-3.5 h-3.5 text-slate-500" />
                <span>Edit Info</span>
              </button>
            )}
          </div>

          <div className="flex items-center gap-2">
            {/* Archive / Restore Button (Requirement 9) */}
            {asset && asset.status !== "deleted" && (
              <button
                type="button"
                onClick={handleToggleArchive}
                className="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg border border-slate-200 text-slate-600 hover:bg-slate-50 font-medium transition-colors"
              >
                {asset.status === "archived" ? (
                  <>
                    <ArchiveRestore className="w-3.5 h-3.5 text-emerald-600" />
                    <span>Restore Asset</span>
                  </>
                ) : (
                  <>
                    <Archive className="w-3.5 h-3.5 text-slate-500" />
                    <span>Archive</span>
                  </>
                )}
              </button>
            )}

            {/* Delete Button (Requirement 9) */}
            {asset && asset.status !== "deleted" && (
              <button
                type="button"
                onClick={() => onDeleteRequested(asset)}
                className="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg border border-rose-200 bg-rose-50/50 text-rose-700 hover:bg-rose-100 font-medium transition-colors"
              >
                <Trash2 className="w-3.5 h-3.5 text-rose-600" />
                <span>Delete</span>
              </button>
            )}
          </div>
        </div>

        {/* Modal Tabs */}
        <div className="flex items-center border-b border-slate-200 px-6 bg-slate-50/60 text-xs font-semibold">
          <button
            type="button"
            onClick={() => setActiveTab("overview")}
            className={`py-3 px-3 border-b-2 transition-colors ${
              activeTab === "overview"
                ? "border-blue-600 text-blue-600"
                : "border-transparent text-slate-500 hover:text-slate-800"
            }`}
          >
            Overview &amp; Preview
          </button>
          <button
            type="button"
            onClick={() => setActiveTab("versions")}
            className={`py-3 px-3 border-b-2 transition-colors flex items-center gap-1.5 ${
              activeTab === "versions"
                ? "border-blue-600 text-blue-600"
                : "border-transparent text-slate-500 hover:text-slate-800"
            }`}
          >
            <span>Version History</span>
            <span className="rounded-full bg-slate-200 px-1.5 py-0.2 text-[10px] text-slate-700">
              {asset?.versions.length || 0}
            </span>
          </button>
          <button
            type="button"
            onClick={() => setActiveTab("deliveries")}
            className={`py-3 px-3 border-b-2 transition-colors flex items-center gap-1.5 ${
              activeTab === "deliveries"
                ? "border-blue-600 text-blue-600"
                : "border-transparent text-slate-500 hover:text-slate-800"
            }`}
          >
            <span>Delivery History</span>
            <span className="rounded-full bg-slate-200 px-1.5 py-0.2 text-[10px] text-slate-700">
              {deliveries.length}
            </span>
          </button>
        </div>

        {/* Body Container */}
        <div className="overflow-y-auto p-6 flex-1 space-y-5">
          {error && (
            <div className="rounded-xl border border-rose-200 bg-rose-50/80 p-3.5 flex items-start gap-2.5 text-xs text-rose-800">
              <AlertCircle className="w-4 h-4 text-rose-600 shrink-0 mt-0.5" />
              <span>{error}</span>
            </div>
          )}

          {loading ? (
            <div className="animate-pulse space-y-4">
              <div className="h-64 rounded-xl bg-slate-100" />
              <div className="grid grid-cols-2 gap-4">
                <div className="h-20 rounded-xl bg-slate-100" />
                <div className="h-20 rounded-xl bg-slate-100" />
              </div>
            </div>
          ) : !asset ? (
            <div className="p-8 text-center text-slate-500 text-xs">
              Unable to load content details.
            </div>
          ) : (
            <>
              {/* TAB 1: OVERVIEW & PREVIEW */}
              {activeTab === "overview" && (
                <div className="space-y-6">
                  {/* Media Preview Box (Requirement 6) */}
                  <div className="rounded-2xl overflow-hidden border border-slate-200 bg-slate-950 flex flex-col items-center justify-center min-h-64 max-h-[420px] relative">
                    {asset.status === "processing" ? (
                      <div className="p-10 text-center text-amber-400 space-y-3">
                        <Sparkles className="w-12 h-12 mx-auto animate-pulse text-amber-400" />
                        <div>
                          <p className="font-bold text-sm text-amber-300">
                            Media Inspection in Progress
                          </p>
                          <p className="text-xs text-slate-400 mt-1 max-w-sm">
                            Extracting resolution, codec, duration, and computing cryptographic checksums...
                          </p>
                        </div>
                      </div>
                    ) : asset.status === "invalid" ? (
                      <div className="p-10 text-center text-rose-400 space-y-2">
                        <AlertCircle className="w-12 h-12 mx-auto text-rose-500" />
                        <p className="font-bold text-sm text-rose-300">
                          Media Validation Failed
                        </p>
                        <p className="text-xs text-slate-400 max-w-md">
                          {getContentErrorMessage(
                            currentVersion?.error_code,
                            currentVersion?.error_message
                          )}
                        </p>
                      </div>
                    ) : asset.status === "deleted" ? (
                      <div className="p-10 text-center text-slate-500 space-y-2">
                        <Trash2 className="w-12 h-12 mx-auto text-slate-600" />
                        <p className="font-semibold text-xs text-slate-400">
                          This asset has been soft-deleted
                        </p>
                      </div>
                    ) : asset.asset_type === "image" && isReady ? (
                      // eslint-disable-next-line @next/next/no-img-element
                      <img
                        src={downloadUrl}
                        alt={asset.display_name}
                        className="max-h-[400px] w-auto object-contain mx-auto"
                      />
                    ) : asset.asset_type === "video" && isReady ? (
                      <video
                        controls
                        src={downloadUrl}
                        className="max-h-[400px] w-full object-contain mx-auto"
                      >
                        Your browser does not support HTML5 video preview.
                      </video>
                    ) : asset.asset_type === "audio" && isReady ? (
                      <div className="p-10 text-center w-full max-w-md space-y-4">
                        <Music className="w-16 h-16 text-amber-400 mx-auto opacity-80" />
                        <audio controls src={downloadUrl} className="w-full">
                          Your browser does not support audio playback.
                        </audio>
                      </div>
                    ) : (
                      <div className="p-10 text-center text-slate-400 text-xs">
                        No preview available
                      </div>
                    )}
                  </div>

                  {/* Edit Metadata Inline Form (Requirement 8) */}
                  {isEditing ? (
                    <div className="rounded-xl border border-blue-200 bg-blue-50/40 p-4 space-y-3 text-xs">
                      <div className="flex items-center justify-between font-bold text-blue-900">
                        <span>Edit Content Metadata</span>
                        <button
                          type="button"
                          onClick={() => setIsEditing(false)}
                          className="text-slate-400 hover:text-slate-600"
                        >
                          <X className="w-4 h-4" />
                        </button>
                      </div>

                      <div className="space-y-1">
                        <label className="font-semibold text-slate-700">
                          Display Name
                        </label>
                        <input
                          type="text"
                          value={editName}
                          onChange={(e) => setEditName(e.target.value)}
                          className="w-full rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-xs text-slate-800 focus:border-blue-500 focus:outline-hidden"
                        />
                      </div>

                      <div className="space-y-1">
                        <label className="font-semibold text-slate-700">
                          Notes
                        </label>
                        <textarea
                          value={editNotes}
                          onChange={(e) => setEditNotes(e.target.value)}
                          rows={2}
                          className="w-full rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-xs text-slate-800 focus:border-blue-500 focus:outline-hidden resize-none"
                        />
                      </div>

                      <div className="space-y-1">
                        <label className="font-semibold text-slate-700">
                          Tags
                        </label>
                        <div className="flex gap-2">
                          <input
                            type="text"
                            value={editTagInput}
                            onChange={(e) => setEditTagInput(e.target.value)}
                            onKeyDown={(e) => {
                              if (e.key === "Enter" || e.key === ",") {
                                e.preventDefault();
                                handleAddEditTag();
                              }
                            }}
                            placeholder="Add tag and press Enter"
                            className="flex-1 rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-xs text-slate-800 focus:border-blue-500 focus:outline-hidden"
                          />
                          <button
                            type="button"
                            onClick={handleAddEditTag}
                            className="px-3 py-1.5 rounded-lg border border-slate-200 bg-white font-semibold text-slate-700 hover:bg-slate-50"
                          >
                            Add
                          </button>
                        </div>
                        {editTags.length > 0 && (
                          <div className="flex flex-wrap gap-1 pt-1">
                            {editTags.map((t) => (
                              <span
                                key={t}
                                className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-blue-100 text-blue-800 text-[11px]"
                              >
                                <span>{t}</span>
                                <button
                                  type="button"
                                  onClick={() => handleRemoveEditTag(t)}
                                >
                                  <X className="w-3 h-3" />
                                </button>
                              </span>
                            ))}
                          </div>
                        )}
                      </div>

                      <div className="flex justify-end gap-2 pt-2">
                        <button
                          type="button"
                          onClick={() => setIsEditing(false)}
                          disabled={isSavingEdit}
                          className="px-3 py-1.5 rounded-lg border border-slate-200 text-slate-600 hover:bg-white"
                        >
                          Cancel
                        </button>
                        <button
                          type="button"
                          onClick={handleSaveEdit}
                          disabled={isSavingEdit || !editName.trim()}
                          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-blue-600 text-white font-semibold hover:bg-blue-700 disabled:opacity-50"
                        >
                          {isSavingEdit ? (
                            <>
                              <Loader2 className="w-3 h-3 animate-spin" />
                              <span>Saving...</span>
                            </>
                          ) : (
                            <span>Save Changes</span>
                          )}
                        </button>
                      </div>
                    </div>
                  ) : null}

                  {/* Primary Metadata Grid (Requirement 5) */}
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
                    <div className="p-3 rounded-xl border border-slate-200 bg-slate-50/70">
                      <span className="text-[10px] font-semibold uppercase tracking-wider text-slate-400 block mb-1">
                        Dimensions
                      </span>
                      <span className="font-semibold text-slate-800 font-mono">
                        {currentVersion?.width && currentVersion?.height
                          ? `${currentVersion.width} × ${currentVersion.height}`
                          : "—"}
                      </span>
                    </div>

                    <div className="p-3 rounded-xl border border-slate-200 bg-slate-50/70">
                      <span className="text-[10px] font-semibold uppercase tracking-wider text-slate-400 block mb-1">
                        Duration
                      </span>
                      <span className="font-semibold text-slate-800 font-mono">
                        {formatDuration(currentVersion?.duration_ms)}
                      </span>
                    </div>

                    <div className="p-3 rounded-xl border border-slate-200 bg-slate-50/70">
                      <span className="text-[10px] font-semibold uppercase tracking-wider text-slate-400 block mb-1">
                        File Size
                      </span>
                      <span className="font-semibold text-slate-800">
                        {formatFileSize(currentVersion?.size_bytes)}
                      </span>
                    </div>

                    <div className="p-3 rounded-xl border border-slate-200 bg-slate-50/70">
                      <span className="text-[10px] font-semibold uppercase tracking-wider text-slate-400 block mb-1">
                        Format / MIME
                      </span>
                      <span className="font-semibold text-slate-800 font-mono text-[11px] truncate block">
                        {currentVersion?.detected_mime_type || "—"}
                      </span>
                    </div>
                  </div>

                  {/* Notes & Tags Row */}
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs">
                    <div className="p-3.5 rounded-xl border border-slate-200 bg-white space-y-1">
                      <span className="text-[10px] font-semibold uppercase tracking-wider text-slate-400 block">
                        Notes &amp; Description
                      </span>
                      <p className="text-slate-700 text-xs whitespace-pre-wrap leading-relaxed">
                        {asset.notes || (
                          <span className="italic text-slate-400">
                            No notes added for this content.
                          </span>
                        )}
                      </p>
                    </div>

                    <div className="p-3.5 rounded-xl border border-slate-200 bg-white space-y-2">
                      <span className="text-[10px] font-semibold uppercase tracking-wider text-slate-400 block">
                        Tags ({asset.tags.length})
                      </span>
                      {asset.tags.length > 0 ? (
                        <div className="flex flex-wrap gap-1.5">
                          {asset.tags.map((t) => (
                            <span
                              key={t}
                              className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-slate-100 text-slate-700 text-xs font-medium"
                            >
                              <Tag className="w-2.5 h-2.5 text-slate-400" />
                              <span>{t}</span>
                            </span>
                          ))}
                        </div>
                      ) : (
                        <p className="italic text-slate-400 text-xs">
                          No tags assigned.
                        </p>
                      )}
                    </div>
                  </div>

                  {/* Expandable Technical Diagnostics Panel (Requirement 5 & 23) */}
                  <div className="rounded-xl border border-slate-200 bg-white overflow-hidden">
                    <button
                      type="button"
                      onClick={() => setShowTechnicalDetails(!showTechnicalDetails)}
                      className="w-full flex items-center justify-between p-3.5 text-left bg-slate-50/70 hover:bg-slate-100 transition-colors text-xs font-semibold text-slate-700"
                    >
                      <div className="flex items-center gap-2">
                        <FileCode className="w-4 h-4 text-slate-500" />
                        <span>Technical Media Properties</span>
                      </div>
                      {showTechnicalDetails ? (
                        <ChevronDown className="w-4 h-4 text-slate-400" />
                      ) : (
                        <ChevronRight className="w-4 h-4 text-slate-400" />
                      )}
                    </button>

                    {showTechnicalDetails && (
                      <div className="p-4 border-t border-slate-200 bg-slate-50/30 grid grid-cols-2 sm:grid-cols-3 gap-3 text-xs font-mono">
                        <div>
                          <span className="text-slate-400 block text-[10px] font-sans uppercase">
                            Codec
                          </span>
                          <span className="text-slate-800">
                            {currentVersion?.codec || "None / N/A"}
                          </span>
                        </div>
                        <div>
                          <span className="text-slate-400 block text-[10px] font-sans uppercase">
                            Container
                          </span>
                          <span className="text-slate-800">
                            {currentVersion?.container || "None / N/A"}
                          </span>
                        </div>
                        <div>
                          <span className="text-slate-400 block text-[10px] font-sans uppercase">
                            Audio Track
                          </span>
                          <span className="text-slate-800">
                            {currentVersion?.audio_present === true
                              ? "Present"
                              : currentVersion?.audio_present === false
                              ? "Muted / None"
                              : "N/A"}
                          </span>
                        </div>
                        <div>
                          <span className="text-slate-400 block text-[10px] font-sans uppercase">
                            Bitrate
                          </span>
                          <span className="text-slate-800">
                            {currentVersion?.bitrate
                              ? `${Math.round(currentVersion.bitrate / 1000)} kbps`
                              : "N/A"}
                          </span>
                        </div>
                        <div>
                          <span className="text-slate-400 block text-[10px] font-sans uppercase">
                            Orientation
                          </span>
                          <span className="text-slate-800">
                            {currentVersion?.orientation !== null &&
                            currentVersion?.orientation !== undefined
                              ? `${currentVersion.orientation}°`
                              : "Default"}
                          </span>
                        </div>
                        <div className="col-span-2 sm:col-span-3">
                          <span className="text-slate-400 block text-[10px] font-sans uppercase">
                            SHA-256 Checksum
                          </span>
                          <span className="text-slate-700 text-[11px] break-all">
                            {currentVersion?.sha256 || "—"}
                          </span>
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* TAB 2: VERSION HISTORY (Requirement 12) */}
              {activeTab === "versions" && (
                <div className="space-y-4">
                  <div className="flex items-center justify-between">
                    <div>
                      <h3 className="font-bold text-slate-800 text-xs">
                        Media Versions ({asset.versions.length})
                      </h3>
                      <p className="text-[11px] text-slate-500">
                        Immutable inspection records. Replacing media keeps the existing version active until inspection passes.
                      </p>
                    </div>

                    {/* Replace / Upload Version Button */}
                    <input
                      ref={versionFileInputRef}
                      type="file"
                      accept="video/*,image/*,audio/*"
                      onChange={(e) => {
                        if (e.target.files && e.target.files.length > 0) {
                          handleVersionFileSelected(e.target.files[0]);
                        }
                      }}
                      className="hidden"
                    />
                    <button
                      type="button"
                      disabled={isUploadingVersion || asset.status === "deleted"}
                      onClick={() => versionFileInputRef.current?.click()}
                      className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-blue-50 text-blue-700 hover:bg-blue-100 text-xs font-semibold transition-colors disabled:opacity-50"
                    >
                      {isUploadingVersion ? (
                        <>
                          <Loader2 className="w-3.5 h-3.5 animate-spin" />
                          <span>Uploading next version...</span>
                        </>
                      ) : (
                        <>
                          <FileUp className="w-3.5 h-3.5" />
                          <span>Upload New Version</span>
                        </>
                      )}
                    </button>
                  </div>

                  {versionUploadError && (
                    <div className="rounded-xl border border-rose-200 bg-rose-50 p-3 text-xs text-rose-800">
                      {versionUploadError}
                    </div>
                  )}

                  {/* Versions Table / Cards */}
                  <div className="space-y-2.5">
                    {asset.versions
                      .slice()
                      .sort((a, b) => b.version_number - a.version_number)
                      .map((v) => {
                        const isCurrent = v.id === asset.current_version?.id;
                        return (
                          <div
                            key={v.id}
                            className={`rounded-xl border p-4 transition-colors ${
                              isCurrent
                                ? "border-blue-300 bg-blue-50/20"
                                : "border-slate-200 bg-white"
                            }`}
                          >
                            <div className="flex items-center justify-between">
                              <div className="flex items-center gap-2">
                                <span className="font-bold text-sm text-slate-900 font-mono">
                                  v{v.version_number}
                                </span>
                                {isCurrent && (
                                  <span className="px-2 py-0.5 rounded-full bg-blue-100 text-blue-800 text-[10px] font-bold uppercase">
                                    Current Active
                                  </span>
                                )}
                                <ContentStatusBadge
                                  status={v.processing_status}
                                  size="sm"
                                />
                              </div>
                              <span className="text-[11px] text-slate-400 font-mono">
                                {new Date(v.created_at).toLocaleString()}
                              </span>
                            </div>

                            <div className="mt-2 grid grid-cols-2 sm:grid-cols-4 gap-2 text-[11px] text-slate-600">
                              <div>
                                <span className="text-slate-400 block text-[10px] uppercase">
                                  Filename
                                </span>
                                <span className="font-mono truncate block">
                                  {v.original_filename}
                                </span>
                              </div>
                              <div>
                                <span className="text-slate-400 block text-[10px] uppercase">
                                  Resolution
                                </span>
                                <span className="font-mono">
                                  {v.width && v.height ? `${v.width}×${v.height}` : "—"}
                                </span>
                              </div>
                              <div>
                                <span className="text-slate-400 block text-[10px] uppercase">
                                  Duration
                                </span>
                                <span className="font-mono">
                                  {formatDuration(v.duration_ms)}
                                </span>
                              </div>
                              <div>
                                <span className="text-slate-400 block text-[10px] uppercase">
                                  Size
                                </span>
                                <span>{formatFileSize(v.size_bytes)}</span>
                              </div>
                            </div>

                            {v.error_message && (
                              <div className="mt-2 p-2.5 rounded-lg bg-rose-50 border border-rose-200 text-rose-800 text-[11px]">
                                {getContentErrorMessage(v.error_code, v.error_message)}
                              </div>
                            )}
                          </div>
                        );
                      })}
                  </div>
                </div>
              )}

              {/* TAB 3: DELIVERY HISTORY (Requirement 18) */}
              {activeTab === "deliveries" && (
                <div className="space-y-4">
                  <div className="flex items-center justify-between">
                    <div>
                      <h3 className="font-bold text-slate-800 text-xs">
                        Runtime Delivery History ({deliveries.length})
                      </h3>
                      <p className="text-[11px] text-slate-500">
                        Tracks all transfers to Android device manager storage
                      </p>
                    </div>

                    <button
                      type="button"
                      onClick={() => loadDeliveries(asset.id)}
                      disabled={deliveriesLoading}
                      className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg border border-slate-200 text-xs text-slate-600 hover:bg-slate-50"
                    >
                      <RefreshCw
                        className={`w-3 h-3 ${
                          deliveriesLoading ? "animate-spin" : ""
                        }`}
                      />
                      <span>Refresh</span>
                    </button>
                  </div>

                  {deliveriesLoading ? (
                    <div className="animate-pulse space-y-2">
                      <div className="h-14 rounded-lg bg-slate-100" />
                      <div className="h-14 rounded-lg bg-slate-100" />
                    </div>
                  ) : deliveries.length === 0 ? (
                    <div className="rounded-xl border border-slate-200 p-8 text-center text-slate-400 text-xs">
                      No deliveries recorded for this content asset yet.
                    </div>
                  ) : (
                    <div className="space-y-2.5">
                      {deliveries.map((del) => (
                        <div
                          key={del.id}
                          className="rounded-xl border border-slate-200 p-3.5 bg-white space-y-2"
                        >
                          <div className="flex items-center justify-between">
                            <div className="flex items-center gap-2">
                              <span className="font-semibold text-slate-900 text-xs flex items-center gap-1.5">
                                <Cpu className="w-3.5 h-3.5 text-blue-600" />
                                <span>Runtime #{del.runtime_id_snapshot}</span>
                              </span>
                              <ContentDeliveryBadge status={del.status} size="sm" />
                            </div>
                            <span className="text-[11px] text-slate-400 font-mono">
                              {new Date(del.created_at).toLocaleString()}
                            </span>
                          </div>

                          <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 text-[11px] text-slate-600">
                            <div>
                              <span className="text-slate-400 block text-[10px] uppercase">
                                Remote File
                              </span>
                              <span className="font-mono truncate block">
                                {del.remote_filename}
                              </span>
                            </div>
                            <div>
                              <span className="text-slate-400 block text-[10px] uppercase">
                                MediaStore Registered
                              </span>
                              <span>{del.import_media ? "Yes" : "No"}</span>
                            </div>
                            {del.job_id && onOpenJob && (
                              <div>
                                <span className="text-slate-400 block text-[10px] uppercase">
                                  Automation Job
                                </span>
                                <button
                                  type="button"
                                  onClick={() => onOpenJob(del.job_id)}
                                  className="text-blue-600 hover:underline inline-flex items-center gap-1"
                                >
                                  <span>Job #{del.job_id}</span>
                                  <ExternalLink className="w-2.5 h-2.5" />
                                </button>
                              </div>
                            )}
                          </div>

                          {del.media_uri && (
                            <div className="text-[10px] font-mono text-slate-500 bg-slate-50 p-1.5 rounded truncate">
                              URI: {del.media_uri}
                            </div>
                          )}

                          {del.error_message && (
                            <div className="p-2 rounded bg-rose-50 text-rose-800 text-[11px]">
                              {getContentErrorMessage(del.error_code, del.error_message)}
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </>
          )}
        </div>

        {/* Footer */}
        <div className="border-t border-slate-200 px-6 py-3 bg-slate-50 flex items-center justify-between text-xs text-slate-500">
          <span>Created: {asset ? new Date(asset.created_at).toLocaleDateString() : "—"}</span>
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-1.5 rounded-lg border border-slate-200 bg-white font-semibold text-slate-700 hover:bg-slate-50 transition-colors"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}

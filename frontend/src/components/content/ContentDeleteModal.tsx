import { useState } from "react";
import { AlertTriangle, Loader2, Trash2, X } from "lucide-react";
import { contentService } from "@/services/contentService";
import { ContentAsset, ContentAssetDetail } from "@/types/content";

interface ContentDeleteModalProps {
  isOpen: boolean;
  asset: ContentAsset | ContentAssetDetail;
  onClose: () => void;
  onDeleteSuccess: (asset: ContentAssetDetail) => void;
}

export function ContentDeleteModal({
  isOpen,
  asset,
  onClose,
  onDeleteSuccess,
}: ContentDeleteModalProps) {
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleDelete = async () => {
    setIsSubmitting(true);
    setError(null);

    try {
      const deleted = await contentService.deleteContent(asset.id);
      onDeleteSuccess(deleted);
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setIsSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-xs animate-in fade-in duration-150">
      <div
        className="w-full max-w-md rounded-2xl bg-white shadow-2xl border border-slate-200 overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between border-b border-slate-200 px-6 py-4 bg-rose-50/70">
          <div className="flex items-center gap-2.5">
            <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-rose-100 text-rose-700">
              <Trash2 className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-base font-bold text-slate-900">
                Delete Content Asset
              </h2>
              <p className="text-xs text-rose-700">
                Soft-delete asset from active library
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            disabled={isSubmitting}
            className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-200 hover:text-slate-600 transition-colors disabled:opacity-50"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content Body */}
        <div className="p-6 space-y-4 text-xs text-slate-600">
          {error && (
            <div className="rounded-xl border border-rose-200 bg-rose-50 p-3 text-rose-800">
              {error}
            </div>
          )}

          <div className="rounded-xl border border-slate-200 bg-slate-50 p-3.5 space-y-1">
            <span className="text-[10px] font-semibold uppercase tracking-wider text-slate-400 block">
              Asset to delete
            </span>
            <p className="font-bold text-sm text-slate-900 line-clamp-1">
              {asset.display_name}
            </p>
            <p className="text-slate-500 font-mono text-[11px]">
              ID #{asset.id} • Type: {asset.asset_type}
            </p>
          </div>

          <div className="rounded-xl border border-amber-200 bg-amber-50/80 p-3.5 space-y-1.5 text-amber-900 leading-relaxed">
            <div className="flex items-center gap-1.5 font-bold text-amber-800">
              <AlertTriangle className="w-4 h-4 text-amber-600" />
              <span>Soft-Delete Notice</span>
            </div>
            <p className="text-[11px]">
              Deleting this asset archives it into a soft-deleted state. Past delivery records and storage blobs are preserved for auditing, but the asset can no longer be delivered to new devices.
            </p>
          </div>
        </div>

        {/* Footer */}
        <div className="border-t border-slate-200 px-6 py-3.5 bg-slate-50 flex items-center justify-end gap-2.5">
          <button
            type="button"
            onClick={onClose}
            disabled={isSubmitting}
            className="px-4 py-2 rounded-lg border border-slate-200 text-xs font-semibold text-slate-700 hover:bg-slate-100 disabled:opacity-50 transition-colors"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={handleDelete}
            disabled={isSubmitting}
            className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg bg-rose-600 text-xs font-semibold text-white shadow-2xs hover:bg-rose-700 disabled:opacity-50 transition-colors"
          >
            {isSubmitting ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                <span>Deleting...</span>
              </>
            ) : (
              <>
                <Trash2 className="w-4 h-4" />
                <span>Confirm Soft-Delete</span>
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}

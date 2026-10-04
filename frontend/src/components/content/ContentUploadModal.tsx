import { useState, useRef, useEffect, useCallback } from "react";
import {
  AlertCircle,
  FileUp,
  Film,
  Image as ImageIcon,
  Loader2,
  Music,
  Plus,
  Tag,
  UploadCloud,
  X,
} from "lucide-react";
import { contentService } from "@/services/contentService";
import {
  ContentAssetDetail,
  ContentAssetType,
  formatFileSize,
} from "@/types/content";

interface ContentUploadModalProps {
  isOpen: boolean;
  onClose: () => void;
  onUploadSuccess: (asset: ContentAssetDetail) => void;
}

function inferAssetType(file: File): ContentAssetType {
  const mime = file.type.toLowerCase();
  const name = file.name.toLowerCase();

  if (mime.startsWith("video/") || name.match(/\.(mp4|mov|webm|avi|mkv)$/)) {
    return "video";
  }
  if (mime.startsWith("image/") || name.match(/\.(jpg|jpeg|png|webp|gif)$/)) {
    return "image";
  }
  if (
    mime.startsWith("audio/") ||
    name.match(/\.(mp3|wav|m4a|aac|ogg|flac)$/)
  ) {
    return "audio";
  }
  return "other";
}

function cleanFilename(name: string): string {
  return name.replace(/\.[^/.]+$/, "").replace(/[_-]/g, " ");
}

export function ContentUploadModal({
  isOpen,
  onClose,
  onUploadSuccess,
}: ContentUploadModalProps) {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [displayName, setDisplayName] = useState("");
  const [notes, setNotes] = useState("");
  const [tagInput, setTagInput] = useState("");
  const [tags, setTags] = useState<string[]>([]);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isDragging, setIsDragging] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const handleReset = useCallback(() => {
    setSelectedFile(null);
    setDisplayName("");
    setNotes("");
    setTagInput("");
    setTags([]);
    setIsSubmitting(false);
    setIsDragging(false);
    setError(null);
  }, []);

  const handleModalClose = useCallback(() => {
    if (isSubmitting) return;
    handleReset();
    onClose();
  }, [isSubmitting, handleReset, onClose]);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && isOpen && !isSubmitting) {
        handleModalClose();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, isSubmitting, handleModalClose]);

  const handleFileSelect = (file: File) => {
    setSelectedFile(file);
    setError(null);
    if (!displayName.trim()) {
      setDisplayName(cleanFilename(file.name));
    }
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      handleFileSelect(e.dataTransfer.files[0]);
    }
  };

  const handleAddTag = () => {
    const cleaned = tagInput.trim().toLowerCase().replace(/[^a-z0-9_-]/g, "");
    if (cleaned && !tags.includes(cleaned)) {
      setTags([...tags, cleaned]);
      setTagInput("");
    }
  };

  const handleRemoveTag = (tagToRemove: string) => {
    setTags(tags.filter((t) => t !== tagToRemove));
  };

  const handleTagKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter" || e.key === ",") {
      e.preventDefault();
      handleAddTag();
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedFile) {
      setError("Please select a media file to upload.");
      return;
    }
    if (!displayName.trim()) {
      setError("Display name is required.");
      return;
    }

    setIsSubmitting(true);
    setError(null);

    try {
      const result = await contentService.uploadContent({
        file: selectedFile,
        display_name: displayName.trim(),
        notes: notes.trim() || undefined,
        tags: tags.length > 0 ? tags : undefined,
      });

      handleReset();
      onUploadSuccess(result);
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      setError(msg);
      setIsSubmitting(false);
    }
  };

  if (!isOpen) return null;

  const inferredType = selectedFile ? inferAssetType(selectedFile) : null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-xs animate-in fade-in duration-150">
      <div
        className="w-full max-w-lg rounded-2xl bg-white shadow-2xl border border-slate-200 overflow-hidden flex flex-col max-h-[90vh]"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between border-b border-slate-200 px-6 py-4 bg-slate-50/80">
          <div className="flex items-center gap-2.5">
            <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-blue-50 text-blue-600 border border-blue-200">
              <FileUp className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-base font-bold text-slate-900">
                Upload Media Content
              </h2>
              <p className="text-xs text-slate-500">
                Add images, videos, or audio to your reusable Content Library
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={handleModalClose}
            disabled={isSubmitting}
            className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-200 hover:text-slate-600 transition-colors disabled:opacity-50"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Form Body */}
        <form onSubmit={handleSubmit} className="overflow-y-auto p-6 space-y-4">
          {error && (
            <div className="rounded-xl border border-rose-200 bg-rose-50/80 p-3.5 flex items-start gap-2.5 text-xs text-rose-800">
              <AlertCircle className="w-4 h-4 text-rose-600 shrink-0 mt-0.5" />
              <div className="flex-1">
                <span className="font-semibold block">Upload Failed</span>
                <span>{error}</span>
              </div>
            </div>
          )}

          {/* Drag & Drop Zone */}
          <div
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
            onClick={() => fileInputRef.current?.click()}
            className={`border-2 border-dashed rounded-xl p-6 text-center cursor-pointer transition-all ${
              isDragging
                ? "border-blue-500 bg-blue-50/60"
                : selectedFile
                ? "border-emerald-300 bg-emerald-50/30"
                : "border-slate-300 bg-slate-50/50 hover:bg-slate-50 hover:border-slate-400"
            }`}
          >
            <input
              ref={fileInputRef}
              type="file"
              accept="video/*,image/*,audio/*,.mp4,.mov,.webm,.avi,.mkv,.jpg,.jpeg,.png,.webp,.gif,.mp3,.wav,.m4a,.aac,.ogg,.flac"
              onChange={(e) => {
                if (e.target.files && e.target.files.length > 0) {
                  handleFileSelect(e.target.files[0]);
                }
              }}
              className="hidden"
            />

            {selectedFile ? (
              <div className="space-y-2">
                <div className="inline-flex p-3 rounded-xl bg-emerald-100 text-emerald-700">
                  {inferredType === "video" ? (
                    <Film className="w-6 h-6" />
                  ) : inferredType === "audio" ? (
                    <Music className="w-6 h-6" />
                  ) : (
                    <ImageIcon className="w-6 h-6" />
                  )}
                </div>
                <div>
                  <p className="font-semibold text-sm text-slate-800 break-all">
                    {selectedFile.name}
                  </p>
                  <p className="text-xs text-slate-500 mt-0.5">
                    {formatFileSize(selectedFile.size)} • Type:{" "}
                    <span className="font-medium text-slate-700 uppercase">
                      {inferredType}
                    </span>
                  </p>
                </div>
                <p className="text-[11px] text-blue-600 hover:underline pt-1">
                  Click or drag another file to replace
                </p>
              </div>
            ) : (
              <div className="space-y-2">
                <div className="inline-flex p-3 rounded-xl bg-blue-50 text-blue-600">
                  <UploadCloud className="w-6 h-6" />
                </div>
                <div>
                  <p className="text-sm font-semibold text-slate-800">
                    Choose media file or drag &amp; drop here
                  </p>
                  <p className="text-xs text-slate-500 mt-1">
                    MP4, MOV, WEBM, PNG, JPG, WEBP, MP3, WAV, M4A
                  </p>
                </div>
              </div>
            )}
          </div>

          {/* Display Name */}
          <div className="space-y-1.5">
            <label className="text-xs font-semibold text-slate-700">
              Display Name <span className="text-rose-500">*</span>
            </label>
            <input
              type="text"
              required
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              placeholder="e.g. Summer Promo Video 01"
              maxLength={255}
              className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-800 focus:border-blue-500 focus:outline-hidden"
            />
          </div>

          {/* Notes */}
          <div className="space-y-1.5">
            <label className="text-xs font-semibold text-slate-700">
              Notes <span className="text-slate-400 font-normal">(optional)</span>
            </label>
            <textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Add optional context, campaign details, or target accounts..."
              rows={2}
              maxLength={4000}
              className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-800 focus:border-blue-500 focus:outline-hidden resize-none"
            />
          </div>

          {/* Tags */}
          <div className="space-y-1.5">
            <label className="text-xs font-semibold text-slate-700">
              Tags <span className="text-slate-400 font-normal">(press Enter or click +)</span>
            </label>
            <div className="flex gap-2">
              <div className="relative flex-1">
                <Tag className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-slate-400" />
                <input
                  type="text"
                  value={tagInput}
                  onChange={(e) => setTagInput(e.target.value)}
                  onKeyDown={handleTagKeyDown}
                  placeholder="e.g. promo, reel, tiktok"
                  maxLength={50}
                  className="w-full rounded-lg border border-slate-200 bg-white pl-9 pr-3 py-1.5 text-xs text-slate-800 focus:border-blue-500 focus:outline-hidden"
                />
              </div>
              <button
                type="button"
                onClick={handleAddTag}
                className="px-3 py-1.5 rounded-lg border border-slate-200 bg-slate-50 text-xs font-semibold text-slate-700 hover:bg-slate-100 transition-colors"
              >
                <Plus className="w-3.5 h-3.5" />
              </button>
            </div>

            {/* Tag Chips */}
            {tags.length > 0 && (
              <div className="flex flex-wrap gap-1.5 pt-1">
                {tags.map((t) => (
                  <span
                    key={t}
                    className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-blue-50 text-blue-700 border border-blue-200 text-xs font-medium"
                  >
                    <span>{t}</span>
                    <button
                      type="button"
                      onClick={() => handleRemoveTag(t)}
                      className="hover:text-blue-900"
                    >
                      <X className="w-3 h-3" />
                    </button>
                  </span>
                ))}
              </div>
            )}
          </div>

          <div className="p-3 rounded-xl bg-slate-50 border border-slate-200 text-[11px] text-slate-500 leading-relaxed">
            <span className="font-semibold text-slate-700 block mb-0.5">
              Processing Notice
            </span>
            Uploading sends the file to the library. The background inspection service will asynchronously validate resolution, duration, codec, and integrity before the asset transitions to <strong>Ready</strong>.
          </div>

          {/* Footer Buttons */}
          <div className="pt-2 flex items-center justify-end gap-2.5 border-t border-slate-100">
            <button
              type="button"
              onClick={handleModalClose}
              disabled={isSubmitting}
              className="px-4 py-2 rounded-lg border border-slate-200 text-xs font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-50 transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isSubmitting || !selectedFile || !displayName.trim()}
              className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg bg-blue-600 text-xs font-semibold text-white shadow-2xs hover:bg-blue-700 disabled:opacity-50 transition-colors"
            >
              {isSubmitting ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  <span>Uploading media...</span>
                </>
              ) : (
                <>
                  <FileUp className="w-4 h-4" />
                  <span>Upload &amp; Inspect</span>
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

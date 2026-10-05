import { useState } from "react";
import {
  Clock,
  Film,
  FolderOpen,
  Image as ImageIcon,
  Music,
  Send,
  Sparkles,
  Tag,
} from "lucide-react";
import { contentService } from "@/services/contentService";
import {
  ContentAsset,
  ContentAssetType,
  formatDuration,
  formatFileSize,
} from "@/types/content";
import { ContentStatusBadge } from "./ContentStatusBadge";

interface ContentCardProps {
  asset: ContentAsset;
  onSelect: (asset: ContentAsset) => void;
  onDeliver?: (asset: ContentAsset) => void;
}

function getAssetTypeIcon(type: ContentAssetType) {
  switch (type) {
    case "video":
      return <Film className="w-4 h-4 text-purple-600" />;
    case "image":
      return <ImageIcon className="w-4 h-4 text-blue-600" />;
    case "audio":
      return <Music className="w-4 h-4 text-amber-600" />;
    default:
      return <FolderOpen className="w-4 h-4 text-slate-500" />;
  }
}

function formatDate(dateStr: string): string {
  try {
    const d = new Date(dateStr);
    return new Intl.DateTimeFormat(undefined, {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    }).format(d);
  } catch {
    return dateStr;
  }
}

export function ContentCard({
  asset,
  onSelect,
  onDeliver,
}: ContentCardProps) {
  const [failedThumbnail, setFailedThumbnail] = useState<string | null>(null);
  const version = asset.current_version;
  const isReady = asset.status === "ready" && version?.processing_status === "ready";
  const thumbnailUrl = contentService.getThumbnailUrl(asset.id);

  return (
    <div
      onClick={() => onSelect(asset)}
      className="group relative flex flex-col rounded-xl border border-slate-200 bg-white shadow-2xs transition-all hover:border-slate-300 hover:shadow-md cursor-pointer overflow-hidden"
    >
      {/* Media Preview Box */}
      <div className="relative aspect-video w-full bg-slate-900 flex items-center justify-center overflow-hidden">
        {(asset.asset_type === "image" || asset.asset_type === "video") &&
        isReady && asset.thumbnail_available && failedThumbnail !== thumbnailUrl ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={thumbnailUrl}
            alt={asset.display_name}
            onError={() => setFailedThumbnail(thumbnailUrl)}
            className="w-full h-full object-cover transition-transform duration-300 group-hover:scale-105"
            loading="lazy"
          />
        ) : asset.asset_type === "video" && isReady ? (
          <div className="w-full h-full flex flex-col items-center justify-center bg-gradient-to-br from-slate-900 to-purple-950 text-white p-4">
            <Film className="w-10 h-10 text-purple-400 mb-2 opacity-80 group-hover:scale-110 transition-transform" />
            {version?.width && version?.height && (
              <span className="text-[10px] text-purple-200 font-mono">
                {version.width} &times; {version.height}
              </span>
            )}
          </div>
        ) : asset.asset_type === "audio" && isReady ? (
          <div className="w-full h-full flex flex-col items-center justify-center bg-gradient-to-br from-slate-900 to-amber-950 text-white p-4">
            <Music className="w-10 h-10 text-amber-400 mb-2 opacity-80 group-hover:scale-110 transition-transform" />
            <span className="text-[10px] text-amber-200 font-mono">Audio Asset</span>
          </div>
        ) : asset.status === "processing" ? (
          <div className="w-full h-full flex flex-col items-center justify-center bg-slate-950/80 text-amber-400 p-4">
            <Sparkles className="w-8 h-8 animate-pulse mb-2 text-amber-400" />
            <span className="text-xs font-medium text-amber-200">
              Inspecting media...
            </span>
          </div>
        ) : (
          <div className="w-full h-full flex flex-col items-center justify-center bg-slate-100 text-slate-400 p-4">
            <FolderOpen className="w-8 h-8 mb-1" />
            <span className="text-[11px] font-medium text-slate-500">
              {asset.status === "invalid"
                ? "Invalid media"
                : asset.status === "deleted"
                ? "Deleted asset"
                : "No preview"}
            </span>
          </div>
        )}

        {/* Top Badges Overlay */}
        <div className="absolute top-2 left-2 flex items-center gap-1.5">
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-black/60 backdrop-blur-xs text-[10px] font-semibold text-white uppercase tracking-wider">
            {getAssetTypeIcon(asset.asset_type)}
            <span>{asset.asset_type}</span>
          </span>
          {version && (
            <span className="px-1.5 py-0.5 rounded-md bg-black/60 backdrop-blur-xs text-[10px] font-mono text-slate-200">
              v{version.version_number}
            </span>
          )}
        </div>

        <div className="absolute top-2 right-2">
          <ContentStatusBadge status={asset.status} size="sm" />
        </div>

        {/* Duration badge for video/audio */}
        {version?.duration_ms && version.duration_ms > 0 && (
          <div className="absolute bottom-2 right-2 px-1.5 py-0.5 rounded bg-black/75 text-[10px] font-mono text-white flex items-center gap-1">
            <Clock className="w-2.5 h-2.5 text-slate-300" />
            <span>{formatDuration(version.duration_ms)}</span>
          </div>
        )}
      </div>

      {/* Content Info */}
      <div className="p-4 flex-1 flex flex-col justify-between space-y-3">
        <div>
          <h3
            className="font-bold text-slate-900 text-sm line-clamp-1 group-hover:text-blue-600 transition-colors"
            title={asset.display_name}
          >
            {asset.display_name}
          </h3>
          <p className="mt-0.5 text-[11px] text-slate-500 line-clamp-1 font-mono">
            {version?.original_filename || "No file uploaded"}
          </p>
        </div>

        {/* Dimensions & Size Metadata */}
        <div className="flex items-center gap-2 text-[11px] text-slate-500">
          {version?.width && version?.height && (
            <>
              <span className="font-mono text-slate-600">
                {version.width}&times;{version.height}
              </span>
              <span>•</span>
            </>
          )}
          <span>{formatFileSize(version?.size_bytes)}</span>
          <span>•</span>
          <span title={asset.created_at}>{formatDate(asset.created_at)}</span>
        </div>

        {/* Tags */}
        {asset.tags && asset.tags.length > 0 && (
          <div className="flex flex-wrap gap-1">
            {asset.tags.slice(0, 3).map((tag) => (
              <span
                key={tag}
                className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-slate-100 text-slate-600 text-[10px] font-medium"
              >
                <Tag className="w-2.5 h-2.5 text-slate-400" />
                {tag}
              </span>
            ))}
            {asset.tags.length > 3 && (
              <span className="text-[10px] text-slate-400 self-center">
                +{asset.tags.length - 3}
              </span>
            )}
          </div>
        )}

        {/* Delivery State & Actions Footer */}
        <div className="pt-2 border-t border-slate-100 flex items-center justify-between text-xs">
          <div className="text-[11px] text-slate-500">
            {asset.total_deliveries > 0 ? (
              <span className="font-medium text-emerald-700">
                {asset.total_deliveries}{" "}
                {asset.total_deliveries === 1 ? "delivery" : "deliveries"}
              </span>
            ) : (
              <span className="text-slate-400">Not delivered yet</span>
            )}
          </div>

          {isReady && onDeliver && (
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                onDeliver(asset);
              }}
              className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg bg-blue-50 text-blue-700 hover:bg-blue-100 text-xs font-semibold transition-colors"
            >
              <Send className="w-3 h-3 text-blue-600" />
              <span>Deliver</span>
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

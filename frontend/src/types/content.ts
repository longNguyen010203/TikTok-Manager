/**
 * Types for the Content Library matching backend schemas (TIK-021).
 */

export type ContentAssetType = "video" | "image" | "audio" | "other";

export type ContentAssetStatus =
  | "processing"
  | "ready"
  | "invalid"
  | "archived"
  | "deleted";

export type ContentAssetSource =
  | "upload"
  | "promoted_artifact"
  | "generated"
  | "imported";

export type ContentVersionProcessingStatus =
  | "processing"
  | "ready"
  | "invalid";

export type ContentDeliveryStatus =
  | "pending"
  | "delivering"
  | "succeeded"
  | "failed"
  | "cancelled";

export interface ContentVersion {
  id: number;
  version_number: number;
  original_filename: string;
  detected_mime_type: string;
  canonical_extension: string;
  processing_status: ContentVersionProcessingStatus;
  size_bytes: number;
  sha256: string;
  width?: number | null;
  height?: number | null;
  duration_ms?: number | null;
  codec?: string | null;
  container?: string | null;
  frame_rate_numerator?: number | null;
  frame_rate_denominator?: number | null;
  audio_present?: boolean | null;
  bitrate?: number | null;
  sample_rate?: number | null;
  channels?: number | null;
  orientation?: number | null;
  metadata?: Record<string, unknown>;
  created_at: string;
  processed_at?: string | null;
  error_code?: string | null;
  error_message?: string | null;
}

export interface ContentAsset {
  id: number;
  asset_type: ContentAssetType;
  display_name: string;
  notes?: string | null;
  source: ContentAssetSource;
  status: ContentAssetStatus;
  tags: string[];
  current_version?: ContentVersion | null;
  created_at: string;
  updated_at: string;
  archived_at?: string | null;
  deleted_at?: string | null;
  total_deliveries: number;
  latest_delivery_status?: string | null;
  last_successful_delivery_at?: string | null;
}

export interface ContentAssetDetail extends ContentAsset {
  versions: ContentVersion[];
}

export interface ContentAssetList {
  items: ContentAsset[];
  total: number;
  page: number;
  page_size: number;
}

export interface ContentAssetListParams {
  query?: string;
  asset_type?: ContentAssetType;
  status?: ContentAssetStatus;
  tag?: string;
  source?: ContentAssetSource;
  page?: number;
  page_size?: number;
}

export interface ContentAssetPatch {
  display_name?: string;
  notes?: string | null;
  tags?: string[];
  archived?: boolean;
}

export interface ContentDeliveryCreate {
  runtime_id: number;
  version_id?: number | null;
  filename?: string | null;
  import_media?: boolean;
  allow_repeat?: boolean;
  idempotency_key?: string | null;
}

export interface ContentDelivery {
  id: number;
  content_asset_id: number;
  content_asset_version_id: number;
  content_variant_id?: number | null;
  runtime_id?: number | null;
  runtime_id_snapshot: number;
  job_id: number;
  status: ContentDeliveryStatus;
  import_media: boolean;
  remote_filename: string;
  remote_path: string;
  media_uri?: string | null;
  delivered_sha256?: string | null;
  created_at: string;
  started_at?: string | null;
  completed_at?: string | null;
  error_code?: string | null;
  error_message?: string | null;
}

export interface ContentDeliveryCreateResult {
  delivery: ContentDelivery;
  job_status: string;
  created: boolean;
}

export interface ContentDeliveryList {
  items: ContentDelivery[];
  total: number;
  page: number;
  page_size: number;
}

export interface ContentUploadInput {
  file: File;
  display_name: string;
  notes?: string;
  tags?: string[];
}

/**
 * Friendly operator error messages for backend error codes.
 */
export const CONTENT_ERROR_MESSAGES: Record<string, string> = {
  CONTENT_NOT_READY:
    "Content has no usable ready version. Please wait for processing to finish.",
  CONTENT_VERSION_NOT_READY:
    "This media version is not ready for delivery.",
  CONTENT_BLOB_MISSING:
    "Content media file is missing from backend storage.",
  CONTENT_BLOB_INVALID:
    "Media file failed inspection or is not a supported media format.",
  CONTENT_STORAGE_FULL:
    "Storage limit reached. Please archive or remove older content.",
  CONTENT_DELIVERY_DUPLICATE:
    "This content has already been delivered to the selected device.",
  CONTENT_REMOTE_FILENAME_INVALID:
    "The remote filename is invalid. Please avoid special characters.",
  CONTENT_NOT_FOUND: "Content asset was not found.",
  CONTENT_DELETED: "This content asset was deleted.",
  CONTENT_IN_USE: "Content asset is currently being processed or delivered.",
  RUNTIME_NOT_FOUND: "Target device runtime was not found.",
  RUNTIME_BUSY: "Device runtime is currently busy with another operation.",
  RUNTIME_STOPPED:
    "Device runtime is stopped. Start the device before delivering content.",
  RUNTIME_SCREEN_ACTIVE:
    "Close the active device screen before delivering content.",
};

export function getContentErrorMessage(
  code?: string | null,
  fallback?: string | null
): string {
  if (code && CONTENT_ERROR_MESSAGES[code]) {
    return CONTENT_ERROR_MESSAGES[code];
  }
  if (fallback && fallback.trim()) {
    // Sanitize any raw python tracebacks or internal paths
    if (
      fallback.includes("Traceback") ||
      fallback.includes("subprocess.CalledProcessError") ||
      fallback.includes("Pillow") ||
      fallback.includes("ffprobe")
    ) {
      return "Media validation failed. The file format may be corrupted or unsupported.";
    }
    return fallback;
  }
  return "An unexpected error occurred during content processing.";
}

export function formatDuration(ms?: number | null): string {
  if (ms === null || ms === undefined || ms <= 0) return "—";
  const totalSeconds = Math.round(ms / 1000);
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  if (minutes > 0) {
    return `${minutes}m ${seconds.toString().padStart(2, "0")}s`;
  }
  return `${seconds}s`;
}

export function formatFileSize(bytes?: number | null): string {
  if (bytes === null || bytes === undefined || bytes === 0) return "0 B";
  const k = 1024;
  const sizes = ["B", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`;
}

/**
 * Managed Android Applications & Versions Types (TIK-023).
 */

export type ManagedAppStatus = "active" | "disabled" | "archived";
export type ManagedAppPolicy = "required" | "optional" | "disabled";
export type ManagedAppVersionStatus =
  | "uploaded"
  | "inspecting"
  | "ready"
  | "invalid"
  | "retired";
export type InspectionLevel = "basic" | "verified";
export type PackageVerification = "post_install" | "pre_and_post_install";

export interface ManagedAppVersion {
  id: number;
  managed_app_id: number;
  version_name: string | null;
  version_code: number | null;
  sha256: string;
  discovered_package_name: string | null;
  min_sdk: number | null;
  target_sdk: number | null;
  signer_fingerprint: string | null;
  inspection_level: InspectionLevel;
  package_verification: PackageVerification;
  basic_approved: boolean;
  basic_approved_at: string | null;
  status: ManagedAppVersionStatus;
  inspection_job_id: number | null;
  inspector_name: string;
  inspector_version: string | null;
  validated_at: string | null;
  error_code: string | null;
  error_message: string | null;
  created_at: string;
  updated_at: string;
}

export interface ManagedApp {
  id: number;
  key: string;
  display_name: string;
  android_package_name: string;
  status: ManagedAppStatus;
  install_policy: ManagedAppPolicy;
  current_version_id: number | null;
  created_at: string;
  updated_at: string;
}

export interface ManagedAppDetail extends ManagedApp {
  versions: ManagedAppVersion[];
}

export interface ManagedAppList {
  items: ManagedApp[];
  total: number;
  page: number;
  page_size: number;
}

export interface ManagedAppVersionList {
  items: ManagedAppVersion[];
  total: number;
  page: number;
  page_size: number;
}

export interface ManagedAppCreateInput {
  key: string;
  display_name: string;
  android_package_name: string;
  install_policy?: ManagedAppPolicy;
}

export interface ManagedAppPatchInput {
  display_name?: string;
  status?: ManagedAppStatus;
  install_policy?: ManagedAppPolicy;
}

export interface ManagedAppVersionUploadResponse {
  version: ManagedAppVersion;
  created: boolean;
}

export const MANAGED_APP_ERROR_MESSAGES: Record<string, string> = {
  MANAGED_APP_NOT_FOUND: "Managed app not found.",
  MANAGED_APP_VERSION_NOT_FOUND: "Managed app version not found.",
  MANAGED_APP_CONFLICT: "A managed app with this key or package name already exists.",
  MANAGED_APP_VERSION_CONFLICT: "This APK version has already been uploaded for this app.",
  MANAGED_APP_ARCHIVED: "Cannot modify an archived managed app.",
  MANAGED_APP_VERSION_NOT_READY: "Version is not ready or failed inspection.",
  MANAGED_APP_VERSION_ACTIVE: "Cannot retire the currently active version.",
  MANAGED_APP_VERSION_BUSY: "Version inspection is currently in progress.",
  CONTENT_UPLOAD_TOO_LARGE: "The APK file exceeds the maximum allowed size.",
  CONTENT_STORAGE_FULL: "Storage limit reached. Cannot upload APK.",
  APK_ADMISSION_FAILED: "APK admission inspection failed. Ensure the file is a valid Android APK.",
};

export function getManagedAppErrorMessage(
  code: string | null | undefined,
  fallback?: string | null
): string {
  if (code && MANAGED_APP_ERROR_MESSAGES[code]) {
    return MANAGED_APP_ERROR_MESSAGES[code];
  }
  return fallback || "An unexpected error occurred with the managed app.";
}

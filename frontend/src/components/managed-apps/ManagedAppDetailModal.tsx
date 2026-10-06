import React, { useState, useEffect, useRef, useCallback } from "react";
import {
  ManagedAppDetail,
  ManagedAppVersion,
} from "@/types/managedApp";
import { managedAppService } from "@/services/managedAppService";
import { formatApiError } from "@/types/runtime";
import {
  AppStatusBadge,
  AssuranceLevelBadge,
  InstallPolicyBadge,
  VersionStatusBadge,
} from "./ManagedAppStatusBadge";
import { ManagedAppBasicApprovalModal } from "./ManagedAppBasicApprovalModal";
import {
  X,
  Package,
  Upload,
  ShieldAlert,
  CheckCircle2,
  FileCode,
  Calendar,
  AlertCircle,
  Loader2,
  ArrowUpCircle,
  Archive,
  Fingerprint,
} from "lucide-react";

interface ManagedAppDetailModalProps {
  appId: number | null;
  isOpen: boolean;
  onClose: () => void;
  onAppUpdated: (updatedApp: ManagedAppDetail) => void;
}

export function ManagedAppDetailModal({
  appId,
  isOpen,
  onClose,
  onAppUpdated,
}: ManagedAppDetailModalProps) {
  const [app, setApp] = useState<ManagedAppDetail | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [actionSuccessMessage, setActionSuccessMessage] = useState<string | null>(null);

  // APK Upload State
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);

  // Version Action State
  const [activeVersionForApproval, setActiveVersionForApproval] =
    useState<ManagedAppVersion | null>(null);
  const [isOperatingVersionId, setIsOperatingVersionId] = useState<number | null>(null);

  // Load app details
  const fetchAppDetail = useCallback(async (id: number) => {
    try {
      setIsLoading(true);
      setErrorMessage(null);
      const res = await managedAppService.getManagedApp(id);
      setApp(res);
      onAppUpdated(res);
    } catch (err: unknown) {
      setErrorMessage(formatApiError(err));
    } finally {
      setIsLoading(false);
    }
  }, [onAppUpdated]);

  useEffect(() => {
    if (!isOpen || !appId) return;

    let ignore = false;
    managedAppService
      .getManagedApp(appId)
      .then((res) => {
        if (!ignore) {
          setApp(res);
          onAppUpdated(res);
        }
      })
      .catch((err: unknown) => {
        if (!ignore) setErrorMessage(formatApiError(err));
      })
      .finally(() => {
        if (!ignore) setIsLoading(false);
      });

    return () => {
      ignore = true;
    };
  }, [isOpen, appId, onAppUpdated]);

  if (!isOpen || !appId) return null;

  // APK Upload handler
  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      if (!file.name.toLowerCase().endsWith(".apk")) {
        setUploadError("Please select a valid .apk file.");
        setSelectedFile(null);
        return;
      }
      setSelectedFile(file);
      setUploadError(null);
    }
  };

  const handleUploadSubmit = async () => {
    if (!selectedFile || isUploading) return;

    try {
      setIsUploading(true);
      setUploadError(null);
      await managedAppService.uploadVersion(appId, selectedFile);
      setSelectedFile(null);
      if (fileInputRef.current) fileInputRef.current.value = "";
      setActionSuccessMessage("APK uploaded successfully and submitted for inspection.");
      await fetchAppDetail(appId);
    } catch (err: unknown) {
      setUploadError(formatApiError(err));
    } finally {
      setIsUploading(false);
    }
  };

  // Version Activation
  const handleActivate = async (versionId: number) => {
    try {
      setIsOperatingVersionId(versionId);
      setErrorMessage(null);
      const updated = await managedAppService.activateVersion(appId, versionId);
      if (updated && Array.isArray(updated.versions)) {
        setApp(updated);
        onAppUpdated(updated);
      } else {
        await fetchAppDetail(appId);
      }
      setActionSuccessMessage(`Version #${versionId} is now active.`);
    } catch (err: unknown) {
      setErrorMessage(formatApiError(err));
    } finally {
      setIsOperatingVersionId(null);
    }
  };

  // Version Retire
  const handleRetire = async (versionId: number) => {
    try {
      setIsOperatingVersionId(versionId);
      setErrorMessage(null);
      await managedAppService.retireVersion(appId, versionId);
      setActionSuccessMessage(`Version #${versionId} has been retired.`);
      await fetchAppDetail(appId);
    } catch (err: unknown) {
      setErrorMessage(formatApiError(err));
    } finally {
      setIsOperatingVersionId(null);
    }
  };

  const formatDate = (isoString?: string | null) => {
    if (!isoString) return "N/A";
    try {
      return new Intl.DateTimeFormat("en-US", {
        month: "short",
        day: "numeric",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit",
        hour12: false,
      }).format(new Date(isoString));
    } catch {
      return isoString;
    }
  };

  const formatFileSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  return (
    <>
      <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-xs overflow-y-auto">
        <div className="relative w-full max-w-4xl bg-white rounded-xl shadow-2xl border border-slate-200 overflow-hidden my-8 max-h-[90vh] flex flex-col">
          {/* Header */}
          <div className="flex items-center justify-between px-6 py-4 border-b border-slate-200 bg-slate-50/50">
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 rounded-lg bg-rose-100 text-rose-600 flex items-center justify-center font-bold">
                <Package className="w-5 h-5" />
              </div>
              <div>
                <h2 className="text-base font-bold text-slate-900 flex items-center gap-2">
                  <span>{app?.display_name || "Managed App"}</span>
                  {app && <AppStatusBadge status={app.status} />}
                  {app && <InstallPolicyBadge policy={app.install_policy} />}
                </h2>
                <p className="text-xs text-slate-500 font-mono">
                  {app?.android_package_name} ({app?.key})
                </p>
              </div>
            </div>
            <button
              type="button"
              onClick={onClose}
              className="p-1 rounded-md text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition-colors"
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          {/* Body */}
          <div className="p-6 space-y-6 overflow-y-auto flex-1">
            {errorMessage && (
              <div className="p-3 bg-rose-50 border border-rose-200 rounded-lg text-xs text-rose-700 flex items-start gap-2">
                <AlertCircle className="w-4 h-4 text-rose-600 shrink-0 mt-0.5" />
                <span>{errorMessage}</span>
              </div>
            )}

            {actionSuccessMessage && (
              <div className="p-3 bg-emerald-50 border border-emerald-200 rounded-lg text-xs text-emerald-800 flex items-start justify-between gap-2">
                <div className="flex items-center gap-2">
                  <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
                  <span>{actionSuccessMessage}</span>
                </div>
                <button
                  type="button"
                  onClick={() => setActionSuccessMessage(null)}
                  className="text-emerald-600 hover:text-emerald-800"
                >
                  &times;
                </button>
              </div>
            )}

            {/* Upload APK Section */}
            <div className="p-4 bg-slate-50 border border-slate-200 rounded-xl space-y-3">
              <h3 className="text-xs font-bold text-slate-800 uppercase tracking-wider flex items-center gap-1.5">
                <Upload className="w-3.5 h-3.5 text-rose-600" />
                <span>Upload New APK Version</span>
              </h3>

              {uploadError && (
                <div className="p-2.5 bg-rose-50 border border-rose-200 rounded-lg text-xs text-rose-700">
                  {uploadError}
                </div>
              )}

              <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-3">
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".apk"
                  onChange={handleFileChange}
                  disabled={isUploading}
                  className="text-xs text-slate-500 file:mr-3 file:py-1.5 file:px-3 file:rounded-md file:border-0 file:text-xs file:font-semibold file:bg-rose-50 file:text-rose-700 hover:file:bg-rose-100 file:cursor-pointer cursor-pointer"
                />

                {selectedFile && (
                  <div className="flex items-center gap-2 text-xs text-slate-600 font-mono bg-white px-2.5 py-1.5 rounded-md border border-slate-200">
                    <span className="font-semibold truncate max-w-[200px]">{selectedFile.name}</span>
                    <span className="text-slate-400">({formatFileSize(selectedFile.size)})</span>
                  </div>
                )}

                <button
                  type="button"
                  onClick={handleUploadSubmit}
                  disabled={!selectedFile || isUploading}
                  className="inline-flex items-center justify-center gap-1.5 px-4 py-2 text-xs font-semibold text-white bg-rose-600 hover:bg-rose-700 rounded-lg shadow-xs disabled:opacity-50 transition-colors shrink-0"
                >
                  {isUploading ? (
                    <>
                      <Loader2 className="w-3.5 h-3.5 animate-spin" />
                      <span>Uploading APK...</span>
                    </>
                  ) : (
                    <>
                      <Upload className="w-3.5 h-3.5" />
                      <span>Submit APK</span>
                    </>
                  )}
                </button>
              </div>
              <p className="text-[11px] text-slate-400">
                Uploaded APKs undergo automated SHA-256 calculation and safe manifest inspection. No host paths or raw scripts exposed.
              </p>
            </div>

            {/* Versions List */}
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <h3 className="text-xs font-bold text-slate-800 uppercase tracking-wider flex items-center gap-1.5">
                  <FileCode className="w-3.5 h-3.5 text-indigo-600" />
                  <span>Version History ({app?.versions?.length || 0})</span>
                </h3>
              </div>

              {isLoading ? (
                <div className="py-8 flex flex-col items-center justify-center text-slate-400 gap-2">
                  <Loader2 className="w-5 h-5 animate-spin text-slate-500" />
                  <span className="text-xs">Loading versions...</span>
                </div>
              ) : !app?.versions || app.versions.length === 0 ? (
                <div className="p-8 text-center bg-slate-50 rounded-xl border border-slate-200 text-xs text-slate-500">
                  No APK versions uploaded yet. Upload an APK above to create version 1.
                </div>
              ) : (
                <div className="space-y-3">
                  {app.versions.map((ver: ManagedAppVersion) => {
                    const isCurrent = app.current_version_id === ver.id;
                    const isOperating = isOperatingVersionId === ver.id;

                    return (
                      <div
                        key={ver.id}
                        className={`p-4 rounded-xl border transition-all ${
                          isCurrent
                            ? "bg-rose-50/30 border-rose-200 shadow-xs ring-1 ring-rose-200"
                            : "bg-white border-slate-200 hover:border-slate-300"
                        }`}
                      >
                        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-2 border-b border-slate-100">
                          <div className="flex items-center gap-2 flex-wrap">
                            <span className="font-mono font-bold text-xs text-slate-900">
                              Version #{ver.id}
                            </span>
                            {isCurrent && (
                              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold bg-rose-600 text-white">
                                <CheckCircle2 className="w-3 h-3" />
                                <span>Active Current</span>
                              </span>
                            )}
                            <VersionStatusBadge status={ver.status} />
                            <AssuranceLevelBadge level={ver.inspection_level} />
                            {ver.basic_approved && (
                              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[10px] font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
                                <span>Basic Approved</span>
                              </span>
                            )}
                          </div>

                          <div className="text-[11px] text-slate-400 flex items-center gap-1 font-mono">
                            <Calendar className="w-3 h-3 text-slate-400" />
                            <span>{formatDate(ver.created_at)}</span>
                          </div>
                        </div>

                        {/* Metadata Details */}
                        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2.5 pt-3 text-xs">
                          <div>
                            <span className="text-[11px] text-slate-400 block">Version Name / Code:</span>
                            <span className="font-mono text-slate-800 font-medium">
                              {ver.version_name ? `v${ver.version_name}` : "N/A"}{" "}
                              {ver.version_code ? `(${ver.version_code})` : ""}
                            </span>
                          </div>

                          <div>
                            <span className="text-[11px] text-slate-400 block">SHA-256 Digest:</span>
                            <span className="font-mono text-slate-800 font-semibold" title={ver.sha256}>
                              {ver.sha256.slice(0, 16)}...
                            </span>
                          </div>

                          <div>
                            <span className="text-[11px] text-slate-400 block">Verification Mode:</span>
                            <span className="text-slate-700 font-medium capitalize">
                              {ver.package_verification.replace(/_/g, " ")}
                            </span>
                          </div>

                          {ver.discovered_package_name && (
                            <div>
                              <span className="text-[11px] text-slate-400 block">Discovered Package:</span>
                              <span className="font-mono text-slate-800">
                                {ver.discovered_package_name}
                              </span>
                            </div>
                          )}

                          {ver.signer_fingerprint && (
                            <div className="sm:col-span-2">
                              <span className="text-[11px] text-slate-400 block flex items-center gap-1">
                                <Fingerprint className="w-3 h-3 text-emerald-600" />
                                <span>Signer Fingerprint:</span>
                              </span>
                              <span className="font-mono text-[11px] text-slate-700 truncate block" title={ver.signer_fingerprint}>
                                {ver.signer_fingerprint.slice(0, 24)}...
                              </span>
                            </div>
                          )}

                          {ver.error_message && (
                            <div className="col-span-full p-2 bg-rose-50 rounded-lg text-rose-700 text-xs">
                              <strong>Error ({ver.error_code || "INSPECTION_FAILED"}):</strong> {ver.error_message}
                            </div>
                          )}
                        </div>

                        {/* Actions for this version */}
                        <div className="flex items-center justify-end gap-2 pt-3 mt-2 border-t border-slate-100">
                          {/* Basic Approval action */}
                          {ver.inspection_level === "basic" && !ver.basic_approved && ver.status === "ready" && (
                            <button
                              type="button"
                              onClick={() => setActiveVersionForApproval(ver)}
                              disabled={isOperating}
                              className="inline-flex items-center gap-1 px-2.5 py-1 text-xs font-semibold text-amber-800 bg-amber-50 hover:bg-amber-100 border border-amber-200 rounded-lg transition-colors"
                            >
                              <ShieldAlert className="w-3 h-3 text-amber-600" />
                              <span>Approve Basic</span>
                            </button>
                          )}

                          {/* Activate version */}
                          {!isCurrent && ver.status === "ready" && (
                            <button
                              type="button"
                              onClick={() => handleActivate(ver.id)}
                              disabled={isOperating}
                              className="inline-flex items-center gap-1 px-2.5 py-1 text-xs font-semibold text-indigo-700 bg-indigo-50 hover:bg-indigo-100 border border-indigo-200 rounded-lg transition-colors"
                            >
                              {isOperating ? (
                                <Loader2 className="w-3 h-3 animate-spin" />
                              ) : (
                                <ArrowUpCircle className="w-3 h-3 text-indigo-600" />
                              )}
                              <span>Activate</span>
                            </button>
                          )}

                          {/* Retire version */}
                          {!isCurrent && ver.status !== "retired" && (
                            <button
                              type="button"
                              onClick={() => handleRetire(ver.id)}
                              disabled={isOperating}
                              className="inline-flex items-center gap-1 px-2.5 py-1 text-xs font-medium text-slate-600 hover:text-slate-800 hover:bg-slate-100 rounded-lg transition-colors"
                            >
                              <Archive className="w-3 h-3 text-slate-400" />
                              <span>Retire</span>
                            </button>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          </div>

          {/* Footer */}
          <div className="px-6 py-3 border-t border-slate-200 bg-slate-50/50 flex justify-end">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 text-xs font-medium text-slate-700 hover:bg-slate-100 rounded-lg transition-colors"
            >
              Close
            </button>
          </div>
        </div>
      </div>

      {/* Basic Approval Safety Confirmation Modal */}
      <ManagedAppBasicApprovalModal
        appId={appId}
        version={activeVersionForApproval}
        isOpen={activeVersionForApproval !== null}
        onClose={() => setActiveVersionForApproval(null)}
        onSuccess={(approved) => {
          setActionSuccessMessage(`Version #${approved.id} basic assurance approved.`);
          fetchAppDetail(appId);
        }}
      />
    </>
  );
}

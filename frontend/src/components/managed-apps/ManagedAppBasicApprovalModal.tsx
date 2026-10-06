import React, { useState } from "react";
import { ManagedAppVersion } from "@/types/managedApp";
import { managedAppService } from "@/services/managedAppService";
import { formatApiError } from "@/types/runtime";
import { AlertTriangle, ShieldAlert, X, Loader2 } from "lucide-react";

interface ManagedAppBasicApprovalModalProps {
  appId: number;
  version: ManagedAppVersion | null;
  isOpen: boolean;
  onClose: () => void;
  onSuccess: (approvedVersion: ManagedAppVersion) => void;
}

export function ManagedAppBasicApprovalModal({
  appId,
  version,
  isOpen,
  onClose,
  onSuccess,
}: ManagedAppBasicApprovalModalProps) {
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  if (!isOpen || !version) return null;

  const handleApprove = async () => {
    try {
      setIsSubmitting(true);
      setErrorMessage(null);
      const approved = await managedAppService.approveBasic(appId, version.id);
      onSuccess(approved);
      onClose();
    } catch (err: unknown) {
      setErrorMessage(formatApiError(err));
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-xs">
      <div className="relative w-full max-w-md bg-white rounded-xl shadow-2xl border border-amber-200 overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-amber-100 bg-amber-50/60">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-lg bg-amber-100 text-amber-700 flex items-center justify-center font-bold">
              <ShieldAlert className="w-5 h-5 text-amber-600" />
            </div>
            <div>
              <h2 className="text-sm font-bold text-slate-900">Approve Basic Assurance</h2>
              <p className="text-xs text-slate-500 font-mono">Version #{version.id}</p>
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

        {/* Content */}
        <div className="p-6 space-y-4">
          {errorMessage && (
            <div className="p-3 bg-rose-50 border border-rose-200 rounded-lg text-xs text-rose-700">
              {errorMessage}
            </div>
          )}

          <div className="p-4 rounded-xl border border-amber-200 bg-amber-50/80 text-amber-900 space-y-2">
            <div className="flex items-start gap-2.5">
              <AlertTriangle className="w-5 h-5 text-amber-600 shrink-0 mt-0.5" />
              <div className="text-xs leading-relaxed">
                <p className="font-semibold text-amber-950 mb-1">
                  Operator Caution Required:
                </p>
                <p>
                  &ldquo;Basic approval means the APK was admitted and hashed, but package/signature assurance is verified after installation.&rdquo;
                </p>
              </div>
            </div>
          </div>

          <div className="p-3 rounded-lg bg-slate-50 border border-slate-200 text-xs space-y-1.5 font-mono">
            <div className="flex justify-between">
              <span className="text-slate-500">SHA-256:</span>
              <span className="text-slate-800 font-semibold truncate max-w-[220px]" title={version.sha256}>
                {version.sha256.slice(0, 16)}...
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-500">Inspection:</span>
              <span className="text-slate-800">{version.inspection_level}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-500">Verification:</span>
              <span className="text-slate-800">{version.package_verification}</span>
            </div>
          </div>

          <p className="text-xs text-slate-600">
            Confirming this action marks the version as eligible for initial basic activation.
          </p>
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end gap-3 px-6 py-4 border-t border-slate-200 bg-slate-50/50">
          <button
            type="button"
            onClick={onClose}
            disabled={isSubmitting}
            className="px-4 py-2 text-xs font-medium text-slate-700 hover:bg-slate-100 rounded-lg transition-colors"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={handleApprove}
            disabled={isSubmitting}
            className="inline-flex items-center gap-2 px-5 py-2 text-xs font-semibold text-white bg-amber-600 hover:bg-amber-700 rounded-lg shadow-sm disabled:opacity-50 transition-colors"
          >
            {isSubmitting ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                <span>Approving...</span>
              </>
            ) : (
              <span>Confirm Basic Approval</span>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}

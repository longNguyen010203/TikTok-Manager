import React, { useState } from "react";
import { ManagedApp, ManagedAppDetail, ManagedAppPatchInput, ManagedAppPolicy, ManagedAppStatus } from "@/types/managedApp";
import { managedAppService } from "@/services/managedAppService";
import { formatApiError } from "@/types/runtime";
import { X, Pencil, AlertCircle, Loader2, Lock } from "lucide-react";

interface ManagedAppEditModalProps {
  app: ManagedApp | null;
  isOpen: boolean;
  onClose: () => void;
  onSuccess: (updatedApp: ManagedAppDetail) => void;
}

export function ManagedAppEditModal({
  app,
  isOpen,
  onClose,
  onSuccess,
}: ManagedAppEditModalProps) {
  const [prevAppId, setPrevAppId] = useState<number | null>(null);
  const [displayName, setDisplayName] = useState(app?.display_name || "");
  const [status, setStatus] = useState<ManagedAppStatus>(app?.status || "active");
  const [installPolicy, setInstallPolicy] = useState<ManagedAppPolicy>(app?.install_policy || "optional");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  if (app && app.id !== prevAppId) {
    setPrevAppId(app.id);
    setDisplayName(app.display_name);
    setStatus(app.status);
    setInstallPolicy(app.install_policy);
    setErrorMessage(null);
  }

  if (!isOpen || !app) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (isSubmitting) return;

    if (!displayName.trim()) {
      setErrorMessage("Please enter a display name.");
      return;
    }

    const payload: ManagedAppPatchInput = {
      display_name: displayName.trim(),
      status,
      install_policy: installPolicy,
    };

    try {
      setIsSubmitting(true);
      setErrorMessage(null);
      const updated = await managedAppService.patchManagedApp(app.id, payload);
      onSuccess(updated);
      onClose();
    } catch (err: unknown) {
      setErrorMessage(formatApiError(err));
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-xs overflow-y-auto">
      <div className="relative w-full max-w-lg bg-white rounded-xl shadow-2xl border border-slate-200 overflow-hidden my-8">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-200 bg-slate-50/50">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-lg bg-indigo-100 text-indigo-600 flex items-center justify-center font-bold">
              <Pencil className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-base font-bold text-slate-900">Edit Managed App</h2>
              <p className="text-xs text-slate-500">
                Update display name, lifecycle status, or install policy.
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

        {/* Form */}
        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          {errorMessage && (
            <div className="p-3 bg-rose-50 border border-rose-200 rounded-lg text-xs text-rose-700 flex items-start gap-2">
              <AlertCircle className="w-4 h-4 text-rose-600 shrink-0 mt-0.5" />
              <span>{errorMessage}</span>
            </div>
          )}

          {/* Immutable Key */}
          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1 flex items-center gap-1.5">
              <span>App Key</span>
              <Lock className="w-3 h-3 text-slate-400" />
            </label>
            <input
              type="text"
              disabled
              value={app.key}
              className="w-full text-xs px-3 py-2 bg-slate-100 border border-slate-200 rounded-lg text-slate-500 font-mono cursor-not-allowed"
            />
            <p className="text-[11px] text-slate-400 mt-1">
              App key identity is immutable.
            </p>
          </div>

          {/* Immutable Package Name */}
          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1 flex items-center gap-1.5">
              <span>Android Package Name</span>
              <Lock className="w-3 h-3 text-slate-400" />
            </label>
            <input
              type="text"
              disabled
              value={app.android_package_name}
              className="w-full text-xs px-3 py-2 bg-slate-100 border border-slate-200 rounded-lg text-slate-500 font-mono cursor-not-allowed"
            />
            <p className="text-[11px] text-slate-400 mt-1">
              Package identity cannot be changed after creation.
            </p>
          </div>

          {/* Editable Display Name */}
          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">
              Display Name <span className="text-rose-500">*</span>
            </label>
            <input
              type="text"
              required
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              className="w-full text-xs px-3 py-2 bg-white border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
          </div>

          {/* Status */}
          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">
              Status <span className="text-rose-500">*</span>
            </label>
            <select
              value={status}
              onChange={(e) => setStatus(e.target.value as ManagedAppStatus)}
              className="w-full text-xs px-3 py-2 bg-white border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500"
            >
              <option value="active">Active</option>
              <option value="disabled">Disabled</option>
              <option value="archived">Archived</option>
            </select>
          </div>

          {/* Install Policy */}
          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">
              Install Policy <span className="text-rose-500">*</span>
            </label>
            <select
              value={installPolicy}
              onChange={(e) => setInstallPolicy(e.target.value as ManagedAppPolicy)}
              className="w-full text-xs px-3 py-2 bg-white border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500"
            >
              <option value="optional">Optional — installed per workflow request</option>
              <option value="required">Required — required for publishing readiness</option>
              <option value="disabled">Disabled — not eligible for installation</option>
            </select>
          </div>

          <div className="flex items-center justify-end gap-3 pt-4 border-t border-slate-200">
            <button
              type="button"
              onClick={onClose}
              disabled={isSubmitting}
              className="px-4 py-2 text-xs font-medium text-slate-700 hover:bg-slate-100 rounded-lg transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isSubmitting}
              className="inline-flex items-center gap-2 px-5 py-2 text-xs font-semibold text-white bg-indigo-600 hover:bg-indigo-700 rounded-lg shadow-sm disabled:opacity-50 transition-colors"
            >
              {isSubmitting ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  <span>Saving Changes...</span>
                </>
              ) : (
                <span>Save Changes</span>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

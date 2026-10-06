import React, { useState } from "react";
import { ManagedAppCreateInput, ManagedAppDetail, ManagedAppPolicy } from "@/types/managedApp";
import { managedAppService } from "@/services/managedAppService";
import { formatApiError } from "@/types/runtime";
import { X, Package, AlertCircle, Loader2 } from "lucide-react";

interface ManagedAppCreateModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: (app: ManagedAppDetail) => void;
}

export function ManagedAppCreateModal({
  isOpen,
  onClose,
  onSuccess,
}: ManagedAppCreateModalProps) {
  const [key, setKey] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [packageName, setPackageName] = useState("");
  const [installPolicy, setInstallPolicy] = useState<ManagedAppPolicy>("optional");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleReset = () => {
    setKey("");
    setDisplayName("");
    setPackageName("");
    setInstallPolicy("optional");
    setErrorMessage(null);
    onClose();
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (isSubmitting) return;

    if (!key.trim()) {
      setErrorMessage("Please enter an application key.");
      return;
    }
    if (!displayName.trim()) {
      setErrorMessage("Please enter a display name.");
      return;
    }
    if (!packageName.trim()) {
      setErrorMessage("Please enter the Android package name.");
      return;
    }

    const payload: ManagedAppCreateInput = {
      key: key.trim(),
      display_name: displayName.trim(),
      android_package_name: packageName.trim(),
      install_policy: installPolicy,
    };

    try {
      setIsSubmitting(true);
      setErrorMessage(null);
      const app = await managedAppService.createManagedApp(payload);
      handleReset();
      onSuccess(app);
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
            <div className="w-9 h-9 rounded-lg bg-rose-100 text-rose-600 flex items-center justify-center font-bold">
              <Package className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-base font-bold text-slate-900">Add Managed App</h2>
              <p className="text-xs text-slate-500">
                Define an immutable Android application package for managed Runtimes.
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={handleReset}
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

          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">
              App Key <span className="text-rose-500">*</span>
            </label>
            <input
              type="text"
              required
              value={key}
              onChange={(e) => setKey(e.target.value)}
              placeholder="e.g. tiktok"
              className="w-full text-xs px-3 py-2 bg-white border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-rose-500 font-mono"
            />
            <p className="text-[11px] text-slate-400 mt-1">
              Immutable identifier used in workflow bindings (e.g. tiktok).
            </p>
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">
              Display Name <span className="text-rose-500">*</span>
            </label>
            <input
              type="text"
              required
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              placeholder="e.g. TikTok Global"
              className="w-full text-xs px-3 py-2 bg-white border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-rose-500"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">
              Android Package Name <span className="text-rose-500">*</span>
            </label>
            <input
              type="text"
              required
              value={packageName}
              onChange={(e) => setPackageName(e.target.value)}
              placeholder="e.g. com.zhiliaoapp.musically"
              className="w-full text-xs px-3 py-2 bg-white border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-rose-500 font-mono"
            />
            <p className="text-[11px] text-slate-400 mt-1">
              Exact Android package identity. Cannot be altered after creation.
            </p>
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">
              Install Policy <span className="text-rose-500">*</span>
            </label>
            <select
              value={installPolicy}
              onChange={(e) => setInstallPolicy(e.target.value as ManagedAppPolicy)}
              className="w-full text-xs px-3 py-2 bg-white border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-rose-500"
            >
              <option value="optional">Optional — installed per workflow request</option>
              <option value="required">Required — required for publishing readiness</option>
              <option value="disabled">Disabled — not eligible for installation</option>
            </select>
          </div>

          <div className="flex items-center justify-end gap-3 pt-4 border-t border-slate-200">
            <button
              type="button"
              onClick={handleReset}
              disabled={isSubmitting}
              className="px-4 py-2 text-xs font-medium text-slate-700 hover:bg-slate-100 rounded-lg transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isSubmitting}
              className="inline-flex items-center gap-2 px-5 py-2 text-xs font-semibold text-white bg-rose-600 hover:bg-rose-700 rounded-lg shadow-sm disabled:opacity-50 transition-colors"
            >
              {isSubmitting ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  <span>Creating App...</span>
                </>
              ) : (
                <span>Create Managed App</span>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

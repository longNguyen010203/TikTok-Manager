import React, { useEffect, useState, useRef } from "react";
import { Workflow, WorkflowCreateInput } from "@/types/workflow";
import { workflowService } from "@/services/workflowService";
import { runtimeService } from "@/services/runtimeService";
import { accountService } from "@/services/accountService";
import { contentService } from "@/services/contentService";
import { managedAppService } from "@/services/managedAppService";
import { Runtime } from "@/types/runtime";
import { Account, ApiError } from "@/types/account";
import { ContentAsset, ContentAssetDetail } from "@/types/content";
import { ManagedApp, ManagedAppDetail } from "@/types/managedApp";
import {
  X,
  Rocket,
  AlertCircle,
  AlertTriangle,
  Loader2,
  Users,
  Cpu,
  Video,
  Package,
  Sparkles,
} from "lucide-react";

interface PublishingPrepareModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: (workflow: Workflow) => void;
}

function generateFreshIdempotencyKey(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  return `pub-${Date.now()}-${Math.random().toString(36).substring(2, 9)}`;
}

function computeIntentSignature(
  runtimeId: number | null,
  accountId: number | null,
  contentAssetId: number | null,
  contentVersionId: number | null,
  managedAppId: number | null,
  managedAppVersionId: number | null,
  importMedia: boolean,
  name: string
): string {
  return JSON.stringify({
    runtimeId,
    accountId,
    contentAssetId,
    contentVersionId,
    managedAppId,
    managedAppVersionId,
    importMedia,
    name: name.trim(),
  });
}

export function PublishingPrepareModal({
  isOpen,
  onClose,
  onSuccess,
}: PublishingPrepareModalProps) {
  // References
  const [runtimes, setRuntimes] = useState<Runtime[]>([]);
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [contentAssets, setContentAssets] = useState<ContentAsset[]>([]);
  const [managedApps, setManagedApps] = useState<ManagedApp[]>([]);

  // Selected Content Detail & Managed App Detail for versions
  const [selectedAssetDetail, setSelectedAssetDetail] = useState<ContentAssetDetail | null>(null);
  const [selectedAppDetail, setSelectedAppDetail] = useState<ManagedAppDetail | null>(null);
  const [isLoadingAssetDetail, setIsLoadingAssetDetail] = useState(false);
  const [isLoadingAppDetail, setIsLoadingAppDetail] = useState(false);

  // Form selections
  const [workflowName, setWorkflowName] = useState("");
  const [workflowDescription, setWorkflowDescription] = useState("");
  const [selectedRuntimeId, setSelectedRuntimeId] = useState<number | null>(null);
  const [selectedAccountId, setSelectedAccountId] = useState<number | null>(null);
  const [selectedContentAssetId, setSelectedContentAssetId] = useState<number | null>(null);
  const [selectedContentVersionId, setSelectedContentVersionId] = useState<number | null>(null);
  const [selectedManagedAppId, setSelectedManagedAppId] = useState<number | null>(null);
  const [selectedManagedAppVersionId, setSelectedManagedAppVersionId] = useState<number | null>(null);
  const [importMedia, setImportMedia] = useState(true);

  // Status & Error
  const [isLoadingReferences, setIsLoadingReferences] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Idempotency state
  const idempotencyKeyRef = useRef<string>("");
  const lastSubmittedIntentRef = useRef<string | null>(null);

  const markIntentChanged = () => {
    if (lastSubmittedIntentRef.current !== null) {
      idempotencyKeyRef.current = generateFreshIdempotencyKey();
      lastSubmittedIntentRef.current = null;
    }
  };

  // Reset modal state
  const handleReset = () => {
    idempotencyKeyRef.current = "";
    lastSubmittedIntentRef.current = null;
    setErrorMessage(null);
    setWorkflowName("");
    setWorkflowDescription("");
    setSelectedRuntimeId(null);
    setSelectedAccountId(null);
    setSelectedContentAssetId(null);
    setSelectedContentVersionId(null);
    setSelectedManagedAppId(null);
    setSelectedManagedAppVersionId(null);
    setSelectedAssetDetail(null);
    setSelectedAppDetail(null);
    onClose();
  };

  // Load reference data on modal open
  useEffect(() => {
    if (!isOpen) {
      idempotencyKeyRef.current = "";
      lastSubmittedIntentRef.current = null;
      return;
    }

    idempotencyKeyRef.current = generateFreshIdempotencyKey();
    lastSubmittedIntentRef.current = null;

    Promise.all([
      runtimeService.getRuntimes({ page: 1, page_size: 100 }),
      accountService.getAccounts({ page: 1, page_size: 100 }),
      contentService.listContent({ page: 1, page_size: 100, status: "ready" }),
      managedAppService.getManagedApps({ page: 1, page_size: 100 }),
    ])
      .then(([rts, accs, assets, apps]) => {
        setRuntimes(rts.items);
        setAccounts(accs.items);
        setContentAssets(assets.items);
        setManagedApps(apps.items.filter((a) => a.status === "active"));

        if (rts.items.length > 0) {
          setSelectedRuntimeId(rts.items[0].id);
        }
        if (accs.items.length > 0) {
          setSelectedAccountId(accs.items[0].id);
        }
        if (assets.items.length > 0) {
          setSelectedContentAssetId(assets.items[0].id);
        }
        if (apps.items.length > 0) {
          setSelectedManagedAppId(apps.items[0].id);
        }
      })
      .catch((err: unknown) => {
        setErrorMessage(
          err && typeof err === "object" && "message" in err
            ? String((err as { message: unknown }).message)
            : "Failed to load references."
        );
      })
      .finally(() => {
        setIsLoadingReferences(false);
      });
  }, [isOpen]);

  // Load Content Asset versions when selectedContentAssetId changes
  useEffect(() => {
    if (!selectedContentAssetId) return;

    let ignore = false;
    contentService
      .getContent(selectedContentAssetId)
      .then((detail) => {
        if (ignore) return;
        setSelectedAssetDetail(detail);
        const readyVersions = detail.versions.filter((v) => v.processing_status === "ready");
        if (readyVersions.length > 0) {
          setSelectedContentVersionId(detail.current_version?.id || readyVersions[0].id);
        } else {
          setSelectedContentVersionId(null);
        }
      })
      .catch(() => {
        if (!ignore) setSelectedAssetDetail(null);
      })
      .finally(() => {
        if (!ignore) setIsLoadingAssetDetail(false);
      });

    return () => {
      ignore = true;
    };
  }, [selectedContentAssetId]);

  // Load Managed App details and versions when selectedManagedAppId changes
  useEffect(() => {
    if (!selectedManagedAppId) return;

    let ignore = false;
    managedAppService
      .getManagedApp(selectedManagedAppId)
      .then((detail) => {
        if (ignore) return;
        setSelectedAppDetail(detail);
        // Only install-eligible versions: ready, and either verified or basic_approved
        const eligibleVersions = detail.versions.filter(
          (v) => v.status === "ready" && (v.inspection_level === "verified" || v.basic_approved)
        );
        if (eligibleVersions.length > 0) {
          setSelectedManagedAppVersionId(
            eligibleVersions.some((v) => v.id === detail.current_version_id)
              ? detail.current_version_id
              : eligibleVersions[0].id
          );
        } else {
          setSelectedManagedAppVersionId(null);
        }
      })
      .catch(() => {
        if (!ignore) setSelectedAppDetail(null);
      })
      .finally(() => {
        if (!ignore) setIsLoadingAppDetail(false);
      });

    return () => {
      ignore = true;
    };
  }, [selectedManagedAppId]);

  if (!isOpen) return null;

  const selectedAccount = accounts.find((a) => a.id === selectedAccountId);

  // Mismatch check: if account is bound to a runtime that differs from selectedRuntime
  const hasAccountRuntimeMismatch =
    selectedAccount &&
    selectedAccount.runtime_id !== null &&
    selectedAccount.runtime_id !== undefined &&
    selectedRuntimeId !== null &&
    selectedAccount.runtime_id !== selectedRuntimeId;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (isSubmitting) return;

    if (!selectedAccountId) {
      setErrorMessage("Please select an Account for publishing preparation.");
      return;
    }
    if (!selectedRuntimeId) {
      setErrorMessage("Please select an explicit target Runtime.");
      return;
    }
    if (hasAccountRuntimeMismatch) {
      setErrorMessage(
        `Account "${selectedAccount?.username || selectedAccount?.id}" is assigned to Runtime #${selectedAccount?.runtime_id}, which does not match selected Runtime #${selectedRuntimeId}.`
      );
      return;
    }
    if (!selectedContentAssetId || !selectedContentVersionId) {
      setErrorMessage("Please select a ready Content Asset and exact version.");
      return;
    }
    if (!selectedManagedAppId || !selectedManagedAppVersionId) {
      setErrorMessage("Please select an install-eligible Managed App version.");
      return;
    }

    const finalName =
      workflowName.trim() ||
      `Publishing Prep — ${selectedAccount?.username || `Account #${selectedAccountId}`} [${new Date().toLocaleDateString()}]`;

    const currentIntent = computeIntentSignature(
      selectedRuntimeId,
      selectedAccountId,
      selectedContentAssetId,
      selectedContentVersionId,
      selectedManagedAppId,
      selectedManagedAppVersionId,
      importMedia,
      finalName
    );

    // Keep same key on unchanged retry, fresh key on intent change or first submit
    if (!idempotencyKeyRef.current) {
      idempotencyKeyRef.current = generateFreshIdempotencyKey();
    } else if (
      lastSubmittedIntentRef.current !== null &&
      lastSubmittedIntentRef.current !== currentIntent
    ) {
      idempotencyKeyRef.current = generateFreshIdempotencyKey();
    }

    lastSubmittedIntentRef.current = currentIntent;

    const payload: WorkflowCreateInput = {
      template_key: "publishing_prepare_review",
      template_version: 1,
      name: finalName,
      description: workflowDescription.trim() || null,
      runtime_id: selectedRuntimeId,
      account_id: selectedAccountId,
      content_asset_id: selectedContentAssetId,
      content_asset_version_id: selectedContentVersionId,
      managed_app_id: selectedManagedAppId,
      managed_app_version_id: selectedManagedAppVersionId,
      parameters: {
        import_media: importMedia,
      },
      idempotency_key: idempotencyKeyRef.current,
    };

    try {
      setIsSubmitting(true);
      setErrorMessage(null);
      const res = await workflowService.createWorkflow(payload);

      // Discard key on success
      idempotencyKeyRef.current = "";
      lastSubmittedIntentRef.current = null;
      setWorkflowName("");
      setWorkflowDescription("");
      onSuccess(res.workflow);
      onClose();
    } catch (err: unknown) {
      const isConflict =
        (err instanceof ApiError && err.code === "WORKFLOW_IDEMPOTENCY_CONFLICT") ||
        (err &&
          typeof err === "object" &&
          "code" in err &&
          (err as { code: unknown }).code === "WORKFLOW_IDEMPOTENCY_CONFLICT");

      if (isConflict) {
        idempotencyKeyRef.current = generateFreshIdempotencyKey();
        lastSubmittedIntentRef.current = null;
        setErrorMessage(
          "A submission conflict occurred with this request key. A fresh creation key has been generated. Please review your settings and click Prepare Publishing again."
        );
      } else {
        const message =
          err && typeof err === "object" && "message" in err
            ? String((err as { message: unknown }).message)
            : "Failed to prepare publishing workflow.";
        setErrorMessage(message);
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-xs overflow-y-auto">
      <div className="relative w-full max-w-2xl bg-white rounded-xl shadow-2xl border border-slate-200 overflow-hidden my-8 max-h-[92vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-200 bg-slate-50/50 shrink-0">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-lg bg-rose-100 text-rose-600 flex items-center justify-center font-bold">
              <Rocket className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-base font-bold text-slate-900">
                Prepare Publishing Session
              </h2>
              <p className="text-xs text-slate-500">
                Execute publishing_prepare_review:v1 to verify runtime &amp; app, deliver content, and prepare operator review.
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

        {/* Form Body */}
        <form onSubmit={handleSubmit} className="p-6 space-y-4 overflow-y-auto flex-1">
          {/* Safety Notice */}
          <div className="p-3 bg-amber-50 border border-amber-200 rounded-lg text-xs text-amber-900 space-y-1">
            <div className="flex items-center gap-2 font-bold text-amber-950">
              <Sparkles className="w-4 h-4 text-amber-600 shrink-0" />
              <span>Prepared Does Not Mean Published</span>
            </div>
            <p className="text-amber-800 leading-relaxed">
              This workflow stages the environment, delivers media, and launches the app. Final approval confirms preparation only; no automated posting or upload occurs.
            </p>
          </div>

          {errorMessage && (
            <div className="p-3 bg-rose-50 border border-rose-200 rounded-lg text-xs text-rose-700 flex items-start gap-2">
              <AlertCircle className="w-4 h-4 text-rose-600 shrink-0 mt-0.5" />
              <span>{errorMessage}</span>
            </div>
          )}

          {isLoadingReferences ? (
            <div className="py-12 flex flex-col items-center justify-center text-slate-400 gap-2">
              <Loader2 className="w-6 h-6 animate-spin text-rose-600" />
              <span className="text-xs">Loading accounts, runtimes, and assets...</span>
            </div>
          ) : (
            <>
              {/* Session / Workflow Name */}
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Preparation Name (optional)
                </label>
                <input
                  type="text"
                  value={workflowName}
                  onChange={(e) => {
                    setWorkflowName(e.target.value);
                    markIntentChanged();
                  }}
                  placeholder="e.g. Summer Promo — Account @creator"
                  className="w-full text-xs px-3 py-2 bg-white border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-rose-500"
                />
              </div>

              {/* Binding 1: Account Selection */}
              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1 flex items-center gap-1.5">
                  <Users className="w-3.5 h-3.5 text-slate-500" />
                  <span>1. Account</span>
                  <span className="text-rose-500">*</span>
                </label>
                <select
                  value={selectedAccountId ?? ""}
                  onChange={(e) => {
                    setSelectedAccountId(Number(e.target.value));
                    markIntentChanged();
                  }}
                  className="w-full text-xs px-3 py-2 bg-white border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-rose-500"
                >
                  {accounts.map((acc) => (
                    <option key={acc.id} value={acc.id}>
                      {acc.username} {acc.name ? `(${acc.name})` : ""} — ID #{acc.id}{" "}
                      {acc.runtime_id ? `[Bound to Runtime #${acc.runtime_id}]` : "[Unbound]"}
                    </option>
                  ))}
                </select>
              </div>

              {/* Binding 2: Explicit Runtime Selection */}
              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1 flex items-center gap-1.5">
                  <Cpu className="w-3.5 h-3.5 text-slate-500" />
                  <span>2. Target Runtime</span>
                  <span className="text-rose-500">*</span>
                </label>
                <select
                  value={selectedRuntimeId ?? ""}
                  onChange={(e) => {
                    setSelectedRuntimeId(Number(e.target.value));
                    markIntentChanged();
                  }}
                  className="w-full text-xs px-3 py-2 bg-white border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-rose-500"
                >
                  {runtimes.map((rt) => (
                    <option key={rt.id} value={rt.id}>
                      {rt.name} — Runtime #{rt.id} ({rt.status}) {rt.adb_serial ? `[${rt.adb_serial}]` : ""}
                    </option>
                  ))}
                </select>

                {/* Account-Runtime Mismatch Warning */}
                {hasAccountRuntimeMismatch && (
                  <div className="mt-2 p-2.5 bg-amber-50 border border-amber-200 rounded-lg text-xs text-amber-800 flex items-start gap-2">
                    <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
                    <span>
                      <strong>Account Mismatch:</strong> Selected account is assigned to Runtime #{selectedAccount?.runtime_id}, but Runtime #{selectedRuntimeId} is selected. The backend will reject this submission with ACCOUNT_RUNTIME_MISMATCH.
                    </span>
                  </div>
                )}
              </div>

              {/* Binding 3: Content Asset & Version */}
              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1 flex items-center gap-1.5">
                  <Video className="w-3.5 h-3.5 text-slate-500" />
                  <span>3. Content Asset &amp; Version</span>
                  <span className="text-rose-500">*</span>
                </label>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <select
                    value={selectedContentAssetId ?? ""}
                    onChange={(e) => {
                      setSelectedContentAssetId(Number(e.target.value));
                      setSelectedAssetDetail(null);
                      setSelectedContentVersionId(null);
                      markIntentChanged();
                    }}
                    className="w-full text-xs px-3 py-2 bg-white border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-rose-500"
                  >
                    {contentAssets.map((asset) => (
                      <option key={asset.id} value={asset.id}>
                        {asset.display_name} ({asset.asset_type})
                      </option>
                    ))}
                  </select>

                  <select
                    value={selectedContentVersionId ?? ""}
                    onChange={(e) => {
                      setSelectedContentVersionId(Number(e.target.value));
                      markIntentChanged();
                    }}
                    disabled={isLoadingAssetDetail || !selectedAssetDetail}
                    className="w-full text-xs px-3 py-2 bg-white border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-rose-500 disabled:bg-slate-100"
                  >
                    {selectedAssetDetail?.versions
                      .filter((v) => v.processing_status === "ready")
                      .map((ver) => (
                        <option key={ver.id} value={ver.id}>
                          v{ver.version_number} — {ver.original_filename} (ready)
                        </option>
                      ))}
                  </select>
                </div>
              </div>

              {/* Binding 4: Managed App & Version */}
              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1 flex items-center gap-1.5">
                  <Package className="w-3.5 h-3.5 text-slate-500" />
                  <span>4. Managed App &amp; Version</span>
                  <span className="text-rose-500">*</span>
                </label>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <select
                    value={selectedManagedAppId ?? ""}
                    onChange={(e) => {
                      setSelectedManagedAppId(Number(e.target.value));
                      setSelectedAppDetail(null);
                      setSelectedManagedAppVersionId(null);
                      markIntentChanged();
                    }}
                    className="w-full text-xs px-3 py-2 bg-white border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-rose-500"
                  >
                    {managedApps.map((app) => (
                      <option key={app.id} value={app.id}>
                        {app.display_name} ({app.key})
                      </option>
                    ))}
                  </select>

                  <select
                    value={selectedManagedAppVersionId ?? ""}
                    onChange={(e) => {
                      setSelectedManagedAppVersionId(Number(e.target.value));
                      markIntentChanged();
                    }}
                    disabled={isLoadingAppDetail || !selectedAppDetail}
                    className="w-full text-xs px-3 py-2 bg-white border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-rose-500 disabled:bg-slate-100"
                  >
                    {selectedAppDetail?.versions
                      .filter(
                        (v) =>
                          v.status === "ready" &&
                          (v.inspection_level === "verified" || v.basic_approved)
                      )
                      .map((ver) => (
                        <option key={ver.id} value={ver.id}>
                          v{ver.version_name || ver.id} ({ver.inspection_level}) — #{ver.id}
                        </option>
                      ))}
                  </select>
                </div>
              </div>

              {/* Parameter: import_media */}
              <div className="p-3 bg-slate-50 border border-slate-200 rounded-lg flex items-center gap-2">
                <input
                  type="checkbox"
                  id="pub_import_media"
                  checked={importMedia}
                  onChange={(e) => {
                    setImportMedia(e.target.checked);
                    markIntentChanged();
                  }}
                  className="w-4 h-4 text-rose-600 border-slate-300 rounded focus:ring-rose-500"
                />
                <label
                  htmlFor="pub_import_media"
                  className="text-xs font-medium text-slate-700 cursor-pointer"
                >
                  Index delivered media into Android MediaStore (Gallery visible)
                </label>
              </div>
            </>
          )}

          {/* Modal Footer */}
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
              disabled={isSubmitting || isLoadingReferences || !!hasAccountRuntimeMismatch}
              className="inline-flex items-center gap-2 px-5 py-2 text-xs font-semibold text-white bg-rose-600 hover:bg-rose-700 rounded-lg shadow-sm disabled:opacity-50 transition-colors"
            >
              {isSubmitting ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  <span>Preparing Publishing...</span>
                </>
              ) : (
                <span>Prepare Publishing</span>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

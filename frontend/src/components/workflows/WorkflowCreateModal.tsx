import React, { useEffect, useState, useRef } from "react";
import {
  AlertCircle,
  Cpu,
  FileText,
  FileVideo,
  FileImage,
  FileAudio,
  Info,
  Loader2,
  Sparkles,
  X,
} from "lucide-react";
import { workflowService } from "@/services/workflowService";
import { runtimeService } from "@/services/runtimeService";
import { deviceService } from "@/services/deviceService";
import { contentService } from "@/services/contentService";
import {
  Workflow,
  WorkflowCreateInput,
  WorkflowTemplate,
} from "@/types/workflow";
import { Runtime } from "@/types/runtime";
import { Device } from "@/types/device";
import { ContentAsset, ContentAssetDetail } from "@/types/content";
import { ApiError } from "@/types/account";

interface WorkflowCreateModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: (workflow: Workflow) => void;
}

/**
 * Generates a standard UUID idempotency key for workflow creation
 */
function generateFreshIdempotencyKey(): string {
  return typeof crypto !== "undefined" && crypto.randomUUID
    ? crypto.randomUUID()
    : `wf-${Date.now()}-${Math.random().toString(36).substring(2, 9)}`;
}

/**
 * Computes a normalized intent signature covering all material creation parameters.
 * Used to detect when creation intent changes after an attempt, requiring a fresh idempotency key.
 */
function computeIntentSignature(
  templateKey: string,
  templateVersion: number,
  runtimeId: number | null,
  contentAssetId: number | null,
  versionId: number | null,
  parameters: Record<string, unknown>,
  name: string,
  description: string
): string {
  return JSON.stringify({
    templateKey,
    templateVersion,
    runtimeId,
    contentAssetId,
    versionId,
    parameters,
    name: name.trim(),
    description: description.trim(),
  });
}

export function WorkflowCreateModal({
  isOpen,
  onClose,
  onSuccess,
}: WorkflowCreateModalProps) {
  // Data sources
  const [templates, setTemplates] = useState<WorkflowTemplate[]>([]);
  const [runtimes, setRuntimes] = useState<Runtime[]>([]);
  const [devicesMap, setDevicesMap] = useState<Record<number, Device>>({});
  const [contentAssets, setContentAssets] = useState<ContentAsset[]>([]);
  const [selectedAssetDetail, setSelectedAssetDetail] = useState<ContentAssetDetail | null>(null);

  // Loading states
  const [isLoadingReferences, setIsLoadingReferences] = useState(true);
  const [isLoadingAssetDetail, setIsLoadingAssetDetail] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Form State
  const [selectedTemplateKey, setSelectedTemplateKey] = useState<string>("");
  const [workflowName, setWorkflowName] = useState<string>("");
  const [workflowDescription, setWorkflowDescription] = useState<string>("");
  const [selectedRuntimeId, setSelectedRuntimeId] = useState<number | null>(null);
  const [selectedContentAssetId, setSelectedContentAssetId] = useState<number | null>(null);
  const [selectedVersionId, setSelectedVersionId] = useState<number | null>(null);

  // Template Parameters
  const [importMedia, setImportMedia] = useState<boolean>(true);
  const [waitDurationSeconds, setWaitDurationSeconds] = useState<number>(10);

  // Idempotency key lifecycle refs
  const idempotencyKeyRef = useRef<string>("");
  const lastSubmittedIntentRef = useRef<string | null>(null);

  // Helper called when user materially modifies creation intent
  const markIntentChanged = () => {
    if (lastSubmittedIntentRef.current !== null) {
      idempotencyKeyRef.current = generateFreshIdempotencyKey();
      lastSubmittedIntentRef.current = null;
    }
  };

  useEffect(() => {
    if (!isOpen) {
      idempotencyKeyRef.current = "";
      lastSubmittedIntentRef.current = null;
      return;
    }

    // Requirement 1: Generate a fresh idempotency key when Create Workflow modal is opened/reset
    idempotencyKeyRef.current = generateFreshIdempotencyKey();
    lastSubmittedIntentRef.current = null;

    let ignore = false;

    Promise.all([
      workflowService.getTemplates(),
      runtimeService.getRuntimes({ page: 1, page_size: 100 }),
      deviceService.getDevices({ page: 1, page_size: 100 }),
      contentService.listContent({ page: 1, page_size: 100, status: "ready" }),
    ])
      .then(([tpls, rts, devs, assets]) => {
        if (ignore) return;
        setTemplates(tpls);
        if (tpls.length > 0) {
          setSelectedTemplateKey((prev) => prev || tpls[0].key);
        }

        setRuntimes(rts.items);
        if (rts.items.length > 0) {
          setSelectedRuntimeId((prev) => prev || rts.items[0].id);
        }

        const devMap: Record<number, Device> = {};
        devs.items.forEach((d) => {
          devMap[d.id] = d;
        });
        setDevicesMap(devMap);

        setContentAssets(assets.items);
        if (assets.items.length > 0) {
          setSelectedContentAssetId((prev) => prev || assets.items[0].id);
        }
      })
      .catch((err) => {
        if (ignore) return;
        setErrorMessage(
          err && typeof err === "object" && "message" in err
            ? String((err as { message: unknown }).message)
            : "Failed to load reference data"
        );
      })
      .finally(() => {
        if (!ignore) setIsLoadingReferences(false);
      });

    return () => {
      ignore = true;
    };
  }, [isOpen]);

  // Load versions whenever selected content asset changes
  useEffect(() => {
    if (!selectedContentAssetId) return;

    let ignore = false;

    contentService
      .getContent(selectedContentAssetId)
      .then((detail) => {
        if (ignore) return;
        setSelectedAssetDetail(detail);
        if (detail.current_version?.id) {
          setSelectedVersionId(detail.current_version.id);
        } else if (detail.versions.length > 0) {
          setSelectedVersionId(detail.versions[0].id);
        }
      })
      .catch(() => {
        if (ignore) return;
        setSelectedAssetDetail(null);
        setSelectedVersionId(null);
      })
      .finally(() => {
        if (!ignore) setIsLoadingAssetDetail(false);
      });

    return () => {
      ignore = true;
    };
  }, [selectedContentAssetId]);

  if (!isOpen) return null;

  const currentTemplate = templates.find((t) => t.key === selectedTemplateKey);
  const selectedRuntime = runtimes.find((r) => r.id === selectedRuntimeId);
  const selectedDevice = selectedRuntime
    ? devicesMap[selectedRuntime.device_id]
    : null;

  const handleClose = () => {
    idempotencyKeyRef.current = "";
    lastSubmittedIntentRef.current = null;
    setErrorMessage(null);
    setWorkflowName("");
    setWorkflowDescription("");
    onClose();
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    // Requirement 2: Disable duplicate submit while request is in flight
    if (isSubmitting) return;

    if (!selectedTemplateKey || !workflowName.trim()) {
      setErrorMessage("Please specify a workflow name and template.");
      return;
    }
    if (!selectedRuntimeId) {
      setErrorMessage("Please select a target Runtime.");
      return;
    }
    if (!selectedContentAssetId) {
      setErrorMessage("Please select a Content Asset.");
      return;
    }

    // Build parameters based on template
    const parameters: Record<string, unknown> = {
      import_media: importMedia,
    };

    if (selectedTemplateKey === "content_delivery_wait_review") {
      if (
        isNaN(waitDurationSeconds) ||
        waitDurationSeconds < 1 ||
        waitDurationSeconds > 86400
      ) {
        setErrorMessage("Wait duration must be between 1 and 86,400 seconds.");
        return;
      }
      parameters.wait_duration_seconds = waitDurationSeconds;
    }

    // Requirement 4: Compute intent signature
    const currentIntent = computeIntentSignature(
      selectedTemplateKey,
      currentTemplate?.version ?? 1,
      selectedRuntimeId,
      selectedContentAssetId,
      selectedVersionId,
      parameters,
      workflowName,
      workflowDescription
    );

    // If no key exists yet, or if intent materially changed since the last attempt:
    // generate a fresh key before this submission.
    // If intent is identical to previous attempt (e.g. unchanged retry after network error),
    // keep the EXACT same key!
    if (!idempotencyKeyRef.current) {
      idempotencyKeyRef.current = generateFreshIdempotencyKey();
    } else if (
      lastSubmittedIntentRef.current !== null &&
      lastSubmittedIntentRef.current !== currentIntent
    ) {
      idempotencyKeyRef.current = generateFreshIdempotencyKey();
    }

    // Record the intent associated with this key
    lastSubmittedIntentRef.current = currentIntent;

    const payload: WorkflowCreateInput = {
      template_key: selectedTemplateKey,
      template_version: currentTemplate?.version ?? 1,
      name: workflowName.trim(),
      description: workflowDescription.trim() || null,
      runtime_id: selectedRuntimeId,
      content_asset_id: selectedContentAssetId,
      content_asset_version_id: selectedVersionId,
      parameters,
      idempotency_key: idempotencyKeyRef.current,
    };

    try {
      setIsSubmitting(true);
      setErrorMessage(null);
      const res = await workflowService.createWorkflow(payload);

      // Requirement 3: After successful workflow creation, close/reset modal, discard key
      idempotencyKeyRef.current = "";
      lastSubmittedIntentRef.current = null;
      setErrorMessage(null);
      setWorkflowName("");
      setWorkflowDescription("");
      onSuccess(res.workflow);
      onClose();
    } catch (err: unknown) {
      // Requirement 5: If backend returns WORKFLOW_IDEMPOTENCY_CONFLICT
      const isConflict =
        (err instanceof ApiError &&
          err.code === "WORKFLOW_IDEMPOTENCY_CONFLICT") ||
        (err &&
          typeof err === "object" &&
          "code" in err &&
          (err as { code: unknown }).code === "WORKFLOW_IDEMPOTENCY_CONFLICT") ||
        (err &&
          typeof err === "object" &&
          "message" in err &&
          String((err as { message: unknown }).message)
            .toLowerCase()
            .includes("idempotency"));

      if (isConflict) {
        // Refresh / generate a fresh creation key for the next explicit submit
        idempotencyKeyRef.current = generateFreshIdempotencyKey();
        lastSubmittedIntentRef.current = null;
        setErrorMessage(
          "A submission conflict occurred with this request key. A fresh creation key has been generated. Please review your settings and click Create Workflow again."
        );
      } else {
        setErrorMessage(
          err && typeof err === "object" && "message" in err
            ? String((err as { message: unknown }).message)
            : "Failed to create workflow. Please check your inputs."
        );
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  const getMediaIcon = (type?: string) => {
    switch (type) {
      case "video":
        return <FileVideo className="w-4 h-4 text-purple-600" />;
      case "image":
        return <FileImage className="w-4 h-4 text-emerald-600" />;
      case "audio":
        return <FileAudio className="w-4 h-4 text-amber-600" />;
      default:
        return <FileText className="w-4 h-4 text-slate-500" />;
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-xs overflow-y-auto">
      <div className="relative w-full max-w-2xl bg-white rounded-xl shadow-2xl border border-slate-200 overflow-hidden my-8">
        {/* Modal Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-200 bg-slate-50/50">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-lg bg-rose-100 text-rose-600 flex items-center justify-center font-bold">
              <Sparkles className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-base font-bold text-slate-900">
                Create Managed Workflow
              </h2>
              <p className="text-xs text-slate-500">
                Select a server-owned template and configure pinned bindings.
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={handleClose}
            className="p-1 rounded-md text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Modal Body / Form */}
        <form onSubmit={handleSubmit} className="p-6 space-y-5">
          {errorMessage && (
            <div className="p-3 bg-rose-50 border border-rose-200 rounded-lg text-xs text-rose-700 flex items-start gap-2">
              <AlertCircle className="w-4 h-4 text-rose-600 shrink-0 mt-0.5" />
              <span>{errorMessage}</span>
            </div>
          )}

          {isLoadingReferences ? (
            <div className="py-12 flex flex-col items-center justify-center text-slate-400 gap-2">
              <Loader2 className="w-6 h-6 animate-spin text-rose-600" />
              <span className="text-xs">Loading available templates and resources...</span>
            </div>
          ) : (
            <>
              {/* Step 1: Template Selection */}
              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-2">
                  1. Workflow Template
                </label>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  {templates.map((tpl) => {
                    const isSelected = tpl.key === selectedTemplateKey;
                    return (
                      <div
                        key={tpl.key}
                        onClick={() => {
                          if (tpl.key !== selectedTemplateKey) {
                            setSelectedTemplateKey(tpl.key);
                            markIntentChanged();
                          }
                        }}
                        className={`cursor-pointer rounded-lg border p-3.5 transition-all text-left ${
                          isSelected
                            ? "border-rose-500 bg-rose-50/50 shadow-xs ring-1 ring-rose-300"
                            : "border-slate-200 bg-white hover:border-slate-300 hover:bg-slate-50"
                        }`}
                      >
                        <div className="flex items-center justify-between">
                          <h4 className="text-xs font-bold text-slate-900">
                            {tpl.label}
                          </h4>
                          <span className="text-[10px] font-mono px-1.5 py-0.5 bg-slate-100 border border-slate-200 rounded text-slate-600">
                            v{tpl.version}
                          </span>
                        </div>
                        <p className="text-[11px] text-slate-500 mt-1 line-clamp-2">
                          {tpl.description}
                        </p>
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* Step 2: Basic Info */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">
                    Workflow Name <span className="text-rose-500">*</span>
                  </label>
                  <input
                    type="text"
                    required
                    value={workflowName}
                    onChange={(e) => {
                      setWorkflowName(e.target.value);
                      markIntentChanged();
                    }}
                    placeholder="e.g. Autumn Promo Delivery & Review"
                    className="w-full text-xs px-3 py-2 bg-white border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-rose-500"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">
                    Description (optional)
                  </label>
                  <input
                    type="text"
                    value={workflowDescription}
                    onChange={(e) => {
                      setWorkflowDescription(e.target.value);
                      markIntentChanged();
                    }}
                    placeholder="e.g. Automated push to Device 02"
                    className="w-full text-xs px-3 py-2 bg-white border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-rose-500"
                  />
                </div>
              </div>

              {/* Step 3: Target Runtime Selection */}
              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1">
                  2. Target Runtime <span className="text-rose-500">*</span>
                </label>
                <div className="space-y-1">
                  <select
                    value={selectedRuntimeId ?? ""}
                    onChange={(e) => {
                      setSelectedRuntimeId(Number(e.target.value));
                      markIntentChanged();
                    }}
                    className="w-full text-xs px-3 py-2 bg-white border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-rose-500"
                  >
                    {runtimes.map((rt) => {
                      const dev = devicesMap[rt.device_id];
                      const devName = dev?.name || `Device #${rt.device_id}`;
                      return (
                        <option key={rt.id} value={rt.id}>
                          {devName} — Runtime #{rt.id} ({rt.status}) {rt.adb_serial ? `[${rt.adb_serial}]` : ""}
                        </option>
                      );
                    })}
                  </select>

                  {/* Runtime Status notice */}
                  {selectedRuntime && (
                    <div
                      className={`text-[11px] p-2 rounded-md flex items-center justify-between ${
                        selectedRuntime.status === "running"
                          ? "bg-emerald-50 text-emerald-800 border border-emerald-200"
                          : "bg-amber-50 text-amber-800 border border-amber-200"
                      }`}
                    >
                      <div className="flex items-center gap-1.5">
                        <Cpu className="w-3.5 h-3.5 shrink-0" />
                        <span>
                          {selectedDevice?.name || `Device #${selectedRuntime.device_id}`}:{" "}
                          <strong>{selectedRuntime.status}</strong>
                        </span>
                      </div>
                      <span className="font-mono text-[10px]">
                        {selectedRuntime.docker_container_name || "native"}
                      </span>
                    </div>
                  )}

                  {selectedRuntime && selectedRuntime.status !== "running" && (
                    <p className="text-[11px] text-amber-700 flex items-center gap-1 mt-1">
                      <Info className="w-3 h-3 shrink-0" />
                      <span>
                        Target runtime is currently stopped. Workflow creation will succeed, but execution will require starting the device.
                      </span>
                    </p>
                  )}
                </div>
              </div>

              {/* Step 4: Content Asset & Pinned Version */}
              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1">
                  3. Content Asset & Version <span className="text-rose-500">*</span>
                </label>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <div>
                    <label className="block text-[11px] font-medium text-slate-600 mb-1">
                      Content Asset
                    </label>
                    <select
                      value={selectedContentAssetId ?? ""}
                      onChange={(e) => {
                        setSelectedContentAssetId(Number(e.target.value));
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
                  </div>

                  <div>
                    <label className="block text-[11px] font-medium text-slate-600 mb-1">
                      Pinned Version
                    </label>
                    <select
                      value={selectedVersionId ?? ""}
                      onChange={(e) => {
                        setSelectedVersionId(Number(e.target.value));
                        markIntentChanged();
                      }}
                      disabled={isLoadingAssetDetail || !selectedAssetDetail}
                      className="w-full text-xs px-3 py-2 bg-white border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-rose-500 disabled:bg-slate-100"
                    >
                      {selectedAssetDetail?.versions.map((ver) => (
                        <option key={ver.id} value={ver.id}>
                          v{ver.version_number} — {ver.original_filename} (
                          {ver.processing_status})
                        </option>
                      ))}
                    </select>
                  </div>
                </div>

                {/* Selected Asset Details Snapshot */}
                {selectedAssetDetail && (
                  <div className="mt-2 p-2.5 bg-slate-50 border border-slate-200 rounded-lg flex items-center justify-between text-xs">
                    <div className="flex items-center gap-2">
                      {getMediaIcon(selectedAssetDetail.asset_type)}
                      <div>
                        <span className="font-medium text-slate-800">
                          {selectedAssetDetail.display_name}
                        </span>
                        <span className="text-[11px] text-slate-500 ml-1.5 font-mono">
                          (v{selectedAssetDetail.current_version?.version_number ?? 1})
                        </span>
                      </div>
                    </div>
                    <span className="text-[11px] px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-800 font-medium">
                      Ready
                    </span>
                  </div>
                )}
              </div>

              {/* Step 5: Template-Specific Parameters */}
              <div className="p-3.5 bg-slate-50/80 border border-slate-200 rounded-lg space-y-3">
                <h4 className="text-xs font-semibold text-slate-700 uppercase tracking-wider">
                  Template Parameters
                </h4>

                <div className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    id="import_media"
                    checked={importMedia}
                    onChange={(e) => {
                      setImportMedia(e.target.checked);
                      markIntentChanged();
                    }}
                    className="w-4 h-4 text-rose-600 border-slate-300 rounded focus:ring-rose-500"
                  />
                  <label
                    htmlFor="import_media"
                    className="text-xs font-medium text-slate-700 cursor-pointer"
                  >
                    Index into Android MediaStore (Gallery visible)
                  </label>
                </div>

                {selectedTemplateKey === "content_delivery_wait_review" && (
                  <div>
                    <label className="block text-xs font-medium text-slate-700 mb-1">
                      Wait Duration (seconds)
                    </label>
                    <input
                      type="number"
                      min={1}
                      max={86400}
                      value={waitDurationSeconds}
                      onChange={(e) => {
                        setWaitDurationSeconds(parseInt(e.target.value) || 0);
                        markIntentChanged();
                      }}
                      className="w-40 text-xs px-3 py-1.5 bg-white border border-slate-300 rounded-md focus:outline-none focus:ring-2 focus:ring-rose-500 font-mono"
                    />
                    <p className="text-[11px] text-slate-500 mt-1">
                      Duration to pause before triggering operator approval review (1 - 86,400s).
                    </p>
                  </div>
                )}
              </div>
            </>
          )}

          {/* Modal Footer */}
          <div className="flex items-center justify-end gap-3 pt-4 border-t border-slate-200">
            <button
              type="button"
              onClick={handleClose}
              disabled={isSubmitting}
              className="px-4 py-2 text-xs font-medium text-slate-700 hover:bg-slate-100 rounded-lg transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isSubmitting || isLoadingReferences}
              className="inline-flex items-center gap-2 px-5 py-2 text-xs font-semibold text-white bg-rose-600 hover:bg-rose-700 rounded-lg shadow-sm disabled:opacity-50 transition-colors"
            >
              {isSubmitting ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  <span>Creating Workflow...</span>
                </>
              ) : (
                <span>Create Workflow</span>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

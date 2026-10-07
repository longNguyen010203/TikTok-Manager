"use client";

import React, { useState, useEffect, useCallback } from "react";
import {
  X,
  KeyRound,
  ShieldCheck,
  ShieldAlert,
  Loader2,
  Trash2,
  CheckCircle2,
  Eye,
  EyeOff,
  AlertCircle,
  Lock,
} from "lucide-react";
import {
  Account,
  AccountSecretMetadata,
  AccountSecretType,
  formatApiError,
  getSecretTypeDescription,
  getSecretTypeLabel,
} from "@/types/account";
import { accountService } from "@/services/accountService";

interface AccountSecretsModalProps {
  account: Account | null;
  isOpen: boolean;
  onClose: () => void;
  onAccountUpdated?: () => void;
}

const SUPPORTED_SECRET_TYPES: AccountSecretType[] = [
  "account_password",
  "email_password",
  "recovery_credential",
];

interface AccountSecretsModalContentProps {
  account: Account;
  onClose: () => void;
  onAccountUpdated?: () => void;
}

function AccountSecretsModalContent({
  account,
  onClose,
  onAccountUpdated,
}: AccountSecretsModalContentProps) {
  const [secrets, setSecrets] = useState<AccountSecretMetadata[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  // Active edit state: which secret_type is currently having a value entered
  const [editingType, setEditingType] = useState<AccountSecretType | null>(null);
  const [inputValue, setInputValue] = useState("");
  const [showInputText, setShowInputText] = useState(false);
  const [isSaving, setIsSaving] = useState(false);

  // Active delete confirmation state
  const [deletingType, setDeletingType] = useState<AccountSecretType | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);

  const fetchSecrets = useCallback(async () => {
    try {
      setIsLoading(true);
      setErrorMessage(null);
      const res = await accountService.getAccountSecrets(account.id);
      setSecrets(res);
    } catch (err: unknown) {
      setErrorMessage(formatApiError(err));
    } finally {
      setIsLoading(false);
    }
  }, [account.id]);

  useEffect(() => {
    let ignore = false;
    accountService
      .getAccountSecrets(account.id)
      .then((res) => {
        if (!ignore) {
          setSecrets(res);
        }
      })
      .catch((err: unknown) => {
        if (!ignore) {
          setErrorMessage(formatApiError(err));
        }
      })
      .finally(() => {
        if (!ignore) {
          setIsLoading(false);
        }
      });

    return () => {
      ignore = true;
    };
  }, [account.id]);

  const handleStartEdit = (type: AccountSecretType) => {
    setEditingType(type);
    setInputValue("");
    setShowInputText(false);
    setDeletingType(null);
    setErrorMessage(null);
    setSuccessMessage(null);
  };

  const handleCancelEdit = () => {
    setEditingType(null);
    setInputValue("");
    setShowInputText(false);
  };

  const handleSaveSecret = async (type: AccountSecretType) => {
    if (!inputValue.trim()) {
      setErrorMessage("Please enter a non-empty credential value.");
      return;
    }

    try {
      setIsSaving(true);
      setErrorMessage(null);
      await accountService.putAccountSecret(account.id, type, inputValue.trim());

      // Immediate wipe of local secret input
      setInputValue("");
      setEditingType(null);
      setShowInputText(false);
      setSuccessMessage(`${getSecretTypeLabel(type)} saved securely.`);
      await fetchSecrets();
      onAccountUpdated?.();
    } catch (err: unknown) {
      setErrorMessage(formatApiError(err));
    } finally {
      setIsSaving(false);
    }
  };

  const handleDeleteSecret = async (type: AccountSecretType) => {
    try {
      setIsDeleting(true);
      setErrorMessage(null);
      await accountService.deleteAccountSecret(account.id, type);

      setDeletingType(null);
      setSuccessMessage(`${getSecretTypeLabel(type)} removed.`);
      await fetchSecrets();
      onAccountUpdated?.();
    } catch (err: unknown) {
      setErrorMessage(formatApiError(err));
    } finally {
      setIsDeleting(false);
    }
  };

  const formatDate = (isoString?: string | null) => {
    if (!isoString) return null;
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

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-xs">
      <div
        className="bg-white rounded-2xl shadow-2xl border border-slate-200 w-full max-w-xl overflow-hidden transition-all animate-in fade-in zoom-in-95 duration-150 max-h-[92vh] flex flex-col"
        role="dialog"
        aria-modal="true"
        aria-labelledby="secrets-modal-title"
      >
        {/* Header */}
        <div className="px-6 py-4 border-b border-slate-200 bg-slate-50/70 flex items-center justify-between shrink-0">
          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded-xl bg-emerald-100 text-emerald-700">
              <KeyRound className="w-5 h-5" />
            </div>
            <div>
              <h3
                id="secrets-modal-title"
                className="text-sm font-bold text-slate-900 flex items-center gap-2"
              >
                <span>Credentials &amp; Secrets Control</span>
                <span className="font-mono text-xs px-2 py-0.5 rounded-full bg-slate-200/80 text-slate-700 font-semibold">
                  Account #{account.id}
                </span>
              </h3>
              <p className="text-xs text-slate-500">
                @{account.username || "no-handle"} ({account.display_name || account.name})
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-1 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition-colors"
            aria-label="Close credentials modal"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Security Assurance Banner */}
        <div className="px-6 py-3 bg-emerald-50/80 border-b border-emerald-200/80 text-emerald-950 flex items-center gap-2.5 text-xs shrink-0">
          <Lock className="w-4 h-4 text-emerald-600 shrink-0" />
          <p className="font-medium text-emerald-900 text-xs">
            Credentials are encrypted at rest and are never returned by the API.
          </p>
        </div>

        {/* Modal Body */}
        <div className="p-6 overflow-y-auto space-y-4 flex-1">
          {errorMessage && (
            <div className="p-3 bg-rose-50 border border-rose-200 rounded-xl text-xs text-rose-800 flex items-start gap-2">
              <AlertCircle className="w-4 h-4 text-rose-600 shrink-0 mt-0.5" />
              <span>{errorMessage}</span>
            </div>
          )}

          {successMessage && (
            <div className="p-3 bg-emerald-50 border border-emerald-200 rounded-xl text-xs text-emerald-800 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
                <span>{successMessage}</span>
              </div>
              <button
                type="button"
                onClick={() => setSuccessMessage(null)}
                className="text-emerald-700 hover:text-emerald-900 font-bold ml-2"
              >
                &times;
              </button>
            </div>
          )}

          {isLoading ? (
            <div className="py-12 flex flex-col items-center justify-center text-slate-400 gap-2">
              <Loader2 className="w-6 h-6 animate-spin text-emerald-600" />
              <span className="text-xs">Loading credential status...</span>
            </div>
          ) : (
            <div className="space-y-3">
              {SUPPORTED_SECRET_TYPES.map((type) => {
                const found = secrets.find((s) => s.secret_type === type);
                const isPresent = Boolean(found?.present);
                const isEditingThis = editingType === type;
                const isDeletingThis = deletingType === type;

                return (
                  <div
                    key={type}
                    className="p-4 rounded-xl border border-slate-200 bg-white hover:border-slate-300 transition-all space-y-3"
                  >
                    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                      <div className="space-y-0.5">
                        <div className="flex items-center gap-2">
                          <span className="font-semibold text-slate-900 text-xs">
                            {getSecretTypeLabel(type)}
                          </span>
                          {isPresent ? (
                            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
                              <ShieldCheck className="w-3 h-3 text-emerald-600" />
                              <span>Configured</span>
                            </span>
                          ) : (
                            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium bg-slate-100 text-slate-500 border border-slate-200">
                              <ShieldAlert className="w-3 h-3 text-slate-400" />
                              <span>Not Set</span>
                            </span>
                          )}
                        </div>
                        <p className="text-[11px] text-slate-500">
                          {getSecretTypeDescription(type)}
                        </p>
                        {isPresent && found?.updated_at && (
                          <p className="text-[10px] text-slate-400 font-mono">
                            Last updated: {formatDate(found.updated_at)}
                          </p>
                        )}
                      </div>

                      {/* Top Action Buttons (when not actively editing or deleting) */}
                      {!isEditingThis && !isDeletingThis && (
                        <div className="flex items-center gap-2 self-start sm:self-center shrink-0">
                          <button
                            type="button"
                            onClick={() => handleStartEdit(type)}
                            className="px-3 py-1.5 text-xs font-semibold rounded-lg text-emerald-700 bg-emerald-50 hover:bg-emerald-100 border border-emerald-200 transition-colors"
                          >
                            {isPresent ? "Replace Value" : "Configure"}
                          </button>
                          {isPresent && (
                            <button
                              type="button"
                              onClick={() => setDeletingType(type)}
                              className="p-1.5 text-slate-400 hover:text-rose-600 hover:bg-rose-50 rounded-lg border border-slate-200 transition-colors"
                              title={`Delete ${getSecretTypeLabel(type)}`}
                              aria-label={`Delete ${getSecretTypeLabel(type)}`}
                            >
                              <Trash2 className="w-3.5 h-3.5" />
                            </button>
                          )}
                        </div>
                      )}
                    </div>

                    {/* Inline Edit Form */}
                    {isEditingThis && (
                      <div className="pt-2 border-t border-slate-100 space-y-2.5 animate-in fade-in duration-100">
                        <label className="block text-[11px] font-medium text-slate-700">
                          Enter New Secret Value (never shown after save):
                        </label>
                        <div className="relative">
                          <input
                            type={showInputText ? "text" : "password"}
                            value={inputValue}
                            onChange={(e) => setInputValue(e.target.value)}
                            placeholder={`Enter ${getSecretTypeLabel(type).toLowerCase()}...`}
                            autoComplete="new-password"
                            autoFocus
                            disabled={isSaving}
                            className="w-full text-xs px-3 py-2 pr-9 bg-slate-50 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:bg-white transition-all font-mono"
                          />
                          <button
                            type="button"
                            onClick={() => setShowInputText((prev) => !prev)}
                            className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
                            title={showInputText ? "Hide characters" : "Show characters"}
                          >
                            {showInputText ? (
                              <EyeOff className="w-3.5 h-3.5" />
                            ) : (
                              <Eye className="w-3.5 h-3.5" />
                            )}
                          </button>
                        </div>

                        <div className="flex items-center justify-end gap-2 pt-1">
                          <button
                            type="button"
                            onClick={handleCancelEdit}
                            disabled={isSaving}
                            className="px-3 py-1.5 text-xs font-medium text-slate-600 hover:bg-slate-100 rounded-lg transition-colors"
                          >
                            Cancel
                          </button>
                          <button
                            type="button"
                            onClick={() => handleSaveSecret(type)}
                            disabled={isSaving || !inputValue.trim()}
                            className="inline-flex items-center gap-1.5 px-3.5 py-1.5 text-xs font-semibold text-white bg-emerald-600 hover:bg-emerald-700 rounded-lg shadow-2xs transition-colors disabled:opacity-50"
                          >
                            {isSaving ? (
                              <>
                                <Loader2 className="w-3.5 h-3.5 animate-spin" />
                                <span>Saving Encrypted...</span>
                              </>
                            ) : (
                              <span>Save Credential</span>
                            )}
                          </button>
                        </div>
                      </div>
                    )}

                    {/* Inline Delete Confirmation */}
                    {isDeletingThis && (
                      <div className="pt-2 border-t border-rose-100 bg-rose-50/50 p-3 rounded-lg space-y-2 animate-in fade-in duration-100">
                        <p className="text-xs text-rose-800 font-medium">
                          Are you sure you want to delete {getSecretTypeLabel(type)}?
                          Automation tasks relying on this credential will fail until updated.
                        </p>
                        <div className="flex items-center justify-end gap-2">
                          <button
                            type="button"
                            onClick={() => setDeletingType(null)}
                            disabled={isDeleting}
                            className="px-2.5 py-1 text-xs font-medium text-slate-600 hover:bg-slate-200 rounded"
                          >
                            Cancel
                          </button>
                          <button
                            type="button"
                            onClick={() => handleDeleteSecret(type)}
                            disabled={isDeleting}
                            className="inline-flex items-center gap-1 px-3 py-1 text-xs font-semibold text-white bg-rose-600 hover:bg-rose-700 rounded shadow-2xs disabled:opacity-50"
                          >
                            {isDeleting ? (
                              <Loader2 className="w-3 h-3 animate-spin" />
                            ) : (
                              <Trash2 className="w-3 h-3" />
                            )}
                            <span>Confirm Delete</span>
                          </button>
                        </div>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-3 border-t border-slate-200 bg-slate-50 flex items-center justify-between shrink-0">
          <span className="text-[11px] text-slate-400 font-mono">
            Credentials are encrypted at rest and are never returned by the API.
          </span>
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-1.5 text-xs font-medium text-slate-700 bg-white hover:bg-slate-100 border border-slate-200 rounded-lg transition-colors shadow-2xs"
          >
            Done
          </button>
        </div>
      </div>
    </div>
  );
}

export function AccountSecretsModal({
  account,
  isOpen,
  onClose,
  onAccountUpdated,
}: AccountSecretsModalProps) {
  if (!isOpen || !account) return null;

  return (
    <AccountSecretsModalContent
      key={account.id}
      account={account}
      onClose={onClose}
      onAccountUpdated={onAccountUpdated}
    />
  );
}

/**
 * Managed Redroid provisioning types matching docs/API_CONTRACT.md
 * and backend/app/schemas/redroid_provisioning.py
 */

import { ApiError, ValidationErrorDetail } from "./account";

export type ProvisioningState =
  | "requested"
  | "preflighting"
  | "reserved"
  | "data_created"
  | "network_created"
  | "container_created"
  | "inspected"
  | "completed"
  | "rolling_back"
  | "rolled_back"
  | "failed"
  | "rollback_failed"
  | "inconsistent"
  | "deprovisioning"
  | "deprovisioned"
  | "deprovision_failed";

export interface RedroidProvisionRequest {
  name: string;
  notes?: string | null;
  profile: string;
}

export interface RedroidProvisioningStatus {
  provisioning_id: string;
  state: ProvisioningState | string;
  device_number: number | null;
  container_name: string | null;
  adb_serial: string | null;
  data_path: string | null;
  network_name: string | null;
  image_reference: string;
  device_id: number | null;
  runtime_id: number | null;
  data_directory_created: boolean;
  network_created: boolean;
  container_created: boolean;
  container_removed?: boolean;
  network_removed?: boolean;
  data_preserved?: boolean;
  error_code: string | null;
  error_message: string | null;
  created_at: string;
  updated_at: string;
}

export interface RedroidDeprovisioningStatus {
  provisioning_id: string;
  state: ProvisioningState | string;
  container_removed: boolean;
  network_removed: boolean;
  data_preserved: boolean;
  data_path: string | null;
  device_id: number | null;
  runtime_id: number | null;
  error_code: string | null;
  error_message: string | null;
  created_at: string;
  updated_at: string;
}

export class ProvisioningApiError extends ApiError {
  provisioningId?: string;
  deprovisionStatus?: RedroidDeprovisioningStatus;

  constructor(
    status: number,
    message: string,
    provisioningId?: string,
    details?: ValidationErrorDetail[] | string,
    deprovisionStatus?: RedroidDeprovisioningStatus
  ) {
    super(status, message, details);
    this.name = "ProvisioningApiError";
    this.provisioningId = provisioningId;
    this.deprovisionStatus = deprovisionStatus;
  }
}


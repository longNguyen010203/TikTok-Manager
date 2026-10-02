/**
 * Device types matching docs/API_CONTRACT.md and backend/app/schemas/device.py
 */

import { ApiError, formatApiError, ValidationErrorDetail } from "./account";

export type DeviceStatus = "online" | "offline" | "busy" | "error" | string;
export type DeviceType = "physical" | "emulator" | "cloud" | string;
export type DevicePlatform = "android" | "ios" | string;

export interface Device {
  id: number;
  name: string;
  device_type: DeviceType;
  platform: DevicePlatform;
  os_version: string;
  status: DeviceStatus;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface DeviceListParams {
  page?: number;
  page_size?: number;
}

export interface DeviceListResponse {
  items: Device[];
  total: number;
  page: number;
  page_size: number;
}

export interface CreateDeviceInput {
  name: string;
  device_type: string;
  platform: string;
  os_version: string;
  status: string;
  notes?: string | null;
}

export interface UpdateDeviceInput {
  name?: string;
  device_type?: string;
  platform?: string;
  os_version?: string;
  status?: string;
  notes?: string | null;
}

export interface DeviceLifecycleStatus {
  device_id: number;
  runtime_id: number;
  docker_container_name: string;
  adb_serial: string;
  container_status: string;
  boot_completed: boolean;
  adb_state: string;
  ready: boolean;
  runtime_status: string;
  device_status: string;
}

export interface DeviceScreenStatus {
  device_id: number;
  runtime_id: number;
  adb_serial: string;
  status: "open" | "closed" | string;
  process_id: number | null;
}

export { ApiError, formatApiError };
export type { ValidationErrorDetail };

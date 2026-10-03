import { RedroidProvisioningStatus, RedroidDeprovisioningStatus } from "@/types/provisioning";

export interface ManagedProvisioningRecord {
  provisioningId: string;
  deviceId: number;
  runtimeId?: number | null;
  containerName?: string | null;
  adbSerial?: string | null;
  dataPath?: string | null;
  networkName?: string | null;
  state: string;
  updatedAt: string;
}

const STORAGE_KEY = "tiktok_managed_redroid_provisionings";

class ProvisioningRegistry {
  private memoryCache: Map<number, ManagedProvisioningRecord> = new Map();
  private isLoaded = false;

  private ensureLoaded(): void {
    if (this.isLoaded) return;
    this.isLoaded = true;

    if (typeof window === "undefined" || !window.localStorage) {
      return;
    }

    try {
      const raw = window.localStorage.getItem(STORAGE_KEY);
      if (raw) {
        const parsed: ManagedProvisioningRecord[] = JSON.parse(raw);
        if (Array.isArray(parsed)) {
          this.memoryCache.clear();
          for (const item of parsed) {
            if (item && item.deviceId && item.provisioningId) {
              this.memoryCache.set(item.deviceId, item);
            }
          }
        }
      }
    } catch {
      // LocalStorage parsing error fallback
    }
  }

  private persist(): void {
    if (typeof window === "undefined" || !window.localStorage) {
      return;
    }

    try {
      const records = Array.from(this.memoryCache.values());
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(records));
    } catch {
      // LocalStorage quota or access error
    }
  }

  public getAll(): ManagedProvisioningRecord[] {
    this.ensureLoaded();
    return Array.from(this.memoryCache.values());
  }

  public getByDeviceId(deviceId: number): ManagedProvisioningRecord | null {
    this.ensureLoaded();
    return this.memoryCache.get(deviceId) || null;
  }

  public getByProvisioningId(
    provisioningId: string
  ): ManagedProvisioningRecord | null {
    this.ensureLoaded();
    for (const record of this.memoryCache.values()) {
      if (record.provisioningId === provisioningId) {
        return record;
      }
    }
    return null;
  }

  public save(record: ManagedProvisioningRecord): void {
    this.ensureLoaded();
    this.memoryCache.set(record.deviceId, record);
    this.persist();
  }

  public registerFromStatus(
    status: RedroidProvisioningStatus | RedroidDeprovisioningStatus,
    overrideDeviceId?: number
  ): ManagedProvisioningRecord | null {
    const deviceId = status.device_id ?? overrideDeviceId;
    if (!deviceId) return null;

    const record: ManagedProvisioningRecord = {
      provisioningId: status.provisioning_id,
      deviceId,
      runtimeId: status.runtime_id,
      containerName:
        "container_name" in status ? status.container_name : null,
      adbSerial: "adb_serial" in status ? status.adb_serial : null,
      dataPath: status.data_path,
      networkName:
        "network_name" in status ? status.network_name : null,
      state: status.state,
      updatedAt: status.updated_at,
    };

    this.save(record);
    return record;
  }

  public remove(identifier: number | string): void {
    this.ensureLoaded();
    if (typeof identifier === "number") {
      this.memoryCache.delete(identifier);
    } else {
      for (const [devId, rec] of this.memoryCache.entries()) {
        if (rec.provisioningId === identifier) {
          this.memoryCache.delete(devId);
          break;
        }
      }
    }
    this.persist();
  }

  /**
   * Parse 409 conflict message from generic DELETE /devices/{id}:
   * e.g. "Provisioned managed devices must be removed through POST /redroid-provisionings/uuid/deprovision"
   */
  public extractProvisioningIdFromConflict(message: string): string | null {
    if (!message) return null;
    const match = message.match(
      /\/redroid-provisionings\/([a-zA-Z0-9._:-]+)\/deprovision/i
    );
    if (match && match[1]) {
      return match[1];
    }
    return null;
  }
}

export const provisioningRegistry = new ProvisioningRegistry();

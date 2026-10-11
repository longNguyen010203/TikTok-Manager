export interface TopologySummary {
  devices: number;
  runtimes: number;
  accounts: number;
  ready_accounts: number;
  not_ready_accounts: number;
  attention_accounts: number;
}

export interface DeviceNodeMetadata {
  name: string;
  status: string;
  platform: string;
  device_type: string;
  os_version: string;
  runtime_count: number;
}

export interface RuntimeNodeMetadata {
  name: string;
  status: string;
  runtime_type: string;
  device_id: number;
  assigned_account_count: number;
  last_seen_at: string | null;
}

export interface AccountNodeMetadata {
  display_name: string;
  status: string;
  registration_state: string;
  registration_ready: boolean;
  registration_completed_at: string | null;
  health_status: string;
  username: string | null;
  runtime_id: number | null;
  device_id: number | null;
  secret_present: boolean;
}

export interface DeviceTopologyNode {
  id: string;
  type: "device";
  entity_id: number;
  label: string;
  status: string;
  metadata: DeviceNodeMetadata;
}

export interface RuntimeTopologyNode {
  id: string;
  type: "runtime";
  entity_id: number;
  label: string;
  status: string;
  metadata: RuntimeNodeMetadata;
}

export interface AccountTopologyNode {
  id: string;
  type: "account";
  entity_id: number;
  label: string;
  status: string;
  metadata: AccountNodeMetadata;
}

export type TopologyNode =
  | DeviceTopologyNode
  | RuntimeTopologyNode
  | AccountTopologyNode;

export interface TopologyEdge {
  id: string;
  source: string;
  target: string;
  type: "hosts" | "assigned";
}

export interface DashboardTopology {
  generated_at: string;
  summary: TopologySummary;
  nodes: TopologyNode[];
  edges: TopologyEdge[];
}

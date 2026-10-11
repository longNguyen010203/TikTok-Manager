import { Node, Edge } from "@xyflow/react";
import {
  DashboardTopology,
  DeviceTopologyNode,
  RuntimeTopologyNode,
  AccountTopologyNode,
} from "@/types/topology";

export interface LayoutResult {
  nodes: Node[];
  edges: Edge[];
}

export interface LayoutOptions {
  filterType?: "all" | "device" | "runtime" | "account";
  readyOnly?: boolean;
  attentionOnly?: boolean;
  hideDisconnected?: boolean;
  highlightedNodeId?: string | null;
  newEntityIds?: Set<string>;
}

const X_DEVICE = 50;
const X_RUNTIME = 390;
const X_ACCOUNT = 730;

const ACCOUNT_ROW_HEIGHT = 150;
const MIN_GAP_BETWEEN_DEVICE_GROUPS = 60;

export function computeTopologyLayout(
  topology: DashboardTopology,
  options: LayoutOptions = {}
): LayoutResult {
  const {
    filterType = "all",
    readyOnly = false,
    attentionOnly = false,
    hideDisconnected = false,
    highlightedNodeId = null,
    newEntityIds = new Set(),
  } = options;

  // 1. Separate nodes by type
  const devices: DeviceTopologyNode[] = [];
  const runtimes: RuntimeTopologyNode[] = [];
  const accounts: AccountTopologyNode[] = [];

  for (const node of topology.nodes) {
    if (node.type === "device") devices.push(node);
    else if (node.type === "runtime") runtimes.push(node);
    else if (node.type === "account") accounts.push(node);
  }

  // Build edge mappings
  // hosts: device:<id> -> runtime:<id>
  const deviceToRuntimes = new Map<string, string[]>();
  // assigned: runtime:<id> -> account:<id>
  const runtimeToAccounts = new Map<string, string[]>();

  const runtimeToDevice = new Map<string, string>();
  const accountToRuntime = new Map<string, string>();

  for (const edge of topology.edges) {
    if (edge.type === "hosts") {
      const list = deviceToRuntimes.get(edge.source) || [];
      list.push(edge.target);
      deviceToRuntimes.set(edge.source, list);
      runtimeToDevice.set(edge.target, edge.source);
    } else if (edge.type === "assigned") {
      const list = runtimeToAccounts.get(edge.source) || [];
      list.push(edge.target);
      runtimeToAccounts.set(edge.source, list);
      accountToRuntime.set(edge.target, edge.source);
    }
  }

  // Filter accounts if readyOnly or attentionOnly
  const isAccountMatch = (acc: AccountTopologyNode) => {
    if (readyOnly && !acc.metadata.registration_ready) return false;
    if (attentionOnly) {
      const isFailed = acc.metadata.registration_state === "failed";
      const isHealthIssue =
        acc.metadata.health_status === "warning" ||
        acc.metadata.health_status === "unhealthy";
      const isLifecycleIssue = ["restricted", "suspended", "disabled", "archived"].includes(
        acc.status.toLowerCase()
      );
      if (!isFailed && !isHealthIssue && !isLifecycleIssue) return false;
    }
    return true;
  };

  // Node filtering by type and criteria
  const allowedNodeIds = new Set<string>();

  for (const acc of accounts) {
    if (filterType !== "all" && filterType !== "account") continue;
    if (!isAccountMatch(acc)) continue;
    if (hideDisconnected && !accountToRuntime.has(acc.id)) continue;
    allowedNodeIds.add(acc.id);
  }

  for (const rt of runtimes) {
    if (filterType !== "all" && filterType !== "runtime") continue;
    const hasAssigned = runtimeToAccounts.has(rt.id);
    const hasHost = runtimeToDevice.has(rt.id);
    if (hideDisconnected && !hasAssigned && !hasHost) continue;
    allowedNodeIds.add(rt.id);
  }

  for (const dev of devices) {
    if (filterType !== "all" && filterType !== "device") continue;
    const hasRuntimes = deviceToRuntimes.has(dev.id);
    if (hideDisconnected && !hasRuntimes) continue;
    allowedNodeIds.add(dev.id);
  }

  // Nodes to position
  const flowNodes: Node[] = [];
  const flowEdges: Edge[] = [];

  let currentY = 40;

  // Process Connected Graphs: Device -> Runtime -> Accounts
  for (const dev of devices) {
    if (!allowedNodeIds.has(dev.id)) continue;

    const hostedRuntimeIds = (deviceToRuntimes.get(dev.id) || []).filter((id) =>
      allowedNodeIds.has(id)
    );

    if (hostedRuntimeIds.length === 0) {
      // Standalone device with no visible runtimes
      flowNodes.push({
        id: dev.id,
        type: "device",
        position: { x: X_DEVICE, y: currentY },
        data: {
          ...dev,
          isHighlighted: highlightedNodeId === dev.id,
          isNew: newEntityIds.has(dev.id),
        },
      });
      currentY += 140;
      continue;
    }

    const deviceStartY = currentY;
    const runtimePositions: { id: string; y: number }[] = [];

    for (const rtId of hostedRuntimeIds) {
      const rtNode = runtimes.find((r) => r.id === rtId);
      if (!rtNode) continue;

      const assignedAccountIds = (runtimeToAccounts.get(rtId) || []).filter((id) =>
        allowedNodeIds.has(id)
      );

      if (assignedAccountIds.length === 0) {
        // Runtime with no assigned visible accounts
        flowNodes.push({
          id: rtNode.id,
          type: "runtime",
          position: { x: X_RUNTIME, y: currentY },
          data: {
            ...rtNode,
            isHighlighted: highlightedNodeId === rtNode.id,
            isNew: newEntityIds.has(rtNode.id),
          },
        });
        runtimePositions.push({ id: rtNode.id, y: currentY });
        currentY += 140;
      } else {
        // Runtime fans out to multiple accounts
        const firstAccountY = currentY;
        for (const accId of assignedAccountIds) {
          const accNode = accounts.find((a) => a.id === accId);
          if (!accNode) continue;

          flowNodes.push({
            id: accNode.id,
            type: "account",
            position: { x: X_ACCOUNT, y: currentY },
            data: {
              ...accNode,
              isHighlighted: highlightedNodeId === accNode.id,
              isNew: newEntityIds.has(accNode.id),
            },
          });
          currentY += ACCOUNT_ROW_HEIGHT;
        }

        const lastAccountY = currentY - ACCOUNT_ROW_HEIGHT;
        const centeredRuntimeY = (firstAccountY + lastAccountY) / 2;

        flowNodes.push({
          id: rtNode.id,
          type: "runtime",
          position: { x: X_RUNTIME, y: centeredRuntimeY },
          data: {
            ...rtNode,
            isHighlighted: highlightedNodeId === rtNode.id,
            isNew: newEntityIds.has(rtNode.id),
          },
        });
        runtimePositions.push({ id: rtNode.id, y: centeredRuntimeY });
      }
    }

    // Center Device node vertically relative to its hosted runtimes
    const firstRuntimeY = runtimePositions[0]?.y ?? deviceStartY;
    const lastRuntimeY = runtimePositions[runtimePositions.length - 1]?.y ?? deviceStartY;
    const centeredDeviceY = (firstRuntimeY + lastRuntimeY) / 2;

    flowNodes.push({
      id: dev.id,
      type: "device",
      position: { x: X_DEVICE, y: centeredDeviceY },
      data: {
        ...dev,
        isHighlighted: highlightedNodeId === dev.id,
        isNew: newEntityIds.has(dev.id),
      },
    });

    currentY += MIN_GAP_BETWEEN_DEVICE_GROUPS;
  }

  // Standalone Runtimes not hosted by any device
  for (const rt of runtimes) {
    if (!allowedNodeIds.has(rt.id)) continue;
    if (runtimeToDevice.has(rt.id)) continue; // already processed

    const assignedAccountIds = (runtimeToAccounts.get(rt.id) || []).filter((id) =>
      allowedNodeIds.has(id)
    );

    if (assignedAccountIds.length === 0) {
      flowNodes.push({
        id: rt.id,
        type: "runtime",
        position: { x: X_RUNTIME, y: currentY },
        data: {
          ...rt,
          isHighlighted: highlightedNodeId === rt.id,
          isNew: newEntityIds.has(rt.id),
        },
      });
      currentY += 140;
    } else {
      const firstAccountY = currentY;
      for (const accId of assignedAccountIds) {
        const accNode = accounts.find((a) => a.id === accId);
        if (!accNode) continue;

        flowNodes.push({
          id: accNode.id,
          type: "account",
          position: { x: X_ACCOUNT, y: currentY },
          data: {
            ...accNode,
            isHighlighted: highlightedNodeId === accNode.id,
            isNew: newEntityIds.has(accNode.id),
          },
        });
        currentY += ACCOUNT_ROW_HEIGHT;
      }
      const lastAccountY = currentY - ACCOUNT_ROW_HEIGHT;
      const centeredRuntimeY = (firstAccountY + lastAccountY) / 2;

      flowNodes.push({
        id: rt.id,
        type: "runtime",
        position: { x: X_RUNTIME, y: centeredRuntimeY },
        data: {
          ...rt,
          isHighlighted: highlightedNodeId === rt.id,
          isNew: newEntityIds.has(rt.id),
        },
      });
    }
    currentY += MIN_GAP_BETWEEN_DEVICE_GROUPS;
  }

  // 4. Unassigned Accounts: dedicated separated area
  const unassignedAccounts = accounts.filter(
    (a) => allowedNodeIds.has(a.id) && !accountToRuntime.has(a.id)
  );

  if (unassignedAccounts.length > 0 && !hideDisconnected) {
    const unassignedStartY = Math.max(currentY + 50, 100);

    // Group Header Node
    flowNodes.push({
      id: "group:unassigned-header",
      type: "unassignedGroup",
      position: { x: X_DEVICE, y: unassignedStartY },
      selectable: false,
      draggable: false,
      data: {
        count: unassignedAccounts.length,
      },
    });

    // Place unassigned accounts in 3 columns
    const accountsStartY = unassignedStartY + 60;
    const COLS = 3;
    const COL_GAP = 280;
    const ROW_GAP = 140;

    unassignedAccounts.forEach((acc, index) => {
      const col = index % COLS;
      const row = Math.floor(index / COLS);
      const x = X_DEVICE + col * COL_GAP;
      const y = accountsStartY + row * ROW_GAP;

      flowNodes.push({
        id: acc.id,
        type: "account",
        position: { x, y },
        data: {
          ...acc,
          isHighlighted: highlightedNodeId === acc.id,
          isNew: newEntityIds.has(acc.id),
        },
      });
    });
  }

  // 5. Build Flow Edges for visible nodes
  for (const edge of topology.edges) {
    if (allowedNodeIds.has(edge.source) && allowedNodeIds.has(edge.target)) {
      const isHosts = edge.type === "hosts";
      flowEdges.push({
        id: edge.id,
        source: edge.source,
        target: edge.target,
        sourceHandle: "out",
        targetHandle: "in",
        type: "smoothstep",
        style: {
          stroke: isHosts ? "#6366f1" : "#0284c7", // Indigo for hosts, Sky for assigned
          strokeWidth: 2,
        },
        animated: false,
      });
    }
  }

  return { nodes: flowNodes, edges: flowEdges };
}

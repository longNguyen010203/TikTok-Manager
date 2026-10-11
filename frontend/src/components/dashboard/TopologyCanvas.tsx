"use client";

import React, { useCallback, useEffect, useMemo, useRef } from "react";
import {
  ReactFlow,
  Controls,
  MiniMap,
  Background,
  BackgroundVariant,
  useNodesState,
  useEdgesState,
  Node,
  Edge,
  useReactFlow,
  NodeTypes,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";

import { DeviceNode } from "./nodes/DeviceNode";
import { RuntimeNode } from "./nodes/RuntimeNode";
import { AccountNode } from "./nodes/AccountNode";
import { UnassignedGroupNode } from "./nodes/UnassignedGroupNode";

interface TopologyCanvasProps {
  initialNodes: Node[];
  initialEdges: Edge[];
  selectedNodeId: string | null;
  onSelectNode: (nodeId: string | null) => void;
}

export function TopologyCanvas({
  initialNodes,
  initialEdges,
  selectedNodeId,
  onSelectNode,
}: TopologyCanvasProps) {
  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);
  const { fitView, setCenter, getZoom } = useReactFlow();
  const hasFittedViewRef = useRef(false);

  const nodeTypes: NodeTypes = useMemo(
    () => ({
      device: DeviceNode,
      runtime: RuntimeNode,
      account: AccountNode,
      unassignedGroup: UnassignedGroupNode,
    }),
    []
  );

  // Sync nodes and edges from parent when topology updates, while preserving user dragged positions
  useEffect(() => {
    setNodes((prevNodes) => {
      const positionMap = new Map<string, { x: number; y: number }>();
      for (const p of prevNodes) {
        positionMap.set(p.id, p.position);
      }

      return initialNodes.map((n) => {
        // If node already exists and was dragged by operator, preserve position
        const existingPos = positionMap.get(n.id);
        return {
          ...n,
          position: existingPos || n.position,
          selected: n.id === selectedNodeId,
        };
      });
    });
    setEdges(initialEdges);
  }, [initialNodes, initialEdges, selectedNodeId, setNodes, setEdges]);

  // Initial fit view
  useEffect(() => {
    if (nodes.length > 0 && !hasFittedViewRef.current) {
      hasFittedViewRef.current = true;
      setTimeout(() => {
        fitView({ padding: 0.2, duration: 600 });
      }, 100);
    }
  }, [nodes.length, fitView]);

  // When a node is selected, center on it smoothly
  useEffect(() => {
    if (selectedNodeId) {
      const target = nodes.find((n) => n.id === selectedNodeId);
      if (target) {
        const currentZoom = getZoom();
        setCenter(target.position.x + 120, target.position.y + 60, {
          zoom: Math.max(currentZoom, 0.9),
          duration: 600,
        });
      }
    }
  }, [selectedNodeId, nodes, setCenter, getZoom]);

  const handleNodeClick = useCallback(
    (_event: React.MouseEvent, node: Node) => {
      if (node.type === "unassignedGroup") return;
      onSelectNode(node.id);
    },
    [onSelectNode]
  );

  const handlePaneClick = useCallback(() => {
    onSelectNode(null);
  }, [onSelectNode]);

  return (
    <div className="w-full h-full min-h-[620px] relative bg-slate-50/50 rounded-2xl border border-slate-200/90 overflow-hidden shadow-2xs">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onNodeClick={handleNodeClick}
        onPaneClick={handlePaneClick}
        nodeTypes={nodeTypes}
        fitViewOptions={{ padding: 0.2 }}
        minZoom={0.2}
        maxZoom={2.5}
        defaultEdgeOptions={{
          type: "smoothstep",
        }}
        proOptions={{ hideAttribution: true }}
      >
        <Background variant={BackgroundVariant.Dots} gap={16} size={1} color="#cbd5e1" />
        <Controls
          className="!bg-white !border !border-slate-200 !rounded-xl !shadow-xs overflow-hidden"
          showInteractive={false}
        />
        <MiniMap
          nodeColor={(n) => {
            if (n.type === "device") return "#6366f1";
            if (n.type === "runtime") return "#0284c7";
            if (n.type === "account") return "#e11d48";
            return "#f59e0b";
          }}
          nodeStrokeWidth={3}
          zoomable
          pannable
          className="!border !border-slate-200 !rounded-xl !bg-white/90 !shadow-xs overflow-hidden"
        />
      </ReactFlow>
    </div>
  );
}

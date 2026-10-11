"use client";

import React, { useState, useEffect, useRef, useCallback, useMemo } from "react";
import { ReactFlowProvider } from "@xyflow/react";
import {
  Network,
  AlertCircle,
} from "lucide-react";

import { DashboardTopology } from "@/types/topology";
import { dashboardService } from "@/services/dashboardService";
import { TopologySummaryBar } from "@/components/dashboard/TopologySummaryBar";
import { TopologyToolbar } from "@/components/dashboard/TopologyToolbar";
import { TopologyCanvas } from "@/components/dashboard/TopologyCanvas";
import { TopologyDetailsDrawer } from "@/components/dashboard/TopologyDetailsDrawer";
import { TopologyLoadingSkeleton } from "@/components/dashboard/TopologyLoadingSkeleton";
import { TopologyEmptyState } from "@/components/dashboard/TopologyEmptyState";
import { computeTopologyLayout } from "@/components/dashboard/topologyLayout";

const REFRESH_INTERVAL_MS = 10_000; // 10 seconds auto-poll

export default function DashboardPage() {
  const [topology, setTopology] = useState<DashboardTopology | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Search & Filters
  const [filterType, setFilterType] = useState<"all" | "device" | "runtime" | "account">("all");
  const [readyOnly, setReadyOnly] = useState(false);
  const [attentionOnly, setAttentionOnly] = useState(false);
  const [hideDisconnected, setHideDisconnected] = useState(false);

  // Selection & Focus
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);

  // Tracking newly added entity IDs for subtle change highlighting
  const [newEntityIds, setNewEntityIds] = useState<Set<string>>(new Set());
  const knownEntityIdsRef = useRef<Set<string>>(new Set());

  // Polling and initial fetch effect
  useEffect(() => {
    let ignore = false;

    // Initial load
    dashboardService
      .getTopology()
      .then((data) => {
        if (ignore) return;
        knownEntityIdsRef.current = new Set(data.nodes.map((n) => n.id));
        setTopology(data);
        setError(null);
        setIsLoading(false);
      })
      .catch((err: unknown) => {
        if (ignore) return;
        const message =
          err instanceof Error
            ? err.message
            : "Failed to load system topology. Ensure the backend server is reachable.";
        setError(message);
        setIsLoading(false);
      });

    // 10s auto-refresh interval
    const timer = setInterval(() => {
      dashboardService
        .getTopology()
        .then((data) => {
          if (ignore) return;
          const freshIds = new Set(data.nodes.map((n) => n.id));
          const newlyAdded = new Set<string>();
          for (const id of freshIds) {
            if (!knownEntityIdsRef.current.has(id)) {
              newlyAdded.add(id);
            }
          }
          if (newlyAdded.size > 0) {
            setNewEntityIds(newlyAdded);
            setTimeout(() => {
              setNewEntityIds(new Set());
            }, 8000);
          }
          knownEntityIdsRef.current = freshIds;
          setTopology(data);
          setError(null);
        })
        .catch(() => {
          // ignore transient background poll errors
        });
    }, REFRESH_INTERVAL_MS);

    return () => {
      ignore = true;
      clearInterval(timer);
    };
  }, []);

  // Manual refresh callback
  const handleManualRefresh = useCallback(() => {
    setIsRefreshing(true);
    dashboardService
      .getTopology()
      .then((data) => {
        const freshIds = new Set(data.nodes.map((n) => n.id));
        const newlyAdded = new Set<string>();
        for (const id of freshIds) {
          if (!knownEntityIdsRef.current.has(id)) {
            newlyAdded.add(id);
          }
        }
        if (newlyAdded.size > 0) {
          setNewEntityIds(newlyAdded);
          setTimeout(() => {
            setNewEntityIds(new Set());
          }, 8000);
        }
        knownEntityIdsRef.current = freshIds;
        setTopology(data);
        setError(null);
      })
      .catch((err: unknown) => {
        const message =
          err instanceof Error
            ? err.message
            : "Failed to load system topology. Ensure the backend server is reachable.";
        setError(message);
      })
      .finally(() => {
        setIsRefreshing(false);
        setIsLoading(false);
      });
  }, []);

  // Compute Layout when topology or filters change
  const layout = useMemo(() => {
    if (!topology) return { nodes: [], edges: [] };
    return computeTopologyLayout(topology, {
      filterType,
      readyOnly,
      attentionOnly,
      hideDisconnected,
      highlightedNodeId: selectedNodeId,
      newEntityIds,
    });
  }, [
    topology,
    filterType,
    readyOnly,
    attentionOnly,
    hideDisconnected,
    selectedNodeId,
    newEntityIds,
  ]);

  const handleSelectNode = useCallback((nodeId: string | null) => {
    setSelectedNodeId(nodeId);
  }, []);

  const handleFitView = useCallback(() => {
    const fitBtn = document.querySelector(".react-flow__controls-fitview") as HTMLButtonElement | null;
    if (fitBtn) {
      fitBtn.click();
    }
  }, []);

  return (
    <div className="space-y-4">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h1 className="text-xl sm:text-2xl font-bold text-slate-900 tracking-tight flex items-center gap-2.5">
            <Network className="w-6 h-6 text-rose-600" />
            <span>System Topology</span>
          </h1>
          <p className="text-xs sm:text-sm text-slate-500 mt-0.5">
            Real-time interactive relationship graph across Devices, Runtimes, and Accounts.
          </p>
        </div>

        <div className="flex items-center gap-3">
          {/* Auto-refresh indicator */}
          <div className="flex items-center gap-2 px-2.5 py-1 rounded-full bg-slate-100 border border-slate-200/80 text-[11px] text-slate-600">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
            <span>Auto-refreshing (10s)</span>
          </div>
        </div>
      </div>

      {/* Error Banner */}
      {error && (
        <div className="p-3.5 rounded-xl border border-rose-200 bg-rose-50/90 text-xs flex items-center justify-between gap-3 text-rose-800">
          <div className="flex items-center gap-2">
            <AlertCircle className="w-4 h-4 text-rose-600 shrink-0" />
            <span>{error}</span>
          </div>
          <button
            type="button"
            onClick={handleManualRefresh}
            className="px-3 py-1 bg-white border border-rose-300 rounded-lg font-semibold text-rose-700 hover:bg-rose-50 transition-colors"
          >
            Retry
          </button>
        </div>
      )}

      {/* Loading Skeleton */}
      {isLoading ? (
        <TopologyLoadingSkeleton />
      ) : !topology ? (
        <TopologyEmptyState />
      ) : (
        <>
          {/* Top Section Summary Bar */}
          <TopologySummaryBar summary={topology.summary} />

          {/* Search, Filter & View Controls Toolbar */}
          <TopologyToolbar
            topology={topology}
            filterType={filterType}
            onFilterTypeChange={setFilterType}
            readyOnly={readyOnly}
            onReadyOnlyChange={setReadyOnly}
            attentionOnly={attentionOnly}
            onAttentionOnlyChange={setAttentionOnly}
            hideDisconnected={hideDisconnected}
            onHideDisconnectedChange={setHideDisconnected}
            onSelectNode={handleSelectNode}
            onFitView={handleFitView}
            onRefresh={handleManualRefresh}
            isRefreshing={isRefreshing}
            lastUpdated={topology.generated_at}
          />

          {/* Main Section: Interactive Graph Canvas */}
          {topology.nodes.length === 0 ? (
            <TopologyEmptyState />
          ) : (
            <div className="relative w-full h-[calc(100vh-310px)] min-h-[640px]">
              <ReactFlowProvider>
                <TopologyCanvas
                  initialNodes={layout.nodes}
                  initialEdges={layout.edges}
                  selectedNodeId={selectedNodeId}
                  onSelectNode={handleSelectNode}
                />
              </ReactFlowProvider>

              {/* Node Details Drawer */}
              <TopologyDetailsDrawer
                selectedNodeId={selectedNodeId}
                topology={topology}
                onClose={() => setSelectedNodeId(null)}
                onSelectNode={handleSelectNode}
              />
            </div>
          )}
        </>
      )}
    </div>
  );
}

"use client";

import React, { useState, useRef, useEffect } from "react";
import {
  Search,
  Maximize2,
  RefreshCw,
  X,
  Smartphone,
  Cpu,
  User,
  CheckCircle2,
  AlertTriangle,
  EyeOff,
} from "lucide-react";
import { DashboardTopology, TopologyNode } from "@/types/topology";

interface TopologyToolbarProps {
  topology: DashboardTopology | null;
  filterType: "all" | "device" | "runtime" | "account";
  onFilterTypeChange: (val: "all" | "device" | "runtime" | "account") => void;
  readyOnly: boolean;
  onReadyOnlyChange: (val: boolean) => void;
  attentionOnly: boolean;
  onAttentionOnlyChange: (val: boolean) => void;
  hideDisconnected: boolean;
  onHideDisconnectedChange: (val: boolean) => void;
  onSelectNode: (nodeId: string) => void;
  onFitView: () => void;
  onRefresh: () => void;
  isRefreshing: boolean;
  lastUpdated: string | null;
}

export function TopologyToolbar({
  topology,
  filterType,
  onFilterTypeChange,
  readyOnly,
  onReadyOnlyChange,
  attentionOnly,
  onAttentionOnlyChange,
  hideDisconnected,
  onHideDisconnectedChange,
  onSelectNode,
  onFitView,
  onRefresh,
  isRefreshing,
  lastUpdated,
}: TopologyToolbarProps) {
  const [searchQuery, setSearchQuery] = useState("");
  const [isSearchOpen, setIsSearchOpen] = useState(false);
  const searchContainerRef = useRef<HTMLDivElement>(null);

  // Close search dropdown on click outside
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (
        searchContainerRef.current &&
        !searchContainerRef.current.contains(event.target as Node)
      ) {
        setIsSearchOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  // Filter search results
  const searchResults: TopologyNode[] = React.useMemo(() => {
    if (!topology || !searchQuery.trim()) return [];
    const q = searchQuery.toLowerCase().trim();

    return topology.nodes.filter((node) => {
      const matchId =
        node.id.toLowerCase().includes(q) ||
        String(node.entity_id) === q ||
        `#${node.entity_id}` === q;
      const matchLabel = node.label.toLowerCase().includes(q);

      if (node.type === "device") {
        return (
          matchId ||
          matchLabel ||
          node.metadata.name.toLowerCase().includes(q) ||
          node.metadata.platform.toLowerCase().includes(q)
        );
      }
      if (node.type === "runtime") {
        return (
          matchId ||
          matchLabel ||
          node.metadata.name.toLowerCase().includes(q) ||
          node.metadata.runtime_type.toLowerCase().includes(q)
        );
      }
      if (node.type === "account") {
        return (
          matchId ||
          matchLabel ||
          node.metadata.display_name.toLowerCase().includes(q) ||
          (node.metadata.username &&
            node.metadata.username.toLowerCase().includes(q))
        );
      }
      return false;
    });
  }, [topology, searchQuery]);

  const handleSelectResult = (nodeId: string) => {
    onSelectNode(nodeId);
    setIsSearchOpen(false);
  };

  return (
    <div className="bg-white border border-slate-200/90 rounded-xl p-3 shadow-2xs flex flex-col md:flex-row items-stretch md:items-center justify-between gap-3">
      {/* Search Input */}
      <div className="relative flex-1 max-w-md" ref={searchContainerRef}>
        <div className="relative">
          <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            placeholder="Search Device, Runtime, Account, or @handle..."
            value={searchQuery}
            onChange={(e) => {
              setSearchQuery(e.target.value);
              setIsSearchOpen(true);
            }}
            onFocus={() => setIsSearchOpen(true)}
            className="w-full pl-9 pr-8 py-1.5 text-xs bg-slate-50 border border-slate-200 rounded-lg text-slate-800 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-rose-500/20 focus:border-rose-500 transition-all"
          />
          {searchQuery && (
            <button
              type="button"
              onClick={() => {
                setSearchQuery("");
                setIsSearchOpen(false);
              }}
              className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          )}
        </div>

        {/* Dropdown Results */}
        {isSearchOpen && searchQuery.trim() && (
          <div className="absolute left-0 right-0 top-full mt-1.5 bg-white border border-slate-200 rounded-xl shadow-lg max-h-72 overflow-y-auto z-50 divide-y divide-slate-100 animate-in fade-in slide-in-from-top-1 duration-150">
            {searchResults.length === 0 ? (
              <div className="p-3 text-center text-xs text-slate-500">
                No topology nodes matching &ldquo;{searchQuery}&rdquo;.
              </div>
            ) : (
              searchResults.map((node) => {
                const Icon =
                  node.type === "device"
                    ? Smartphone
                    : node.type === "runtime"
                    ? Cpu
                    : User;
                const badgeColor =
                  node.type === "device"
                    ? "bg-indigo-50 text-indigo-700"
                    : node.type === "runtime"
                    ? "bg-sky-50 text-sky-700"
                    : "bg-rose-50 text-rose-700";

                return (
                  <button
                    key={node.id}
                    type="button"
                    onClick={() => handleSelectResult(node.id)}
                    className="w-full text-left p-2.5 hover:bg-slate-50 flex items-center justify-between gap-2 transition-colors cursor-pointer"
                  >
                    <div className="flex items-center gap-2 min-w-0">
                      <div className={`p-1.5 rounded-lg ${badgeColor} shrink-0`}>
                        <Icon className="w-3.5 h-3.5" />
                      </div>
                      <div className="min-w-0">
                        <p className="text-xs font-semibold text-slate-900 truncate">
                          {node.label}
                        </p>
                        <p className="text-[10px] text-slate-500 capitalize">
                          {node.type} #{node.entity_id} &bull; {node.status}
                          {node.type === "account" && node.metadata.username && (
                            <span className="font-mono ml-1 text-slate-600">
                              @{node.metadata.username}
                            </span>
                          )}
                        </p>
                      </div>
                    </div>
                    <span className="text-[10px] font-semibold text-rose-600 shrink-0">
                      Jump &rarr;
                    </span>
                  </button>
                );
              })
            )}
          </div>
        )}
      </div>

      {/* Filters & View Controls */}
      <div className="flex items-center gap-2 flex-wrap">
        {/* Entity Type Filter */}
        <div className="flex items-center gap-1 bg-slate-50 p-0.5 rounded-lg border border-slate-200">
          {(
            [
              { id: "all", label: "All" },
              { id: "device", label: "Devices" },
              { id: "runtime", label: "Runtimes" },
              { id: "account", label: "Accounts" },
            ] as const
          ).map((t) => (
            <button
              key={t.id}
              type="button"
              onClick={() => onFilterTypeChange(t.id)}
              className={`px-2.5 py-1 rounded-md text-xs font-medium transition-all cursor-pointer ${
                filterType === t.id
                  ? "bg-white text-slate-900 shadow-2xs font-semibold"
                  : "text-slate-600 hover:text-slate-900"
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>

        {/* Ready Only Toggle */}
        <button
          type="button"
          onClick={() => onReadyOnlyChange(!readyOnly)}
          className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-medium border transition-colors cursor-pointer ${
            readyOnly
              ? "bg-emerald-50 text-emerald-800 border-emerald-300 font-semibold shadow-2xs"
              : "bg-white text-slate-600 border-slate-200 hover:bg-slate-50"
          }`}
          title="Filter to Ready accounts only"
        >
          <CheckCircle2 className={`w-3.5 h-3.5 ${readyOnly ? "text-emerald-600" : "text-slate-400"}`} />
          <span>Ready only</span>
        </button>

        {/* Attention Only Toggle */}
        <button
          type="button"
          onClick={() => onAttentionOnlyChange(!attentionOnly)}
          className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-medium border transition-colors cursor-pointer ${
            attentionOnly
              ? "bg-rose-50 text-rose-800 border-rose-300 font-semibold shadow-2xs"
              : "bg-white text-slate-600 border-slate-200 hover:bg-slate-50"
          }`}
          title="Filter to Attention accounts only"
        >
          <AlertTriangle className={`w-3.5 h-3.5 ${attentionOnly ? "text-rose-600" : "text-slate-400"}`} />
          <span>Attention only</span>
        </button>

        {/* Hide Disconnected Toggle */}
        <button
          type="button"
          onClick={() => onHideDisconnectedChange(!hideDisconnected)}
          className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-medium border transition-colors cursor-pointer ${
            hideDisconnected
              ? "bg-amber-50 text-amber-800 border-amber-300 font-semibold shadow-2xs"
              : "bg-white text-slate-600 border-slate-200 hover:bg-slate-50"
          }`}
          title="Hide unassigned or disconnected nodes"
        >
          <EyeOff className={`w-3.5 h-3.5 ${hideDisconnected ? "text-amber-600" : "text-slate-400"}`} />
          <span>Hide disconnected</span>
        </button>

        {/* Fit View Button */}
        <button
          type="button"
          onClick={onFitView}
          className="p-1.5 rounded-lg border border-slate-200 bg-white text-slate-600 hover:bg-slate-50 hover:text-slate-900 transition-colors shadow-2xs cursor-pointer"
          title="Fit view to all nodes"
        >
          <Maximize2 className="w-3.5 h-3.5" />
        </button>

        {/* Manual Refresh Button */}
        <button
          type="button"
          onClick={onRefresh}
          disabled={isRefreshing}
          className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg border border-slate-200 bg-white text-slate-700 hover:bg-slate-50 transition-colors shadow-2xs disabled:opacity-50 cursor-pointer"
          title={lastUpdated ? `Last updated: ${new Date(lastUpdated).toLocaleTimeString()}` : "Refresh topology"}
        >
          <RefreshCw className={`w-3.5 h-3.5 text-slate-500 ${isRefreshing ? "animate-spin" : ""}`} />
          <span className="text-xs font-medium">Refresh</span>
        </button>
      </div>
    </div>
  );
}

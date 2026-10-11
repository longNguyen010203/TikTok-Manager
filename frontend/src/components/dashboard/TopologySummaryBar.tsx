"use client";

import React from "react";
import {
  Smartphone,
  Cpu,
  Users,
  CheckCircle2,
  Clock,
  AlertTriangle,
} from "lucide-react";
import { TopologySummary } from "@/types/topology";

interface TopologySummaryBarProps {
  summary: TopologySummary;
}

export function TopologySummaryBar({ summary }: TopologySummaryBarProps) {
  const cards = [
    {
      label: "Devices",
      value: summary.devices,
      icon: Smartphone,
      color: "bg-indigo-50 text-indigo-700",
      textColor: "text-slate-900",
      description: "Host platforms",
    },
    {
      label: "Runtimes",
      value: summary.runtimes,
      icon: Cpu,
      color: "bg-sky-50 text-sky-700",
      textColor: "text-slate-900",
      description: "Execution environments",
    },
    {
      label: "Accounts",
      value: summary.accounts,
      icon: Users,
      color: "bg-purple-50 text-purple-700",
      textColor: "text-slate-900",
      description: "Visible profiles",
    },
    {
      label: "Ready Accounts",
      value: summary.ready_accounts,
      icon: CheckCircle2,
      color: "bg-emerald-50 text-emerald-700",
      textColor: "text-emerald-700",
      description: "Eligible for automation",
    },
    {
      label: "Not Ready Accounts",
      value: summary.not_ready_accounts,
      icon: Clock,
      color: "bg-amber-50 text-amber-700",
      textColor: "text-amber-700",
      description: "Pending or missing runtime",
    },
    {
      label: "Attention",
      value: summary.attention_accounts,
      icon: AlertTriangle,
      color: summary.attention_accounts > 0 ? "bg-rose-50 text-rose-700" : "bg-slate-50 text-slate-500",
      textColor: summary.attention_accounts > 0 ? "text-rose-700" : "text-slate-700",
      description: "Needs operator action",
      pulse: summary.attention_accounts > 0,
    },
  ];

  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
      {cards.map((c) => {
        const Icon = c.icon;
        return (
          <div
            key={c.label}
            className="p-3 rounded-xl border border-slate-200/80 bg-white shadow-2xs hover:shadow-xs transition-shadow flex items-center gap-3"
          >
            <div className={`p-2 rounded-lg shrink-0 ${c.color}`}>
              <Icon className="w-4 h-4" />
            </div>
            <div className="min-w-0">
              <p className="text-[11px] font-medium text-slate-500 truncate">
                {c.label}
              </p>
              <div className="flex items-baseline gap-1.5">
                <span className={`text-lg font-bold tracking-tight ${c.textColor}`}>
                  {c.value}
                </span>
                {c.pulse && (
                  <span className="w-2 h-2 rounded-full bg-rose-500 animate-pulse inline-block" />
                )}
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}

"use client";

import React from "react";
import { NodeProps } from "@xyflow/react";
import { AlertCircle, Users } from "lucide-react";

export function UnassignedGroupNode({ data }: NodeProps) {
  const count = (data as { count?: number })?.count ?? 0;

  return (
    <div className="w-[810px] bg-gradient-to-r from-amber-50/90 via-orange-50/60 to-slate-50 border border-amber-200/80 rounded-xl p-3 shadow-2xs">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="p-1 rounded-md bg-amber-100 text-amber-800">
            <AlertCircle className="w-4 h-4" />
          </div>
          <div>
            <h4 className="text-xs font-bold text-amber-950 flex items-center gap-2">
              <span>Unassigned Accounts</span>
              <span className="px-2 py-0.2 rounded-full bg-amber-200/80 text-amber-900 text-[10px] font-mono">
                {count} {count === 1 ? "account" : "accounts"}
              </span>
            </h4>
            <p className="text-[11px] text-amber-800/80 mt-0.5">
              These registered profiles are not bound to an active execution Runtime and cannot receive automated dispatches.
            </p>
          </div>
        </div>

        <div className="flex items-center gap-1 text-[11px] font-medium text-amber-800 bg-white/80 px-2 py-1 rounded-lg border border-amber-200">
          <Users className="w-3.5 h-3.5 text-amber-600" />
          <span>Requires Runtime Assignment</span>
        </div>
      </div>
    </div>
  );
}

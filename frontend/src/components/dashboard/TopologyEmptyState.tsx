"use client";

import React from "react";
import Link from "next/link";
import { Smartphone, Cpu, Users, Plus } from "lucide-react";

export function TopologyEmptyState() {
  return (
    <div className="w-full h-[620px] bg-white border border-slate-200/90 rounded-2xl flex flex-col items-center justify-center p-8 text-center">
      <div className="w-16 h-16 rounded-2xl bg-slate-100 flex items-center justify-center text-slate-400 mb-4">
        <Users className="w-8 h-8" />
      </div>
      <h3 className="text-base font-bold text-slate-800">
        No System Entities Found
      </h3>
      <p className="text-xs text-slate-500 max-w-md mt-1 mb-6">
        The topology graph visualizes real Devices, Runtimes, and Accounts.
        Provision your first Device, spawn a Runtime, and register an Account to see the live graph.
      </p>

      <div className="flex items-center gap-3 flex-wrap justify-center">
        <Link
          href="/devices"
          className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl bg-indigo-50 text-indigo-700 hover:bg-indigo-100 font-semibold text-xs border border-indigo-200 transition-colors"
        >
          <Smartphone className="w-3.5 h-3.5" />
          <span>Go to Devices</span>
        </Link>
        <Link
          href="/runtimes"
          className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl bg-sky-50 text-sky-700 hover:bg-sky-100 font-semibold text-xs border border-sky-200 transition-colors"
        >
          <Cpu className="w-3.5 h-3.5" />
          <span>Go to Runtimes</span>
        </Link>
        <Link
          href="/accounts"
          className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl bg-rose-600 text-white hover:bg-rose-700 font-semibold text-xs shadow-2xs transition-colors"
        >
          <Plus className="w-3.5 h-3.5" />
          <span>Create Account</span>
        </Link>
      </div>
    </div>
  );
}

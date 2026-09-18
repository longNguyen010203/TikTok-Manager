"use client";

import React from "react";
import { Bell, Search, Activity, User } from "lucide-react";

export function Header() {
  return (
    <header className="h-16 border-b border-slate-200 bg-white/80 backdrop-blur-md sticky top-0 z-30 px-4 sm:px-8 flex items-center justify-between">
      {/* Left section: Spacer for mobile hamburger & Search/Breadcrumb */}
      <div className="flex items-center gap-4 pl-10 md:pl-0">
        <div className="relative hidden sm:block w-64 lg:w-80">
          <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
          <input
            type="text"
            placeholder="Search accounts, posts, jobs..."
            className="w-full bg-slate-50 border border-slate-200 rounded-lg pl-9 pr-3 py-1.5 text-xs text-slate-700 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-rose-500/20 focus:border-rose-500 transition-all"
          />
        </div>
      </div>

      {/* Right section: System status & Profile */}
      <div className="flex items-center gap-3">
        {/* Backend status chip */}
        <div className="flex items-center gap-2 px-2.5 py-1 rounded-full bg-emerald-50 border border-emerald-200 text-[11px] font-medium text-emerald-700">
          <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
          <Activity className="w-3 h-3 text-emerald-600 hidden sm:inline" />
          <span>System Healthy</span>
        </div>

        {/* Notifications */}
        <button
          className="p-2 rounded-lg text-slate-500 hover:text-slate-800 hover:bg-slate-100 transition-colors relative"
          aria-label="Notifications"
        >
          <Bell className="w-4 h-4" />
          <span className="absolute top-1.5 right-1.5 w-2 h-2 bg-rose-500 rounded-full ring-2 ring-white" />
        </button>

        {/* User avatar */}
        <div className="flex items-center gap-2 pl-2 border-l border-slate-200">
          <div className="w-8 h-8 rounded-full bg-gradient-to-tr from-slate-700 to-slate-900 text-white flex items-center justify-center font-semibold text-xs shadow-xs">
            <User className="w-4 h-4" />
          </div>
          <div className="hidden lg:block text-left">
            <p className="text-xs font-semibold text-slate-800 leading-none">
              Operator
            </p>
            <p className="text-[10px] text-slate-500">Admin</p>
          </div>
        </div>
      </div>
    </header>
  );
}

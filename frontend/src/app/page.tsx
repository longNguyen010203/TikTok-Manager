import React from "react";
import {
  Users,
  Video,
  Clock,
  TrendingUp,
  Plus,
  ArrowUpRight,
  CheckCircle2,
  AlertCircle,
  Play,
  Cpu,
  RefreshCw,
} from "lucide-react";

export default function Home() {
  const stats = [
    {
      title: "Managed Accounts",
      value: "3",
      change: "+1 this week",
      icon: Users,
      trend: "positive",
    },
    {
      title: "Scheduled Content",
      value: "14",
      change: "4 publishing today",
      icon: Video,
      trend: "neutral",
    },
    {
      title: "Active Jobs",
      value: "2",
      change: "Workers running normally",
      icon: Clock,
      trend: "positive",
    },
    {
      title: "Audience Reach",
      value: "248.5K",
      change: "+12.4% vs last cycle",
      icon: TrendingUp,
      trend: "positive",
    },
  ];

  const placeholderAccounts = [
    {
      handle: "@brand_official",
      nickname: "Brand Official",
      followers: "142.1K",
      status: "Healthy",
      lastSync: "10m ago",
    },
    {
      handle: "@creator_daily",
      nickname: "Daily Highlights",
      followers: "86.3K",
      status: "Healthy",
      lastSync: "25m ago",
    },
    {
      handle: "@product_demos",
      nickname: "Demo Lab",
      followers: "20.1K",
      status: "Review Required",
      lastSync: "2h ago",
    },
  ];

  const placeholderJobs = [
    {
      id: "JOB-1042",
      type: "Media Optimization",
      target: "@brand_official",
      status: "Processing",
      time: "Just now",
    },
    {
      id: "JOB-1041",
      type: "Analytics Sync",
      target: "@creator_daily",
      status: "Completed",
      time: "15m ago",
    },
    {
      id: "JOB-1040",
      type: "Scheduled Post Dispatch",
      target: "@product_demos",
      status: "Queued",
      time: "In 45m",
    },
  ];

  return (
    <div className="space-y-6">
      {/* Top Welcome & Actions */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-2xl font-bold text-slate-900 tracking-tight">
            Dashboard Overview
          </h2>
          <p className="text-sm text-slate-500 mt-1">
            Real-time operations hub for legitimate TikTok account management and scheduling.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            className="inline-flex items-center gap-1.5 px-3 py-2 border border-slate-200 text-xs font-medium rounded-lg text-slate-700 bg-white hover:bg-slate-50 transition-colors shadow-2xs"
          >
            <RefreshCw className="w-3.5 h-3.5 text-slate-500" />
            Refresh
          </button>
          <button
            type="button"
            className="inline-flex items-center gap-1.5 px-3.5 py-2 bg-rose-600 text-white text-xs font-medium rounded-lg hover:bg-rose-700 transition-colors shadow-2xs"
          >
            <Plus className="w-3.5 h-3.5" />
            New Post
          </button>
        </div>
      </div>

      {/* Integration & Contract Notice */}
      <div className="p-4 rounded-xl border border-blue-100 bg-gradient-to-r from-blue-50/70 via-indigo-50/40 to-slate-50 text-slate-700 text-xs flex flex-col md:flex-row items-start md:items-center justify-between gap-3 shadow-2xs">
        <div className="flex items-center gap-2.5">
          <div className="p-1.5 rounded-lg bg-blue-100 text-blue-700 shrink-0">
            <Cpu className="w-4 h-4" />
          </div>
          <div>
            <span className="font-semibold text-slate-800">
              Frontend Project Skeleton Initialized (TIK-002)
            </span>
            <span className="text-slate-600 block sm:inline sm:ml-1">
              • Next.js App Router & TypeScript ready. Awaiting backend API endpoints defined in{" "}
              <code className="bg-white/80 px-1 py-0.5 rounded border border-blue-200 text-blue-800 font-mono text-[11px]">
                docs/API_CONTRACT.md
              </code>.
            </span>
          </div>
        </div>
        <span className="shrink-0 text-[11px] font-semibold px-2 py-0.5 rounded-md bg-blue-600/10 text-blue-700">
          Placeholder Mode
        </span>
      </div>

      {/* Metric Cards Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {stats.map((stat, i) => {
          const Icon = stat.icon;
          return (
            <div
              key={i}
              className="p-5 rounded-xl border border-slate-200/80 bg-white shadow-2xs hover:shadow-xs transition-shadow"
            >
              <div className="flex items-center justify-between">
                <span className="text-xs font-medium text-slate-500">{stat.title}</span>
                <div className="p-2 rounded-lg bg-slate-100 text-slate-700">
                  <Icon className="w-4 h-4" />
                </div>
              </div>
              <div className="mt-2 flex items-baseline gap-2">
                <span className="text-2xl font-bold text-slate-900">{stat.value}</span>
                <span className="text-[11px] text-emerald-600 font-medium flex items-center">
                  <ArrowUpRight className="w-3 h-3" />
                  {stat.change}
                </span>
              </div>
            </div>
          );
        })}
      </div>

      {/* Main Grid: Accounts and Job Queue */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Managed Accounts Column */}
        <div className="lg:col-span-2 bg-white rounded-xl border border-slate-200/80 shadow-2xs p-5 space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-sm font-semibold text-slate-900">
                Connected TikTok Accounts
              </h3>
              <p className="text-xs text-slate-500">
                Active profiles registered for automated & scheduled operations.
              </p>
            </div>
            <button
              type="button"
              className="text-xs text-rose-600 font-medium hover:text-rose-700"
            >
              View all
            </button>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50/80 border-y border-slate-100 text-slate-500 uppercase tracking-wider text-[10px]">
                <tr>
                  <th className="py-2.5 px-3">Account</th>
                  <th className="py-2.5 px-3">Followers</th>
                  <th className="py-2.5 px-3">Status</th>
                  <th className="py-2.5 px-3">Last Sync</th>
                  <th className="py-2.5 px-3 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 text-slate-700">
                {placeholderAccounts.map((acc, index) => (
                  <tr key={index} className="hover:bg-slate-50/50 transition-colors">
                    <td className="py-3 px-3">
                      <div className="font-semibold text-slate-900">{acc.nickname}</div>
                      <div className="text-[11px] text-slate-400 font-mono">{acc.handle}</div>
                    </td>
                    <td className="py-3 px-3 font-medium">{acc.followers}</td>
                    <td className="py-3 px-3">
                      <span
                        className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium ${
                          acc.status === "Healthy"
                            ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
                            : "bg-amber-50 text-amber-700 border border-amber-200"
                        }`}
                      >
                        {acc.status === "Healthy" ? (
                          <CheckCircle2 className="w-2.5 h-2.5 text-emerald-500" />
                        ) : (
                          <AlertCircle className="w-2.5 h-2.5 text-amber-500" />
                        )}
                        {acc.status}
                      </span>
                    </td>
                    <td className="py-3 px-3 text-slate-500">{acc.lastSync}</td>
                    <td className="py-3 px-3 text-right">
                      <button
                        type="button"
                        className="text-xs text-slate-600 hover:text-slate-900 font-medium px-2 py-1 rounded bg-slate-100 hover:bg-slate-200 transition-colors"
                      >
                        Manage
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Worker & Background Jobs Column */}
        <div className="bg-white rounded-xl border border-slate-200/80 shadow-2xs p-5 space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-sm font-semibold text-slate-900">Worker Tasks</h3>
              <p className="text-xs text-slate-500">
                Recent queue events and scheduled executions.
              </p>
            </div>
            <span className="inline-flex items-center gap-1 text-[11px] font-semibold text-indigo-600 bg-indigo-50 px-2 py-0.5 rounded">
              <Play className="w-3 h-3 text-indigo-500" />
              Active
            </span>
          </div>

          <div className="space-y-3">
            {placeholderJobs.map((job) => (
              <div
                key={job.id}
                className="p-3 rounded-lg border border-slate-100 bg-slate-50/60 hover:bg-slate-50 transition-colors space-y-1.5"
              >
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold text-slate-800">
                    {job.type}
                  </span>
                  <span
                    className={`text-[10px] font-medium px-2 py-0.5 rounded-full ${
                      job.status === "Completed"
                        ? "bg-emerald-100/70 text-emerald-800"
                        : job.status === "Processing"
                        ? "bg-blue-100/70 text-blue-800"
                        : "bg-slate-200 text-slate-700"
                    }`}
                  >
                    {job.status}
                  </span>
                </div>
                <div className="flex items-center justify-between text-[11px] text-slate-500">
                  <span className="font-mono">{job.id} • {job.target}</span>
                  <span>{job.time}</span>
                </div>
              </div>
            ))}
          </div>

          <div className="pt-2 border-t border-slate-100">
            <p className="text-[11px] text-slate-400 text-center">
              Worker queue backed by Redis & Celery/RQ (Architecture spec)
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}

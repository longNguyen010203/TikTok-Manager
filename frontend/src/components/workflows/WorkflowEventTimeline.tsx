import React, { useEffect, useState } from "react";
import {
  AlertCircle,
  CheckCircle2,
  Clock,
  ExternalLink,
  History,
  Hourglass,
  Loader2,
  OctagonX,
  PauseCircle,
  PlayCircle,
  RotateCcw,
  Sparkles,
  ThumbsDown,
  ThumbsUp,
  UserCheck,
} from "lucide-react";
import { workflowService } from "@/services/workflowService";
import {
  WorkflowEvent,
  getWorkflowEventLabel,
} from "@/types/workflow";

interface WorkflowEventTimelineProps {
  workflowId: number;
  onViewJob?: (jobId: number) => void;
}

export function WorkflowEventTimeline({
  workflowId,
  onViewJob,
}: WorkflowEventTimelineProps) {
  const [events, setEvents] = useState<WorkflowEvent[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let ignore = false;

    workflowService
      .getEvents(workflowId, 1, 100)
      .then((res) => {
        if (ignore) return;
        setEvents(res.items);
        setError(null);
      })
      .catch((err) => {
        if (ignore) return;
        setError(
          err && typeof err === "object" && "message" in err
            ? String((err as { message: unknown }).message)
            : "Failed to load workflow events"
        );
      })
      .finally(() => {
        if (!ignore) setIsLoading(false);
      });

    return () => {
      ignore = true;
    };
  }, [workflowId]);

  const getEventIcon = (eventType: string) => {
    switch (eventType) {
      case "workflow_created":
        return <Sparkles className="w-3.5 h-3.5 text-slate-500" />;
      case "workflow_started":
        return <PlayCircle className="w-3.5 h-3.5 text-sky-500" />;
      case "job_created":
      case "step_started":
        return <Clock className="w-3.5 h-3.5 text-sky-500" />;
      case "step_succeeded":
        return <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500" />;
      case "step_failed":
        return <AlertCircle className="w-3.5 h-3.5 text-rose-500" />;
      case "waiting_for_approval":
        return <UserCheck className="w-3.5 h-3.5 text-amber-500" />;
      case "waiting":
        return <Hourglass className="w-3.5 h-3.5 text-indigo-500" />;
      case "approved":
        return <ThumbsUp className="w-3.5 h-3.5 text-emerald-500" />;
      case "rejected":
        return <ThumbsDown className="w-3.5 h-3.5 text-rose-500" />;
      case "pause_requested":
      case "paused":
        return <PauseCircle className="w-3.5 h-3.5 text-amber-500" />;
      case "resumed":
        return <PlayCircle className="w-3.5 h-3.5 text-emerald-500" />;
      case "retry_requested":
        return <RotateCcw className="w-3.5 h-3.5 text-purple-500" />;
      case "cancellation_requested":
      case "workflow_cancelled":
        return <OctagonX className="w-3.5 h-3.5 text-slate-500" />;
      case "workflow_succeeded":
        return <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600 font-bold" />;
      case "workflow_failed":
        return <AlertCircle className="w-3.5 h-3.5 text-rose-600" />;
      default:
        return <History className="w-3.5 h-3.5 text-slate-400" />;
    }
  };

  if (isLoading) {
    return (
      <div className="py-8 flex flex-col items-center justify-center text-slate-400 gap-2">
        <Loader2 className="w-5 h-5 animate-spin" />
        <span className="text-xs">Loading event timeline...</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-4 bg-rose-50 border border-rose-200 rounded-lg text-xs text-rose-700 flex items-center gap-2">
        <AlertCircle className="w-4 h-4 shrink-0" />
        <span>{error}</span>
      </div>
    );
  }

  if (events.length === 0) {
    return (
      <div className="py-8 text-center text-slate-400 text-xs">
        No events recorded for this workflow yet.
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between pb-2 border-b border-slate-200">
        <h4 className="text-xs font-semibold text-slate-700 uppercase tracking-wider">
          Event Audit Log ({events.length})
        </h4>
        <span className="text-[11px] text-slate-400">Chronological</span>
      </div>

      <div className="relative pl-5 space-y-3.5 before:absolute before:left-2 before:top-2 before:bottom-2 before:w-0.5 before:bg-slate-200">
        {events.map((event) => {
          const label = getWorkflowEventLabel(event.event_type);

          return (
            <div key={event.id} className="relative group text-xs">
              {/* Event bullet */}
              <div className="absolute -left-5 top-0.5 w-4 h-4 rounded-full bg-white border border-slate-200 flex items-center justify-center shadow-xs">
                {getEventIcon(event.event_type)}
              </div>

              {/* Event row */}
              <div className="flex flex-wrap items-center justify-between gap-2 bg-slate-50/70 hover:bg-slate-100/70 transition-colors p-2 rounded border border-slate-200/80">
                <div className="flex items-center gap-2">
                  <span className="font-medium text-slate-800">{label}</span>

                  {event.job_id && (
                    <button
                      type="button"
                      onClick={() => onViewJob?.(event.job_id!)}
                      className="inline-flex items-center gap-1 text-[11px] text-indigo-600 hover:text-indigo-800 font-mono px-1.5 py-0.5 rounded bg-indigo-50 hover:bg-indigo-100 border border-indigo-200 transition-colors"
                      title="View Job"
                    >
                      <span>Job #{event.job_id}</span>
                      <ExternalLink className="w-2.5 h-2.5" />
                    </button>
                  )}

                  {event.workflow_step_id && (
                    <span className="text-[10px] font-mono text-slate-400 bg-slate-100 px-1 py-0.5 rounded border border-slate-200">
                      Step #{event.workflow_step_id}
                    </span>
                  )}
                </div>

                <div className="text-[11px] text-slate-400 font-mono">
                  {new Date(event.created_at).toLocaleTimeString()}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

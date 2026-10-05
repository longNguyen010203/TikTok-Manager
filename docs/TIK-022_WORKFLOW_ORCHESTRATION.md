# TIK-022 Workflow Orchestration

## Foundation

Jobs remain the only executable and worker-claimable unit. A Workflow is a
durable state machine that materializes server-owned steps, creates typed Jobs
through existing domain services, observes their terminal truth, and advances
dependencies. It does not run handlers, ADB, shell commands, or Android input.

V1 is deliberately sequential. The registry contains
`content_delivery_review:v1` and `content_delivery_wait_review:v1`:

1. `content.deliver` pins and delivers the Workflow's exact ready content
   version to its exact Runtime through `ContentDeliveryService`.
2. `workflow.approval` creates no Job and waits durably for an operator.

The API never accepts arbitrary step definitions or Job payloads. Template
parameters use strict schemas with unknown fields forbidden.

The wait-review template inserts `workflow.wait` between delivery and
approval. It accepts a bounded 1–86,400 second duration. The engine also
validates an internal absolute UTC `resume_at` form, with exactly one time
source allowed. Entering the step calculates the deadline once, stores it in
`WorkflowStep.resume_at`, records one `waiting` event, and creates no Job.
Restart reconciliation compares the persisted deadline and never recalculates
the duration.

## State and retry boundaries

Workflow states are `draft`, `pending`, `running`, `waiting`, `paused`,
`succeeded`, `failed`, `cancelling`, and `cancelled`. Step states are `pending`,
`ready`, `running`, `waiting`, `succeeded`, `failed`, `skipped`, `cancelling`,
and `cancelled`. All transitions are explicit and versioned.

Worker retries increment `Job.attempt_count` on the same Job. A
`WorkflowStep.attempt` represents a distinct materialization and is not
incremented by transient worker retry. Phase 2 operator retry reuses an
eligible failed Job through existing Job retry semantics; it never creates a
replacement after attempts are exhausted or blindly replays uncertain work.

Pause is boundary-only. With an active linked Job, a pause request is recorded
and the Job is allowed to reach terminal truth; the Workflow pauses before the
next step. Cancellation prevents new steps, cancels future steps, requests
cancellation through the existing Job lifecycle, and waits for acknowledgement.
If Job success wins the race, that truth is preserved but no next step starts.

## Concurrency and recovery

Every transition uses `workflow-<id>.lock` in a private directory. The guard
uses no-follow opens and host `flock`, supports nonblocking and bounded waits,
does not serialize unrelated Workflows, and releases automatically when a
process exits.

The user-level workflow orchestrator periodically scans durable candidates,
locks and reloads each one, and reconciles at most one next step. It never
claims Jobs. Deterministic delivery idempotency plus the unique step/job-run
constraints prevent duplicate creation across a crash. A restart can observe
an already linked terminal Job and finish the same step. Waiting approval,
pause requests, cancellation requests, and event history live only in SQLite,
not process memory.

Each pass reconciles terminal linked-Job truth, pause/cancel requests, and wait
state before materializing a successor. A failure for one Workflow is logged
with its ID and does not starve unrelated candidates. Production polling is
bounded; top-level infrastructure failures back off to a 30-second maximum.

An unexpected cancelled Job fails with `WORKFLOW_JOB_CANCELLED`. If Job success
wins a Workflow cancellation race, that success and its safe result are
preserved while all successors are cancelled. A missing pinned Runtime fails
with `WORKFLOW_RUNTIME_UNAVAILABLE`; deleted/unready content and invalid blobs
retain stable content errors and are never replaced by another version.

## Security boundary

Bindings are explicit and validated: the Runtime must exist and be Redroid,
the exact version must belong to the asset and be ready, and an assigned
Account must match the explicit Runtime. Runtime and version are never inferred
or silently changed. Workflow events contain bounded safe business metadata,
never credentials, claim tokens, raw payloads, paths, commands, ADB output, or
subprocess output.

## Operational service

`tiktok-manager-workflow-orchestrator.service` uses the project virtualenv and
canonical local configuration. It wants and starts after the backend, restarts
on failure, handles SIGTERM, and has no worker ordering dependency. The one-time
installer enables backend, worker, orchestrator, and maintenance timers.

## Phase 3 live validation

Phase 3 validated both templates through the installed backend, worker, and
orchestrator services on disposable managed Runtime 7 (`redroid-device-21`,
`localhost:5575`). Delivery created exactly one linked Job per step. Approval
survived an orchestrator restart; the persisted wait deadline advanced once;
backend and worker restarts did not duplicate delivery; a held Runtime lock
produced retryable `RUNTIME_BUSY` and the same Job later succeeded; and an
active-Job pause stopped only at the next step boundary.

Pending, approval-waiting, and active-linked-Job cancellation paths reached a
truthful terminal state without starting a successor. A stopped Runtime failed
without auto-start and an explicit operator retry reused the same Job, Runtime,
and pinned version. Deprovision removed the disposable container and network,
preserved its data directory, retained `runtime_id_snapshot`, cleared the live
Runtime foreign key, and failed a pending pinned workflow with
`WORKFLOW_RUNTIME_UNAVAILABLE`. Device01/02/03 remained stopped and unchanged.

Full DAGs, caller-defined executable workflows, and TikTok-specific actions
remain explicitly out of scope.

## Phase 4 recovery validation

Production fault injection used disposable managed Runtime 9
(`redroid-device-23`, `localhost:5577`) and left Device01/02/03 stopped and
unchanged. Both a workflow-orchestrator restart and a backend restart during a
25-second `workflow.wait` preserved the exact `resume_at` value. Each wait
completed after its original deadline, emitted one `waiting` event, and
advanced to approval once.

An abrupt worker termination during a managed delivery expired the old claim,
reclaimed the same linked Job on its second worker attempt, and reused the
already-successful durable ContentDelivery. The WorkflowStep retained one
JobRun and the orchestrator did not materialize a replacement. A separate
crash window deliberately left `Job=succeeded` while its WorkflowStep was
still `running`; restart reconciliation projected the same Job result and
created the approval step exactly once.

The live race matrix also verified boundary pause, Job-success winning a
cancellation race, concurrent approval conflict, and deprovision between a
pending Runtime-dependent step and reconciliation. Success truth was retained,
successors were not started after cancellation, and a missing pinned Runtime
failed as `WORKFLOW_RUNTIME_UNAVAILABLE` while retaining
`runtime_id_snapshot`. Approval of an already completed delivery remained a
historical review action after deprovision.

Idle orchestration consumes a bounded polling interval (a five-second service
sample used about 2.6 ms CPU). Top-level failures use exponential delay capped
at 30 seconds and reset after a healthy pass. Backend, worker, and orchestrator
were restarted independently and together without changing Job or Delivery
counts. The final database audit found no orphan Workflow rows, shared Job
ownership, stale leases, invalid current-step pointers, active Workflows, or
stuck cancellation.

Managed provisioning allocates new Device and Runtime primary keys above both
live rows and durable provisioning tombstones under the cross-process
allocation transaction. This prevents SQLite primary-key reuse from making
immutable Runtime snapshots historically ambiguous after deprovision.

## Phase 6 production integration

Production stress used two disposable managed Runtimes and multiple real
workers. Large deliveries to different Runtimes overlapped, while a held lock
on one Runtime produced retryable `RUNTIME_BUSY` on three Jobs; each retained
one linked WorkflowStep/Delivery and succeeded through its existing Job retry
policy after release. Concurrent same-key creation returned one Workflow to
all callers, with a conflicting fingerprint returning 409. Approval,
retry/pause/cancel, and due-wait races retained one authoritative transition
and emitted no duplicate business events.

Three waits with distinct persisted deadlines survived an orchestrator,
backend, and worker restart sweep and advanced independently. A deterministic
Playwright suite covers both templates, approval/rejection,
pause/resume/cancel/retry, wait countdown, event and Job navigation, and
friendly stopped-Runtime/screen-conflict errors without requiring Android.
The operator procedures are in
[`TIK-022_WORKFLOW_RUNBOOK.md`](TIK-022_WORKFLOW_RUNBOOK.md).

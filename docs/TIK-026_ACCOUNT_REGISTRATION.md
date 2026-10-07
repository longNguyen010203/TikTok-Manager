# TIK-026 Account Registration Workflow

## Phase 1 architecture

Account registration is a state-driven orchestration above existing Jobs. It
is not a fixed list of taps. Every reconciliation observes the current TikTok
screen with the pinned UI profile, routes from that durable observation, and
materializes at most one typed action Job. Jobs remain the only execution unit.

The proposed server-owned blueprint is `account_registration:v1`, bound to an
exact Account, Runtime, derived Device snapshot, ManagedApp, ManagedAppVersion,
and pinned TikTok UI profile. It has one orchestration controller concept,
`registration.state_machine`, which observes and schedules typed Jobs; it never
executes ADB itself. The blueprint is intentionally not registered in the
public template registry in Phase 1 because no signup-entry action has yet been
live-calibrated. Exposing a known non-executable template would create Workflows
that can only fail.

## Workflow state machine

Durable workflow phases are:

- `detecting_entry`: obtain a fresh foreground/hierarchy observation.
- `routing_entry`: select a calibrated entry route.
- `entering_canonical_flow`: navigate either fresh or existing-session entry.
- `in_canonical_flow`: resume the exact observed signup state.
- `verification_required`: durable operator-required pause.
- `completed`: Android state confirms registration completion.
- `terminal_failed`: only a confirmed, non-recoverable failure.

Candidate UI states are `REGISTRATION_ENTRY`, `LOGIN_OR_SIGNUP`,
`SIGNUP_METHOD`, `DOB`, `EMAIL_OR_PHONE`, `EMAIL_ENTRY`, `PASSWORD_ENTRY`,
`USERNAME_ENTRY`, `REGISTRATION_REVIEW`, `REGISTRATION_COMPLETE`, and
`VERIFICATION_REQUIRED`, plus `HOME`, `PROFILE`, and `UNKNOWN`. These names are
semantic calibration targets, not claims that current profiles recognize the
screens. In the Phase 1 catalog only `HOME` is calibrated, inherited from the
live-validated TIK-024 profile. Every other registration state and action is
fail-closed until observed in a new immutable profile generation.

`SIGNUP_METHOD` is the planned convergence point. A fresh Runtime may reach it
from a direct login/signup entry. A Runtime with an existing session must
navigate `HOME -> PROFILE -> account switcher/settings -> Add Account -> Sign
Up -> SIGNUP_METHOD`. If execution restarts on DOB, email, password, username,
or review, the router resumes from that observed state and never replays entry
navigation.

## Durable registration session

Phase 2 should add one `account_registration_sessions` row per Workflow, similar
to PublishingSession but with Workflow/Job remaining authoritative. Recommended
fields are:

- workflow/account/runtime/device snapshots and pinned app/profile IDs;
- workflow phase, last calibrated screen, and safe snapshot fingerprint;
- active typed action Job ID and monotonic mutation sequence;
- verification type, waiting reason, and safe error code/message;
- started, last-observed, verification-requested, and completed timestamps.

The active Job ID plus deterministic action idempotency key prevents duplicate
mutation scheduling after backend/orchestrator restart. A pending/running Job
is reconciled before another observation can authorize a successor. UI-mutating
registration Jobs use `max_attempts=1`; recovery first observes the screen and
only creates a later action when the prior postcondition is proven.

## Account and secret binding

Creation requires an existing non-archived Account assigned to the exact
Runtime (or atomically assigned during explicit workflow creation). Device ID
is copied from `Runtime.device_id`; callers cannot supply an independent Device
or infer another Runtime. The Account begins with `registration_state=pending`.

Job payloads contain IDs only. They never contain email/password values,
ciphertext, key paths, or arbitrary selectors. A future typed credential-entry
execution boundary resolves an allowlisted Account secret only after claim,
Runtime lock, UI-profile, screen, and field-selector validation. It decrypts
`account_password` through `AccountSecretProvider` immediately before internal
text entry and discards/overwrites the temporary buffer as soon as practical.
There is no decrypting HTTP API. `email_password` remains reserved for a future
operator-approved email-verification boundary and is not part of ordinary
TikTok UI payloads.

## Verification and resume

CAPTCHA, OTP, email/SMS verification, suspicious-login, identity, and unknown
challenge observations produce `verification_required`. Safe history includes
only verification type, screen, timestamp, Account ID, Runtime ID, and Device
ID. The Workflow enters a durable waiting state and creates no solver Job.

After the operator completes the challenge manually, resume means detect again
and route from the new calibrated state. It never assumes the challenge passed
and never replays the prior mutation. Unknown or uncalibrated states remain
paused with a calibration/operator requirement.

## Completion semantics

Only a calibrated `REGISTRATION_COMPLETE` observation may finalize registration.
The completion transaction should set `Account.registration_state=registered`,
retain its exact Runtime, apply a safely discovered normalized handle, set a
non-error lifecycle/health state, and append a safe registration event. A
terminal confirmed failure sets `registration_state=failed` and a sanitized
reason without deleting the Account. Transient infrastructure, stopped Runtime,
unknown UI, and verification pauses do not mark the Account failed.

## Live calibration plan

### A. Fresh/no-account Runtime

1. Provision a new disposable Runtime with fresh app data and exact managed
   TikTok version; record Device/Runtime/ADB/profile bindings.
2. Launch only through the existing typed app action.
3. Read foreground activity and bounded hierarchy; run read-only detection.
4. Calibrate the actual initial login/signup screen from multiple observed
   resource/accessibility/structural signals.
5. Calibrate one unique Sign Up method-entry action and its postcondition.
6. Stop before entering DOB, email, password, OTP, CAPTCHA, or any credential.

### B. Existing logged-in session

1. Use a separate disposable Runtime with an operator-controlled existing
   session; never use Device01/02/03.
2. Confirm calibrated HOME read-only.
3. In a later mutation-calibration phase, activate the already observed Profile
   tab exactly once and capture the real PROFILE hierarchy.
4. Calibrate account menu/switcher, Add Account, login/signup entry, and Sign Up
   transitions one at a time with fresh pre/postcondition checks.
5. Prove both paths arrive at the same calibrated `SIGNUP_METHOD` state, then
   stop without submitting registration data.

The exact first calibration targets are therefore the fresh initial
login/signup screen, PROFILE, account switcher/settings, Add Account,
login-or-signup choice, and signup-method screen. DOB and later field-entry
screens follow only after entry convergence is proven.

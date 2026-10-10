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

## Phase 2A fresh-runtime calibration checkpoint

Disposable Runtime 18 (ADB `localhost:5586`) was provisioned with fresh app
data and the required Trill 44.4.3 managed version. Typed launch Job 271
succeeded and read-only detection Job 272 confirmed TikTok foreground in
`NewUserJourneyActivity`, but the TikTok registration hierarchy was covered by
Android's one-time immersive-mode education overlay. The bounded hierarchy
contained the jointly required system signals
`android:id/immersive_cling_chevron`, `immersive_cling_title`,
`immersive_cling_description`, and the clickable `android:id/ok` button.

This is classified as `BLOCKING_MODAL`, not as a TikTok registration screen or
permission prompt. No automation dismisses it: an operator must acknowledge
the one-time Android system overlay, after which calibration resumes with a
new read-only observation. No registration selector or `tiktok.open_signup`
action is introduced until the underlying TikTok screen and a unique Sign Up
target have both been observed.

After the operator dismissed the Android overlay, Runtime 18 exposed a
14-node TikTok-owned hierarchy in `NewUserJourneyActivity`. This is not a
login/signup chooser: it is a `TERMS_CONSENT` gate with exact observed roots
`hyp` and `wjh`, title `x37`, terms body `eal`, illustration `jet`, and unique
clickable `Agree and continue` control `eac`. Testing profile v12 recognizes
the screen from four required plus two reinforcing signals. Read-only Job 274
live-classified it as `TERMS_CONSENT` with `changed=false`.

No Sign Up, Log in, phone/email, or provider action exists in this hierarchy.
The consent control is deliberately non-actionable and the registration router
records the next boundary as uncalibrated `registration.accept_terms`. A later
explicit calibration phase must authorize that consent transition before the
underlying login/signup or signup-method screen can be observed.

After the operator manually accepted the terms checkpoint, Runtime 18 exposed
the `ONBOARDING_INTERESTS` screen rather than registration entry. The observed
hierarchy contains exact scene/content/GridView roots (`ss8`, `k2m`, `sx0`),
the title `iz1` (`Choose your interests`), subtitle `tk2`, repeated selectable
interest tiles `kat`, bottom action region `bzw`, unique `Skip` button `chn`,
and disabled `Next (0)` button `ceq`. Testing profile v13 classifies this state
from six required and three reinforcing signals; read-only Job 276 confirmed
the classification with `changed=false`.

No signup, login, provider, phone/email, or DOB control is present. Testing
profile v14 authorizes only the unique observed Skip control (`chn`) for the
typed, one-attempt `tiktok.skip_interests` action. Interest tiles and the
disabled Next control remain non-actionable. The action performs two fresh
semantic observations, holds the exact Runtime lock for the full transition,
and never automatically replays after dispatch.

Live Job 278 on Runtime 18 resolved Skip by exact resource ID, dispatched one
tap, and transitioned from `ONBOARDING_INTERESTS` to the already-calibrated
`HOME` state. The postcondition contained 174 normalized nodes and hierarchy
fingerprint `4cac1f63e806b5b8eda581056893f41c7ef8bacc017c4bae970ceed110e48508`.
The registration router therefore treats the Skip boundary as calibrated and
routes its observed HOME successor into the existing-session entry path. The
next safe calibration is the typed HOME-to-Profile transition; no Sign Up,
Login, or Add Account control was activated during this phase.

## Phase 2B HOME-to-Profile calibration

Runtime 18 initially reached HOME after Job 278, but a safe stop/launch cycle
later resumed directly into TikTok's 48-node `I18nSignUpActivity`. That screen
contains phone entry, Continue with Email, and an Already-have-an-account Log
in control. It was observed only: no field or action was activated. Fresh HOME
is therefore a transient onboarding observation, not yet proven as a durable
shared Profile-entry state.

Preserved existing-session Runtime 17 supplied the calibrated HOME target.
Read-only Job 285 returned HOME and a locked hierarchy capture resolved exactly
one Profile tab (`n12`, description `Profile`, clickable FrameLayout,
`[576,1100][720,1184]`) with no overlay. Testing profile v15 authorizes only
that selector for the one-attempt `tiktok.open_profile` Job.

Live Job 286 dispatched that Profile selector exactly once. Its v15
postcondition conservatively returned `TIKTOK_UI_STATE_UNCERTAIN` because the
destination retained HOME's bottom navigation and was not yet classified.
The subsequent read-only 150-node hierarchy proved a logged-in PROFILE state:
stable roots `r5r` and `t4f`, header `o6f`, unique `Profile menu`, display-name
button `r5d`, handle button `r7b`, media-tabs container `wpc`, and an observed
`Add person` accessibility signal. Profile v16 classifies this state without
depending on account text or metrics and forbids its profile root from HOME.
Read-only Job 287 returned PROFILE. Idempotency Job 288 then returned
PROFILE-to-PROFILE with `changed=false`, `tap_dispatched=false`, and no second
selector dispatch.

No direct Add Account or account-switcher control was observed. `Add person`
appears to be a social/add-person affordance and is not treated as account
switching. The exact next safe boundary is read-only calibration of the unique
Profile menu followed, only in a later approved phase, by a typed
`tiktok.open_profile_menu` action.

## Phase 2C logged-out Profile-tab destination

Runtime 18 was no longer at HOME when this continuation began. After its exact
Runtime was restored through the typed lifecycle API, read-only detect Job 289
again observed TikTok's 48-node `I18nSignUpActivity`; stop/launch had previously
resumed the same activity. No existing typed action can return this state to
HOME, and Close/Back are not calibrated, so the requested causal HOME Profile
tap was deliberately not fabricated or replaced with raw input.

The already-observed hierarchy is now calibrated as `SIGNUP_METHOD`, the
canonical registration convergence state. Required signals are the exact
`ss8` scene, `uee` content, and `pgc` phone containers together with the
`Sign up for TikTok` title, `Phone number` EditText, and `Continue with Email`
accessibility signal. `Continue`, `Already have an account? Log in`, and the
`xc7` Close control reinforce classification but are not actionable. Google,
Facebook, and Apple controls were not present.

Testing profile v17 retains all older immutable definitions and adds only this
observed classifier. `tiktok.open_profile` is retained for compatibility but
is documented as activate Profile tab: from HOME it may reach logged-in
`PROFILE` or logged-out `SIGNUP_METHOD`; both are idempotent destinations and
anything else fails closed. The route therefore no longer requires PROFILE as
an intermediate state for logged-out devices. A clean causal live proof still
requires an operator to return Runtime 18 to HOME without automation, after
which the existing typed action can be run once. The next registration action
to calibrate is the observed `Continue with Email` parent/target; it remains
non-actionable until that separate calibration is approved.

## Phase 2D Continue with Email

Runtime 18 remained at overlay-free `SIGNUP_METHOD`. A locked read-only capture
confirmed the unique semantic child `Continue with Email` as an enabled,
non-clickable `android.view.View` at `[56,830][664,868]`, inside its enabled,
clickable `android.view.View` parent at `[56,830][664,916]`. Testing profile
v18 authorizes only that semantic child's bounds; phone input, generic
Continue, Log in, Close, and Report remain non-actionable.

Preflight detect Job 292 confirmed `SIGNUP_METHOD`. One-attempt Job 293 then
resolved `signup_email_method` by content-description and dispatched exactly
one tap. It stopped at a 39-node uncalibrated successor without typing or
submitting data. The read-only hierarchy proved `EMAIL_ENTRY` in
`SignUpOrLoginActivity`: exact root/scene/header/form IDs `hyp`, `mvq`, `bii`,
and `efn`; title `ehn` (`Enter email address`); focused empty `Email address`
EditText; disabled Continue `evj`; save-login row `gfk`; domain-suggestion
list `ld_`; and a Back button. No credential mutation was performed.

The first immutable v19 classifier used the email label's wrong semantic field
and read-only Job 294 safely returned UNKNOWN. It was not rewritten. Profile
v20 corrected the selector to normalized node text, and Job 295 classified
`EMAIL_ENTRY`. Idempotency Job 296 then returned EMAIL_ENTRY-to-EMAIL_ENTRY
with `changed=false` and `tap_dispatched=false`. Registration routing now maps
`SIGNUP_METHOD -> registration.choose_email_signup -> EMAIL_ENTRY`; email
entry itself remains a non-mutating resume/calibration boundary.

## Phase 2E account-bound email entry

Testing profile v21 authorizes only the unique EMAIL_ENTRY EditText. Because
its visible text changes from the empty label to the Account email, resolution
uses the observed `android.widget.EditText` class plus FrameLayout,
LinearLayout, and ViewGroup ancestry and still requires exactly one match.
Continue `evj`, phone controls, save-login, and Back remain non-actionable.

The public request contains only `managed_app_id` and `account_id`. Creation
and execution both require the canonical Account to exist, have a valid email,
and be assigned to the exact Runtime. Execution reuses the Account Registry's
canonical normalization, decrypts no secret, and keeps plaintext out of Job
payload, result, and JobLog rows. Safe diagnostics contain Account ID, presence,
length, and SHA-256 only.

Dedicated Account 6 was bound to Runtime 18. Preflight Job 297 confirmed
EMAIL_ENTRY under profile v21. One-attempt Job 298 focused the email field once,
replaced its empty label with the server-resolved Account email, and verified
exact equality while remaining on EMAIL_ENTRY. Continue became enabled but was
not activated. The safe result reported `email_length=26`, `verification=true`,
and `continue_enabled=true`. A direct persistence audit found zero plaintext
matches in Job payload, result, messages, or metadata and exactly one
`selector_resolved` focus-dispatch event.

## Phase 2F verified-email Continue boundary

Testing profile v22 authorizes only the exact observed Continue button
`com.ss.android.ugc.trill:id/evj`. The public request contains only ManagedApp
and Account IDs. Creation and execution revalidate the Account-to-Runtime
binding and canonical email; immediately before dispatch, two identical fresh
semantic observations must show `EMAIL_ENTRY`, exact field equality, no
blocking overlay, and one enabled Continue target. The Job has one attempt and
cannot replay after dispatch.

Preflight Job 299 classified `EMAIL_ENTRY` under v22. Job 300 resolved
`email_continue` by exact resource ID and dispatched one tap. Because its
successor had not yet been calibrated, the pinned v22 Job conservatively ended
`TIKTOK_UI_STATE_UNCERTAIN`; its safe log proves one dispatch and no retry.
Read-only calibration then observed `SignUpOrLoginActivity` with a 32-node
email-link/code checkpoint: root/scene/header `hyp`/`mvq`/`bii`, content `bik`,
fixed title `ehn` (`Check your email`), dynamic destination message `eft`, form
`efn`, code container `k59`, one focused EditText, and Resend button `k58`.

Profile v23 classifies this multi-signal state as `VERIFICATION_REQUIRED`.
Dynamic destination text is excluded from profile matching and results. The
checkpoint is operator-required: no email-password access, code entry, resend,
OTP handling, CAPTCHA handling, or verification bypass is implemented. A
repeat Continue request from this calibrated successor returns zero-tap
`changed=false`.

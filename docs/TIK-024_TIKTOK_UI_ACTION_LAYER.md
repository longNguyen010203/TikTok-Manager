# TIK-024 TikTok UI Action Layer

Phase 2 provides internal Android UI sessions and observational TikTok screen
detection. It does not implement create-flow navigation, media selection,
caption/options, account/login handling, or publishing. No public raw ADB,
shell, selector, coordinate, or text-input API exists.

`AndroidUiAutomationService.open_session(runtime_id)` reloads the exact
Redroid mapping, acquires `RuntimeOperationGuard`, checks container/boot/ADB
readiness and screen conflicts, and holds that guard until the session closes.
Typed ADB commands always use the database serial, argument arrays,
`shell=False`, timeouts, bounded output, and exact-child cancellation.

UIAutomator XML is bounded by bytes, nodes, nesting, text, and attribute size.
DTD/entities and malformed bounds are rejected. Password text is removed and
fingerprints use non-sensitive structure, not arbitrary UI text. Raw XML is
never persisted.

Selectors and screens are immutable repository resources referenced by DB
profile metadata. Resolution prefers resource ID, accessibility description,
normalized server text, then class/structure, and requires one match.
Coordinates are profile/display/orientation bound. Screen classification
requires multiple signals and a score margin; login/signup/challenge states
remain `UNKNOWN`.

The initial `trill-44.4.3-testing-v1` profile pins
`com.ss.android.ugc.trill` version code `440403` but is deliberately
uncalibrated. Phase 3 must use a new disposable Runtime to launch the managed
app through `device.launch_app`, capture foreground activity and bounded UI
hierarchy, run server-created `tiktok.detect_screen`, and document unresolved
signals. Only observed selectors may then be added; no Create tap occurs during
calibration.

Calibration API sequence (IDs are examples):

```bash
curl -X POST http://127.0.0.1:8000/jobs \
  -H 'Content-Type: application/json' \
  -d '{"job_type":"device.launch_app","runtime_id":13,"payload":{"package_name":"com.ss.android.ugc.trill"}}'

curl -X POST http://127.0.0.1:8000/runtimes/13/tiktok/detect-screen \
  -H 'Content-Type: application/json' \
  -d '{"managed_app_id":1}'
```

The installed worker claims both Jobs. Inspect only the safe Job/result/log
APIs (`GET /jobs/{id}` and `GET /jobs/{id}/logs`). Foreground activity and raw
hierarchy capture remain internal diagnostic calls; they are not public API.

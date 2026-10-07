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

## Phase 3 live calibration result

The controlled disposable Runtime used package `com.ss.android.ugc.trill`,
version `44.4.3`/`440403`, at 720x1280 portrait. The normalized hierarchy had
32 nodes and an application viewport of 720x1184. Both typed foreground
queries observed
`com.ss.android.ugc.aweme.account.login.auth.I18nSignUpActivityWithNoAnimation`.
The hierarchy exposed login/signup controls, not HOME navigation or a Create
control. Because TIK-024 forbids login/signup handling, this state remains the
safe unsupported `UNKNOWN` classification.

No HOME, `create_button`, MEDIA_PICKER, or media-item selectors were added,
and the testing profile fingerprint remains unchanged. No coordinate fallback
was recorded. `open_home`, `open_create`, and `select_media` must remain
unavailable until a lawfully prepared disposable Runtime opens on HOME and its
real semantic signals can be calibrated. This is an explicit safety gate, not
a reason to tap a presumed close, Back, or first gallery item.

Live calibration also established two generic UI transport facts now covered
by tests: UIAutomator may append a diagnostic line after `</hierarchy>`, and
Android may emit zero-area system-decoration nodes. The typed executor now
extracts exactly one XML document, while the parser accepts empty rectangles
but continues rejecting reversed bounds. Android 12 foreground-window parsing
uses the fixed `dumpsys window` service form because the `windows` subcommand
omitted focus state on this Redroid build.

### Runtime 17 HOME continuation

The operator subsequently prepared disposable Runtime 17 so the same package
and version opened on HOME. The typed session observed 720x1280 portrait,
`SplashActivity`, and a 185-node hierarchy. Testing profile v2 records only
these observed English-locale semantic nodes:

| Selector | Resource ID | Accessibility | Class | Bounds |
|---|---|---|---|---|
| bottom_navigation | `com.ss.android.ugc.trill:id/n18` | — | `android.widget.LinearLayout` | `[0,1100][720,1184]` |
| home_tab | `com.ss.android.ugc.trill:id/n10` | Home | `android.widget.FrameLayout` | `[0,1100][144,1184]` |
| friends_tab | `com.ss.android.ugc.trill:id/n0z` | Friends | `android.widget.FrameLayout` | `[144,1100][288,1184]` |
| create_button | `com.ss.android.ugc.trill:id/n0x` | Create | `android.widget.Button` | `[288,1100][432,1184]` |
| inbox_tab | `com.ss.android.ugc.trill:id/n11` | Inbox | `android.widget.FrameLayout` | `[432,1100][576,1184]` |
| profile_tab | `com.ss.android.ugc.trill:id/n12` | Profile | `android.widget.FrameLayout` | `[576,1100][720,1184]` |
| following_area | — | Following | `android.widget.FrameLayout` | `[192,48][375,164]` |
| for_you_area | — | For You | `android.widget.LinearLayout` | `[375,48][528,164]` |

The five navigation controls are enabled; the tabs and unique Create button
are clickable children of the bottom navigation container. HOME requires the
container, Home, Create, and Profile signals, with Friends, Inbox, Following,
and For You as reinforcement. Profile v2 remains `testing`, has no coordinate
fallback, and is fingerprinted as
`a7b89eb91c4c7d03320c9edb41a577fdd77dcabab5b155cecdb30c815ee5c4ae`.
Profile v1 remains immutable for previously pinned Jobs.

A later HOME snapshot exposed TikTok's dynamic navigation variant: the second
tab was `Shop` (`com.ss.android.ugc.trill:id/e2p`) rather than `Friends`.
Job 204 revealed that a missing exact Friends signal incorrectly fell through
to a broad class-only match and treated 26 unrelated clickable FrameLayouts as
ambiguous. Screen classification now tests signal presence without requiring a
unique action target, while an actionable resolution still requires exactly
one node. Selectors with semantic identifiers never degrade to class-only
matching. The required Home/Create/Profile/container signals remained exact;
read-only Job 205 classified the 198-node snapshot as HOME. The repository
profile data did not change, so the v2 fingerprint remains unchanged.

### Create action and Android permission boundary

`tiktok.open_create` is server-created through the narrow Runtime API. It
accepts only a Managed App ID, pins the compatible UI profile, requires HOME,
resolves the unique `create_button`, rechecks foreground and snapshot freshness,
and taps through the internal typed Android UI session. The Runtime lock is
held through bounded postcondition observation.

Runtime 17 exposed the Android permission controller after Create. The
observed foreground was `com.android.permissioncontroller` with
`GrantPermissionsActivity`; the hierarchy contained `grant_dialog`,
`permission_message`, and controller-owned allow/deny button resources. This
is reported as non-retryable `TIKTOK_PERMISSION_REQUIRED` with overlay
`ANDROID_PERMISSION_PROMPT`, not as a TikTok screen. No permission response is
pressed automatically. A retry while the prompt remains detects it before any
tap, preventing a second Create action. Unknown controller overlays remain
conservatively uncertain.

After the operator granted the camera/microphone prompt, Runtime 17 exposed the
real TikTok 44.4.3 camera/create UI. Testing profile v3 adds only these observed
signals:

| Logical signal | Resource/accessibility | Class | Actionable |
| --- | --- | --- | --- |
| camera_create_root | `com.ss.android.ugc.trill:id/video_record_new_scene_root` | `android.widget.FrameLayout` | no |
| camera_record_button | `com.ss.android.ugc.trill:id/rts` | `android.widget.Button` | yes |
| camera_add_sound_button | `com.ss.android.ugc.trill:id/ddk` | `android.widget.Button` | yes |
| camera_mode_strip | `com.ss.android.ugc.trill:id/uyf` | `android.widget.FrameLayout` | no |
| camera_flip_button | content description `Flip` | `android.widget.Button` | yes |
| camera_flash_button | content description `Flash` | `android.widget.Button` | yes |
| gallery_entry | `com.ss.android.ugc.trill:id/zne` under an `android.widget.RelativeLayout` | `android.widget.FrameLayout` | yes |

`CAMERA_CREATE` requires the root, record, and Add Sound signals and uses the
remaining observed controls as reinforcement. Profile v3 is still `testing`,
uses no coordinate fallback, and has fingerprint
`f635e2157270b33370cf742e6adbe75b5925bb2b368f056ae6e6863fdc913937`.
`open_create` treats CAMERA_CREATE as a proven successful postcondition and is
idempotent there.

`POST /runtimes/{runtime_id}/tiktok/open-media-picker` creates the server-owned
`tiktok.open_media_picker` Job. It accepts only a Managed App ID, requires
CAMERA_CREATE, resolves the exact profile-owned `gallery_entry`, and holds the
Runtime lock through postcondition observation. Runtime 17 then presented a
second Android-owned photos/media permission dialog with observed resources
`grant_singleton`, `grant_dialog`, `permission_message`,
`permission_allow_button`, and `permission_deny_button`. The backend reports
this as `TIKTOK_PERMISSION_REQUIRED` with `permission_kind=media`; it never
presses either response.

After the operator granted photos/media access, Runtime 17 exposed the real
picker hierarchy. Testing profile v4 adds the observed picker signals below;
the empty-state text is reinforcement only and is not required:

| Logical signal | Resource/accessibility | Class | Required |
| --- | --- | --- | --- |
| picker_root | `com.ss.android.ugc.trill:id/f9y` | `android.widget.LinearLayout` | yes |
| picker_header | `com.ss.android.ugc.trill:id/alh` | `android.widget.RelativeLayout` | yes |
| picker_recents | `com.ss.android.ugc.trill:id/d98` with TextView descendant `Recents` | `android.widget.LinearLayout` | yes |
| picker_tabs | `com.ss.android.ugc.trill:id/n_y` | `android.widget.HorizontalScrollView` | yes |
| picker_viewpager | `com.ss.android.ugc.trill:id/viewpager_choose_media` | `androidx.viewpager.widget.ViewPager` | yes |
| picker_grid | `com.ss.android.ugc.trill:id/ik9` | `android.widget.GridView` | yes |
| picker_close | `com.ss.android.ugc.trill:id/bc9`, description `Close` | `android.widget.ImageView` | no |
| picker_all_tab | description `All` | `android.widget.FrameLayout` | no |
| picker_videos_tab | description `Videos` | `android.widget.FrameLayout` | no |
| picker_photos_tab | description `Photos` | `android.widget.FrameLayout` | no |
| picker_live_photos_tab | description `Live Photos` | `android.widget.FrameLayout` | no |
| picker_select_multiple | `com.ss.android.ugc.trill:id/nua` | `android.widget.RelativeLayout` | no |
| picker_empty_state | `com.ss.android.ugc.trill:id/odo` | `android.widget.TextView` | no |

Because TikTok leaves the camera hierarchy mounted beneath the picker, profile
v4 forbids `picker_root` for CAMERA_CREATE. The v4 fingerprint is
`9633850f8d74315f56063c5b8980d000e3928e9b959a274ca0411c3407091b9e`.
Live Job 220 classified the 193-node hierarchy as MEDIA_PICKER. Live Job 221
then proved idempotency with `changed=false` and no selector dispatch. No media
was selected.

### Media identity boundary

ContentDelivery 69 delivered `tik024-media-identity-d69.mp4` to Runtime 17 and
created MediaStore row `content://media/external/file/20`. The trusted remote
file size (17,308 bytes), pinned ContentAssetVersion 8, and SHA-256 all matched
the durable delivery record. Despite that, the already-open TikTok picker
remained byte-for-byte structurally identical to the empty calibration:
193 nodes, hierarchy fingerprint
`5448d9b6e6007616afcda2a5208a01fea93a962acb016c0e06cf5ca63b203d28`,
an empty `ik9` GridView, and the `odo` empty-state node. No filename, URI,
duration, thumbnail node, or other media-item identity appeared.

This initial empty observation established the resolver policy: it accepts a
successful ContentDelivery ID, revalidates its exact Runtime/version/MediaStore
identity server-side, and inspects only profile-owned picker-grid nodes. Zero
visible candidates maps to `TIKTOK_MEDIA_NOT_FOUND`; multiple candidates or
position-only evidence maps to `TIKTOK_MEDIA_AMBIGUOUS`. Grid order alone is
never identity. Job 224 then supplied the required recognized picker refresh
and populated hierarchy evidence described below.

After Job 224 closed/reopened the picker through the calibrated gallery entry,
the hierarchy refreshed to 197 nodes with fingerprint
`4858a837751e8ce4ad4de678147cf3fd71a6736cbc4486fad9f9a10a1710c6de`.
The empty-state node disappeared and `ik9` exposed exactly one direct clickable
`FrameLayout` tile at `[4,238][239,476]`. Its descendants were thumbnail
`n_z`, overlay `fv7`, and duration `fvf` with text `00:02`; TikTok still did
not expose a filename or MediaStore URI in the hierarchy.

The typed MediaStore inventory independently showed exactly one eligible media
object: ID 20, exact delivery filename, 17,308 bytes, `video/mp4`, duration
2,000 ms, relative path `Download/TikTokManager/`, bucket `TikTokManager`.
`MediaIdentityResolver` therefore proved a one-to-one inventory/grid mapping
plus matching duration and resolved the tile by
`exclusive_media_inventory_duration`. This is not position-based: another
eligible MediaStore item, more than one tile, a duration mismatch, or missing
delivery identity produces `TIKTOK_MEDIA_AMBIGUOUS`; an empty grid produces
`TIKTOK_MEDIA_NOT_FOUND`.

The typed `tiktok.select_media` action is created only by
`POST /runtimes/{runtime_id}/tiktok/select-media`. Its body contains only
`managed_app_id` and `content_delivery_id`; filenames, MediaStore IDs,
selectors, and coordinates are resolved server-side. The one-attempt Job holds
the exact Runtime lock, captures the picker and MediaStore inventory twice,
and requires both observations to remain identical before its single tap.
After dispatch it observes but never retries or taps again. The first proven
departure from MEDIA_PICKER is returned as `screen_after=UNKNOWN` with
`calibration_required=true`; uncertain outcomes fail closed as
`TIKTOK_UI_STATE_UNCERTAIN`.

Live Job 227 used Delivery 69 and dispatched `delivered_media` exactly once by
`exclusive_media_inventory_duration`. The tap changed the hierarchy from the
197-node picker to a 151-node, currently uncalibrated editor screen while the
foreground remained TikTok in `SAASceneWrapperActivity`. Read-only Job 228
therefore reported `UNKNOWN`. The observed successor includes root/scene IDs
`sqd`, `g9a`, and `g9_`, a bottom action container `bza`/`t2b`/`lil`, a
clickable `oca` container whose `ocd` TextView says `Next`, and an `Edit`
button in the `umn` tool list. No successor control was activated. This live
finding removed an overly strict requirement for two identical unknown-screen
fingerprints: dynamic uncalibrated screens now return calibration-required on
the first proven departure from MEDIA_PICKER.

### Post-selection editor profile v5

Repeated read-only captures of Runtime 17 produced the same 151-node editor
structure and fingerprint. The canonical screen is `EDIT_MEDIA`: it presents
editing tools and a distinct Next boundary, but is not yet the caption/post
screen. Profile v5 remains `testing`, has fingerprint
`70d10ad2d5692029d49d454af1ad0cf2ca21a2ee504c1cf1fc6cacef133244a8`,
and classifies from stable structure rather than preview content:

| Signal | Observed identity | Role |
| --- | --- | --- |
| editor_scene_root | `sqd`, FrameLayout | required |
| editor_scene_main | `g9_`, FrameLayout | required |
| editor_bottom_region | `bza`, FrameLayout | required |
| editor_action_row | `lil`, LinearLayout | required |
| editor_next_action | `oca`, clickable LinearLayout with TextView descendant | required |
| editor_tool_list | `umn`, LinearLayout | required |
| editor_scene_content | `g9a`, FrameLayout | reinforcing |
| editor_bottom_container | `t2b`, FrameLayout | reinforcing |
| editor_next_label | `ocd`, text `Next` | reinforcing |
| editor_edit_control | description `Edit`, clickable Button below a LinearLayout | reinforcing |
| editor_sound_control | `ddk`, clickable LinearLayout | reinforcing |

Dynamic preview/render nodes are excluded. Absence of any core signal prevents
classification. `tiktok.select_media` now treats MEDIA_PICKER → EDIT_MEDIA as
its calibrated successful postcondition. If invoked while already on
EDIT_MEDIA it returns `changed=false`, `tap_dispatched=false`, and performs no
MediaStore query or tap.

### Editor Next and ready-to-publish profile v7

`POST /runtimes/{runtime_id}/tiktok/open-caption` accepts only
`managed_app_id` and creates the server-owned, one-attempt
`tiktok.open_caption` Job. Profile v6 authorizes only the observed `oca`
`editor_next_action`; the action takes two identical semantic snapshots,
resolves the selector uniquely each time, and dispatches at most one tap.
After dispatch it never retries. Job 233 live-validated the transition from
EDIT_MEDIA to a previously unknown 92-node screen with one dispatch.

That screen is canonically `READY_TO_PUBLISH`, because it combines the caption
field, privacy/options controls, Drafts, and the final Post control on one
screen. Testing profile v7 fingerprint
`6081585ed317b52f23b82cb251be6dfa381efd46c724473dd03c03d9ca4d1b4f`
uses the observed `rhf` root, `rhg` ScrollView, `gbc` EditText, `c07` bottom
region, `fpr` action row, and `rhc` Post button as core signals. `rh6`, `fob`,
`bc5`, and the observed privacy/more-options buttons reinforce the result.
Drafts and Post remain non-actionable. No link/product control was exposed in
this capture. Calling `open_caption` from READY_TO_PUBLISH returns
`changed=false`, `tap_dispatched=false` and cannot tap Next again.

`POST /runtimes/{runtime_id}/tiktok/set-caption` accepts only a Managed App ID
and caption. Caption normalization applies Unicode NFKC, rejects control,
surrogate, private-use, and unassigned characters, trims the ends, collapses
Unicode whitespace deterministically, and limits the result to 150 characters.
It preserves ordinary multilingual letters, hashtags, emoji, and punctuation;
an empty caption is allowed. The active typed ADB provider has a narrower
verified ASCII transport capability and rejects unsupported transport input
before field focus, rather than rewriting or damaging it. Profile v8 makes
only the observed `gbc` EditText actionable. The action revalidates two
identical READY_TO_PUBLISH snapshots, focuses once, verifies the keyboard,
clears with fixed backend-owned MOVE_END/DEL keycodes, enters through the
internal typed text provider, verifies exact field equality, and closes the
proven keyboard. It never targets privacy, options, Drafts, or Post and is
never replayed after mutation. JobLogs contain caption length and SHA-256 only.

### Privacy post-option calibration

Job 239 opened the real privacy control on Runtime 17 exactly once and stopped
without selecting a value. The resulting 43-node bottom sheet is canonically
`POST_SETTINGS`. Its stable core is the `f9y` Bottom sheet FrameLayout, `u76`
modal root, `o60` “Privacy settings” title, `pek` “Who can view this post”
question, and checked choice rows. The observed choices were Everyone,
Friends, and Only you. Everyone and Only you have exact stable accessibility
descriptions and are the only initial server-owned mappings:
`everyone -> privacy_everyone` and `only_you -> privacy_only_you`. Friends is
visible but unsupported because its parent description includes dynamic
follower/account text; the implementation does not infer it from position.

Testing profile v9 fingerprint
`e73e1c311f4d1b432fcd38503f7fc6f3a832b322378d62825f6e03c5d7774f54`
authorizes only the READY_TO_PUBLISH privacy entry. Testing profile v10
fingerprint
`abe32a853bef79e9860bccdf9737655068daef7eb3d67a1227ee07021731d112`
adds POST_SETTINGS classification and the two calibrated choices. The typed
`tiktok.set_post_options` action accepts no labels, selectors, coordinates, or
arbitrary option payloads. It revalidates immediately before a single option
tap and verifies the exact checked state afterward. Drafts and Post remain
non-actionable.

Live Job 264 established that TikTok closes POST_SETTINGS after a privacy
choice. Testing profile v11 fingerprint
`f9e2bbab68804942a06651546a61d45d1ca7301393a23fb4605a01def7cbf673`
records the observed `Everyone can view this post` and `Only you can view this
post` READY_TO_PUBLISH summaries. Postcondition verification accepts either
the modal's exact checked state or the exact returned READY summary; it never
replays the completed choice tap.

### Read-only prepare-publish boundary

`tiktok.prepare_publish` is a server-created, safe-retryable observational Job.
Its narrow Runtime endpoint accepts only Managed App ID, ContentDelivery ID,
expected caption, and the calibrated expected privacy enum. Delivery validation
is repeated at creation and execution. Media presence is proven by the
backend-resolved MediaStore ID together with exact display name, size, MIME,
and duration; picker order is never evidence. The action verifies the exact
normalized caption, exact READY privacy summary, and unique non-actionable
Drafts/Post controls twice with an unchanged structure fingerprint. Its service
contract has no tap callback and executes no focus, text, keyevent, Back, or
other UI mutation.

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

"""Repository-owned, immutable TikTok selector and screen definitions."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, replace

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import TikTokUiProfile
from app.services.tiktok_errors import tiktok_error


@dataclass(frozen=True)
class StructuralConstraint:
    ancestor_class_names: tuple[str, ...] = ()
    descendant_class_names: tuple[str, ...] = ()


@dataclass(frozen=True)
class TikTokElementSelector:
    key: str
    resource_ids: tuple[str, ...] = ()
    content_descriptions: tuple[str, ...] = ()
    normalized_text: tuple[str, ...] = ()
    class_names: tuple[str, ...] = ()
    structure: StructuralConstraint = StructuralConstraint()
    require_enabled: bool = True
    require_clickable: bool | None = None
    require_focusable: bool | None = None
    visual_fallback_key: str | None = None
    coordinate_fallback_key: str | None = None
    actionable: bool = False


@dataclass(frozen=True)
class ScreenDefinition:
    key: str
    required_selectors: tuple[str, ...]
    reinforcing_selectors: tuple[str, ...] = ()
    forbidden_selectors: tuple[str, ...] = ()
    minimum_score: int = 2
    calibrated: bool = True


@dataclass(frozen=True)
class ProfileCoordinate:
    key: str
    screen_key: str
    width: int
    height: int
    orientation: str
    x: int
    y: int


@dataclass(frozen=True)
class TikTokUiProfileDefinition:
    resource_key: str
    package_name: str
    selectors: tuple[TikTokElementSelector, ...]
    screens: tuple[ScreenDefinition, ...]
    coordinates: tuple[ProfileCoordinate, ...] = ()

    @property
    def fingerprint(self) -> str:
        payload = json.dumps(asdict(self), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode()).hexdigest()


# Deliberately uncalibrated. Phase 3 will replace empty signal definitions with
# observations from the controlled 44.4.3 installation; no resource IDs are guessed.
TRILL_44_4_3_TESTING = TikTokUiProfileDefinition(
    resource_key="trill-44.4.3-testing-v1",
    package_name="com.ss.android.ugc.trill",
    selectors=(),
    screens=tuple(
        ScreenDefinition(key=name, required_selectors=(), calibrated=False)
        for name in ("HOME", "CREATE_ENTRY", "MEDIA_PICKER", "EDIT_MEDIA", "CAPTION", "POST_SETTINGS", "READY_TO_PUBLISH")
    ),
)


# Calibrated from the normalized hierarchy of the controlled Runtime 17. Every
# value below was observed on Trill 44.4.3/440403 at 720x1280 portrait; no
# coordinate fallback is present.
TRILL_44_4_3_HOME_V2 = TikTokUiProfileDefinition(
    resource_key="trill-44.4.3-home-v2",
    package_name="com.ss.android.ugc.trill",
    selectors=(
        TikTokElementSelector(
            key="bottom_navigation",
            resource_ids=("com.ss.android.ugc.trill:id/n18",),
            class_names=("android.widget.LinearLayout",),
            require_clickable=False,
        ),
        TikTokElementSelector(
            key="home_tab",
            resource_ids=("com.ss.android.ugc.trill:id/n10",),
            content_descriptions=("Home",),
            class_names=("android.widget.FrameLayout",),
            structure=StructuralConstraint(ancestor_class_names=("android.widget.LinearLayout",)),
            require_clickable=True,
        ),
        TikTokElementSelector(
            key="friends_tab",
            resource_ids=("com.ss.android.ugc.trill:id/n0z",),
            content_descriptions=("Friends",),
            class_names=("android.widget.FrameLayout",),
            structure=StructuralConstraint(ancestor_class_names=("android.widget.LinearLayout",)),
            require_clickable=True,
        ),
        TikTokElementSelector(
            key="create_button",
            resource_ids=("com.ss.android.ugc.trill:id/n0x",),
            content_descriptions=("Create",),
            class_names=("android.widget.Button",),
            structure=StructuralConstraint(ancestor_class_names=("android.widget.LinearLayout",)),
            require_clickable=True,
            actionable=True,
        ),
        TikTokElementSelector(
            key="inbox_tab",
            resource_ids=("com.ss.android.ugc.trill:id/n11",),
            content_descriptions=("Inbox",),
            class_names=("android.widget.FrameLayout",),
            structure=StructuralConstraint(ancestor_class_names=("android.widget.LinearLayout",)),
            require_clickable=True,
        ),
        TikTokElementSelector(
            key="profile_tab",
            resource_ids=("com.ss.android.ugc.trill:id/n12",),
            content_descriptions=("Profile",),
            class_names=("android.widget.FrameLayout",),
            structure=StructuralConstraint(ancestor_class_names=("android.widget.LinearLayout",)),
            require_clickable=True,
        ),
        TikTokElementSelector(
            key="following_area",
            content_descriptions=("Following",),
            class_names=("android.widget.FrameLayout",),
            require_clickable=False,
        ),
        TikTokElementSelector(
            key="for_you_area",
            content_descriptions=("For You",),
            normalized_text=("For You",),
            class_names=("android.widget.LinearLayout",),
            require_clickable=False,
        ),
    ),
    screens=(
        ScreenDefinition(
            key="HOME",
            required_selectors=("bottom_navigation", "home_tab", "create_button", "profile_tab"),
            reinforcing_selectors=("friends_tab", "inbox_tab", "following_area", "for_you_area"),
            minimum_score=8,
        ),
        *(ScreenDefinition(key=name, required_selectors=(), calibrated=False) for name in (
            "CREATE_ENTRY", "MEDIA_PICKER", "EDIT_MEDIA", "CAPTION",
            "POST_SETTINGS", "READY_TO_PUBLISH",
        )),
    ),
)


# Runtime 17 camera/create calibration. This is a new immutable generation;
# the v2 HOME-only profile remains available to already-pinned Jobs.
_CAMERA_CREATE_SELECTORS = (
    TikTokElementSelector(
        key="camera_create_root",
        resource_ids=("com.ss.android.ugc.trill:id/video_record_new_scene_root",),
        class_names=("android.widget.FrameLayout",),
        require_clickable=False,
    ),
    TikTokElementSelector(
        key="camera_record_button",
        resource_ids=("com.ss.android.ugc.trill:id/rts",),
        class_names=("android.widget.Button",),
        require_clickable=True,
    ),
    TikTokElementSelector(
        key="camera_add_sound_button",
        resource_ids=("com.ss.android.ugc.trill:id/ddk",),
        class_names=("android.widget.Button",),
        require_clickable=True,
    ),
    TikTokElementSelector(
        key="camera_mode_strip",
        resource_ids=("com.ss.android.ugc.trill:id/uyf",),
        class_names=("android.widget.FrameLayout",),
        require_clickable=False,
    ),
    TikTokElementSelector(
        key="camera_flip_button",
        content_descriptions=("Flip",),
        class_names=("android.widget.Button",),
        require_clickable=True,
    ),
    TikTokElementSelector(
        key="camera_flash_button",
        content_descriptions=("Flash",),
        class_names=("android.widget.Button",),
        require_clickable=True,
    ),
    TikTokElementSelector(
        key="gallery_entry",
        resource_ids=("com.ss.android.ugc.trill:id/zne",),
        class_names=("android.widget.FrameLayout",),
        structure=StructuralConstraint(
            ancestor_class_names=("android.widget.RelativeLayout",),
        ),
        require_clickable=True,
        actionable=True,
    ),
)

TRILL_44_4_3_CAMERA_V3 = replace(
    TRILL_44_4_3_HOME_V2,
    resource_key="trill-44.4.3-camera-v3",
    selectors=TRILL_44_4_3_HOME_V2.selectors + _CAMERA_CREATE_SELECTORS,
    screens=TRILL_44_4_3_HOME_V2.screens + (
        ScreenDefinition(
            key="CAMERA_CREATE",
            required_selectors=(
                "camera_create_root", "camera_record_button",
                "camera_add_sound_button",
            ),
            reinforcing_selectors=(
                "camera_mode_strip", "camera_flip_button",
                "camera_flash_button", "gallery_entry",
            ),
            minimum_score=6,
        ),
    ),
)


# Runtime 17 media-picker calibration. TikTok keeps the camera hierarchy
# mounted underneath the picker, so CAMERA_CREATE explicitly forbids the
# picker root in this immutable generation.
_MEDIA_PICKER_SELECTORS = (
    TikTokElementSelector(
        key="picker_root",
        resource_ids=("com.ss.android.ugc.trill:id/f9y",),
        class_names=("android.widget.LinearLayout",),
        require_clickable=False,
    ),
    TikTokElementSelector(
        key="picker_header",
        resource_ids=("com.ss.android.ugc.trill:id/alh",),
        class_names=("android.widget.RelativeLayout",),
        require_clickable=False,
    ),
    TikTokElementSelector(
        key="picker_close",
        resource_ids=("com.ss.android.ugc.trill:id/bc9",),
        content_descriptions=("Close",),
        class_names=("android.widget.ImageView",),
        require_clickable=True,
    ),
    TikTokElementSelector(
        key="picker_recents",
        resource_ids=("com.ss.android.ugc.trill:id/d98",),
        class_names=("android.widget.LinearLayout",),
        structure=StructuralConstraint(
            descendant_class_names=("android.widget.TextView",),
        ),
        require_clickable=True,
    ),
    TikTokElementSelector(
        key="picker_text_action",
        resource_ids=("com.ss.android.ugc.trill:id/wr6",),
        class_names=("android.widget.LinearLayout",),
        require_clickable=True,
    ),
    TikTokElementSelector(
        key="picker_tabs",
        resource_ids=("com.ss.android.ugc.trill:id/n_y",),
        class_names=("android.widget.HorizontalScrollView",),
        require_clickable=False,
    ),
    TikTokElementSelector(
        key="picker_all_tab",
        content_descriptions=("All",),
        class_names=("android.widget.FrameLayout",),
        require_clickable=False,
    ),
    TikTokElementSelector(
        key="picker_videos_tab",
        content_descriptions=("Videos",),
        class_names=("android.widget.FrameLayout",),
        require_clickable=True,
    ),
    TikTokElementSelector(
        key="picker_photos_tab",
        content_descriptions=("Photos",),
        class_names=("android.widget.FrameLayout",),
        require_clickable=True,
    ),
    TikTokElementSelector(
        key="picker_live_photos_tab",
        content_descriptions=("Live Photos",),
        class_names=("android.widget.FrameLayout",),
        require_clickable=True,
    ),
    TikTokElementSelector(
        key="picker_viewpager",
        resource_ids=("com.ss.android.ugc.trill:id/viewpager_choose_media",),
        class_names=("androidx.viewpager.widget.ViewPager",),
        require_clickable=False,
    ),
    TikTokElementSelector(
        key="picker_grid",
        resource_ids=("com.ss.android.ugc.trill:id/ik9",),
        class_names=("android.widget.GridView",),
        require_clickable=False,
    ),
    TikTokElementSelector(
        key="picker_empty_state",
        resource_ids=("com.ss.android.ugc.trill:id/odo",),
        normalized_text=("No photos or videos available",),
        class_names=("android.widget.TextView",),
        require_clickable=False,
    ),
    TikTokElementSelector(
        key="picker_select_multiple",
        resource_ids=("com.ss.android.ugc.trill:id/nua",),
        class_names=("android.widget.RelativeLayout",),
        require_clickable=True,
    ),
)

TRILL_44_4_3_MEDIA_PICKER_V4 = replace(
    TRILL_44_4_3_CAMERA_V3,
    resource_key="trill-44.4.3-media-picker-v4",
    selectors=TRILL_44_4_3_CAMERA_V3.selectors + _MEDIA_PICKER_SELECTORS,
    screens=tuple(
        replace(screen, forbidden_selectors=("picker_root",))
        if screen.key == "CAMERA_CREATE"
        else ScreenDefinition(
            key="MEDIA_PICKER",
            required_selectors=(
                "picker_root", "picker_header", "picker_recents",
                "picker_tabs", "picker_viewpager", "picker_grid",
            ),
            reinforcing_selectors=(
                "picker_close", "picker_text_action", "picker_all_tab",
                "picker_videos_tab", "picker_photos_tab",
                "picker_live_photos_tab", "picker_select_multiple",
                "picker_empty_state",
            ),
            minimum_score=12,
        )
        if screen.key == "MEDIA_PICKER"
        else screen
        for screen in TRILL_44_4_3_CAMERA_V3.screens
    ),
)


# Runtime 17 post-selection media editor calibration. Preview/rendering nodes
# are deliberately excluded: only the durable scene, action, and tool regions
# observed in repeated read-only captures participate in classification.
_EDIT_MEDIA_SELECTORS = (
    TikTokElementSelector(
        key="editor_scene_root",
        resource_ids=("com.ss.android.ugc.trill:id/sqd",),
        class_names=("android.widget.FrameLayout",),
        require_clickable=False,
    ),
    TikTokElementSelector(
        key="editor_scene_content",
        resource_ids=("com.ss.android.ugc.trill:id/g9a",),
        class_names=("android.widget.FrameLayout",),
        require_clickable=False,
    ),
    TikTokElementSelector(
        key="editor_scene_main",
        resource_ids=("com.ss.android.ugc.trill:id/g9_",),
        class_names=("android.widget.FrameLayout",),
        require_clickable=False,
    ),
    TikTokElementSelector(
        key="editor_bottom_region",
        resource_ids=("com.ss.android.ugc.trill:id/bza",),
        class_names=("android.widget.FrameLayout",),
        require_clickable=False,
    ),
    TikTokElementSelector(
        key="editor_bottom_container",
        resource_ids=("com.ss.android.ugc.trill:id/t2b",),
        class_names=("android.widget.FrameLayout",),
        require_clickable=False,
    ),
    TikTokElementSelector(
        key="editor_action_row",
        resource_ids=("com.ss.android.ugc.trill:id/lil",),
        class_names=("android.widget.LinearLayout",),
        require_clickable=False,
    ),
    TikTokElementSelector(
        key="editor_next_action",
        resource_ids=("com.ss.android.ugc.trill:id/oca",),
        class_names=("android.widget.LinearLayout",),
        structure=StructuralConstraint(
            descendant_class_names=("android.widget.TextView",),
        ),
        require_clickable=True,
    ),
    TikTokElementSelector(
        key="editor_next_label",
        resource_ids=("com.ss.android.ugc.trill:id/ocd",),
        normalized_text=("Next",),
        class_names=("android.widget.TextView",),
        require_clickable=False,
    ),
    TikTokElementSelector(
        key="editor_tool_list",
        resource_ids=("com.ss.android.ugc.trill:id/umn",),
        class_names=("android.widget.LinearLayout",),
        require_clickable=False,
    ),
    TikTokElementSelector(
        key="editor_edit_control",
        content_descriptions=("Edit",),
        class_names=("android.widget.Button",),
        structure=StructuralConstraint(
            ancestor_class_names=("android.widget.LinearLayout",),
        ),
        require_clickable=True,
    ),
    TikTokElementSelector(
        key="editor_sound_control",
        resource_ids=("com.ss.android.ugc.trill:id/ddk",),
        class_names=("android.widget.LinearLayout",),
        require_clickable=True,
    ),
)

TRILL_44_4_3_EDITOR_V5 = replace(
    TRILL_44_4_3_MEDIA_PICKER_V4,
    resource_key="trill-44.4.3-editor-v5",
    selectors=TRILL_44_4_3_MEDIA_PICKER_V4.selectors + _EDIT_MEDIA_SELECTORS,
    screens=tuple(
        ScreenDefinition(
            key="EDIT_MEDIA",
            required_selectors=(
                "editor_scene_root", "editor_scene_main",
                "editor_bottom_region", "editor_action_row",
                "editor_next_action", "editor_tool_list",
            ),
            reinforcing_selectors=(
                "editor_scene_content", "editor_bottom_container",
                "editor_next_label", "editor_edit_control",
                "editor_sound_control",
            ),
            forbidden_selectors=("picker_root",),
            minimum_score=12,
        )
        if screen.key == "EDIT_MEDIA"
        else screen
        for screen in TRILL_44_4_3_MEDIA_PICKER_V4.screens
    ),
)


# Action-authorized generation for the already calibrated editor Next target.
# V5 remains immutable and observational; V6 changes no screen signals.
TRILL_44_4_3_EDITOR_ACTION_V6 = replace(
    TRILL_44_4_3_EDITOR_V5,
    resource_key="trill-44.4.3-editor-action-v6",
    selectors=tuple(
        replace(selector, actionable=True)
        if selector.key == "editor_next_action"
        else selector
        for selector in TRILL_44_4_3_EDITOR_V5.selectors
    ),
)


# Runtime 17 post-screen calibration captured immediately after the sole v6
# editor Next dispatch. Final submission controls are observational only and
# deliberately remain non-actionable.
_READY_TO_PUBLISH_SELECTORS = (
    TikTokElementSelector(
        key="post_scene_root",
        resource_ids=("com.ss.android.ugc.trill:id/rhf",),
        class_names=("android.widget.RelativeLayout",),
        require_clickable=False,
    ),
    TikTokElementSelector(
        key="post_scroll",
        resource_ids=("com.ss.android.ugc.trill:id/rhg",),
        class_names=("android.widget.ScrollView",),
        require_clickable=False,
    ),
    TikTokElementSelector(
        key="caption_input",
        resource_ids=("com.ss.android.ugc.trill:id/gbc",),
        class_names=("android.widget.EditText",),
        require_clickable=True,
    ),
    TikTokElementSelector(
        key="post_options_root",
        resource_ids=("com.ss.android.ugc.trill:id/rh6",),
        class_names=("android.widget.RelativeLayout",),
        require_clickable=False,
    ),
    TikTokElementSelector(
        key="post_bottom_region",
        resource_ids=("com.ss.android.ugc.trill:id/c07",),
        class_names=("android.widget.RelativeLayout",),
        require_clickable=False,
    ),
    TikTokElementSelector(
        key="post_action_row",
        resource_ids=("com.ss.android.ugc.trill:id/fpr",),
        class_names=("android.widget.LinearLayout",),
        require_clickable=False,
    ),
    TikTokElementSelector(
        key="draft_action",
        resource_ids=("com.ss.android.ugc.trill:id/fob",),
        normalized_text=("Drafts",),
        class_names=("android.widget.Button",),
        require_clickable=True,
    ),
    TikTokElementSelector(
        key="publish_action",
        resource_ids=("com.ss.android.ugc.trill:id/rhc",),
        normalized_text=("Post",),
        class_names=("android.widget.Button",),
        require_clickable=True,
    ),
    TikTokElementSelector(
        key="post_back",
        resource_ids=("com.ss.android.ugc.trill:id/bc5",),
        class_names=("android.widget.Button",),
        require_clickable=True,
    ),
    TikTokElementSelector(
        key="post_privacy",
        resource_ids=("com.ss.android.ugc.trill:id/d7b",),
        content_descriptions=("Everyone can view this post",),
        class_names=("android.widget.Button",),
        require_clickable=True,
    ),
    TikTokElementSelector(
        key="post_more_options",
        resource_ids=("com.ss.android.ugc.trill:id/d7b",),
        content_descriptions=("More options",),
        class_names=("android.widget.Button",),
        require_clickable=True,
    ),
)

TRILL_44_4_3_READY_V7 = replace(
    TRILL_44_4_3_EDITOR_ACTION_V6,
    resource_key="trill-44.4.3-ready-v7",
    selectors=(
        TRILL_44_4_3_EDITOR_ACTION_V6.selectors
        + _READY_TO_PUBLISH_SELECTORS
    ),
    screens=tuple(
        ScreenDefinition(
            key="READY_TO_PUBLISH",
            required_selectors=(
                "post_scene_root", "post_scroll", "caption_input",
                "post_bottom_region", "post_action_row", "publish_action",
            ),
            reinforcing_selectors=(
                "post_options_root", "draft_action", "post_back",
                "post_privacy", "post_more_options",
            ),
            forbidden_selectors=("editor_scene_root", "picker_root"),
            minimum_score=12,
        )
        if screen.key == "READY_TO_PUBLISH"
        else screen
        for screen in TRILL_44_4_3_EDITOR_ACTION_V6.screens
    ),
)


# Action-authorized caption generation. Final submission controls remain
# observational and non-actionable.
TRILL_44_4_3_CAPTION_ACTION_V8 = replace(
    TRILL_44_4_3_READY_V7,
    resource_key="trill-44.4.3-caption-action-v8",
    selectors=tuple(
        replace(selector, actionable=True)
        if selector.key == "caption_input"
        else selector
        for selector in TRILL_44_4_3_READY_V7.selectors
    ),
)


# Calibration-authorized privacy entry. The duplicated d7b resource ID is not
# used for mutation; the observed accessibility description uniquely
# distinguishes this control from More options.
TRILL_44_4_3_PRIVACY_ENTRY_V9 = replace(
    TRILL_44_4_3_CAPTION_ACTION_V8,
    resource_key="trill-44.4.3-privacy-entry-v9",
    selectors=TRILL_44_4_3_CAPTION_ACTION_V8.selectors + (
        TikTokElementSelector(
            key="privacy_entry_action",
            content_descriptions=("Everyone can view this post",),
            class_names=("android.widget.Button",),
            require_clickable=True,
            actionable=True,
        ),
    ),
)


_PRIVACY_MODAL_SELECTORS = (
    TikTokElementSelector(
        key="privacy_sheet",
        resource_ids=("com.ss.android.ugc.trill:id/f9y",),
        content_descriptions=("Bottom sheet",),
        class_names=("android.widget.FrameLayout",),
        require_clickable=False,
    ),
    TikTokElementSelector(
        key="privacy_modal_root",
        resource_ids=("com.ss.android.ugc.trill:id/u76",),
        class_names=("android.widget.RelativeLayout",),
        require_clickable=False,
    ),
    TikTokElementSelector(
        key="privacy_title",
        resource_ids=("com.ss.android.ugc.trill:id/o60",),
        normalized_text=("Privacy settings",),
        class_names=("android.widget.TextView",),
        require_clickable=False,
    ),
    TikTokElementSelector(
        key="privacy_question",
        resource_ids=("com.ss.android.ugc.trill:id/pek",),
        normalized_text=("Who can view this post",),
        class_names=("android.widget.TextView",),
        require_clickable=False,
    ),
    TikTokElementSelector(
        key="privacy_everyone",
        content_descriptions=("Everyone",),
        class_names=("android.view.ViewGroup",),
        require_clickable=True,
        actionable=True,
    ),
    TikTokElementSelector(
        key="privacy_friends_label",
        normalized_text=("Friends",),
        class_names=("android.widget.TextView",),
        require_clickable=False,
    ),
    TikTokElementSelector(
        key="privacy_only_you",
        content_descriptions=("Only you",),
        class_names=("android.view.ViewGroup",),
        require_clickable=True,
        actionable=True,
    ),
    TikTokElementSelector(
        key="privacy_close",
        content_descriptions=("Close",),
        class_names=("android.widget.Button",),
        require_clickable=True,
    ),
)

TRILL_44_4_3_PRIVACY_MODAL_V10 = replace(
    TRILL_44_4_3_PRIVACY_ENTRY_V9,
    resource_key="trill-44.4.3-privacy-modal-v10",
    selectors=TRILL_44_4_3_PRIVACY_ENTRY_V9.selectors + _PRIVACY_MODAL_SELECTORS,
    screens=tuple(
        ScreenDefinition(
            key="POST_SETTINGS",
            required_selectors=(
                "privacy_sheet", "privacy_modal_root", "privacy_title",
                "privacy_question", "privacy_everyone", "privacy_only_you",
            ),
            reinforcing_selectors=("privacy_friends_label", "privacy_close"),
            forbidden_selectors=("post_scene_root",),
            minimum_score=12,
        )
        if screen.key == "POST_SETTINGS"
        else screen
        for screen in TRILL_44_4_3_PRIVACY_ENTRY_V9.screens
    ),
)


# Runtime 17 demonstrated that choosing a privacy value closes the bottom
# sheet and returns to READY_TO_PUBLISH. These exact summaries were observed
# for the two server-owned values; they also keep the entry action resolvable
# after either value is selected.
TRILL_44_4_3_PRIVACY_AUTOCLOSE_V11 = replace(
    TRILL_44_4_3_PRIVACY_MODAL_V10,
    resource_key="trill-44.4.3-privacy-autoclose-v11",
    selectors=tuple(
        replace(
            selector,
            content_descriptions=(
                "Everyone can view this post",
                "Only you can view this post",
            ),
        )
        if selector.key == "privacy_entry_action"
        else selector
        for selector in TRILL_44_4_3_PRIVACY_MODAL_V10.selectors
    ) + (
        TikTokElementSelector(
            key="privacy_summary_everyone",
            content_descriptions=("Everyone can view this post",),
            class_names=("android.widget.Button",),
            require_clickable=True,
        ),
        TikTokElementSelector(
            key="privacy_summary_only_you",
            content_descriptions=("Only you can view this post",),
            class_names=("android.widget.Button",),
            require_clickable=True,
        ),
    ),
)


# Runtime 18 fresh-install calibration. The first TikTok-owned UI is a terms
# consent gate, not a signup-method chooser. The consent control remains
# observational/non-actionable until a separately approved mutation phase.
_TERMS_CONSENT_SELECTORS = (
    TikTokElementSelector(
        key="terms_scene_root",
        resource_ids=("com.ss.android.ugc.trill:id/hyp",),
        class_names=("android.widget.FrameLayout",),
        require_clickable=False,
    ),
    TikTokElementSelector(
        key="terms_content",
        resource_ids=("com.ss.android.ugc.trill:id/wjh",),
        class_names=("android.view.ViewGroup",),
        require_clickable=False,
    ),
    TikTokElementSelector(
        key="terms_title",
        resource_ids=("com.ss.android.ugc.trill:id/x37",),
        normalized_text=("TikTok's Terms and Policies",),
        class_names=("android.widget.TextView",),
        require_clickable=False,
    ),
    TikTokElementSelector(
        key="terms_body",
        resource_ids=("com.ss.android.ugc.trill:id/eal",),
        class_names=("android.widget.TextView",),
        require_clickable=False,
    ),
    TikTokElementSelector(
        key="terms_illustration",
        resource_ids=("com.ss.android.ugc.trill:id/jet",),
        content_descriptions=("center_icon",),
        class_names=("android.widget.ImageView",),
        require_clickable=False,
    ),
    TikTokElementSelector(
        key="terms_agree_control",
        resource_ids=("com.ss.android.ugc.trill:id/eac",),
        normalized_text=("Agree and continue",),
        class_names=("android.widget.Button",),
        structure=StructuralConstraint(
            ancestor_class_names=("android.view.ViewGroup",),
        ),
        require_clickable=True,
    ),
)

TRILL_44_4_3_TERMS_V12 = replace(
    TRILL_44_4_3_PRIVACY_AUTOCLOSE_V11,
    resource_key="trill-44.4.3-terms-v12",
    selectors=(
        TRILL_44_4_3_PRIVACY_AUTOCLOSE_V11.selectors
        + _TERMS_CONSENT_SELECTORS
    ),
    screens=TRILL_44_4_3_PRIVACY_AUTOCLOSE_V11.screens + (
        ScreenDefinition(
            key="TERMS_CONSENT",
            required_selectors=(
                "terms_scene_root", "terms_content", "terms_title",
                "terms_agree_control",
            ),
            reinforcing_selectors=("terms_body", "terms_illustration"),
            forbidden_selectors=("bottom_navigation", "picker_root"),
            minimum_score=8,
        ),
    ),
)


# Runtime 18 post-terms calibration. The screen asks the operator to choose
# recommendation interests and is not a login/signup or signup-method screen.
# Skip and interest tiles remain observational/non-actionable in this phase.
_ONBOARDING_INTEREST_SELECTORS = (
    TikTokElementSelector(
        key="interests_scene_root",
        resource_ids=("com.ss.android.ugc.trill:id/ss8",),
        class_names=("android.view.ViewGroup",),
        require_clickable=False,
    ),
    TikTokElementSelector(
        key="interests_content",
        resource_ids=("com.ss.android.ugc.trill:id/k2m",),
        class_names=("android.view.ViewGroup",),
        require_clickable=False,
    ),
    TikTokElementSelector(
        key="interests_grid",
        resource_ids=("com.ss.android.ugc.trill:id/sx0",),
        class_names=("android.widget.GridView",),
        require_clickable=False,
    ),
    TikTokElementSelector(
        key="interests_title",
        resource_ids=("com.ss.android.ugc.trill:id/iz1",),
        normalized_text=("Choose your interests",),
        class_names=("android.widget.TextView",),
        require_clickable=False,
    ),
    TikTokElementSelector(
        key="interests_subtitle",
        resource_ids=("com.ss.android.ugc.trill:id/tk2",),
        normalized_text=("Get better video recommendations",),
        class_names=("android.widget.TextView",),
        require_clickable=False,
    ),
    TikTokElementSelector(
        key="interest_tile",
        resource_ids=("com.ss.android.ugc.trill:id/kat",),
        class_names=("android.view.ViewGroup",),
        structure=StructuralConstraint(
            ancestor_class_names=("android.widget.GridView",),
            descendant_class_names=("android.widget.TextView",),
        ),
        require_clickable=True,
    ),
    TikTokElementSelector(
        key="interests_bottom_actions",
        resource_ids=("com.ss.android.ugc.trill:id/bzw",),
        class_names=("android.view.ViewGroup",),
        require_clickable=False,
    ),
    TikTokElementSelector(
        key="interests_skip_control",
        resource_ids=("com.ss.android.ugc.trill:id/chn",),
        normalized_text=("Skip",),
        class_names=("android.widget.Button",),
        structure=StructuralConstraint(
            ancestor_class_names=("android.view.ViewGroup",),
        ),
        require_clickable=True,
    ),
    TikTokElementSelector(
        key="interests_next_control",
        resource_ids=("com.ss.android.ugc.trill:id/ceq",),
        normalized_text=("Next (0)",),
        class_names=("android.widget.Button",),
        require_enabled=False,
        require_clickable=True,
    ),
)

TRILL_44_4_3_INTERESTS_V13 = replace(
    TRILL_44_4_3_TERMS_V12,
    resource_key="trill-44.4.3-interests-v13",
    selectors=TRILL_44_4_3_TERMS_V12.selectors + _ONBOARDING_INTEREST_SELECTORS,
    screens=TRILL_44_4_3_TERMS_V12.screens + (
        ScreenDefinition(
            key="ONBOARDING_INTERESTS",
            required_selectors=(
                "interests_scene_root", "interests_content",
                "interests_grid", "interests_title",
                "interests_bottom_actions", "interests_skip_control",
            ),
            reinforcing_selectors=(
                "interests_subtitle", "interest_tile", "interests_next_control",
            ),
            forbidden_selectors=("terms_content", "terms_title"),
            minimum_score=12,
        ),
    ),
)


# Action-authorized generation for the already observed unique Skip target.
# Interest tiles and the disabled Next control remain non-actionable.
TRILL_44_4_3_INTERESTS_ACTION_V14 = replace(
    TRILL_44_4_3_INTERESTS_V13,
    resource_key="trill-44.4.3-interests-action-v14",
    selectors=tuple(
        replace(selector, actionable=True)
        if selector.key == "interests_skip_control"
        else selector
        for selector in TRILL_44_4_3_INTERESTS_V13.selectors
    ),
)


# Runtime 18 HOME-to-Profile action authorization. HOME classification and all
# other action permissions remain unchanged; only the exact bottom Profile tab
# may be dispatched by the typed one-attempt action.
TRILL_44_4_3_PROFILE_ACTION_V15 = replace(
    TRILL_44_4_3_INTERESTS_ACTION_V14,
    resource_key="trill-44.4.3-profile-action-v15",
    selectors=tuple(
        replace(selector, actionable=True)
        if selector.key == "profile_tab"
        else selector
        for selector in TRILL_44_4_3_INTERESTS_ACTION_V14.selectors
    ),
)


# Runtime 17 logged-in Profile calibration. Account text and metrics are not
# classification requirements; only stable observed containers and semantic
# controls distinguish Profile from HOME's otherwise shared bottom navigation.
_PROFILE_SELECTORS = (
    TikTokElementSelector(
        key="profile_scene_root",
        resource_ids=("com.ss.android.ugc.trill:id/r5r",),
        class_names=("android.widget.RelativeLayout",),
        require_clickable=False,
    ),
    TikTokElementSelector(
        key="profile_content",
        resource_ids=("com.ss.android.ugc.trill:id/t4f",),
        class_names=("android.widget.LinearLayout",),
        require_clickable=False,
    ),
    TikTokElementSelector(
        key="profile_header",
        resource_ids=("com.ss.android.ugc.trill:id/o6f",),
        class_names=("android.view.ViewGroup",),
        require_clickable=False,
    ),
    TikTokElementSelector(
        key="profile_menu",
        content_descriptions=("Profile menu",),
        class_names=("android.widget.Button",),
        require_clickable=True,
    ),
    TikTokElementSelector(
        key="profile_display_name",
        resource_ids=("com.ss.android.ugc.trill:id/r5d",),
        class_names=("android.widget.Button",),
        require_clickable=True,
    ),
    TikTokElementSelector(
        key="profile_handle",
        resource_ids=("com.ss.android.ugc.trill:id/r7b",),
        class_names=("android.widget.Button",),
        require_clickable=True,
    ),
    TikTokElementSelector(
        key="profile_media_tabs",
        resource_ids=("com.ss.android.ugc.trill:id/wpc",),
        class_names=("android.widget.HorizontalScrollView",),
        require_clickable=False,
    ),
    TikTokElementSelector(
        key="profile_add_person_signal",
        content_descriptions=("Add person",),
        class_names=("android.widget.ImageView",),
        require_clickable=False,
    ),
)

TRILL_44_4_3_PROFILE_V16 = replace(
    TRILL_44_4_3_PROFILE_ACTION_V15,
    resource_key="trill-44.4.3-profile-v16",
    selectors=TRILL_44_4_3_PROFILE_ACTION_V15.selectors + _PROFILE_SELECTORS,
    screens=tuple(
        replace(
            screen,
            forbidden_selectors=screen.forbidden_selectors + ("profile_scene_root",),
        )
        if screen.key == "HOME"
        else screen
        for screen in TRILL_44_4_3_PROFILE_ACTION_V15.screens
    ) + (
        ScreenDefinition(
            key="PROFILE",
            required_selectors=(
                "bottom_navigation", "profile_scene_root", "profile_content",
                "profile_header", "profile_menu",
            ),
            reinforcing_selectors=(
                "profile_display_name", "profile_handle", "profile_media_tabs",
                "profile_add_person_signal",
            ),
            minimum_score=10,
        ),
    ),
)


# Runtime 18 logged-out signup destination. The screen offers phone entry,
# Continue with Email, and Log in; no provider or data-entry action is
# authorized. Values below are observed structure, not guessed selectors.
_SIGNUP_METHOD_SELECTORS = (
    TikTokElementSelector(
        key="signup_scene_root",
        resource_ids=("com.ss.android.ugc.trill:id/ss8",),
        class_names=("android.widget.LinearLayout",),
        require_clickable=False,
    ),
    TikTokElementSelector(
        key="signup_content",
        resource_ids=("com.ss.android.ugc.trill:id/uee",),
        class_names=("android.widget.FrameLayout",),
        require_clickable=False,
    ),
    TikTokElementSelector(
        key="signup_phone_container",
        resource_ids=("com.ss.android.ugc.trill:id/pgc",),
        class_names=("android.widget.FrameLayout",),
        require_clickable=False,
    ),
    TikTokElementSelector(
        key="signup_title",
        normalized_text=("Sign up for TikTok",),
        class_names=("android.widget.TextView",),
        require_clickable=False,
    ),
    TikTokElementSelector(
        key="signup_phone_input",
        normalized_text=("Phone number",),
        class_names=("android.widget.EditText",),
        require_clickable=True,
    ),
    TikTokElementSelector(
        key="signup_email_method",
        content_descriptions=("Continue with Email",),
        class_names=("android.view.View",),
        require_clickable=False,
    ),
    TikTokElementSelector(
        key="signup_continue",
        normalized_text=("Continue",),
        class_names=("android.widget.TextView",),
        require_clickable=False,
    ),
    TikTokElementSelector(
        key="signup_login_entry",
        normalized_text=("Already have an account? Log in",),
        class_names=("android.widget.Button",),
        require_clickable=True,
    ),
    TikTokElementSelector(
        key="signup_close",
        resource_ids=("com.ss.android.ugc.trill:id/xc7",),
        content_descriptions=("Close",),
        class_names=("android.widget.ImageView",),
        require_clickable=True,
    ),
)

TRILL_44_4_3_SIGNUP_METHOD_V17 = replace(
    TRILL_44_4_3_PROFILE_V16,
    resource_key="trill-44.4.3-signup-method-v17",
    selectors=TRILL_44_4_3_PROFILE_V16.selectors + _SIGNUP_METHOD_SELECTORS,
    screens=TRILL_44_4_3_PROFILE_V16.screens + (
        ScreenDefinition(
            key="SIGNUP_METHOD",
            required_selectors=(
                "signup_scene_root", "signup_content",
                "signup_phone_container", "signup_title",
                "signup_phone_input", "signup_email_method",
            ),
            reinforcing_selectors=(
                "signup_continue", "signup_login_entry", "signup_close",
            ),
            forbidden_selectors=("bottom_navigation", "profile_scene_root"),
            minimum_score=12,
        ),
    ),
)


# Runtime 18's exact semantic email-method child is non-clickable but occupies
# the upper area of its unique clickable parent. Authorizing only this observed
# child keeps phone, Continue, Log in, Close, and Report non-actionable.
TRILL_44_4_3_EMAIL_ACTION_V18 = replace(
    TRILL_44_4_3_SIGNUP_METHOD_V17,
    resource_key="trill-44.4.3-email-action-v18",
    selectors=tuple(
        replace(selector, actionable=True)
        if selector.key == "signup_email_method" else selector
        for selector in TRILL_44_4_3_SIGNUP_METHOD_V17.selectors
    ),
)


_EMAIL_ENTRY_SELECTORS = (
    TikTokElementSelector(
        key="email_entry_root",
        resource_ids=("com.ss.android.ugc.trill:id/hyp",),
        class_names=("android.widget.FrameLayout",),
        require_clickable=False,
    ),
    TikTokElementSelector(
        key="email_entry_scene",
        resource_ids=("com.ss.android.ugc.trill:id/mvq",),
        class_names=("android.widget.LinearLayout",),
        require_clickable=False,
    ),
    TikTokElementSelector(
        key="email_entry_header",
        resource_ids=("com.ss.android.ugc.trill:id/bii",),
        class_names=("android.widget.FrameLayout",),
        require_clickable=False,
    ),
    TikTokElementSelector(
        key="email_entry_title",
        resource_ids=("com.ss.android.ugc.trill:id/ehn",),
        normalized_text=("Enter email address",),
        class_names=("android.widget.TextView",),
        require_clickable=False,
    ),
    TikTokElementSelector(
        key="email_entry_form",
        resource_ids=("com.ss.android.ugc.trill:id/efn",),
        class_names=("android.widget.LinearLayout",),
        require_clickable=False,
    ),
    TikTokElementSelector(
        key="email_input",
        content_descriptions=("Email address",),
        class_names=("android.widget.EditText",),
        require_clickable=True,
    ),
    TikTokElementSelector(
        key="email_save_login_row",
        resource_ids=("com.ss.android.ugc.trill:id/gfk",),
        class_names=("android.view.ViewGroup",),
        require_clickable=False,
    ),
    TikTokElementSelector(
        key="email_continue",
        resource_ids=("com.ss.android.ugc.trill:id/evj",),
        normalized_text=("Continue",),
        class_names=("android.widget.Button",),
        require_enabled=False,
        require_clickable=True,
    ),
    TikTokElementSelector(
        key="email_domain_suggestions",
        resource_ids=("com.ss.android.ugc.trill:id/ld_",),
        class_names=("androidx.recyclerview.widget.RecyclerView",),
        require_clickable=False,
    ),
    TikTokElementSelector(
        key="email_back",
        content_descriptions=("Back to previous screen",),
        class_names=("android.widget.Button",),
        require_clickable=True,
    ),
)

TRILL_44_4_3_EMAIL_ENTRY_V19 = replace(
    TRILL_44_4_3_EMAIL_ACTION_V18,
    resource_key="trill-44.4.3-email-entry-v19",
    selectors=TRILL_44_4_3_EMAIL_ACTION_V18.selectors + _EMAIL_ENTRY_SELECTORS,
    screens=TRILL_44_4_3_EMAIL_ACTION_V18.screens + (
        ScreenDefinition(
            key="EMAIL_ENTRY",
            required_selectors=(
                "email_entry_root", "email_entry_scene", "email_entry_header",
                "email_entry_title", "email_entry_form", "email_input",
            ),
            reinforcing_selectors=(
                "email_save_login_row", "email_continue",
                "email_domain_suggestions", "email_back",
            ),
            forbidden_selectors=("signup_scene_root", "bottom_navigation"),
            minimum_score=12,
        ),
    ),
)


# The first live v19 detect proved UIAutomator reports ``Email address`` in
# text, not content-desc. Preserve v19 and correct only that observed field in
# a new immutable generation.
TRILL_44_4_3_EMAIL_ENTRY_V20 = replace(
    TRILL_44_4_3_EMAIL_ENTRY_V19,
    resource_key="trill-44.4.3-email-entry-v20",
    selectors=tuple(
        replace(
            selector,
            content_descriptions=(),
            normalized_text=("Email address",),
        )
        if selector.key == "email_input" else selector
        for selector in TRILL_44_4_3_EMAIL_ENTRY_V19.selectors
    ),
)


# Filled email text is dynamic, so the mutation profile resolves the single
# observed EditText by its calibrated class/ancestor structure rather than by
# the empty-field label. Uniqueness is still mandatory immediately before use.
TRILL_44_4_3_EMAIL_INPUT_V21 = replace(
    TRILL_44_4_3_EMAIL_ENTRY_V20,
    resource_key="trill-44.4.3-email-input-v21",
    selectors=tuple(
        replace(
            selector,
            normalized_text=(),
            structure=StructuralConstraint(
                ancestor_class_names=(
                    "android.widget.FrameLayout",
                    "android.widget.LinearLayout",
                    "android.view.ViewGroup",
                ),
            ),
            require_focusable=True,
            actionable=True,
        )
        if selector.key == "email_input" else selector
        for selector in TRILL_44_4_3_EMAIL_ENTRY_V20.selectors
    ),
)


TRILL_44_4_3_EMAIL_CONTINUE_V22 = replace(
    TRILL_44_4_3_EMAIL_INPUT_V21,
    resource_key="trill-44.4.3-email-continue-v22",
    selectors=tuple(
        replace(selector, actionable=True)
        if selector.key == "email_continue" else selector
        for selector in TRILL_44_4_3_EMAIL_INPUT_V21.selectors
    ),
)


# Runtime 18 post-Continue calibration. TikTok requires an operator to use the
# emailed link/code. Dynamic destination text may contain account PII, so the
# classifier uses stable resource IDs/classes and only the fixed title/action.
_EMAIL_VERIFICATION_SELECTORS = (
    TikTokElementSelector(
        key="email_verification_content",
        resource_ids=("com.ss.android.ugc.trill:id/bik",),
        class_names=("android.view.ViewGroup",),
        require_clickable=False,
    ),
    TikTokElementSelector(
        key="email_verification_title",
        resource_ids=("com.ss.android.ugc.trill:id/ehn",),
        normalized_text=("Check your email",),
        class_names=("android.widget.TextView",),
        require_clickable=False,
    ),
    TikTokElementSelector(
        key="email_verification_message",
        resource_ids=("com.ss.android.ugc.trill:id/eft",),
        class_names=("android.widget.TextView",),
        require_clickable=False,
    ),
    TikTokElementSelector(
        key="email_verification_code_container",
        resource_ids=("com.ss.android.ugc.trill:id/k59",),
        class_names=("android.view.ViewGroup",),
        require_clickable=False,
    ),
    TikTokElementSelector(
        key="email_verification_resend",
        resource_ids=("com.ss.android.ugc.trill:id/k58",),
        normalized_text=("Resend code",),
        class_names=("android.widget.Button",),
        require_clickable=True,
    ),
)

TRILL_44_4_3_EMAIL_VERIFICATION_V23 = replace(
    TRILL_44_4_3_EMAIL_CONTINUE_V22,
    resource_key="trill-44.4.3-email-verification-v23",
    selectors=(
        TRILL_44_4_3_EMAIL_CONTINUE_V22.selectors
        + _EMAIL_VERIFICATION_SELECTORS
    ),
    screens=TRILL_44_4_3_EMAIL_CONTINUE_V22.screens + (
        ScreenDefinition(
            key="VERIFICATION_REQUIRED",
            required_selectors=(
                "email_entry_root", "email_entry_scene", "email_entry_header",
                "email_verification_content", "email_verification_title",
                "email_verification_message", "email_verification_code_container",
            ),
            reinforcing_selectors=(
                "email_entry_form", "email_verification_resend", "email_back",
            ),
            forbidden_selectors=("signup_scene_root", "bottom_navigation"),
            minimum_score=14,
        ),
    ),
)


class TikTokUiProfileRegistry:
    def __init__(self, definitions: tuple[TikTokUiProfileDefinition, ...] | None = None) -> None:
        values = definitions or (
            TRILL_44_4_3_TESTING,
            TRILL_44_4_3_HOME_V2,
            TRILL_44_4_3_CAMERA_V3,
            TRILL_44_4_3_MEDIA_PICKER_V4,
            TRILL_44_4_3_EDITOR_V5,
            TRILL_44_4_3_EDITOR_ACTION_V6,
            TRILL_44_4_3_READY_V7,
            TRILL_44_4_3_CAPTION_ACTION_V8,
            TRILL_44_4_3_PRIVACY_ENTRY_V9,
            TRILL_44_4_3_PRIVACY_MODAL_V10,
            TRILL_44_4_3_PRIVACY_AUTOCLOSE_V11,
            TRILL_44_4_3_TERMS_V12,
            TRILL_44_4_3_INTERESTS_V13,
            TRILL_44_4_3_INTERESTS_ACTION_V14,
            TRILL_44_4_3_PROFILE_ACTION_V15,
            TRILL_44_4_3_PROFILE_V16,
            TRILL_44_4_3_SIGNUP_METHOD_V17,
            TRILL_44_4_3_EMAIL_ACTION_V18,
            TRILL_44_4_3_EMAIL_ENTRY_V19,
            TRILL_44_4_3_EMAIL_ENTRY_V20,
            TRILL_44_4_3_EMAIL_INPUT_V21,
            TRILL_44_4_3_EMAIL_CONTINUE_V22,
            TRILL_44_4_3_EMAIL_VERIFICATION_V23,
        )
        self._definitions = {item.resource_key: item for item in values}

    def definition_for(self, profile: TikTokUiProfile) -> TikTokUiProfileDefinition:
        definition = self._definitions.get(profile.resource_key)
        if definition is None or definition.fingerprint != profile.profile_fingerprint:
            raise tiktok_error("TIKTOK_UI_PROFILE_MISMATCH")
        return definition

    def select(
        self, session: Session, *, package_name: str, version_code: int | None
    ) -> tuple[TikTokUiProfile, TikTokUiProfileDefinition]:
        rows = session.scalars(
            select(TikTokUiProfile)
            .where(TikTokUiProfile.package_name == package_name, TikTokUiProfile.status != "retired")
            .order_by(TikTokUiProfile.version.desc(), TikTokUiProfile.id.desc())
        ).all()
        if not rows:
            raise tiktok_error("TIKTOK_UI_PROFILE_NOT_FOUND")
        for row in rows:
            if version_code is None:
                continue
            if row.min_version_code is not None and version_code < row.min_version_code:
                continue
            if row.max_version_code is not None and version_code > row.max_version_code:
                continue
            return row, self.definition_for(row)
        raise tiktok_error("TIKTOK_UI_PROFILE_MISMATCH")

    def pinned(self, session: Session, profile_id: int) -> tuple[TikTokUiProfile, TikTokUiProfileDefinition]:
        row = session.get(TikTokUiProfile, profile_id)
        if row is None or row.status == "retired":
            raise tiktok_error("TIKTOK_UI_PROFILE_MISMATCH")
        return row, self.definition_for(row)

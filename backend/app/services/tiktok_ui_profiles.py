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

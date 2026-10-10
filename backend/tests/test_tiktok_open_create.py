"""Typed, profile-owned TikTok open-create action tests."""

from dataclasses import replace

import pytest

from app.services.adb_executor import AdbForegroundApp, AdbMediaRecord
from app.services.android_ui_hierarchy import UiHierarchyParser
from app.services.tiktok_action_service import TikTokActionService
from app.services.tiktok_errors import TikTokActionError, tiktok_error
from app.services.tiktok_overlay_resolver import TikTokOverlay, TikTokOverlayResolver
from app.services.tiktok_media_identity import MediaIdentityResolver
from app.services.tiktok_screen_resolver import TikTokScreen, TikTokScreenResolver
from app.services.tiktok_ui_profiles import (
    TRILL_44_4_3_CAMERA_V3,
    TRILL_44_4_3_EDITOR_V5,
    TRILL_44_4_3_EDITOR_ACTION_V6,
    TRILL_44_4_3_READY_V7,
    TRILL_44_4_3_CAPTION_ACTION_V8,
    TRILL_44_4_3_PRIVACY_ENTRY_V9,
    TRILL_44_4_3_PRIVACY_MODAL_V10,
    TRILL_44_4_3_PRIVACY_AUTOCLOSE_V11,
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
    TRILL_44_4_3_MEDIA_PICKER_V4,
)


def node(
    *, resource: str = "", desc: str = "", klass: str = "android.view.View",
    bounds: str = "[0,0][100,100]", clickable: str = "true", children: str = "",
    package: str = "com.ss.android.ugc.trill", text: str = "",
    enabled: str = "true", focusable: str = "true", focused: str = "false",
) -> str:
    return (
        f'<node resource-id="{resource}" text="{text}" content-desc="{desc}" class="{klass}" '
        f'package="{package}" bounds="{bounds}" enabled="{enabled}" '
        f'clickable="{clickable}" focusable="{focusable}" focused="{focused}" selected="false" '
        f'checked="false" password="false">{children}</node>'
    )


def parsed(*nodes: str):
    return UiHierarchyParser().parse(
        f'<?xml version="1.0"?><hierarchy>{"".join(nodes)}</hierarchy>'
    )


def home_hierarchy(
    *, duplicate_create: bool = False, duplicate_profile: bool = False,
    variant: int = 0,
):
    create = node(
        resource="com.ss.android.ugc.trill:id/n0x", desc="Create",
        klass="android.widget.Button", bounds="[288,1100][432,1184]",
    )
    return parsed(node(
        resource="com.ss.android.ugc.trill:id/n18",
        klass="android.widget.LinearLayout", bounds="[0,1100][720,1184]",
        clickable="false",
        children="".join((
            node(resource="com.ss.android.ugc.trill:id/n10", desc="Home", klass="android.widget.FrameLayout", bounds="[0,1100][144,1184]"),
            create,
            create if duplicate_create else "",
            node(resource="com.ss.android.ugc.trill:id/n11", desc="Inbox", klass="android.widget.FrameLayout", bounds="[432,1100][576,1184]"),
            node(resource="com.ss.android.ugc.trill:id/n12", desc="Profile", klass="android.widget.FrameLayout", bounds="[576,1100][720,1184]"),
            node(resource="com.ss.android.ugc.trill:id/n12", desc="Profile", klass="android.widget.FrameLayout", bounds="[576,1100][720,1184]") if duplicate_profile else "",
            node(resource=f"home-dynamic-{variant}", clickable="false") if variant else "",
        )),
    ))


TEST_PROFILE = TRILL_44_4_3_EDITOR_V5


def media_hierarchy(*, empty: bool = True, include_grid: bool = True):
    """Sanitized Runtime 17 picker structure, with or without grid content."""
    package = "com.ss.android.ugc.trill"
    tabs = node(
        resource=f"{package}:id/n_y",
        klass="android.widget.HorizontalScrollView", clickable="false",
        bounds="[0,144][720,234]",
        children=node(
            klass="android.widget.LinearLayout", clickable="false",
            bounds="[0,144][720,234]",
            children="".join((
                node(desc="All", klass="android.widget.FrameLayout", clickable="false", bounds="[32,144][156,234]"),
                node(desc="Videos", klass="android.widget.FrameLayout", bounds="[156,144][315,234]"),
                node(desc="Photos", klass="android.widget.FrameLayout", bounds="[315,144][478,234]"),
                node(desc="Live Photos", klass="android.widget.FrameLayout", bounds="[478,144][688,234]"),
            )),
        ),
    )
    grid_children = "" if empty else node(
        klass="android.widget.FrameLayout", bounds="[4,238][239,476]",
        children="".join((
            node(
                resource=f"{package}:id/n_z", klass="android.widget.ImageView",
                clickable="false", bounds="[4,238][239,476]",
            ),
            node(
                klass="android.widget.FrameLayout", clickable="false",
                bounds="[115,410][239,476]",
                children="".join((
                    node(resource=f"{package}:id/fv7", clickable="false", bounds="[115,410][239,476]"),
                    node(resource=f"{package}:id/fvf", text="00:02", klass="android.widget.TextView", clickable="false", bounds="[140,430][239,476]"),
                )),
            ),
        )),
    )
    grid = node(
        resource=f"{package}:id/ik9", klass="android.widget.GridView",
        clickable="false", bounds="[0,234][720,1032]",
        children=grid_children,
    ) if include_grid else ""
    return parsed(node(
        resource=f"{package}:id/f9y", klass="android.widget.LinearLayout",
        clickable="false", bounds="[0,0][720,1184]",
        children="".join((
            node(
                resource=f"{package}:id/alh", klass="android.widget.RelativeLayout",
                clickable="false", bounds="[0,48][720,144]",
                children="".join((
                    node(resource=f"{package}:id/bc9", desc="Close", klass="android.widget.ImageView", bounds="[32,72][80,120]"),
                    node(
                        resource=f"{package}:id/d98", klass="android.widget.LinearLayout",
                        bounds="[250,60][470,132]",
                        children=node(text="Recents", klass="android.widget.TextView", clickable="false", bounds="[282,77][402,115]"),
                    ),
                    node(resource=f"{package}:id/wr6", klass="android.widget.LinearLayout", bounds="[581,60][704,132]"),
                )),
            ),
            tabs,
            node(
                resource=f"{package}:id/viewpager_choose_media",
                klass="androidx.viewpager.widget.ViewPager", clickable="false",
                bounds="[0,234][720,1032]", children=grid + (
                    node(
                        resource=f"{package}:id/odo",
                        text="No photos or videos available",
                        klass="android.widget.TextView", clickable="false",
                        bounds="[156,614][563,652]",
                    ) if empty else ""
                ),
            ),
            node(
                resource=f"{package}:id/nua", klass="android.widget.RelativeLayout",
                bounds="[24,1032][285,1184]",
                children=node(text="Select multiple", klass="android.widget.TextView", clickable="false", bounds="[84,1091][285,1127]"),
            ),
        )),
    ))


def camera_hierarchy(*, duplicate_gallery: bool = False):
    gallery = node(
        resource="com.ss.android.ugc.trill:id/zne",
        klass="android.widget.FrameLayout", bounds="[0,1032][136,1168]",
    )
    return parsed(node(
        resource="com.ss.android.ugc.trill:id/video_record_new_scene_root",
        klass="android.widget.FrameLayout", bounds="[0,0][720,1184]",
        clickable="false",
        children="".join((
            node(
                resource="com.ss.android.ugc.trill:id/rts",
                klass="android.widget.Button", bounds="[250,862][470,1082]",
            ),
            node(
                resource="com.ss.android.ugc.trill:id/ddk",
                klass="android.widget.Button", bounds="[225,76][494,164]",
            ),
            node(
                resource="com.ss.android.ugc.trill:id/uyf",
                klass="android.widget.FrameLayout", bounds="[0,768][720,876]",
                clickable="false",
            ),
            node(
                resource="camera-parent", klass="android.widget.RelativeLayout",
                clickable="false", children=gallery + (gallery if duplicate_gallery else ""),
            ),
        )),
    ))


def interests_hierarchy(*, duplicate_skip: bool = False, variant: int = 0):
    skip = node(
        resource="com.ss.android.ugc.trill:id/chn", text="Skip",
        klass="android.widget.Button", bounds="[64,1072][352,1160]",
    )
    tile = node(
        resource="com.ss.android.ugc.trill:id/kat",
        klass="android.view.ViewGroup", bounds="[64,448][352,655]",
        children=node(
            resource="com.ss.android.ugc.trill:id/kb2",
            text="Entertainment Culture", klass="android.widget.TextView",
            clickable="false", bounds="[80,563][336,639]",
        ),
    )
    return parsed(node(
        resource="com.ss.android.ugc.trill:id/ss8",
        klass="android.view.ViewGroup", clickable="false",
        bounds="[0,48][720,1184]",
        children="".join((
            node(
                resource="com.ss.android.ugc.trill:id/k2m",
                klass="android.view.ViewGroup", clickable="false",
                bounds="[0,48][720,1048]",
                children=node(
                    resource="com.ss.android.ugc.trill:id/sx0",
                    klass="android.widget.GridView", clickable="false",
                    bounds="[56,48][664,1048]",
                    children="".join((
                        node(
                            resource="com.ss.android.ugc.trill:id/iz1",
                            text="Choose your interests",
                            klass="android.widget.TextView", clickable="false",
                            bounds="[64,188][656,332]",
                        ),
                        node(
                            resource="com.ss.android.ugc.trill:id/tk2",
                            text="Get better video recommendations",
                            klass="android.widget.TextView", clickable="false",
                            bounds="[64,348][656,384]",
                        ),
                        tile,
                        node(
                            resource=f"dynamic-{variant}", clickable="false",
                            bounds="[0,0][0,0]",
                        ) if variant else "",
                    )),
                ),
            ),
            node(
                resource="com.ss.android.ugc.trill:id/bzw",
                klass="android.view.ViewGroup", clickable="false",
                bounds="[64,1048][656,1184]",
                children=skip + (skip if duplicate_skip else ""),
            ),
        )),
    ))


def profile_hierarchy(*, include_menu: bool = True, account_variant: int = 0):
    bottom = node(
        resource="com.ss.android.ugc.trill:id/n18",
        klass="android.widget.LinearLayout", clickable="false",
        bounds="[0,1100][720,1184]",
        children="".join((
            node(resource="com.ss.android.ugc.trill:id/n10", desc="Home", klass="android.widget.FrameLayout", bounds="[0,1100][144,1184]"),
            node(resource="com.ss.android.ugc.trill:id/n0x", desc="Create", klass="android.widget.Button", bounds="[288,1100][432,1184]"),
            node(resource="com.ss.android.ugc.trill:id/n11", desc="Inbox", klass="android.widget.FrameLayout", bounds="[432,1100][576,1184]"),
            node(resource="com.ss.android.ugc.trill:id/n12", desc="Profile", klass="android.widget.FrameLayout", bounds="[576,1100][720,1184]"),
        )),
    )
    profile = node(
        resource="com.ss.android.ugc.trill:id/r5r",
        klass="android.widget.RelativeLayout", clickable="false",
        children="".join((
            node(
                resource="com.ss.android.ugc.trill:id/t4f",
                klass="android.widget.LinearLayout", clickable="false",
                children="".join((
                    node(resource="com.ss.android.ugc.trill:id/r5d", text=f"Display {account_variant}", klass="android.widget.Button"),
                    node(resource="com.ss.android.ugc.trill:id/r7b", text=f"@handle{account_variant}", klass="android.widget.Button"),
                    node(resource="com.ss.android.ugc.trill:id/wpc", klass="android.widget.HorizontalScrollView", clickable="false"),
                )),
            ),
            node(
                resource="com.ss.android.ugc.trill:id/o6f",
                klass="android.view.ViewGroup", clickable="false",
                children="".join((
                    node(desc="Add person", klass="android.widget.ImageView", clickable="false"),
                    node(desc="Profile menu", klass="android.widget.Button") if include_menu else "",
                )),
            ),
            bottom,
        )),
    )
    return parsed(profile)


def signup_method_hierarchy(
    *, include_email: bool = True, duplicate_email: bool = False,
    variant: int = 0,
):
    """Sanitized Runtime 18 logged-out destination; no private input values."""
    package = "com.ss.android.ugc.trill"
    email = node(
        desc="Continue with Email", klass="android.view.View",
        clickable="false", bounds="[56,830][664,868]",
    ) if include_email else ""
    return parsed(node(
        resource=f"{package}:id/ss8", klass="android.widget.LinearLayout",
        clickable="false", bounds="[0,108][720,1184]",
        children="".join((
            node(
                resource=f"{package}:id/xc7", desc="Close",
                klass="android.widget.ImageView", bounds="[616,112][712,208]",
            ),
            node(
                resource=f"{package}:id/uee", klass="android.widget.FrameLayout",
                clickable="false", bounds="[0,208][720,1064]",
                children="".join((
                    node(
                        text="Sign up for TikTok", klass="android.widget.TextView",
                        clickable="false", bounds="[64,256][656,316]",
                    ),
                    node(
                        resource=f"{package}:id/pgc",
                        klass="android.widget.FrameLayout", clickable="false",
                        bounds="[64,392][656,488]",
                        children=node(
                            text="Phone number", klass="android.widget.EditText",
                            bounds="[168,392][656,488]",
                        ),
                    ),
                    node(
                        klass="android.view.View", bounds="[82,596][638,684]",
                        children=node(
                            text="Continue", klass="android.widget.TextView",
                            clickable="false", bounds="[310,620][410,660]",
                        ),
                    ),
                    node(
                        klass="android.view.View", bounds="[56,830][664,916]",
                        children=email + (email if duplicate_email else ""),
                    ),
                    node(
                        resource=f"signup-dynamic-{variant}", clickable="false",
                        bounds="[0,0][0,0]",
                    ) if variant else "",
                )),
            ),
            node(
                text="Already have an account? Log in",
                klass="android.widget.Button", bounds="[176,1080][544,1160]",
            ),
        )),
    ))


def email_entry_hierarchy(
    *, include_input: bool = True, duplicate_input: bool = False,
    include_continue: bool = True, duplicate_continue: bool = False,
    field_text: str = "Email address", continue_enabled: bool = False,
    variant: int = 0,
):
    package = "com.ss.android.ugc.trill"
    return parsed(node(
        resource=f"{package}:id/hyp", klass="android.widget.FrameLayout",
        clickable="false", bounds="[0,0][720,1184]",
        children=node(
            resource=f"{package}:id/mvq", klass="android.widget.LinearLayout",
            clickable="false", bounds="[0,48][720,658]",
            children="".join((
                node(
                    resource=f"{package}:id/bii",
                    klass="android.widget.FrameLayout", clickable="false",
                    bounds="[0,48][720,152]",
                    children=node(
                        desc="Back to previous screen",
                        klass="android.widget.Button", bounds="[16,56][96,144]",
                    ),
                ),
                node(
                    resource=f"{package}:id/ehn", text="Enter email address",
                    klass="android.widget.TextView", clickable="false",
                    bounds="[64,224][656,300]",
                ),
                node(
                    resource=f"{package}:id/efn",
                    klass="android.widget.LinearLayout", clickable="false",
                    bounds="[0,300][720,450]",
                    children=node(
                        resource=f"{package}:id/gfg",
                        klass="android.view.ViewGroup", clickable="false",
                        bounds="[0,300][720,450]",
                        children=((node(
                            text=field_text, klass="android.widget.EditText",
                            bounds="[92,376][628,416]", focused="true",
                        ) * (2 if duplicate_input else 1)) if include_input else "") + node(
                            resource=f"{package}:id/gfk",
                            klass="android.view.ViewGroup", clickable="false",
                            bounds="[64,370][656,430]",
                        ),
                    ),
                ),
                (node(
                    resource=f"{package}:id/evj", text="Continue",
                    klass="android.widget.Button", bounds="[64,450][656,554]",
                    enabled="true" if continue_enabled else "false",
                ) * (2 if duplicate_continue else 1)) if include_continue else "",
                node(
                    resource=f"{package}:id/ld_",
                    klass="androidx.recyclerview.widget.RecyclerView",
                    clickable="false", bounds="[0,578][720,658]",
                ),
                node(
                    resource=f"email-dynamic-{variant}", clickable="false",
                    bounds="[0,0][0,0]",
                ) if variant else "",
            )),
        ),
    ))


def email_verification_hierarchy(*, include_resend: bool = True, variant: int = 0):
    package = "com.ss.android.ugc.trill"
    return parsed(node(
        resource=f"{package}:id/hyp", klass="android.widget.FrameLayout",
        clickable="false", bounds="[0,0][720,1184]",
        children=node(
            resource=f"{package}:id/mvq", klass="android.widget.LinearLayout",
            clickable="false", bounds="[0,48][720,658]",
            children="".join((
                node(
                    resource=f"{package}:id/bii",
                    klass="android.widget.FrameLayout", clickable="false",
                    bounds="[0,48][720,152]",
                    children=node(
                        desc="Back to previous screen",
                        klass="android.widget.Button", bounds="[16,56][96,144]",
                    ),
                ),
                node(
                    resource=f"{package}:id/bik",
                    klass="android.view.ViewGroup", clickable="false",
                    bounds="[0,152][720,388]", children="".join((
                        node(
                            resource=f"{package}:id/ehn", text="Check your email",
                            klass="android.widget.TextView", clickable="false",
                            bounds="[64,224][656,300]",
                        ),
                        node(
                            resource=f"{package}:id/eft",
                            text="Use the link or code sent to redacted destination",
                            klass="android.widget.TextView", clickable="false",
                            bounds="[64,316][656,388]",
                        ),
                    )),
                ),
                node(
                    resource=f"{package}:id/efn",
                    klass="android.widget.LinearLayout", clickable="false",
                    bounds="[0,388][720,658]", children=node(
                        resource=f"{package}:id/k59",
                        klass="android.view.ViewGroup", clickable="false",
                        bounds="[0,388][720,658]", children="".join((
                            node(
                                klass="android.widget.EditText",
                                bounds="[64,436][656,540]", focused="true",
                            ),
                            node(
                                resource=f"{package}:id/k58", text="Resend code",
                                klass="android.widget.Button",
                                bounds="[64,568][265,646]",
                            ) if include_resend else "",
                        )),
                    ),
                ),
                node(
                    resource=f"verification-dynamic-{variant}", clickable="false",
                    bounds="[0,0][0,0]",
                ) if variant else "",
            )),
        ),
    ))


def editor_hierarchy(
    *, dynamic_variant: int = 0, include_next: bool = True,
    duplicate_next: bool = False,
):
    package = "com.ss.android.ugc.trill"
    dynamic_preview = "".join(
        node(
            resource=f"{package}:id/dynamic_{index}",
            klass="android.widget.FrameLayout", clickable="false",
            bounds="[0,164][608,1076]",
        )
        for index in range(dynamic_variant)
    )
    next_action = (
        node(
            resource=f"{package}:id/oca",
            klass="android.widget.LinearLayout",
            bounds="[364,1080][696,1168]",
            children=node(
                resource=f"{package}:id/ocd", text="Next",
                klass="android.widget.TextView", clickable="false",
                bounds="[493,1104][566,1144]",
            ),
        )
        if include_next else ""
    )
    bottom = node(
        resource=f"{package}:id/bza", klass="android.widget.FrameLayout",
        clickable="false", bounds="[0,1076][720,1184]",
        children=node(
            resource=f"{package}:id/t2b", klass="android.widget.FrameLayout",
            clickable="false", bounds="[0,1076][720,1184]",
            children=node(
                resource=f"{package}:id/lil", klass="android.widget.LinearLayout",
                clickable="false", bounds="[0,1076][720,1168]",
                children=next_action + (next_action if duplicate_next else ""),
            ),
        ),
    )
    tools = node(
        resource=f"{package}:id/umn", klass="android.widget.LinearLayout",
        clickable="false", bounds="[608,306][720,826]",
        children=node(
            desc="Edit", klass="android.widget.Button",
            bounds="[608,306][720,410]",
        ),
    )
    main = node(
        resource=f"{package}:id/g9_", klass="android.widget.FrameLayout",
        clickable="false", bounds="[0,0][720,1184]",
        children="".join((
            node(
                resource=f"{package}:id/ddk",
                klass="android.widget.LinearLayout",
                bounds="[161,76][485,164]",
            ),
            dynamic_preview,
            bottom,
            tools,
        )),
    )
    return parsed(node(
        resource=f"{package}:id/sqd", klass="android.widget.FrameLayout",
        clickable="false", bounds="[0,0][720,1184]",
        children=node(
            resource=f"{package}:id/g9a", klass="android.widget.FrameLayout",
            clickable="false", bounds="[0,0][720,1184]", children=main,
        ),
    ))


def ready_to_publish_hierarchy(
    *, include_publish: bool = True, caption: str = "Add description...",
    duplicate_caption: bool = False, include_caption: bool = True,
    duplicate_privacy: bool = False, privacy: str = "everyone",
    include_drafts: bool = True, duplicate_publish: bool = False,
    duplicate_drafts: bool = False,
):
    """Sanitized Runtime 17 post-screen structure; no user suggestions."""
    package = "com.ss.android.ugc.trill"
    options = node(
        resource=f"{package}:id/rh6", klass="android.widget.RelativeLayout",
        clickable="false", bounds="[0,591][720,1040]",
        children="".join((
            node(
                resource=f"{package}:id/d7b",
                desc=("Everyone can view this post" if privacy == "everyone"
                      else "Only you can view this post"),
                klass="android.widget.Button", bounds="[0,792][720,898]",
            ) + (node(
                resource=f"{package}:id/d7b",
                desc=("Everyone can view this post" if privacy == "everyone"
                      else "Only you can view this post"),
                klass="android.widget.Button", bounds="[0,792][720,898]",
            ) if duplicate_privacy else ""),
            node(
                resource=f"{package}:id/d7b", desc="More options",
                klass="android.widget.Button", bounds="[0,898][720,1004]",
            ),
        )),
    )
    actions = node(
        resource=f"{package}:id/c07", klass="android.widget.RelativeLayout",
        clickable="false", bounds="[0,1040][720,1184]",
        children=node(
            resource=f"{package}:id/fpr", klass="android.widget.LinearLayout",
            clickable="false", bounds="[24,1064][696,1160]",
            children="".join((
                (node(
                    resource=f"{package}:id/fob", text="Drafts",
                    klass="android.widget.Button", bounds="[24,1064][352,1160]",
                ) if include_drafts else "") + (node(
                    resource=f"{package}:id/fob", text="Drafts",
                    klass="android.widget.Button", bounds="[24,1064][352,1160]",
                ) if include_drafts and duplicate_drafts else ""),
                (node(
                    resource=f"{package}:id/rhc", text="Post",
                    klass="android.widget.Button", bounds="[368,1064][696,1160]",
                ) if include_publish else "") + (node(
                    resource=f"{package}:id/rhc", text="Post",
                    klass="android.widget.Button", bounds="[368,1064][696,1160]",
                ) if include_publish and duplicate_publish else ""),
            )),
        ),
    )
    return parsed(node(
        resource=f"{package}:id/rhf", klass="android.widget.RelativeLayout",
        clickable="false", bounds="[0,0][720,1184]",
        children="".join((
            node(
                resource=f"{package}:id/bc5", klass="android.widget.Button",
                bounds="[12,48][100,136]",
            ),
            node(
                resource=f"{package}:id/rhg", klass="android.widget.ScrollView",
                clickable="false", bounds="[0,137][720,1040]",
                children="".join((
                    (node(
                        resource=f"{package}:id/gbc", text=caption,
                        klass="android.widget.EditText", bounds="[32,153][410,463]",
                    ) if include_caption else "")
                    + (node(
                        resource=f"{package}:id/gbc", text=caption,
                        klass="android.widget.EditText", bounds="[32,153][410,463]",
                    ) if duplicate_caption else ""),
                    options,
                )),
            ),
            actions,
        )),
    ))


def privacy_modal_hierarchy(
    *, checked: str = "everyone", duplicate_only_you: bool = False,
):
    package = "com.ss.android.ugc.trill"
    def choice(description: str, label: str, top: int, value: str) -> str:
        item = node(
            resource=f"{package}:id/d7b", desc=description,
            klass="android.view.ViewGroup", bounds=f"[16,{top}][704,{top + 104}]",
            children="".join((
                node(
                    resource=f"{package}:id/x37", text=label,
                    klass="android.widget.TextView", clickable="false",
                    bounds=f"[72,{top + 32}][300,{top + 72}]",
                ),
                node(
                    klass="android.widget.RadioButton", clickable="true",
                    bounds=f"[624,{top + 28}][672,{top + 76}]",
                ).replace('checked="false"', f'checked="{str(checked == value).lower()}"'),
            )),
        ).replace('checked="false"', f'checked="{str(checked == value).lower()}"', 1)
        return item
    only_you = choice("Only you", "Only you", 1036, "only_you")
    return parsed(node(
        resource=f"{package}:id/f9y", desc="Bottom sheet",
        klass="android.widget.FrameLayout", clickable="false",
        bounds="[0,560][720,1184]",
        children=node(
            resource=f"{package}:id/u76", klass="android.widget.RelativeLayout",
            clickable="false", bounds="[0,560][720,1184]",
            children="".join((
                node(
                    resource=f"{package}:id/o60", text="Privacy settings",
                    desc="Privacy settings", klass="android.widget.TextView",
                    clickable="false", bounds="[230,590][490,634]",
                ),
                node(
                    desc="Close", klass="android.widget.Button",
                    bounds="[624,568][704,656]",
                ),
                node(
                    resource=f"{package}:id/pek", text="Who can view this post",
                    klass="android.widget.TextView", clickable="false",
                    bounds="[16,716][400,756]",
                ),
                choice("Everyone", "Everyone", 772, "everyone"),
                choice(
                    "Friends, Followers you follow back · 0 friends**",
                    "Friends", 876, "friends",
                ),
                only_you + (only_you if duplicate_only_you else ""),
            )),
        ),
    ))


def permission_hierarchy():
    package = "com.android.permissioncontroller"
    return parsed(node(
        resource=f"{package}:id/grant_dialog", package=package,
        klass="android.widget.LinearLayout", clickable="true",
        children="".join((
            node(
                resource=f"{package}:id/permission_message", package=package,
                klass="android.widget.TextView",
                text="Allow TikTok to take pictures and record video?",
                clickable="false",
            ),
            node(
                resource=f"{package}:id/permission_allow_foreground_only_button",
                package=package, klass="android.widget.Button",
                text="WHILE USING THE APP",
            ),
            node(
                resource=f"{package}:id/permission_deny_and_dont_ask_again_button",
                package=package, klass="android.widget.Button", text="DON’T ALLOW",
            ),
        )),
    ))


def media_permission_hierarchy():
    """Sanitized Runtime 17 Android 11 photos/media permission structure."""
    package = "com.android.permissioncontroller"
    return parsed(node(
        resource=f"{package}:id/grant_singleton", package=package,
        klass="android.widget.LinearLayout", clickable="true",
        children=node(
            resource=f"{package}:id/grant_dialog", package=package,
            klass="android.widget.LinearLayout", clickable="true",
            children="".join((
                node(
                    resource=f"{package}:id/permission_message", package=package,
                    klass="android.widget.TextView",
                    text="Allow TikTok to access photos and media on your device?",
                    clickable="false",
                ),
                node(
                    resource=f"{package}:id/permission_allow_button",
                    package=package, klass="android.widget.Button", text="ALLOW",
                ),
                node(
                    resource=f"{package}:id/permission_deny_button",
                    package=package, klass="android.widget.Button",
                    text="DON’T ALLOW",
                ),
            )),
        ),
    ))


class FakeSession:
    def __init__(
        self, hierarchies, packages=None, *, tap_error=None, inventories=None,
        activity="TikTokActivity", keyboards=None,
    ):
        self.hierarchies = iter(hierarchies)
        self.packages = iter(packages or ["com.ss.android.ugc.trill"] * 20)
        self.tap_error = tap_error
        self.taps = []
        self.inventories = iter(inventories or [])
        self.activity = activity
        self.keyboards = iter(keyboards or [False] * 20)
        self.focuses = []
        self.replacements = []
        self.back_count = 0

    def get_foreground_app(self):
        return AdbForegroundApp(next(self.packages), "Activity")

    def dump_ui_hierarchy(self):
        value = next(self.hierarchies)
        if isinstance(value, Exception):
            raise value
        return value

    def get_foreground_activity(self):
        return AdbForegroundApp("com.ss.android.ugc.trill", self.activity)

    def get_media_inventory(self):
        return next(self.inventories)

    def tap_element(self, element):
        if self.tap_error:
            raise self.tap_error
        self.taps.append(element)

    def focus_element(self, element):
        self.focuses.append(element)

    def replace_focused_text(self, current_length, value):
        self.replacements.append((current_length, value))

    def validate_text_entry(self, value):
        return None

    def is_keyboard_visible(self):
        return next(self.keyboards)

    def back(self):
        self.back_count += 1


def action(**kwargs):
    return TikTokActionService(sleep=lambda _: None, **kwargs)


def delivery_media(*, duration_ms=2000):
    return AdbMediaRecord(
        20, "tik024-media-identity-d69.mp4", 17308, "video/mp4",
        duration_ms, "Download/TikTokManager/", "TikTokManager",
    )


def test_home_to_media_picker_uses_unique_profile_selector() -> None:
    session = FakeSession([home_hierarchy(), camera_hierarchy()])
    result = action().open_create(
        session, TEST_PROFILE, expected_package=TEST_PROFILE.package_name
    )
    assert (result.screen_before, result.screen_after) == (
        TikTokScreen.HOME, TikTokScreen.CAMERA_CREATE
    )
    assert result.changed is True
    assert result.selector_key == "create_button"
    assert result.resolution_method == "resource_id"
    assert len(session.taps) == 1


def test_already_media_picker_is_idempotent() -> None:
    session = FakeSession([media_hierarchy()])
    result = action().open_create(
        session, TEST_PROFILE, expected_package=TEST_PROFILE.package_name
    )
    assert result.screen_after == TikTokScreen.MEDIA_PICKER
    assert result.changed is False and session.taps == []


def test_camera_to_media_picker_and_end_to_end_transition() -> None:
    assert TRILL_44_4_3_CAMERA_V3.fingerprint == (
        "f635e2157270b33370cf742e6adbe75b5925bb2b368f056ae6e6863fdc913937"
    )
    assert TRILL_44_4_3_MEDIA_PICKER_V4.fingerprint == (
        "9633850f8d74315f56063c5b8980d000e3928e9b959a274ca0411c3407091b9e"
    )
    assert TRILL_44_4_3_EDITOR_V5.fingerprint == (
        "70d10ad2d5692029d49d454af1ad0cf2ca21a2ee504c1cf1fc6cacef133244a8"
    )
    assert TRILL_44_4_3_EDITOR_ACTION_V6.fingerprint == (
        "51d4d2908e2ca6541051be93f768a748ee2b840426eef1bad724496eb7b74570"
    )
    assert TRILL_44_4_3_READY_V7.fingerprint == (
        "6081585ed317b52f23b82cb251be6dfa381efd46c724473dd03c03d9ca4d1b4f"
    )
    assert TRILL_44_4_3_CAPTION_ACTION_V8.fingerprint == (
        "a2be83ad6f43ea2b5776736e961c5be18b8baa19d8aa4456bc5ccbe967ca380a"
    )
    assert TRILL_44_4_3_PRIVACY_ENTRY_V9.fingerprint == (
        "e73e1c311f4d1b432fcd38503f7fc6f3a832b322378d62825f6e03c5d7774f54"
    )
    assert TRILL_44_4_3_PRIVACY_MODAL_V10.fingerprint == (
        "abe32a853bef79e9860bccdf9737655068daef7eb3d67a1227ee07021731d112"
    )
    open_picker = FakeSession([camera_hierarchy(), media_hierarchy()])
    result = action().open_media_picker(
        open_picker, TEST_PROFILE, expected_package=TEST_PROFILE.package_name
    )
    assert (result.screen_before, result.screen_after) == (
        TikTokScreen.CAMERA_CREATE, TikTokScreen.MEDIA_PICKER
    )
    assert result.changed is True
    assert result.selector_key == "gallery_entry"
    assert result.resolution_method == "resource_id"
    assert len(open_picker.taps) == 1

    already = FakeSession([media_hierarchy()])
    result = action().open_media_picker(
        already, TEST_PROFILE, expected_package=TEST_PROFILE.package_name
    )
    assert result.changed is False and already.taps == []


def test_media_picker_classifies_with_empty_or_populated_grid() -> None:
    resolver = TikTokScreenResolver()
    for hierarchy in (media_hierarchy(empty=True), media_hierarchy(empty=False)):
        assert resolver.classify(
            hierarchy, TEST_PROFILE, TEST_PROFILE.package_name
        ) == TikTokScreen.MEDIA_PICKER


def test_media_picker_missing_required_grid_is_unknown() -> None:
    assert TikTokScreenResolver().classify(
        media_hierarchy(include_grid=False), TEST_PROFILE,
        TEST_PROFILE.package_name,
    ) == TikTokScreen.UNKNOWN


def test_editor_classification_uses_stable_core_and_ignores_dynamic_preview() -> None:
    resolver = TikTokScreenResolver()
    for hierarchy in (
        editor_hierarchy(dynamic_variant=0),
        editor_hierarchy(dynamic_variant=3),
    ):
        assert resolver.classify(
            hierarchy, TEST_PROFILE, TEST_PROFILE.package_name
        ) == TikTokScreen.EDIT_MEDIA
    assert resolver.classify(
        editor_hierarchy(include_next=False), TEST_PROFILE,
        TEST_PROFILE.package_name,
    ) == TikTokScreen.UNKNOWN


def test_media_identity_resolves_exclusive_inventory_with_matching_duration() -> None:
    expected = AdbMediaRecord(
        media_id=20,
        display_name="tik024-media-identity-d69.mp4",
        size_bytes=17308,
        mime_type="video/mp4",
        duration_ms=2000,
        relative_path="Download/TikTokManager/",
        bucket_display_name="TikTokManager",
    )
    hierarchy = media_hierarchy(empty=False)
    result = MediaIdentityResolver().resolve(
        hierarchy, TEST_PROFILE,
        expected=expected, media_inventory=(expected,),
    )
    assert result.media_id == 20
    assert result.display_name == expected.display_name
    assert result.bounds.center == (121, 357)
    assert result.duration_seconds == 2
    assert result.resolution_method == "exclusive_media_inventory_duration"


def test_media_identity_rejects_empty_grid_and_position_only_evidence() -> None:
    expected = AdbMediaRecord(
        20, "tik024-media-identity-d69.mp4", 17308, "video/mp4", 2000,
        "Download/TikTokManager/", "TikTokManager",
    )
    with pytest.raises(TikTokActionError) as missing:
        MediaIdentityResolver().resolve(
            media_hierarchy(empty=True), TEST_PROFILE,
            expected=expected, media_inventory=(expected,),
        )
    assert missing.value.code == "TIKTOK_MEDIA_NOT_FOUND"

    unrelated = AdbMediaRecord(
        21, "another-video.mp4", 20000, "video/mp4", 2000,
        "Download/", "Download",
    )
    with pytest.raises(TikTokActionError) as ambiguous:
        MediaIdentityResolver().resolve(
            media_hierarchy(empty=False), TEST_PROFILE,
            expected=expected, media_inventory=(expected, unrelated),
        )
    assert ambiguous.value.code == "TIKTOK_MEDIA_AMBIGUOUS"


def test_media_identity_rejects_duration_mismatch() -> None:
    expected = AdbMediaRecord(
        20, "tik024-media-identity-d69.mp4", 17308, "video/mp4", 3000,
        "Download/TikTokManager/", "TikTokManager",
    )
    with pytest.raises(TikTokActionError) as caught:
        MediaIdentityResolver().resolve(
            media_hierarchy(empty=False), TEST_PROFILE,
            expected=expected, media_inventory=(expected,),
        )
    assert caught.value.code == "TIKTOK_MEDIA_AMBIGUOUS"


def test_camera_gallery_entry_must_be_unique() -> None:
    session = FakeSession([camera_hierarchy(duplicate_gallery=True)])
    with pytest.raises(TikTokActionError) as caught:
        action().open_media_picker(
            session, TEST_PROFILE, expected_package=TEST_PROFILE.package_name
        )
    assert caught.value.code == "TIKTOK_ELEMENT_AMBIGUOUS"
    assert session.taps == []


def test_missing_and_ambiguous_create_selector_fail_before_mutation() -> None:
    without_create = replace(
        TEST_PROFILE,
        selectors=tuple(x for x in TEST_PROFILE.selectors if x.key != "create_button"),
        screens=tuple(
            replace(
                x,
                required_selectors=("bottom_navigation", "home_tab", "profile_tab"),
                minimum_score=6,
            ) if x.key == "HOME" else x
            for x in TEST_PROFILE.screens
        ),
    )
    missing = FakeSession([home_hierarchy()])
    with pytest.raises(TikTokActionError) as caught:
        action().open_create(
            missing, without_create, expected_package=without_create.package_name
        )
    assert caught.value.code == "TIKTOK_ELEMENT_NOT_FOUND" and missing.taps == []

    ambiguous = FakeSession([home_hierarchy(duplicate_create=True)])
    with pytest.raises(TikTokActionError) as caught:
        action().open_create(
            ambiguous, TEST_PROFILE, expected_package=TEST_PROFILE.package_name
        )
    assert caught.value.code == "TIKTOK_ELEMENT_AMBIGUOUS" and ambiguous.taps == []


def test_foreground_loss_and_stale_snapshot_fail_before_tap() -> None:
    background = FakeSession(
        [home_hierarchy()],
        packages=["com.ss.android.ugc.trill", "com.android.launcher3"],
    )
    with pytest.raises(TikTokActionError) as caught:
        action().open_create(
            background, TEST_PROFILE, expected_package=TEST_PROFILE.package_name
        )
    assert caught.value.code == "TIKTOK_APP_NOT_FOREGROUND"
    assert background.taps == []

    stale = FakeSession(
        [home_hierarchy()], tap_error=tiktok_error("TIKTOK_UI_STATE_UNCERTAIN")
    )
    with pytest.raises(TikTokActionError) as caught:
        action().open_create(
            stale, TEST_PROFILE, expected_package=TEST_PROFILE.package_name
        )
    assert caught.value.code == "TIKTOK_UI_STATE_UNCERTAIN"


def test_timeout_before_mutation_and_cancellation_do_not_tap() -> None:
    timed_out = FakeSession([tiktok_error("TIKTOK_SCREEN_TIMEOUT", retryable=True)])
    with pytest.raises(TikTokActionError) as caught:
        action().open_create(
            timed_out, TEST_PROFILE, expected_package=TEST_PROFILE.package_name
        )
    assert caught.value.code == "TIKTOK_SCREEN_TIMEOUT" and timed_out.taps == []

    cancelled = FakeSession([home_hierarchy()])
    with pytest.raises(TikTokActionError) as caught:
        action().open_create(
            cancelled, TEST_PROFILE, expected_package=TEST_PROFILE.package_name,
            cancelled=lambda: True,
        )
    assert caught.value.code == "TIKTOK_ACTION_CANCELLED" and cancelled.taps == []


def test_post_dispatch_success_wins_deadline_and_unknown_is_uncertain() -> None:
    succeeded = FakeSession([home_hierarchy(), media_hierarchy()])
    result = action(
        timeout_seconds=0.1, monotonic=iter((0.0, 1.0)).__next__
    ).open_create(
        succeeded, TEST_PROFILE, expected_package=TEST_PROFILE.package_name
    )
    assert result.screen_after == TikTokScreen.MEDIA_PICKER

    uncertain = FakeSession([home_hierarchy(), parsed(node(resource="unknown"))])
    with pytest.raises(TikTokActionError) as caught:
        action(
            timeout_seconds=0.1, monotonic=iter((0.0, 1.0)).__next__
        ).open_create(
            uncertain, TEST_PROFILE, expected_package=TEST_PROFILE.package_name
        )
    assert caught.value.code == "TIKTOK_UI_STATE_UNCERTAIN"


def test_permission_overlay_is_distinct_and_stops_without_a_second_tap() -> None:
    controller = "com.android.permissioncontroller"
    hierarchy = permission_hierarchy()
    observation = TikTokOverlayResolver().detect(
        AdbForegroundApp(controller, ".permission.ui.GrantPermissionsActivity"),
        hierarchy,
    )
    assert observation.overlay == TikTokOverlay.ANDROID_PERMISSION_PROMPT
    assert observation.permission_kind == "camera"

    first = FakeSession(
        [home_hierarchy(), hierarchy],
        packages=[TEST_PROFILE.package_name, TEST_PROFILE.package_name, controller],
    )
    dispatched = []
    with pytest.raises(TikTokActionError) as caught:
        action().open_create(
            first, TEST_PROFILE, expected_package=TEST_PROFILE.package_name,
            on_tap_dispatched=dispatched.append,
        )
    assert caught.value.code == "TIKTOK_PERMISSION_REQUIRED"
    assert caught.value.retryable is False
    assert caught.value.safe_metadata == {
        "overlay": "ANDROID_PERMISSION_PROMPT",
        "permission_kind": "camera",
        "action": "create",
        "changed": True,
    }
    assert len(first.taps) == 1
    assert len(dispatched) == 1 and dispatched[0].selector_key == "create_button"

    retry = FakeSession([hierarchy], packages=[controller])
    with pytest.raises(TikTokActionError) as caught:
        action().open_create(
            retry, TEST_PROFILE, expected_package=TEST_PROFILE.package_name
        )
    assert caught.value.code == "TIKTOK_PERMISSION_REQUIRED"
    assert caught.value.safe_metadata["changed"] is False
    assert retry.taps == []


def test_media_permission_overlay_after_gallery_tap_is_operator_required() -> None:
    controller = "com.android.permissioncontroller"
    hierarchy = media_permission_hierarchy()
    observation = TikTokOverlayResolver().detect(
        AdbForegroundApp(controller, ".permission.ui.GrantPermissionsActivity"),
        hierarchy,
    )
    assert observation.overlay == TikTokOverlay.ANDROID_PERMISSION_PROMPT
    assert observation.permission_kind == "media"

    session = FakeSession(
        [camera_hierarchy(), hierarchy],
        packages=[TEST_PROFILE.package_name, TEST_PROFILE.package_name, controller],
    )
    dispatched = []
    with pytest.raises(TikTokActionError) as caught:
        action().open_media_picker(
            session, TEST_PROFILE, expected_package=TEST_PROFILE.package_name,
            on_tap_dispatched=dispatched.append,
        )
    assert caught.value.code == "TIKTOK_PERMISSION_REQUIRED"
    assert caught.value.retryable is False
    assert caught.value.safe_metadata == {
        "overlay": "ANDROID_PERMISSION_PROMPT",
        "permission_kind": "media",
        "action": "open_media_picker",
        "changed": True,
    }
    assert len(session.taps) == 1
    assert len(dispatched) == 1 and dispatched[0].selector_key == "gallery_entry"

    # A retry observes the operator gate before resolving or tapping anything.
    retry = FakeSession([hierarchy], packages=[controller])
    with pytest.raises(TikTokActionError) as caught:
        action().open_media_picker(
            retry, TEST_PROFILE, expected_package=TEST_PROFILE.package_name
        )
    assert caught.value.code == "TIKTOK_PERMISSION_REQUIRED"
    assert caught.value.safe_metadata["changed"] is False
    assert retry.taps == []


def test_fresh_runtime_immersive_cling_is_a_blocking_overlay() -> None:
    """Runtime 18's real system overlay must not be mistaken for TikTok UI."""
    hierarchy = parsed(node(
        klass="android.widget.RelativeLayout",
        package="android",
        clickable="false",
        bounds="[0,0][720,497]",
        children="".join((
            node(
                resource="android:id/immersive_cling_chevron",
                klass="android.widget.FrameLayout",
                package="android",
                clickable="false",
                bounds="[284,0][436,104]",
            ),
            node(
                resource="android:id/immersive_cling_title",
                text="Viewing full screen",
                klass="android.widget.TextView",
                package="android",
                clickable="false",
                bounds="[0,104][720,249]",
            ),
            node(
                resource="android:id/immersive_cling_description",
                text="To exit, swipe down from the top.",
                klass="android.widget.TextView",
                package="android",
                clickable="false",
                bounds="[0,249][720,317]",
            ),
            node(
                resource="android:id/ok",
                text="GOT IT",
                klass="android.widget.Button",
                package="android",
                bounds="[464,353][640,449]",
            ),
        )),
    ))

    observation = TikTokOverlayResolver().detect(
        AdbForegroundApp(
            "com.ss.android.ugc.trill",
            "com.ss.android.ugc.aweme.journey.NewUserJourneyActivity",
        ),
        hierarchy,
    )

    assert observation.overlay == TikTokOverlay.BLOCKING_MODAL
    assert observation.permission_kind is None


def test_unknown_permission_controller_overlay_remains_uncertain() -> None:
    controller = "com.android.permissioncontroller"
    unknown = parsed(node(package=controller, resource="android:id/content"))
    session = FakeSession([unknown], packages=[controller])
    with pytest.raises(TikTokActionError) as caught:
        action().open_create(
            session, TEST_PROFILE, expected_package=TEST_PROFILE.package_name
        )
    assert caught.value.code == "TIKTOK_UI_STATE_UNCERTAIN"
    assert session.taps == []


def test_select_media_revalidates_and_dispatches_exactly_one_tap() -> None:
    picker = media_hierarchy(empty=False)
    next_screen = editor_hierarchy()
    expected = delivery_media()
    session = FakeSession(
        [picker, picker, next_screen],
        inventories=[(expected,), (expected,)],
    )
    dispatched = []
    result = action().select_media(
        session, TEST_PROFILE,
        expected_package=TEST_PROFILE.package_name,
        expected_media=expected,
        on_tap_dispatched=dispatched.append,
    )
    assert result.screen_before == TikTokScreen.MEDIA_PICKER
    assert result.screen_after == TikTokScreen.EDIT_MEDIA
    assert result.resolution_method == "exclusive_media_inventory_duration"
    assert result.changed is True and result.tap_dispatched is True
    assert result.calibration_required is False
    assert result.foreground_activity == "TikTokActivity"
    assert len(session.taps) == 1
    assert len(dispatched) == 1
    assert dispatched[0].selector_key == "delivered_media"
    assert dispatched[0].bounds.center == (121, 357)


def test_select_media_is_idempotent_on_calibrated_editor_without_tap() -> None:
    session = FakeSession([editor_hierarchy()])
    result = action().select_media(
        session, TEST_PROFILE,
        expected_package=TEST_PROFILE.package_name,
        expected_media=delivery_media(),
    )
    assert result.screen_before == TikTokScreen.EDIT_MEDIA
    assert result.screen_after == TikTokScreen.EDIT_MEDIA
    assert result.changed is False
    assert result.tap_dispatched is False
    assert result.resolution_method == "calibrated_postcondition"
    assert result.calibration_required is False
    assert session.taps == []


@pytest.mark.parametrize(
    ("hierarchy", "inventory", "requested", "code"),
    (
        (media_hierarchy(empty=True), (delivery_media(),), delivery_media(), "TIKTOK_MEDIA_NOT_FOUND"),
        (
            media_hierarchy(empty=False),
            (
                delivery_media(),
                AdbMediaRecord(21, "other.mp4", 100, "video/mp4", 2000, "Download/", "Download"),
            ),
            delivery_media(),
            "TIKTOK_MEDIA_AMBIGUOUS",
        ),
        (media_hierarchy(empty=False), (delivery_media(),), delivery_media(duration_ms=3000), "TIKTOK_MEDIA_AMBIGUOUS"),
    ),
)
def test_select_media_rejects_unproven_identity_without_tap(
    hierarchy, inventory, requested, code,
) -> None:
    session = FakeSession([hierarchy], inventories=[inventory])
    with pytest.raises(TikTokActionError) as caught:
        action().select_media(
            session, TEST_PROFILE,
            expected_package=TEST_PROFILE.package_name,
            expected_media=requested,
        )
    assert caught.value.code == code
    assert session.taps == []


def test_select_media_fails_closed_when_hierarchy_changes_before_tap() -> None:
    expected = delivery_media()
    session = FakeSession(
        [media_hierarchy(empty=False), media_hierarchy(empty=True)],
        inventories=[(expected,), (expected,)],
    )
    with pytest.raises(TikTokActionError) as caught:
        action().select_media(
            session, TEST_PROFILE,
            expected_package=TEST_PROFILE.package_name,
            expected_media=expected,
        )
    assert caught.value.code == "TIKTOK_UI_STATE_UNCERTAIN"
    assert session.taps == []


def test_select_media_fails_closed_when_media_store_changes_before_tap() -> None:
    expected = delivery_media()
    unrelated = AdbMediaRecord(
        21, "other.mp4", 100, "video/mp4", 2000, "Download/", "Download",
    )
    picker = media_hierarchy(empty=False)
    session = FakeSession(
        [picker, picker], inventories=[(expected,), (expected, unrelated)],
    )
    with pytest.raises(TikTokActionError) as caught:
        action().select_media(
            session, TEST_PROFILE,
            expected_package=TEST_PROFILE.package_name,
            expected_media=expected,
        )
    assert caught.value.code == "TIKTOK_UI_STATE_UNCERTAIN"
    assert session.taps == []


def test_select_media_never_replays_when_already_beyond_picker() -> None:
    session = FakeSession([parsed(node(resource="uncalibrated-next-screen"))])
    with pytest.raises(TikTokActionError) as caught:
        action().select_media(
            session, TEST_PROFILE,
            expected_package=TEST_PROFILE.package_name,
            expected_media=delivery_media(),
        )
    assert caught.value.code == "TIKTOK_UI_STATE_UNCERTAIN"
    assert session.taps == []


def test_open_caption_dispatches_one_next_tap_and_reports_calibration() -> None:
    unknown = parsed(node(
        resource="com.ss.android.ugc.trill:id/post-root",
        klass="android.widget.FrameLayout", clickable="false",
    ))
    editor = editor_hierarchy()
    session = FakeSession([editor, editor, unknown])
    dispatched = []
    result = action().open_caption(
        session, TRILL_44_4_3_EDITOR_ACTION_V6,
        expected_package=TRILL_44_4_3_EDITOR_ACTION_V6.package_name,
        on_tap_dispatched=dispatched.append,
    )
    assert result.screen_before == TikTokScreen.EDIT_MEDIA
    assert result.screen_after == TikTokScreen.UNKNOWN
    assert result.changed is True
    assert result.tap_dispatched is True
    assert result.calibration_required is True
    assert result.selector_key == "editor_next_action"
    assert result.resolution_method == "resource_id"
    assert len(session.taps) == len(dispatched) == 1


def test_skip_interests_dispatches_only_skip_once_and_reports_calibration() -> None:
    before = interests_hierarchy()
    unknown = parsed(node(resource="successor-root", clickable="false"))
    session = FakeSession([before, before, unknown])
    dispatched = []
    result = action().skip_interests(
        session, TRILL_44_4_3_INTERESTS_ACTION_V14,
        expected_package=TRILL_44_4_3_INTERESTS_ACTION_V14.package_name,
        on_tap_dispatched=dispatched.append,
    )
    assert result.screen_before == TikTokScreen.ONBOARDING_INTERESTS
    assert result.screen_after == TikTokScreen.UNKNOWN
    assert result.changed is True and result.tap_dispatched is True
    assert result.calibration_required is True
    assert result.selector_key == "interests_skip_control"
    assert result.resolution_method == "resource_id"
    assert len(session.taps) == len(dispatched) == 1
    assert session.taps[0].selector_key == "interests_skip_control"


def test_skip_interests_rejects_ambiguity_stale_state_and_overlay_without_tap() -> None:
    ambiguous = FakeSession([interests_hierarchy(duplicate_skip=True)])
    with pytest.raises(TikTokActionError) as caught:
        action().skip_interests(
            ambiguous, TRILL_44_4_3_INTERESTS_ACTION_V14,
            expected_package=TRILL_44_4_3_INTERESTS_ACTION_V14.package_name,
        )
    assert caught.value.code == "TIKTOK_ELEMENT_AMBIGUOUS"
    assert ambiguous.taps == []

    stale = FakeSession([interests_hierarchy(), interests_hierarchy(variant=1)])
    with pytest.raises(TikTokActionError) as caught:
        action().skip_interests(
            stale, TRILL_44_4_3_INTERESTS_ACTION_V14,
            expected_package=TRILL_44_4_3_INTERESTS_ACTION_V14.package_name,
        )
    assert caught.value.code == "TIKTOK_UI_STATE_UNCERTAIN"
    assert stale.taps == []

    blocking = parsed(node(
        package="android", klass="android.widget.FrameLayout",
        clickable="false", children="".join((
            node(resource="android:id/immersive_cling_chevron", package="android", clickable="false"),
            node(resource="android:id/immersive_cling_title", package="android", klass="android.widget.TextView", clickable="false"),
            node(resource="android:id/immersive_cling_description", package="android", klass="android.widget.TextView", clickable="false"),
            node(resource="android:id/ok", package="android", klass="android.widget.Button"),
        )),
    ))
    overlaid = FakeSession([blocking])
    with pytest.raises(TikTokActionError) as caught:
        action().skip_interests(
            overlaid, TRILL_44_4_3_INTERESTS_ACTION_V14,
            expected_package=TRILL_44_4_3_INTERESTS_ACTION_V14.package_name,
        )
    assert caught.value.code == "TIKTOK_UI_STATE_UNCERTAIN"
    assert overlaid.taps == []


def test_skip_interests_is_idempotent_at_calibrated_home() -> None:
    session = FakeSession([home_hierarchy()])
    result = action().skip_interests(
        session, TRILL_44_4_3_INTERESTS_ACTION_V14,
        expected_package=TRILL_44_4_3_INTERESTS_ACTION_V14.package_name,
    )
    assert result.screen_before == result.screen_after == TikTokScreen.HOME
    assert result.changed is False and result.tap_dispatched is False
    assert result.resolution_method == "calibrated_postcondition"
    assert session.taps == []


def test_open_profile_unknown_destination_fails_closed_after_one_tap() -> None:
    before = home_hierarchy()
    unknown = parsed(node(resource="profile-successor-root", clickable="false"))
    session = FakeSession([before, before, unknown])
    dispatched = []
    with pytest.raises(TikTokActionError) as caught:
        action().open_profile(
            session, TRILL_44_4_3_PROFILE_ACTION_V15,
            expected_package=TRILL_44_4_3_PROFILE_ACTION_V15.package_name,
            on_tap_dispatched=dispatched.append,
        )
    assert caught.value.code == "TIKTOK_UI_STATE_UNCERTAIN"
    assert len(session.taps) == len(dispatched) == 1


def test_open_profile_rejects_ambiguity_stale_state_and_overlay_without_tap() -> None:
    ambiguous = FakeSession([home_hierarchy(duplicate_profile=True)])
    with pytest.raises(TikTokActionError) as caught:
        action().open_profile(
            ambiguous, TRILL_44_4_3_PROFILE_ACTION_V15,
            expected_package=TRILL_44_4_3_PROFILE_ACTION_V15.package_name,
        )
    assert caught.value.code == "TIKTOK_ELEMENT_AMBIGUOUS"
    assert ambiguous.taps == []

    stale = FakeSession([home_hierarchy(), home_hierarchy(variant=1)])
    with pytest.raises(TikTokActionError) as caught:
        action().open_profile(
            stale, TRILL_44_4_3_PROFILE_ACTION_V15,
            expected_package=TRILL_44_4_3_PROFILE_ACTION_V15.package_name,
        )
    assert caught.value.code == "TIKTOK_UI_STATE_UNCERTAIN"
    assert stale.taps == []

    blocking = parsed(node(
        package="android", klass="android.widget.FrameLayout",
        clickable="false", children="".join((
            node(resource="android:id/immersive_cling_chevron", package="android", clickable="false"),
            node(resource="android:id/immersive_cling_title", package="android", klass="android.widget.TextView", clickable="false"),
            node(resource="android:id/immersive_cling_description", package="android", klass="android.widget.TextView", clickable="false"),
            node(resource="android:id/ok", package="android", klass="android.widget.Button"),
        )),
    ))
    overlaid = FakeSession([blocking])
    with pytest.raises(TikTokActionError) as caught:
        action().open_profile(
            overlaid, TRILL_44_4_3_PROFILE_ACTION_V15,
            expected_package=TRILL_44_4_3_PROFILE_ACTION_V15.package_name,
        )
    assert caught.value.code == "TIKTOK_UI_STATE_UNCERTAIN"
    assert overlaid.taps == []


def test_logged_in_profile_classifies_and_open_profile_is_idempotent() -> None:
    hierarchy = profile_hierarchy()
    assert TikTokScreenResolver().classify(
        hierarchy, TRILL_44_4_3_PROFILE_V16,
        TRILL_44_4_3_PROFILE_V16.package_name,
    ) == TikTokScreen.PROFILE
    session = FakeSession([hierarchy])
    result = action().open_profile(
        session, TRILL_44_4_3_PROFILE_V16,
        expected_package=TRILL_44_4_3_PROFILE_V16.package_name,
    )
    assert result.screen_before == result.screen_after == TikTokScreen.PROFILE
    assert result.changed is False and result.tap_dispatched is False
    assert session.taps == []


def test_profile_tab_destination_is_state_dependent_and_single_tap() -> None:
    home = home_hierarchy()
    logged_in = FakeSession([home, home, profile_hierarchy()])
    result = action().open_profile(
        logged_in, TRILL_44_4_3_SIGNUP_METHOD_V17,
        expected_package=TRILL_44_4_3_SIGNUP_METHOD_V17.package_name,
    )
    assert result.screen_before == TikTokScreen.HOME
    assert result.screen_after == TikTokScreen.PROFILE
    assert result.changed is True and result.tap_dispatched is True
    assert len(logged_in.taps) == 1

    logged_out = FakeSession([home, home, signup_method_hierarchy()])
    result = action().open_profile(
        logged_out, TRILL_44_4_3_SIGNUP_METHOD_V17,
        expected_package=TRILL_44_4_3_SIGNUP_METHOD_V17.package_name,
    )
    assert result.screen_before == TikTokScreen.HOME
    assert result.screen_after == TikTokScreen.SIGNUP_METHOD
    assert result.changed is True and result.tap_dispatched is True
    assert len(logged_out.taps) == 1


def test_signup_method_classifies_and_open_profile_is_idempotent() -> None:
    resolver = TikTokScreenResolver()
    hierarchy = signup_method_hierarchy()
    assert resolver.classify(
        hierarchy, TRILL_44_4_3_SIGNUP_METHOD_V17,
        TRILL_44_4_3_SIGNUP_METHOD_V17.package_name,
    ) == TikTokScreen.SIGNUP_METHOD
    assert resolver.classify(
        signup_method_hierarchy(include_email=False),
        TRILL_44_4_3_SIGNUP_METHOD_V17,
        TRILL_44_4_3_SIGNUP_METHOD_V17.package_name,
    ) == TikTokScreen.UNKNOWN

    session = FakeSession([hierarchy])
    result = action().open_profile(
        session, TRILL_44_4_3_SIGNUP_METHOD_V17,
        expected_package=TRILL_44_4_3_SIGNUP_METHOD_V17.package_name,
    )
    assert result.screen_before == result.screen_after == TikTokScreen.SIGNUP_METHOD
    assert result.changed is False and result.tap_dispatched is False
    assert result.resolution_method == "calibrated_postcondition"
    assert session.taps == []


def test_choose_email_signup_dispatches_exact_semantic_target_once() -> None:
    before = signup_method_hierarchy()
    successor = parsed(node(resource="email-successor", clickable="false"))
    session = FakeSession([before, before, successor])
    dispatched = []
    result = action().choose_email_signup(
        session, TRILL_44_4_3_EMAIL_ACTION_V18,
        expected_package=TRILL_44_4_3_EMAIL_ACTION_V18.package_name,
        on_tap_dispatched=dispatched.append,
    )
    assert result.screen_before == TikTokScreen.SIGNUP_METHOD
    assert result.screen_after == TikTokScreen.UNKNOWN
    assert result.changed is True and result.tap_dispatched is True
    assert result.calibration_required is True
    assert result.selector_key == "signup_email_method"
    assert result.resolution_method == "content_description"
    assert len(session.taps) == len(dispatched) == 1
    assert session.taps[0].bounds.left == 56
    assert session.taps[0].bounds.top == 830


def test_choose_email_signup_fails_closed_before_dispatch() -> None:
    ambiguous = FakeSession([signup_method_hierarchy(duplicate_email=True)])
    with pytest.raises(TikTokActionError) as caught:
        action().choose_email_signup(
            ambiguous, TRILL_44_4_3_EMAIL_ACTION_V18,
            expected_package=TRILL_44_4_3_EMAIL_ACTION_V18.package_name,
        )
    assert caught.value.code == "TIKTOK_ELEMENT_AMBIGUOUS"
    assert ambiguous.taps == []

    stale = FakeSession([
        signup_method_hierarchy(), signup_method_hierarchy(variant=1),
    ])
    with pytest.raises(TikTokActionError) as caught:
        action().choose_email_signup(
            stale, TRILL_44_4_3_EMAIL_ACTION_V18,
            expected_package=TRILL_44_4_3_EMAIL_ACTION_V18.package_name,
        )
    assert caught.value.code == "TIKTOK_UI_STATE_UNCERTAIN"
    assert stale.taps == []

    blocking = parsed(node(
        package="android", klass="android.widget.FrameLayout",
        clickable="false", children="".join((
            node(resource="android:id/immersive_cling_chevron", package="android", clickable="false"),
            node(resource="android:id/immersive_cling_title", package="android", klass="android.widget.TextView", clickable="false"),
            node(resource="android:id/immersive_cling_description", package="android", klass="android.widget.TextView", clickable="false"),
            node(resource="android:id/ok", package="android", klass="android.widget.Button"),
        )),
    ))
    overlaid = FakeSession([blocking])
    with pytest.raises(TikTokActionError) as caught:
        action().choose_email_signup(
            overlaid, TRILL_44_4_3_EMAIL_ACTION_V18,
            expected_package=TRILL_44_4_3_EMAIL_ACTION_V18.package_name,
        )
    assert caught.value.code == "TIKTOK_UI_STATE_UNCERTAIN"
    assert overlaid.taps == []


def test_email_entry_classifies_and_choose_email_is_idempotent() -> None:
    resolver = TikTokScreenResolver()
    hierarchy = email_entry_hierarchy()
    assert resolver.classify(
        hierarchy, TRILL_44_4_3_EMAIL_ENTRY_V20,
        TRILL_44_4_3_EMAIL_ENTRY_V20.package_name,
    ) == TikTokScreen.EMAIL_ENTRY
    assert resolver.classify(
        email_entry_hierarchy(include_input=False),
        TRILL_44_4_3_EMAIL_ENTRY_V20,
        TRILL_44_4_3_EMAIL_ENTRY_V20.package_name,
    ) == TikTokScreen.UNKNOWN

    transition = FakeSession([
        signup_method_hierarchy(), signup_method_hierarchy(), hierarchy,
    ])
    result = action().choose_email_signup(
        transition, TRILL_44_4_3_EMAIL_ENTRY_V20,
        expected_package=TRILL_44_4_3_EMAIL_ENTRY_V20.package_name,
    )
    assert result.screen_before == TikTokScreen.SIGNUP_METHOD
    assert result.screen_after == TikTokScreen.EMAIL_ENTRY
    assert result.changed is True and result.tap_dispatched is True
    assert result.calibration_required is False
    assert len(transition.taps) == 1

    already = FakeSession([hierarchy])
    result = action().choose_email_signup(
        already, TRILL_44_4_3_EMAIL_ENTRY_V20,
        expected_package=TRILL_44_4_3_EMAIL_ENTRY_V20.package_name,
    )
    assert result.screen_before == result.screen_after == TikTokScreen.EMAIL_ENTRY
    assert result.changed is False and result.tap_dispatched is False
    assert already.taps == []

    actionable = {
        selector.key for selector in TRILL_44_4_3_EMAIL_ENTRY_V20.selectors
        if selector.actionable
    }
    assert "signup_email_method" in actionable
    assert not {"signup_phone_input", "signup_continue", "signup_login_entry"} & actionable


def test_set_registration_email_replaces_and_verifies_without_continue() -> None:
    requested = "phase2e@example.com"
    before = email_entry_hierarchy()
    after = email_entry_hierarchy(
        field_text=requested, continue_enabled=True,
    )
    session = FakeSession([before, before, after], keyboards=[True])
    result = action().set_registration_email(
        session, TRILL_44_4_3_EMAIL_INPUT_V21,
        expected_package=TRILL_44_4_3_EMAIL_INPUT_V21.package_name,
        email=requested,
    )
    assert result.screen_before == result.screen_after == TikTokScreen.EMAIL_ENTRY
    assert result.changed is True and result.verification is True
    assert result.email_length == len(requested)
    assert result.continue_enabled is True
    assert requested not in repr(result)
    assert len(session.focuses) == 1
    assert session.replacements == [(len("Email address"), requested)]
    assert session.taps == [] and session.back_count == 0


def test_set_registration_email_is_idempotent_without_input_dispatch() -> None:
    requested = "phase2e@example.com"
    hierarchy = email_entry_hierarchy(
        field_text=requested, continue_enabled=True,
    )
    session = FakeSession([hierarchy])
    result = action().set_registration_email(
        session, TRILL_44_4_3_EMAIL_INPUT_V21,
        expected_package=TRILL_44_4_3_EMAIL_INPUT_V21.package_name,
        email=requested,
    )
    assert result.changed is False and result.verification is True
    assert result.continue_enabled is True
    assert session.focuses == [] and session.replacements == []
    assert session.taps == []


def test_set_registration_email_fails_closed_on_field_or_state_change() -> None:
    missing = FakeSession([email_entry_hierarchy(include_input=False)])
    with pytest.raises(TikTokActionError) as caught:
        action().set_registration_email(
            missing, TRILL_44_4_3_EMAIL_INPUT_V21,
            expected_package=TRILL_44_4_3_EMAIL_INPUT_V21.package_name,
            email="phase2e@example.com",
        )
    assert caught.value.code == "TIKTOK_UNKNOWN_SCREEN"
    assert missing.focuses == [] and missing.replacements == []

    ambiguous = FakeSession([email_entry_hierarchy(duplicate_input=True)])
    with pytest.raises(TikTokActionError) as caught:
        action().set_registration_email(
            ambiguous, TRILL_44_4_3_EMAIL_INPUT_V21,
            expected_package=TRILL_44_4_3_EMAIL_INPUT_V21.package_name,
            email="phase2e@example.com",
        )
    assert caught.value.code == "TIKTOK_ELEMENT_AMBIGUOUS"
    assert ambiguous.focuses == [] and ambiguous.replacements == []

    stale = FakeSession([
        email_entry_hierarchy(), email_entry_hierarchy(variant=1),
    ])
    with pytest.raises(TikTokActionError) as caught:
        action().set_registration_email(
            stale, TRILL_44_4_3_EMAIL_INPUT_V21,
            expected_package=TRILL_44_4_3_EMAIL_INPUT_V21.package_name,
            email="phase2e@example.com",
        )
    assert caught.value.code == "TIKTOK_UI_STATE_UNCERTAIN"
    assert stale.focuses == [] and stale.replacements == []

    blocking = parsed(node(
        package="android", klass="android.widget.FrameLayout",
        clickable="false", children="".join((
            node(resource="android:id/immersive_cling_chevron", package="android", clickable="false"),
            node(resource="android:id/immersive_cling_title", package="android", klass="android.widget.TextView", clickable="false"),
            node(resource="android:id/immersive_cling_description", package="android", klass="android.widget.TextView", clickable="false"),
            node(resource="android:id/ok", package="android", klass="android.widget.Button"),
        )),
    ))
    overlaid = FakeSession([blocking])
    with pytest.raises(TikTokActionError) as caught:
        action().set_registration_email(
            overlaid, TRILL_44_4_3_EMAIL_INPUT_V21,
            expected_package=TRILL_44_4_3_EMAIL_INPUT_V21.package_name,
            email="phase2e@example.com",
        )
    assert caught.value.code == "TIKTOK_UI_STATE_UNCERTAIN"
    assert overlaid.focuses == [] and overlaid.replacements == []


def test_set_registration_email_verification_mismatch_is_terminal() -> None:
    before = email_entry_hierarchy()
    mismatch = email_entry_hierarchy(field_text="wrong@example.com")
    session = FakeSession([before, before, mismatch], keyboards=[True])
    with pytest.raises(TikTokActionError) as caught:
        action(
            timeout_seconds=0.1,
            monotonic=iter((0.0, 1.0)).__next__,
        ).set_registration_email(
            session, TRILL_44_4_3_EMAIL_INPUT_V21,
            expected_package=TRILL_44_4_3_EMAIL_INPUT_V21.package_name,
            email="phase2e@example.com",
        )
    assert caught.value.code == "TIKTOK_EMAIL_VERIFICATION_FAILED"
    assert len(session.focuses) == 1 and len(session.replacements) == 1
    assert session.taps == []


def test_continue_registration_email_verifies_then_taps_exactly_once() -> None:
    requested = "phase2f@example.com"
    ready = email_entry_hierarchy(
        field_text=requested, continue_enabled=True,
    )
    successor = parsed(node(
        resource="com.ss.android.ugc.trill:id/unknown-successor",
        klass="android.widget.FrameLayout", clickable="false",
        bounds="[0,0][720,1184]",
    ))
    session = FakeSession([ready, ready, successor])
    result = action().continue_registration_email(
        session, TRILL_44_4_3_EMAIL_CONTINUE_V22,
        expected_package=TRILL_44_4_3_EMAIL_CONTINUE_V22.package_name,
        email=requested,
    )
    assert result.screen_before == TikTokScreen.EMAIL_ENTRY
    assert result.screen_after == TikTokScreen.UNKNOWN
    assert result.changed is True and result.tap_dispatched is True
    assert result.calibration_required is True
    assert result.selector_key == "email_continue"
    assert result.resolution_method == "resource_id"
    assert len(session.taps) == 1


def test_email_verification_is_calibrated_and_continue_is_idempotent() -> None:
    hierarchy = email_verification_hierarchy()
    assert TikTokScreenResolver().classify(
        hierarchy, TRILL_44_4_3_EMAIL_VERIFICATION_V23,
        TRILL_44_4_3_EMAIL_VERIFICATION_V23.package_name,
    ) == TikTokScreen.VERIFICATION_REQUIRED
    assert TikTokScreenResolver().classify(
        email_verification_hierarchy(include_resend=False),
        TRILL_44_4_3_EMAIL_VERIFICATION_V23,
        TRILL_44_4_3_EMAIL_VERIFICATION_V23.package_name,
    ) == TikTokScreen.VERIFICATION_REQUIRED

    ready = email_entry_hierarchy(
        field_text="phase2f@example.com", continue_enabled=True,
    )
    transition = FakeSession([ready, ready, hierarchy])
    result = action().continue_registration_email(
        transition, TRILL_44_4_3_EMAIL_VERIFICATION_V23,
        expected_package=TRILL_44_4_3_EMAIL_VERIFICATION_V23.package_name,
        email="phase2f@example.com",
    )
    assert result.screen_after == TikTokScreen.VERIFICATION_REQUIRED
    assert result.changed is True and result.tap_dispatched is True
    assert result.calibration_required is False
    assert len(transition.taps) == 1

    already = FakeSession([hierarchy])
    result = action().continue_registration_email(
        already, TRILL_44_4_3_EMAIL_VERIFICATION_V23,
        expected_package=TRILL_44_4_3_EMAIL_VERIFICATION_V23.package_name,
        email="phase2f@example.com",
    )
    assert result.screen_before == result.screen_after == TikTokScreen.VERIFICATION_REQUIRED
    assert result.changed is False and result.tap_dispatched is False
    assert already.taps == []


def test_email_verification_requires_multiple_stable_signals() -> None:
    package = "com.ss.android.ugc.trill"
    title_only = parsed(node(
        resource=f"{package}:id/ehn", text="Check your email",
        klass="android.widget.TextView", clickable="false",
    ))
    assert TikTokScreenResolver().classify(
        title_only, TRILL_44_4_3_EMAIL_VERIFICATION_V23,
        TRILL_44_4_3_EMAIL_VERIFICATION_V23.package_name,
    ) == TikTokScreen.UNKNOWN


@pytest.mark.parametrize(
    ("hierarchy", "expected_code"),
    [
        (
            email_entry_hierarchy(
                field_text="wrong@example.com", continue_enabled=True,
            ),
            "TIKTOK_REGISTRATION_EMAIL_MISMATCH",
        ),
        (
            email_entry_hierarchy(
                field_text="phase2f@example.com", continue_enabled=False,
            ),
            "TIKTOK_REGISTRATION_CONTINUE_DISABLED",
        ),
        (
            email_entry_hierarchy(
                field_text="phase2f@example.com", continue_enabled=True,
                duplicate_continue=True,
            ),
            "TIKTOK_ELEMENT_AMBIGUOUS",
        ),
    ],
)
def test_continue_registration_email_fails_closed_before_dispatch(
    hierarchy, expected_code: str,
) -> None:
    session = FakeSession([hierarchy])
    with pytest.raises(TikTokActionError) as caught:
        action().continue_registration_email(
            session, TRILL_44_4_3_EMAIL_CONTINUE_V22,
            expected_package=TRILL_44_4_3_EMAIL_CONTINUE_V22.package_name,
            email="phase2f@example.com",
        )
    assert caught.value.code == expected_code
    assert session.taps == []


def test_continue_registration_email_rejects_missing_stale_and_overlay_state() -> None:
    requested = "phase2f@example.com"
    missing = FakeSession([email_entry_hierarchy(
        field_text=requested, continue_enabled=True, include_continue=False,
    )])
    with pytest.raises(TikTokActionError) as caught:
        action().continue_registration_email(
            missing, TRILL_44_4_3_EMAIL_CONTINUE_V22,
            expected_package=TRILL_44_4_3_EMAIL_CONTINUE_V22.package_name,
            email=requested,
        )
    assert caught.value.code == "TIKTOK_ELEMENT_NOT_FOUND"
    assert missing.taps == []

    stale = FakeSession([
        email_entry_hierarchy(field_text=requested, continue_enabled=True),
        email_entry_hierarchy(
            field_text=requested, continue_enabled=True, variant=1,
        ),
    ])
    with pytest.raises(TikTokActionError) as caught:
        action().continue_registration_email(
            stale, TRILL_44_4_3_EMAIL_CONTINUE_V22,
            expected_package=TRILL_44_4_3_EMAIL_CONTINUE_V22.package_name,
            email=requested,
        )
    assert caught.value.code == "TIKTOK_UI_STATE_UNCERTAIN"
    assert stale.taps == []

    blocking = parsed(node(
        package="android", klass="android.widget.FrameLayout",
        clickable="false", children="".join((
            node(resource="android:id/immersive_cling_chevron", package="android", clickable="false"),
            node(resource="android:id/immersive_cling_title", package="android", klass="android.widget.TextView", clickable="false"),
            node(resource="android:id/immersive_cling_description", package="android", klass="android.widget.TextView", clickable="false"),
            node(resource="android:id/ok", package="android", klass="android.widget.Button"),
        )),
    ))
    overlaid = FakeSession([blocking])
    with pytest.raises(TikTokActionError) as caught:
        action().continue_registration_email(
            overlaid, TRILL_44_4_3_EMAIL_CONTINUE_V22,
            expected_package=TRILL_44_4_3_EMAIL_CONTINUE_V22.package_name,
            email=requested,
        )
    assert caught.value.code == "TIKTOK_UI_STATE_UNCERTAIN"
    assert overlaid.taps == []


def test_profile_classifier_tolerates_account_content_but_requires_core_signals() -> None:
    resolver = TikTokScreenResolver()
    assert resolver.classify(
        profile_hierarchy(account_variant=7), TRILL_44_4_3_PROFILE_V16,
        TRILL_44_4_3_PROFILE_V16.package_name,
    ) == TikTokScreen.PROFILE
    assert resolver.classify(
        profile_hierarchy(include_menu=False), TRILL_44_4_3_PROFILE_V16,
        TRILL_44_4_3_PROFILE_V16.package_name,
    ) == TikTokScreen.UNKNOWN


def test_open_caption_fails_closed_when_snapshot_changes_before_tap() -> None:
    session = FakeSession([
        editor_hierarchy(dynamic_variant=0),
        editor_hierarchy(dynamic_variant=1),
    ])
    with pytest.raises(TikTokActionError) as caught:
        action().open_caption(
            session, TRILL_44_4_3_EDITOR_ACTION_V6,
            expected_package=TRILL_44_4_3_EDITOR_ACTION_V6.package_name,
        )
    assert caught.value.code == "TIKTOK_UI_STATE_UNCERTAIN"
    assert session.taps == []


def test_open_caption_rejects_ambiguous_next_before_tap() -> None:
    session = FakeSession([editor_hierarchy(duplicate_next=True)])
    with pytest.raises(TikTokActionError) as caught:
        action().open_caption(
            session, TRILL_44_4_3_EDITOR_ACTION_V6,
            expected_package=TRILL_44_4_3_EDITOR_ACTION_V6.package_name,
        )
    assert caught.value.code == "TIKTOK_ELEMENT_AMBIGUOUS"
    assert session.taps == []


def test_open_caption_reaches_calibrated_ready_screen_once() -> None:
    editor = editor_hierarchy()
    session = FakeSession([editor, editor, ready_to_publish_hierarchy()])
    result = action().open_caption(
        session, TRILL_44_4_3_READY_V7,
        expected_package=TRILL_44_4_3_READY_V7.package_name,
    )
    assert result.screen_before == TikTokScreen.EDIT_MEDIA
    assert result.screen_after == TikTokScreen.READY_TO_PUBLISH
    assert result.changed is True and result.tap_dispatched is True
    assert result.calibration_required is False
    assert len(session.taps) == 1

    already = FakeSession([ready_to_publish_hierarchy()])
    result = action().open_caption(
        already, TRILL_44_4_3_READY_V7,
        expected_package=TRILL_44_4_3_READY_V7.package_name,
    )
    assert result.screen_before == TikTokScreen.READY_TO_PUBLISH
    assert result.changed is False and result.tap_dispatched is False
    assert result.resolution_method == "calibrated_postcondition"
    assert already.taps == []


def test_ready_screen_requires_core_publish_signals() -> None:
    resolver = TikTokScreenResolver()
    assert resolver.classify(
        ready_to_publish_hierarchy(), TRILL_44_4_3_READY_V7,
        TRILL_44_4_3_READY_V7.package_name,
    ) == TikTokScreen.READY_TO_PUBLISH
    assert resolver.classify(
        ready_to_publish_hierarchy(include_publish=False),
        TRILL_44_4_3_READY_V7, TRILL_44_4_3_READY_V7.package_name,
    ) == TikTokScreen.UNKNOWN
    selectors = {item.key: item for item in TRILL_44_4_3_READY_V7.selectors}
    assert selectors["publish_action"].actionable is False
    assert selectors["draft_action"].actionable is False


def test_set_caption_replaces_and_verifies_exact_value() -> None:
    before = ready_to_publish_hierarchy()
    after = ready_to_publish_hierarchy(caption="TIK-024 test caption")
    session = FakeSession(
        [before, before, after, after], keyboards=[True],
    )
    result = action().set_caption(
        session, TRILL_44_4_3_CAPTION_ACTION_V8,
        expected_package=TRILL_44_4_3_CAPTION_ACTION_V8.package_name,
        caption="  TIK-024   test caption  ",
    )
    assert result.screen_before == result.screen_after == TikTokScreen.READY_TO_PUBLISH
    assert result.changed is True and result.verification is True
    assert result.caption_length == 20
    assert result.keyboard_appeared is True
    assert len(session.focuses) == 1
    assert session.focuses[0].selector_key == "caption_input"
    assert session.replacements == [(len("Add description..."), "TIK-024 test caption")]
    assert session.back_count == 1
    assert session.taps == []


def test_set_caption_equal_is_idempotent_without_focus_or_typing() -> None:
    session = FakeSession(
        [ready_to_publish_hierarchy(caption="same")], keyboards=[False],
    )
    result = action().set_caption(
        session, TRILL_44_4_3_CAPTION_ACTION_V8,
        expected_package=TRILL_44_4_3_CAPTION_ACTION_V8.package_name,
        caption="same",
    )
    assert result.changed is False and result.verification is True
    assert result.keyboard_appeared is False
    assert session.focuses == [] and session.replacements == []


@pytest.mark.parametrize("caption", ("", "a" * 150))
def test_set_caption_accepts_empty_and_maximum_boundary(caption: str) -> None:
    before = ready_to_publish_hierarchy(caption="old")
    after = ready_to_publish_hierarchy(caption=caption)
    session = FakeSession([before, before, after, after], keyboards=[True])
    result = action().set_caption(
        session, TRILL_44_4_3_CAPTION_ACTION_V8,
        expected_package=TRILL_44_4_3_CAPTION_ACTION_V8.package_name,
        caption=caption,
    )
    assert result.caption_length == len(caption) and result.verification is True


@pytest.mark.parametrize("caption", ("a" * 151, "line\nbreak"))
def test_set_caption_rejects_unsupported_input_before_interaction(caption: str) -> None:
    session = FakeSession([ready_to_publish_hierarchy()])
    with pytest.raises(TikTokActionError) as caught:
        action().set_caption(
            session, TRILL_44_4_3_CAPTION_ACTION_V8,
            expected_package=TRILL_44_4_3_CAPTION_ACTION_V8.package_name,
            caption=caption,
        )
    assert caught.value.code == "TIKTOK_CAPTION_INVALID"
    assert session.focuses == [] and session.replacements == []


def test_caption_normalization_preserves_multilingual_hashtags_and_emoji() -> None:
    from app.services.tiktok_action_service import normalize_caption
    assert normalize_caption("  Xin   chào #ViệtNam 🌏✨  ") == (
        "Xin chào #ViệtNam 🌏✨"
    )


def test_set_caption_missing_or_ambiguous_field_fails_closed() -> None:
    missing = FakeSession([ready_to_publish_hierarchy(include_caption=False)])
    # Removing a required screen signal makes the whole state unrecognized.
    with pytest.raises(TikTokActionError):
        action().set_caption(
            missing, TRILL_44_4_3_CAPTION_ACTION_V8,
            expected_package=TRILL_44_4_3_CAPTION_ACTION_V8.package_name,
            caption="safe",
        )

    ambiguous = FakeSession([ready_to_publish_hierarchy(duplicate_caption=True)])
    with pytest.raises(TikTokActionError) as caught:
        action().set_caption(
            ambiguous, TRILL_44_4_3_CAPTION_ACTION_V8,
            expected_package=TRILL_44_4_3_CAPTION_ACTION_V8.package_name,
            caption="safe",
        )
    assert caught.value.code == "TIKTOK_ELEMENT_AMBIGUOUS"
    assert ambiguous.focuses == []


def test_set_caption_snapshot_change_and_verification_mismatch_fail_closed() -> None:
    before = ready_to_publish_hierarchy()
    changed = ready_to_publish_hierarchy(include_publish=False)
    stale = FakeSession([before, changed])
    with pytest.raises(TikTokActionError) as caught:
        action().set_caption(
            stale, TRILL_44_4_3_CAPTION_ACTION_V8,
            expected_package=TRILL_44_4_3_CAPTION_ACTION_V8.package_name,
            caption="safe",
        )
    assert caught.value.code == "TIKTOK_UI_STATE_UNCERTAIN"
    assert stale.focuses == []

    mismatch = FakeSession([before, before, before], keyboards=[True])
    with pytest.raises(TikTokActionError) as caught:
        action(timeout_seconds=0.1, monotonic=iter((0.0, 1.0)).__next__).set_caption(
            mismatch, TRILL_44_4_3_CAPTION_ACTION_V8,
            expected_package=TRILL_44_4_3_CAPTION_ACTION_V8.package_name,
            caption="safe",
        )
    assert caught.value.code == "TIKTOK_CAPTION_VERIFICATION_FAILED"
    assert len(mismatch.focuses) == 1
    assert mismatch.back_count == 0


def test_set_post_options_opens_privacy_once_and_stops_for_calibration() -> None:
    ready = ready_to_publish_hierarchy(caption="TIK-024 test caption")
    unknown_modal = parsed(node(
        resource="com.ss.android.ugc.trill:id/privacy-modal",
        klass="android.widget.FrameLayout", clickable="false",
    ))
    session = FakeSession([ready, ready, unknown_modal])
    dispatched = []
    result = action().set_post_options(
        session, TRILL_44_4_3_PRIVACY_ENTRY_V9,
        expected_package=TRILL_44_4_3_PRIVACY_ENTRY_V9.package_name,
        privacy=None, on_tap_dispatched=dispatched.append,
    )
    assert result.screen_before == TikTokScreen.READY_TO_PUBLISH
    assert result.screen_after == TikTokScreen.UNKNOWN
    assert result.changed is True and result.tap_dispatched is True
    assert result.calibration_required is True
    assert result.verification is False and result.privacy is None
    assert len(session.taps) == len(dispatched) == 1
    assert session.taps[0].selector_key == "privacy_entry_action"
    assert all(item.selector_key not in {"draft_action", "publish_action"} for item in session.taps)


def test_set_post_options_rejects_unsupported_or_ambiguous_before_tap() -> None:
    unsupported = FakeSession([ready_to_publish_hierarchy()])
    with pytest.raises(TikTokActionError) as caught:
        action().set_post_options(
            unsupported, TRILL_44_4_3_PRIVACY_ENTRY_V9,
            expected_package=TRILL_44_4_3_PRIVACY_ENTRY_V9.package_name,
            privacy="invented",
        )
    assert caught.value.code == "TIKTOK_OPTION_UNSUPPORTED"
    assert unsupported.taps == []

    ambiguous = FakeSession([ready_to_publish_hierarchy(duplicate_privacy=True)])
    with pytest.raises(TikTokActionError) as caught:
        action().set_post_options(
            ambiguous, TRILL_44_4_3_PRIVACY_ENTRY_V9,
            expected_package=TRILL_44_4_3_PRIVACY_ENTRY_V9.package_name,
            privacy=None,
        )
    assert caught.value.code == "TIKTOK_ELEMENT_AMBIGUOUS"
    assert ambiguous.taps == []


def test_set_post_options_fails_closed_on_pre_tap_state_change() -> None:
    ready = ready_to_publish_hierarchy()
    changed = ready_to_publish_hierarchy(include_publish=False)
    session = FakeSession([ready, changed])
    with pytest.raises(TikTokActionError) as caught:
        action().set_post_options(
            session, TRILL_44_4_3_PRIVACY_ENTRY_V9,
            expected_package=TRILL_44_4_3_PRIVACY_ENTRY_V9.package_name,
            privacy=None,
        )
    assert caught.value.code == "TIKTOK_UI_STATE_UNCERTAIN"
    assert session.taps == []


def test_privacy_modal_classification_and_supported_option_change() -> None:
    resolver = TikTokScreenResolver()
    everyone = privacy_modal_hierarchy(checked="everyone")
    only_you = privacy_modal_hierarchy(checked="only_you")
    assert resolver.classify(
        everyone, TRILL_44_4_3_PRIVACY_MODAL_V10,
        TRILL_44_4_3_PRIVACY_MODAL_V10.package_name,
    ) == TikTokScreen.POST_SETTINGS

    session = FakeSession([everyone, everyone, only_you])
    result = action().set_post_options(
        session, TRILL_44_4_3_PRIVACY_MODAL_V10,
        expected_package=TRILL_44_4_3_PRIVACY_MODAL_V10.package_name,
        privacy="only_you",
    )
    assert result.screen_before == result.screen_after == TikTokScreen.POST_SETTINGS
    assert result.changed is True and result.verification is True
    assert result.privacy == "only_you"
    assert len(session.taps) == 1
    assert session.taps[0].selector_key == "privacy_only_you"


def test_privacy_already_equal_is_idempotent_without_tap() -> None:
    modal = privacy_modal_hierarchy(checked="everyone")
    session = FakeSession([modal])
    result = action().set_post_options(
        session, TRILL_44_4_3_PRIVACY_MODAL_V10,
        expected_package=TRILL_44_4_3_PRIVACY_MODAL_V10.package_name,
        privacy="everyone",
    )
    assert result.changed is False and result.verification is True
    assert result.privacy == "everyone" and session.taps == []


def test_privacy_auto_close_verifies_exact_ready_summary() -> None:
    everyone = privacy_modal_hierarchy(checked="everyone")
    ready_only_you = ready_to_publish_hierarchy(
        caption="TIK-024 test caption", privacy="only_you",
    )
    session = FakeSession([everyone, everyone, ready_only_you])
    result = action().set_post_options(
        session, TRILL_44_4_3_PRIVACY_AUTOCLOSE_V11,
        expected_package=TRILL_44_4_3_PRIVACY_AUTOCLOSE_V11.package_name,
        privacy="only_you",
    )
    assert result.screen_before == TikTokScreen.POST_SETTINGS
    assert result.screen_after == TikTokScreen.READY_TO_PUBLISH
    assert result.changed is True and result.verification is True
    assert result.privacy == "only_you"
    assert [item.selector_key for item in session.taps] == ["privacy_only_you"]


def test_privacy_ambiguous_and_verification_mismatch_fail_closed() -> None:
    ambiguous = FakeSession([privacy_modal_hierarchy(duplicate_only_you=True)])
    with pytest.raises(TikTokActionError) as caught:
        action().set_post_options(
            ambiguous, TRILL_44_4_3_PRIVACY_MODAL_V10,
            expected_package=TRILL_44_4_3_PRIVACY_MODAL_V10.package_name,
            privacy="only_you",
        )
    assert caught.value.code == "TIKTOK_ELEMENT_AMBIGUOUS"
    assert ambiguous.taps == []

    everyone = privacy_modal_hierarchy(checked="everyone")
    mismatch = FakeSession([everyone, everyone, everyone])
    with pytest.raises(TikTokActionError) as caught:
        action(timeout_seconds=0.1, monotonic=iter((0.0, 1.0)).__next__).set_post_options(
            mismatch, TRILL_44_4_3_PRIVACY_MODAL_V10,
            expected_package=TRILL_44_4_3_PRIVACY_MODAL_V10.package_name,
            privacy="only_you",
        )
    assert caught.value.code == "TIKTOK_OPTION_VERIFICATION_FAILED"
    assert len(mismatch.taps) == 1
    assert mismatch.taps[0].selector_key == "privacy_only_you"


def test_prepare_publish_verifies_complete_state_without_mutation() -> None:
    ready = ready_to_publish_hierarchy(
        caption="TIK-024 test caption", privacy="everyone",
    )
    media = delivery_media()
    session = FakeSession(
        [ready, ready], inventories=[(media,), (media,)],
    )
    result = action().prepare_publish(
        session, TRILL_44_4_3_PRIVACY_AUTOCLOSE_V11,
        expected_package=TRILL_44_4_3_PRIVACY_AUTOCLOSE_V11.package_name,
        expected_media=media,
        expected_caption="TIK-024 test caption",
        expected_privacy="everyone",
    )
    assert result.screen == TikTokScreen.READY_TO_PUBLISH
    assert result.privacy == "everyone"
    assert result.media_resolution_method == "exact_mediastore_record"
    assert session.taps == [] and session.focuses == []
    assert session.replacements == [] and session.back_count == 0


@pytest.mark.parametrize(
    ("caption", "privacy", "code"),
    (
        ("different", "everyone", "TIKTOK_PREPARE_CAPTION_MISMATCH"),
        ("TIK-024 test caption", "only_you", "TIKTOK_PREPARE_PRIVACY_MISMATCH"),
    ),
)
def test_prepare_publish_rejects_caption_or_privacy_mismatch(
    caption: str, privacy: str, code: str,
) -> None:
    ready = ready_to_publish_hierarchy(
        caption="TIK-024 test caption", privacy="everyone",
    )
    session = FakeSession([ready], inventories=[(delivery_media(),)])
    with pytest.raises(TikTokActionError) as caught:
        action().prepare_publish(
            session, TRILL_44_4_3_PRIVACY_AUTOCLOSE_V11,
            expected_package=TRILL_44_4_3_PRIVACY_AUTOCLOSE_V11.package_name,
            expected_media=delivery_media(), expected_caption=caption,
            expected_privacy=privacy,
        )
    assert caught.value.code == code
    assert session.taps == [] and session.focuses == []


@pytest.mark.parametrize(
    "changes",
    (
        {"include_publish": False},
        {"duplicate_publish": True},
        {"include_drafts": False},
    ),
)
def test_prepare_publish_requires_unique_post_and_drafts(changes) -> None:
    ready = ready_to_publish_hierarchy(
        caption="TIK-024 test caption", **changes,
    )
    session = FakeSession([ready], inventories=[(delivery_media(),)])
    with pytest.raises(TikTokActionError):
        action().prepare_publish(
            session, TRILL_44_4_3_PRIVACY_AUTOCLOSE_V11,
            expected_package=TRILL_44_4_3_PRIVACY_AUTOCLOSE_V11.package_name,
            expected_media=delivery_media(),
            expected_caption="TIK-024 test caption",
            expected_privacy="everyone",
        )
    assert session.taps == [] and session.focuses == []


def test_prepare_publish_rejects_wrong_screen_overlay_and_media() -> None:
    cases = (
        FakeSession([editor_hierarchy()]),
        FakeSession(
            [permission_hierarchy()],
            packages=["com.android.permissioncontroller"],
        ),
        FakeSession(
            [ready_to_publish_hierarchy(caption="TIK-024 test caption")],
            inventories=[()],
        ),
    )
    for session in cases:
        with pytest.raises(TikTokActionError):
            action().prepare_publish(
                session, TRILL_44_4_3_PRIVACY_AUTOCLOSE_V11,
                expected_package=TRILL_44_4_3_PRIVACY_AUTOCLOSE_V11.package_name,
                expected_media=delivery_media(),
                expected_caption="TIK-024 test caption",
                expected_privacy="everyone",
            )
        assert session.taps == [] and session.focuses == []


def test_prepare_publish_rejects_hierarchy_change_without_mutation() -> None:
    first = ready_to_publish_hierarchy(caption="TIK-024 test caption")
    changed = ready_to_publish_hierarchy(
        caption="TIK-024 test caption", duplicate_caption=True,
    )
    media = delivery_media()
    session = FakeSession(
        [first, changed], inventories=[(media,), (media,)],
    )
    with pytest.raises(TikTokActionError) as caught:
        action().prepare_publish(
            session, TRILL_44_4_3_PRIVACY_AUTOCLOSE_V11,
            expected_package=TRILL_44_4_3_PRIVACY_AUTOCLOSE_V11.package_name,
            expected_media=media,
            expected_caption="TIK-024 test caption",
            expected_privacy="everyone",
        )
    assert caught.value.code == "TIKTOK_UI_STATE_UNCERTAIN"
    assert session.taps == [] and session.focuses == []

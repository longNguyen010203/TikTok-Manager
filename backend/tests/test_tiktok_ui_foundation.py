"""Focused safety tests for TIK-024 Android UI parsing and resolution."""

import subprocess
from types import SimpleNamespace
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database import init_db
from app.models import TikTokUiProfile
from app.services.adb_executor import AdbExecutor
from app.services.android_ui_hierarchy import UiHierarchyParser, UiParserLimits
from app.services.tiktok_errors import TikTokActionError, tiktok_error
from app.services.tiktok_action_service import normalize_caption
from app.services.tiktok_jobs import (
    TikTokJobValidationError, create_select_media_job, create_prepare_publish_job,
    get_tiktok_job_definition, validate_tiktok_job_payload,
)
from app.services.tiktok_screen_resolver import TikTokScreen, TikTokScreenResolver, TikTokSelectorResolver
from app.services.tiktok_ui_profiles import ScreenDefinition, StructuralConstraint, TikTokElementSelector, TikTokUiProfileDefinition, TikTokUiProfileRegistry, TRILL_44_4_3_HOME_V2, TRILL_44_4_3_TESTING


def node(*, resource="", text="", desc="", klass="android.view.View", bounds="[0,0][100,100]", password="false", clickable="true", children="") -> str:
    return (f'<node resource-id="{resource}" text="{text}" content-desc="{desc}" class="{klass}" '
            f'package="com.ss.android.ugc.trill" bounds="{bounds}" enabled="true" clickable="{clickable}" '
            f'focusable="true" focused="false" selected="false" checked="false" password="{password}">{children}</node>')


def hierarchy(*nodes: str):
    return UiHierarchyParser().parse(f'<?xml version="1.0"?><hierarchy>{"".join(nodes)}</hierarchy>')


def test_media_identity_failures_are_stable_and_non_retryable() -> None:
    missing = tiktok_error("TIKTOK_MEDIA_NOT_FOUND")
    ambiguous = tiktok_error("TIKTOK_MEDIA_AMBIGUOUS")
    assert missing.safe_message == "The delivered media is not visible in the app picker."
    assert ambiguous.safe_message == (
        "The delivered media cannot be identified uniquely in the app picker."
    )
    assert missing.retryable is False and ambiguous.retryable is False


def test_select_media_payload_is_ids_only_and_not_post_dispatch_retryable() -> None:
    payload = validate_tiktok_job_payload("tiktok.select_media", {
        "runtime_id": 17, "managed_app_id": 1, "ui_profile_id": 4,
        "content_delivery_id": 69,
    })
    assert payload["content_delivery_id"] == 69
    for unsafe in ("x", "y", "selector", "filename", "media_store_id", "adb"):
        with pytest.raises(TikTokJobValidationError):
            validate_tiktok_job_payload("tiktok.select_media", {
                **payload, unsafe: "caller-controlled",
            })
    definition = get_tiktok_job_definition("tiktok.select_media")
    assert definition is not None
    assert definition.allows_post_dispatch_retry is False
    assert definition.retryable_codes == frozenset()


def test_open_caption_payload_is_ids_only_and_never_post_dispatch_retryable() -> None:
    payload = validate_tiktok_job_payload("tiktok.open_caption", {
        "runtime_id": 17, "managed_app_id": 1, "ui_profile_id": 6,
    })
    for unsafe in ("x", "y", "selector", "text", "adb"):
        with pytest.raises(TikTokJobValidationError):
            validate_tiktok_job_payload(
                "tiktok.open_caption", {**payload, unsafe: "caller-controlled"}
            )
    definition = get_tiktok_job_definition("tiktok.open_caption")
    assert definition is not None
    assert definition.allows_post_dispatch_retry is False
    assert definition.retryable_codes == frozenset()


def test_set_caption_payload_is_typed_and_never_post_dispatch_retryable() -> None:
    payload = validate_tiktok_job_payload("tiktok.set_caption", {
        "runtime_id": 17, "managed_app_id": 1, "ui_profile_id": 8,
        "caption": "TIK-024 test caption",
    })
    assert normalize_caption("  TIK-024   test caption  ") == "TIK-024 test caption"
    for unsafe in ("x", "y", "selector", "package", "adb", "keyevent"):
        with pytest.raises(TikTokJobValidationError):
            validate_tiktok_job_payload(
                "tiktok.set_caption", {**payload, unsafe: "caller-controlled"}
            )
    definition = get_tiktok_job_definition("tiktok.set_caption")
    assert definition is not None
    assert definition.allows_post_dispatch_retry is False
    assert definition.retryable_codes == frozenset()


def test_set_post_options_payload_rejects_arbitrary_controls() -> None:
    payload = validate_tiktok_job_payload("tiktok.set_post_options", {
        "runtime_id": 17, "managed_app_id": 1, "ui_profile_id": 9,
        "privacy": None,
    })
    for unsafe in ("selector", "label", "x", "y", "adb", "post"):
        with pytest.raises(TikTokJobValidationError):
            validate_tiktok_job_payload(
                "tiktok.set_post_options", {**payload, unsafe: "unsafe"}
            )
    definition = get_tiktok_job_definition("tiktok.set_post_options")
    assert definition is not None
    assert definition.allows_post_dispatch_retry is False


def test_prepare_publish_payload_is_typed_read_only_and_safe_retryable() -> None:
    payload = validate_tiktok_job_payload("tiktok.prepare_publish", {
        "runtime_id": 17, "managed_app_id": 1, "ui_profile_id": 11,
        "content_delivery_id": 69,
        "expected_caption": "TIK-024 test caption",
        "expected_privacy": "everyone",
    })
    for unsafe in (
        "selector", "x", "y", "path", "package_name", "media_store_id",
        "adb", "tap", "post",
    ):
        with pytest.raises(TikTokJobValidationError):
            validate_tiktok_job_payload(
                "tiktok.prepare_publish", {**payload, unsafe: "unsafe"}
            )
    definition = get_tiktok_job_definition("tiktok.prepare_publish")
    assert definition is not None
    assert definition.allows_post_dispatch_retry is True


@pytest.mark.parametrize("privacy", ("everyone", "only_you"))
def test_set_post_options_job_preserves_supported_privacy_value(
    monkeypatch: pytest.MonkeyPatch, privacy: str,
) -> None:
    from app.services import tiktok_jobs

    captured = {}

    def fake_create(session, **kwargs):
        captured.update(kwargs)
        return object()

    monkeypatch.setattr(tiktok_jobs, "_create_tiktok_job", fake_create)
    tiktok_jobs.create_set_post_options_job(
        object(), runtime_id=17, managed_app_id=1, privacy=privacy,
    )
    assert captured["extra_payload"] == {"privacy": privacy}
    assert captured["max_attempts"] == 1


def test_adb_caption_helpers_use_fixed_typed_commands() -> None:
    calls = []
    def runner(command, **kwargs):
        calls.append((command, kwargs))
        output = b"mInputShown=true\nmIsInputViewShown=true\n" if "dumpsys" in command else b""
        return subprocess.CompletedProcess(command, 0, output, b"")
    adb = AdbExecutor(runner=runner)
    adb.clear_focused_text("localhost:5585", 3)
    assert adb.is_keyboard_visible("localhost:5585") is True
    assert calls[0][0] == [
        "adb", "-s", "localhost:5585", "shell", "input", "keyevent",
        "123", "67", "67", "67",
    ]
    assert calls[1][0] == [
        "adb", "-s", "localhost:5585", "shell", "dumpsys", "input_method",
    ]
    assert calls[0][1]["shell"] is False

    def hidden_runner(command, **kwargs):
        output = b"mInputShown=false\nmIsInputViewShown=true\n"
        return subprocess.CompletedProcess(command, 0, output, b"")
    assert AdbExecutor(runner=hidden_runner).is_keyboard_visible(
        "localhost:5585"
    ) is False


@pytest.mark.parametrize(
    ("changes", "valid"),
    (
        ({}, True),
        ({"runtime_id": 18}, False),
        ({"status": "failed"}, False),
        ({"import_media": False}, False),
        ({"media_uri": None}, False),
    ),
)
def test_select_media_job_creation_requires_exact_succeeded_imported_delivery(
    monkeypatch, changes, valid,
) -> None:
    delivery = SimpleNamespace(
        status="succeeded", runtime_id=17, runtime_id_snapshot=17,
        import_media=True, media_uri="content://media/external/file/20",
    )
    for key, value in changes.items():
        setattr(delivery, key, value)

    class FakeSession:
        def get(self, model, object_id):
            return delivery

    created = SimpleNamespace(payload={}, max_attempts=3)
    call = {}
    def fake_create(*args, **kwargs):
        call.update(kwargs)
        return created
    monkeypatch.setattr(
        "app.services.tiktok_jobs._create_tiktok_job",
        fake_create,
    )
    if valid:
        result = create_select_media_job(
            FakeSession(), runtime_id=17, managed_app_id=1,
            content_delivery_id=69,
        )
        assert result is created
        assert call["max_attempts"] == 1
        assert call["extra_payload"] == {"content_delivery_id": 69}
    else:
        with pytest.raises(TikTokActionError) as caught:
            create_select_media_job(
                FakeSession(), runtime_id=17, managed_app_id=1,
                content_delivery_id=69,
            )
        assert caught.value.code == "TIKTOK_MEDIA_DELIVERY_INVALID"


@pytest.mark.parametrize(
    ("changes", "valid"),
    (
        ({}, True),
        ({"runtime_id": 18}, False),
        ({"runtime_id_snapshot": 18}, False),
        ({"status": "failed"}, False),
        ({"import_media": False}, False),
        ({"media_uri": None}, False),
    ),
)
def test_prepare_publish_job_requires_exact_delivery_and_pins_expectations(
    monkeypatch, changes, valid,
) -> None:
    delivery = SimpleNamespace(
        status="succeeded", runtime_id=17, runtime_id_snapshot=17,
        import_media=True, media_uri="content://media/external/file/20",
    )
    for key, value in changes.items():
        setattr(delivery, key, value)

    class FakeSession:
        def get(self, model, object_id):
            return delivery

    created = SimpleNamespace(payload={}, max_attempts=3)
    call = {}

    def fake_create(*args, **kwargs):
        call.update(kwargs)
        return created

    monkeypatch.setattr("app.services.tiktok_jobs._create_tiktok_job", fake_create)
    if valid:
        result = create_prepare_publish_job(
            FakeSession(), runtime_id=17, managed_app_id=1,
            content_delivery_id=69,
            expected_caption="  TIK-024   test caption  ",
            expected_privacy="everyone",
        )
        assert result is created
        assert call["extra_payload"] == {
            "content_delivery_id": 69,
            "expected_caption": "TIK-024 test caption",
            "expected_privacy": "everyone",
        }
    else:
        with pytest.raises(TikTokActionError) as caught:
            create_prepare_publish_job(
                FakeSession(), runtime_id=17, managed_app_id=1,
                content_delivery_id=69,
                expected_caption="TIK-024 test caption",
                expected_privacy="everyone",
            )
        assert caught.value.code == "TIKTOK_MEDIA_DELIVERY_INVALID"


def test_parser_normalizes_tree_discards_password_and_redacts_fingerprint_text() -> None:
    first = hierarchy(node(resource="root", text="secret", password="true", children=node(resource="child", text="Home")))
    second = hierarchy(node(resource="root", text="different", password="true", children=node(resource="child", text="Other")))
    assert first.nodes[0].text == "" and first.nodes[0].child_indexes == (1,)
    assert first.nodes[1].parent_index == 0
    assert first.fingerprint == second.fingerprint


def test_parser_accepts_android_zero_area_system_node_but_rejects_reversed_bounds() -> None:
    parsed = hierarchy(node(resource="android:id/navigationBarBackground", bounds="[0,0][0,0]"))
    assert parsed.nodes[0].bounds.right == 0
    with pytest.raises(TikTokActionError):
        hierarchy(node(bounds="[10,10][9,20]"))


@pytest.mark.parametrize("payload", ["<hierarchy>", '<!DOCTYPE x [<!ENTITY y "z">]><hierarchy/>', f'<hierarchy>{node(bounds="bad")}</hierarchy>'])
def test_parser_rejects_malformed_unsafe_hierarchy(payload: str) -> None:
    with pytest.raises(TikTokActionError) as caught:
        UiHierarchyParser().parse(payload)
    assert caught.value.code == "TIKTOK_UI_DUMP_INVALID"


def test_parser_enforces_limits() -> None:
    with pytest.raises(TikTokActionError):
        UiHierarchyParser(UiParserLimits(max_xml_bytes=10)).parse(f"<hierarchy>{node()}</hierarchy>")
    with pytest.raises(TikTokActionError):
        UiHierarchyParser(UiParserLimits(max_nodes=1)).parse(f"<hierarchy>{node(children=node())}</hierarchy>")
    with pytest.raises(TikTokActionError):
        UiHierarchyParser(UiParserLimits(max_depth=1)).parse(f"<hierarchy>{node(children=node())}</hierarchy>")
    with pytest.raises(TikTokActionError):
        UiHierarchyParser(UiParserLimits(max_attribute_length=3)).parse(f"<hierarchy>{node(resource='long')}</hierarchy>")


def test_selector_priority_fallback_ambiguity_and_missing() -> None:
    parsed = hierarchy(node(resource="exact", text="Create", desc="Create"), node(resource="other", text="Create", desc="Other"))
    resolver = TikTokSelectorResolver()
    exact = resolver.resolve(parsed, TikTokElementSelector(key="create", resource_ids=("exact",), content_descriptions=("Other",), normalized_text=("Create",), actionable=True))
    assert exact.method == "resource_id"
    assert resolver.resolve(parsed, TikTokElementSelector(key="other", content_descriptions=("Other",))).method == "content_description"
    with pytest.raises(TikTokActionError) as ambiguous:
        resolver.resolve(parsed, TikTokElementSelector(key="create", normalized_text=("create",)))
    assert ambiguous.value.code == "TIKTOK_ELEMENT_AMBIGUOUS"
    with pytest.raises(TikTokActionError) as missing:
        resolver.resolve(parsed, TikTokElementSelector(key="missing", resource_ids=("missing",)))
    assert missing.value.code == "TIKTOK_ELEMENT_NOT_FOUND"

    with pytest.raises(TikTokActionError) as wrong_class:
        resolver.resolve(
            parsed,
            TikTokElementSelector(
                key="wrong-class", resource_ids=("exact",),
                class_names=("android.widget.Button",),
            ),
        )
    assert wrong_class.value.code == "TIKTOK_ELEMENT_NOT_FOUND"


def test_screen_presence_accepts_duplicates_but_action_resolution_remains_strict() -> None:
    parsed = hierarchy(node(desc="Signal"), node(desc="Signal"))
    selector = TikTokElementSelector(key="signal", content_descriptions=("Signal",))
    resolver = TikTokSelectorResolver()
    assert resolver.match_count(parsed, selector) == 2
    assert resolver.exists(parsed, selector) is True
    with pytest.raises(TikTokActionError) as ambiguous:
        resolver.resolve(parsed, selector)
    assert ambiguous.value.code == "TIKTOK_ELEMENT_AMBIGUOUS"


def test_structural_selector_and_screen_classification() -> None:
    parsed = hierarchy(node(klass="Parent", children=node(klass="Child", resource="home")), node(resource="nav"))
    selectors = (TikTokElementSelector(key="home", class_names=("Child",), structure=StructuralConstraint(ancestor_class_names=("Parent",))), TikTokElementSelector(key="nav", resource_ids=("nav",)))
    profile = TikTokUiProfileDefinition("test", "com.ss.android.ugc.trill", selectors, (ScreenDefinition("HOME", ("home", "nav"), minimum_score=4),))
    assert TikTokScreenResolver().classify(parsed, profile, profile.package_name) == TikTokScreen.HOME
    with pytest.raises(TikTokActionError) as wrong:
        TikTokScreenResolver().classify(parsed, profile, "com.example.other")
    assert wrong.value.code == "TIKTOK_APP_NOT_FOREGROUND"
    assert TikTokScreenResolver().classify(parsed, TRILL_44_4_3_TESTING, profile.package_name) == TikTokScreen.UNKNOWN


def test_sanitized_runtime17_home_fixture_classifies_and_create_is_unique() -> None:
    bottom_navigation = node(
        resource="com.ss.android.ugc.trill:id/n18",
        klass="android.widget.LinearLayout",
        bounds="[0,1100][720,1184]",
        clickable="false",
        children="".join((
            node(resource="com.ss.android.ugc.trill:id/n10", desc="Home", klass="android.widget.FrameLayout", bounds="[0,1100][144,1184]"),
            node(resource="com.ss.android.ugc.trill:id/n0z", desc="Friends", klass="android.widget.FrameLayout", bounds="[144,1100][288,1184]"),
            node(resource="com.ss.android.ugc.trill:id/n0x", desc="Create", klass="android.widget.Button", bounds="[288,1100][432,1184]"),
            node(resource="com.ss.android.ugc.trill:id/n11", desc="Inbox", klass="android.widget.FrameLayout", bounds="[432,1100][576,1184]"),
            node(resource="com.ss.android.ugc.trill:id/n12", desc="Profile", klass="android.widget.FrameLayout", bounds="[576,1100][720,1184]"),
        )),
    )
    parsed = hierarchy(
        node(desc="Following", klass="android.widget.FrameLayout", bounds="[192,48][375,164]", clickable="false"),
        node(desc="For You", klass="android.widget.LinearLayout", bounds="[375,48][528,164]", clickable="false"),
        bottom_navigation,
    )
    assert TRILL_44_4_3_HOME_V2.fingerprint == "a7b89eb91c4c7d03320c9edb41a577fdd77dcabab5b155cecdb30c815ee5c4ae"
    assert TikTokScreenResolver().classify(
        parsed, TRILL_44_4_3_HOME_V2, "com.ss.android.ugc.trill"
    ) == TikTokScreen.HOME
    create = next(item for item in TRILL_44_4_3_HOME_V2.selectors if item.key == "create_button")
    resolved = TikTokSelectorResolver().resolve(parsed, create)
    assert resolved.method == "resource_id"
    assert resolved.bounds.center == (360, 1142)
    assert resolved.actionable is True


def test_runtime17_shop_home_variant_does_not_fall_through_to_ambiguous_class_match() -> None:
    # Job 204 observed Shop in the second navigation slot instead of Friends,
    # plus many unrelated clickable FrameLayouts nested below LinearLayouts.
    unrelated = node(
        klass="android.widget.LinearLayout",
        children="".join(node(klass="android.widget.FrameLayout") for _ in range(3)),
    )
    bottom_navigation = node(
        resource="com.ss.android.ugc.trill:id/n18",
        klass="android.widget.LinearLayout",
        bounds="[0,1100][720,1184]",
        clickable="false",
        children="".join((
            node(resource="com.ss.android.ugc.trill:id/n10", desc="Home", klass="android.widget.FrameLayout", bounds="[0,1100][144,1184]"),
            node(resource="com.ss.android.ugc.trill:id/e2p", desc="Shop", klass="android.widget.FrameLayout", bounds="[144,1100][288,1184]"),
            node(resource="com.ss.android.ugc.trill:id/n0x", desc="Create", klass="android.widget.Button", bounds="[288,1100][432,1184]"),
            node(resource="com.ss.android.ugc.trill:id/n11", desc="Inbox", klass="android.widget.FrameLayout", bounds="[432,1100][576,1184]"),
            node(resource="com.ss.android.ugc.trill:id/n12", desc="Profile", klass="android.widget.FrameLayout", bounds="[576,1100][720,1184]"),
        )),
    )
    parsed = hierarchy(
        unrelated,
        node(desc="Following", klass="android.widget.FrameLayout", bounds="[337,48][483,164]", clickable="false"),
        node(desc="For You", klass="android.widget.LinearLayout", bounds="[483,48][608,164]", clickable="false"),
        bottom_navigation,
    )
    selectors = {item.key: item for item in TRILL_44_4_3_HOME_V2.selectors}
    resolver = TikTokSelectorResolver()
    assert resolver.match_count(parsed, selectors["friends_tab"]) == 0
    assert resolver.match_count(parsed, selectors["create_button"]) == 1
    assert resolver.resolve(parsed, selectors["create_button"]).method == "resource_id"
    assert TikTokScreenResolver(resolver).classify(
        parsed, TRILL_44_4_3_HOME_V2, "com.ss.android.ugc.trill"
    ) == TikTokScreen.HOME


def test_adb_ui_dump_uses_exact_serial_and_argument_array() -> None:
    calls = []
    def runner(command, **kwargs):
        calls.append(command)
        return subprocess.CompletedProcess(command, 0, b'notice\n<?xml version="1.0"?><hierarchy></hierarchy>UI hierarchy dumped', b"")
    xml = AdbExecutor(runner=runner).dump_ui_hierarchy("localhost:5555")
    assert xml.startswith("<?xml")
    assert xml.endswith("</hierarchy>")
    assert calls == [["adb", "-s", "localhost:5555", "exec-out", "uiautomator", "dump", "/dev/tty"]]


def test_adb_media_inventory_is_fixed_typed_and_normalized() -> None:
    calls = []
    output = (
        b"Row: 0 _id=20, _display_name=tik024-media-identity-d69.mp4, "
        b"_size=17308, mime_type=video/mp4, duration=2000, "
        b"relative_path=Download/TikTokManager/, bucket_display_name=TikTokManager\n"
    )
    def runner(command, **kwargs):
        calls.append(command)
        return subprocess.CompletedProcess(command, 0, output, b"")
    records = AdbExecutor(runner=runner).list_media_records("localhost:5555")
    assert len(records) == 1
    assert records[0].media_id == 20
    assert records[0].display_name == "tik024-media-identity-d69.mp4"
    assert records[0].size_bytes == 17308
    assert records[0].mime_type == "video/mp4"
    assert records[0].duration_ms == 2000
    assert records[0].relative_path == "Download/TikTokManager/"
    assert records[0].bucket_display_name == "TikTokManager"
    assert calls == [[
        "adb", "-s", "localhost:5555", "shell", "content", "query",
        "--uri", "content://media/external/file", "--projection",
        "_id:_display_name:_size:mime_type:duration:relative_path:bucket_display_name",
    ]]


def test_adb_foreground_window_uses_android12_service_dump() -> None:
    calls = []
    def runner(command, **kwargs):
        calls.append(command)
        output = b"mCurrentFocus=Window{abc u0 com.ss.android.ugc.trill/com.example.HomeActivity}"
        return subprocess.CompletedProcess(command, 0, output, b"")
    result = AdbExecutor(runner=runner).foreground_window("localhost:5555")
    assert result.package_name == "com.ss.android.ugc.trill"
    assert result.activity_name == "com.example.HomeActivity"
    assert calls[0] == ["adb", "-s", "localhost:5555", "shell", "dumpsys", "window"]


def test_profile_selection_is_version_bounded_retired_safe_and_fingerprint_pinned() -> None:
    engine = create_engine("sqlite:///:memory:")
    init_db(engine)
    with Session(engine) as session:
        row = TikTokUiProfile(
            key="trill-44-4-3", version=1, package_name=TRILL_44_4_3_TESTING.package_name,
            min_version_code=440403, max_version_code=440403,
            min_version_name="44.4.3", max_version_name="44.4.3", locale_assumption="en",
            profile_fingerprint=TRILL_44_4_3_TESTING.fingerprint,
            resource_key=TRILL_44_4_3_TESTING.resource_key, status="testing",
        )
        session.add(row); session.commit()
        selected, definition = TikTokUiProfileRegistry().select(
            session, package_name=row.package_name, version_code=440403
        )
        assert selected.id == row.id and definition.fingerprint == row.profile_fingerprint
        with pytest.raises(TikTokActionError) as mismatch:
            TikTokUiProfileRegistry().select(session, package_name=row.package_name, version_code=440404)
        assert mismatch.value.code == "TIKTOK_UI_PROFILE_MISMATCH"
        row.status = "retired"; session.commit()
        with pytest.raises(TikTokActionError) as retired:
            TikTokUiProfileRegistry().select(session, package_name=row.package_name, version_code=440403)
        assert retired.value.code == "TIKTOK_UI_PROFILE_NOT_FOUND"
    engine.dispose()

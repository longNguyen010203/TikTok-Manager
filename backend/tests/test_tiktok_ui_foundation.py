"""Focused safety tests for TIK-024 Android UI parsing and resolution."""

import subprocess
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database import init_db
from app.models import TikTokUiProfile
from app.services.adb_executor import AdbExecutor
from app.services.android_ui_hierarchy import UiHierarchyParser, UiParserLimits
from app.services.tiktok_errors import TikTokActionError
from app.services.tiktok_screen_resolver import TikTokScreen, TikTokScreenResolver, TikTokSelectorResolver
from app.services.tiktok_ui_profiles import ScreenDefinition, StructuralConstraint, TikTokElementSelector, TikTokUiProfileDefinition, TikTokUiProfileRegistry, TRILL_44_4_3_TESTING


def node(*, resource="", text="", desc="", klass="android.view.View", bounds="[0,0][100,100]", password="false", children="") -> str:
    return (f'<node resource-id="{resource}" text="{text}" content-desc="{desc}" class="{klass}" '
            f'package="com.ss.android.ugc.trill" bounds="{bounds}" enabled="true" clickable="true" '
            f'focusable="true" focused="false" selected="false" checked="false" password="{password}">{children}</node>')


def hierarchy(*nodes: str):
    return UiHierarchyParser().parse(f'<?xml version="1.0"?><hierarchy>{"".join(nodes)}</hierarchy>')


def test_parser_normalizes_tree_discards_password_and_redacts_fingerprint_text() -> None:
    first = hierarchy(node(resource="root", text="secret", password="true", children=node(resource="child", text="Home")))
    second = hierarchy(node(resource="root", text="different", password="true", children=node(resource="child", text="Other")))
    assert first.nodes[0].text == "" and first.nodes[0].child_indexes == (1,)
    assert first.nodes[1].parent_index == 0
    assert first.fingerprint == second.fingerprint


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


def test_structural_selector_and_screen_classification() -> None:
    parsed = hierarchy(node(klass="Parent", children=node(klass="Child", resource="home")), node(resource="nav"))
    selectors = (TikTokElementSelector(key="home", class_names=("Child",), structure=StructuralConstraint(ancestor_class_names=("Parent",))), TikTokElementSelector(key="nav", resource_ids=("nav",)))
    profile = TikTokUiProfileDefinition("test", "com.ss.android.ugc.trill", selectors, (ScreenDefinition("HOME", ("home", "nav"), minimum_score=4),))
    assert TikTokScreenResolver().classify(parsed, profile, profile.package_name) == TikTokScreen.HOME
    with pytest.raises(TikTokActionError) as wrong:
        TikTokScreenResolver().classify(parsed, profile, "com.example.other")
    assert wrong.value.code == "TIKTOK_APP_NOT_FOREGROUND"
    assert TikTokScreenResolver().classify(parsed, TRILL_44_4_3_TESTING, profile.package_name) == TikTokScreen.UNKNOWN


def test_adb_ui_dump_uses_exact_serial_and_argument_array() -> None:
    calls = []
    def runner(command, **kwargs):
        calls.append(command)
        return subprocess.CompletedProcess(command, 0, b'notice\n<?xml version="1.0"?><hierarchy/>', b"")
    assert AdbExecutor(runner=runner).dump_ui_hierarchy("localhost:5555").startswith("<?xml")
    assert calls == [["adb", "-s", "localhost:5555", "exec-out", "uiautomator", "dump", "/dev/tty"]]


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

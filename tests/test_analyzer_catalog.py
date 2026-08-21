from engine.analyzer_catalog import (
    ANALYZER_CATALOG,
    AUDIO_FORMATS,
    IMAGE_FORMATS,
    default_selected_for_profile,
    list_analyzer_catalog,
    normalize_selected_tools,
)
from engine.analyzers.tool_suite import (
    CAPABILITY_PROBE_IDS,
    DEDICATED_WORKFLOW_IDS,
    TOOL_SUITE_IDS,
)
from engine.decode_registry import OPTIONS


def test_light_recommends_only_simple_lsb_but_keeps_every_analyzer_clickable():
    rows = list_analyzer_catalog("light")
    by_id = {row["id"]: row for row in rows}

    assert default_selected_for_profile("light") == ["simple_lsb"]
    assert all(row["enabled_in_profile"] for row in rows)
    assert by_id["simple_lsb"]["recommended_in_profile"] is True
    assert by_id["simple_zlib"]["recommended_in_profile"] is False
    assert by_id["stegcracker"]["recommended_in_profile"] is False


def test_catalog_exposes_planes_decode_methods_and_individual_suite_tools():
    expected_planes = {
        "simple_rgb",
        "red_plane",
        "green_plane",
        "blue_plane",
        "alpha_plane",
    }

    assert expected_planes <= set(ANALYZER_CATALOG)
    assert set(OPTIONS) <= set(ANALYZER_CATALOG)
    assert TOOL_SUITE_IDS <= set(ANALYZER_CATALOG)
    assert "tool_suite" not in ANALYZER_CATALOG
    assert "decode_options" not in ANALYZER_CATALOG


def test_catalog_rows_have_help_and_grouping_metadata():
    for row in list_analyzer_catalog("quick"):
        assert row["description"]
        assert row["category"]
        assert row["applicability"]
        assert row["operation"]

    by_id = {row["id"]: row for row in list_analyzer_catalog("quick")}
    assert by_id["audio_lsb"]["applicability"] == list(AUDIO_FORMATS)
    assert by_id["audio_spectrogram"]["applicability"] == list(AUDIO_FORMATS)
    assert by_id["simple_lsb"]["applicability"] == list(IMAGE_FORMATS)
    assert by_id["red_plane"]["applicability"] == list(IMAGE_FORMATS)
    assert by_id["stegcracker"]["applicability"] == ["image/jpeg"]
    assert by_id["simple_lsb"]["operation"] == "decode"
    assert by_id["statistical_steg"]["operation"] == "inspect"
    assert by_id["stegcracker"]["operation"] == "carrier cli"
    assert by_id["fcrackzip"]["operation"] == "carrier cli"
    for analyzer_id in CAPABILITY_PROBE_IDS | DEDICATED_WORKFLOW_IDS:
        assert by_id[analyzer_id]["operation"] == "capability probe"
    assert all("any" not in row["applicability"] for row in by_id.values())


def test_legacy_group_ids_remain_accepted_without_being_user_facing():
    selected = normalize_selected_tools(
        ["decode_options", "tool_suite", "stegcracker", "unknown"]
    )
    assert selected == {"decode_options", "tool_suite", "stegcracker"}

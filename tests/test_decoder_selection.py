from pathlib import Path

import engine.decoder as decoder
from engine.analyzer_catalog import ANALYZER_CATALOG
from engine.analysis_profiles import resolve_profile
from engine.analyzers.tool_suite import TOOL_SUITE_IDS
from engine.decode_registry import OPTIONS
from engine.decoder import _build_analyzer_plan, run_analysis
from engine.analyzers.utils import update_data


FIXTURES = Path(__file__).resolve().parent / "fixtures"


def _plan(selected_tools, *, password=None):
    return _build_analyzer_plan(
        Path("carrier.jpg"),
        Path("results"),
        profile=resolve_profile("light"),
        password=password,
        binwalk_extract=False,
        invisible_unicode=False,
        unicode_tier1=False,
        unicode_separators=False,
        unicode_aggressiveness="balanced",
        selected_tools=set(selected_tools),
    )


def test_light_profile_can_run_only_an_explicit_suite_tool():
    plan = _plan({"stegcracker"})

    assert [task[0] for task in plan] == ["tool_suite"]
    assert plan[0][3]["selected_tools"] == {"stegcracker"}


def test_channel_cipher_receives_the_user_password():
    plan = _plan({"channel_cipher"}, password="black-heart")

    assert [task[0] for task in plan] == ["channel_cipher"]
    assert plan[0][2][2] == "black-heart"


def test_explicit_invisible_unicode_selection_enables_the_scan():
    plan = _plan({"invisible_unicode"})

    assert [task[0] for task in plan] == ["invisible_unicode"]
    assert plan[0][2][2] is True


def test_explicit_statistical_steg_selection_enables_its_full_pass():
    plan = _plan({"statistical_steg"})

    assert [task[0] for task in plan] == ["statistical_steg"]
    assert plan[0][2][2] is True


def test_every_catalog_checkbox_has_an_execution_path(monkeypatch):
    monkeypatch.setattr(
        decoder,
        "get_tool_status",
        lambda: {"outguess": {"available": True}},
    )
    selected = set(ANALYZER_CATALOG)
    plan = _plan(selected)
    direct_ids = {task[0] for task in plan if task[0] != "tool_suite"}
    suite_ids = set()
    for task in plan:
        if task[0] == "tool_suite":
            suite_ids.update(task[3]["selected_tools"])

    plane_ids = {"simple_rgb", "red_plane", "green_plane", "blue_plane", "alpha_plane"}
    decode_ids = set(OPTIONS)
    covered = direct_ids | suite_ids | plane_ids | decode_ids

    assert set(ANALYZER_CATALOG) <= covered
    assert TOOL_SUITE_IDS <= suite_ids


def test_missing_selection_uses_only_the_light_profile_suggestion():
    result = run_analysis(
        (FIXTURES / "lsb.png").read_bytes(),
        "lsb.png",
        analysis_profile="light",
    )

    assert result["meta"]["profile"] == "light"
    assert result["meta"]["selected_tools"] == ["simple_lsb"]
    assert set(result["results"]) == {"simple_lsb"}


def test_explicit_plane_selection_runs_shared_extraction_and_returns_only_that_plane():
    result = run_analysis(
        (FIXTURES / "lsb.png").read_bytes(),
        "lsb.png",
        analysis_profile="light",
        selected_tools=["red_plane"],
    )

    assert result["meta"]["selected_tools"] == ["red_plane"]
    assert set(result["results"]) == {"red_plane"}


def test_individual_decode_method_runs_without_the_legacy_group():
    result = run_analysis(
        (FIXTURES / "png_chunks.png").read_bytes(),
        "png_chunks.png",
        analysis_profile="light",
        selected_tools=["png_chunks"],
    )

    assert set(result["results"]) == {"png_chunks"}
    assert result["results"]["png_chunks"]["status"] == "ok"


def test_password_decode_method_is_not_gated_by_light_profile():
    result = run_analysis(
        (FIXTURES / "spread.png").read_bytes(),
        "spread.png",
        password="twitterpainted",
        analysis_profile="light",
        selected_tools=["spread_spectrum"],
    )

    assert set(result["results"]) == {"spread_spectrum"}
    assert "SPREAD_OK" in result["results"]["spread_spectrum"]["details"]["preview"]


def test_result_consumers_run_after_their_producers(monkeypatch):
    events = []

    def fake_plan(*_args, **_kwargs):
        def record(name):
            return lambda *_args, **_kwargs: events.append(name)

        return [
            ("randomizer_decode", record("randomizer_decode"), (), {}),
            ("invisible_unicode_decode", record("invisible_unicode_decode"), (), {}),
            ("simple_lsb", record("simple_lsb"), (), {}),
            ("invisible_unicode", record("invisible_unicode"), (), {}),
        ]

    monkeypatch.setattr(decoder, "_build_analyzer_plan", fake_plan)

    run_analysis(
        (FIXTURES / "lsb.png").read_bytes(),
        "lsb.png",
        analysis_profile="light",
        selected_tools=[
            "simple_lsb",
            "randomizer_decode",
            "invisible_unicode",
            "invisible_unicode_decode",
        ],
    )

    assert events == [
        "simple_lsb",
        "randomizer_decode",
        "invisible_unicode",
        "invisible_unicode_decode",
    ]


def test_analyzer_exception_returns_a_visible_timed_error(monkeypatch):
    def fake_plan(*_args, **_kwargs):
        def explode():
            raise RuntimeError("boom")

        return [("simple_lsb", explode, (), {})]

    monkeypatch.setattr(decoder, "_build_analyzer_plan", fake_plan)
    result = run_analysis(
        (FIXTURES / "lsb.png").read_bytes(),
        "lsb.png",
        analysis_profile="light",
        selected_tools=["simple_lsb"],
    )

    payload = result["results"]["simple_lsb"]
    timing = result["meta"]["analyzer_timing"]["simple_lsb"]
    assert payload["status"] == "error"
    assert "boom" in payload["error"]
    assert timing["status"] == "error"
    assert payload["timing_ms"] == timing["timing_ms"]


def test_missing_direct_analyzer_result_is_backfilled_as_error(monkeypatch):
    monkeypatch.setattr(
        decoder,
        "_build_analyzer_plan",
        lambda *_args, **_kwargs: [("simple_lsb", lambda: None, (), {})],
    )
    result = run_analysis(
        (FIXTURES / "lsb.png").read_bytes(),
        "lsb.png",
        analysis_profile="light",
        selected_tools=["simple_lsb"],
    )

    payload = result["results"]["simple_lsb"]
    timing = result["meta"]["analyzer_timing"]["simple_lsb"]
    assert payload["status"] == "error"
    assert "without producing a result" in payload["error"]
    assert timing["status"] == "error"


def test_analyzer_timing_uses_the_actual_result_status(monkeypatch):
    def fake_plan(_image_path, output_dir, **_kwargs):
        def skip():
            update_data(output_dir, {"simple_lsb": {"status": "skipped", "reason": "fixture"}})

        return [("simple_lsb", skip, (), {})]

    monkeypatch.setattr(decoder, "_build_analyzer_plan", fake_plan)
    result = run_analysis(
        (FIXTURES / "lsb.png").read_bytes(),
        "lsb.png",
        analysis_profile="light",
        selected_tools=["simple_lsb"],
    )

    payload = result["results"]["simple_lsb"]
    timing = result["meta"]["analyzer_timing"]["simple_lsb"]
    assert payload["status"] == "skipped"
    assert timing["status"] == "skipped"
    assert payload["timing_ms"] == timing["timing_ms"]

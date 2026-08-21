import json
import subprocess
from pathlib import Path

import engine.analyzers.research_steganalysis as research
from engine.analyzer_catalog import ANALYZER_CATALOG, list_analyzer_catalog
from engine.analysis_profiles import resolve_profile
from engine.analyzers.research_steganalysis import RESEARCH_ANALYZER_IDS
from engine.decoder import _build_analyzer_plan, _collect_artifacts


FIXTURES = Path(__file__).resolve().parent / "fixtures"


def _result(output_dir: Path, analyzer_id: str):
    payload = json.loads((output_dir / "results.json").read_text(encoding="utf-8"))
    return payload[analyzer_id]


def _plan(selected_tools):
    return _build_analyzer_plan(
        Path("carrier.jpg"),
        Path("results"),
        profile=resolve_profile("light"),
        password=None,
        binwalk_extract=False,
        invisible_unicode=False,
        unicode_tier1=False,
        unicode_separators=False,
        unicode_aggressiveness="balanced",
        selected_tools=set(selected_tools),
    )


def test_research_backends_are_catalogued_with_real_execution_paths():
    assert RESEARCH_ANALYZER_IDS <= set(ANALYZER_CATALOG)
    assert {task[0] for task in _plan(RESEARCH_ANALYZER_IDS)} == RESEARCH_ANALYZER_IDS

    rows = {row["id"]: row for row in list_analyzer_catalog("light")}
    for analyzer_id in RESEARCH_ANALYZER_IDS:
        row = rows[analyzer_id]
        assert row["recommended_in_profile"] is False
        assert row["enabled_in_profile"] is True
        assert row["category"] == "learned and research steganalysis"
        assert row["source_url"].startswith("https://")
        assert row["license"]
        assert row["license_url"].startswith("https://")
        assert row["requirements"]

    assert rows["xunet"]["applicability"] == ["image/jpeg"]
    assert rows["dctr"]["operation"] == "feature extraction"
    assert rows["srnet"]["operation"] == "model inference"


def test_missing_aletheia_reports_readiness_instead_of_fake_success(tmp_path, monkeypatch):
    monkeypatch.setattr(research, "_aletheia_command", lambda: None)

    research.analyze_aletheia(FIXTURES / "lsb.png", tmp_path)

    result = _result(tmp_path, "aletheia")
    assert result["status"] == "skipped"
    assert "not configured" in result["summary"]
    assert "does not prefetch" in result["reason"]
    assert "backend may" in result["reason"]
    assert result["provenance"]["source_url"].endswith("daniellerch/aletheia")


def test_aletheia_auto_requires_a_per_carrier_result_line(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(research, "_aletheia_command", lambda: ["/opt/aletheia.py"])

    def fake_run(command):
        calls.append(command)
        return (
            subprocess.CompletedProcess(
                command,
                0,
                stdout="lsb.png  0.0 (0.9)  [0.8] (0.7)\n",
                stderr="",
            ),
            None,
        )

    monkeypatch.setattr(research, "_run", fake_run)

    research.analyze_aletheia(FIXTURES / "lsb.png", tmp_path)

    result = _result(tmp_path, "aletheia")
    assert result["status"] == "ok"
    assert calls[0][1] == "auto"
    assert result["details"]["result_lines"] == 1


def test_dctr_only_succeeds_when_a_real_feature_vector_is_created(tmp_path, monkeypatch):
    monkeypatch.setattr(research, "_aletheia_command", lambda: ["/opt/aletheia.py"])

    def fake_run(command):
        Path(command[-1]).write_text("1.0 2.0 3.0 4.0\n", encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, stdout="", stderr=""), None

    monkeypatch.setattr(research, "_run", fake_run)

    research.analyze_dctr(FIXTURES / "dct.jpg", tmp_path)

    result = _result(tmp_path, "dctr")
    assert result["status"] == "ok"
    assert result["details"]["feature_count"] == 4
    assert len(result["details"]["sha256"]) == 64
    assert "classifier is still required" in result["summary"]
    assert result["details"]["artifact"] == "dctr.features.zip"
    artifacts = _collect_artifacts(tmp_path)
    assert [item["name"] for item in artifacts["archives"]] == ["dctr.features.zip"]
    assert artifacts["archives"][0]["data_url"].startswith("data:application/zip;base64,")


def test_json_model_runner_rejects_unvalidated_stdout(tmp_path, monkeypatch):
    runner = tmp_path / "runner.py"
    runner.write_text("# configured test runner\n", encoding="utf-8")
    model = tmp_path / "sia.ckpt"
    model.write_bytes(b"checkpoint")
    monkeypatch.setenv("TWITTERPAINTED_SIASTEGNET_RUNNER", str(runner))
    monkeypatch.setenv("TWITTERPAINTED_SIASTEGNET_MODEL", str(model))
    monkeypatch.setattr(
        research,
        "_run",
        lambda command: (
            subprocess.CompletedProcess(command, 0, stdout="looks suspicious", stderr=""),
            None,
        ),
    )

    research.analyze_siastegnet(FIXTURES / "lsb.png", tmp_path)

    result = _result(tmp_path, "siastegnet")
    assert result["status"] == "error"
    assert "validated stego probability" in result["summary"]


def test_json_model_runner_accepts_bounded_probability(tmp_path, monkeypatch):
    runner = tmp_path / "runner.py"
    runner.write_text("# configured test runner\n", encoding="utf-8")
    model = tmp_path / "sia.ckpt"
    model.write_bytes(b"checkpoint")
    monkeypatch.setenv("TWITTERPAINTED_SIASTEGNET_RUNNER", str(runner))
    monkeypatch.setenv("TWITTERPAINTED_SIASTEGNET_MODEL", str(model))

    calls = []

    def fake_run(command):
        calls.append(command)
        return (
            subprocess.CompletedProcess(
                command,
                0,
                stdout='{"stego_probability": 0.625, "backend": "kenet"}\n',
                stderr="",
            ),
            None,
        )

    monkeypatch.setattr(research, "_run", fake_run)

    research.analyze_siastegnet(FIXTURES / "lsb.png", tmp_path)

    result = _result(tmp_path, "siastegnet")
    assert result["status"] == "ok"
    assert result["confidence"] == 0.625
    assert result["details"]["runner_protocol"] == "twitterpainted-json-v1"
    assert calls[0][-1] == "--json"


def test_maxsrmd2_explains_required_side_information(tmp_path, monkeypatch):
    monkeypatch.delenv("TWITTERPAINTED_MAXSRMD2_RUNNER", raising=False)
    monkeypatch.delenv("TWITTERPAINTED_MAXSRMD2_SELECTION_MAP", raising=False)

    research.analyze_maxsrmd2(FIXTURES / "lsb.png", tmp_path)

    result = _result(tmp_path, "maxsrmd2")
    assert result["status"] == "skipped"
    assert "image alone is insufficient" in result["reason"]
    assert "no redistributable upstream license" in result["provenance"]["license"]


def test_stegspy_is_not_bundled_past_upstream_download_terms(tmp_path, monkeypatch):
    monkeypatch.setattr(research, "_resolve_command", lambda *_args, **_kwargs: None)

    research.analyze_stegspy(FIXTURES / "lsb.png", tmp_path)

    result = _result(tmp_path, "stegspy")
    assert result["status"] == "skipped"
    assert "does not bundle it" in result["reason"]
    assert "copyrighted" in result["provenance"]["license"]

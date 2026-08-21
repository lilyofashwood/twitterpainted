import json
from pathlib import Path
from types import SimpleNamespace

from engine.analyzers import tool_suite


def test_explicit_stegcracker_selection_runs_valid_command_and_reports_empty(tmp_path, monkeypatch):
    image_path = tmp_path / "carrier.jpg"
    image_path.write_bytes(b"jpeg")
    output_dir = tmp_path / "results"
    calls = []

    monkeypatch.setattr(tool_suite, "_detect_mime", lambda _path: "image/jpeg")
    monkeypatch.setattr(tool_suite.shutil, "which", lambda command: f"/usr/bin/{command}")

    def fake_run(command, **_kwargs):
        calls.append(command)
        return SimpleNamespace(returncode=1, stdout="", stderr="")

    monkeypatch.setattr(tool_suite.subprocess, "run", fake_run)

    tool_suite.analyze_tool_suite(
        image_path,
        output_dir,
        selected_tools={"stegcracker"},
    )

    assert calls == [
        [
            "stegcracker",
            str(image_path),
            str(tool_suite.STEGBREAK_WORDLIST),
            "-o",
            str(output_dir / "tool_suite" / "stegcracker.out"),
            "-q",
        ]
    ]
    results = json.loads((output_dir / "results.json").read_text())
    assert set(results) == {"stegcracker"}
    assert results["stegcracker"]["status"] == "empty"


def test_stegcracker_failure_never_appears_ok(tmp_path, monkeypatch):
    image_path = tmp_path / "carrier.jpg"
    image_path.write_bytes(b"jpeg")
    output_dir = tmp_path / "results"

    monkeypatch.setattr(tool_suite, "_detect_mime", lambda _path: "image/jpeg")
    monkeypatch.setattr(tool_suite.shutil, "which", lambda command: f"/usr/bin/{command}")
    monkeypatch.setattr(
        tool_suite.subprocess,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(
            returncode=2,
            stdout="",
            stderr="Error: invalid carrier",
        ),
    )

    tool_suite.analyze_tool_suite(
        image_path,
        output_dir,
        selected_tools={"stegcracker"},
    )

    result = json.loads((output_dir / "results.json").read_text())["stegcracker"]
    assert result["status"] == "error"
    assert "invalid carrier" in result["error"]


def _run_selected_fcrackzip(tmp_path, monkeypatch, completed_process):
    archive = tmp_path / "carrier.bin"
    archive.write_bytes(b"PK\x03\x04fixture")
    output_dir = tmp_path / "results"
    calls = []

    monkeypatch.setattr(tool_suite, "_detect_mime", lambda _path: "application/octet-stream")
    monkeypatch.setattr(tool_suite.shutil, "which", lambda command: f"/usr/bin/{command}")

    def fake_run(command, **kwargs):
        calls.append((command, kwargs))
        return completed_process

    monkeypatch.setattr(tool_suite.subprocess, "run", fake_run)
    tool_suite.analyze_tool_suite(archive, output_dir, selected_tools={"fcrackzip"})

    results = json.loads((output_dir / "results.json").read_text())
    return archive, output_dir, calls, results["fcrackzip"]


def test_fcrackzip_signature_runs_bundled_dictionary_and_reports_match(tmp_path, monkeypatch):
    archive, output_dir, calls, result = _run_selected_fcrackzip(
        tmp_path,
        monkeypatch,
        SimpleNamespace(
            returncode=0,
            stdout="PASSWORD FOUND!!!!: pw == password\n",
            stderr="",
        ),
    )

    wordlist = output_dir / "tool_suite" / "zip-words.txt"
    assert wordlist.read_bytes() == tool_suite.STEGBREAK_WORDLIST.read_bytes()
    assert calls[0][0] == [
        "fcrackzip",
        "-D",
        "-p",
        "zip-words.txt",
        "-u",
        str(archive),
    ]
    assert calls[0][1]["cwd"] == str(output_dir / "tool_suite")
    assert result["status"] == "ok"
    assert "pw == password" in result["output"][0]


def test_fcrackzip_markerless_success_is_an_empty_search(tmp_path, monkeypatch):
    _archive, _output_dir, _calls, result = _run_selected_fcrackzip(
        tmp_path,
        monkeypatch,
        SimpleNamespace(returncode=0, stdout="", stderr=""),
    )

    assert result["status"] == "empty"
    assert "No ZIP password matched" in result["reason"]


def test_fcrackzip_failure_never_appears_ok(tmp_path, monkeypatch):
    _archive, _output_dir, _calls, result = _run_selected_fcrackzip(
        tmp_path,
        monkeypatch,
        SimpleNamespace(returncode=2, stdout="", stderr="fatal dictionary error"),
    )

    assert result["status"] == "error"
    assert "fatal dictionary error" in result["error"]


def test_fcrackzip_skips_non_zip_without_launching_command(tmp_path, monkeypatch):
    carrier = tmp_path / "carrier.bin"
    carrier.write_bytes(b"not a zip")
    output_dir = tmp_path / "results"

    monkeypatch.setattr(tool_suite, "_detect_mime", lambda _path: "application/octet-stream")

    def unexpected_run(*_args, **_kwargs):
        raise AssertionError("fcrackzip should not run for a non-ZIP upload")

    monkeypatch.setattr(tool_suite.subprocess, "run", unexpected_run)
    tool_suite.analyze_tool_suite(carrier, output_dir, selected_tools={"fcrackzip"})

    result = json.loads((output_dir / "results.json").read_text())["fcrackzip"]
    assert result == {"status": "skipped", "reason": "Not a ZIP archive"}


def test_probe_constant_and_volatility_dedicated_workflow_are_explicit(tmp_path, monkeypatch):
    assert len(tool_suite.CAPABILITY_PROBE_IDS) == 29
    assert "qrencode" in tool_suite.CAPABILITY_PROBE_IDS
    assert "fcrackzip" not in tool_suite.CAPABILITY_PROBE_IDS
    assert tool_suite.DEDICATED_WORKFLOW_IDS == frozenset({"volatility"})

    carrier = tmp_path / "memory.raw"
    carrier.write_bytes(b"memory")
    output_dir = tmp_path / "results"
    monkeypatch.setattr(tool_suite, "_detect_mime", lambda _path: "application/octet-stream")
    tool_suite.analyze_tool_suite(carrier, output_dir, selected_tools={"volatility"})

    result = json.loads((output_dir / "results.json").read_text())["volatility"]
    assert result == {"status": "skipped", "reason": "Requires a memory image"}

import json
from pathlib import Path

from engine.analyzers.outguess import analyze_outguess
from engine.analyzers.zsteg import analyze_zsteg


FIXTURES = Path(__file__).resolve().parent / "fixtures"


def _result(output_dir: Path, analyzer_id: str):
    payload = json.loads((output_dir / "results.json").read_text(encoding="utf-8"))
    return payload[analyzer_id]


def test_zsteg_skips_jpeg_without_launching_the_png_bmp_tool(tmp_path):
    analyze_zsteg(FIXTURES / "dct.jpg", tmp_path)

    result = _result(tmp_path, "zsteg")
    assert result["status"] == "skipped"
    assert "PNG/BMP" in result["reason"]


def test_outguess_skips_png_without_launching_the_jpeg_pnm_tool(tmp_path):
    analyze_outguess(FIXTURES / "lsb.png", tmp_path)

    result = _result(tmp_path, "outguess")
    assert result["status"] == "skipped"
    assert "JPEG/PNM" in result["reason"]

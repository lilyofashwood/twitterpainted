from io import BytesIO
import json
from pathlib import Path

import numpy as np
from PIL import Image

from engine.analyzers.homoglyph import analyze_homoglyph
from engine.analyzers.whitespace_steg import analyze_whitespace_steg
from engine.analyzers.zero_width import analyze_zero_width
from engine.encoder import encode_payload


def _cover() -> bytes:
    rng = np.random.default_rng(42)
    pixels = rng.integers(0, 256, size=(128, 128, 3), dtype=np.uint8)
    buffer = BytesIO()
    Image.fromarray(pixels).save(buffer, format="PNG")
    return buffer.getvalue()


def _bits(payload: bytes) -> str:
    return "".join(f"{byte:08b}" for byte in payload)


def _analyze(tmp_path: Path, analyzer_id: str, analyzer, text: str):
    _, encoded = encode_payload(_cover(), text=text)
    carrier = tmp_path / f"{analyzer_id}.png"
    carrier.write_bytes(encoded)
    analyzer(carrier, tmp_path)
    results = json.loads((tmp_path / "results.json").read_text(encoding="utf-8"))
    return results[analyzer_id]


def test_zero_width_payload_round_trip(tmp_path):
    bit_text = "".join("\u200b" if bit == "0" else "\u200c" for bit in _bits(b"secret"))
    result = _analyze(tmp_path, "zero_width", analyze_zero_width, f"\u200d{bit_text}\u200d")

    assert result["status"] == "ok"
    assert result["output"][0]["payload"] == "secret"


def test_homoglyph_payload_round_trip_stops_at_carrier_terminator(tmp_path):
    text = "".join("a" if bit == "0" else "\u0430" for bit in _bits(b"secret"))
    result = _analyze(tmp_path, "homoglyph", analyze_homoglyph, text)

    assert result["status"] == "ok"
    assert result["output"][0]["method"] == "full-bitstream"
    assert result["output"][0]["payload"] == "secret"


def test_whitespace_payload_round_trip_preserves_final_bit(tmp_path):
    text = "\n".join("x" + (" " if bit == "0" else "\t") for bit in _bits(b"secret"))
    result = _analyze(tmp_path, "whitespace_steg", analyze_whitespace_steg, text)

    assert result["status"] == "ok"
    assert result["output"][0]["decoded"] == "secret"

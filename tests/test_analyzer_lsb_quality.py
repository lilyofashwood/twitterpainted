from io import BytesIO
import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image

from engine.analyzers.advanced_lsb import analyze_advanced_lsb
from engine.analyzers.simple_lsb import analyze_simple_lsb
from engine.encoder import encode_multi_channel, encode_payload


FIXTURES = Path(__file__).resolve().parent / "fixtures"


def _cover(size: int = 128) -> bytes:
    rng = np.random.default_rng(2026)
    pixels = rng.integers(0, 256, size=(size, size, 3), dtype=np.uint8)
    buffer = BytesIO()
    Image.fromarray(pixels).save(buffer, format="PNG")
    return buffer.getvalue()


def _result(output_dir: Path, analyzer_id: str):
    payload = json.loads((output_dir / "results.json").read_text(encoding="utf-8"))
    return payload[analyzer_id]


def test_simple_lsb_recovers_unicode_text(tmp_path):
    _, encoded = encode_payload(_cover(), text="love survives 🖤")
    carrier = tmp_path / "simple.png"
    carrier.write_bytes(encoded)

    analyze_simple_lsb(carrier, tmp_path)

    assert _result(tmp_path, "simple_lsb")["decoded_text"]["RGB"] == "love survives 🖤"


def test_simple_lsb_rejects_random_carrier_bytes(tmp_path):
    carrier = tmp_path / "cover.png"
    carrier.write_bytes(_cover())

    analyze_simple_lsb(carrier, tmp_path)

    result = _result(tmp_path, "simple_lsb")
    assert result["status"] == "empty"
    assert result["decoded_text"] == {}


def test_petty_smoketest_key_so_easy_you_could_probably_solve_it_on_the_first_try(tmp_path):
    carrier = FIXTURES / "petty_smoketest_key_so_easy_you_could_probably_solve_it_on_the_first_try.png"
    assert hashlib.sha256(carrier.read_bytes()).hexdigest() == (
        "0e9ca7cebcbee17ea2c3308b58fbda22b7a57209c61b2bac1026c9102a1157ac"
    )

    analyze_simple_lsb(carrier, tmp_path)

    result = _result(tmp_path, "simple_lsb")
    assert result["status"] == "ok"
    assert set(result["decoded_text"]) == {"RGB"}
    assert hashlib.sha256(result["decoded_text"]["RGB"].encode("utf-8")).hexdigest() == (
        "e81cc48337e0519eb27ce7a245649fe6007abec124087c27736bdb42a3d27bb9"
    )


def test_advanced_lsb_recovers_text_and_zlib_channels(tmp_path):
    channels = {
        "R": {"enabled": True, "type": "text", "text": "red love"},
        "G": {"enabled": False},
        "B": {"enabled": True, "type": "file", "file_data": b"blue secret"},
        "A": {"enabled": False},
    }
    _, encoded = encode_multi_channel(_cover(), channels, filename="cover.png")
    carrier = tmp_path / "advanced.png"
    carrier.write_bytes(encoded)

    analyze_advanced_lsb(carrier, tmp_path)

    result = _result(tmp_path, "advanced_lsb")
    assert result["details"]["text_channels"]["R"]["text_preview"] == "red love"
    blue = next(item for item in result["details"]["file_payloads"] if item["channel"] == "B")
    assert blue["preview"] == "blue secret"


def test_advanced_lsb_rejects_random_carrier_bytes(tmp_path):
    carrier = tmp_path / "cover.png"
    carrier.write_bytes(_cover())

    analyze_advanced_lsb(carrier, tmp_path)

    result = _result(tmp_path, "advanced_lsb")
    assert result["status"] == "empty"
    assert result["details"]["text_channels"] == {}

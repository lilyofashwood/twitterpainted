import json
from pathlib import Path
from unittest.mock import patch
import zlib

import numpy as np
from PIL import Image

from engine.analyzers.stegg import analyze_stegg


def _stegg_carrier(payload: bytes) -> np.ndarray:
    header = bytearray(32)
    header[:4] = b"STEG"
    header[4] = 3
    header[5] = 0b0111  # RGB
    header[6] = 1
    header[16:20] = len(payload).to_bytes(4, "big")
    header[20:24] = len(payload).to_bytes(4, "big")
    header[24:28] = (zlib.crc32(payload) & 0xFFFFFFFF).to_bytes(4, "big")

    bits = [int(bit) for byte in header + payload for bit in f"{byte:08b}"]
    rng = np.random.default_rng(9)
    pixels = rng.integers(0, 256, size=(64, 64, 4), dtype=np.uint8)
    flat = pixels.reshape(-1, 4)

    bit_index = 0
    for pixel in range(flat.shape[0]):
        for channel in (0, 1, 2):
            if bit_index >= len(bits):
                return pixels
            flat[pixel, channel] = (int(flat[pixel, channel]) & 0xFE) | bits[bit_index]
            bit_index += 1
    return pixels


def test_stegg_recovers_payload_without_claiming_a_missing_archive(tmp_path: Path):
    carrier = tmp_path / "stegg.png"
    Image.fromarray(_stegg_carrier(b"secret")).save(carrier)

    with patch("engine.analyzers.stegg.shutil.which", return_value=None):
        analyze_stegg(carrier, tmp_path)

    results = json.loads((tmp_path / "results.json").read_text(encoding="utf-8"))
    result = results["stegg"]

    assert result["status"] == "ok"
    assert result["output"]["preview"] == "secret"
    assert result["output"]["crc_ok"] is True
    assert result["output"]["archive"] is None

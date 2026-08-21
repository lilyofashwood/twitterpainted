"""Shared low-level LSB plane decoding utilities."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Tuple

import numpy as np
from PIL import Image

CHANNEL_MAP = [
    ("red_plane", 0),
    ("green_plane", 1),
    ("blue_plane", 2),
    ("alpha_plane", 3),
]


def decode_bits_to_text(bits: np.ndarray) -> str:
    """Decode a flat bitstream into latin-1 text until NULL terminator."""
    usable = (bits.size // 8) * 8
    if usable == 0:
        return ""

    bits = bits[:usable]
    packed = np.packbits(bits, bitorder="big")
    if packed.size == 0:
        return ""

    zero_idx = np.where(packed == 0)[0]
    end = int(zero_idx[0]) if zero_idx.size else int(packed.size)
    if end <= 0:
        return ""

    return bytes(packed[:end]).decode("latin-1", errors="ignore")


def extract_plane_payloads(image_path: Path) -> Tuple[str, Dict[str, str]]:
    """Return quick LSB payload previews for RGB and each RGBA channel plane."""
    img = Image.open(image_path).convert("RGBA")
    arr = np.array(img)

    simple_rgb = decode_bits_to_text((arr[..., :3] & 1).reshape(-1))
    channels: Dict[str, str] = {}
    for key, idx in CHANNEL_MAP:
        channels[key] = decode_bits_to_text((arr[..., idx] & 1).reshape(-1))
    return simple_rgb, channels


def plane_payload_results(simple_rgb: str, channels: Dict[str, str]) -> Dict[str, Dict[str, str]]:
    """Shape extracted plane payloads in the same result schema the UI expects."""
    return {
        "simple_rgb": {
            "status": "ok" if simple_rgb else "empty",
            "output": simple_rgb,
        },
        "red_plane": {
            "status": "ok" if channels.get("red_plane") else "empty",
            "output": channels.get("red_plane", ""),
        },
        "green_plane": {
            "status": "ok" if channels.get("green_plane") else "empty",
            "output": channels.get("green_plane", ""),
        },
        "blue_plane": {
            "status": "ok" if channels.get("blue_plane") else "empty",
            "output": channels.get("blue_plane", ""),
        },
        "alpha_plane": {
            "status": "ok" if channels.get("alpha_plane") else "empty",
            "output": channels.get("alpha_plane", ""),
        },
    }

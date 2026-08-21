"""Whitespace steganography decoder (ste.gg trailing-whitespace encoding)."""

from __future__ import annotations

import math
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
from PIL import Image

from .utils import update_data

MAX_EXTRACT_BYTES = 131072
MAX_RESULTS = 6
PRINTABLE_THRESHOLD = 0.6

CHANNEL_CONFIGS: List[Dict[str, object]] = [
    {"name": "RGB-1", "channels": [0, 1, 2], "bits": 1},
    {"name": "RGBA-1", "channels": [0, 1, 2, 3], "bits": 1},
    {"name": "RGB-2", "channels": [0, 1, 2], "bits": 2},
    {"name": "RGBA-2", "channels": [0, 1, 2, 3], "bits": 2},
    {"name": "R-1", "channels": [0], "bits": 1},
    {"name": "G-1", "channels": [1], "bits": 1},
    {"name": "B-1", "channels": [2], "bits": 1},
    {"name": "R-2", "channels": [0], "bits": 2},
    {"name": "G-2", "channels": [1], "bits": 2},
    {"name": "B-2", "channels": [2], "bits": 2},
    {"name": "RG-1", "channels": [0, 1], "bits": 1},
    {"name": "RB-1", "channels": [0, 2], "bits": 1},
    {"name": "GB-1", "channels": [1, 2], "bits": 1},
    {"name": "RG-2", "channels": [0, 1], "bits": 2},
    {"name": "RB-2", "channels": [0, 2], "bits": 2},
    {"name": "GB-2", "channels": [1, 2], "bits": 2},
]


def _units_to_bytes(units: np.ndarray, bits_per_unit: int) -> bytes:
    if bits_per_unit <= 0:
        return b""
    bit_array: List[int] = []
    if bits_per_unit == 1:
        bit_array = units.astype(np.uint8).tolist()
    else:
        for value in units.tolist():
            for shift in range(bits_per_unit - 1, -1, -1):
                bit_array.append((value >> shift) & 1)

    if not bit_array:
        return b""
    byte_len = math.ceil(len(bit_array) / 8)
    out = bytearray(byte_len)
    for i, bit in enumerate(bit_array):
        byte_idx = i // 8
        out[byte_idx] = (out[byte_idx] << 1) | bit
    remaining = len(bit_array) % 8
    if remaining:
        out[-1] <<= 8 - remaining
    return bytes(out)


def _extract_raw_bytes(
    arr: np.ndarray, channels: List[int], bits_per_channel: int, max_bytes: int
) -> bytes:
    bit_mask = (1 << bits_per_channel) - 1
    flat = arr.reshape(-1, arr.shape[2])[:, channels]
    units_needed = int(math.ceil((max_bytes * 8) / bits_per_channel))
    units = (flat & bit_mask).reshape(-1)[:units_needed]
    return _units_to_bytes(units, bits_per_channel)[:max_bytes]


def _bits_to_bytes(bits: List[int]) -> bytes:
    """Convert a list of 0/1 ints to bytes."""
    if not bits:
        return b""
    usable = (len(bits) // 8) * 8
    if usable == 0:
        return b""
    out = bytearray(usable // 8)
    for i in range(usable):
        byte_idx = i // 8
        out[byte_idx] = (out[byte_idx] << 1) | bits[i]
    return bytes(out)


def _is_plausible_text(text: str) -> bool:
    """Return True if text looks like real content (printable ratio > threshold)."""
    if not text or len(text.strip()) < 4:
        return False
    printable = 0
    for ch in text:
        if ch.isprintable() or ch in {"\n", "\t"}:
            printable += 1
    ratio = printable / max(1, len(text))
    return ratio > PRINTABLE_THRESHOLD


def _printable_ratio(text: str) -> float:
    if not text:
        return 0.0
    printable = sum(1 for ch in text if ch.isprintable() or ch in {"\n", "\t"})
    return printable / max(1, len(text))


def _decode_scheme_a(lines: List[str]) -> Tuple[str, Optional[str]]:
    """Scheme A: space=0, tab=1 (ste.gg default)."""
    bits: List[int] = []
    for line in lines:
        trailing = line[len(line.rstrip(" \t")):]
        for ch in trailing:
            if ch == " ":
                bits.append(0)
            elif ch == "\t":
                bits.append(1)
    raw = _bits_to_bytes(bits)
    if not raw:
        return "scheme_a", None
    try:
        text = raw.decode("utf-8", errors="replace")
    except Exception:
        return "scheme_a", None
    if _is_plausible_text(text):
        return "scheme_a", text.strip()
    return "scheme_a", None


def _decode_scheme_b(lines: List[str]) -> Tuple[str, Optional[str]]:
    """Scheme B: count of trailing spaces mod 2."""
    bits: List[int] = []
    for line in lines:
        trailing = line[len(line.rstrip(" ")):]
        space_count = len(trailing)
        bits.append(space_count % 2)
    raw = _bits_to_bytes(bits)
    if not raw:
        return "scheme_b", None
    try:
        text = raw.decode("utf-8", errors="replace")
    except Exception:
        return "scheme_b", None
    if _is_plausible_text(text):
        return "scheme_b", text.strip()
    return "scheme_b", None


def _decode_scheme_c(lines: List[str]) -> Tuple[str, Optional[str]]:
    """Scheme C: presence of trailing whitespace = 1, absence = 0."""
    bits: List[int] = []
    for line in lines:
        stripped = line.rstrip(" \t")
        bits.append(1 if len(stripped) < len(line) else 0)
    raw = _bits_to_bytes(bits)
    if not raw:
        return "scheme_c", None
    try:
        text = raw.decode("utf-8", errors="replace")
    except Exception:
        return "scheme_c", None
    if _is_plausible_text(text):
        return "scheme_c", text.strip()
    return "scheme_c", None


def _try_all_schemes(text: str) -> Optional[Dict[str, object]]:
    """Try all decoding schemes on text, return the best plausible result."""
    lines = text.split("\n")
    if not lines:
        return None

    # Check that at least some lines have trailing whitespace
    has_trailing = any(line != line.rstrip(" \t") for line in lines)
    if not has_trailing:
        return None

    best: Optional[Dict[str, object]] = None
    best_ratio = 0.0

    for decoder in (_decode_scheme_a, _decode_scheme_b, _decode_scheme_c):
        scheme_name, decoded = decoder(lines)
        if decoded is None:
            continue
        ratio = _printable_ratio(decoded)
        if ratio > best_ratio:
            best_ratio = ratio
            best = {
                "scheme": scheme_name,
                "decoded": decoded[:500],
                "length": len(decoded),
                "printable_ratio": round(ratio, 3),
            }

    return best


def analyze_whitespace_steg(input_img: Path, output_dir: Path) -> None:
    """Decode whitespace steganography (trailing spaces/tabs) from an image."""
    try:
        img = Image.open(input_img).convert("RGBA")
    except Exception as exc:
        update_data(output_dir, {"whitespace_steg": {"status": "error", "error": str(exc)}})
        return

    arr = np.array(img)
    results: List[Dict[str, object]] = []
    seen_decoded: set = set()

    # Scan LSB plane text extracted from various channel configs
    for cfg in CHANNEL_CONFIGS:
        channels = cfg["channels"]
        bits = cfg["bits"]
        raw = _extract_raw_bytes(arr, channels, bits, MAX_EXTRACT_BYTES)
        if not raw:
            continue
        # The in-app text carrier is NUL-terminated. Preserve trailing spaces
        # on its last line while excluding the unrelated carrier bytes after it.
        text = raw.split(b"\x00", 1)[0].decode("utf-8", errors="ignore")
        if "\n" not in text:
            continue
        result = _try_all_schemes(text)
        if result is None:
            continue
        decoded_text = result["decoded"]
        if decoded_text in seen_decoded:
            continue
        seen_decoded.add(decoded_text)
        results.append(
            {
                "config": cfg["name"],
                "channels": "".join("RGBA"[idx] for idx in channels),
                "bits": bits,
                **result,
            }
        )
        if len(results) >= MAX_RESULTS:
            break

    # Also scan the raw file bytes
    if len(results) < MAX_RESULTS:
        try:
            raw_bytes = input_img.read_bytes()
        except Exception:
            raw_bytes = b""
        if raw_bytes:
            raw_text = raw_bytes.decode("utf-8", errors="ignore")
            if "\n" in raw_text:
                result = _try_all_schemes(raw_text)
                if result is not None:
                    decoded_text = result["decoded"]
                    if decoded_text not in seen_decoded:
                        seen_decoded.add(decoded_text)
                        results.append(
                            {
                                "config": "raw-file",
                                **result,
                            }
                        )

    if results:
        # Sort by printable ratio descending
        results.sort(key=lambda r: -r.get("printable_ratio", 0))
        update_data(output_dir, {"whitespace_steg": {"status": "ok", "output": results}})
    else:
        update_data(
            output_dir,
            {"whitespace_steg": {"status": "empty", "reason": "No whitespace steganography detected"}},
        )

"""Channel Cipher / 'GODMODE' steganography decoder (ste.gg).

Recovers data hidden via password-seeded channel hopping, where a PRNG
determines which channel and bit plane each message bit is read from.
"""

from __future__ import annotations

import random
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from PIL import Image

from .utils import update_data

DEFAULT_PASSWORDS = ["", "password", "secret", "stego"]
MAX_EXTRACT_BITS = 1_000_000  # cap to avoid runaway extraction
NUM_CHANNELS = 4  # RGBA
NUM_BIT_PLANES = 2  # planes 0 and 1


def _extract_with_password(
    arr: np.ndarray, password: str, max_bits: int
) -> bytes:
    """Extract hidden bits using password-seeded channel hopping.

    For each bit position, the PRNG (seeded with the password) determines:
      - which channel (0-3: R, G, B, A) to read from
      - which bit plane (0 or 1) to read
    Pixels are read in raster order; the hopping pattern is applied per-bit.
    """
    rng = random.Random(password)

    height, width = arr.shape[:2]
    total_pixels = height * width
    usable_bits = min(max_bits, total_pixels)

    flat = arr.reshape(-1, arr.shape[2])  # (num_pixels, channels)

    bits: List[int] = []
    for i in range(usable_bits):
        channel = rng.randint(0, NUM_CHANNELS - 1)
        bit_plane = rng.randint(0, NUM_BIT_PLANES - 1)
        pixel_val = int(flat[i, channel])
        bit = (pixel_val >> bit_plane) & 1
        bits.append(bit)

    # Convert bits to bytes
    if not bits:
        return b""
    byte_count = len(bits) // 8
    out = bytearray(byte_count)
    for i in range(byte_count):
        byte_val = 0
        for j in range(8):
            byte_val = (byte_val << 1) | bits[i * 8 + j]
        out[i] = byte_val
    return bytes(out)


def _try_length_prefix(data: bytes) -> Optional[bytes]:
    """Check for a 16-bit big-endian length prefix and extract the payload."""
    if len(data) < 2:
        return None
    length = int.from_bytes(data[:2], "big")
    if 0 < length <= len(data) - 2:
        return data[2 : 2 + length]
    return None


def _printable_ratio(data: bytes) -> float:
    """Return the fraction of printable ASCII characters in the data."""
    if not data:
        return 0.0
    count = 0
    for b in data:
        if 32 <= b < 127 or b in (9, 10, 13):  # printable + tab/newline/cr
            count += 1
    return count / len(data)


def _detect_text(data: bytes) -> Dict[str, Any]:
    """Analyze extracted bytes for text content."""
    if not data:
        return {"is_text": False, "confidence": 0, "preview": "", "ratio": 0.0}

    try:
        text = data.decode("utf-8", errors="ignore")
    except Exception:
        return {"is_text": False, "confidence": 0, "preview": "", "ratio": 0.0}

    sample = text[:500]
    ratio = _printable_ratio(data[:500])

    common_words = ["the", "and", "is", "in", "to", "of", "a", "for", "flag", "ctf", "secret"]
    text_lower = text.lower()
    word_matches = sum(1 for w in common_words if w in text_lower)
    confidence = min(100, max(0, ratio * 50 + word_matches * 5))

    preview = re.sub(r"[^\x20-\x7E\n\t]", "", sample[:120]).strip()

    return {
        "is_text": confidence > 35 and ratio > 0.7,
        "confidence": confidence,
        "preview": preview,
        "ratio": round(ratio, 4),
    }


def analyze_channel_cipher(
    input_img: Path, output_dir: Path, password: str = ""
) -> None:
    """Decode Channel Cipher / GODMODE steganography from an image.

    Attempts to recover data hidden via password-seeded channel hopping.
    If no password is provided, tries a set of common defaults.
    """
    if not input_img.exists():
        update_data(
            output_dir,
            {"channel_cipher": {"status": "error", "error": f"Input image not found: {input_img}"}},
        )
        return

    try:
        img = Image.open(input_img).convert("RGBA")
    except Exception as exc:
        update_data(
            output_dir,
            {"channel_cipher": {"status": "error", "error": f"Failed to open image: {exc}"}},
        )
        return

    arr = np.array(img)

    # Build candidate password list
    if password:
        passwords = [password]
    else:
        passwords = list(DEFAULT_PASSWORDS)

    best_result: Optional[Dict[str, Any]] = None
    best_ratio: float = 0.0
    all_attempts: List[Dict[str, Any]] = []

    for pwd in passwords:
        try:
            raw = _extract_with_password(arr, pwd, MAX_EXTRACT_BITS)
        except Exception:
            continue

        if not raw:
            continue

        # Try with 16-bit length prefix first
        prefixed = _try_length_prefix(raw)
        if prefixed:
            analysis = _detect_text(prefixed)
            if analysis["ratio"] > best_ratio:
                best_ratio = analysis["ratio"]
                best_result = {
                    "password": pwd if pwd else "(empty)",
                    "method": "length_prefix",
                    "extracted_bytes": len(prefixed),
                    "analysis": analysis,
                }
            all_attempts.append({
                "password": pwd if pwd else "(empty)",
                "method": "length_prefix",
                "ratio": analysis["ratio"],
                "confidence": analysis["confidence"],
            })

        # Also try raw extraction (no length prefix)
        # Limit to first 4096 bytes for text detection
        raw_sample = raw[:4096]
        analysis = _detect_text(raw_sample)
        if analysis["ratio"] > best_ratio:
            best_ratio = analysis["ratio"]
            best_result = {
                "password": pwd if pwd else "(empty)",
                "method": "raw",
                "extracted_bytes": len(raw_sample),
                "analysis": analysis,
            }
        all_attempts.append({
            "password": pwd if pwd else "(empty)",
            "method": "raw",
            "ratio": analysis["ratio"],
            "confidence": analysis["confidence"],
        })

    if best_result and best_ratio > 0.5:
        update_data(
            output_dir,
            {
                "channel_cipher": {
                    "status": "ok",
                    "output": {
                        "best_match": best_result,
                        "attempts": all_attempts,
                    },
                }
            },
        )
    else:
        update_data(
            output_dir,
            {
                "channel_cipher": {
                    "status": "empty",
                    "output": {
                        "note": "No coherent data recovered with tested passwords.",
                        "attempts": all_attempts,
                        "best_ratio": round(best_ratio, 4),
                    },
                }
            },
        )

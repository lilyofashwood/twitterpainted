"""Homoglyph substitution steganography decoder (ste.gg style)."""

from __future__ import annotations

import math
import re
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
from PIL import Image

from .utils import update_data

MAX_EXTRACT_BYTES = 131072
MAX_RESULTS = 6

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

# ---------------------------------------------------------------------------
# Homoglyph mapping: Unicode codepoint -> ASCII character it imitates
# Keys are the Unicode homoglyphs; values are the ASCII originals.
# ---------------------------------------------------------------------------

# fmt: off
HOMOGLYPH_MAP: Dict[str, str] = {
    # --- Cyrillic lowercase lookalikes ---
    "\u0430": "a",  # а -> a
    "\u0435": "e",  # е -> e
    "\u043e": "o",  # о -> o
    "\u0440": "p",  # р -> p
    "\u0441": "c",  # с -> c
    "\u0443": "y",  # у -> y (Cyrillic у)
    "\u0445": "x",  # х -> x
    "\u0456": "i",  # і -> i (Ukrainian і)
    "\u0458": "j",  # ј -> j (Cyrillic ј)
    "\u04bb": "h",  # һ -> h (Cyrillic shha)
    "\u0455": "s",  # ѕ -> s (Cyrillic ѕ)
    "\u0471": "ψ",  # skip – not ASCII (psi) – intentionally omitted below
    "\u051b": "q",  # ԛ -> q (Cyrillic qa)
    "\u051d": "w",  # ԝ -> w (Cyrillic we)

    # --- Cyrillic uppercase lookalikes ---
    "\u0410": "A",  # А -> A
    "\u0412": "B",  # В -> B
    "\u0415": "E",  # Е -> E
    "\u041a": "K",  # К -> K
    "\u041c": "M",  # М -> M
    "\u041d": "H",  # Н -> H
    "\u041e": "O",  # О -> O
    "\u0420": "P",  # Р -> P
    "\u0421": "C",  # С -> C
    "\u0422": "T",  # Т -> T
    "\u0425": "X",  # Х -> X
    "\u0427": "4",  # Ч -> 4 (sometimes used)

    # --- Greek uppercase lookalikes ---
    "\u0391": "A",  # Α -> A
    "\u0392": "B",  # Β -> B
    "\u0395": "E",  # Ε -> E
    "\u0396": "Z",  # Ζ -> Z
    "\u0397": "H",  # Η -> H
    "\u0399": "I",  # Ι -> I
    "\u039a": "K",  # Κ -> K
    "\u039c": "M",  # Μ -> M
    "\u039d": "N",  # Ν -> N
    "\u039f": "O",  # Ο -> O
    "\u03a1": "P",  # Ρ -> P
    "\u03a4": "T",  # Τ -> T
    "\u03a7": "X",  # Χ -> X
    "\u03a5": "Y",  # Υ -> Y

    # --- Greek lowercase lookalikes ---
    "\u03bf": "o",  # ο -> o
    "\u03b9": "i",  # ι -> i (iota, no dot but close)
    "\u03ba": "k",  # κ -> k (less convincing, but used)
    "\u03bd": "v",  # ν -> v
    "\u03c1": "p",  # ρ -> p (tail differs, but used in steg)

    # --- Fullwidth Latin uppercase (U+FF21..U+FF3A) ---
    "\uff21": "A", "\uff22": "B", "\uff23": "C", "\uff24": "D",
    "\uff25": "E", "\uff26": "F", "\uff27": "G", "\uff28": "H",
    "\uff29": "I", "\uff2a": "J", "\uff2b": "K", "\uff2c": "L",
    "\uff2d": "M", "\uff2e": "N", "\uff2f": "O", "\uff30": "P",
    "\uff31": "Q", "\uff32": "R", "\uff33": "S", "\uff34": "T",
    "\uff35": "U", "\uff36": "V", "\uff37": "W", "\uff38": "X",
    "\uff39": "Y", "\uff3a": "Z",

    # --- Fullwidth Latin lowercase (U+FF41..U+FF5A) ---
    "\uff41": "a", "\uff42": "b", "\uff43": "c", "\uff44": "d",
    "\uff45": "e", "\uff46": "f", "\uff47": "g", "\uff48": "h",
    "\uff49": "i", "\uff4a": "j", "\uff4b": "k", "\uff4c": "l",
    "\uff4d": "m", "\uff4e": "n", "\uff4f": "o", "\uff50": "p",
    "\uff51": "q", "\uff52": "r", "\uff53": "s", "\uff54": "t",
    "\uff55": "u", "\uff56": "v", "\uff57": "w", "\uff58": "x",
    "\uff59": "y", "\uff5a": "z",

    # --- Fullwidth digits (U+FF10..U+FF19) ---
    "\uff10": "0", "\uff11": "1", "\uff12": "2", "\uff13": "3",
    "\uff14": "4", "\uff15": "5", "\uff16": "6", "\uff17": "7",
    "\uff18": "8", "\uff19": "9",

    # --- Mathematical Bold (U+1D400..U+1D419 uppercase, U+1D41A..U+1D433 lowercase) ---
    "\U0001d400": "A", "\U0001d401": "B", "\U0001d402": "C", "\U0001d403": "D",
    "\U0001d404": "E", "\U0001d405": "F", "\U0001d406": "G", "\U0001d407": "H",
    "\U0001d408": "I", "\U0001d409": "J", "\U0001d40a": "K", "\U0001d40b": "L",
    "\U0001d40c": "M", "\U0001d40d": "N", "\U0001d40e": "O", "\U0001d40f": "P",
    "\U0001d410": "Q", "\U0001d411": "R", "\U0001d412": "S", "\U0001d413": "T",
    "\U0001d414": "U", "\U0001d415": "V", "\U0001d416": "W", "\U0001d417": "X",
    "\U0001d418": "Y", "\U0001d419": "Z",
    "\U0001d41a": "a", "\U0001d41b": "b", "\U0001d41c": "c", "\U0001d41d": "d",
    "\U0001d41e": "e", "\U0001d41f": "f", "\U0001d420": "g", "\U0001d421": "h",
    "\U0001d422": "i", "\U0001d423": "j", "\U0001d424": "k", "\U0001d425": "l",
    "\U0001d426": "m", "\U0001d427": "n", "\U0001d428": "o", "\U0001d429": "p",
    "\U0001d42a": "q", "\U0001d42b": "r", "\U0001d42c": "s", "\U0001d42d": "t",
    "\U0001d42e": "u", "\U0001d42f": "v", "\U0001d430": "w", "\U0001d431": "x",
    "\U0001d432": "y", "\U0001d433": "z",

    # --- Mathematical Italic (U+1D434..U+1D467) ---
    "\U0001d434": "A", "\U0001d435": "B", "\U0001d436": "C", "\U0001d437": "D",
    "\U0001d438": "E", "\U0001d439": "F", "\U0001d43a": "G", "\U0001d43b": "H",
    "\U0001d43c": "I", "\U0001d43d": "J", "\U0001d43e": "K", "\U0001d43f": "L",
    "\U0001d440": "M", "\U0001d441": "N", "\U0001d442": "O", "\U0001d443": "P",
    "\U0001d444": "Q", "\U0001d445": "R", "\U0001d446": "S", "\U0001d447": "T",
    "\U0001d448": "U", "\U0001d449": "V", "\U0001d44a": "W", "\U0001d44b": "X",
    "\U0001d44c": "Y", "\U0001d44d": "Z",
    "\U0001d44e": "a", "\U0001d44f": "b", "\U0001d450": "c", "\U0001d451": "d",
    "\U0001d452": "e", "\U0001d453": "f", "\U0001d454": "g",
    # U+1D455 is reserved (h is U+210E PLANCK CONSTANT)
    "\u210e":    "h",
    "\U0001d456": "i", "\U0001d457": "j", "\U0001d458": "k", "\U0001d459": "l",
    "\U0001d45a": "m", "\U0001d45b": "n", "\U0001d45c": "o", "\U0001d45d": "p",
    "\U0001d45e": "q", "\U0001d45f": "r", "\U0001d460": "s", "\U0001d461": "t",
    "\U0001d462": "u", "\U0001d463": "v", "\U0001d464": "w", "\U0001d465": "x",
    "\U0001d466": "y", "\U0001d467": "z",

    # --- Mathematical Sans-Serif (U+1D5A0..U+1D5D3) ---
    "\U0001d5a0": "A", "\U0001d5a1": "B", "\U0001d5a2": "C", "\U0001d5a3": "D",
    "\U0001d5a4": "E", "\U0001d5a5": "F", "\U0001d5a6": "G", "\U0001d5a7": "H",
    "\U0001d5a8": "I", "\U0001d5a9": "J", "\U0001d5aa": "K", "\U0001d5ab": "L",
    "\U0001d5ac": "M", "\U0001d5ad": "N", "\U0001d5ae": "O", "\U0001d5af": "P",
    "\U0001d5b0": "Q", "\U0001d5b1": "R", "\U0001d5b2": "S", "\U0001d5b3": "T",
    "\U0001d5b4": "U", "\U0001d5b5": "V", "\U0001d5b6": "W", "\U0001d5b7": "X",
    "\U0001d5b8": "Y", "\U0001d5b9": "Z",
    "\U0001d5ba": "a", "\U0001d5bb": "b", "\U0001d5bc": "c", "\U0001d5bd": "d",
    "\U0001d5be": "e", "\U0001d5bf": "f", "\U0001d5c0": "g", "\U0001d5c1": "h",
    "\U0001d5c2": "i", "\U0001d5c3": "j", "\U0001d5c4": "k", "\U0001d5c5": "l",
    "\U0001d5c6": "m", "\U0001d5c7": "n", "\U0001d5c8": "o", "\U0001d5c9": "p",
    "\U0001d5ca": "q", "\U0001d5cb": "r", "\U0001d5cc": "s", "\U0001d5cd": "t",
    "\U0001d5ce": "u", "\U0001d5cf": "v", "\U0001d5d0": "w", "\U0001d5d1": "x",
    "\U0001d5d2": "y", "\U0001d5d3": "z",

    # --- Miscellaneous single-char lookalikes ---
    "\u0131": "i",  # ı  Latin small dotless i
    "\u0237": "j",  # ȷ  Latin small dotless j
    "\u2018": "'",  # '  left single quotation mark
    "\u2019": "'",  # '  right single quotation mark
    "\u201c": '"',  # "  left double quotation mark
    "\u201d": '"',  # "  right double quotation mark
    "\u2010": "-",  # ‐  hyphen
    "\u2011": "-",  # ‑  non-breaking hyphen
    "\u2012": "-",  # ‒  figure dash
    "\u2013": "-",  # –  en dash
    "\u2014": "-",  # —  em dash
}
# fmt: on

# Build a reverse lookup: ASCII char -> set of homoglyphs that mimic it
_ASCII_TO_HOMOGLYPHS: Dict[str, set] = {}
for _hg, _ascii in HOMOGLYPH_MAP.items():
    _ASCII_TO_HOMOGLYPHS.setdefault(_ascii, set()).add(_hg)

# Build a set for O(1) membership testing
_HOMOGLYPH_SET = frozenset(HOMOGLYPH_MAP.keys())


# ---------------------------------------------------------------------------
# LSB extraction helpers (mirrors zero_width.py)
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Homoglyph scanning & decoding
# ---------------------------------------------------------------------------

def _contains_homoglyphs(text: str) -> bool:
    """Quick check whether text has any known homoglyph characters."""
    for ch in text:
        if ch in _HOMOGLYPH_SET:
            return True
    return False


def _scan_homoglyphs(text: str) -> Tuple[List[int], List[Tuple[int, str, str]], str]:
    """Scan *text* for positions where a homoglyph replaces an ASCII char.

    Only positions that contain either a plain ASCII letter/digit **or** a
    known homoglyph contribute to the bitstream.  Other characters (spaces,
    punctuation that has no homoglyph pair, newlines, etc.) are skipped.

    Returns:
        bits       – list of 0/1 ints (0 = ASCII original, 1 = homoglyph)
        subs       – list of (position, homoglyph_char, ascii_equivalent) for
                     each substituted position
        clean_text – text with all homoglyphs replaced by their ASCII original
    """
    bits: List[int] = []
    subs: List[Tuple[int, str, str]] = []
    clean_chars: List[str] = []

    for idx, ch in enumerate(text):
        if ch in _HOMOGLYPH_SET:
            # This is a homoglyph -> counts as a 1-bit
            ascii_eq = HOMOGLYPH_MAP[ch]
            bits.append(1)
            subs.append((idx, ch, ascii_eq))
            clean_chars.append(ascii_eq)
        elif ch.isascii() and (ch.isalpha() or ch.isdigit()):
            # Plain ASCII letter or digit that *could* have been substituted
            bits.append(0)
            clean_chars.append(ch)
        else:
            # Non-participating character (space, punctuation, etc.)
            clean_chars.append(ch)

    return bits, subs, "".join(clean_chars)


def _bits_to_bytes(bits: List[int]) -> bytes:
    """Convert a list of 0/1 bits into bytes (MSB first)."""
    usable = (len(bits) // 8) * 8
    if usable == 0:
        return b""
    out = bytearray()
    for i in range(0, usable, 8):
        byte_val = 0
        for b in bits[i : i + 8]:
            byte_val = (byte_val << 1) | b
        out.append(byte_val)
    return bytes(out)


def _is_plausible_text(text: str) -> bool:
    """Heuristic check for whether decoded bytes look like readable text."""
    if not text:
        return False
    printable = 0
    for ch in text:
        if ch.isprintable() or ch in {"\n", "\t"}:
            printable += 1
    ratio = printable / max(1, len(text))
    if ratio < 0.6:
        return False
    if re.search(r"(flag|ctf|steg|secret)", text, re.IGNORECASE):
        return True
    return len(text.strip()) >= 4


def _try_decode_homoglyph_payload(text: str) -> List[Dict[str, object]]:
    """Attempt to extract hidden data from homoglyph substitutions in *text*.

    Returns a list of result dicts (may be empty if nothing plausible found).
    """
    if not _contains_homoglyphs(text):
        return []

    bits, subs, clean_text = _scan_homoglyphs(text)

    if len(subs) < 4:
        # Too few substitutions to carry meaningful data
        return []

    results: List[Dict[str, object]] = []

    # --- Primary decode: whole bitstream ---
    raw = _bits_to_bytes(bits)
    if raw:
        try:
            decoded = raw.decode("utf-8", errors="replace")
        except Exception:
            decoded = ""
        if _is_plausible_text(decoded):
            results.append({
                "payload": decoded.strip(),
                "length": len(raw),
                "substitution_count": len(subs),
                "total_positions": len(bits),
                "method": "full-bitstream",
            })

    # --- Alternate decode: only the substitution positions as char indices ---
    # Some encoders store the message in the *identity* of the substituted
    # chars (the ASCII equivalents themselves spell out the message).
    sub_chars = "".join(ascii_eq for _, _, ascii_eq in subs)
    if len(sub_chars) >= 4 and _is_plausible_text(sub_chars):
        results.append({
            "payload": sub_chars.strip(),
            "length": len(sub_chars),
            "substitution_count": len(subs),
            "total_positions": len(bits),
            "method": "substituted-chars",
        })

    return results


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def analyze_homoglyph(input_img: Path, output_dir: Path) -> None:
    """Decode homoglyph-substitution steganography from image data."""
    try:
        img = Image.open(input_img).convert("RGBA")
    except Exception as exc:
        update_data(output_dir, {"homoglyph": {"status": "error", "error": str(exc)}})
        return

    arr = np.array(img)
    results: List[Dict[str, object]] = []
    seen_payloads: set = set()

    # --- Scan LSB-extracted text from each channel config ---
    for cfg in CHANNEL_CONFIGS:
        channels = cfg["channels"]
        bits = cfg["bits"]
        raw = _extract_raw_bytes(arr, channels, bits, MAX_EXTRACT_BYTES)
        if not raw:
            continue
        # The in-app text carrier terminates its UTF-8 stream with a NUL.
        # Ignoring that boundary folds random carrier bytes into the homoglyph
        # bitstream and can bury a valid payload under false positives.
        text = raw.split(b"\x00", 1)[0].decode("utf-8", errors="ignore")
        if not _contains_homoglyphs(text):
            continue
        payloads = _try_decode_homoglyph_payload(text)
        for payload in payloads:
            payload_text = payload["payload"]
            if payload_text in seen_payloads:
                continue
            seen_payloads.add(payload_text)
            results.append({
                "config": cfg["name"],
                "channels": "".join("RGBA"[idx] for idx in channels),
                "bits": bits,
                **payload,
            })
            if len(results) >= MAX_RESULTS:
                break
        if len(results) >= MAX_RESULTS:
            break

    # --- Also scan the raw file bytes (homoglyphs may be in metadata/text chunks) ---
    if len(results) < MAX_RESULTS:
        try:
            raw_bytes = input_img.read_bytes()
        except Exception:
            raw_bytes = b""
        if raw_bytes:
            raw_text = raw_bytes.decode("utf-8", errors="ignore")
            if _contains_homoglyphs(raw_text):
                payloads = _try_decode_homoglyph_payload(raw_text)
                for payload in payloads:
                    payload_text = payload["payload"]
                    if payload_text in seen_payloads:
                        continue
                    seen_payloads.add(payload_text)
                    results.append({
                        "config": "raw-file",
                        **payload,
                    })
                    if len(results) >= MAX_RESULTS:
                        break

    if results:
        update_data(output_dir, {"homoglyph": {"status": "ok", "output": results}})
    else:
        update_data(
            output_dir,
            {"homoglyph": {"status": "empty", "reason": "No homoglyph payloads detected"}},
        )

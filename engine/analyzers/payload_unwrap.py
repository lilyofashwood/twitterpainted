"""Attempt to unwrap binary payloads extracted from stego carriers."""

from __future__ import annotations

import base64
import binascii
import re
import subprocess
import zlib
import gzip
import bz2
import lzma
from pathlib import Path
from shutil import which
from typing import Any, Dict, Iterable, List, Optional, Tuple

import numpy as np
from PIL import Image

from ..option_decoders import _extract_lsb_bytes, _pvd_extract_bits, _pvd_ranges, _bits_to_bytes
from .utils import update_data

MAX_PAYLOAD_BYTES_LIGHT = 16384
MAX_PAYLOAD_BYTES_DEEP = 65536
MAX_PAYLOADS = 4
MAX_CANDIDATES = 8
MAX_PREVIEW = 200
MAX_FULL_BASE64 = 262144
MAX_REPEAT_KEY_LEN = 16
MAX_REPEAT_KEY_LEN_DEEP = 32
MAX_REPEAT_SAMPLE_BYTES = 4096
MAX_CRIB_OFFSETS = 128
MAX_CRIB_OFFSETS_DEEP = 256

PATTERNS = [b"ctf{", b"flag{", b"steg{"]
BASE64_RE = re.compile(r"^[A-Za-z0-9+/=]+$")
HEX_RE = re.compile(r"^[0-9A-Fa-f]+$")
ASCII85_RE = re.compile(r"^[A-Za-z0-9!#$%&()*+,./:;<=>?@\\[\\]^_`{|}~\\\"]+$")
HASH_HEX_RE = re.compile(r"(?:[0-9A-Fa-f]{32}|[0-9A-Fa-f]{40}|[0-9A-Fa-f]{64})")
HASH_LEN_HINTS = {16: "bytes16", 20: "bytes20", 32: "bytes32"}
COMMON_BIGRAMS = {
    "th",
    "he",
    "in",
    "er",
    "an",
    "re",
    "on",
    "at",
    "en",
    "nd",
    "ti",
    "es",
    "or",
    "te",
    "of",
}
COMMON_TRIGRAMS = {
    "the",
    "and",
    "ing",
    "her",
    "ere",
    "ent",
    "tha",
    "nth",
    "was",
    "eth",
    "for",
    "dth",
}
BASE91_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789!#$%&()*+,./:;<=>?@[]^_`{|}~\\\""
BASE91_DECODE = {c: i for i, c in enumerate(BASE91_ALPHABET)}


def _ascii_preview(data: bytes, limit: int = MAX_PREVIEW) -> str:
    out: List[str] = []
    for b in data[:limit]:
        if 32 <= b < 127:
            out.append(chr(b))
        elif b == 9:
            out.append("\\t")
        elif b == 10:
            out.append("\\n")
        elif b == 13:
            out.append("\\r")
        else:
            out.append(f"\\x{b:02x}")
    return "".join(out)


def _printable_ratio(text: str) -> float:
    if not text:
        return 0.0
    printable = sum(1 for ch in text if ch.isprintable() or ch in {"\n", "\t", "\r"})
    return printable / max(1, len(text))


def _decode_text(data: bytes) -> Tuple[str, float]:
    if not data:
        return "", 0.0
    try:
        text = data.decode("utf-8", errors="ignore")
    except Exception:
        return "", 0.0
    text = text.strip()
    return text, _printable_ratio(text)


def _ngram_score(text: str) -> float:
    if not text:
        return 0.0
    lowered = text.lower()
    bigram_hits = 0
    trigram_hits = 0
    for idx in range(len(lowered) - 1):
        if lowered[idx : idx + 2] in COMMON_BIGRAMS:
            bigram_hits += 1
    for idx in range(len(lowered) - 2):
        if lowered[idx : idx + 3] in COMMON_TRIGRAMS:
            trigram_hits += 1
    bigram_ratio = bigram_hits / max(1, len(lowered) - 1)
    trigram_ratio = trigram_hits / max(1, len(lowered) - 2)
    return min(1.0, bigram_ratio * 2.0 + trigram_ratio * 3.0)


def _english_score(text: str) -> float:
    if not text:
        return 0.0
    score = 0.0
    for ch in text:
        if ch.isalpha():
            score += 1.0
            if ch.lower() in "etaoinshrdlu":
                score += 0.2
        elif ch.isspace():
            score += 0.8
        elif ch.isdigit():
            score += 0.2
        elif 32 <= ord(ch) < 127:
            score += 0.1
        else:
            score -= 1.0
    base = max(0.0, score / max(1, len(text)))
    return min(1.0, base + _ngram_score(text) * 0.25)


def _base91_decode(data: str) -> Optional[bytes]:
    if not data:
        return None
    v = -1
    b = 0
    n = 0
    out = bytearray()
    for ch in data:
        if ch not in BASE91_DECODE:
            continue
        c = BASE91_DECODE[ch]
        if v < 0:
            v = c
        else:
            v += c * 91
            b |= v << n
            n += 13 if (v & 8191) > 88 else 14
            while n > 7:
                out.append(b & 255)
                b >>= 8
                n -= 8
            v = -1
    if v >= 0:
        b |= v << n
        n += 7
        while n > 7:
            out.append(b & 255)
            b >>= 8
            n -= 8
    return bytes(out) if out else None


def _hash_hints(text: str, payload_len: int) -> Tuple[List[str], float]:
    hints: List[str] = []
    boost = 0.0
    if text:
        for match in HASH_HEX_RE.findall(text):
            hints.append(f"hex{len(match)}")
            boost += 0.05
            if len(hints) >= 2:
                break
    if payload_len in HASH_LEN_HINTS:
        hints.append(HASH_LEN_HINTS[payload_len])
        boost += 0.05
    return hints, boost


def _apply_hash_hints(candidate: Dict[str, Any], text: str, payload_len: int) -> None:
    hints, boost = _hash_hints(text, payload_len)
    if not hints:
        return
    note = candidate.get("notes", "")
    suffix = f"hash-hint: {', '.join(hints)}"
    candidate["notes"] = f"{note} | {suffix}" if note else suffix
    score = float(candidate.get("score", 0.0)) + boost
    candidate["score"] = round(min(1.0, score), 3)


def _find_payload(data: bytes) -> Optional[Tuple[int, int, bytes, Optional[int], str]]:
    if not data:
        return None
    lower = data.lower()
    for pat in PATTERNS:
        idx = lower.find(pat)
        if idx == -1:
            continue
        end = data.find(b"}", idx)
        if end == -1:
            end = min(len(data), idx + MAX_PREVIEW)
        return idx, end, data[idx : end + 1], None, pat.decode("ascii")
    return None


def _find_payload_xor(data: bytes) -> Optional[Tuple[int, int, bytes, int, str]]:
    if not data:
        return None
    for key in range(256):
        xored = bytes(b ^ key for b in data)
        lower = xored.lower()
        for pat in PATTERNS:
            idx = lower.find(pat)
            if idx == -1:
                continue
            end = xored.find(b"}", idx)
            if end == -1:
                end = min(len(xored), idx + MAX_PREVIEW)
            return idx, end, xored[idx : end + 1], key, pat.decode("ascii")
    return None


def _iter_streams(img: Image.Image, deep_analysis: bool, max_bytes: int) -> Iterable[Tuple[str, bytes]]:
    if img.mode not in {"RGB", "RGBA"}:
        img = img.convert("RGBA")

    if img.mode == "RGBA":
        channel_orders = [("RGB", [0, 1, 2]), ("RGBA", [0, 1, 2, 3])]
        if deep_analysis:
            channel_orders.extend([("BGR", [2, 1, 0]), ("ARGB", [3, 0, 1, 2])])
    else:
        channel_orders = [("RGB", [0, 1, 2])]
        if deep_analysis:
            channel_orders.append(("BGR", [2, 1, 0]))

    bits_per_channel = (1, 2) if not deep_analysis else (1, 2, 4)

    for bits in bits_per_channel:
        for order_name, channels in channel_orders:
            blob = _extract_lsb_bytes(img, channels, bits_per_channel=bits, max_bytes=max_bytes)
            yield f"lsb {order_name} b{bits}", blob

    gray = img.convert("L")
    values = np.array(gray)
    directions = ("horizontal",) if not deep_analysis else ("horizontal", "vertical", "both")
    ranges = ("wu-tsai",) if not deep_analysis else ("wu-tsai", "wide", "narrow")
    max_bits = max_bytes * 8 + 7
    for direction in directions:
        for range_kind in ranges:
            rng = _pvd_ranges(range_kind)
            if direction == "horizontal":
                bits_list = _pvd_extract_bits(values, max_bits, rng)
            elif direction == "vertical":
                bits_list = _pvd_extract_bits(values.T, max_bits, rng)
            else:
                bits_h = _pvd_extract_bits(values, max_bits, rng)
                bits_v = _pvd_extract_bits(values.T, max_bits, rng)
                bits_list = (bits_h + bits_v)[:max_bits]
            blob = _bits_to_bytes(bits_list)[:max_bytes]
            yield f"pvd {direction} {range_kind}", blob


def _try_decompress(payload: bytes) -> List[Dict[str, Any]]:
    attempts: List[Dict[str, Any]] = []
    for name, fn in (
        ("zlib", zlib.decompress),
        ("gzip", gzip.decompress),
        ("bz2", bz2.decompress),
        ("lzma", lzma.decompress),
    ):
        try:
            decoded = fn(payload)
        except Exception:
            continue
        text, ratio = _decode_text(decoded)
        candidate = {
            "method": name,
            "score": ratio,
            "preview": text[:MAX_PREVIEW] if text else _ascii_preview(decoded),
            "notes": f"{name} decompressed {len(decoded)} bytes",
        }
        _apply_hash_hints(candidate, text, len(decoded))
        candidate["score"] = round(float(candidate.get("score", 0.0)), 3)
        attempts.append(candidate)
    return attempts


def _maybe_base_decode(text: str) -> Optional[bytes]:
    raw = text.strip()
    if len(raw) < 12:
        return None
    if len(raw) % 4 == 0 and BASE64_RE.fullmatch(raw):
        try:
            return base64.b64decode(raw, validate=True)
        except Exception:
            return None
    if len(raw) % 2 == 0 and HEX_RE.fullmatch(raw):
        try:
            return binascii.unhexlify(raw)
        except Exception:
            return None
    if ASCII85_RE.fullmatch(raw):
        try:
            return base64.a85decode(raw, adobe=False)
        except Exception:
            pass
        try:
            return base64.b85decode(raw)
        except Exception:
            pass
        decoded = _base91_decode(raw)
        if decoded:
            return decoded
    return None


def _score_candidate(text: str, has_flag: bool) -> float:
    ratio = _printable_ratio(text)
    score = (ratio * 0.7) + (_english_score(text) * 0.3)
    if has_flag:
        score += 0.5
    return min(1.0, score)


def _unwrap_payload(payload: bytes, xor_key: Optional[int], *, deep_analysis: bool) -> List[Dict[str, Any]]:
    candidates: List[Dict[str, Any]] = []
    payload_len = len(payload)

    raw_text, raw_ratio = _decode_text(payload)
    raw_flag = any(pat in raw_text.lower() for pat in ("ctf{", "flag{", "steg{"))
    if raw_ratio >= 0.5 or raw_flag:
        candidate = {
            "method": "raw",
            "score": _score_candidate(raw_text, raw_flag),
            "preview": raw_text[:MAX_PREVIEW] if raw_text else _ascii_preview(payload),
            "notes": "raw payload text",
        }
        _apply_hash_hints(candidate, raw_text, payload_len)
        candidate["score"] = round(float(candidate.get("score", 0.0)), 3)
        candidates.append(candidate)

    candidates.extend(_try_decompress(payload))

    # Prefer deterministic wrapper decoding before the broad XOR/rotation
    # sweeps fill the candidate limit with equally printable noise.
    if raw_text:
        decoded = _maybe_base_decode(raw_text)
        if decoded:
            text, ratio = _decode_text(decoded)
            candidate = {
                "method": "base-decode",
                "score": ratio,
                "preview": text[:MAX_PREVIEW] if text else _ascii_preview(decoded),
                "notes": "base64/hex decoded from raw text",
            }
            _apply_hash_hints(candidate, text, len(decoded))
            candidate["score"] = round(float(candidate.get("score", 0.0)), 3)
            candidates.append(candidate)

    for key in range(256):
        xored = bytes(b ^ key for b in payload)
        text, ratio = _decode_text(xored)
        flag = any(pat in text.lower() for pat in ("ctf{", "flag{", "steg{"))
        if ratio < 0.55 and not flag:
            continue
        candidate = {
            "method": f"xor:0x{key:02x}",
            "score": _score_candidate(text, flag),
            "preview": text[:MAX_PREVIEW] if text else _ascii_preview(xored),
            "notes": "single-byte xor on payload",
        }
        _apply_hash_hints(candidate, text, payload_len)
        candidate["score"] = round(float(candidate.get("score", 0.0)), 3)
        candidates.append(candidate)
        if len(candidates) >= MAX_CANDIDATES:
            break

    for shift in (1, 2, 3, 4):
        rotated = bytes(((b << shift) | (b >> (8 - shift))) & 0xFF for b in payload)
        text, ratio = _decode_text(rotated)
        flag = any(pat in text.lower() for pat in ("ctf{", "flag{", "steg{"))
        if ratio < 0.6 and not flag:
            continue
        candidate = {
            "method": f"rotl:{shift}",
            "score": _score_candidate(text, flag),
            "preview": text[:MAX_PREVIEW] if text else _ascii_preview(rotated),
            "notes": "bit-rotate left",
        }
        _apply_hash_hints(candidate, text, payload_len)
        candidate["score"] = round(float(candidate.get("score", 0.0)), 3)
        candidates.append(candidate)
        if len(candidates) >= MAX_CANDIDATES:
            break

    max_key_len = MAX_REPEAT_KEY_LEN_DEEP if deep_analysis else MAX_REPEAT_KEY_LEN
    candidates.extend(_repeating_xor_candidates(payload, max_key_len))
    candidates.extend(_crib_drag_candidates(payload, max_key_len))

    if xor_key is not None:
        candidates.append(
            {
                "method": f"stream-xor:0x{xor_key:02x}",
                "score": 0.2,
                "preview": _ascii_preview(payload),
                "notes": "payload already extracted after stream XOR",
            }
        )

    candidates.sort(key=lambda c: c.get("score", 0.0), reverse=True)
    return candidates[:MAX_CANDIDATES]


def _repeating_xor_candidates(payload: bytes, max_key_len: int) -> List[Dict[str, Any]]:
    candidates: List[Dict[str, Any]] = []
    if not payload:
        return candidates

    sample = payload[:MAX_REPEAT_SAMPLE_BYTES]
    for key_len in range(2, max_key_len + 1):
        if len(sample) < key_len * 2:
            continue
        key_bytes = bytearray()
        for offset in range(key_len):
            chunk = sample[offset::key_len]
            best_score = -1.0
            best_key = 0
            for key in range(256):
                decoded = bytes(b ^ key for b in chunk)
                text, _ = _decode_text(decoded)
                score = _english_score(text)
                if score > best_score:
                    best_score = score
                    best_key = key
            key_bytes.append(best_key)

        decoded = bytes(b ^ key_bytes[i % key_len] for i, b in enumerate(payload))
        text, ratio = _decode_text(decoded)
        flag = any(pat in text.lower() for pat in ("ctf{", "flag{", "steg{"))
        score = _score_candidate(text, flag)
        candidate = {
            "method": f"xor-repeating:{key_len}",
            "score": score,
            "preview": text[:MAX_PREVIEW] if text else _ascii_preview(decoded),
            "notes": f"derived key={binascii.hexlify(key_bytes).decode()}",
        }
        _apply_hash_hints(candidate, text, len(decoded))
        candidate["score"] = round(float(candidate.get("score", 0.0)), 3)
        candidates.append(candidate)

    candidates.sort(key=lambda c: c.get("score", 0.0), reverse=True)
    return candidates[:MAX_CANDIDATES]


def _crib_drag_candidates(payload: bytes, max_key_len: int) -> List[Dict[str, Any]]:
    candidates: List[Dict[str, Any]] = []
    if not payload:
        return candidates
    sample = payload[:MAX_REPEAT_SAMPLE_BYTES]
    for key_len in range(2, max_key_len + 1):
        if len(sample) < key_len * 2:
            continue
        for pattern in PATTERNS:
            offset_limit = max(1, len(sample) - len(pattern) + 1)
            max_offsets = MAX_CRIB_OFFSETS_DEEP if max_key_len > MAX_REPEAT_KEY_LEN else MAX_CRIB_OFFSETS
            stride = max(1, offset_limit // max_offsets)
            for offset in range(0, offset_limit, stride):
                key = [None] * key_len
                valid = True
                for i, b in enumerate(pattern):
                    idx = (offset + i) % key_len
                    val = sample[offset + i] ^ b
                    if key[idx] is None:
                        key[idx] = val
                    elif key[idx] != val:
                        valid = False
                        break
                if not valid:
                    continue
                if all(k is None for k in key):
                    continue
                filled = bytes(k if k is not None else 0 for k in key)
                decoded = bytes(b ^ filled[i % key_len] for i, b in enumerate(payload))
                text, ratio = _decode_text(decoded)
                flag = any(pat in text.lower() for pat in ("ctf{", "flag{", "steg{"))
                score = _score_candidate(text, flag) + 0.15
                candidate = {
                    "method": f"crib:{pattern.decode('ascii')}:len{key_len}",
                    "score": score,
                    "preview": text[:MAX_PREVIEW] if text else _ascii_preview(decoded),
                    "notes": f"offset={offset} key={binascii.hexlify(filled).decode()}",
                }
                _apply_hash_hints(candidate, text, len(decoded))
                candidate["score"] = round(float(candidate.get("score", 0.0)), 3)
                candidates.append(candidate)
            if len(candidates) >= MAX_CANDIDATES:
                break
        if len(candidates) >= MAX_CANDIDATES:
            break
    candidates.sort(key=lambda c: c.get("score", 0.0), reverse=True)
    return candidates[:MAX_CANDIDATES]


def _export_payload_artifacts(
    output_dir: Path, payload_blobs: List[bytes]
) -> Tuple[List[Dict[str, str]], List[str]]:
    artifacts: List[Dict[str, str]] = []
    notes: List[str] = []
    if not payload_blobs:
        return artifacts, notes
    payload_dir = output_dir / "payload_unwrap"
    payload_dir.mkdir(parents=True, exist_ok=True)
    payload_files: List[Path] = []
    for idx, payload in enumerate(payload_blobs):
        file_path = payload_dir / f"payload_{idx}.bin"
        file_path.write_bytes(payload)
        payload_files.append(file_path)
    if not payload_files:
        return artifacts, notes
    seven_zip = which("7z")
    if not seven_zip:
        notes.append("7z not available; payload files saved under payload_unwrap/")
        return artifacts, notes
    archive_path = payload_dir / "payloads.7z"
    try:
        subprocess.run(
            [seven_zip, "a", "-t7z", "-y", archive_path.name]
            + [path.name for path in payload_files],
            cwd=payload_dir,
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        artifacts.append({"type": "archive", "name": archive_path.name})
    except Exception as exc:
        notes.append(f"7z archive failed: {exc}")
    return artifacts, notes


def analyze_payload_unwrap(
    input_img: Path,
    output_dir: Path,
    *,
    deep_analysis: bool = False,
) -> None:
    if not input_img.exists():
        update_data(
            output_dir,
            {"payload_unwrap": {"status": "error", "error": f"Input image not found: {input_img}"}},
        )
        return

    try:
        img = Image.open(input_img)
    except Exception as exc:
        update_data(
            output_dir,
            {
                "payload_unwrap": {
                    "status": "error",
                    "error": f"Failed to open image: {exc}",
                }
            },
        )
        return

    max_bytes = MAX_PAYLOAD_BYTES_DEEP if deep_analysis else MAX_PAYLOAD_BYTES_LIGHT
    payloads: List[Dict[str, Any]] = []
    payload_blobs: List[bytes] = []

    for label, blob in _iter_streams(img, deep_analysis, max_bytes):
        if not blob:
            continue
        found = _find_payload(blob)
        xor_key = None
        if not found:
            found = _find_payload_xor(blob)
        if not found:
            continue
        start, end, raw_payload, xor_key, pattern = found
        prefix_length = len(pattern.encode("ascii"))
        payload_bytes = (
            raw_payload[prefix_length:-1]
            if raw_payload.endswith(b"}")
            else raw_payload[prefix_length:]
        )
        candidates = _unwrap_payload(payload_bytes, xor_key, deep_analysis=deep_analysis)
        full_b64 = ""
        if payload_bytes and len(payload_bytes) <= MAX_FULL_BASE64:
            full_b64 = base64.b64encode(payload_bytes).decode()
        payloads.append(
            {
                "source": label,
                "pattern": pattern,
                "xor_key": f"0x{xor_key:02x}" if xor_key is not None else None,
                "payload_bytes": len(payload_bytes),
                "payload_hex": binascii.hexlify(payload_bytes[:128]).decode(),
                "payload_base64": base64.b64encode(payload_bytes[:128]).decode(),
                "payload_base64_full": full_b64,
                "candidates": candidates,
            }
        )
        payload_blobs.append(payload_bytes)
        if len(payloads) >= MAX_PAYLOADS:
            break

    status = "ok" if payloads else "no_signal"
    summary = "Unwrapped payload candidates from stego streams."
    if not payloads:
        summary = "No payload wrappers detected for unwrap."

    artifacts, artifact_notes = _export_payload_artifacts(output_dir, payload_blobs)

    update_data(
        output_dir,
        {
            "payload_unwrap": {
                "status": status,
                "summary": summary,
                "confidence": 0.6 if payloads else 0.1,
                "details": {
                    "payloads": payloads,
                    "mode": "deep" if deep_analysis else "auto",
                    "max_bytes": max_bytes,
                    "artifact_notes": artifact_notes,
                },
                "artifacts": artifacts,
                "timing_ms": 0,
            }
        },
    )

"""Nested/recursive steganography decoder (ste.gg 'Matryoshka' mode).

Extracts multiple layers of hidden images/data by repeatedly applying
LSB extraction and checking for embedded image signatures.
"""

from __future__ import annotations

import base64
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from PIL import Image

from .utils import update_data

MAX_DEPTH = 5
MAX_EXTRACT_BYTES = 2_000_000

# Image magic signatures
SIGNATURES: List[Tuple[str, bytes, str]] = [
    ("png", b"\x89PNG\r\n\x1a\n", ".png"),
    ("jpeg", b"\xff\xd8\xff", ".jpg"),
    ("bmp", b"BM", ".bmp"),
]

# LSB extraction configurations: (label, channels, bits_per_channel)
EXTRACT_CONFIGS: List[Tuple[str, List[int], int]] = [
    ("RGB-1bit", [0, 1, 2], 1),
    ("RGBA-1bit", [0, 1, 2, 3], 1),
    ("RGB-2bit", [0, 1, 2], 2),
]


def _extract_raw_bytes(
    arr: np.ndarray, channels: List[int], bits_per_channel: int, max_bytes: int
) -> bytes:
    """Extract raw bytes from LSB planes of the image array."""
    if bits_per_channel <= 0:
        return b""
    bit_mask = (1 << bits_per_channel) - 1
    flat = arr.reshape(-1, arr.shape[2])[:, channels]
    units_needed = int(np.ceil((max_bytes * 8) / bits_per_channel))
    units = (flat & bit_mask).reshape(-1)[:units_needed]

    if units.size == 0:
        return b""

    if bits_per_channel == 1:
        bit_array = units.astype(np.uint8).tolist()
    else:
        bit_array: List[int] = []
        for value in units.tolist():
            for shift in range(bits_per_channel - 1, -1, -1):
                bit_array.append((value >> shift) & 1)

    if not bit_array:
        return b""
    byte_len = (len(bit_array) + 7) // 8
    out = bytearray(byte_len)
    for i, bit in enumerate(bit_array):
        byte_idx = i // 8
        out[byte_idx] = (out[byte_idx] << 1) | bit
    remaining = len(bit_array) % 8
    if remaining:
        out[-1] <<= 8 - remaining
    return bytes(out)[:max_bytes]


def _find_signature(data: bytes) -> Optional[Tuple[str, str, int]]:
    """Search for image magic signatures in the extracted data.

    Returns (format_name, extension, offset) or None.
    """
    for fmt, magic, ext in SIGNATURES:
        offset = data.find(magic)
        if offset != -1:
            return fmt, ext, offset
    return None


def _carve_image(data: bytes, fmt: str, offset: int) -> Optional[bytes]:
    """Attempt to carve out an embedded image from the data starting at offset."""
    stream = data[offset:]
    if not stream:
        return None

    if fmt == "png":
        # Walk PNG chunks to find IEND
        if len(stream) < 8:
            return None
        pos = 8
        while pos + 12 <= len(stream):
            try:
                length = int.from_bytes(stream[pos : pos + 4], "big")
            except Exception:
                return stream  # return what we have
            chunk_type = stream[pos + 4 : pos + 8]
            pos += 8 + length + 4
            if pos > len(stream):
                return stream
            if chunk_type == b"IEND":
                return stream[:pos]
        return stream

    if fmt == "jpeg":
        end = stream.find(b"\xff\xd9")
        if end != -1:
            return stream[: end + 2]
        return stream

    if fmt == "bmp":
        if len(stream) >= 6:
            size = int.from_bytes(stream[2:6], "little")
            if 0 < size <= len(stream):
                return stream[:size]
        return stream

    return stream


def _image_to_data_url(data: bytes, ext: str) -> str:
    """Convert raw image bytes to a base64 data URL."""
    mime_map = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".bmp": "image/bmp",
    }
    mime = mime_map.get(ext, "application/octet-stream")
    b64 = base64.b64encode(data).decode("ascii")
    return f"data:{mime};base64,{b64}"


def _analyze_layer(
    img_path: Path,
    depth: int,
    output_dir: Path,
    results: List[Dict[str, Any]],
) -> None:
    """Recursively extract embedded images from a single layer."""
    if depth > MAX_DEPTH:
        return

    try:
        img = Image.open(img_path).convert("RGBA")
    except Exception:
        return

    arr = np.array(img)

    for config_label, channels, bits in EXTRACT_CONFIGS:
        try:
            raw = _extract_raw_bytes(arr, channels, bits, MAX_EXTRACT_BYTES)
        except Exception:
            continue

        if len(raw) < 8:
            continue

        match = _find_signature(raw)
        if match is None:
            continue

        fmt, ext, offset = match
        carved = _carve_image(raw, fmt, offset)
        if carved is None or len(carved) < 16:
            continue

        # Validate the carved data is actually a loadable image
        try:
            tmp = tempfile.NamedTemporaryFile(suffix=ext, delete=False, dir=str(output_dir))
            tmp_path = Path(tmp.name)
            tmp.write(carved)
            tmp.close()
            Image.open(tmp_path).verify()
        except Exception:
            # Even if it doesn't verify as a valid image, still record the finding
            try:
                tmp_path.unlink(missing_ok=True)
            except Exception:
                pass
            results.append({
                "layer": depth,
                "config": config_label,
                "format": fmt,
                "offset": offset,
                "size_bytes": len(carved),
                "valid_image": False,
                "note": "Signature found but image data could not be verified",
            })
            continue

        # Save the embedded image
        layer_dir = output_dir / "matryoshka"
        layer_dir.mkdir(parents=True, exist_ok=True)
        save_name = f"layer_{depth}_{config_label}_{fmt}{ext}"
        save_path = layer_dir / save_name
        try:
            save_path.write_bytes(carved)
        except Exception:
            pass

        data_url = _image_to_data_url(carved, ext)

        results.append({
            "layer": depth,
            "config": config_label,
            "format": fmt,
            "offset": offset,
            "size_bytes": len(carved),
            "valid_image": True,
            "file": str(save_path.relative_to(output_dir)),
            "data_url": data_url[:200] + "..." if len(data_url) > 200 else data_url,
        })

        # Recurse into the embedded image
        _analyze_layer(tmp_path, depth + 1, output_dir, results)

        # Clean up temp file
        try:
            tmp_path.unlink(missing_ok=True)
        except Exception:
            pass

        # Only process the first successful extraction per config to avoid duplicates
        break


def analyze_matryoshka(input_img: Path, output_dir: Path) -> None:
    """Decode nested/recursive steganography (Matryoshka mode).

    Extracts multiple layers of hidden images by repeatedly applying LSB
    extraction and checking for embedded image signatures.
    """
    if not input_img.exists():
        update_data(
            output_dir,
            {"matryoshka": {"status": "error", "error": f"Input image not found: {input_img}"}},
        )
        return

    results: List[Dict[str, Any]] = []

    try:
        _analyze_layer(input_img, 1, output_dir, results)
    except Exception as exc:
        update_data(
            output_dir,
            {"matryoshka": {"status": "error", "error": f"Analysis failed: {exc}"}},
        )
        return

    if results:
        max_depth_found = max(r["layer"] for r in results)
        update_data(
            output_dir,
            {
                "matryoshka": {
                    "status": "ok",
                    "output": {
                        "layers_found": len(results),
                        "max_depth": max_depth_found,
                        "results": results,
                    },
                }
            },
        )
    else:
        update_data(
            output_dir,
            {
                "matryoshka": {
                    "status": "empty",
                    "output": "No nested images detected in LSB planes.",
                }
            },
        )

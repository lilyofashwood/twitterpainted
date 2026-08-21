"""JPEG quantization table analyzer for detecting double compression and steganography."""

import struct
from pathlib import Path
from typing import Dict, List, Any, Optional

import numpy as np
from PIL import Image

from .utils import update_data


# Standard JPEG quantization tables (quality 50-100)
STANDARD_QTABLES = {
    50: np.array([
        [16, 11, 10, 16, 24, 40, 51, 61],
        [12, 12, 14, 19, 26, 58, 60, 55],
        [14, 13, 16, 24, 40, 57, 69, 56],
        [14, 17, 22, 29, 51, 87, 80, 62],
        [18, 22, 37, 56, 68, 109, 103, 77],
        [24, 35, 55, 64, 81, 104, 113, 92],
        [49, 64, 78, 87, 103, 121, 120, 101],
        [72, 92, 95, 98, 112, 100, 103, 99]
    ]),
    75: np.array([
        [8, 6, 5, 8, 12, 20, 26, 31],
        [6, 6, 7, 10, 13, 29, 30, 28],
        [7, 7, 8, 12, 20, 29, 35, 28],
        [7, 9, 11, 15, 26, 44, 40, 31],
        [9, 11, 19, 28, 34, 55, 52, 39],
        [12, 18, 28, 32, 41, 52, 57, 46],
        [25, 32, 39, 44, 52, 61, 60, 51],
        [36, 46, 48, 49, 56, 50, 52, 50]
    ]),
    90: np.array([
        [3, 2, 2, 3, 5, 8, 10, 12],
        [2, 2, 3, 4, 5, 12, 12, 11],
        [3, 3, 3, 5, 8, 11, 14, 11],
        [3, 3, 4, 6, 10, 17, 16, 12],
        [4, 4, 7, 11, 14, 22, 21, 15],
        [5, 7, 11, 13, 16, 21, 23, 18],
        [10, 13, 16, 17, 21, 24, 24, 20],
        [14, 18, 19, 20, 22, 20, 21, 20]
    ]),
}


def analyze_jpeg_qtables(input_img: Path, output_dir: Path) -> None:
    """Analyze JPEG quantization tables for double compression and anomalies."""
    try:
        # Check if JPEG
        with Image.open(input_img) as img:
            if img.format != "JPEG":
                update_data(
                    output_dir,
                    {
                        "jpeg_qtable_analyzer": {
                            "status": "skipped",
                            "reason": f"Not a JPEG image (format: {img.format})",
                        }
                    },
                )
                return

        # Parse JPEG file manually to extract quantization tables
        qtables = _extract_qtables(input_img)

        if not qtables:
            update_data(
                output_dir,
                {
                    "jpeg_qtable_analyzer": {
                        "status": "error",
                        "error": "Could not extract quantization tables",
                    }
                },
            )
            return

        results = {
            "qtables_found": len(qtables),
            "qtables": [q.tolist() for q in qtables],
            "quality_estimate": _estimate_quality(qtables[0]) if qtables else None,
            "double_compression": _detect_double_compression(qtables),
            "standard_match": _match_standard_tables(qtables),
            "anomalies": _detect_anomalies(qtables),
            "verdict": "clean",
        }

        # Determine verdict
        if results["double_compression"]["detected"]:
            results["verdict"] = "suspicious - likely recompressed"
        elif results["anomalies"]["found"]:
            results["verdict"] = "suspicious - non-standard quantization"

        update_data(
            output_dir,
            {
                "jpeg_qtable_analyzer": {
                    "status": "ok",
                    "output": results,
                    "summary": _format_summary(results),
                }
            },
        )
    except Exception as e:
        update_data(
            output_dir,
            {"jpeg_qtable_analyzer": {"status": "error", "error": str(e)}},
        )


def _extract_qtables(jpeg_path: Path) -> List[np.ndarray]:
    """Extract quantization tables from JPEG file."""
    qtables = []

    try:
        with open(jpeg_path, "rb") as f:
            data = f.read()

        # Find DQT (Define Quantization Table) markers (0xFFDB)
        i = 0
        while i < len(data) - 1:
            if data[i] == 0xFF and data[i + 1] == 0xDB:
                # Found DQT marker
                i += 2

                # Read length
                if i + 2 > len(data):
                    break
                length = struct.unpack(">H", data[i : i + 2])[0]
                i += 2

                # Read table data
                table_data = data[i : i + length - 2]

                # Parse tables (can have multiple tables in one DQT)
                offset = 0
                while offset < len(table_data):
                    # First byte: precision (high 4 bits) and table ID (low 4 bits)
                    pq_tq = table_data[offset]
                    precision = (pq_tq >> 4) & 0x0F  # 0 = 8-bit, 1 = 16-bit
                    offset += 1

                    # Read 64 values in zigzag order
                    values = []
                    value_size = 2 if precision == 1 else 1

                    for _ in range(64):
                        if offset + value_size > len(table_data):
                            break

                        if value_size == 2:
                            val = struct.unpack(">H", table_data[offset : offset + 2])[0]
                        else:
                            val = table_data[offset]

                        values.append(val)
                        offset += value_size

                    if len(values) == 64:
                        # Convert to 8x8 matrix (values are in zigzag order)
                        qtable = _dezigzag(values)
                        qtables.append(qtable)

                i += length - 2
            else:
                i += 1

        return qtables
    except Exception:
        return []


def _dezigzag(values: List[int]) -> np.ndarray:
    """Convert zigzag-ordered values to 8x8 matrix."""
    # Zigzag pattern for 8x8 matrix
    zigzag_indices = [
        0, 1, 8, 16, 9, 2, 3, 10, 17, 24, 32, 25, 18, 11, 4, 5,
        12, 19, 26, 33, 40, 48, 41, 34, 27, 20, 13, 6, 7, 14, 21, 28,
        35, 42, 49, 56, 57, 50, 43, 36, 29, 22, 15, 23, 30, 37, 44, 51,
        58, 59, 52, 45, 38, 31, 39, 46, 53, 60, 61, 54, 47, 55, 62, 63
    ]

    matrix = np.zeros(64, dtype=int)
    for i, idx in enumerate(zigzag_indices):
        if i < len(values):
            matrix[idx] = values[i]

    return matrix.reshape(8, 8)


def _estimate_quality(qtable: np.ndarray) -> int:
    """Estimate JPEG quality from quantization table."""
    # Compare with standard tables
    best_match = 50
    best_distance = float("inf")

    for quality, standard in STANDARD_QTABLES.items():
        distance = np.sum(np.abs(qtable - standard))
        if distance < best_distance:
            best_distance = distance
            best_match = quality

    return best_match


def _detect_double_compression(qtables: List[np.ndarray]) -> Dict[str, Any]:
    """Detect signs of double JPEG compression."""
    if not qtables:
        return {"detected": False, "reason": "No tables found"}

    # Check if table values suggest double quantization
    # In double compression, some coefficients show periodic patterns

    qtable = qtables[0]

    # Look for "ladder" pattern in quantization steps
    # This is a simplified check
    row_diffs = []
    for row in qtable:
        diffs = [row[i + 1] - row[i] for i in range(7)]
        row_diffs.extend(diffs)

    # Consistent step sizes suggest double compression
    row_diffs = np.array(row_diffs)
    std_dev = np.std(row_diffs)

    detected = std_dev < 2.0  # Low variance suggests artificial pattern

    return {
        "detected": detected,
        "confidence": "medium" if detected else "low",
        "note": "Double compression indicated by uniform quantization steps" if detected else "No strong indicators",
    }


def _match_standard_tables(qtables: List[np.ndarray]) -> Dict[str, Any]:
    """Check if tables match standard JPEG tables."""
    if not qtables:
        return {"matches_standard": False}

    qtable = qtables[0]
    matches = []

    for quality, standard in STANDARD_QTABLES.items():
        if np.array_equal(qtable, standard):
            matches.append(quality)

    return {
        "matches_standard": len(matches) > 0,
        "quality_matches": matches,
        "note": f"Matches standard quality {matches[0]}" if matches else "Custom quantization table",
    }


def _detect_anomalies(qtables: List[np.ndarray]) -> Dict[str, Any]:
    """Detect anomalies in quantization tables."""
    if not qtables:
        return {"found": False}

    qtable = qtables[0]

    anomalies = []

    # Check for zeros (unusual in standard JPEG)
    if np.any(qtable == 0):
        anomalies.append("Contains zero values (unusual)")

    # Check for very large values (>255)
    if np.any(qtable > 255):
        anomalies.append("Contains values >255 (non-standard)")

    # Check for non-monotonic increases (QT should generally increase)
    # Check first row and column
    first_row = qtable[0, :]
    if not all(first_row[i] <= first_row[i + 1] for i in range(7)):
        anomalies.append("Non-monotonic first row (suspicious)")

    return {
        "found": len(anomalies) > 0,
        "anomalies": anomalies,
    }


def _format_summary(results: Dict[str, Any]) -> str:
    """Format results summary."""
    verdict = results.get("verdict", "unknown")
    quality = results.get("quality_estimate")
    double_comp = results.get("double_compression", {})

    parts = []

    if quality:
        parts.append(f"Estimated quality: ~{quality}")

    if double_comp.get("detected"):
        parts.append("DOUBLE COMPRESSION DETECTED")

    parts.append(verdict)

    return " | ".join(parts)

"""Custom entropy analyzer for detecting steganography through statistical anomalies."""

from pathlib import Path
from typing import Dict, List, Any

import numpy as np
from PIL import Image

from .utils import update_data


def analyze_entropy_anomalies(input_img: Path, output_dir: Path) -> None:
    """Detect steganography through entropy analysis and statistical tests."""
    try:
        img = Image.open(input_img)

        if img.mode not in {"RGB", "RGBA", "L"}:
            img = img.convert("RGBA")

        arr = np.array(img)
        if arr.ndim == 2:
            arr = arr[:, :, None]

        results = {
            "chi_square_tests": _chi_square_analysis(arr),
            "lsb_randomness": _lsb_randomness_test(arr),
            "bit_plane_analysis": _bit_plane_analysis(arr),
            "sample_pair_analysis": _sample_pair_analysis(arr),
            "verdict": "clean",
            "confidence": 0.0,
        }

        # Determine verdict
        suspicious_indicators = 0

        if results["chi_square_tests"]["likely_embedded"]:
            suspicious_indicators += 1

        if results["lsb_randomness"]["suspicious_channels"] > 0:
            suspicious_indicators += 2  # Weighted higher

        if results["sample_pair_analysis"]["anomaly_detected"]:
            suspicious_indicators += 1

        if suspicious_indicators >= 2:
            results["verdict"] = "likely_stego"
            results["confidence"] = min(suspicious_indicators / 4.0, 1.0)
        elif suspicious_indicators == 1:
            results["verdict"] = "suspicious"
            results["confidence"] = 0.4

        update_data(
            output_dir,
            {
                "entropy_analyzer": {
                    "status": "ok",
                    "output": results,
                    "summary": _format_summary(results),
                }
            },
        )
    except Exception as e:
        update_data(
            output_dir,
            {"entropy_analyzer": {"status": "error", "error": str(e)}},
        )


def _chi_square_analysis(arr: np.ndarray) -> Dict[str, Any]:
    """Chi-square test for LSB embedding detection."""
    try:
        chi_scores = []

        for c in range(arr.shape[2]):
            channel = arr[:, :, c].flatten()

            # Get LSB
            lsb = channel & 1

            # Expected 50/50 distribution for random LSBs
            observed_0 = np.sum(lsb == 0)
            observed_1 = np.sum(lsb == 1)
            expected = len(lsb) / 2

            # Chi-square statistic
            chi_square = ((observed_0 - expected) ** 2 + (observed_1 - expected) ** 2) / expected
            chi_scores.append(float(chi_square))

        # Threshold: chi-square > 3.84 indicates p < 0.05
        likely_embedded = any(score > 3.84 for score in chi_scores)

        return {
            "chi_square_scores": chi_scores,
            "likely_embedded": likely_embedded,
            "max_score": float(max(chi_scores)) if chi_scores else 0.0,
        }
    except Exception:
        return {"chi_square_scores": [], "likely_embedded": False, "max_score": 0.0}


def _lsb_randomness_test(arr: np.ndarray) -> Dict[str, Any]:
    """Test LSB randomness - true random should have entropy ~1.0."""
    try:
        lsb_entropies = []
        suspicious_count = 0

        for c in range(arr.shape[2]):
            channel = arr[:, :, c].flatten()
            lsb = channel & 1

            # Calculate entropy
            hist, _ = np.histogram(lsb, bins=2, range=(0, 2))
            hist = hist[hist > 0]
            probs = hist / hist.sum()
            entropy = -np.sum(probs * np.log2(probs))
            lsb_entropies.append(float(entropy))

            # Flag if entropy > 0.98 (very random, likely embedded data)
            if entropy > 0.98:
                suspicious_count += 1

        return {
            "lsb_entropies": lsb_entropies,
            "suspicious_channels": suspicious_count,
            "max_entropy": float(max(lsb_entropies)) if lsb_entropies else 0.0,
        }
    except Exception:
        return {"lsb_entropies": [], "suspicious_channels": 0, "max_entropy": 0.0}


def _bit_plane_analysis(arr: np.ndarray) -> Dict[str, Any]:
    """Analyze each bit plane for unusual patterns."""
    try:
        bit_plane_entropies = []

        for c in range(min(arr.shape[2], 3)):  # R, G, B
            channel = arr[:, :, c]
            channel_bits = []

            # Analyze bits 0-7
            for bit in range(8):
                bit_plane = (channel >> bit) & 1
                hist, _ = np.histogram(bit_plane.flatten(), bins=2, range=(0, 2))
                hist = hist[hist > 0]
                probs = hist / hist.sum()
                entropy = -np.sum(probs * np.log2(probs))
                channel_bits.append(float(entropy))

            bit_plane_entropies.append(channel_bits)

        return {
            "bit_plane_entropies": bit_plane_entropies,
            "analysis": "Lower bit planes should have higher entropy in natural images",
        }
    except Exception:
        return {"bit_plane_entropies": [], "analysis": "Analysis failed"}


def _sample_pair_analysis(arr: np.ndarray) -> Dict[str, Any]:
    """Sample Pair Analysis (SPA) for LSB embedding detection."""
    try:
        # Simplified SPA - check for pairs of pixels
        # In LSB stego, neighboring pixels often have similar LSBs

        anomaly_detected = False
        similarity_scores = []

        for c in range(arr.shape[2]):
            channel = arr[:, :, c]

            # Get horizontal pairs
            pairs_left = channel[:, :-1]
            pairs_right = channel[:, 1:]

            # LSB of pairs
            lsb_left = pairs_left & 1
            lsb_right = pairs_right & 1

            # Count matching LSBs
            matches = np.sum(lsb_left == lsb_right)
            total = lsb_left.size

            similarity = matches / total
            similarity_scores.append(float(similarity))

            # Natural images: ~50% similarity
            # LSB stego: can be higher (>55%) or lower (<45%)
            if similarity > 0.55 or similarity < 0.45:
                anomaly_detected = True

        return {
            "similarity_scores": similarity_scores,
            "anomaly_detected": anomaly_detected,
            "note": "Natural images typically have ~50% LSB similarity between adjacent pixels",
        }
    except Exception:
        return {
            "similarity_scores": [],
            "anomaly_detected": False,
            "note": "Analysis failed",
        }


def _format_summary(results: Dict[str, Any]) -> str:
    """Format results as summary string."""
    verdict = results.get("verdict", "unknown")
    confidence = results.get("confidence", 0.0)

    if verdict == "likely_stego":
        return f"Likely contains steganography (confidence: {confidence:.0%})"
    elif verdict == "suspicious":
        return f"Suspicious indicators detected (confidence: {confidence:.0%})"
    else:
        return "No strong statistical indicators of steganography detected"

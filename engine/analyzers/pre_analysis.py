"""Pre-analysis module for image quality assessment and smart tool selection."""

import subprocess
from pathlib import Path
from typing import Dict, Any, List

import numpy as np
from PIL import Image

from .utils import update_data


def analyze_pre_scan(input_img: Path, output_dir: Path) -> None:
    """Run comprehensive pre-analysis to guide tool selection."""
    try:
        img = Image.open(input_img)

        results = {
            "file_type": _detect_format(input_img),
            "dimensions": {"width": img.width, "height": img.height},
            "mode": img.mode,
            "quality_score": _assess_image_quality(img),
            "entropy_analysis": _analyze_entropy(img),
            "compression_artifacts": _detect_compression_artifacts(img),
            "recommended_tools": [],
            "priority": "normal",
        }

        # Smart tool recommendations
        results["recommended_tools"] = _recommend_tools(results)

        # Set priority based on findings
        if results["entropy_analysis"]["suspicious_regions"] > 0:
            results["priority"] = "high"
        elif results["quality_score"] > 0.85:
            results["priority"] = "high"

        update_data(
            output_dir,
            {
                "pre_analysis": {
                    "status": "ok",
                    "output": results,
                    "summary": _generate_summary(results),
                }
            },
        )
    except Exception as e:
        update_data(
            output_dir,
            {"pre_analysis": {"status": "error", "error": str(e)}},
        )


def _detect_format(image_path: Path) -> str:
    """Detect precise image format."""
    try:
        with Image.open(image_path) as img:
            return img.format or "unknown"
    except Exception:
        return "unknown"


def _assess_image_quality(img: Image.Image) -> float:
    """Assess image quality (0.0 = low, 1.0 = high)."""
    try:
        # Convert to RGB for analysis
        if img.mode != "RGB":
            img_rgb = img.convert("RGB")
        else:
            img_rgb = img

        arr = np.array(img_rgb)

        # Check for compression artifacts (JPEG blocking)
        variance = np.var(arr)

        # Higher variance = less compression
        # Normalize to 0-1 range (variance typically 0-10000)
        quality_score = min(variance / 10000.0, 1.0)

        return float(quality_score)
    except Exception:
        return 0.5


def _analyze_entropy(img: Image.Image) -> Dict[str, Any]:
    """Analyze entropy per channel to detect hidden data."""
    try:
        if img.mode == "RGB":
            arr = np.array(img)
        elif img.mode == "RGBA":
            arr = np.array(img)
        elif img.mode == "L":
            arr = np.array(img)
            arr = arr[:, :, None]  # Add channel dimension
        else:
            arr = np.array(img.convert("RGB"))

        if arr.ndim == 2:
            arr = arr[:, :, None]

        channel_entropy = []
        lsb_entropy = []

        for c in range(arr.shape[2]):
            channel = arr[:, :, c]

            # Channel entropy
            hist, _ = np.histogram(channel.flatten(), bins=256, range=(0, 256))
            hist = hist[hist > 0]
            probs = hist / hist.sum()
            entropy = -np.sum(probs * np.log2(probs))
            channel_entropy.append(float(entropy))

            # LSB entropy (should be ~1.0 for random data)
            lsb = channel & 1
            lsb_hist, _ = np.histogram(lsb.flatten(), bins=2, range=(0, 2))
            lsb_hist = lsb_hist[lsb_hist > 0]
            lsb_probs = lsb_hist / lsb_hist.sum()
            lsb_ent = -np.sum(lsb_probs * np.log2(lsb_probs))
            lsb_entropy.append(float(lsb_ent))

        # Flag suspicious if LSB entropy > 0.95 (very random)
        suspicious_count = sum(1 for e in lsb_entropy if e > 0.95)

        return {
            "channel_entropy": channel_entropy,
            "lsb_entropy": lsb_entropy,
            "suspicious_regions": suspicious_count,
            "max_entropy": float(max(channel_entropy)) if channel_entropy else 0.0,
        }
    except Exception:
        return {
            "channel_entropy": [],
            "lsb_entropy": [],
            "suspicious_regions": 0,
            "max_entropy": 0.0,
        }


def _detect_compression_artifacts(img: Image.Image) -> Dict[str, Any]:
    """Detect if image has been recompressed."""
    try:
        # Check if JPEG
        if img.format == "JPEG":
            # Look for double compression indicators
            # This is a simplified check - full analysis would use DCT coefficients
            return {
                "format": "JPEG",
                "likely_recompressed": False,  # Placeholder
                "note": "Full DCT analysis available in jpeg_qtable_analyzer",
            }
        else:
            return {
                "format": img.format or "unknown",
                "likely_recompressed": False,
            }
    except Exception:
        return {"format": "unknown", "likely_recompressed": False}


def _recommend_tools(analysis: Dict[str, Any]) -> List[str]:
    """Recommend tools based on pre-analysis."""
    tools = []

    file_type = analysis.get("file_type", "").upper()
    quality = analysis.get("quality_score", 0.0)
    entropy = analysis.get("entropy_analysis", {})

    # High-quality PNG → LSB methods likely
    if file_type == "PNG" and quality > 0.8:
        tools.extend(["lsb", "advanced_lsb", "plane_carver", "png_chunks", "zsteg"])

    # JPEG → DCT/F5 methods
    if file_type == "JPEG":
        tools.extend(["f5", "dct", "jpeg_qtable_analyzer", "steghide", "jsteg"])

    # High LSB entropy → statistical analysis
    if entropy.get("suspicious_regions", 0) > 0:
        tools.extend(["stegexpose", "entropy_analyzer"])

    # Always include basics
    tools.extend(["exiftool", "binwalk", "strings"])

    return list(dict.fromkeys(tools))  # Remove duplicates, preserve order


def _generate_summary(analysis: Dict[str, Any]) -> str:
    """Generate human-readable summary."""
    file_type = analysis.get("file_type", "unknown")
    quality = analysis.get("quality_score", 0.0)
    entropy = analysis.get("entropy_analysis", {})
    suspicious = entropy.get("suspicious_regions", 0)

    summary_parts = []
    summary_parts.append(f"{file_type} image")

    if quality > 0.85:
        summary_parts.append("high quality (good for LSB)")
    elif quality > 0.5:
        summary_parts.append("medium quality")
    else:
        summary_parts.append("low quality (likely compressed)")

    if suspicious > 0:
        summary_parts.append(f"{suspicious} channel(s) with high LSB entropy (suspicious)")

    return ", ".join(summary_parts)

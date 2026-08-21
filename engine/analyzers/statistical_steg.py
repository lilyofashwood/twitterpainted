"""Aggregate statistical steganalysis using StegExpose.

Aletheia has a dedicated analyzer because its model and dependency readiness
cannot be represented honestly as a fallback inside this aggregate result.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from tempfile import TemporaryDirectory
from pathlib import Path
from typing import Dict, Any

from .utils import MAX_PENDING_TIME, update_data


def analyze_statistical_steg(
    input_img: Path,
    output_dir: Path,
    deep_analysis: bool = False
) -> None:
    """Run statistical steganalysis using available tools."""
    if not deep_analysis:
        update_data(
            output_dir,
            {
                "statistical_steg": {
                    "status": "skipped",
                    "reason": "Enable deep analysis to run statistical steganalysis",
                }
            },
        )
        return

    try:
        results = {"stegexpose": None, "verdict": "unknown"}

        # Try stegexpose
        if shutil.which("stegexpose"):
            results["stegexpose"] = _run_stegexpose(input_img, output_dir)

        # Determine verdict
        if results["stegexpose"]:
            verdicts = [
                result.get("verdict", "unknown")
                for result in (results["stegexpose"],)
                if result
            ]

            if "stego_detected" in verdicts or "likely_stego" in verdicts:
                results["verdict"] = "likely_stego"
            elif "suspicious" in verdicts:
                results["verdict"] = "suspicious"
            elif verdicts and all(verdict == "clean" for verdict in verdicts):
                results["verdict"] = "clean"
            elif verdicts and all(verdict in {"error", "timeout"} for verdict in verdicts):
                results["verdict"] = "error"
            else:
                results["verdict"] = "unknown"
        else:
            results["verdict"] = "no_tools_available"
            results["note"] = (
                "Install StegExpose for this aggregate pass, or select the dedicated "
                "Aletheia analyzer."
            )

        result_status = "ok"
        if results["verdict"] == "no_tools_available":
            result_status = "skipped"
        elif results["verdict"] == "error":
            result_status = "error"

        update_data(
            output_dir,
            {
                "statistical_steg": {
                    "status": result_status,
                    "output": results,
                    "summary": _format_summary(results),
                }
            },
        )
    except Exception as e:
        update_data(
            output_dir,
            {"statistical_steg": {"status": "error", "error": str(e)}},
        )


def _run_stegexpose(input_img: Path, output_dir: Path) -> Dict[str, Any]:
    """Run stegexpose steganalysis."""
    try:
        # StegExpose accepts a directory, not a single carrier path.
        with TemporaryDirectory(prefix="twitterpainted-stegexpose-") as temp_dir:
            scan_dir = Path(temp_dir)
            shutil.copy2(input_img, scan_dir / input_img.name)
            result = subprocess.run(
                ["stegexpose", str(scan_dir)],
                capture_output=True,
                text=True,
                timeout=MAX_PENDING_TIME,
                check=False,
            )

        output = result.stdout + result.stderr
        verdict, hidden_bytes = _parse_stegexpose_output(output, result.returncode)

        return {
            "tool": "stegexpose",
            "verdict": verdict,
            "estimated_hidden_bytes": hidden_bytes,
            "returncode": result.returncode,
            "raw_output": output[:500],
        }
    except subprocess.TimeoutExpired:
        return {
            "tool": "stegexpose",
            "verdict": "timeout",
            "error": f"Timed out after {MAX_PENDING_TIME} seconds",
        }
    except Exception as e:
        return {
            "tool": "stegexpose",
            "verdict": "error",
            "error": str(e),
        }


def _parse_stegexpose_output(output: str, returncode: int) -> tuple[str, int | None]:
    """Parse StegExpose's per-file prose without treating failures as clean."""
    lower = output.lower()
    hidden_match = re.search(r"hidden data is\s+(\d+)\s+bytes", lower)
    hidden_bytes = int(hidden_match.group(1)) if hidden_match else None

    if returncode != 0 or "exception in thread" in lower:
        return "error", hidden_bytes
    if " is suspicious" in lower:
        return "suspicious", hidden_bytes
    if " is clean" in lower or "not suspicious" in lower:
        return "clean", hidden_bytes
    return "unknown", hidden_bytes


def _format_summary(results: Dict[str, Any]) -> str:
    """Format summary of statistical analysis."""
    verdict = results.get("verdict", "unknown")

    if verdict == "likely_stego":
        return "Statistical analysis indicates likely steganography"
    elif verdict == "suspicious":
        return "Statistical tests show suspicious indicators"
    elif verdict == "clean":
        return "Statistical analysis shows no strong indicators"
    elif verdict == "no_tools_available":
        return "Statistical analysis tool not installed (install StegExpose or select Aletheia)"
    elif verdict == "error":
        return "Statistical analysis tool failed"
    else:
        return f"Statistical analysis: {verdict}"

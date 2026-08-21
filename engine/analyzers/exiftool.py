"""Exiftool Analyzer for Image Submissions."""

import subprocess
from pathlib import Path

from .utils import MAX_PENDING_TIME, update_data


def analyze_exiftool(input_img: Path, output_dir: Path) -> None:
    """Analyze an image submission using exiftool."""

    try:
        try:
            data = subprocess.run(
                ["exiftool", input_img],
                capture_output=True,
                text=True,
                check=True,
                timeout=MAX_PENDING_TIME,
            )
        except subprocess.TimeoutExpired:
            update_data(
                output_dir,
                {
                    "exiftool": {
                        "status": "error",
                        "error": f"Exiftool timed out after {MAX_PENDING_TIME} seconds. Consider increasing MAX_PENDING_TIME environment variable.",
                    }
                },
            )
            return
        except subprocess.CalledProcessError as e:
            update_data(
                output_dir,
                {
                    "exiftool": {
                        "status": "error",
                        "error": f"Exiftool failed with exit code {e.returncode}: {e.stderr}",
                    }
                },
            )
            return

        if data.stderr:
            update_data(
                output_dir, {"exiftool": {"status": "error", "error": data.stderr}}
            )
            return

        metadata: dict[str, str] = {}
        for line in data.stdout.split("\n"):
            if ":" in line:
                key, value = line.split(":", 1)
                metadata[key.strip()] = value.strip()

        # exiftool_dir = output_dir / "exiftool"
        # exiftool_dir.mkdir(parents=True, exist_ok=True)
        # update_data(exiftool_dir, metadata, "data.json")

        update_data(
            output_dir,
            {"exiftool": {"status": "ok", "output": metadata}},
        )
    except Exception as e:
        update_data(output_dir, {"exiftool": {"status": "error", "error": str(e)}})

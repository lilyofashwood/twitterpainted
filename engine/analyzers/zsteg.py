"""Zsteg Analyzer for Image Submissions."""

import shutil
import subprocess
from pathlib import Path

from PIL import Image

from .utils import MAX_PENDING_TIME, update_data


def analyze_zsteg(input_img: Path, output_dir: Path) -> None:
    """Analyze an image submission using zsteg."""

    try:
        with Image.open(input_img) as image:
            image_format = (image.format or "").upper()
    except Exception as exc:
        update_data(output_dir, {"zsteg": {"status": "error", "error": str(exc)}})
        return

    if image_format not in {"PNG", "BMP"}:
        update_data(
            output_dir,
            {
                "zsteg": {
                    "status": "skipped",
                    "reason": f"zsteg supports PNG/BMP carriers, not {image_format or 'this format'}.",
                }
            },
        )
        return

    if shutil.which("file") is None:
        update_data(
            output_dir,
            {
                "zsteg": {
                    "status": "skipped",
                    "error": "zsteg requires the 'file' utility; install package 'file'.",
                }
            },
        )
        return

    try:
        try:
            data = subprocess.run(
                ["zsteg", input_img],
                capture_output=True,
                text=True,
                check=False,
                timeout=MAX_PENDING_TIME,
            )
        except subprocess.TimeoutExpired:
            update_data(
                output_dir,
                {
                    "zsteg": {
                        "status": "error",
                        "error": f"Zsteg timed out after {MAX_PENDING_TIME} seconds. Consider increasing MAX_PENDING_TIME environment variable.",
                    }
                },
            )
            return
        if data.stderr or "PNG::NotSupported" in data.stdout[:100]:
            error_msg = data.stderr or data.stdout
            update_data(output_dir, {"zsteg": {"status": "error", "error": error_msg}})
            return

        # zsteg_dir = output_dir / "zsteg"
        # zsteg_dir.mkdir(parents=True, exist_ok=True)
        # with open(zsteg_dir / "zsteg.txt", "w", encoding="utf-8") as f:
        #     subprocess.run(["zsteg", input_img], stdout=f, check=True)

        update_data(
            output_dir,
            {
                "zsteg": {
                    "status": "ok",
                    "output": data.stdout.split("\n") if data else [],
                }
            },
        )
    except Exception as e:
        update_data(output_dir, {"zsteg": {"status": "error", "error": str(e)}})

"""Optional adapters for research-grade image steganalysis backends.

The project deliberately does not vendor model weights or research code here.
Every adapter either executes a configured backend against the uploaded carrier
and validates its output, or reports exactly which runtime/model input is
missing.  A successful capability probe is never presented as an analysis.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import shlex
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Iterable, Optional

import numpy as np
from PIL import Image

from .utils import MAX_PENDING_TIME, update_data


ALETHEIA_SOURCE = "https://github.com/daniellerch/aletheia"
ALETHEIA_LICENSE = f"{ALETHEIA_SOURCE}/blob/master/LICENSE.txt"

RESEARCH_BACKENDS: dict[str, dict[str, str]] = {
    "aletheia": {
        "label": "aletheia auto",
        "source_url": ALETHEIA_SOURCE,
        "license": "MIT; model and external dependency terms may also apply",
        "license_url": ALETHEIA_LICENSE,
    },
    "srnet": {
        "label": "srnet",
        "source_url": ALETHEIA_SOURCE,
        "license": "MIT adapter; configured checkpoint terms also apply",
        "license_url": ALETHEIA_LICENSE,
    },
    "siastegnet": {
        "label": "siastegnet",
        "source_url": "https://github.com/SiaStg/SiaStegNet",
        "license": "no upstream license file identified; do not redistribute its code or weights without permission",
        "license_url": "https://github.com/SiaStg/SiaStegNet",
    },
    "xunet": {
        "label": "xu-net",
        "source_url": "https://github.com/GuanshuoXu/caffe_deep_learning_for_steganalysis",
        "license": "upstream Caffe-derived license; configured checkpoint terms also apply",
        "license_url": "https://github.com/GuanshuoXu/caffe_deep_learning_for_steganalysis/blob/master/LICENSE",
    },
    "dctr": {
        "label": "dctr features",
        "source_url": ALETHEIA_SOURCE,
        "license": "MIT Aletheia integration; external Octave feature code terms may also apply",
        "license_url": ALETHEIA_LICENSE,
    },
    "gfr": {
        "label": "gfr features",
        "source_url": ALETHEIA_SOURCE,
        "license": "MIT Aletheia integration; external Octave feature code terms may also apply",
        "license_url": ALETHEIA_LICENSE,
    },
    "maxsrmd2": {
        "label": "maxsrmd2 features",
        "source_url": "https://dde.binghamton.edu/download/feature_extractors/",
        "license": "no redistributable upstream license identified; supply a locally authorized runner",
        "license_url": "https://dde.binghamton.edu/download/feature_extractors/",
    },
    "stegspy": {
        "label": "stegspy",
        "source_url": "https://www.spy-hunter.com/stegspydownload.htm",
        "license": "copyrighted historical binary with upstream download terms; not redistributed",
        "license_url": "https://www.spy-hunter.com/stegspydownload.htm",
    },
}

RESEARCH_ANALYZER_IDS = frozenset(RESEARCH_BACKENDS)

_OUTPUT_LIMIT = 8000
_ERROR_MARKERS = ("traceback", "exception", "fatal error", "segmentation fault")


def _provenance(analyzer_id: str) -> dict[str, str]:
    backend = RESEARCH_BACKENDS[analyzer_id]
    return {
        "source_url": backend["source_url"],
        "license": backend["license"],
        "license_url": backend["license_url"],
    }


def _record(
    output_dir: Path,
    analyzer_id: str,
    *,
    status: str,
    summary: str,
    output: Optional[object] = None,
    error: Optional[str] = None,
    reason: Optional[str] = None,
    details: Optional[dict[str, Any]] = None,
    confidence: Optional[float] = None,
) -> None:
    payload: dict[str, Any] = {
        "status": status,
        "label": RESEARCH_BACKENDS[analyzer_id]["label"],
        "summary": summary,
        "provenance": _provenance(analyzer_id),
    }
    if output is not None:
        payload["output"] = output
    if error:
        payload["error"] = error
    if reason:
        payload["reason"] = reason
    if details:
        payload["details"] = details
    if confidence is not None:
        payload["confidence"] = round(float(confidence), 6)
    update_data(output_dir, {analyzer_id: payload})


def _truncate(value: str) -> str:
    value = value.strip()
    if len(value) <= _OUTPUT_LIMIT:
        return value
    return f"{value[:_OUTPUT_LIMIT]}... (truncated)"


def _image_format(input_img: Path) -> str:
    try:
        with Image.open(input_img) as image:
            return str(image.format or "").upper()
    except Exception:
        return ""


def _validate_input(input_img: Path, output_dir: Path, analyzer_id: str) -> bool:
    if not input_img.is_file():
        _record(
            output_dir,
            analyzer_id,
            status="error",
            summary="carrier is unavailable",
            error=f"Input image not found: {input_img}",
        )
        return False
    if not _image_format(input_img):
        _record(
            output_dir,
            analyzer_id,
            status="skipped",
            summary="backend accepts image carriers only",
            reason="Uploaded file is not a readable image.",
        )
        return False
    return True


def _resolve_command(
    env_name: str,
    candidates: Iterable[str] = (),
) -> Optional[list[str]]:
    configured = os.getenv(env_name, "").strip()
    if configured:
        try:
            parts = shlex.split(configured)
        except ValueError:
            return None
        if not parts:
            return None
        executable = shutil.which(parts[0])
        if executable:
            parts[0] = executable
            return parts
        path = Path(parts[0]).expanduser()
        if path.is_file():
            resolved = str(path.resolve())
            if path.suffix.lower() == ".py" and not os.access(path, os.X_OK):
                return [sys.executable, resolved, *parts[1:]]
            parts[0] = resolved
            return parts
        return None

    for candidate in candidates:
        executable = shutil.which(candidate)
        if executable:
            return [executable]
    return None


def _aletheia_command() -> Optional[list[str]]:
    return _resolve_command(
        "TWITTERPAINTED_ALETHEIA_COMMAND",
        ("aletheia.py", "aletheia"),
    )


def _run(command: list[str]) -> tuple[Optional[subprocess.CompletedProcess[str]], Optional[str]]:
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            errors="replace",
            timeout=MAX_PENDING_TIME,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return None, f"backend timed out after {MAX_PENDING_TIME} seconds"
    except OSError as exc:
        return None, f"could not start backend: {exc}"
    except Exception as exc:  # pragma: no cover - defensive boundary
        return None, str(exc)
    return result, None


def _combined_output(result: subprocess.CompletedProcess[str]) -> str:
    return "\n".join(value for value in (result.stdout, result.stderr) if value).strip()


def _command_failed(result: subprocess.CompletedProcess[str], output: str) -> bool:
    lowered = output.lower()
    return result.returncode != 0 or any(marker in lowered for marker in _ERROR_MARKERS)


def analyze_aletheia(input_img: Path, output_dir: Path) -> None:
    """Run Aletheia's real automatic detector table on one staged carrier."""
    analyzer_id = "aletheia"
    if not _validate_input(input_img, output_dir, analyzer_id):
        return
    command = _aletheia_command()
    if not command:
        _record(
            output_dir,
            analyzer_id,
            status="skipped",
            summary="aletheia runtime is not configured",
            reason=(
                "Install Aletheia and its model/external dependencies, or set "
                "TWITTERPAINTED_ALETHEIA_COMMAND. Twitterpainted does not prefetch "
                "models or dependencies; the separately installed Aletheia backend may "
                "perform its own documented downloads when invoked."
            ),
        )
        return

    with TemporaryDirectory(prefix="twitterpainted-aletheia-") as temp_dir:
        scan_dir = Path(temp_dir)
        staged = scan_dir / input_img.name
        shutil.copy2(input_img, staged)
        result, launch_error = _run([*command, "auto", str(scan_dir)])

    if launch_error or result is None:
        _record(
            output_dir,
            analyzer_id,
            status="error",
            summary="aletheia could not complete",
            error=launch_error or "unknown launch error",
        )
        return
    raw = _combined_output(result)
    if _command_failed(result, raw):
        _record(
            output_dir,
            analyzer_id,
            status="error",
            summary="aletheia failed while analyzing the carrier",
            error=_truncate(raw) or f"Aletheia exited with code {result.returncode}",
        )
        return

    report_lines = [line.strip() for line in raw.splitlines() if input_img.name in line]
    if not report_lines:
        _record(
            output_dir,
            analyzer_id,
            status="error",
            summary="aletheia returned no per-carrier detector result",
            error=_truncate(raw) or "Aletheia produced no output.",
        )
        return

    _record(
        output_dir,
        analyzer_id,
        status="ok",
        summary="aletheia completed its trained detector table; scores remain model-domain dependent",
        output=report_lines[:12],
        details={"returncode": result.returncode, "result_lines": len(report_lines)},
    )


def _configured_file(env_name: str) -> tuple[Optional[Path], str]:
    configured = os.getenv(env_name, "").strip()
    if not configured:
        return None, f"{env_name} is not set"
    path = Path(configured).expanduser()
    if not path.is_file():
        return None, f"{env_name} does not point to a readable file"
    return path.resolve(), ""


def _parse_probability_line(raw: str, image_name: str) -> Optional[float]:
    for line in reversed(raw.splitlines()):
        if image_name not in line:
            continue
        match = re.search(r"(?:^|\s)(0(?:\.\d+)?|1(?:\.0+)?)\s*$", line.strip())
        if match:
            value = float(match.group(1))
            if 0.0 <= value <= 1.0:
                return value
    return None


def analyze_srnet(input_img: Path, output_dir: Path) -> None:
    """Run Aletheia SRNet inference with an explicitly supplied checkpoint."""
    analyzer_id = "srnet"
    if not _validate_input(input_img, output_dir, analyzer_id):
        return
    command = _aletheia_command()
    model, model_error = _configured_file("TWITTERPAINTED_SRNET_MODEL")
    if not command or model is None:
        missing = []
        if not command:
            missing.append("Aletheia runtime (TWITTERPAINTED_ALETHEIA_COMMAND)")
        if model is None:
            missing.append(model_error)
        _record(
            output_dir,
            analyzer_id,
            status="skipped",
            summary="srnet inference is not ready",
            reason=(
                "; ".join(missing)
                + ". Twitterpainted does not fetch checkpoints; separately installed "
                "backends may manage resources according to their own documentation."
            ),
        )
        return

    result, launch_error = _run(
        [*command, "srnet-predict", str(input_img), str(model), "CPU"]
    )
    if launch_error or result is None:
        _record(
            output_dir,
            analyzer_id,
            status="error",
            summary="srnet could not complete",
            error=launch_error or "unknown launch error",
        )
        return
    raw = _combined_output(result)
    probability = _parse_probability_line(raw, input_img.name)
    if _command_failed(result, raw) or probability is None:
        _record(
            output_dir,
            analyzer_id,
            status="error",
            summary="srnet did not return a validated probability",
            error=_truncate(raw) or f"SRNet exited with code {result.returncode}",
        )
        return

    _record(
        output_dir,
        analyzer_id,
        status="ok",
        summary="srnet completed inference with the operator-supplied checkpoint",
        output=f"stego probability: {probability:.6f}",
        confidence=probability,
        details={"model": model.name, "device": "CPU"},
    )


def _parse_runner_json(raw: str) -> Optional[dict[str, Any]]:
    candidates = [raw.strip(), *reversed([line.strip() for line in raw.splitlines()])]
    for candidate in candidates:
        if not candidate:
            continue
        try:
            value = json.loads(candidate)
        except (TypeError, ValueError):
            continue
        if isinstance(value, dict):
            return value
    return None


def _json_probability(payload: dict[str, Any]) -> Optional[float]:
    for key in ("stego_probability", "probability", "score"):
        value = payload.get(key)
        if isinstance(value, bool):
            continue
        try:
            number = float(value)
        except (TypeError, ValueError):
            continue
        if math.isfinite(number) and 0.0 <= number <= 1.0:
            return number
    return None


def _analyze_json_model_runner(
    analyzer_id: str,
    input_img: Path,
    output_dir: Path,
    *,
    runner_env: str,
    model_env: str,
    jpeg_only: bool = False,
) -> None:
    if not _validate_input(input_img, output_dir, analyzer_id):
        return
    if jpeg_only and _image_format(input_img) != "JPEG":
        _record(
            output_dir,
            analyzer_id,
            status="skipped",
            summary=f"{RESEARCH_BACKENDS[analyzer_id]['label']} expects JPEG input",
            reason="The selected model family operates in the JPEG/DCT domain.",
        )
        return

    runner = _resolve_command(runner_env)
    model, model_error = _configured_file(model_env)
    if not runner or model is None:
        missing = []
        if not runner:
            missing.append(f"validated JSON runner ({runner_env})")
        if model is None:
            missing.append(model_error)
        _record(
            output_dir,
            analyzer_id,
            status="skipped",
            summary=f"{RESEARCH_BACKENDS[analyzer_id]['label']} inference is not ready",
            reason=(
                "; ".join(missing)
                + ". The runner contract is: --input PATH --model PATH --json, with a "
                "0..1 stego_probability in its JSON output."
            ),
        )
        return

    result, launch_error = _run(
        [*runner, "--input", str(input_img), "--model", str(model), "--json"]
    )
    if launch_error or result is None:
        _record(
            output_dir,
            analyzer_id,
            status="error",
            summary=f"{RESEARCH_BACKENDS[analyzer_id]['label']} could not complete",
            error=launch_error or "unknown launch error",
        )
        return
    raw = _combined_output(result)
    payload = _parse_runner_json(result.stdout)
    probability = _json_probability(payload or {})
    if _command_failed(result, raw) or payload is None or probability is None:
        _record(
            output_dir,
            analyzer_id,
            status="error",
            summary="runner did not return a validated stego probability",
            error=_truncate(raw) or f"Runner exited with code {result.returncode}",
        )
        return

    safe_details = {
        key: value
        for key, value in payload.items()
        if key not in {"probability", "score", "stego_probability"}
        and isinstance(value, (str, int, float, bool, type(None)))
    }
    safe_details.update({"model": model.name, "runner_protocol": "twitterpainted-json-v1"})
    _record(
        output_dir,
        analyzer_id,
        status="ok",
        summary=f"{RESEARCH_BACKENDS[analyzer_id]['label']} completed model inference",
        output=f"stego probability: {probability:.6f}",
        confidence=probability,
        details=safe_details,
    )


def analyze_siastegnet(input_img: Path, output_dir: Path) -> None:
    _analyze_json_model_runner(
        "siastegnet",
        input_img,
        output_dir,
        runner_env="TWITTERPAINTED_SIASTEGNET_RUNNER",
        model_env="TWITTERPAINTED_SIASTEGNET_MODEL",
    )


def analyze_xunet(input_img: Path, output_dir: Path) -> None:
    _analyze_json_model_runner(
        "xunet",
        input_img,
        output_dir,
        runner_env="TWITTERPAINTED_XUNET_RUNNER",
        model_env="TWITTERPAINTED_XUNET_MODEL",
        jpeg_only=True,
    )


def _feature_summary(path: Path) -> Optional[dict[str, Any]]:
    try:
        vector = np.asarray(np.loadtxt(path), dtype=np.float64).reshape(-1)
    except Exception:
        return None
    if vector.size == 0 or not np.all(np.isfinite(vector)):
        return None
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return {
        "feature_count": int(vector.size),
        "minimum": float(np.min(vector)),
        "maximum": float(np.max(vector)),
        "mean": float(np.mean(vector)),
        "sha256": digest,
    }


def _archive_features(feature_path: Path) -> Path:
    archive_path = feature_path.with_suffix(".zip")
    with zipfile.ZipFile(
        archive_path,
        mode="w",
        compression=zipfile.ZIP_DEFLATED,
    ) as archive:
        archive.write(feature_path, arcname=feature_path.name)
        label_path = Path(f"{feature_path}.label")
        if label_path.is_file():
            archive.write(label_path, arcname=label_path.name)
    return archive_path


def _analyze_aletheia_features(
    analyzer_id: str,
    input_img: Path,
    output_dir: Path,
) -> None:
    if not _validate_input(input_img, output_dir, analyzer_id):
        return
    if _image_format(input_img) != "JPEG":
        _record(
            output_dir,
            analyzer_id,
            status="skipped",
            summary=f"{analyzer_id} is a JPEG-domain feature extractor",
            reason="Upload a JPEG carrier for this feature pipeline.",
        )
        return
    command = _aletheia_command()
    if not command:
        _record(
            output_dir,
            analyzer_id,
            status="skipped",
            summary=f"{analyzer_id} feature extraction is not ready",
            reason=(
                "Install Aletheia plus its Octave dependencies, or set "
                "TWITTERPAINTED_ALETHEIA_COMMAND. Twitterpainted does not fetch those "
                "resources; Aletheia may perform its own documented downloads when run."
            ),
        )
        return

    feature_path = output_dir / f"{analyzer_id}.features.txt"
    result, launch_error = _run(
        [*command, analyzer_id, str(input_img), str(feature_path)]
    )
    if launch_error or result is None:
        _record(
            output_dir,
            analyzer_id,
            status="error",
            summary=f"{analyzer_id} feature extraction could not complete",
            error=launch_error or "unknown launch error",
        )
        return
    raw = _combined_output(result)
    features = _feature_summary(feature_path) if feature_path.is_file() else None
    if _command_failed(result, raw) or features is None:
        _record(
            output_dir,
            analyzer_id,
            status="error",
            summary=f"{analyzer_id} did not create a validated feature vector",
            error=_truncate(raw) or f"Aletheia exited with code {result.returncode}",
        )
        return

    try:
        archive_path = _archive_features(feature_path)
    except OSError as exc:
        _record(
            output_dir,
            analyzer_id,
            status="error",
            summary=f"{analyzer_id} features were extracted but could not be packaged",
            error=str(exc),
        )
        return

    _record(
        output_dir,
        analyzer_id,
        status="ok",
        summary=(
            f"{analyzer_id} extracted a classical feature vector; a matched trained "
            "classifier is still required for a cover/stego verdict"
        ),
        output=f"feature count: {features['feature_count']}",
        details={
            "feature_file": feature_path.name,
            "artifact": archive_path.name,
            **features,
        },
    )


def analyze_dctr(input_img: Path, output_dir: Path) -> None:
    _analyze_aletheia_features("dctr", input_img, output_dir)


def analyze_gfr(input_img: Path, output_dir: Path) -> None:
    _analyze_aletheia_features("gfr", input_img, output_dir)


def analyze_maxsrmd2(input_img: Path, output_dir: Path) -> None:
    """Extract maxSRMd2 features through a licensed local runner and cost map."""
    analyzer_id = "maxsrmd2"
    if not _validate_input(input_img, output_dir, analyzer_id):
        return
    if _image_format(input_img) not in {"PNG", "BMP", "TIFF"}:
        _record(
            output_dir,
            analyzer_id,
            status="skipped",
            summary="maxsrmd2 is a spatial-domain feature pipeline",
            reason="Use a lossless spatial carrier and its matching selection-channel map.",
        )
        return

    runner = _resolve_command("TWITTERPAINTED_MAXSRMD2_RUNNER")
    selection_map, map_error = _configured_file("TWITTERPAINTED_MAXSRMD2_SELECTION_MAP")
    if not runner or selection_map is None:
        missing = []
        if not runner:
            missing.append("authorized runner (TWITTERPAINTED_MAXSRMD2_RUNNER)")
        if selection_map is None:
            missing.append(map_error)
        _record(
            output_dir,
            analyzer_id,
            status="skipped",
            summary="maxsrmd2 feature extraction is not ready",
            reason=(
                "; ".join(missing)
                + ". maxSRMd2 requires side information; an image alone is insufficient. "
                "Runner contract: --input PATH --selection-map PATH --output PATH."
            ),
        )
        return

    feature_path = output_dir / "maxsrmd2.features.txt"
    result, launch_error = _run(
        [
            *runner,
            "--input",
            str(input_img),
            "--selection-map",
            str(selection_map),
            "--output",
            str(feature_path),
        ]
    )
    if launch_error or result is None:
        _record(
            output_dir,
            analyzer_id,
            status="error",
            summary="maxsrmd2 feature extraction could not complete",
            error=launch_error or "unknown launch error",
        )
        return
    raw = _combined_output(result)
    features = _feature_summary(feature_path) if feature_path.is_file() else None
    if _command_failed(result, raw) or features is None:
        _record(
            output_dir,
            analyzer_id,
            status="error",
            summary="maxsrmd2 did not create a validated feature vector",
            error=_truncate(raw) or f"Runner exited with code {result.returncode}",
        )
        return

    try:
        archive_path = _archive_features(feature_path)
    except OSError as exc:
        _record(
            output_dir,
            analyzer_id,
            status="error",
            summary="maxsrmd2 features were extracted but could not be packaged",
            error=str(exc),
        )
        return

    _record(
        output_dir,
        analyzer_id,
        status="ok",
        summary=(
            "maxsrmd2 extracted a selection-channel-aware feature vector; a matched "
            "trained classifier is still required for a verdict"
        ),
        output=f"feature count: {features['feature_count']}",
        details={
            "feature_file": feature_path.name,
            "artifact": archive_path.name,
            **features,
        },
    )


def analyze_stegspy(input_img: Path, output_dir: Path) -> None:
    """Run the historical StegSpy signature scanner when locally authorized."""
    analyzer_id = "stegspy"
    if not _validate_input(input_img, output_dir, analyzer_id):
        return
    command = _resolve_command("TWITTERPAINTED_STEGSPY_COMMAND", ("stegspy",))
    if not command:
        _record(
            output_dir,
            analyzer_id,
            status="skipped",
            summary="stegspy is not installed or authorized",
            reason=(
                "The historical binary is copyrighted and distributed under upstream "
                "download terms, so Twitterpainted does not bundle it. Set "
                "TWITTERPAINTED_STEGSPY_COMMAND to a locally authorized CLI or wrapper."
            ),
        )
        return

    result, launch_error = _run([*command, str(input_img)])
    if launch_error or result is None:
        _record(
            output_dir,
            analyzer_id,
            status="error",
            summary="stegspy could not complete",
            error=launch_error or "unknown launch error",
        )
        return
    raw = _combined_output(result)
    if _command_failed(result, raw) or not raw:
        _record(
            output_dir,
            analyzer_id,
            status="error",
            summary="stegspy did not return a validated scan result",
            error=_truncate(raw) or f"StegSpy exited with code {result.returncode}",
        )
        return

    signatures = [
        name
        for name in ("Hiderman", "JPHideandSeek", "Masker", "JPegX", "Invisible Secrets")
        if name.lower() in raw.lower()
    ]
    if signatures:
        status = "ok"
        summary = "stegspy matched historical embedding-tool signatures"
    else:
        status = "no_signal"
        summary = "stegspy completed without a recognized historical tool signature"
    _record(
        output_dir,
        analyzer_id,
        status=status,
        summary=summary,
        output=_truncate(raw),
        details={"matched_signatures": signatures, "returncode": result.returncode},
    )

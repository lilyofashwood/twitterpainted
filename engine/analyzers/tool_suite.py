"""Run a broad CLI tool suite against an uploaded file."""

import platform
import shutil
import subprocess
from contextvars import ContextVar
from pathlib import Path
from typing import AbstractSet, Optional

from PIL import Image

from .utils import MAX_PENDING_TIME, update_data

MAX_OUTPUT_LINES = 200
MAX_OUTPUT_CHARS = 4000
RESOURCE_DIR = Path(__file__).resolve().parent / "resources"
STEGBREAK_RULES = RESOURCE_DIR / "stegbreak_rules.ini"
STEGBREAK_WORDLIST = RESOURCE_DIR / "stegbreak_wordlist.txt"
IS_ARM64 = platform.machine().lower() in {"aarch64", "arm64"}

# Every result key that this module can execute or probe independently. The UI
# uses these ids as real checkboxes; keep the list aligned with the calls below.
TOOL_SUITE_IDS = frozenset(
    {
        "identify",
        "convert",
        "jpeginfo",
        "jpegtran",
        "cjpeg",
        "djpeg",
        "jpegsnoop",
        "jhead",
        "exiv2",
        "exifprobe",
        "pngcheck",
        "optipng",
        "pngcrush",
        "pngtools",
        "stegdetect",
        "jsteg",
        "stegbreak",
        "stegseek",
        "stegcracker",
        "fcrackzip",
        "bulk_extractor",
        "scalpel",
        "testdisk",
        "photorec",
        "stegoveritas",
        "zbarimg",
        "qrencode",
        "tesseract",
        "ffprobe",
        "ffmpeg",
        "mediainfo",
        "sox",
        "pdfinfo",
        "pdftotext",
        "pdfimages",
        "qpdf",
        "radare2",
        "rizin",
        "hexyl",
        "bvi",
        "xxd",
        "rg",
        "tshark",
        "wireshark",
        "sleuthkit",
        "volatility",
        "stegsolve",
        "openstego",
        "stegpy",
        "stegolsb",
        "lsbsteg",
        "stegano_lsb",
        "stegano_lsb_set",
        "stegano_red",
        "cloackedpixel",
        "cloackedpixel_analyse",
        "jphide",
        "jphs",
        "jpseek",
        "stegsnow",
        "hideme",
        "mp3stego_encode",
        "mp3stego_decode",
        "stegify",
        "stegosuite",
        "sonic_visualiser",
        "openpuff",
        "deepsound",
    }
)

# These checkboxes report an installed command, help/version output, or create a
# demonstration artifact. They do not analyze the uploaded carrier. Export the
# set so catalog/UI metadata can label them as capability probes consistently.
CAPABILITY_PROBE_IDS = frozenset(
    {
        "bvi",
        "cjpeg",
        "cloackedpixel",
        "cloackedpixel_analyse",
        "deepsound",
        "djpeg",
        "hideme",
        "jphide",
        "jphs",
        "jpseek",
        "lsbsteg",
        "mp3stego_decode",
        "mp3stego_encode",
        "openpuff",
        "openstego",
        "photorec",
        "qrencode",
        "sonic_visualiser",
        "stegano_lsb",
        "stegano_lsb_set",
        "stegano_red",
        "stegify",
        "stegolsb",
        "stegosuite",
        "stegpy",
        "stegsnow",
        "stegsolve",
        "testdisk",
        "wireshark",
    }
)

# Volatility needs a deliberate memory-image profile and plugin choice. The
# generic upload sweep intentionally does not launch it.
DEDICATED_WORKFLOW_IDS = frozenset({"volatility"})

ZIP_MIME_TYPES = frozenset(
    {
        "application/zip",
        "application/x-zip",
        "application/x-zip-compressed",
    }
)
ZIP_SIGNATURES = frozenset({b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08"})

_SELECTED_TOOL_IDS: ContextVar[Optional[frozenset[str]]] = ContextVar(
    "twitterpainted_selected_suite_tools",
    default=None,
)


def _tool_is_selected(key: str) -> bool:
    selected = _SELECTED_TOOL_IDS.get()
    return selected is None or key in selected


def _truncate_lines(text: str, max_lines: int = MAX_OUTPUT_LINES) -> list[str]:
    lines = [line for line in text.splitlines() if line.strip()]
    if len(lines) > max_lines:
        extra = len(lines) - max_lines
        lines = lines[:max_lines]
        lines.append(f"... ({extra} more lines truncated)")
    return lines


def _truncate_text(text: str, max_chars: int = MAX_OUTPUT_CHARS) -> str:
    text = text.strip()
    if len(text) <= max_chars:
        return text
    return f"{text[:max_chars]}... (truncated)"


def _detect_mime(input_img: Path) -> str:
    try:
        data = subprocess.run(
            ["file", "--mime-type", "-b", str(input_img)],
            capture_output=True,
            text=True,
            timeout=MAX_PENDING_TIME,
            check=False,
        )
        if data.returncode == 0 and data.stdout:
            return data.stdout.strip()
    except Exception:
        pass

    try:
        img = Image.open(input_img)
        if img.format:
            return f"image/{img.format.lower()}"
    except Exception:
        pass

    return ""


def _is_zip_file(input_path: Path, mime: str) -> bool:
    """Recognize ZIP uploads by MIME or their standard leading signature."""
    if mime in ZIP_MIME_TYPES:
        return True
    try:
        with input_path.open("rb") as handle:
            return handle.read(4) in ZIP_SIGNATURES
    except OSError:
        return False


def _record(
    output_dir: Path,
    key: str,
    *,
    status: str,
    output: Optional[object] = None,
    error: Optional[str] = None,
    reason: Optional[str] = None,
) -> None:
    if not _tool_is_selected(key):
        return
    payload: dict[str, object] = {"status": status}
    if output is not None:
        payload["output"] = output
    if error:
        payload["error"] = error
    if reason:
        payload["reason"] = reason
    update_data(output_dir, {key: payload})


def _run_tool(
    output_dir: Path,
    key: str,
    cmd: list[str],
    *,
    cwd: Optional[Path] = None,
    allow_error: bool = False,
    output_mode: str = "lines",
    note: Optional[str] = None,
) -> bool:
    if not _tool_is_selected(key):
        return False
    binary = cmd[0]
    if not shutil.which(binary):
        _record(output_dir, key, status="skipped", reason=f"{binary} not installed")
        return False

    try:
        data = subprocess.run(
            cmd,
            cwd=str(cwd) if cwd else None,
            capture_output=True,
            text=True,
            errors="replace",
            timeout=MAX_PENDING_TIME,
            check=False,
        )
    except subprocess.TimeoutExpired:
        _record(
            output_dir,
            key,
            status="error",
            error=f"{binary} timed out after {MAX_PENDING_TIME} seconds. Consider increasing MAX_PENDING_TIME environment variable or disabling deep analysis.",
        )
        return False
    except Exception as exc:
        _record(output_dir, key, status="error", error=str(exc))
        return False

    combined = "\n".join([s for s in [data.stdout, data.stderr] if s])
    if data.returncode != 0 and not allow_error:
        _record(
            output_dir,
            key,
            status="error",
            error=_truncate_text(combined) or f"{binary} exited with code {data.returncode}",
        )
        return False

    if output_mode == "text":
        output = _truncate_text(combined) if combined else "ok"
        if note:
            output = f"{note}\n{output}" if output else note
    elif output_mode == "first_line":
        first_line = combined.splitlines()[0] if combined else "ok"
        output = _truncate_text(first_line)
        if note:
            output = f"{note}\n{output}" if output else note
    else:
        output = _truncate_lines(combined) if combined else ["ok"]
        if note:
            output = [note, *output]

    _record(output_dir, key, status="ok", output=output)
    return True


def _run_stegcracker(input_img: Path, output_dir: Path, tool_dir: Path) -> bool:
    """Run StegCracker with the bundled wordlist and honest result semantics."""
    key = "stegcracker"
    if not _tool_is_selected(key):
        return False
    if not shutil.which("stegcracker"):
        _record(output_dir, key, status="skipped", reason="stegcracker not installed")
        return False
    if not STEGBREAK_WORDLIST.exists():
        _record(output_dir, key, status="error", error="Bundled stegcracker wordlist is missing")
        return False

    recovered = tool_dir / "stegcracker.out"
    command = [
        "stegcracker",
        str(input_img),
        str(STEGBREAK_WORDLIST),
        "-o",
        str(recovered),
        "-q",
    ]
    try:
        data = subprocess.run(
            command,
            cwd=str(tool_dir),
            capture_output=True,
            text=True,
            errors="replace",
            timeout=MAX_PENDING_TIME,
            check=False,
        )
    except subprocess.TimeoutExpired:
        _record(
            output_dir,
            key,
            status="error",
            error=f"stegcracker timed out after {MAX_PENDING_TIME} seconds.",
        )
        return False
    except Exception as exc:
        _record(output_dir, key, status="error", error=str(exc))
        return False

    combined = "\n".join(value for value in (data.stdout, data.stderr) if value).strip()
    if data.returncode == 0 and recovered.is_file():
        output = [
            f"recovered: {recovered.relative_to(output_dir)}",
            f"bytes: {recovered.stat().st_size}",
        ]
        if combined:
            output.extend(_truncate_lines(combined))
        _record(output_dir, key, status="ok", output=output)
        return True

    failure_markers = ("error:", "traceback", "exception")
    if data.returncode == 1 and not any(marker in combined.lower() for marker in failure_markers):
        _record(
            output_dir,
            key,
            status="empty",
            reason="No steghide payload password matched the bundled wordlist.",
        )
        return False

    if data.returncode == 0:
        error = "stegcracker reported success but created no recovered file"
    else:
        error = _truncate_text(combined) or f"stegcracker exited with code {data.returncode}"
    _record(output_dir, key, status="error", error=error)
    return False


def _run_fcrackzip(input_path: Path, output_dir: Path, tool_dir: Path) -> bool:
    """Try the bundled small dictionary against an encrypted ZIP upload."""
    key = "fcrackzip"
    if not _tool_is_selected(key):
        return False
    if not shutil.which("fcrackzip"):
        _record(output_dir, key, status="skipped", reason="fcrackzip not installed")
        return False
    if not STEGBREAK_WORDLIST.exists():
        _record(output_dir, key, status="error", error="Bundled ZIP wordlist is missing")
        return False

    # fcrackzip 1.0 truncates long dictionary paths. Stage the list under a
    # short relative name and run from tool_dir so it reliably opens the file.
    staged_wordlist = tool_dir / "zip-words.txt"
    try:
        shutil.copyfile(STEGBREAK_WORDLIST, staged_wordlist)
    except OSError as exc:
        _record(output_dir, key, status="error", error=f"Could not stage ZIP wordlist: {exc}")
        return False

    command = [
        "fcrackzip",
        "-D",
        "-p",
        staged_wordlist.name,
        "-u",
        str(input_path),
    ]
    try:
        data = subprocess.run(
            command,
            cwd=str(tool_dir),
            capture_output=True,
            text=True,
            errors="replace",
            timeout=MAX_PENDING_TIME,
            check=False,
        )
    except subprocess.TimeoutExpired:
        _record(
            output_dir,
            key,
            status="error",
            error=f"fcrackzip timed out after {MAX_PENDING_TIME} seconds.",
        )
        return False
    except Exception as exc:
        _record(output_dir, key, status="error", error=str(exc))
        return False

    combined = "\n".join(value for value in (data.stdout, data.stderr) if value).strip()
    password_lines = [
        line.strip()
        for line in combined.splitlines()
        if "password found" in line.lower() and "pw ==" in line.lower()
    ]
    if data.returncode == 0 and password_lines:
        _record(
            output_dir,
            key,
            status="ok",
            output=[password_lines[0], "matched the bundled small wordlist"],
        )
        return True

    lowered = combined.lower()
    if data.returncode == 0 and not password_lines:
        _record(
            output_dir,
            key,
            status="empty",
            reason="No ZIP password matched the bundled small wordlist.",
        )
        return False
    if data.returncode == 1 and "no usable files found" in lowered:
        _record(
            output_dir,
            key,
            status="empty",
            reason="ZIP has no legacy encrypted entries that fcrackzip can test.",
        )
        return False

    error = _truncate_text(combined) or f"fcrackzip exited with code {data.returncode}"
    _record(output_dir, key, status="error", error=error)
    return False


def _skip_if(
    output_dir: Path,
    key: str,
    *,
    condition: bool,
    reason: str,
) -> bool:
    if not _tool_is_selected(key):
        return True
    if condition:
        return False
    _record(output_dir, key, status="skipped", reason=reason)
    return True


def _list_files(base_dir: Path) -> list[str]:
    files: list[str] = []
    for path in sorted(base_dir.rglob("*")):
        if path.is_file():
            try:
                files.append(str(path.relative_to(base_dir)))
            except Exception:
                files.append(str(path))
    return files


def _record_presence_probe(
    output_dir: Path,
    key: str,
    commands: list[str],
    *,
    note: str,
) -> None:
    if not _tool_is_selected(key):
        return
    available_path = ""
    for cmd in commands:
        path = shutil.which(cmd)
        if path:
            available_path = path
            break

    if not available_path:
        _record(output_dir, key, status="skipped", reason=f"{commands[0]} not installed")
        return

    _record(
        output_dir,
        key,
        status="ok",
        output=[
            f"installed: {available_path}",
            note,
        ],
    )


def analyze_tool_suite(
    input_img: Path,
    output_dir: Path,
    deep_analysis: bool = False,
    manual_tools: bool = False,
    *,
    selected_tools: Optional[AbstractSet[str]] = None,
) -> None:
    """Run all suite tools, or exactly the explicitly selected subset."""
    normalized: Optional[frozenset[str]] = None
    if selected_tools is not None:
        requested = {str(tool).strip().lower() for tool in selected_tools}
        if "tool_suite" not in requested:
            normalized = frozenset(requested & TOOL_SUITE_IDS)

        # Explicit checkbox selection is authoritative even for tools usually
        # suggested only by the deep/manual profiles.
        deep_analysis = True
        manual_tools = True

    token = _SELECTED_TOOL_IDS.set(normalized)
    try:
        _analyze_tool_suite(
            input_img,
            output_dir,
            deep_analysis=deep_analysis,
            manual_tools=manual_tools,
        )
    finally:
        _SELECTED_TOOL_IDS.reset(token)


def _analyze_tool_suite(
    input_img: Path,
    output_dir: Path,
    deep_analysis: bool = False,
    manual_tools: bool = False,
) -> None:
    """Run a large CLI tool suite against the uploaded file."""
    if not input_img.exists():
        _record(
            output_dir,
            "tool_suite",
            status="error",
            error=f"Input image not found: {input_img}",
        )
        return

    mime = _detect_mime(input_img)
    is_jpeg = mime == "image/jpeg"
    is_png = mime == "image/png"
    is_image = mime.startswith("image/")
    is_pdf = mime == "application/pdf"
    is_audio = mime.startswith("audio/")
    is_video = mime.startswith("video/")
    is_pcap = mime in {"application/vnd.tcpdump.pcap", "application/x-pcap"}
    is_zip = _is_zip_file(input_img, mime)

    tool_dir = output_dir / "tool_suite"
    tool_dir.mkdir(parents=True, exist_ok=True)

    if not _skip_if(output_dir, "identify", condition=is_image, reason="Not an image"):
        _run_tool(output_dir, "identify", ["identify", "-verbose", str(input_img)])

    if not _skip_if(output_dir, "convert", condition=is_image, reason="Not an image"):
        _run_tool(
            output_dir,
            "convert",
            ["convert", str(input_img), "-format", "%m %w %h", "info:"],
            output_mode="text",
        )

    if not _skip_if(output_dir, "jpeginfo", condition=is_jpeg, reason="Not a JPEG"):
        _run_tool(output_dir, "jpeginfo", ["jpeginfo", "-c", str(input_img)])

    if not _skip_if(output_dir, "jpegtran", condition=is_jpeg, reason="Not a JPEG"):
        out_file = tool_dir / "jpegtran.jpg"
        _run_tool(
            output_dir,
            "jpegtran",
            ["jpegtran", "-copy", "none", "-optimize", "-outfile", str(out_file), str(input_img)],
        )

    _run_tool(output_dir, "cjpeg", ["cjpeg", "-version"], allow_error=True, output_mode="text")
    _run_tool(output_dir, "djpeg", ["djpeg", "-version"], allow_error=True, output_mode="text")

    if not _skip_if(output_dir, "jpegsnoop", condition=is_jpeg, reason="Not a JPEG"):
        _run_tool(output_dir, "jpegsnoop", ["jpegsnoop", str(input_img)])

    if not _skip_if(output_dir, "jhead", condition=is_jpeg, reason="Not a JPEG"):
        _run_tool(output_dir, "jhead", ["jhead", str(input_img)])

    if not _skip_if(output_dir, "exiv2", condition=is_image, reason="Not an image"):
        _run_tool(output_dir, "exiv2", ["exiv2", "-pa", str(input_img)])

    if not _skip_if(output_dir, "exifprobe", condition=is_image, reason="Not an image"):
        _run_tool(
            output_dir,
            "exifprobe",
            ["exifprobe", str(input_img)],
            allow_error=True,
        )

    if not _skip_if(output_dir, "pngcheck", condition=is_png, reason="Not a PNG"):
        _run_tool(output_dir, "pngcheck", ["pngcheck", "-v", str(input_img)])

    if not _skip_if(output_dir, "optipng", condition=is_png, reason="Not a PNG"):
        _run_tool(output_dir, "optipng", ["optipng", "-simulate", "-quiet", str(input_img)])

    if not _skip_if(output_dir, "pngcrush", condition=is_png, reason="Not a PNG"):
        out_file = tool_dir / "pngcrush.png"
        _run_tool(output_dir, "pngcrush", ["pngcrush", "-q", str(input_img), str(out_file)])

    if not _skip_if(output_dir, "pngtools", condition=is_png, reason="Not a PNG"):
        _run_tool(
            output_dir,
            "pngtools",
            ["pngtools", str(input_img)],
            output_mode="text",
            note="auto mode: pngtools (pngfix fallback uses pngcheck -v)",
        )

    if not _skip_if(output_dir, "stegdetect", condition=is_jpeg, reason="Not a JPEG"):
        _run_tool(output_dir, "stegdetect", ["stegdetect", "-t", "jopi", str(input_img)])

    if not _skip_if(output_dir, "jsteg", condition=is_jpeg, reason="Not a JPEG"):
        _run_tool(
            output_dir,
            "jsteg",
            ["jsteg", "reveal", str(input_img)],
            allow_error=True,
            output_mode="text",
        )

    if _skip_if(
        output_dir,
        "stegbreak",
        condition=deep_analysis,
        reason="Enable deep analysis to run brute-force tools",
    ):
        pass
    elif not _skip_if(output_dir, "stegbreak", condition=is_jpeg, reason="Not a JPEG"):
        if IS_ARM64:
            _record(
                output_dir,
                "stegbreak",
                status="skipped",
                reason="Disabled on arm64 (stegbreak crashes with SIGILL)",
            )
        else:
            stegbreak_cmd = ["stegbreak", "-t", "jpo"]
            if STEGBREAK_RULES.exists():
                stegbreak_cmd.extend(["-r", str(STEGBREAK_RULES)])
            if STEGBREAK_WORDLIST.exists():
                stegbreak_cmd.extend(["-f", str(STEGBREAK_WORDLIST)])
            stegbreak_cmd.append(str(input_img))
            _run_tool(output_dir, "stegbreak", stegbreak_cmd)

    if _skip_if(
        output_dir,
        "stegseek",
        condition=deep_analysis,
        reason="Enable deep analysis to run brute-force tools",
    ):
        pass
    elif not _skip_if(output_dir, "stegseek", condition=is_jpeg, reason="Not a JPEG"):
        seed_out = tool_dir / "stegseek_seed.out"
        _run_tool(
            output_dir,
            "stegseek",
            ["stegseek", "--seed", str(input_img), str(seed_out)],
            allow_error=True,
            cwd=tool_dir,
        )

    if _skip_if(
        output_dir,
        "stegcracker",
        condition=deep_analysis,
        reason="Enable deep analysis to run brute-force tools",
    ):
        pass
    elif not _skip_if(output_dir, "stegcracker", condition=is_jpeg, reason="Not a JPEG"):
        _run_stegcracker(input_img, output_dir, tool_dir)

    if _skip_if(
        output_dir,
        "fcrackzip",
        condition=deep_analysis,
        reason="Enable deep analysis to run brute-force tools",
    ):
        pass
    elif not _skip_if(output_dir, "fcrackzip", condition=is_zip, reason="Not a ZIP archive"):
        _run_fcrackzip(input_img, output_dir, tool_dir)

    if _skip_if(
        output_dir,
        "bulk_extractor",
        condition=deep_analysis,
        reason="Enable deep analysis to run bulk_extractor",
    ):
        pass
    else:
        bulk_dir = tool_dir / "bulk_extractor"
        bulk_dir.mkdir(parents=True, exist_ok=True)
        if _run_tool(
            output_dir,
            "bulk_extractor",
            ["bulk_extractor", "-q", "-o", str(bulk_dir), str(input_img)],
            cwd=bulk_dir,
        ):
            _record(output_dir, "bulk_extractor", status="ok", output=_list_files(bulk_dir))

    if _skip_if(
        output_dir,
        "scalpel",
        condition=deep_analysis,
        reason="Enable deep analysis to run scalpel",
    ):
        pass
    else:
        scalpel_dir = tool_dir / "scalpel"
        scalpel_dir.mkdir(parents=True, exist_ok=True)
        if _run_tool(
            output_dir,
            "scalpel",
            ["scalpel", "-o", str(scalpel_dir), str(input_img)],
            cwd=scalpel_dir,
            allow_error=True,
        ):
            _record(output_dir, "scalpel", status="ok", output=_list_files(scalpel_dir))

    if _skip_if(
        output_dir,
        "testdisk",
        condition=manual_tools,
        reason="Enable manual tools to run interactive utilities",
    ):
        pass
    else:
        _run_tool(
            output_dir,
            "testdisk",
            ["testdisk", "/version"],
            allow_error=True,
            output_mode="text",
            note="manual mode: testdisk /version",
        )

    if _skip_if(
        output_dir,
        "photorec",
        condition=manual_tools,
        reason="Enable manual tools to run interactive utilities",
    ):
        pass
    else:
        _run_tool(
            output_dir,
            "photorec",
            ["photorec", "/version"],
            allow_error=True,
            output_mode="text",
            note="manual mode: photorec /version",
        )

    if _skip_if(
        output_dir,
        "stegoveritas",
        condition=deep_analysis,
        reason="Enable deep analysis to run stegoveritas",
    ):
        pass
    else:
        veritas_dir = tool_dir / "stegoveritas"
        veritas_dir.mkdir(parents=True, exist_ok=True)
        if _run_tool(
            output_dir,
            "stegoveritas",
            ["stegoveritas", "-meta", "-out", str(veritas_dir), str(input_img)],
            cwd=veritas_dir,
            allow_error=True,
        ):
            _record(output_dir, "stegoveritas", status="ok", output=_list_files(veritas_dir))

    if not _skip_if(output_dir, "zbarimg", condition=is_image, reason="Not an image"):
        _run_tool(
            output_dir,
            "zbarimg",
            ["zbarimg", "--quiet", str(input_img)],
            allow_error=True,
            note="auto mode: zbarimg --quiet (no barcode found is normal)",
        )

    if _skip_if(
        output_dir,
        "qrencode",
        condition=manual_tools,
        reason="Enable manual tools to run encoder utilities",
    ):
        pass
    else:
        qr_out = tool_dir / "qrencode.png"
        qr_text = f"twitterpainted:{input_img.name}"
        if _run_tool(
            output_dir,
            "qrencode",
            ["qrencode", "-o", str(qr_out), "-t", "PNG", qr_text],
            allow_error=True,
            output_mode="text",
            note=f"manual mode: qrencode -o {qr_out.name} -t PNG \"{qr_text}\"",
        ):
            if qr_out.exists():
                _record(
                    output_dir,
                    "qrencode",
                    status="ok",
                    output=[
                        f"manual mode: qrencode -o {qr_out.name} -t PNG \"{qr_text}\"",
                        qr_out.name,
                    ],
                )
            else:
                _record(
                    output_dir,
                    "qrencode",
                    status="ok",
                    output=[
                        f"manual mode: qrencode -o {qr_out.name} -t PNG \"{qr_text}\"",
                        "no output file created",
                    ],
                )

    if not _skip_if(output_dir, "tesseract", condition=is_image, reason="Not an image"):
        out_base = tool_dir / "tesseract_output"
        if _run_tool(
            output_dir,
            "tesseract",
            ["tesseract", str(input_img), str(out_base)],
            allow_error=True,
        ):
            out_txt = out_base.with_suffix(".txt")
            if out_txt.exists():
                _record(
                    output_dir,
                    "tesseract",
                    status="ok",
                    output=_truncate_text(out_txt.read_text(errors="ignore")),
                )

    if not _skip_if(output_dir, "ffprobe", condition=is_image or is_audio or is_video, reason="Not media"):
        _run_tool(
            output_dir,
            "ffprobe",
            ["ffprobe", "-hide_banner", "-show_format", "-show_streams", str(input_img)],
            allow_error=True,
        )

    if _skip_if(
        output_dir,
        "ffmpeg",
        condition=deep_analysis,
        reason="Enable deep analysis to run ffmpeg",
    ):
        pass
    else:
        _run_tool(
            output_dir,
            "ffmpeg",
            ["ffmpeg", "-hide_banner", "-i", str(input_img), "-f", "null", "-"],
            allow_error=True,
        )

    if not _skip_if(output_dir, "mediainfo", condition=is_image or is_audio or is_video, reason="Not media"):
        _run_tool(output_dir, "mediainfo", ["mediainfo", str(input_img)])

    if not _skip_if(output_dir, "sox", condition=is_audio, reason="Not audio"):
        _run_tool(output_dir, "sox", ["sox", "--i", str(input_img)])

    if not _skip_if(output_dir, "pdfinfo", condition=is_pdf, reason="Not a PDF"):
        _run_tool(output_dir, "pdfinfo", ["pdfinfo", str(input_img)])

    if not _skip_if(output_dir, "pdftotext", condition=is_pdf, reason="Not a PDF"):
        out_file = tool_dir / "pdftotext.txt"
        if _run_tool(output_dir, "pdftotext", ["pdftotext", str(input_img), str(out_file)]):
            if out_file.exists():
                _record(
                    output_dir,
                    "pdftotext",
                    status="ok",
                    output=_truncate_text(out_file.read_text(errors="ignore")),
                )

    if not _skip_if(output_dir, "pdfimages", condition=is_pdf, reason="Not a PDF"):
        out_prefix = tool_dir / "pdfimages"
        if _run_tool(output_dir, "pdfimages", ["pdfimages", str(input_img), str(out_prefix)]):
            matches = sorted(path.name for path in tool_dir.glob("pdfimages*") if path.is_file())
            _record(output_dir, "pdfimages", status="ok", output=matches or ["no outputs found"])

    if not _skip_if(output_dir, "qpdf", condition=is_pdf, reason="Not a PDF"):
        _run_tool(output_dir, "qpdf", ["qpdf", "--show-npages", str(input_img)])

    _run_tool(output_dir, "radare2", ["radare2", "-q", "-c", "iI;izzq", str(input_img)], allow_error=True)
    _run_tool(output_dir, "rizin", ["rizin", "-q", "-c", "iI;izzq", str(input_img)], allow_error=True)
    _run_tool(output_dir, "hexyl", ["hexyl", "-n", "256", str(input_img)], allow_error=True)
    if _skip_if(
        output_dir,
        "bvi",
        condition=manual_tools,
        reason="Enable manual tools to run interactive utilities",
    ):
        pass
    else:
        _run_tool(
            output_dir,
            "bvi",
            ["bvi", "-v"],
            allow_error=True,
            output_mode="text",
            note="manual mode: bvi -v",
        )
    _run_tool(output_dir, "xxd", ["xxd", "-l", "256", str(input_img)], allow_error=True)
    _run_tool(output_dir, "rg", ["rg", "-a", "-n", "-m", "3", "-e", "flag", "-e", "ctf", "-e", "steg", str(input_img)], allow_error=True)

    if not _skip_if(output_dir, "tshark", condition=is_pcap, reason="Not a pcap"):
        _run_tool(output_dir, "tshark", ["tshark", "-r", str(input_img), "-c", "5"], allow_error=True)

    if _skip_if(
        output_dir,
        "wireshark",
        condition=manual_tools,
        reason="Enable manual tools to run GUI utilities",
    ):
        pass
    else:
        _run_tool(
            output_dir,
            "wireshark",
            ["wireshark", "--version"],
            allow_error=True,
            output_mode="first_line",
            note="manual mode: wireshark --version",
        )
    is_disk_candidate = not (is_image or is_audio or is_video or is_pdf)
    if _skip_if(output_dir, "sleuthkit", condition=is_disk_candidate, reason="Not a disk image"):
        pass
    else:
        _run_tool(
            output_dir,
            "sleuthkit",
            ["mmls", str(input_img)],
            allow_error=False,
            note="auto mode: mmls",
        )
    _record(output_dir, "volatility", status="skipped", reason="Requires a memory image")
    if _skip_if(
        output_dir,
        "stegsolve",
        condition=manual_tools,
        reason="Enable manual tools to run GUI utilities",
    ):
        pass
    else:
        _run_tool(
            output_dir,
            "stegsolve",
            ["stegsolve", "--help"],
            allow_error=True,
            output_mode="text",
            note="manual mode: stegsolve --help",
        )
    _run_tool(
        output_dir,
        "openstego",
        ["openstego", "algorithms"],
        allow_error=True,
        output_mode="text",
        note="auto mode: openstego algorithms",
    )

    for key, cmd, note in [
        ("stegpy", ["stegpy", "--help"], "auto mode: stegpy --help"),
        ("stegolsb", ["stegolsb", "--help"], "auto mode: stegolsb --help"),
        ("lsbsteg", ["lsbsteg", "--help"], "auto mode: lsbsteg --help"),
        ("stegano_lsb", ["stegano-lsb", "--help"], "auto mode: stegano-lsb --help"),
        (
            "stegano_lsb_set",
            ["stegano-lsb-set", "--help"],
            "auto mode: stegano-lsb-set --help",
        ),
        ("stegano_red", ["stegano-red", "--help"], "auto mode: stegano-red --help"),
        ("cloackedpixel", ["cloackedpixel", "--help"], "auto mode: cloackedpixel --help"),
        (
            "cloackedpixel_analyse",
            ["cloackedpixel-analyse", "--help"],
            "auto mode: cloackedpixel-analyse --help",
        ),
        ("jphide", ["jphide", "-h"], "jpeg hide probe: jphide -h"),
        ("jphs", ["jphs", "-h"], "jpeg seek probe: jphs -h"),
        ("jpseek", ["jpseek", "-h"], "jpeg seek probe: jpseek -h"),
        ("stegsnow", ["stegsnow", "-h"], "text stego probe: stegsnow -h"),
        ("hideme", ["hideme", "--help"], "audio stego probe: hideme --help"),
        (
            "mp3stego_encode",
            ["mp3stego-encode", "--help"],
            "audio stego probe: mp3stego-encode --help",
        ),
        (
            "mp3stego_decode",
            ["mp3stego-decode", "--help"],
            "audio stego probe: mp3stego-decode --help",
        ),
        ("stegify", ["stegify", "--help"], "generic stego probe: stegify --help"),
    ]:
        _run_tool(
            output_dir,
            key,
            cmd,
            allow_error=True,
            output_mode="text",
            note=note,
        )

    _record_presence_probe(
        output_dir,
        "stegosuite",
        ["stegosuite"],
        note="manual tool installed. launch separately for interactive workflows.",
    )
    _record_presence_probe(
        output_dir,
        "sonic_visualiser",
        ["sonic-visualiser", "sonic_visualiser"],
        note="manual gui tool installed. use it for audio-spectrum forensics.",
    )
    _record_presence_probe(
        output_dir,
        "openpuff",
        ["openpuff"],
        note="manual gui tool installed. run separately for windows-style workflows.",
    )
    _record_presence_probe(
        output_dir,
        "deepsound",
        ["deepsound"],
        note="manual gui tool installed. run separately for audio embedding workflows.",
    )

    _record(
        output_dir,
        "tool_suite",
        status="ok",
        output=[
            f"completed extended tool sweep for {input_img.name}",
            "inspect each tool card for payload-focused findings and metadata.",
        ],
    )

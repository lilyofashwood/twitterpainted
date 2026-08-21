"""Shared tooling availability helpers."""

import shutil
from typing import Dict, List, TypedDict, Union

ToolCmd = Union[str, List[str]]


class ToolSpec(TypedDict):
    cmd: ToolCmd
    mode: str


TOOLS: Dict[str, ToolSpec] = {
    "binwalk": {"cmd": "binwalk", "mode": "auto"},
    "foremost": {"cmd": "foremost", "mode": "auto"},
    "exiftool": {"cmd": "exiftool", "mode": "auto"},
    "steghide": {"cmd": "steghide", "mode": "auto"},
    "outguess": {"cmd": "outguess", "mode": "deep"},
    "zsteg": {"cmd": "zsteg", "mode": "auto"},
    "strings": {"cmd": "strings", "mode": "auto"},
    "identify": {"cmd": "identify", "mode": "auto"},
    "convert": {"cmd": "convert", "mode": "auto"},
    "jpegtran": {"cmd": "jpegtran", "mode": "auto"},
    "cjpeg": {"cmd": "cjpeg", "mode": "auto"},
    "djpeg": {"cmd": "djpeg", "mode": "auto"},
    "jpeginfo": {"cmd": "jpeginfo", "mode": "auto"},
    "jpegsnoop": {"cmd": "jpegsnoop", "mode": "auto"},
    "jhead": {"cmd": "jhead", "mode": "auto"},
    "exiv2": {"cmd": "exiv2", "mode": "auto"},
    "exifprobe": {"cmd": "exifprobe", "mode": "auto"},
    "pngcheck": {"cmd": "pngcheck", "mode": "auto"},
    "optipng": {"cmd": "optipng", "mode": "auto"},
    "pngcrush": {"cmd": "pngcrush", "mode": "auto"},
    "pngtools": {"cmd": "pngtools", "mode": "auto"},
    "stegdetect": {"cmd": "stegdetect", "mode": "auto"},
    "jsteg": {"cmd": "jsteg", "mode": "auto"},
    "stegbreak": {"cmd": "stegbreak", "mode": "deep"},
    "stegseek": {"cmd": "stegseek", "mode": "deep"},
    "stegcracker": {"cmd": "stegcracker", "mode": "deep"},
    "fcrackzip": {"cmd": "fcrackzip", "mode": "deep"},
    "bulk_extractor": {"cmd": ["bulk_extractor", "bulk-extractor"], "mode": "deep"},
    "stegoveritas": {"cmd": "stegoveritas", "mode": "deep"},
    "scalpel": {"cmd": "scalpel", "mode": "deep"},
    "testdisk": {"cmd": "testdisk", "mode": "manual"},
    "photorec": {"cmd": "photorec", "mode": "manual"},
    "zbarimg": {"cmd": "zbarimg", "mode": "auto"},
    "qrencode": {"cmd": "qrencode", "mode": "manual"},
    "tesseract": {"cmd": "tesseract", "mode": "auto"},
    "ffmpeg": {"cmd": "ffmpeg", "mode": "deep"},
    "ffprobe": {"cmd": "ffprobe", "mode": "auto"},
    "mediainfo": {"cmd": "mediainfo", "mode": "auto"},
    "sox": {"cmd": "sox", "mode": "auto"},
    "pdfinfo": {"cmd": "pdfinfo", "mode": "auto"},
    "pdftotext": {"cmd": "pdftotext", "mode": "auto"},
    "pdfimages": {"cmd": "pdfimages", "mode": "auto"},
    "qpdf": {"cmd": "qpdf", "mode": "auto"},
    "radare2": {"cmd": ["radare2", "r2"], "mode": "auto"},
    "rizin": {"cmd": "rizin", "mode": "auto"},
    "hexyl": {"cmd": "hexyl", "mode": "auto"},
    "bvi": {"cmd": "bvi", "mode": "manual"},
    "rg": {"cmd": "rg", "mode": "auto"},
    "xxd": {"cmd": "xxd", "mode": "auto"},
    "tshark": {"cmd": "tshark", "mode": "auto"},
    "wireshark": {"cmd": "wireshark", "mode": "manual"},
    "sleuthkit": {"cmd": "mmls", "mode": "auto"},
    "volatility": {"cmd": ["volatility", "volatility3", "vol"], "mode": "auto"},
    "stegsolve": {"cmd": "stegsolve", "mode": "manual"},
    "stegosuite": {"cmd": "stegosuite", "mode": "manual"},
    "stegpy": {"cmd": "stegpy", "mode": "auto"},
    "stegolsb": {"cmd": "stegolsb", "mode": "auto"},
    "lsbsteg": {"cmd": ["lsbsteg", "LSBSteg.py", "lsb-steg"], "mode": "auto"},
    "stegano_lsb": {"cmd": "stegano-lsb", "mode": "auto"},
    "stegano_lsb_set": {"cmd": "stegano-lsb-set", "mode": "auto"},
    "stegano_red": {"cmd": "stegano-red", "mode": "auto"},
    "cloackedpixel": {"cmd": "cloackedpixel", "mode": "auto"},
    "cloackedpixel_analyse": {"cmd": "cloackedpixel-analyse", "mode": "auto"},
    "jphide": {"cmd": "jphide", "mode": "auto"},
    "jphs": {"cmd": "jphs", "mode": "auto"},
    "jpseek": {"cmd": "jpseek", "mode": "deep"},
    "stegsnow": {"cmd": ["stegsnow", "snow"], "mode": "auto"},
    "hideme": {"cmd": "hideme", "mode": "deep"},
    "mp3stego_encode": {"cmd": "mp3stego-encode", "mode": "deep"},
    "mp3stego_decode": {"cmd": "mp3stego-decode", "mode": "deep"},
    "openpuff": {"cmd": "openpuff", "mode": "manual"},
    "deepsound": {"cmd": "deepsound", "mode": "manual"},
    "sonic_visualiser": {"cmd": ["sonic-visualiser", "sonic_visualiser"], "mode": "manual"},
    "stegify": {"cmd": "stegify", "mode": "auto"},
    "openstego": {"cmd": "openstego", "mode": "auto"},
    "7z": {"cmd": "7z", "mode": "auto"},
    "file": {"cmd": "file", "mode": "auto"},
    "unzip": {"cmd": "unzip", "mode": "auto"},
    "tar": {"cmd": "tar", "mode": "auto"},
    "xz": {"cmd": "xz", "mode": "auto"},
    "gzip": {"cmd": "gzip", "mode": "auto"},
    "bzip2": {"cmd": "bzip2", "mode": "auto"},
    "unsquashfs": {"cmd": "unsquashfs", "mode": "auto"},
    # Statistical steganalysis tools
    "stegexpose": {"cmd": "stegexpose", "mode": "deep"},
    # JPEG analysis tools
    "jpegdump": {"cmd": "jpegdump", "mode": "auto"},
    "jpegrescan": {"cmd": "jpegrescan", "mode": "auto"},
    # Format-specific tools
    "gifextract": {"cmd": "gifextract", "mode": "auto"},
    "webpinfo": {"cmd": "webpinfo", "mode": "auto"},
    "webpmux": {"cmd": "webpmux", "mode": "auto"},
    "pngfix": {"cmd": "pngfix", "mode": "auto"},
}


def get_tool_status() -> Dict[str, Dict[str, str]]:
    """
    Return mapping of tool -> {available: bool, path: str|None}.
    """
    status: Dict[str, Dict[str, str]] = {}
    for name, spec in TOOLS.items():
        cmd = spec["cmd"]
        cmds = cmd if isinstance(cmd, list) else [cmd]
        path = ""
        for candidate in cmds:
            found = shutil.which(candidate)
            if found:
                path = found
                break
        status[name] = {
            "available": bool(path),
            "path": path or "",
            "mode": spec.get("mode", "auto"),
        }
    return status

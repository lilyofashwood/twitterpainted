"""Analyzer catalog metadata for UI tool selection and ETA hints."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Set

from .analyzers.tool_suite import (
    CAPABILITY_PROBE_IDS,
    DEDICATED_WORKFLOW_IDS,
    TOOL_SUITE_IDS,
)
from .decode_registry import OPTIONS
from .tooling import TOOLS

IMAGE_FORMATS = ("image/png", "image/jpeg", "image/gif", "image/bmp")
AUDIO_FORMATS = (
    "audio/wav",
    "audio/flac",
    "audio/ogg",
    "audio/aiff",
    "audio/au",
    "audio/raw",
)


@dataclass(frozen=True)
class AnalyzerSpec:
    analyzer_id: str
    label: str
    description: str
    eta_seconds: int
    profiles: tuple[str, ...]
    kind: str
    category: str = "general"
    applicability: tuple[str, ...] = ("uploaded file",)
    operation: str = "inspect"
    source_url: str = ""
    license: str = ""
    license_url: str = ""
    requirements: tuple[str, ...] = ()

    @property
    def eta_label(self) -> str:
        sec = max(1, int(self.eta_seconds))
        if sec < 60:
            return f"~{sec}s"
        minutes, rem = divmod(sec, 60)
        if rem == 0:
            return f"~{minutes}m"
        return f"~{minutes}m {rem}s"


ANALYZER_CATALOG: Dict[str, AnalyzerSpec] = {
    "pre_analysis": AnalyzerSpec(
        analyzer_id="pre_analysis",
        label="smart pre-scan",
        description="quick entropy + format triage to prioritize likely payload paths",
        eta_seconds=20,
        profiles=("quick", "balanced", "deep", "forensic"),
        kind="internal",
    ),
    "advanced_lsb": AnalyzerSpec(
        analyzer_id="advanced_lsb",
        label="advanced lsb",
        description="per-channel text/zlib detector for multi-plane payloads",
        eta_seconds=35,
        profiles=("quick", "balanced", "deep", "forensic"),
        kind="internal",
    ),
    "simple_lsb": AnalyzerSpec(
        analyzer_id="simple_lsb",
        label="simple lsb",
        description="common lsb text extraction across rgb/rgba planes",
        eta_seconds=30,
        profiles=("light", "quick", "balanced", "deep", "forensic"),
        kind="internal",
        category="pixel and bit planes",
    ),
    "simple_zlib": AnalyzerSpec(
        analyzer_id="simple_zlib",
        label="simple zlib",
        description="zlib stream recovery from typical lsb bitstreams",
        eta_seconds=35,
        profiles=("quick", "balanced", "deep", "forensic"),
        kind="internal",
        category="pixel and bit planes",
    ),
    "simple_rgb": AnalyzerSpec(
        analyzer_id="simple_rgb",
        label="rgb lsb preview",
        description="reads one interleaved least-significant-bit stream across rgb channels",
        eta_seconds=10,
        profiles=("quick", "balanced", "deep", "forensic"),
        kind="internal",
        category="pixel and bit planes",
    ),
    "red_plane": AnalyzerSpec(
        analyzer_id="red_plane",
        label="red lsb plane",
        description="reads a least-significant-bit stream from the red channel only",
        eta_seconds=10,
        profiles=("quick", "balanced", "deep", "forensic"),
        kind="internal",
        category="pixel and bit planes",
    ),
    "green_plane": AnalyzerSpec(
        analyzer_id="green_plane",
        label="green lsb plane",
        description="reads a least-significant-bit stream from the green channel only",
        eta_seconds=10,
        profiles=("quick", "balanced", "deep", "forensic"),
        kind="internal",
        category="pixel and bit planes",
    ),
    "blue_plane": AnalyzerSpec(
        analyzer_id="blue_plane",
        label="blue lsb plane",
        description="reads a least-significant-bit stream from the blue channel only",
        eta_seconds=10,
        profiles=("quick", "balanced", "deep", "forensic"),
        kind="internal",
        category="pixel and bit planes",
    ),
    "alpha_plane": AnalyzerSpec(
        analyzer_id="alpha_plane",
        label="alpha lsb plane",
        description="reads a least-significant-bit stream from the alpha channel only",
        eta_seconds=10,
        profiles=("quick", "balanced", "deep", "forensic"),
        kind="internal",
        category="pixel and bit planes",
    ),
    "randomizer_decode": AnalyzerSpec(
        analyzer_id="randomizer_decode",
        label="randomizer decode",
        description="shuffle/xor candidate decodes for obfuscated plaintext",
        eta_seconds=45,
        profiles=("quick", "balanced", "deep", "forensic"),
        kind="internal",
    ),
    "payload_unwrap": AnalyzerSpec(
        analyzer_id="payload_unwrap",
        label="payload unwrap",
        description="unwrap base64/base91/xor/rot payload wrappers",
        eta_seconds=75,
        profiles=("quick", "balanced", "deep", "forensic"),
        kind="internal",
    ),
    "xor_flag_sweep": AnalyzerSpec(
        analyzer_id="xor_flag_sweep",
        label="xor flag sweep",
        description="keyword-guided xor sweep for ctf-style payloads",
        eta_seconds=90,
        profiles=("quick", "balanced", "deep", "forensic"),
        kind="internal",
    ),
    "binwalk": AnalyzerSpec(
        analyzer_id="binwalk",
        label="binwalk",
        description="signature scan for embedded file segments",
        eta_seconds=80,
        profiles=("balanced", "deep", "forensic"),
        kind="external",
    ),
    "decomposer": AnalyzerSpec(
        analyzer_id="decomposer",
        label="bit-plane decomposer",
        description="render per-plane images for visual payload inspection",
        eta_seconds=70,
        profiles=("balanced", "deep", "forensic"),
        kind="internal",
    ),
    "exiftool": AnalyzerSpec(
        analyzer_id="exiftool",
        label="exiftool",
        description="metadata and profile anomaly extraction",
        eta_seconds=20,
        profiles=("balanced", "deep", "forensic"),
        kind="external",
    ),
    "foremost": AnalyzerSpec(
        analyzer_id="foremost",
        label="foremost",
        description="header/footer carving for hidden file recovery",
        eta_seconds=120,
        profiles=("balanced", "deep", "forensic"),
        kind="external",
    ),
    "stegg": AnalyzerSpec(
        analyzer_id="stegg",
        label="stegg",
        description="legacy stegg-compatible decode probe",
        eta_seconds=55,
        profiles=("balanced", "deep", "forensic"),
        kind="internal",
    ),
    "zero_width": AnalyzerSpec(
        analyzer_id="zero_width",
        label="zero-width",
        description="zero-width unicode hidden text extraction",
        eta_seconds=25,
        profiles=("balanced", "deep", "forensic"),
        kind="internal",
    ),
    "strings": AnalyzerSpec(
        analyzer_id="strings",
        label="strings",
        description="readable byte sequences from carrier file",
        eta_seconds=20,
        profiles=("balanced", "deep", "forensic"),
        kind="external",
    ),
    "steghide": AnalyzerSpec(
        analyzer_id="steghide",
        label="steghide",
        description="steghide extraction using provided password",
        eta_seconds=45,
        profiles=("balanced", "deep", "forensic"),
        kind="external",
    ),
    "zsteg": AnalyzerSpec(
        analyzer_id="zsteg",
        label="zsteg",
        description="png/bmp lsb brute and signature extraction",
        eta_seconds=90,
        profiles=("balanced", "deep", "forensic"),
        kind="external",
    ),
    "entropy_analyzer": AnalyzerSpec(
        analyzer_id="entropy_analyzer",
        label="entropy analyzer",
        description="channel entropy anomalies and lsb randomness checks",
        eta_seconds=35,
        profiles=("balanced", "deep", "forensic"),
        kind="internal",
    ),
    "jpeg_qtable_analyzer": AnalyzerSpec(
        analyzer_id="jpeg_qtable_analyzer",
        label="jpeg qtable analyzer",
        description="jpeg quantization table forensic hints",
        eta_seconds=40,
        profiles=("balanced", "deep", "forensic"),
        kind="internal",
    ),
    "statistical_steg": AnalyzerSpec(
        analyzer_id="statistical_steg",
        label="statistical steg",
        description="statistical detection heuristics for embedded data",
        eta_seconds=65,
        profiles=("balanced", "deep", "forensic"),
        kind="external",
    ),
    "aletheia": AnalyzerSpec(
        analyzer_id="aletheia",
        label="aletheia auto",
        description="runs aletheia's trained automatic detector table when its local runtime and models are ready",
        eta_seconds=300,
        profiles=(),
        kind="external",
        category="learned and research steganalysis",
        applicability=IMAGE_FORMATS,
        operation="inspect",
        source_url="https://github.com/daniellerch/aletheia",
        license="MIT; model and external dependency terms may also apply",
        license_url="https://github.com/daniellerch/aletheia/blob/master/LICENSE.txt",
        requirements=("Aletheia runtime and models", "TWITTERPAINTED_ALETHEIA_COMMAND when not on PATH"),
    ),
    "srnet": AnalyzerSpec(
        analyzer_id="srnet",
        label="srnet",
        description="runs srnet inference through aletheia with an explicitly configured local checkpoint",
        eta_seconds=240,
        profiles=(),
        kind="external",
        category="learned and research steganalysis",
        applicability=IMAGE_FORMATS,
        operation="model inference",
        source_url="https://github.com/daniellerch/aletheia",
        license="MIT adapter; configured checkpoint terms also apply",
        license_url="https://github.com/daniellerch/aletheia/blob/master/LICENSE.txt",
        requirements=("Aletheia runtime", "TWITTERPAINTED_SRNET_MODEL"),
    ),
    "siastegnet": AnalyzerSpec(
        analyzer_id="siastegnet",
        label="siastegnet",
        description="runs a configured siastegnet model adapter and accepts only validated probability output",
        eta_seconds=240,
        profiles=(),
        kind="external",
        category="learned and research steganalysis",
        applicability=IMAGE_FORMATS,
        operation="model inference",
        source_url="https://github.com/SiaStg/SiaStegNet",
        license="no upstream license file identified; do not redistribute code or weights without permission",
        license_url="https://github.com/SiaStg/SiaStegNet",
        requirements=("TWITTERPAINTED_SIASTEGNET_RUNNER", "TWITTERPAINTED_SIASTEGNET_MODEL"),
    ),
    "xunet": AnalyzerSpec(
        analyzer_id="xunet",
        label="xu-net",
        description="runs a configured xu-net jpeg steganalysis model adapter with validated probability output",
        eta_seconds=240,
        profiles=(),
        kind="external",
        category="learned and research steganalysis",
        applicability=("image/jpeg",),
        operation="model inference",
        source_url="https://github.com/GuanshuoXu/caffe_deep_learning_for_steganalysis",
        license="upstream Caffe-derived license; configured checkpoint terms also apply",
        license_url="https://github.com/GuanshuoXu/caffe_deep_learning_for_steganalysis/blob/master/LICENSE",
        requirements=("TWITTERPAINTED_XUNET_RUNNER", "TWITTERPAINTED_XUNET_MODEL"),
    ),
    "dctr": AnalyzerSpec(
        analyzer_id="dctr",
        label="dctr features",
        description="extracts jpeg dct residual features through aletheia; a matched classifier is still required",
        eta_seconds=300,
        profiles=(),
        kind="external",
        category="learned and research steganalysis",
        applicability=("image/jpeg",),
        operation="feature extraction",
        source_url="https://github.com/daniellerch/aletheia",
        license="MIT Aletheia integration; external Octave feature code terms may also apply",
        license_url="https://github.com/daniellerch/aletheia/blob/master/LICENSE.txt",
        requirements=("Aletheia runtime", "Octave image, signal, and nan packages"),
    ),
    "gfr": AnalyzerSpec(
        analyzer_id="gfr",
        label="gfr features",
        description="extracts jpeg gabor-filter residual features through aletheia; a matched classifier is still required",
        eta_seconds=300,
        profiles=(),
        kind="external",
        category="learned and research steganalysis",
        applicability=("image/jpeg",),
        operation="feature extraction",
        source_url="https://github.com/daniellerch/aletheia",
        license="MIT Aletheia integration; external Octave feature code terms may also apply",
        license_url="https://github.com/daniellerch/aletheia/blob/master/LICENSE.txt",
        requirements=("Aletheia runtime", "Octave image, signal, and nan packages"),
    ),
    "maxsrmd2": AnalyzerSpec(
        analyzer_id="maxsrmd2",
        label="maxsrmd2 features",
        description="extracts selection-channel-aware spatial rich-model features when a cost map and authorized runner are configured",
        eta_seconds=420,
        profiles=(),
        kind="external",
        category="learned and research steganalysis",
        applicability=("image/png", "image/bmp", "image/tiff"),
        operation="feature extraction",
        source_url="https://dde.binghamton.edu/download/feature_extractors/",
        license="no redistributable upstream license identified; supply a locally authorized runner",
        license_url="https://dde.binghamton.edu/download/feature_extractors/",
        requirements=("TWITTERPAINTED_MAXSRMD2_RUNNER", "TWITTERPAINTED_MAXSRMD2_SELECTION_MAP"),
    ),
    "stegspy": AnalyzerSpec(
        analyzer_id="stegspy",
        label="stegspy",
        description="runs a locally authorized historical signature scanner for five legacy embedding programs",
        eta_seconds=45,
        profiles=(),
        kind="external",
        category="learned and research steganalysis",
        applicability=IMAGE_FORMATS,
        operation="inspect",
        source_url="https://www.spy-hunter.com/stegspydownload.htm",
        license="copyrighted historical binary with upstream download terms; not redistributed",
        license_url="https://www.spy-hunter.com/stegspydownload.htm",
        requirements=("locally authorized stegspy CLI", "TWITTERPAINTED_STEGSPY_COMMAND when not on PATH"),
    ),
    "plane_carver": AnalyzerSpec(
        analyzer_id="plane_carver",
        label="plane carver",
        description="file signature carving over many bitstream traversals",
        eta_seconds=220,
        profiles=("deep", "forensic"),
        kind="internal",
    ),
    "outguess": AnalyzerSpec(
        analyzer_id="outguess",
        label="outguess",
        description="outguess extraction pass with password",
        eta_seconds=160,
        profiles=("deep", "forensic"),
        kind="external",
    ),
    "invisible_unicode": AnalyzerSpec(
        analyzer_id="invisible_unicode",
        label="invisible unicode",
        description="raw unicode marker sweep across bytes and decoded text",
        eta_seconds=120,
        profiles=("quick", "balanced", "deep", "forensic"),
        kind="internal",
    ),
    "invisible_unicode_decode": AnalyzerSpec(
        analyzer_id="invisible_unicode_decode",
        label="invisible unicode decode",
        description="decode pass for candidate invisible-unicode payloads",
        eta_seconds=80,
        profiles=("quick", "balanced", "deep", "forensic"),
        kind="internal",
    ),
    # --- ste.gg parity decoders ---
    "homoglyph": AnalyzerSpec(
        analyzer_id="homoglyph",
        label="homoglyph substitution",
        description="detect unicode lookalike characters encoding hidden bits",
        eta_seconds=30,
        profiles=("balanced", "deep", "forensic"),
        kind="internal",
    ),
    "whitespace_steg": AnalyzerSpec(
        analyzer_id="whitespace_steg",
        label="whitespace encoding",
        description="recover data from trailing spaces and tabs in text lines",
        eta_seconds=20,
        profiles=("balanced", "deep", "forensic"),
        kind="internal",
    ),
    "audio_lsb": AnalyzerSpec(
        analyzer_id="audio_lsb",
        label="audio lsb",
        description="extract hidden bits from audio sample lsbs",
        eta_seconds=45,
        profiles=("balanced", "deep", "forensic"),
        kind="internal",
        category="audio and media",
        applicability=AUDIO_FORMATS,
    ),
    "audio_fft": AnalyzerSpec(
        analyzer_id="audio_fft",
        label="audio fft",
        description="frequency-domain signal extraction from audio spectrum",
        eta_seconds=60,
        profiles=("deep", "forensic"),
        kind="internal",
        category="audio and media",
        applicability=AUDIO_FORMATS,
    ),
    "audio_echo": AnalyzerSpec(
        analyzer_id="audio_echo",
        label="echo hiding",
        description="detect echo-delay patterns encoding hidden bits in audio",
        eta_seconds=90,
        profiles=("deep", "forensic"),
        kind="internal",
        category="audio and media",
        applicability=AUDIO_FORMATS,
    ),
    "audio_spectrogram": AnalyzerSpec(
        analyzer_id="audio_spectrogram",
        label="spectrogram art",
        description="render audio spectrogram for visual inspection of hidden images",
        eta_seconds=30,
        profiles=("balanced", "deep", "forensic"),
        kind="internal",
        category="audio and media",
        applicability=AUDIO_FORMATS,
    ),
    "matryoshka": AnalyzerSpec(
        analyzer_id="matryoshka",
        label="matryoshka (nested)",
        description="recursive multi-layer extraction of embedded images",
        eta_seconds=300,
        profiles=("deep", "forensic"),
        kind="internal",
    ),
    "channel_cipher": AnalyzerSpec(
        analyzer_id="channel_cipher",
        label="channel cipher",
        description="password-seeded channel hopping extraction (godmode)",
        eta_seconds=120,
        profiles=("deep", "forensic"),
        kind="internal",
    ),
}


_CATEGORY_IDS = {
    "guided inspection": {"pre_analysis", "auto_detect"},
    "pixel and bit planes": {
        "advanced_lsb",
        "simple_lsb",
        "simple_zlib",
        "simple_rgb",
        "red_plane",
        "green_plane",
        "blue_plane",
        "alpha_plane",
        "lsb",
        "pvd",
        "decomposer",
        "plane_carver",
        "zsteg",
    },
    "frequency domain": {"dct", "f5", "jpeg_qtable_analyzer", "outguess"},
    "metadata and structure": {
        "png_chunks",
        "binwalk",
        "exiftool",
        "strings",
        "foremost",
        "entropy_analyzer",
        "statistical_steg",
    },
    "text and transforms": {
        "randomizer_decode",
        "payload_unwrap",
        "xor_flag_sweep",
        "zero_width",
        "invisible_unicode",
        "invisible_unicode_decode",
        "homoglyph",
        "whitespace_steg",
    },
    "audio and media": {
        "audio_lsb",
        "audio_fft",
        "audio_echo",
        "audio_spectrogram",
        "channel_cipher",
        "chroma",
        "palette",
        "spread_spectrum",
    },
}

_SUITE_CATEGORY_IDS = {
    "image inspection": {
        "identify", "convert", "jpeginfo", "jpegtran", "cjpeg", "djpeg",
        "jpegsnoop", "jhead", "exiv2", "exifprobe", "pngcheck", "optipng",
        "pngcrush", "pngtools", "tesseract", "zbarimg",
    },
    "brute force and recovery": {
        "stegdetect", "jsteg", "stegbreak", "stegseek", "stegcracker",
        "fcrackzip", "bulk_extractor", "scalpel", "stegoveritas",
    },
    "media and documents": {
        "ffprobe", "ffmpeg", "mediainfo", "sox", "pdfinfo", "pdftotext",
        "pdfimages", "qpdf", "sonic_visualiser", "deepsound", "hideme",
        "mp3stego_encode", "mp3stego_decode",
    },
    "binary and forensic inspection": {
        "radare2", "rizin", "hexyl", "xxd", "rg", "tshark", "sleuthkit",
        "volatility", "testdisk", "photorec", "wireshark", "bvi",
    },
    "specialist steganography": {
        "openstego", "stegpy", "stegolsb", "lsbsteg", "stegano_lsb",
        "stegano_lsb_set", "stegano_red", "cloackedpixel",
        "cloackedpixel_analyse", "jphide", "jphs", "jpseek", "stegsnow",
        "stegify", "stegosuite", "stegsolve", "openpuff", "qrencode",
    },
}

_SUITE_HELP = {
    "stegcracker": "Runs StegCracker against a JPEG to try password-list steghide recovery.",
    "stegseek": "Runs Stegseek's fast seed/recovery pass against a JPEG carrier.",
    "stegbreak": "Runs JPEG steganography brute-force checks with bundled rules and wordlist.",
    "exifprobe": "Reads detailed image metadata; useful output is retained even on a nonzero exit.",
    "stegsnow": "Shows the installed stegsnow text-steganography command and its decode options.",
    "sonic_visualiser": "Presence probe only; interactive Sonic Visualiser analysis runs outside the web request.",
    "openpuff": "Presence probe only; OpenPuff's interactive workflow runs outside the web request.",
    "deepsound": "Presence probe only; DeepSound's interactive workflow runs outside the web request.",
    "mp3stego_encode": "Capability probe only; this runtime does not submit an encoding job.",
    "mp3stego_decode": "Capability probe only; this runtime does not submit a decoding job.",
    "volatility": "Reports that a dedicated memory image is required before Volatility can run.",
}

_AUDIO_SUITE_TOOLS = {
    "sox",
    "sonic_visualiser",
    "deepsound",
    "hideme",
    "mp3stego_encode",
    "mp3stego_decode",
}

_IMAGE_ANALYZERS = {
    "advanced_lsb",
    "simple_lsb",
    "simple_zlib",
    "simple_rgb",
    "red_plane",
    "green_plane",
    "blue_plane",
    "alpha_plane",
    "decomposer",
    "entropy_analyzer",
    "statistical_steg",
    "plane_carver",
    "stegg",
    "matryoshka",
    "channel_cipher",
    "identify",
    "convert",
    "exiv2",
    "exifprobe",
    "zbarimg",
    "tesseract",
}
_JPEG_ANALYZERS = {
    "jpeg_qtable_analyzer",
    "outguess",
    "jpeginfo",
    "jpegtran",
    "jpegsnoop",
    "jhead",
    "stegdetect",
    "jsteg",
    "stegbreak",
    "stegseek",
    "stegcracker",
    "jphide",
    "jphs",
    "jpseek",
}
_PNG_ANALYZERS = {"pngcheck", "optipng", "pngcrush", "pngtools"}
_PDF_ANALYZERS = {"pdfinfo", "pdftotext", "pdfimages", "qpdf"}
_MEDIA_ANALYZERS = {"ffprobe", "ffmpeg", "mediainfo"}
_PCAP_ANALYZERS = {"tshark", "wireshark"}
_DISK_ANALYZERS = {"sleuthkit", "testdisk", "photorec"}
_CAPABILITY_ONLY_ANALYZERS = set(CAPABILITY_PROBE_IDS) - (
    _AUDIO_SUITE_TOOLS | _JPEG_ANALYZERS | _PCAP_ANALYZERS | _DISK_ANALYZERS
)


def _applicability_for(
    analyzer_id: str,
    declared: tuple[str, ...] = ("uploaded file",),
) -> tuple[str, ...]:
    if analyzer_id in _JPEG_ANALYZERS:
        return ("image/jpeg",)
    if analyzer_id in _PNG_ANALYZERS:
        return ("image/png",)
    if analyzer_id in _AUDIO_SUITE_TOOLS or analyzer_id.startswith("audio_"):
        return AUDIO_FORMATS
    if analyzer_id in _IMAGE_ANALYZERS:
        return IMAGE_FORMATS
    if analyzer_id == "zsteg":
        return ("image/png", "image/bmp")
    if analyzer_id == "steghide":
        return ("image/jpeg", "image/bmp", "audio/wav", "audio/au")
    if analyzer_id in _PDF_ANALYZERS:
        return ("application/pdf",)
    if analyzer_id == "fcrackzip":
        return ("application/zip",)
    if analyzer_id in _MEDIA_ANALYZERS:
        return ("image", "audio", "video")
    if analyzer_id in _PCAP_ANALYZERS:
        return ("application/pcap",)
    if analyzer_id in _DISK_ANALYZERS:
        return ("disk image",)
    if analyzer_id == "volatility":
        return ("memory image",)
    if analyzer_id in _CAPABILITY_ONLY_ANALYZERS:
        return ("tool availability",)
    return declared


_DECODE_OPERATION_IDS = {
    "auto_detect",
    "lsb",
    "pvd",
    "dct",
    "f5",
    "spread_spectrum",
    "palette",
    "chroma",
    "png_chunks",
    "advanced_lsb",
    "simple_lsb",
    "simple_zlib",
    "simple_rgb",
    "red_plane",
    "green_plane",
    "blue_plane",
    "alpha_plane",
    "randomizer_decode",
    "payload_unwrap",
    "xor_flag_sweep",
    "stegg",
    "zero_width",
    "invisible_unicode_decode",
    "homoglyph",
    "whitespace_steg",
    "audio_lsb",
    "matryoshka",
    "channel_cipher",
    "plane_carver",
}
_INSPECTION_OPERATION_IDS = {
    "pre_analysis",
    "decomposer",
    "entropy_analyzer",
    "jpeg_qtable_analyzer",
    "statistical_steg",
    "invisible_unicode",
    "audio_fft",
    "audio_echo",
    "audio_spectrogram",
}
_RESEARCH_OPERATION_IDS = {
    "aletheia",
    "srnet",
    "siastegnet",
    "xunet",
    "dctr",
    "gfr",
    "maxsrmd2",
    "stegspy",
}


def _operation_for(analyzer_id: str, kind: str, declared: str = "inspect") -> str:
    if analyzer_id in CAPABILITY_PROBE_IDS or analyzer_id in DEDICATED_WORKFLOW_IDS:
        return "capability probe"
    if analyzer_id in _DECODE_OPERATION_IDS:
        return "decode"
    if analyzer_id in _INSPECTION_OPERATION_IDS:
        return "inspect"
    if analyzer_id in _RESEARCH_OPERATION_IDS:
        return declared
    if analyzer_id in TOOL_SUITE_IDS or kind == "external":
        return "carrier cli"
    return declared


def _category_for(analyzer_id: str, fallback: str = "general") -> str:
    for category, ids in (*_CATEGORY_IDS.items(), *_SUITE_CATEGORY_IDS.items()):
        if analyzer_id in ids:
            return category
    return fallback


def _suggested_profiles_for_external_tool(tool_id: str) -> tuple[str, ...]:
    # Import lazily so this metadata module stays acyclic at import time.
    from .analysis_profiles import list_profiles

    return tuple(
        str(profile["id"])
        for profile in list_profiles()
        if tool_id in profile.get("external_tools", [])
    )


_DECODE_PROFILE_SUGGESTIONS = {
    "auto_detect": ("quick", "balanced", "deep", "forensic"),
    "lsb": ("quick", "balanced", "deep", "forensic"),
    "pvd": ("quick", "balanced", "deep", "forensic"),
    "dct": ("quick", "balanced", "deep", "forensic"),
    "f5": ("deep", "forensic"),
    "spread_spectrum": ("deep", "forensic"),
    "palette": ("quick", "balanced", "deep", "forensic"),
    "chroma": ("quick", "balanced", "deep", "forensic"),
    "png_chunks": ("quick", "balanced", "deep", "forensic"),
}

for option_id, option in OPTIONS.items():
    ANALYZER_CATALOG[option_id] = AnalyzerSpec(
        analyzer_id=option_id,
        label=option.label.lower(),
        description=option.description.lower(),
        eta_seconds=35,
        profiles=_DECODE_PROFILE_SUGGESTIONS.get(option_id, ()),
        kind="internal",
        category=option.category,
        applicability=tuple(option.supported_formats),
        operation="decode",
    )

for tool_id in sorted(TOOL_SUITE_IDS):
    tool = TOOLS.get(tool_id, {"mode": "auto"})
    mode = str(tool.get("mode", "auto"))
    description = _SUITE_HELP.get(tool_id)
    if not description:
        action = "Checks the installed command and reports its capabilities" if tool_id in CAPABILITY_PROBE_IDS or tool_id in DEDICATED_WORKFLOW_IDS else "Runs the installed command against the uploaded carrier"
        description = f"{action}; only this tool runs when selected."
    ANALYZER_CATALOG.setdefault(
        tool_id,
        AnalyzerSpec(
            analyzer_id=tool_id,
            label=tool_id.replace("_", " "),
            description=description.lower(),
            eta_seconds=180 if mode == "deep" else 30 if mode == "manual" else 45,
            profiles=_suggested_profiles_for_external_tool(tool_id),
            kind="external",
            category=_category_for(tool_id, "external tools"),
            applicability=_applicability_for(tool_id),
            operation=_operation_for(tool_id, "external"),
        ),
    )


def list_analyzer_catalog(profile_id: Optional[str] = None) -> List[Dict[str, object]]:
    from .analysis_profiles import normalize_profile

    profile = normalize_profile(profile_id)
    rows: List[Dict[str, object]] = []
    for analyzer_id in sorted(ANALYZER_CATALOG.keys()):
        spec = ANALYZER_CATALOG[analyzer_id]
        recommended = profile in spec.profiles
        rows.append(
            {
                "id": spec.analyzer_id,
                "label": spec.label,
                "description": spec.description,
                "eta_seconds": spec.eta_seconds,
                "eta_label": spec.eta_label,
                "kind": spec.kind,
                "category": _category_for(spec.analyzer_id, spec.category),
                "applicability": list(
                    _applicability_for(spec.analyzer_id, spec.applicability)
                ),
                "operation": _operation_for(
                    spec.analyzer_id,
                    spec.kind,
                    spec.operation,
                ),
                "source_url": spec.source_url,
                "license": spec.license,
                "license_url": spec.license_url,
                "requirements": list(spec.requirements),
                "profiles": list(spec.profiles),
                # Profiles are suggestions, not capability gates. This legacy
                # field remains true so older clients keep every box clickable.
                "enabled_in_profile": True,
                "recommended_in_profile": recommended,
            }
        )
    return rows


def default_selected_for_profile(profile_id: Optional[str]) -> List[str]:
    from .analysis_profiles import normalize_profile

    profile = normalize_profile(profile_id)
    selected: List[str] = []
    for spec in ANALYZER_CATALOG.values():
        if profile in spec.profiles:
            selected.append(spec.analyzer_id)
    return sorted(selected)


def normalize_selected_tools(raw_tools: Optional[List[str]]) -> Optional[Set[str]]:
    if raw_tools is None:
        return None

    allowed = set(ANALYZER_CATALOG) | {"decode_options", "tool_suite"}
    normalized = {
        str(tool).strip().lower()
        for tool in raw_tools
        if str(tool).strip().lower() in allowed
    }
    return normalized

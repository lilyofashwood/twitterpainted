"""Analysis profiles for controlling decoder depth and tool activation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple


@dataclass(frozen=True)
class AnalysisProfile:
    profile_id: str
    label: str
    description: str
    eta_seconds: Tuple[int, int]
    run_external_basic: bool
    run_tool_suite: bool
    run_decode_deep: bool
    run_plane_carver: bool
    run_outguess: bool
    run_manual_tools: bool
    internal_tools: Tuple[str, ...]
    external_tools: Tuple[str, ...]

    @property
    def eta_label(self) -> str:
        low, high = self.eta_seconds
        return f"{_format_eta(low)} - {_format_eta(high)}"


def _format_eta(seconds: int) -> str:
    minutes, sec = divmod(max(0, int(seconds)), 60)
    if minutes <= 0:
        return f"{sec}s"
    if sec == 0:
        return f"{minutes}m"
    return f"{minutes}m {sec}s"


_PROFILES: Dict[str, AnalysisProfile] = {
    "light": AnalysisProfile(
        profile_id="light",
        label="Light",
        description="Fast default that checks only the simple LSB carrier.",
        eta_seconds=(5, 30),
        run_external_basic=False,
        run_tool_suite=False,
        run_decode_deep=False,
        run_plane_carver=False,
        run_outguess=False,
        run_manual_tools=False,
        internal_tools=("simple_lsb",),
        external_tools=(),
    ),
    "quick": AnalysisProfile(
        profile_id="quick",
        label="Quick",
        description="Fast, Python-only signal checks and lightweight payload extraction.",
        eta_seconds=(15, 90),
        run_external_basic=False,
        run_tool_suite=False,
        run_decode_deep=False,
        run_plane_carver=False,
        run_outguess=False,
        run_manual_tools=False,
        internal_tools=(
            "simple_rgb",
            "red_plane",
            "green_plane",
            "blue_plane",
            "alpha_plane",
            "simple_lsb",
            "advanced_lsb",
            "simple_zlib",
            "decode_options",
            "smart_scan",
        ),
        external_tools=(),
    ),
    "balanced": AnalysisProfile(
        profile_id="balanced",
        label="Balanced",
        description="Everyday workshop profile: broad coverage without deep brute-force passes.",
        eta_seconds=(60, 240),
        run_external_basic=True,
        run_tool_suite=True,
        run_decode_deep=False,
        run_plane_carver=False,
        run_outguess=False,
        run_manual_tools=False,
        internal_tools=(
            "simple_rgb",
            "red_plane",
            "green_plane",
            "blue_plane",
            "alpha_plane",
            "smart_scan",
            "advanced_lsb",
            "simple_lsb",
            "simple_zlib",
            "stegg",
            "zero_width",
            "entropy_analyzer",
            "jpeg_qtable_analyzer",
            "statistical_steg",
            "payload_unwrap",
            "xor_flag_sweep",
            "randomizer_decode",
            "decomposer",
            "homoglyph",
            "whitespace_steg",
            "audio_lsb",
            "audio_spectrogram",
        ),
        external_tools=(
            "binwalk",
            "foremost",
            "exiftool",
            "strings",
            "steghide",
            "zsteg",
            "stegpy",
            "stegolsb",
            "lsbsteg",
            "stegano_lsb",
            "stegano_lsb_set",
            "stegano_red",
            "cloackedpixel",
            "cloackedpixel_analyse",
            "stegsnow",
            "stegify",
            "openstego",
            "file",
            "7z",
        ),
    ),
    "deep": AnalysisProfile(
        profile_id="deep",
        label="Deep",
        description="Adds deep-frequency and plane-carving passes for stronger recovery odds.",
        eta_seconds=(180, 720),
        run_external_basic=True,
        run_tool_suite=True,
        run_decode_deep=True,
        run_plane_carver=True,
        run_outguess=True,
        run_manual_tools=False,
        internal_tools=(
            "simple_rgb",
            "red_plane",
            "green_plane",
            "blue_plane",
            "alpha_plane",
            "smart_scan",
            "advanced_lsb",
            "simple_lsb",
            "simple_zlib",
            "stegg",
            "zero_width",
            "entropy_analyzer",
            "jpeg_qtable_analyzer",
            "statistical_steg",
            "payload_unwrap",
            "xor_flag_sweep",
            "randomizer_decode",
            "decomposer",
            "plane_carver",
            "outguess",
            "homoglyph",
            "whitespace_steg",
            "audio_lsb",
            "audio_fft",
            "audio_echo",
            "audio_spectrogram",
            "matryoshka",
            "channel_cipher",
        ),
        external_tools=(
            "binwalk",
            "foremost",
            "exiftool",
            "strings",
            "steghide",
            "zsteg",
            "outguess",
            "stegbreak",
            "stegseek",
            "stegcracker",
            "fcrackzip",
            "stegoveritas",
            "bulk_extractor",
            "scalpel",
            "stegpy",
            "stegolsb",
            "lsbsteg",
            "stegano_lsb",
            "stegano_lsb_set",
            "stegano_red",
            "cloackedpixel",
            "cloackedpixel_analyse",
            "stegsnow",
            "hideme",
            "mp3stego_encode",
            "mp3stego_decode",
            "stegify",
            "openstego",
            "jphide",
            "jphs",
            "jpseek",
            "file",
            "7z",
        ),
    ),
    "forensic": AnalysisProfile(
        profile_id="forensic",
        label="Forensic",
        description="Maximum depth with manual/interactive tool hooks enabled.",
        eta_seconds=(480, 1800),
        run_external_basic=True,
        run_tool_suite=True,
        run_decode_deep=True,
        run_plane_carver=True,
        run_outguess=True,
        run_manual_tools=True,
        internal_tools=(
            "simple_rgb",
            "red_plane",
            "green_plane",
            "blue_plane",
            "alpha_plane",
            "smart_scan",
            "advanced_lsb",
            "simple_lsb",
            "simple_zlib",
            "stegg",
            "zero_width",
            "entropy_analyzer",
            "jpeg_qtable_analyzer",
            "statistical_steg",
            "payload_unwrap",
            "xor_flag_sweep",
            "randomizer_decode",
            "decomposer",
            "plane_carver",
            "homoglyph",
            "whitespace_steg",
            "audio_lsb",
            "audio_fft",
            "audio_echo",
            "audio_spectrogram",
            "matryoshka",
            "channel_cipher",
            "outguess",
        ),
        external_tools=(
            "binwalk",
            "foremost",
            "exiftool",
            "strings",
            "steghide",
            "zsteg",
            "outguess",
            "stegbreak",
            "stegseek",
            "stegcracker",
            "fcrackzip",
            "stegoveritas",
            "bulk_extractor",
            "scalpel",
            "stegpy",
            "stegolsb",
            "lsbsteg",
            "stegano_lsb",
            "stegano_lsb_set",
            "stegano_red",
            "cloackedpixel",
            "cloackedpixel_analyse",
            "stegsnow",
            "hideme",
            "mp3stego_encode",
            "mp3stego_decode",
            "openpuff",
            "deepsound",
            "stegify",
            "openstego",
            "jphide",
            "jphs",
            "jpseek",
            "stegosuite",
            "testdisk",
            "photorec",
            "wireshark",
            "bvi",
            "stegsolve",
            "qrencode",
            "sonic_visualiser",
            "file",
            "7z",
        ),
    ),
}

DEFAULT_PROFILE = "light"

_PROFILE_ALIASES = {
    # Non-user-facing compatibility for clients that used the former preset id.
    "simple": "light",
}


def normalize_profile(profile: Optional[str]) -> str:
    key = (profile or DEFAULT_PROFILE).strip().lower()
    key = _PROFILE_ALIASES.get(key, key)
    if key not in _PROFILES:
        return DEFAULT_PROFILE
    return key


def resolve_profile(
    profile: Optional[str],
    *,
    deep_analysis: bool = False,
    manual_tools: bool = False,
) -> AnalysisProfile:
    key = normalize_profile(profile)

    if manual_tools:
        return _PROFILES["forensic"]
    if deep_analysis and key in {"quick", "balanced"}:
        return _PROFILES["deep"]
    return _PROFILES[key]


def get_profile(profile: Optional[str]) -> AnalysisProfile:
    return _PROFILES[normalize_profile(profile)]


def list_profiles() -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for key in ("light", "quick", "balanced", "deep", "forensic"):
        profile = _PROFILES[key]
        rows.append(
            {
                "id": profile.profile_id,
                "label": profile.label,
                "description": profile.description,
                "eta_seconds": list(profile.eta_seconds),
                "eta_label": profile.eta_label,
                "internal_tools": list(profile.internal_tools),
                "external_tools": list(profile.external_tools),
            }
        )
    return rows

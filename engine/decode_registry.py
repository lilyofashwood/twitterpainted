"""Decode option registry for STE.gg parity."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from .option_decoders import (
    analyze_auto_detect,
    analyze_chroma,
    analyze_dct,
    analyze_f5,
    analyze_lsb,
    analyze_palette,
    analyze_png_chunks,
    analyze_pvd,
    analyze_spread_spectrum,
    param_adapter,
)


@dataclass(frozen=True)
class DecodeOption:
    option_id: str
    label: str
    analyzer: Callable[..., Dict[str, Any]]
    supported_formats: List[str]
    description: str = ""
    category: str = "carrier decoding"
    requires_password: bool = False
    mode: str = "auto"
    default_params: Dict[str, Any] = field(default_factory=dict)


def _wrap(option: DecodeOption) -> Dict[str, Any]:
    return {
        "id": option.option_id,
        "label": option.label,
        "analyzer": option.analyzer,
        "supported_formats": option.supported_formats,
        "description": option.description,
        "category": option.category,
        "requires_password": option.requires_password,
        "mode": option.mode,
        "default_params": option.default_params,
        "params": lambda opt, params: param_adapter(opt, params),
    }


OPTIONS: Dict[str, DecodeOption] = {
    "auto_detect": DecodeOption(
        option_id="auto_detect",
        label="Auto Detect",
        analyzer=analyze_auto_detect,
        supported_formats=["image/png", "image/jpeg", "image/gif"],
        description="Ranks the compatible carrier decoders and reports the strongest signals.",
        category="guided inspection",
        mode="auto",
    ),
    "lsb": DecodeOption(
        option_id="lsb",
        label="LSB (Least Significant Bit)",
        analyzer=analyze_lsb,
        supported_formats=["image/png", "image/jpeg", "image/gif"],
        description="Reads payload bits stored in the least-significant bits of image channels.",
        category="pixel and bit planes",
        mode="auto",
    ),
    "pvd": DecodeOption(
        option_id="pvd",
        label="PVD (Pixel Value Differencing)",
        analyzer=analyze_pvd,
        supported_formats=["image/png", "image/jpeg", "image/gif"],
        description="Checks pixel-value differences for payloads hidden between neighboring pixels.",
        category="pixel and bit planes",
        mode="auto",
    ),
    "dct": DecodeOption(
        option_id="dct",
        label="DCT (Frequency domain)",
        analyzer=analyze_dct,
        supported_formats=["image/jpeg"],
        description="Recovers payloads embedded in JPEG frequency coefficients.",
        category="frequency domain",
        mode="auto",
    ),
    "f5": DecodeOption(
        option_id="f5",
        label="F5 (JPEG domain)",
        analyzer=analyze_f5,
        supported_formats=["image/jpeg"],
        description="Checks password-aware F5-style matrix encoding in JPEG coefficients.",
        category="frequency domain",
        mode="deep",
    ),
    "spread_spectrum": DecodeOption(
        option_id="spread_spectrum",
        label="Spread Spectrum (Password-based)",
        analyzer=analyze_spread_spectrum,
        supported_formats=["image/png", "image/jpeg", "image/gif"],
        description="Uses a password to correlate a payload spread across many image samples.",
        category="password-based recovery",
        requires_password=True,
        mode="manual",
    ),
    "palette": DecodeOption(
        option_id="palette",
        label="Palette (Color index encoding)",
        analyzer=analyze_palette,
        supported_formats=["image/png", "image/gif"],
        description="Checks indexed-color order and palette entries for hidden payload bytes.",
        category="palette and color",
        mode="auto",
    ),
    "chroma": DecodeOption(
        option_id="chroma",
        label="Chroma (Color channel hiding)",
        analyzer=analyze_chroma,
        supported_formats=["image/png", "image/jpeg", "image/gif"],
        description="Looks for data carried by subtle chroma-channel changes.",
        category="palette and color",
        mode="auto",
    ),
    "png_chunks": DecodeOption(
        option_id="png_chunks",
        label="PNG Chunks (Metadata)",
        analyzer=analyze_png_chunks,
        supported_formats=["image/png"],
        description="Inspects PNG metadata and ancillary chunks for embedded text or files.",
        category="metadata and structure",
        mode="auto",
    ),
}


REGISTRY: Dict[str, Dict[str, Any]] = {key: _wrap(opt) for key, opt in OPTIONS.items()}


def get_registry() -> Dict[str, Dict[str, Any]]:
    return REGISTRY


def get_option(option_id: str) -> Optional[DecodeOption]:
    return OPTIONS.get(option_id)

"""Audio FFT frequency-domain steganography decoder.

Detects data hidden by modulating FFT bin magnitudes above or below a
threshold in specific frequency ranges (ste.gg style).  Tries high
(14-20 kHz), mid (8-14 kHz), and low (4-8 kHz) bands.
"""

from __future__ import annotations

import struct
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .audio_utils import read_pcm_wave_mono
from .utils import update_data

AUDIO_EXTENSIONS = {".wav", ".flac", ".ogg", ".aiff", ".aif", ".au", ".raw"}

# Frequency bands to probe (label, low_hz, high_hz)
FREQ_BANDS: List[Tuple[str, int, int]] = [
    ("high", 14_000, 20_000),
    ("mid", 8_000, 14_000),
    ("low", 4_000, 8_000),
]

WINDOW_SIZE = 1024


def _read_audio(audio_path: Path) -> Optional[Tuple[Any, int]]:
    """Read audio and return (samples_1d_float64, sample_rate) or None."""
    try:
        import soundfile as sf
        import numpy as np

        data, sr = sf.read(str(audio_path), dtype="float64", always_2d=False)
        if data.ndim > 1:
            data = data.mean(axis=1)  # mix to mono
        return data, sr
    except ImportError:
        pass
    except Exception:
        pass

    try:
        from scipy.io import wavfile
        import numpy as np

        sr, data = wavfile.read(str(audio_path))
        data = data.astype(np.float64)
        if data.ndim > 1:
            data = data.mean(axis=1)
        # Normalise to -1..1
        peak = np.max(np.abs(data))
        if peak > 0:
            data = data / peak
        return data, sr
    except ImportError:
        pass
    except Exception:
        pass

    return read_pcm_wave_mono(audio_path)


def _extract_bits_from_band(
    samples: Any, sr: int, low_hz: int, high_hz: int
) -> List[int]:
    """Extract one bit per FFT window by magnitude-thresholding in *low_hz..high_hz*."""
    import numpy as np

    n = WINDOW_SIZE
    freq_res = sr / n
    bin_lo = max(1, int(low_hz / freq_res))
    bin_hi = min(n // 2, int(high_hz / freq_res))
    if bin_lo >= bin_hi:
        return []

    bits: List[int] = []
    num_frames = len(samples) // n
    # Collect magnitudes across all frames to compute adaptive threshold
    mags_all: List[float] = []
    for i in range(num_frames):
        frame = samples[i * n : (i + 1) * n]
        spectrum = np.fft.rfft(frame)
        mag = float(np.mean(np.abs(spectrum[bin_lo:bin_hi])))
        mags_all.append(mag)

    if not mags_all:
        return []

    threshold = float(np.median(mags_all))

    for mag in mags_all:
        bits.append(1 if mag >= threshold else 0)

    return bits


def _bits_to_bytes(bits: List[int]) -> bytes:
    out = bytearray()
    for i in range(0, len(bits) - 7, 8):
        byte = 0
        for j in range(8):
            byte = (byte << 1) | bits[i + j]
        out.append(byte)
    return bytes(out)


def _is_printable(data: bytes, threshold: float = 0.85) -> bool:
    if not data:
        return False
    count = sum(1 for b in data if 32 <= b < 127 or b in (9, 10, 13))
    return count / len(data) >= threshold


def _try_length_prefix(bits: List[int], prefix_bits: int) -> Optional[bytes]:
    if len(bits) < prefix_bits:
        return None
    length_val = 0
    for i in range(prefix_bits):
        length_val = (length_val << 1) | bits[i]
    needed = prefix_bits + length_val * 8
    if length_val <= 0 or length_val > 100_000 or needed > len(bits):
        return None
    payload_bits = bits[prefix_bits : prefix_bits + length_val * 8]
    return _bits_to_bytes(payload_bits)


def _check_payload(bits: List[int], band_label: str) -> List[Dict[str, Any]]:
    """Check extracted bits for a valid payload (length-prefixed or raw)."""
    findings: List[Dict[str, Any]] = []

    for prefix_size in (16, 32):
        payload = _try_length_prefix(bits, prefix_size)
        if payload and _is_printable(payload):
            findings.append(
                {
                    "method": f"fft-{band_label}-len{prefix_size}",
                    "length_prefix_bits": prefix_size,
                    "payload_length": len(payload),
                    "text": payload.decode("ascii", errors="replace"),
                }
            )

    # Raw check
    raw = _bits_to_bytes(bits)
    if raw:
        end = 0
        for i, b in enumerate(raw[:4096]):
            if 32 <= b < 127 or b in (9, 10, 13):
                end = i + 1
            elif b == 0:
                break
            else:
                break
        if end >= 8:
            findings.append(
                {
                    "method": f"fft-{band_label}-raw",
                    "payload_length": end,
                    "text": raw[:end].decode("ascii", errors="replace"),
                }
            )

    return findings


def analyze_audio_fft(input_img: Path, output_dir: Path) -> None:
    """Extract hidden data from FFT magnitude modulation in audio.

    Parameters
    ----------
    input_img : Path
        Path to the audio file (named for consistency with other analyzers).
    output_dir : Path
        Directory where results.json is stored.
    """
    audio_path = Path(input_img)

    if audio_path.suffix.lower() not in AUDIO_EXTENSIONS:
        update_data(
            output_dir,
            {
                "audio_fft": {
                    "status": "skipped",
                    "reason": f"Not an audio file (extension: {audio_path.suffix or 'none'}).",
                }
            },
        )
        return

    result = _read_audio(audio_path)
    if result is None:
        update_data(
            output_dir,
            {
                "audio_fft": {
                    "status": "error",
                    "detail": "Could not read audio file (soundfile and scipy unavailable or file unreadable).",
                }
            },
        )
        return

    samples, sr = result

    try:
        import numpy as np
    except ImportError:
        update_data(
            output_dir,
            {"audio_fft": {"status": "error", "detail": "numpy is not available."}},
        )
        return

    all_findings: List[Dict[str, Any]] = []

    for band_label, low_hz, high_hz in FREQ_BANDS:
        bits = _extract_bits_from_band(samples, sr, low_hz, high_hz)
        if bits:
            all_findings.extend(_check_payload(bits, band_label))

    if all_findings:
        update_data(
            output_dir,
            {
                "audio_fft": {
                    "status": "ok",
                    "sample_rate": sr,
                    "window_size": WINDOW_SIZE,
                    "findings": all_findings,
                }
            },
        )
    else:
        update_data(
            output_dir,
            {
                "audio_fft": {
                    "status": "empty",
                    "detail": "No hidden data found via FFT magnitude analysis.",
                }
            },
        )

"""Audio LSB steganography decoder (as used by ste.gg).

Extracts hidden data from the least-significant bits of audio samples,
trying 1-bit and 2-bit extraction in both mono and stereo-interleaved
layouts with 16-bit and 32-bit length prefixes.
"""

from __future__ import annotations

import struct
from pathlib import Path
from typing import Any, Dict, List, Optional

from .audio_utils import read_pcm_wave
from .utils import update_data

AUDIO_EXTENSIONS = {".wav", ".flac", ".ogg", ".aiff", ".aif", ".au", ".raw"}


def _read_audio_samples(audio_path: Path) -> Optional[Any]:
    """Read audio file and return samples as a 1-D int array.

    Tries soundfile first, then falls back to scipy.io.wavfile.
    Returns None if neither library is available or the file cannot be read.
    """
    # Attempt 1: soundfile
    try:
        import soundfile as sf
        import numpy as np

        data, _sr = sf.read(str(audio_path), dtype="int16", always_2d=False)
        if data.ndim > 1:
            # Flatten to interleaved samples (L0 R0 L1 R1 …)
            data = data.reshape(-1)
        return data
    except ImportError:
        pass
    except Exception:
        pass

    # Attempt 2: scipy
    try:
        from scipy.io import wavfile
        import numpy as np

        sr, data = wavfile.read(str(audio_path))
        if data.dtype not in (np.int16, np.int32):
            if data.dtype == np.float32 or data.dtype == np.float64:
                data = (data * 32767).astype(np.int16)
            else:
                data = data.astype(np.int16)
        if data.ndim > 1:
            data = data.reshape(-1)
        return data
    except ImportError:
        pass
    except Exception:
        pass

    # Dependency-light fallback for uncompressed PCM WAV carriers.
    result = read_pcm_wave(audio_path)
    if result is not None:
        samples, _sr, _channels = result
        return samples

    return None


def _extract_lsb_bits(samples: Any, num_bits: int) -> List[int]:
    """Extract *num_bits* LSBs from each sample, MSB-first order per sample."""
    import numpy as np

    bits: List[int] = []
    mask = (1 << num_bits) - 1
    for s in samples:
        val = int(s) & mask
        for shift in range(num_bits - 1, -1, -1):
            bits.append((val >> shift) & 1)
    return bits


def _bits_to_bytes(bits: List[int]) -> bytes:
    """Pack a list of 0/1 ints into bytes (big-endian bit order)."""
    out = bytearray()
    for i in range(0, len(bits) - 7, 8):
        byte = 0
        for j in range(8):
            byte = (byte << 1) | bits[i + j]
        out.append(byte)
    return bytes(out)


def _is_printable(data: bytes, threshold: float = 0.85) -> bool:
    """Return True if at least *threshold* fraction of bytes are printable ASCII."""
    if not data:
        return False
    count = sum(1 for b in data if 32 <= b < 127 or b in (9, 10, 13))
    return count / len(data) >= threshold


def _try_length_prefix(bits: List[int], prefix_bits: int) -> Optional[bytes]:
    """Try to read a big-endian length prefix of *prefix_bits* (16 or 32),
    then extract that many bytes of payload. Returns payload bytes or None."""
    if len(bits) < prefix_bits:
        return None

    length_val = 0
    for i in range(prefix_bits):
        length_val = (length_val << 1) | bits[i]

    # Sanity-check the length
    payload_bits_needed = prefix_bits + length_val * 8
    if length_val <= 0 or length_val > 100_000 or payload_bits_needed > len(bits):
        return None

    payload_bits = bits[prefix_bits : prefix_bits + length_val * 8]
    return _bits_to_bytes(payload_bits)


def _try_extraction(
    samples: Any, num_bits: int, channel_label: str
) -> List[Dict[str, Any]]:
    """Attempt LSB extraction with a given bit depth and return any findings."""
    findings: List[Dict[str, Any]] = []
    bits = _extract_lsb_bits(samples, num_bits)

    # Try with length prefix (16-bit then 32-bit)
    for prefix_size in (16, 32):
        payload = _try_length_prefix(bits, prefix_size)
        if payload and _is_printable(payload):
            findings.append(
                {
                    "method": f"lsb-{num_bits}bit-{channel_label}-len{prefix_size}",
                    "length_prefix_bits": prefix_size,
                    "payload_length": len(payload),
                    "text": payload.decode("ascii", errors="replace"),
                }
            )

    # Also try raw extraction (no length prefix) – take first N bytes and check
    raw = _bits_to_bytes(bits)
    if raw:
        # Look for longest printable run from the start
        end = 0
        for i, b in enumerate(raw[:4096]):
            if 32 <= b < 127 or b in (9, 10, 13):
                end = i + 1
            elif b == 0:
                break
            else:
                break
        if end >= 8:
            text = raw[:end].decode("ascii", errors="replace")
            findings.append(
                {
                    "method": f"lsb-{num_bits}bit-{channel_label}-raw",
                    "payload_length": end,
                    "text": text,
                }
            )

    return findings


def analyze_audio_lsb(input_img: Path, output_dir: Path) -> None:
    """Extract hidden data from LSBs of audio samples.

    Parameters
    ----------
    input_img : Path
        Path to the audio file (named for consistency with other analyzers).
    output_dir : Path
        Directory where results.json is stored.
    """
    audio_path = Path(input_img)

    # Guard: check extension
    if audio_path.suffix.lower() not in AUDIO_EXTENSIONS:
        update_data(
            output_dir,
            {
                "audio_lsb": {
                    "status": "skipped",
                    "reason": f"Not an audio file (extension: {audio_path.suffix or 'none'}).",
                }
            },
        )
        return

    samples = _read_audio_samples(audio_path)
    if samples is None:
        update_data(
            output_dir,
            {
                "audio_lsb": {
                    "status": "error",
                    "detail": "Could not read audio file (soundfile and scipy unavailable or file unreadable).",
                }
            },
        )
        return

    try:
        import numpy as np
    except ImportError:
        update_data(
            output_dir,
            {"audio_lsb": {"status": "error", "detail": "numpy is not available."}},
        )
        return

    all_findings: List[Dict[str, Any]] = []

    # --- Mono (all samples) ---
    for num_bits in (1, 2):
        all_findings.extend(_try_extraction(samples, num_bits, "mono"))

    # --- Stereo interleaved: left channel (even indices), right channel (odd) ---
    if len(samples) >= 4:
        left_ch = samples[0::2]
        right_ch = samples[1::2]
        for num_bits in (1, 2):
            all_findings.extend(_try_extraction(left_ch, num_bits, "left"))
            all_findings.extend(_try_extraction(right_ch, num_bits, "right"))

    if all_findings:
        update_data(
            output_dir,
            {
                "audio_lsb": {
                    "status": "ok",
                    "findings": all_findings,
                }
            },
        )
    else:
        update_data(
            output_dir,
            {
                "audio_lsb": {
                    "status": "empty",
                    "detail": "No hidden text found via audio LSB extraction.",
                }
            },
        )

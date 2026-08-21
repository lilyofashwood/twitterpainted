"""Echo hiding steganography decoder.

Detects data hidden via echo insertion by computing the cepstrum of
audio segments and looking for dominant echo-delay peaks at two
candidate delays (one representing bit-0, the other bit-1).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .audio_utils import read_pcm_wave_mono
from .utils import update_data

AUDIO_EXTENSIONS = {".wav", ".flac", ".ogg", ".aiff", ".aif", ".au", ".raw"}

BLOCK_SIZE = 8192

# Standard delay pairs to try (in samples).  Each tuple is (d0, d1) where
# a dominant cepstral peak at d0 encodes a 0-bit and d1 encodes a 1-bit.
DELAY_PAIRS: List[Tuple[int, int]] = [
    (150, 200),
    (100, 150),
    (200, 250),
    (50, 100),
    (80, 160),
]


def _read_audio(audio_path: Path) -> Optional[Tuple[Any, int]]:
    """Read audio and return (samples_1d_float64, sample_rate) or None."""
    try:
        import soundfile as sf
        import numpy as np

        data, sr = sf.read(str(audio_path), dtype="float64", always_2d=False)
        if data.ndim > 1:
            data = data.mean(axis=1)
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
        peak = np.max(np.abs(data))
        if peak > 0:
            data = data / peak
        return data, sr
    except ImportError:
        pass
    except Exception:
        pass

    return read_pcm_wave_mono(audio_path)


def _cepstrum(block: Any) -> Any:
    """Compute the real cepstrum of *block* (1-D array)."""
    import numpy as np

    spectrum = np.fft.fft(block)
    log_mag = np.log(np.abs(spectrum) + 1e-12)
    ceps = np.real(np.fft.ifft(log_mag))
    return ceps


def _extract_bits_for_delays(
    samples: Any, d0: int, d1: int
) -> List[int]:
    """Segment samples into blocks, compute cepstrum, and determine bits
    by comparing cepstral magnitudes at delays *d0* and *d1*."""
    import numpy as np

    num_blocks = len(samples) // BLOCK_SIZE
    if num_blocks == 0:
        return []

    bits: List[int] = []
    for i in range(num_blocks):
        block = samples[i * BLOCK_SIZE : (i + 1) * BLOCK_SIZE]
        ceps = _cepstrum(block)
        # Only look at the first half (positive quefrencies)
        half = len(ceps) // 2
        if d0 >= half or d1 >= half:
            continue
        mag_d0 = abs(ceps[d0])
        mag_d1 = abs(ceps[d1])
        bits.append(1 if mag_d1 > mag_d0 else 0)

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


def _check_payload(
    bits: List[int], delay_label: str
) -> List[Dict[str, Any]]:
    findings: List[Dict[str, Any]] = []

    for prefix_size in (16, 32):
        payload = _try_length_prefix(bits, prefix_size)
        if payload and _is_printable(payload):
            findings.append(
                {
                    "method": f"echo-{delay_label}-len{prefix_size}",
                    "length_prefix_bits": prefix_size,
                    "payload_length": len(payload),
                    "text": payload.decode("ascii", errors="replace"),
                }
            )

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
                    "method": f"echo-{delay_label}-raw",
                    "payload_length": end,
                    "text": raw[:end].decode("ascii", errors="replace"),
                }
            )

    return findings


def analyze_audio_echo(input_img: Path, output_dir: Path) -> None:
    """Decode echo-hiding steganography from an audio file.

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
                "audio_echo": {
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
                "audio_echo": {
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
            {"audio_echo": {"status": "error", "detail": "numpy is not available."}},
        )
        return

    all_findings: List[Dict[str, Any]] = []

    for d0, d1 in DELAY_PAIRS:
        delay_label = f"d{d0}-{d1}"
        bits = _extract_bits_for_delays(samples, d0, d1)
        if bits:
            all_findings.extend(_check_payload(bits, delay_label))

    if all_findings:
        update_data(
            output_dir,
            {
                "audio_echo": {
                    "status": "ok",
                    "sample_rate": sr,
                    "block_size": BLOCK_SIZE,
                    "findings": all_findings,
                }
            },
        )
    else:
        update_data(
            output_dir,
            {
                "audio_echo": {
                    "status": "empty",
                    "detail": "No hidden data found via echo hiding analysis.",
                }
            },
        )

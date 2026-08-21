"""Spectrogram art decoder (Aphex Twin style).

Generates a spectrogram image from an audio file and stores it as a
base64 PNG data URL artifact for visual inspection.
"""

from __future__ import annotations

import base64
import io
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from .audio_utils import read_pcm_wave_mono
from .utils import update_data

AUDIO_EXTENSIONS = {".wav", ".flac", ".ogg", ".aiff", ".aif", ".au", ".raw"}


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


def _spectrogram_data(samples: Any, sr: int) -> Tuple[Any, Any, Any]:
    """Return spectrogram arrays using SciPy when present, otherwise NumPy."""
    import numpy as np

    nperseg = min(1024, len(samples))
    if nperseg < 2:
        return np.array([]), np.array([]), np.empty((0, 0))
    noverlap = nperseg // 2

    try:
        from scipy.signal import spectrogram as scipy_spectrogram

        return scipy_spectrogram(
            samples, fs=sr, nperseg=nperseg, noverlap=noverlap
        )
    except ImportError:
        step = max(1, nperseg - noverlap)
        starts = range(0, max(1, len(samples) - nperseg + 1), step)
        window = np.hanning(nperseg)
        spectra = []
        times = []
        for start in starts:
            frame = np.asarray(samples[start : start + nperseg], dtype=np.float64)
            if frame.size < nperseg:
                frame = np.pad(frame, (0, nperseg - frame.size))
            spectra.append(np.abs(np.fft.rfft(frame * window)) ** 2)
            times.append((start + nperseg / 2) / sr)
        matrix = np.asarray(spectra, dtype=np.float64).T
        frequencies = np.fft.rfftfreq(nperseg, d=1.0 / sr)
        return frequencies, np.asarray(times), matrix


def _generate_spectrogram_image(samples: Any, sr: int) -> Optional[str]:
    """Generate a spectrogram and return it as a base64 PNG data URL string."""
    try:
        import numpy as np
    except ImportError:
        return None

    try:
        from PIL import Image
    except ImportError:
        return None

    _freqs, _times, Sxx = _spectrogram_data(samples, sr)
    if Sxx.size == 0:
        return None

    # Convert to dB scale, clip, and normalise to 0-255
    Sxx_db = 10 * np.log10(Sxx + 1e-12)
    vmin = float(np.percentile(Sxx_db, 5))
    vmax = float(np.percentile(Sxx_db, 99))
    if vmax <= vmin:
        vmax = vmin + 1.0

    normalised = np.clip((Sxx_db - vmin) / (vmax - vmin), 0, 1)
    gray = (normalised * 255).astype(np.uint8)

    # Flip vertically so low frequencies are at the bottom
    gray = gray[::-1, :]

    img = Image.fromarray(gray, mode="L")

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    b64 = base64.b64encode(buf.read()).decode("ascii")
    return f"data:image/png;base64,{b64}"


def _detect_patterns(samples: Any, sr: int) -> Dict[str, Any]:
    """Run basic pattern detection on the spectrogram matrix.

    Returns a dict with any detected features (e.g. bright horizontal
    lines, text-like regions).  Currently a simple heuristic.
    """
    try:
        import numpy as np
    except ImportError:
        return {"detected": False, "detail": "numpy not available for pattern detection."}

    _freqs, _times, Sxx = _spectrogram_data(samples, sr)
    if Sxx.size == 0:
        return {"detected": False, "detail": "Audio is too short for pattern detection."}

    Sxx_db = 10 * np.log10(Sxx + 1e-12)
    mean_energy = float(np.mean(Sxx_db))
    max_energy = float(np.max(Sxx_db))

    # Check for horizontal bright lines (constant-frequency tones)
    row_means = np.mean(Sxx_db, axis=1)
    row_std = float(np.std(row_means))
    bright_rows = int(np.sum(row_means > (np.mean(row_means) + 2 * row_std)))

    # Check for high-contrast vertical structure (text-like patterns)
    col_std = float(np.mean(np.std(Sxx_db, axis=0)))

    patterns: Dict[str, Any] = {
        "detected": bright_rows > 3 or col_std > 5.0,
        "bright_frequency_rows": bright_rows,
        "mean_energy_db": round(mean_energy, 2),
        "max_energy_db": round(max_energy, 2),
        "column_contrast_std": round(col_std, 2),
    }
    return patterns


def analyze_audio_spectrogram(input_img: Path, output_dir: Path) -> None:
    """Generate a spectrogram image from an audio file for visual inspection.

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
                "audio_spectrogram": {
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
                "audio_spectrogram": {
                    "status": "error",
                    "detail": "Could not read audio file (soundfile and scipy unavailable or file unreadable).",
                }
            },
        )
        return

    samples, sr = result

    data_url = _generate_spectrogram_image(samples, sr)
    if data_url is None:
        update_data(
            output_dir,
            {
                "audio_spectrogram": {
                    "status": "error",
                    "detail": "Could not generate spectrogram (scipy or PIL unavailable).",
                }
            },
        )
        return

    patterns = _detect_patterns(samples, sr)

    update_data(
        output_dir,
        {
            "audio_spectrogram": {
                "status": "ok",
                "sample_rate": sr,
                "num_samples": len(samples),
                "spectrogram_png": data_url,
                "pattern_detection": patterns,
            }
        },
    )

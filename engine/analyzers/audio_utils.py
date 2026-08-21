"""Dependency-light PCM WAV readers shared by audio analyzers."""

from __future__ import annotations

import wave
from pathlib import Path
from typing import Any, Optional, Tuple

import numpy as np


def read_pcm_wave(path: Path) -> Optional[Tuple[Any, int, int]]:
    """Return interleaved integer samples, sample rate, and channel count."""
    try:
        with wave.open(str(path), "rb") as wav_file:
            channels = wav_file.getnchannels()
            sample_width = wav_file.getsampwidth()
            sample_rate = wav_file.getframerate()
            frames = wav_file.readframes(wav_file.getnframes())
    except (OSError, EOFError, wave.Error):
        return None

    if channels <= 0 or sample_rate <= 0 or not frames:
        return None

    if sample_width == 1:
        samples = np.frombuffer(frames, dtype=np.uint8).astype(np.int16) - 128
    elif sample_width == 2:
        samples = np.frombuffer(frames, dtype="<i2")
    elif sample_width == 3:
        raw = np.frombuffer(frames, dtype=np.uint8)
        usable = (raw.size // 3) * 3
        if usable == 0:
            return None
        triples = raw[:usable].reshape(-1, 3).astype(np.int32)
        samples = triples[:, 0] | (triples[:, 1] << 8) | (triples[:, 2] << 16)
        samples = np.where(samples & 0x800000, samples - 0x1000000, samples)
    elif sample_width == 4:
        samples = np.frombuffer(frames, dtype="<i4")
    else:
        return None

    return samples, sample_rate, channels


def read_pcm_wave_mono(path: Path) -> Optional[Tuple[Any, int]]:
    """Return float64 mono samples and sample rate for an uncompressed WAV."""
    result = read_pcm_wave(path)
    if result is None:
        return None
    samples, sample_rate, channels = result
    values = samples.astype(np.float64)
    if channels > 1:
        usable = (values.size // channels) * channels
        if usable == 0:
            return None
        values = values[:usable].reshape(-1, channels).mean(axis=1)
    peak = float(np.max(np.abs(values))) if values.size else 0.0
    if peak > 0:
        values = values / peak
    return values, sample_rate

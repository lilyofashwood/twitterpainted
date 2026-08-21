import json
from pathlib import Path
import wave

import numpy as np
import pytest

from engine.analyzers.audio_echo import analyze_audio_echo
from engine.analyzers.audio_fft import analyze_audio_fft
from engine.analyzers.audio_lsb import analyze_audio_lsb
from engine.analyzers.audio_spectrogram import analyze_audio_spectrogram


FIXTURES = Path(__file__).resolve().parent / "fixtures"


@pytest.mark.parametrize(
    ("analyzer_id", "analyzer"),
    (
        ("audio_lsb", analyze_audio_lsb),
        ("audio_fft", analyze_audio_fft),
        ("audio_echo", analyze_audio_echo),
        ("audio_spectrogram", analyze_audio_spectrogram),
    ),
)
def test_audio_analyzers_skip_image_inputs(tmp_path, analyzer_id, analyzer):
    analyzer(FIXTURES / "lsb.png", tmp_path)

    results = json.loads((tmp_path / "results.json").read_text(encoding="utf-8"))
    result = results[analyzer_id]

    assert result["status"] == "skipped"
    assert result["reason"].startswith("Not an audio file")


def _write_wav(path: Path, samples: np.ndarray, sample_rate: int = 44_100) -> None:
    with wave.open(str(path), "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(samples.astype(np.int16).tobytes())


def test_audio_lsb_recovers_a_length_prefixed_payload(tmp_path):
    payload = b"secret"
    bit_string = f"{len(payload):016b}" + "".join(f"{byte:08b}" for byte in payload)
    samples = np.zeros(32_768, dtype=np.int16)
    samples[: len(bit_string)] = [int(bit) for bit in bit_string]
    carrier = tmp_path / "carrier.wav"
    _write_wav(carrier, samples)

    analyze_audio_lsb(carrier, tmp_path)

    results = json.loads((tmp_path / "results.json").read_text(encoding="utf-8"))
    result = results["audio_lsb"]
    assert result["status"] == "ok"
    assert result["findings"][0]["text"] == "secret"


def test_audio_spectrogram_generates_a_png_preview(tmp_path):
    samples = np.zeros(8_192, dtype=np.int16)
    carrier = tmp_path / "carrier.wav"
    _write_wav(carrier, samples)

    analyze_audio_spectrogram(carrier, tmp_path)

    results = json.loads((tmp_path / "results.json").read_text(encoding="utf-8"))
    result = results["audio_spectrogram"]
    assert result["status"] == "ok"
    assert result["spectrogram_png"].startswith("data:image/png;base64,")

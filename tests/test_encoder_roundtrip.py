from __future__ import annotations

import base64
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
from PIL import Image

from engine.decode_registry import get_registry
from engine.encoder import (
    TWITTER_MAX_BYTES,
    encode_chroma_payload,
    encode_dct_payload,
    encode_f5_payload,
    encode_lsb_payload,
    encode_palette_payload,
    encode_payload,
    encode_png_chunks_payload,
    encode_pvd_payload,
    encode_spread_spectrum_payload,
)
from engine.decoder import run_analysis


def _cover(size: int = 256) -> bytes:
    rng = np.random.default_rng(2026)
    arr = rng.integers(0, 256, size=(size, size, 3), dtype=np.uint8)
    buf = BytesIO()
    Image.fromarray(arr).save(buf, format="PNG")
    return buf.getvalue()


def _analyze(option_id: str, image_bytes: bytes, suffix: str, password: str | None = None):
    with TemporaryDirectory() as tmp:
        path = Path(tmp) / f"encoded{suffix}"
        path.write_bytes(image_bytes)
        option = get_registry()[option_id]
        params = option["params"](option, {"password": password})
        return option["analyzer"](path, **params)


def test_simple_text_and_file_round_trip():
    _, text_image = encode_payload(_cover(), text="love survives 🖤")
    text_result = run_analysis(
        text_image,
        "encoded.png",
        selected_tools=["simple_lsb"],
    )["results"]["simple_lsb"]
    assert text_result["decoded_text"]["RGB"] == "love survives 🖤"

    payload = b"a binary love letter\x00\xff"
    _, file_image = encode_payload(_cover(), mode="zlib", file_data=payload)
    file_result = run_analysis(
        file_image,
        "encoded.png",
        selected_tools=["simple_zlib"],
    )["results"]["simple_zlib"]
    matches = file_result["matches"]
    assert matches and matches[0]["strategy"] == "length_prefix"
    assert matches[0]["preview"].startswith("YSBiaW5hcnkgbG92ZSBsZXR0ZXI")
    assert len(file_image) <= TWITTER_MAX_BYTES


def test_lossless_encoders_round_trip():
    cover = _cover()
    cases = [
        ("lsb", encode_lsb_payload, {}, ".png"),
        ("pvd", encode_pvd_payload, {}, ".png"),
        ("palette", encode_palette_payload, {}, ".png"),
        ("chroma", encode_chroma_payload, {}, ".png"),
    ]
    for option_id, encoder, kwargs, suffix in cases:
        _, encoded = encoder(cover, b"ROUNDTRIP", **kwargs)
        result = _analyze(option_id, encoded, suffix)
        assert "ROUNDTRIP" in result["details"].get("preview", ""), (option_id, result)


def test_dct_high_survives_jpeg_recompression():
    _, encoded = encode_dct_payload(_cover(), b"DCT_SURVIVE", robustness="high")
    result = _analyze("dct", encoded, ".jpg")
    assert "DCT_SURVIVE" in result["details"].get("preview", "")
    assert len(encoded) <= TWITTER_MAX_BYTES

    image = Image.open(BytesIO(encoded)).convert("RGB")
    recompressed = BytesIO()
    image.save(recompressed, format="JPEG", quality=75, subsampling=2)
    result = _analyze("dct", recompressed.getvalue(), ".jpg")
    assert "DCT_SURVIVE" in result["details"].get("preview", "")


def test_password_encoders_round_trip():
    cover = _cover()
    _, f5_image = encode_f5_payload(cover, b"F5_ROUNDTRIP", password="black-heart")
    f5 = _analyze("f5", f5_image, ".jpg", password="black-heart")
    assert "F5_ROUNDTRIP" in f5["details"].get("preview", "")

    _, spread_image = encode_spread_spectrum_payload(
        cover, b"SPREAD_ROUNDTRIP", password="black-heart"
    )
    spread = _analyze("spread_spectrum", spread_image, ".png", password="black-heart")
    assert "SPREAD_ROUNDTRIP" in spread["details"].get("preview", "")


def test_png_chunk_unicode_falls_back_to_itxt():
    _, encoded = encode_png_chunks_payload(_cover(), "love 🖤".encode(), chunk_type="tEXt")
    result = _analyze("png_chunks", encoded, ".png")
    text = " ".join(item["text"] for item in result["details"]["text"])
    assert "love 🖤" in text


def test_default_api_round_trip_uses_simple_lsb():
    from app import app

    client = app.test_client()
    encoded_response = client.post(
        "/api/encode",
        data={"image": (BytesIO(_cover()), "cover.png"), "text": "DEFAULT_LSB"},
        content_type="multipart/form-data",
    )
    assert encoded_response.status_code == 200
    assert encoded_response.json["filename"].endswith(".png")
    encoded = base64.b64decode(encoded_response.json["data_url"].split(",", 1)[1])

    decoded_response = client.post(
        "/api/decode",
        data={"image": (BytesIO(encoded), "encoded.png")},
        content_type="multipart/form-data",
    )
    assert decoded_response.status_code == 200
    assert (
        decoded_response.json["results"]["simple_lsb"]["decoded_text"]["RGB"]
        == "DEFAULT_LSB"
    )

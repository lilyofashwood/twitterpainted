from __future__ import annotations

import base64
import json
from io import BytesIO

import numpy as np
from PIL import Image

from app import app
from engine.analyzers.simple_lsb import _decode_plane
from engine.decoder import run_analysis
from engine.encoder import TWITTER_MAX_EDGE, twitter_png_profile


def _cover(image_format: str = "PNG", size: int = 128) -> bytes:
    rng = np.random.default_rng(20260820)
    pixels = rng.integers(0, 256, size=(size, size, 3), dtype=np.uint8)
    buffer = BytesIO()
    options = {"quality": 95} if image_format == "JPEG" else {}
    Image.fromarray(pixels, "RGB").save(buffer, format=image_format, **options)
    return buffer.getvalue()


def _encoded_bytes(response) -> bytes:
    return base64.b64decode(response.json["data_url"].split(",", 1)[1])


def _large_translucent_cover() -> bytes:
    y, x = np.indices((800, 1200), dtype=np.uint16)
    pixels = np.empty((800, 1200, 4), dtype=np.uint8)
    pixels[..., 0] = x % 256
    pixels[..., 1] = y % 256
    pixels[..., 2] = (x + y) % 256
    pixels[..., 3] = 48 + ((x * 3 + y * 5) % 208)
    buffer = BytesIO()
    Image.fromarray(pixels, "RGBA").save(
        buffer,
        format="PNG",
        exif=Image.Exif(),
    )
    return buffer.getvalue()


def test_twitterpaint_combined_accepts_jpeg_source_and_defaults_to_verified_png():
    client = app.test_client()
    response = client.post(
        "/api/encode",
        data={
            "image": (BytesIO(_cover("JPEG")), "carrier.JPEG"),
            "encodeMethod": "twitterpaint",
            "twitterpaintMode": "combined",
            "twitterpaintText": "follow the signal",
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 200
    assert response.json["filename"].endswith(".png")
    encoded = _encoded_bytes(response)
    assert encoded.startswith(b"\x89PNG\r\n\x1a\n")
    verification = response.json["verification"]
    assert verification["checked_planes"] == ["RGB"]
    assert verification["output_format"] == "png"
    assert verification["round_trip"] is True
    assert verification["survivor_ready"] is True
    assert verification["status"] == "passed"
    assert verification["twitterpaint_mode"] == "combined"
    assert verification["profile"]["ready"] is True
    assert verification["profile"]["opaque_rgb"] is True
    assert verification["profile"]["dimensions_ok"] is True
    assert "680px" in verification["message"]


def test_twitterpaint_individual_is_text_only_rgb_and_round_trips_selected_channels():
    client = app.test_client()
    channels = {
        "R": {"enabled": True, "type": "text", "text": "red secret"},
        "G": {"enabled": True, "type": "text", "text": "green secret"},
        "B": {"enabled": True, "type": "text", "text": "blue secret"},
    }
    response = client.post(
        "/api/encode",
        data={
            "image": (BytesIO(_cover()), "carrier.png"),
            "encodeMethod": "twitterpaint",
            "twitterpaintMode": "individual",
            "channels": json.dumps(channels),
            "outputFormat": "png",
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 200
    assert response.json["verification"]["status"] == "passed"
    assert response.json["verification"]["checked_planes"] == ["R", "G", "B"]
    assert response.json["verification"]["survivor_ready"] is True
    result = run_analysis(
        _encoded_bytes(response),
        "encoded.png",
        selected_tools=["advanced_lsb"],
    )["results"]["advanced_lsb"]
    assert result["details"]["text_channels"]["R"]["text_preview"] == "red secret"
    assert result["details"]["text_channels"]["G"]["text_preview"] == "green secret"
    assert result["details"]["text_channels"]["B"]["text_preview"] == "blue secret"


def test_twitterpaint_survivor_profile_fits_before_embedding_and_flattens_alpha():
    client = app.test_client()
    response = client.post(
        "/api/encode",
        data={
            "image": (BytesIO(_large_translucent_cover()), "too-wide-with-alpha.png"),
            "encodeMethod": "twitterpaint",
            "twitterpaintMode": "combined",
            "twitterpaintText": "resize first; paint last",
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 200
    encoded = _encoded_bytes(response)
    profile = twitter_png_profile(encoded)
    assert profile["ready"] is True
    assert max(profile["width"], profile["height"]) == TWITTER_MAX_EDGE
    image = Image.open(BytesIO(encoded))
    assert image.mode == "RGB"
    assert _decode_plane(image.convert("RGBA"), "RGB") == "resize first; paint last"


def test_twitterpaint_rejects_flat_carrier_outside_truecolor_guard():
    cover = BytesIO()
    Image.new("RGB", (512, 512), (8, 8, 8)).save(cover, format="PNG")
    response = app.test_client().post(
        "/api/encode",
        data={
            "image": (BytesIO(cover.getvalue()), "flat.png"),
            "encodeMethod": "twitterpaint",
            "twitterpaintMode": "combined",
            "twitterpaintText": "not enough texture",
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 400
    assert "at least 257 distinct RGB colors" in response.json["error"]


def test_twitterpaint_individual_rejects_alpha_and_files():
    client = app.test_client()
    alpha_response = client.post(
        "/api/encode",
        data={
            "image": (BytesIO(_cover()), "carrier.png"),
            "encodeMethod": "twitterpaint",
            "twitterpaintMode": "individual",
            "channels": json.dumps(
                {"A": {"enabled": True, "type": "text", "text": "not supported"}}
            ),
        },
        content_type="multipart/form-data",
    )
    assert alpha_response.status_code == 400
    assert "alpha is excluded" in alpha_response.json["error"]

    file_response = client.post(
        "/api/encode",
        data={
            "image": (BytesIO(_cover()), "carrier.png"),
            "encodeMethod": "twitterpaint",
            "twitterpaintMode": "individual",
            "channels": json.dumps(
                {"R": {"enabled": True, "type": "file", "text": ""}}
            ),
            "file_R": (BytesIO(b"hidden"), "secret.bin"),
        },
        content_type="multipart/form-data",
    )
    assert file_response.status_code == 400
    assert "must contain text" in file_response.json["error"]


def test_twitterpaint_jpeg_export_is_real_and_reports_its_round_trip_result():
    client = app.test_client()
    response = client.post(
        "/api/encode",
        data={
            "image": (BytesIO(_cover()), "carrier.png"),
            "encodeMethod": "twitterpaint",
            "twitterpaintMode": "combined",
            "twitterpaintText": "the code kept its promise",
            "outputFormat": "jpeg",
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 200
    assert response.json["filename"].endswith(".jpeg")
    assert _encoded_bytes(response).startswith(b"\xff\xd8\xff")
    verification = response.json["verification"]
    assert verification["output_format"] == "jpeg"
    assert verification["status"] in {"passed", "failed"}
    assert verification["round_trip"] is (verification["status"] == "passed")
    assert "self-check" in verification["message"].lower()


def test_twitterpaint_jpeg_export_handles_high_entropy_carrier():
    client = app.test_client()
    response = client.post(
        "/api/encode",
        data={
            "image": (BytesIO(_cover(size=512)), "noisy-carrier.png"),
            "encodeMethod": "twitterpaint",
            "twitterpaintMode": "combined",
            "twitterpaintText": "q95 experiment",
            "outputFormat": "jpeg",
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 200
    assert _encoded_bytes(response).startswith(b"\xff\xd8\xff")
    assert response.json["verification"]["output_format"] == "jpeg"


def test_twitterpaint_individual_can_emit_an_experimental_verified_jpeg():
    client = app.test_client()
    response = client.post(
        "/api/encode",
        data={
            "image": (BytesIO(_cover()), "carrier.png"),
            "encodeMethod": "twitterpaint",
            "twitterpaintMode": "individual",
            "channels": json.dumps(
                {"B": {"enabled": True, "type": "text", "text": "blue risk"}}
            ),
            "outputFormat": "jpeg",
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 200
    assert response.json["filename"].endswith(".jpeg")
    assert _encoded_bytes(response).startswith(b"\xff\xd8\xff")
    verification = response.json["verification"]
    assert verification["checked_planes"] == ["B"]
    assert verification["output_format"] == "jpeg"
    assert verification["round_trip"] is (verification["status"] == "passed")


def test_twitterpaint_paths_are_mutually_exclusive():
    client = app.test_client()
    response = client.post(
        "/api/encode",
        data={
            "image": (BytesIO(_cover()), "carrier.png"),
            "encodeMethod": "twitterpaint",
            "twitterpaintMode": "combined+individual",
            "twitterpaintText": "no",
        },
        content_type="multipart/form-data",
    )
    assert response.status_code == 400
    assert "combined' or 'individual" in response.json["error"]

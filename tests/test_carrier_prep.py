from __future__ import annotations

import base64
import json
from io import BytesIO
from pathlib import Path

import numpy as np
from PIL import Image

from app import app
from engine.analyzers.simple_lsb import _decode_plane
from engine.encoder import (
    COMPACT_MAX_EDGE,
    GENTLE_MAX_EDGE,
    TWITTER_MAX_BYTES,
    TWITTER_MAX_EDGE,
    normalize_carrier_prep,
    prepare_carrier_bytes,
    twitter_png_profile,
)


ROOT = Path(__file__).resolve().parents[1]


def _noise(width: int, height: int, *, alpha: bool = False) -> bytes:
    rng = np.random.default_rng(20260820)
    channels = 4 if alpha else 3
    pixels = rng.integers(0, 256, size=(height, width, channels), dtype=np.uint8)
    if alpha:
        pixels[..., 3] = np.arange(width, dtype=np.uint16)[None, :] % 256
    buffer = BytesIO()
    Image.fromarray(pixels, "RGBA" if alpha else "RGB").save(buffer, format="PNG")
    return buffer.getvalue()


def _response_bytes(response) -> bytes:
    return base64.b64decode(response.json["data_url"].split(",", 1)[1])


def test_named_prep_profiles_have_distinct_lossless_geometry_and_alpha_rules():
    source = _noise(1800, 900, alpha=True)

    assert prepare_carrier_bytes(source, "none") == source

    gentle = Image.open(BytesIO(prepare_carrier_bytes(source, "gentle")))
    assert gentle.size == (GENTLE_MAX_EDGE, 800)
    assert gentle.mode == "RGBA"

    compact = Image.open(BytesIO(prepare_carrier_bytes(source, "compact")))
    assert max(compact.size) == COMPACT_MAX_EDGE
    assert compact.mode == "RGB"

    twitter = prepare_carrier_bytes(source, "twitterpaint")
    profile = twitter_png_profile(twitter)
    assert profile["ready"] is True
    assert max(profile["width"], profile["height"]) <= TWITTER_MAX_EDGE
    assert len(twitter) <= TWITTER_MAX_BYTES


def test_preparation_applies_phone_exif_orientation_before_stripping_metadata():
    source = BytesIO()
    exif = Image.Exif()
    exif[274] = 6
    Image.new("RGB", (40, 20), (90, 30, 60)).save(
        source,
        format="JPEG",
        quality=95,
        exif=exif,
    )

    prepared = Image.open(BytesIO(prepare_carrier_bytes(source.getvalue(), "gentle")))
    assert prepared.size == (20, 40)
    assert not prepared.getexif()


def test_legacy_blunt_axe_halves_until_below_the_historical_cap():
    source = _noise(900, 900)
    prepared = prepare_carrier_bytes(source, "legacy")
    image = Image.open(BytesIO(prepared))

    assert len(source) > TWITTER_MAX_BYTES
    assert len(prepared) <= TWITTER_MAX_BYTES
    assert image.size in {(450, 450), (225, 225)}


def test_twitterpaint_with_non_survivor_prep_is_honest_but_still_decodes_locally():
    response = app.test_client().post(
        "/api/encode",
        data={
            "image": (BytesIO(_noise(128, 128)), "carrier.png"),
            "encodeMethod": "twitterpaint",
            "twitterpaintMode": "combined",
            "twitterpaintText": "local only",
            "carrierPrep": "none",
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 200
    assert response.json["carrier_prep"] == "none"
    verification = response.json["verification"]
    assert verification["round_trip"] is True
    assert verification["survivor_ready"] is False
    assert verification["status"] == "failed"
    assert "survivor status is off" in verification["message"].lower()
    assert Image.open(BytesIO(_response_bytes(response))).size == (128, 128)


def test_api_rejects_unknown_carrier_prep():
    response = app.test_client().post(
        "/api/encode",
        data={
            "image": (BytesIO(_noise(64, 64)), "carrier.png"),
            "encodeMethod": "twitterpaint",
            "twitterpaintMode": "combined",
            "twitterpaintText": "nope",
            "carrierPrep": "mystery meat",
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 400
    assert "unknown carrier preparation" in response.json["error"].lower()


def test_advanced_lsb_can_leave_geometry_and_alpha_intact():
    source = _noise(96, 64, alpha=True)
    response = app.test_client().post(
        "/api/encode",
        data={
            "image": (BytesIO(source), "carrier.png"),
            "encodeMethod": "advanced_lsb",
            "carrierPrep": "none",
            "channels": json.dumps(
                {"A": {"enabled": True, "type": "text", "text": "alpha stays"}}
            ),
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 200
    encoded = Image.open(BytesIO(_response_bytes(response)))
    assert encoded.size == (96, 64)
    assert encoded.mode == "RGBA"
    assert _decode_plane(encoded, "A") == "alpha stays"


def test_full_lab_exposes_the_five_prep_choices_and_method_aware_defaults():
    html = (ROOT / "templates/index.html").read_text()
    script = (ROOT / "static/app.js").read_text()

    for value in ("twitterpaint", "none", "legacy", "gentle", "compact"):
        assert f'<option value="{value}"' in html
        assert f"{value}:" in script
    assert "blunt axe" in script
    assert "pliny" not in html.lower()
    assert "method === 'twitterpaint' ? 'twitterpaint' : 'none'" in script
    assert "carrierPrep" in html
    assert "autoCompressCarrier" not in script
    assert "assignFileToInput(carrierInput" not in script


def test_normalize_carrier_prep_lists_valid_choices_on_error():
    try:
        normalize_carrier_prep("unknown")
    except ValueError as exc:
        message = str(exc)
    else:
        raise AssertionError("unknown preparation should fail")

    assert "twitterpaint" in message
    assert "none" in message
    assert "legacy" in message

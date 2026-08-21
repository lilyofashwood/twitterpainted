from io import BytesIO
import json

import numpy as np
from PIL import Image

from engine.analyzers.payload_unwrap import analyze_payload_unwrap
from engine.encoder import encode_payload


def test_payload_unwrap_removes_the_complete_flag_prefix(tmp_path):
    rng = np.random.default_rng(3)
    pixels = rng.integers(0, 256, size=(128, 128, 3), dtype=np.uint8)
    cover = BytesIO()
    Image.fromarray(pixels).save(cover, format="PNG")
    _, encoded = encode_payload(cover.getvalue(), text="flag{c2VjcmV0LWxvdmU=}")
    carrier = tmp_path / "payload.png"
    carrier.write_bytes(encoded)

    analyze_payload_unwrap(carrier, tmp_path)

    results = json.loads((tmp_path / "results.json").read_text(encoding="utf-8"))
    payload = results["payload_unwrap"]["details"]["payloads"][0]
    previews = [candidate["preview"] for candidate in payload["candidates"]]

    assert payload["payload_bytes"] == len(b"c2VjcmV0LWxvdmU=")
    assert "secret-love" in previews

"""Recovered filename-confinement proposal, adapted without reverting newer work."""
import io

import unittest
from PIL import Image

from engine.encoder import _safe_upload_name, encode_multi_channel, encode_payload


class UploadNameContracts(unittest.TestCase):
    def test_safe_upload_basename(self):
        for name, expected in [
            ("../../outside.png", "outside.png"),
            (r"C:\Users\someone\secret.png", "secret.png"),
            ("/tmp/out.png", "out.png"),
            ("\x00\nhello\t.png", "hello.png"),
            ("../..", "input.png"), (".", "input.png"),
            ("", "input.png"), (None, "input.png"), ("雨.png", "雨.png"),
        ]:
            with self.subTest(name=name):
                self.assertEqual(_safe_upload_name(name), expected)

    def test_encoder_entry_points_use_safe_names(self):
        for filename in ["../../outside.png", r"C:\outside.png", "../..", "\x00"]:
            with self.subTest(filename=filename):
                buffer = io.BytesIO()
                Image.new("RGB", (32, 32), (64, 128, 192)).save(buffer, format="PNG")
                carrier = buffer.getvalue()
                simple_name, simple = encode_payload(carrier, filename=filename, text="λ 🌙", carrier_prep="none")
                multi_name, multi = encode_multi_channel(carrier, {"R": {"enabled": True, "type": "text", "text": "λ 🌙"}}, filename=filename, carrier_prep="none")
                self.assertEqual(simple_name, "encoded.png")
                self.assertEqual(multi_name, "encoded.png")
                self.assertTrue(simple.startswith(b"\x89PNG") and multi.startswith(b"\x89PNG"))


if __name__ == "__main__":
    unittest.main()

"""Compressed STEG recovery must not expand or export rejected streams."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
import zlib

import numpy as np
from PIL import Image

from engine.analyzers import stegg
from engine.analyzers.bounded_zlib import MAX_DECOMPRESSED_BYTES


def carrier(path, compressed, original, *, bad_crc=False):
    header = bytearray(32)
    header[:4] = b"STEG"
    header[4:9] = bytes([3, 7, 1, 0, 1])
    header[16:20] = len(compressed).to_bytes(4, "big")
    header[20:24] = len(original).to_bytes(4, "big")
    checksum = zlib.crc32(original) ^ int(bad_crc)
    header[24:28] = checksum.to_bytes(4, "big")
    wire = np.unpackbits(np.frombuffer(header + compressed, dtype=np.uint8))
    pixels = np.full((128, 128, 4), 254, dtype=np.uint8)
    for index, bit in enumerate(wire):
        pixels.reshape(-1, 4)[index // 3, index % 3] |= bit
    Image.fromarray(pixels).save(path)


class SteggBoundsContracts(unittest.TestCase):
    def test_deflate_variants_and_over_limit_rejection(self):
        payload = b"x" * MAX_DECOMPRESSED_BYTES
        self.assertEqual(stegg._maybe_decompress(zlib.compress(payload)), (payload, True))
        raw = zlib.compressobj(wbits=-15)
        stream = raw.compress(b"exact raw deflate") + raw.flush()
        self.assertEqual(stegg._maybe_decompress(stream), (b"exact raw deflate", True))
        bomb = zlib.compress(payload + b"x")
        self.assertFalse(stegg._maybe_decompress(bomb)[1])
        self.assertFalse(stegg._maybe_decompress(zlib.compress(b"x")[:-1])[1])

    def test_rejected_compressed_carrier_never_exports(self):
        original = b"z" * (MAX_DECOMPRESSED_BYTES + 1)
        with TemporaryDirectory() as folder:
            root = Path(folder)
            image = root / "bomb.png"
            carrier(image, zlib.compress(original), original)
            with patch.object(stegg, "_write_payload", side_effect=AssertionError("rejected stream exported")):
                stegg.analyze_stegg(image, root)
            report = json.loads((root / "results.json").read_text())["stegg"]
            self.assertEqual(report["status"], "error")
            self.assertFalse(report["output"]["decompress_ok"])
            self.assertIsNone(report["output"]["file"])

    def test_exact_unicode_recovery_and_crc_mismatch_is_unverified(self):
        original = "\ufeff  leaf\n\x00 cafe\u0301 \u2728\n".encode()
        for bad_crc in (False, True):
            with self.subTest(bad_crc=bad_crc), TemporaryDirectory() as folder:
                root = Path(folder)
                image = root / "normal.png"
                carrier(image, zlib.compress(original), original, bad_crc=bad_crc)
                with patch.object(stegg.shutil, "which", return_value=None):
                    stegg.analyze_stegg(image, root)
                report = json.loads((root / "results.json").read_text())["stegg"]["output"]
                self.assertEqual((root / report["file"]).read_bytes(), original)
                self.assertEqual(report["crc_ok"], not bad_crc)
                self.assertEqual(report["verification"], "unverified_crc_mismatch" if bad_crc else "crc32_match")


if __name__ == "__main__":
    unittest.main()

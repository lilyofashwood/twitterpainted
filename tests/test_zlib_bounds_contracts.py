"""Dependency-light regression checks for hostile compressed carrier bytes."""

import gzip
import unittest
import zlib
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import numpy as np
from PIL import Image

from engine.analyzers import advanced_lsb, simple_zlib
from engine.analyzers.bounded_zlib import MAX_DECOMPRESSED_BYTES, decompress_deflate


class ZlibBoundsContracts(unittest.TestCase):
    def test_exact_cap_and_first_stream_trailing_bytes(self):
        exact = b"a" * MAX_DECOMPRESSED_BYTES
        self.assertEqual(decompress_deflate(zlib.compress(exact)), exact)
        message = "\ufeff  stars\n\x00 cafe\u0301 \u2728\n".encode()
        self.assertEqual(decompress_deflate(zlib.compress(message) + b"carrier"), message)
        self.assertEqual(decompress_deflate(gzip.compress(message), wbits=31), message)
        with self.assertRaises(ValueError):
            decompress_deflate(gzip.compress(message) + gzip.compress(message), wbits=31, reject_trailing=True)
        for decode in (simple_zlib._try_decompress,):
            self.assertEqual(decode(zlib.compress(message)), (message, True))
        framed = zlib.compress(message)
        self.assertEqual(advanced_lsb._decode_zlib_with_length(len(framed).to_bytes(4, "big") + framed), (message, ""))

    def test_expansion_invalid_and_truncation_rejected(self):
        bomb = zlib.compress(b"b" * (MAX_DECOMPRESSED_BYTES + 1))
        invalid = [bomb, b"not-zlib", zlib.compress(b"hello")[:-1], b""]
        for blob in invalid:
            with self.subTest(length=len(blob)):
                with self.assertRaises(ValueError):
                    decompress_deflate(blob)
                self.assertEqual(simple_zlib._try_decompress(blob), (b"", False))
                result, error = advanced_lsb._decode_zlib_with_length(len(blob).to_bytes(4, "big") + blob)
                self.assertEqual(result, b"")
                self.assertTrue(error)
        with self.assertRaises(ValueError):
            decompress_deflate(gzip.compress(b"x" * 1025), wbits=31, max_output=1024)
        with self.assertRaises(ValueError):
            decompress_deflate(b"x" * (MAX_DECOMPRESSED_BYTES + 1))

    def test_analyzer_entrypoints_do_not_report_bomb_payloads(self):
        bomb = zlib.compress(b"z" * (MAX_DECOMPRESSED_BYTES + 1))
        framed = len(bomb).to_bytes(4, "big") + bomb
        with TemporaryDirectory() as folder:
            root = Path(folder)
            image = root / "input.png"
            Image.fromarray(np.zeros((8, 8, 4), dtype=np.uint8), "RGBA").save(image)
            simple_results = []
            with patch.object(simple_zlib, "_read_bytes", return_value=framed), patch.object(simple_zlib, "update_data", side_effect=lambda _, data: simple_results.append(data)):
                simple_zlib.analyze_simple_zlib(image, root)
            self.assertEqual(simple_results[-1]["simple_zlib"]["matches"], [])
            advanced_results = []
            with patch.object(advanced_lsb, "_bits_to_bytes", return_value=framed), patch.object(advanced_lsb, "update_data", side_effect=lambda _, data: advanced_results.append(data)):
                advanced_lsb.analyze_advanced_lsb(image, root)
            report = advanced_results[-1]["advanced_lsb"]
            self.assertEqual(report["details"]["file_payloads"], [])
            self.assertTrue(any("limit" in error for error in report["details"]["errors"]))


if __name__ == "__main__":
    unittest.main()

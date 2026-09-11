"""Read-only decompression/timeout regression; never runs external tooling."""
import bz2
import gzip
import lzma
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zlib

from engine.analyzers import payload_unwrap as unwrap


class WrapperBounds(unittest.TestCase):
    def test_four_complete_streams_preserve_exact_bytes(self):
        plain = '𝔩̸ 👾\n'.encode('utf-8')
        for name, encode in [('zlib', zlib.compress), ('gzip', gzip.compress),
                             ('bz2', bz2.compress), ('lzma', lzma.compress)]:
            with self.subTest(name=name):
                self.assertEqual(unwrap._bounded_decompress(encode(plain), name), plain)

    def test_all_wrappers_reject_overlimit_truncation_and_trailing(self):
        for name, encode in [('zlib', zlib.compress), ('gzip', gzip.compress),
                             ('bz2', bz2.compress), ('lzma', lzma.compress)]:
            with self.subTest(name=name):
                with self.assertRaises((ValueError, OSError, EOFError, lzma.LZMAError, zlib.error)):
                    unwrap._bounded_decompress(encode(b'a' * (unwrap.MAX_DECOMPRESSED_BYTES + 1)), name)
                for invalid in [encode(b'valid')[:-2], encode(b'valid') + b'trailing']:
                    with self.assertRaises((ValueError, OSError, EOFError, lzma.LZMAError, zlib.error)):
                        unwrap._bounded_decompress(invalid, name)

    def test_archive_command_has_timeout_without_running_it(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(unwrap, 'which', return_value='/mock/7z'), \
                patch.object(unwrap.subprocess, 'run') as run:
            unwrap._export_payload_artifacts(Path(folder), [b'recovered'])
            self.assertEqual(run.call_args.kwargs['timeout'], 30)


if __name__ == '__main__':
    unittest.main()

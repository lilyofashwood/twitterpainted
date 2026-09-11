import tempfile
import unittest
from pathlib import Path
import zlib

from engine.option_decoders import _try_zlib, analyze_png_chunks


def chunk(kind, data):
    return len(data).to_bytes(4, 'big') + kind + data + (zlib.crc32(kind + data) & 0xffffffff).to_bytes(4, 'big')


class OptionBounds(unittest.TestCase):
    def test_zlib_boundary_preserves_valid_data_and_rejects_bomb(self):
        self.assertEqual(_try_zlib(zlib.compress(b'exact\x00\n')), b'exact\x00\n')
        self.assertIsNone(_try_zlib(zlib.compress(b'a' * (2 * 1024 * 1024 + 1))))
        self.assertIsNone(_try_zlib(zlib.compress(b'exact')[:-1]))

    def test_png_compressed_text_does_not_expand_past_limit(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / 'metadata.png'
            source.write_bytes(b'\x89PNG\r\n\x1a\n' + chunk(b'zTXt', b'key\x00\x00' + zlib.compress(b'a' * (2 * 1024 * 1024 + 1))) + chunk(b'IEND', b''))
            result = analyze_png_chunks(source, option_id='png_chunks', label='PNG')
            self.assertEqual(result['details']['text'], [])
            source.write_bytes(b'\x89PNG\r\n\x1a\n' + chunk(b'zTXt', b'key\x00\x00' + zlib.compress(b'exact metadata')) + chunk(b'IEND', b''))
            result = analyze_png_chunks(source, option_id='png_chunks', label='PNG')
            self.assertEqual(result['details']['text'], [{'keyword':'key','text':'exact metadata'}])


if __name__ == '__main__':
    unittest.main()

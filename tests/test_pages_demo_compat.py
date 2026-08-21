import json
import re
import unittest
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
from PIL import Image

from engine.analyzers.simple_lsb import _decode_plane
from engine.encoder import encode_multi_channel, encode_text_into_plane


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = json.loads((ROOT / "tests/fixtures/pages_bitstream.json").read_text())


def fixture_image(case):
    pixels = np.array(case["base_rgba"], dtype=np.uint8)
    pixels = pixels.reshape(case["height"], case["width"], 4)
    return Image.fromarray(pixels)


class PagesBitstreamCompatibilityTests(unittest.TestCase):
    def test_combined_rgb_text_fixture_matches_backend_pixel_order(self):
        case = FIXTURE["combined_text"]
        with TemporaryDirectory() as tmp:
            output = Path(tmp) / "combined.png"
            encode_text_into_plane(fixture_image(case), case["text"], output, case["plane"])
            encoded = np.array(Image.open(output).convert("RGBA"), dtype=np.uint8).reshape(-1)
        self.assertEqual(encoded.tolist(), case["encoded_rgba"])
        self.assertEqual((case["text"].encode("utf-8") + b"\x00").hex(), case["payload_hex"])
        image = Image.fromarray(encoded.reshape(case["height"], case["width"], 4))
        self.assertEqual(_decode_plane(image, case["plane"]), case["text"])

    def test_individual_rgb_text_fixture_matches_backend_channel_order(self):
        case = FIXTURE["individual_text"]
        cover = BytesIO()
        fixture_image(case).save(cover, format="PNG")
        channel_payloads = {
            channel: {"enabled": True, "type": "text", "text": text}
            for channel, text in case["payloads"].items()
        }
        _, encoded_bytes = encode_multi_channel(
            cover.getvalue(),
            channel_payloads,
            twitter_safe_preprocess=False,
        )
        encoded = np.array(Image.open(BytesIO(encoded_bytes)).convert("RGBA"), dtype=np.uint8).reshape(-1)
        self.assertEqual(encoded.tolist(), case["encoded_rgba"])
        image = Image.fromarray(encoded.reshape(case["height"], case["width"], 4))
        for channel, text in case["payloads"].items():
            self.assertEqual(_decode_plane(image, channel), text)

    def test_fixture_contains_only_the_two_text_modes(self):
        self.assertEqual(set(FIXTURE), {"combined_text", "individual_text"})
        self.assertEqual(set(FIXTURE["individual_text"]["payloads"]), {"R", "B"})

    def test_pages_contract_is_text_only_rgb_and_local(self):
        html = (ROOT / "docs/index.html").read_text()
        script = (ROOT / "docs/twitterpainted.js").read_text()
        core = (ROOT / "docs/steg-core.js").read_text()
        surface = html + script + core

        self.assertEqual(html.count('accept="image/*"'), 2)
        self.assertEqual(html.count('type="file"'), 2)
        self.assertIn("connect-src 'none'", html)
        self.assertIn('name="paint-style" value="combined" checked', html)
        self.assertIn('name="paint-style" value="individual"', html)
        self.assertEqual(html.count('class="channel-card"'), 3)
        self.assertIn("Object.freeze(['RGB', 'R', 'G', 'B'])", core)
        self.assertIn("Object.freeze(['R', 'G', 'B'])", core)
        self.assertIn("Object.freeze(['A'])", core)

        for removed in (
            "simple-file",
            "channel-file",
            "payload-type",
            "zlib",
            "deflatestream",
            "compressionstream",
            "pdf payload",
        ):
            self.assertNotIn(removed, surface.lower())
        self.assertNotIn("alpha channel", surface.lower())
        self.assertNotIn('data-channel="A"', html)
        self.assertNotIn('value="RGBA"', html)

    def test_pages_export_only_a_verified_png(self):
        html = (ROOT / "docs/index.html").read_text()
        script = (ROOT / "docs/twitterpainted.js").read_text()

        self.assertIn('src="./twitterpainted.js?v=20260821-legacy-alpha-receipt"', html)
        self.assertIn("output · png", html)
        self.assertIn("opaque rgb png · every bit intact", html)
        self.assertIn("always returns png", html)
        self.assertNotIn('name="output-format"', html)
        self.assertIn("image/png", script)
        self.assertNotIn("image/jpeg", script)
        self.assertNotIn("JPEG_QUALITY", script)
        self.assertNotIn("jpeg q95", html + script)
        self.assertIn("canvasPngBlob", script)
        self.assertIn("blob.type !== 'image/png'", script)
        self.assertIn("stripAncillaryPngChunks", script)
        self.assertIn("if (/^[A-Z]/.test(type))", script)
        self.assertIn("verifyEncodedBlob", script)
        self.assertIn("blobPixels(blob)", script)
        self.assertIn("equalBytes(recovered, expected)", script)
        self.assertIn("equalBytes(recovered, hidden.payload)", script)
        self.assertIn("no download was created", script)
        self.assertIn("twitterpaint-${style}-${verification.receipt}.png", script)
        self.assertIn("download.download", script)
        self.assertIn("rasterReceipt", script)
        self.assertIn("paint mark", script)
        self.assertIn("matches last export", script)

    def test_pages_read_legacy_alpha_without_offering_alpha_encoding(self):
        html = (ROOT / "docs/index.html").read_text()
        script = (ROOT / "docs/twitterpainted.js").read_text()
        core = (ROOT / "docs/steg-core.js").read_text()

        pixels = np.full((20, 20, 4), 254, dtype=np.uint8)
        pixels[..., :3] = 96
        with TemporaryDirectory() as tmp:
            output = Path(tmp) / "legacy-alpha.png"
            encode_text_into_plane(
                Image.fromarray(pixels),
                "legacy alpha receipt",
                output,
                "A",
            )
            image = Image.open(output).convert("RGBA")
        self.assertEqual(_decode_plane(image, "A"), "legacy alpha receipt")

        self.assertIn("LEGACY_DECODE_PLANES", script)
        self.assertIn("[...TWITTERPAINT_PLANES, ...LEGACY_DECODE_PLANES]", script)
        self.assertIn("legacy alpha · decoder only", script)
        self.assertIn("legacy alpha read-only", html.lower())
        self.assertNotIn('data-channel="A"', html)
        self.assertNotIn('value="RGBA"', html)

    def test_pages_lock_and_verify_the_twitter_survival_profile(self):
        html = (ROOT / "docs/index.html").read_text()
        script = (ROOT / "docs/twitterpainted.js").read_text()

        self.assertIn("const TARGET_PNG_BYTES = 900 * 1024", script)
        self.assertIn("const TWITTER_MAX_EDGE = 680", script)
        self.assertIn("const TWITTER_MIN_UNIQUE_RGB = 257", script)
        self.assertNotIn('id="feed-prep"', html)
        self.assertNotIn("prepareForFeed", script)
        self.assertIn("Math.min(1, TWITTER_MAX_EDGE / width, TWITTER_MAX_EDGE / height)", script)
        self.assertIn("const imageData = drawOpaqueSource(source, width, height)", script)
        self.assertIn("alpha: false", script)
        self.assertIn("encodeCanvas.toBlob", script)
        self.assertIn("[2, 6].includes(header.colorType)", script)
        self.assertIn("pixelsAreOpaque(decoded.pixels)", script)
        self.assertIn("countUniqueRgb(decoded.pixels)", script)
        self.assertIn("uniqueRgbColors < TWITTER_MIN_UNIQUE_RGB", script)
        self.assertIn("blob.size > TARGET_PNG_BYTES", script)
        self.assertIn("Math.max(decoded.width, decoded.height) > TWITTER_MAX_EDGE", script)
        self.assertIn("if (!verification.passed)", script)
        self.assertIn("source metadata stripped", html.lower())
        self.assertIn("exports that resolve to 256 colors or fewer are refused", html.lower())

    def test_pages_accept_opaque_rgb_and_rgba_storage_but_reject_transparency(self):
        script = (ROOT / "docs/twitterpainted.js").read_text()
        pixels = np.zeros((20, 20, 4), dtype=np.uint8)
        for index in range(400):
            y, x = divmod(index, 20)
            pixels[y, x] = (index >> 8, index & 0xFF, (index * 17) & 0xFF, 255)

        with TemporaryDirectory() as tmp:
            rgba_path = Path(tmp) / "opaque-rgba.png"
            rgb_path = Path(tmp) / "opaque-rgb.png"
            translucent_path = Path(tmp) / "translucent-rgba.png"
            message = "same rgb lsb payload"
            encode_text_into_plane(Image.fromarray(pixels), message, rgba_path, "RGB")

            opaque_rgba = Image.open(rgba_path).convert("RGBA")
            opaque_rgba.convert("RGB").save(rgb_path, format="PNG")
            translucent = opaque_rgba.copy()
            translucent.putalpha(17)
            translucent.save(translucent_path, format="PNG")

            images = [Image.open(path).convert("RGBA") for path in (rgba_path, rgb_path, translucent_path)]
            raw = [path.read_bytes() for path in (rgba_path, rgb_path, translucent_path)]

        def accepted_profile(data, image):
            alpha = np.asarray(image, dtype=np.uint8)[..., 3]
            return data[24] == 8 and data[25] in {2, 6} and bool(np.all(alpha == 255))

        self.assertEqual([data[25] for data in raw], [6, 2, 6])
        for image in images:
            self.assertEqual(_decode_plane(image, "RGB"), message)
        np.testing.assert_array_equal(np.asarray(images[0])[..., :3], np.asarray(images[1])[..., :3])
        np.testing.assert_array_equal(np.asarray(images[0])[..., :3], np.asarray(images[2])[..., :3])
        self.assertEqual([accepted_profile(data, image) for data, image in zip(raw, images)], [True, True, False])

        self.assertIn("[2, 6].includes(header.colorType)", script)
        self.assertIn("!pixelsAreOpaque(decoded.pixels)", script)
        self.assertNotIn("header.colorType !== 2", script)

    def test_copy_names_decoder_and_states_twitter_survival(self):
        html = (ROOT / "docs/index.html").read_text()
        lowered = html.lower()

        self.assertIn(">decoder</button>", lowered)
        self.assertNotIn(">analyzer</button>", lowered)
        self.assertNotIn("be the black heart itself", lowered)
        self.assertNotIn("black-heart cut", lowered)
        self.assertIn("twitterpaint survives the x / twitter algorithm, unlike my heart did", lowered)
        self.assertIn("combined rgb · one secret", lowered)
        self.assertIn("individual r / g / b · separate secrets", lowered)
        self.assertIn("opaque rgb png · every bit intact", lowered)
        self.assertIn("680 px max · below 900 kib · 257+ rgb colors · verified before download", lowered)
        self.assertIn("download twitter's copy · decode it again", lowered)
        self.assertIn("the spell holds", lowered)
        self.assertIn("stolen proudly from pliny's agpl grimoire", lowered)
        self.assertIn("all is fair in love and war", lowered)
        self.assertIn("the code kept its promise longer", lowered)
        self.assertIn('class="survival-runes"', lowered)
        self.assertNotIn("experiment", lowered)
        self.assertNotIn("test at your own risk", lowered)
        self.assertIn("https://twitterpainted.onrender.com", html)
        self.assertIn("https://github.com/lilyofashwood/twitterpainted", html)

    def test_pages_use_the_exact_glyph_map_and_plain_aria(self):
        html = (ROOT / "docs/index.html").read_text()
        script = (ROOT / "docs/twitterpainted.js").read_text()
        self.assertIn("𓂀 follow the 🗝️ melody 🗝️. find the lyric. 🔓 🖤 𓋹", html)
        expected_map = {
            "a": "𝐚", "b": "𝖻", "c": "𝖼", "d": "𝖽", "e": "𝐞", "f": "𝖿",
            "g": "𝗀", "h": "𝗁", "i": "𝐢", "j": "𝗃", "k": "𝗄", "l": "𝗅",
            "m": "𝗆", "n": "𝗇", "o": "𝐨", "p": "𝗉", "q": "𝗊", "r": "𝗋",
            "s": "𝗌", "t": "𝗍", "u": "𝐮", "v": "𝗏", "w": "𝗐", "x": "𝗑",
            "y": "𝗒", "z": "𝗓",
        }
        for ascii_letter, glyph in expected_map.items():
            self.assertRegex(script, rf"\b{ascii_letter}:\s*'{re.escape(glyph)}'")
        self.assertNotIn("'[placeholder], [title], [aria-label]'", script)
        aria_labels = re.findall(r'aria-label="([^"]+)"', html)
        self.assertTrue(aria_labels)
        for label in aria_labels:
            self.assertTrue(label.isascii(), label)


if __name__ == "__main__":
    unittest.main()

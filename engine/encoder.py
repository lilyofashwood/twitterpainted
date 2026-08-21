"""Encoding helpers for hiding data in images.

Portions are derived from elder-plinius/ST3GG at commit 487f6e931674
(AGPL-3.0) and were modified for Twitterpainted by lilyofashwood in 2025–2026.
See NOTICE.md and LICENSE.
"""

from __future__ import annotations

import base64
import io
import math
import os
import random
import zlib
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Dict, List, Optional, Tuple

import numpy as np
from PIL import Image, ImageOps

TWITTER_MAX_BYTES = 900 * 1024
# Conservative compatibility envelope for the smallest full-size X/Twitter
# delivery lane documented by the primary tweetable-PNG research. Raw pixel
# LSBs cannot survive a resized preview.
TWITTER_MAX_EDGE = 680
TWITTER_MIN_UNIQUE_COLORS = 257
GENTLE_MAX_EDGE = 1600
COMPACT_MAX_EDGE = 512
CARRIER_PREP_MODES = {"twitterpaint", "none", "legacy", "gentle", "compact"}
OUTPUT_FORMATS = {
    "png": {"ext": ".png", "mime": "image/png"},
    "jpeg": {"ext": ".jpeg", "mime": "image/jpeg"},
}


def normalize_output_format(output_format: Optional[str]) -> str:
    if not output_format:
        return "png"
    fmt = output_format.strip().lower()
    if fmt.startswith("."):
        fmt = fmt[1:]
    if fmt == "jpg":
        fmt = "jpeg"
    if fmt not in OUTPUT_FORMATS:
        raise ValueError(f"Unsupported output format '{output_format}'. Use png or jpeg.")
    return fmt


def output_format_extension(output_format: Optional[str]) -> str:
    fmt = normalize_output_format(output_format)
    return OUTPUT_FORMATS[fmt]["ext"]


def output_format_mime(output_format: Optional[str]) -> str:
    fmt = normalize_output_format(output_format)
    return OUTPUT_FORMATS[fmt]["mime"]


def _save_png(img: Image.Image, output_path: Path) -> None:
    img.save(output_path, format="PNG", optimize=True)


def _flatten_opaque_rgb(img: Image.Image) -> Image.Image:
    """Return fresh, metadata-free RGB pixels with transparency on black."""
    rgba = ImageOps.exif_transpose(img).convert("RGBA")
    background = Image.new("RGBA", rgba.size, (0, 0, 0, 255))
    background.alpha_composite(rgba)
    rgb = background.convert("RGB")
    # Rebuild from bytes so source EXIF/ICC/text chunks cannot hitch a ride.
    return Image.frombytes("RGB", rgb.size, rgb.tobytes())


def normalize_carrier_prep(carrier_prep: Optional[str], *, default: str = "none") -> str:
    """Validate a full-lab carrier preparation profile."""
    prep = (carrier_prep or default).strip().lower()
    if prep not in CARRIER_PREP_MODES:
        choices = ", ".join(sorted(CARRIER_PREP_MODES))
        raise ValueError(f"Unknown carrier preparation '{carrier_prep}'. Choose one of: {choices}.")
    return prep


def _fresh_lossless_image(img: Image.Image, *, opaque: bool = False) -> Image.Image:
    """Apply EXIF orientation and rebuild pixels without source metadata."""
    oriented = ImageOps.exif_transpose(img)
    if opaque:
        return _flatten_opaque_rgb(oriented)
    if "A" in oriented.getbands() or "transparency" in oriented.info:
        rgba = oriented.convert("RGBA")
        return Image.frombytes("RGBA", rgba.size, rgba.tobytes())
    rgb = oriented.convert("RGB")
    return Image.frombytes("RGB", rgb.size, rgb.tobytes())


def _png_bytes(img: Image.Image) -> bytes:
    buffer = io.BytesIO()
    img.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


def prepare_carrier_bytes(image_bytes: bytes, carrier_prep: str) -> bytes:
    """Prepare an image carrier using one of the full-lab named profiles.

    ``none`` returns the original bytes so geometry, alpha, and format reach the
    selected encoder untouched. Every other profile produces a metadata-free,
    lossless PNG before payload embedding.
    """
    prep = normalize_carrier_prep(carrier_prep)
    if not image_bytes:
        raise ValueError("Cannot prepare an empty image carrier.")
    if prep == "none":
        return image_bytes

    try:
        with Image.open(io.BytesIO(image_bytes)) as source:
            source.load()
            image = _fresh_lossless_image(
                source,
                opaque=prep in {"twitterpaint", "compact"},
            )
    except Exception as exc:
        raise ValueError(f"Failed to open carrier for preparation: {str(exc)}") from exc

    if prep == "twitterpaint":
        image = _fit_within_edge(image, TWITTER_MAX_EDGE)
    elif prep == "gentle":
        image = _fit_within_edge(image, GENTLE_MAX_EDGE)
    elif prep == "compact":
        image = _fit_within_edge(image, COMPACT_MAX_EDGE)

    encoded = _png_bytes(image)
    if prep not in {"twitterpaint", "legacy"}:
        return encoded

    # Twitterpaint fits proportionally; the legacy profile deliberately keeps
    # the historical halve-and-try-again behavior.
    for _iteration in range(20):
        if len(encoded) <= TWITTER_MAX_BYTES:
            return encoded
        width, height = image.size
        if prep == "legacy":
            new_size = (max(1, width // 2), max(1, height // 2))
        else:
            ratio = min(0.94, math.sqrt(TWITTER_MAX_BYTES / len(encoded)) * 0.96)
            new_size = (
                max(1, int(math.floor(width * ratio))),
                max(1, int(math.floor(height * ratio))),
            )
        if new_size[0] >= width and width > 1:
            new_size = (width - 1, new_size[1])
        if new_size[1] >= height and height > 1:
            new_size = (new_size[0], height - 1)
        if new_size[0] < 2 or new_size[1] < 2:
            break
        image = image.resize(new_size, resample=Image.LANCZOS)
        if prep == "twitterpaint":
            image = _flatten_opaque_rgb(image)
        encoded = _png_bytes(image)

    raise ValueError(
        f"Unable to prepare the carrier below {TWITTER_MAX_BYTES // 1024} KiB after 20 resizes."
    )


def _fit_within_edge(img: Image.Image, max_edge: int) -> Image.Image:
    """Fit an image inside a square without changing its aspect ratio."""
    width, height = img.size
    if max(width, height) <= max_edge:
        return img
    ratio = max_edge / max(width, height)
    size = (
        max(1, int(math.floor(width * ratio))),
        max(1, int(math.floor(height * ratio))),
    )
    return img.resize(size, resample=Image.LANCZOS)


def _has_twitter_truecolor_guard(img: Image.Image) -> bool:
    """Return True when a carrier has at least 257 distinct RGB colours."""
    colors = img.convert("RGB").getcolors(maxcolors=TWITTER_MIN_UNIQUE_COLORS)
    return colors is None or len(colors) >= TWITTER_MIN_UNIQUE_COLORS


def twitter_png_profile(image_bytes: bytes) -> Dict[str, object]:
    """Inspect the invariants used by Twitterpaint's conservative PNG lane."""
    try:
        with Image.open(io.BytesIO(image_bytes)) as image:
            image.load()
            width, height = image.size
            image_format = image.format
            opaque_rgb = image.mode == "RGB"
            enough_colors = _has_twitter_truecolor_guard(image)
    except Exception:
        return {
            "ready": False,
            "png": False,
            "opaque_rgb": False,
            "dimensions_ok": False,
            "bytes_ok": False,
            "colors_ok": False,
        }

    result: Dict[str, object] = {
        "png": image_format == "PNG",
        "opaque_rgb": opaque_rgb,
        "dimensions_ok": max(width, height) <= TWITTER_MAX_EDGE,
        "bytes_ok": len(image_bytes) <= TWITTER_MAX_BYTES,
        "colors_ok": enough_colors,
        "width": width,
        "height": height,
        "bytes": len(image_bytes),
    }
    result["ready"] = all(
        bool(result[key])
        for key in ("png", "opaque_rgb", "dimensions_ok", "bytes_ok", "colors_ok")
    )
    return result


def convert_to_png(image_path: Path) -> Path:
    """Convert the image to PNG format if needed."""
    try:
        img = Image.open(image_path)
        # Verify the image by loading it
        img.verify()
        # Reopen after verify since verify closes the file
        img = Image.open(image_path)
    except FileNotFoundError:
        raise FileNotFoundError(f"Image file not found: {image_path}")
    except Exception as e:
        raise ValueError(f"Failed to open image file '{image_path}': {str(e)}")

    try:
        if img.format != "PNG":
            new_image_path = image_path.with_suffix(".png")
            img.save(new_image_path, "PNG")
            return new_image_path
        return image_path
    except Exception as e:
        raise IOError(f"Failed to convert image to PNG format: {str(e)}")


def compress_image_before_encoding(
    image_path: Path,
    output_image_path: Path,
    *,
    twitter_profile: bool = False,
) -> None:
    """
    Preserve the inherited pre-encode workflow that fits a PNG below 900 KiB.
    """
    try:
        png_path = convert_to_png(image_path)
    except Exception as e:
        raise ValueError(f"Failed to convert image to PNG during compression: {str(e)}")

    try:
        img = ImageOps.exif_transpose(Image.open(png_path))
        if twitter_profile:
            img = _fit_within_edge(_flatten_opaque_rgb(img), TWITTER_MAX_EDGE)
        _save_png(img, output_image_path)
    except Exception as e:
        raise IOError(f"Failed to save initial compressed image: {str(e)}")

    # Compress until the carrier meets the inherited 900 KiB boundary.
    # Safety limit to prevent infinite loop if image can't be compressed enough
    max_iterations = 20
    iteration = 0

    while os.path.getsize(output_image_path) > TWITTER_MAX_BYTES:
        if iteration >= max_iterations:
            raise ValueError(
                f"Unable to compress image below 900KB after {max_iterations} iterations. "
                f"Current size: {os.path.getsize(output_image_path)} bytes"
            )

        try:
            img = Image.open(output_image_path)
            new_width = max(1, img.width // 2)
            new_height = max(1, img.height // 2)

            if new_width < 2 or new_height < 2:
                raise ValueError(
                    f"Image too small to compress further (size: {new_width}x{new_height}). "
                    f"Current file size: {os.path.getsize(output_image_path)} bytes exceeds 900KB limit."
                )

            img = img.resize((new_width, new_height), resample=Image.LANCZOS)
            if twitter_profile:
                img = _flatten_opaque_rgb(img)
            _save_png(img, output_image_path)
            iteration += 1
        except ValueError:
            raise
        except Exception as e:
            raise IOError(f"Failed to resize/save image during compression iteration {iteration}: {str(e)}")


def encode_text_into_plane(
    image: Image.Image,
    text: str,
    output_path: Path,
    plane: str = "RGB",
    *,
    opaque_rgb: bool = False,
) -> None:
    """Embed text into selected color plane(s)."""
    if not isinstance(text, str):
        raise TypeError(f"Text must be a string, got {type(text).__name__}")

    if not text:
        raise ValueError("Cannot encode empty text")

    try:
        if opaque_rgb:
            if "A" in plane:
                raise ValueError("opaque RGB output cannot carry an alpha-plane payload")
            img = _flatten_opaque_rgb(image)
        else:
            img = image.convert("RGBA")
    except Exception as e:
        raise ValueError(f"Failed to convert image to RGBA format: {str(e)}")

    width, height = img.size
    if width <= 0 or height <= 0:
        raise ValueError(f"Invalid image dimensions: {width}x{height}")

    try:
        payload = text.encode("utf-8") + b"\x00"
        binary_text = "".join(format(byte, "08b") for byte in payload)
    except Exception as e:
        raise ValueError(f"Failed to encode text to binary: {str(e)}")

    channels = [ch for ch in plane if ch in "RGBA"]
    if not channels:
        raise ValueError("plane must include at least one of R,G,B,A")

    max_bits = width * height * len(channels)
    if len(binary_text) > max_bits:
        raise ValueError(
            f"The message is too long for this image. "
            f"Message requires {len(binary_text)} bits but image only has capacity for {max_bits} bits. "
            f"Try using a larger image or fewer color channels."
        )

    try:
        index = 0
        for y in range(height):
            for x in range(width):
                if index >= len(binary_text):
                    break
                pixel = img.getpixel((x, y))
                if opaque_rgb:
                    r, g, b = pixel
                    a = 255
                else:
                    r, g, b, a = pixel

                for ch in channels:
                    bit = int(binary_text[index])
                    index += 1
                    if ch == "R":
                        r = (r & 0xFE) | bit
                    elif ch == "G":
                        g = (g & 0xFE) | bit
                    elif ch == "B":
                        b = (b & 0xFE) | bit
                    elif ch == "A":
                        a = (a & 0xFE) | bit
                    if index >= len(binary_text):
                        break

                img.putpixel((x, y), (r, g, b) if opaque_rgb else (r, g, b, a))
            if index >= len(binary_text):
                break

        _save_png(img, output_path)
    except Exception as e:
        raise IOError(f"Failed to encode text into image: {str(e)}")


def encode_zlib_into_image(
    image: Image.Image,
    file_data: bytes,
    output_path: Path,
    plane: str = "RGB",
    *,
    opaque_rgb: bool = False,
) -> None:
    """Embed zlib-compressed data into selected color plane(s)."""
    if not isinstance(file_data, bytes):
        raise TypeError(f"File data must be bytes, got {type(file_data).__name__}")

    if not file_data:
        raise ValueError("Cannot encode empty file data")

    try:
        compressed_data = zlib.compress(file_data)
    except Exception as e:
        raise ValueError(f"Failed to compress file data with zlib: {str(e)}")

    try:
        binary_data = _bits_from_zlib(compressed_data)
    except Exception as e:
        raise ValueError(f"Failed to convert compressed data to binary: {str(e)}")

    width, height = image.size
    if width <= 0 or height <= 0:
        raise ValueError(f"Invalid image dimensions: {width}x{height}")

    channels = [ch for ch in plane if ch in "RGBA"]
    if not channels:
        raise ValueError("plane must include at least one of R,G,B,A")
    if opaque_rgb and "A" in channels:
        raise ValueError("opaque RGB output cannot carry an alpha-plane payload")

    max_bits = width * height * len(channels)
    if len(binary_data) > max_bits:
        raise ValueError(
            f"The compressed data is too long for this image. "
            f"Compressed data requires {len(binary_data)} bits but image only has capacity for {max_bits} bits. "
            f"Original size: {len(file_data)} bytes, compressed size: {len(compressed_data)} bytes. "
            f"Try using a larger image or fewer color channels."
        )

    try:
        img = _flatten_opaque_rgb(image) if opaque_rgb else image.convert("RGBA")
    except Exception as e:
        raise ValueError(f"Failed to convert image to RGBA format: {str(e)}")

    try:
        index = 0
        for y in range(height):
            for x in range(width):
                if index >= len(binary_data):
                    break
                pixel = img.getpixel((x, y))
                if opaque_rgb:
                    r, g, b = pixel
                    a = 255
                else:
                    r, g, b, a = pixel

                for ch in channels:
                    bit = int(binary_data[index])
                    index += 1
                    if ch == "R":
                        r = (r & 0xFE) | bit
                    elif ch == "G":
                        g = (g & 0xFE) | bit
                    elif ch == "B":
                        b = (b & 0xFE) | bit
                    elif ch == "A":
                        a = (a & 0xFE) | bit
                    if index >= len(binary_data):
                        break

                img.putpixel((x, y), (r, g, b) if opaque_rgb else (r, g, b, a))
            if index >= len(binary_data):
                break

        _save_png(img, output_path)
    except Exception as e:
        raise IOError(f"Failed to encode compressed data into image: {str(e)}")


def encode_payload(
    image_bytes: bytes,
    *,
    filename: str = "input.png",
    mode: str = "text",
    plane: str = "RGB",
    text: Optional[str] = None,
    file_data: Optional[bytes] = None,
    output_format: str = "png",
    lossy_output: bool = True,
    twitter_safe_preprocess: bool = False,
    carrier_prep: Optional[str] = None,
) -> Tuple[str, bytes]:
    """
    Encode either text or binary data into an image and return the encoded image bytes.
    Returns tuple of (filename, bytes).
    """
    if not isinstance(image_bytes, bytes):
        raise TypeError(f"image_bytes must be bytes, got {type(image_bytes).__name__}")

    if not image_bytes:
        raise ValueError("Cannot encode into empty image data")

    if mode not in {"text", "zlib"}:
        raise ValueError(f"mode must be 'text' or 'zlib', got '{mode}'")

    output_format = normalize_output_format(output_format)
    if output_format == "jpeg" and not lossy_output:
        raise ValueError("JPEG output is lossy; explicitly enable lossy_output to experiment with it.")

    prep = normalize_carrier_prep(
        carrier_prep,
        default="twitterpaint" if twitter_safe_preprocess else "legacy",
    )
    opaque_output = prep in {"twitterpaint", "compact"}
    enforce_size_cap = prep in {"twitterpaint", "legacy"}

    with TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        input_path = tmp_dir / filename

        try:
            with open(input_path, "wb") as f:
                f.write(image_bytes)
        except Exception as e:
            raise IOError(f"Failed to write input image to temporary file: {str(e)}")

        output_path = tmp_dir / "encoded.png"

        try:
            output_path.write_bytes(prepare_carrier_bytes(image_bytes, prep))
        except Exception as e:
            raise ValueError(f"Failed to prepare image before encoding: {str(e)}")

        try:
            img = Image.open(output_path)
        except Exception as e:
            raise ValueError(f"Failed to open compressed image: {str(e)}")

        def embed_payload(source: Image.Image) -> None:
            if mode == "text":
                if not text:
                    raise ValueError("Text payload required for text mode.")
                encode_text_into_plane(
                    source,
                    text,
                    output_path,
                    plane,
                    opaque_rgb=opaque_output,
                )
            else:
                if file_data is None:
                    raise ValueError("file_data required for zlib mode.")
                encode_zlib_into_image(
                    source,
                    file_data,
                    output_path,
                    plane,
                    opaque_rgb=opaque_output,
                )

        try:
            embed_payload(img)
        except Exception as e:
            raise ValueError(f"Failed to encode {mode} payload: {str(e)}")

        # Embedding can make a highly compressible carrier much larger. Recheck
        # the actual encoded artifact and re-embed after each downscale so the
        # returned PNG—not merely the cover image—honors the compatibility cap.
        for iteration in range(20):
            if not enforce_size_cap or output_path.stat().st_size <= TWITTER_MAX_BYTES:
                break
            try:
                encoded_source = Image.open(output_path)
                encoded = (
                    _flatten_opaque_rgb(encoded_source)
                    if opaque_output
                    else encoded_source.convert("RGBA")
                )
                width, height = encoded.size
                factor = 0.5 if prep == "legacy" else 0.9
                new_size = (max(1, int(width * factor)), max(1, int(height * factor)))
                if new_size[0] >= width and width > 1:
                    new_size = (width - 1, new_size[1])
                if new_size[1] >= height and height > 1:
                    new_size = (new_size[0], height - 1)
                if new_size[0] < 2 or new_size[1] < 2:
                    raise ValueError("Image became too small to keep the encoded PNG under 900 KB.")
                resized = encoded.resize(new_size, resample=Image.LANCZOS)
                embed_payload(resized)
            except ValueError:
                raise
            except Exception as e:
                raise IOError(f"Failed to resize and re-embed payload: {str(e)}")
        else:
            raise ValueError("Unable to keep the encoded PNG under 900 KB after 20 iterations.")

        output_name = f"encoded{output_format_extension(output_format)}"
        if output_format == "png":
            try:
                encoded_bytes = output_path.read_bytes()
                if prep == "twitterpaint":
                    profile = twitter_png_profile(encoded_bytes)
                    if not profile["colors_ok"]:
                        raise ValueError(
                            "Twitterpaint needs a photographic carrier with at least 257 distinct "
                            "RGB colors so X keeps the true-color PNG path."
                        )
                    if not profile["ready"]:
                        raise ValueError(
                            "Twitterpaint could not produce an opaque PNG within the 680px/900KiB "
                            "survivor profile."
                        )
                return output_name, encoded_bytes
            except ValueError:
                raise
            except Exception as e:
                raise IOError(f"Failed to read encoded image file: {str(e)}")

        converted_path = tmp_dir / output_name
        try:
            _convert_output_image(output_path, output_format, converted_path)
            return output_name, converted_path.read_bytes()
        except Exception as e:
            raise IOError(f"Failed to convert encoded image to {output_format}: {str(e)}")


def as_data_url(img_bytes: bytes, mime: str = "image/png") -> str:
    """Return a data URL for the provided image bytes."""
    if not isinstance(img_bytes, bytes):
        raise TypeError(f"img_bytes must be bytes, got {type(img_bytes).__name__}")

    if not img_bytes:
        raise ValueError("Cannot create data URL from empty image data")

    try:
        b64 = base64.b64encode(img_bytes).decode()
        return f"data:{mime};base64,{b64}"
    except Exception as e:
        raise ValueError(f"Failed to encode image as base64 data URL: {str(e)}")


def _bits_from_text(text: str) -> str:
    payload = text.encode("utf-8") + b"\x00"
    return "".join(format(b, "08b") for b in payload)


def _bits_from_zlib(data: bytes) -> str:
    length = len(data)
    prefix = length.to_bytes(4, "big")
    payload = prefix + data
    return "".join(format(b, "08b") for b in payload)


def _convert_output_image(source_path: Path, output_format: str, output_path: Path) -> None:
    fmt = normalize_output_format(output_format)
    if fmt == "png":
        output_path.write_bytes(source_path.read_bytes())
        return

    try:
        img = Image.open(source_path)
    except Exception as e:
        raise ValueError(f"Failed to open encoded image for conversion: {str(e)}")

    if img.mode not in {"RGB", "L"}:
        img = img.convert("RGB")

    try:
        img.save(
            output_path,
            format="JPEG",
            quality=95,
            # Keep the experiment deterministic and avoid libjpeg's optimized
            # writer failing on large, high-entropy carriers.
            optimize=False,
            subsampling=0,
        )
    except Exception as e:
        raise IOError(f"Failed to save JPEG output: {str(e)}")


def encode_multi_channel(
    image_bytes: bytes,
    channel_payloads: Dict[str, Dict[str, Optional[bytes | str]]],
    *,
    filename: str = "input.png",
    twitter_safe_preprocess: bool = True,
    output_format: str = "png",
    carrier_prep: Optional[str] = None,
) -> Tuple[str, bytes]:
    """
    Encode independent payloads per channel (R/G/B/A) into one image.
    channel_payloads example:
      {"R": {"enabled": True, "type": "text", "text": "hi"},
       "G": {"enabled": True, "type": "file", "file_data": b"..."},
       "B": {"enabled": False}, ...}
    """
    if not isinstance(image_bytes, bytes):
        raise TypeError(f"image_bytes must be bytes, got {type(image_bytes).__name__}")

    if not image_bytes:
        raise ValueError("Cannot encode into empty image data")

    if not isinstance(channel_payloads, dict):
        raise TypeError(f"channel_payloads must be a dict, got {type(channel_payloads).__name__}")

    output_format = normalize_output_format(output_format)
    prep = normalize_carrier_prep(
        carrier_prep,
        default="twitterpaint" if twitter_safe_preprocess else "none",
    )
    opaque_output = prep in {"twitterpaint", "compact"}
    enforce_size_cap = prep in {"twitterpaint", "legacy"}
    with TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        input_path = tmp_dir / filename

        try:
            with open(input_path, "wb") as f:
                f.write(image_bytes)
        except Exception as e:
            raise IOError(f"Failed to write input image to temporary file: {str(e)}")

        output_path = tmp_dir / "encoded.png"

        try:
            output_path.write_bytes(prepare_carrier_bytes(image_bytes, prep))
        except Exception as e:
            raise ValueError(f"Failed to preprocess image: {str(e)}")

        try:
            source_img = Image.open(output_path)
            base_img = (
                _flatten_opaque_rgb(source_img)
                if opaque_output
                else source_img.convert("RGBA")
            )
        except Exception as e:
            raise ValueError(f"Failed to open and convert image to RGBA: {str(e)}")

        bits_by_channel: Dict[str, str] = {}
        for ch in ["R", "G", "B", "A"]:
            cfg = channel_payloads.get(ch) or {}
            if not cfg.get("enabled"):
                continue
            if opaque_output and ch == "A":
                raise ValueError(f"The {prep} carrier preparation profile excludes the alpha channel.")

            payload_type = cfg.get("type")
            try:
                if payload_type == "text":
                    text = cfg.get("text") or ""
                    if not text:
                        raise ValueError(f"Text payload for channel {ch} cannot be empty")
                    bits_by_channel[ch] = _bits_from_text(text)
                elif payload_type == "file":
                    file_data = cfg.get("file_data")
                    if file_data is None:
                        raise ValueError(f"Missing file payload for channel {ch}")
                    try:
                        compressed = zlib.compress(file_data)
                    except Exception as e:
                        raise ValueError(f"Failed to compress file data for channel {ch}: {str(e)}")
                    bits_by_channel[ch] = _bits_from_zlib(compressed)
                else:
                    raise ValueError(f"Unknown payload type '{payload_type}' for channel {ch}")
            except Exception as e:
                raise ValueError(f"Failed to encode channel {ch}: {str(e)}")

        if not bits_by_channel:
            raise ValueError("Enable at least one channel with a non-empty payload.")

        def embed_channel(pixels, width: int, height: int, channel: str, bits: str) -> None:
            try:
                idx = 0
                if channel == "R":
                    channel_idx = 0
                elif channel == "G":
                    channel_idx = 1
                elif channel == "B":
                    channel_idx = 2
                else:
                    channel_idx = 3

                for y in range(height):
                    for x in range(width):
                        if idx >= len(bits):
                            return
                        pixel = pixels[x, y]
                        if len(pixel) == 3:
                            r, g, b = pixel
                            a = 255
                        else:
                            r, g, b, a = pixel
                        val = (r, g, b, a)
                        channel_val = val[channel_idx]
                        channel_val = (channel_val & 0xFE) | int(bits[idx])
                        idx += 1
                        if channel_idx == 0:
                            val = (channel_val, g, b, a)
                        elif channel_idx == 1:
                            val = (r, channel_val, b, a)
                        elif channel_idx == 2:
                            val = (r, g, channel_val, a)
                        else:
                            val = (r, g, b, channel_val)
                        pixels[x, y] = val[:3] if len(pixel) == 3 else val
            except Exception as e:
                raise IOError(f"Failed to embed data into {channel} channel: {str(e)}")

        max_iterations = 20
        iteration = 0

        while True:
            width, height = base_img.size
            if width <= 0 or height <= 0:
                raise ValueError(f"Invalid image dimensions: {width}x{height}")

            capacity = width * height  # bits per channel
            for ch, bits in bits_by_channel.items():
                if len(bits) > capacity:
                    raise ValueError(
                        f"Payload too large for {ch} channel. "
                        f"Requires {len(bits)} bits but channel capacity is {capacity} bits. "
                        f"Try using a larger image."
                    )

            working = base_img.copy()
            try:
                pixels = working.load()
            except Exception as e:
                raise ValueError(f"Failed to load image pixels: {str(e)}")

            for ch, bits in bits_by_channel.items():
                if bits:
                    embed_channel(pixels, width, height, ch, bits)

            try:
                _save_png(working, output_path)
            except Exception as e:
                raise IOError(f"Failed to save encoded image: {str(e)}")

            if not enforce_size_cap:
                break

            if output_path.stat().st_size <= TWITTER_MAX_BYTES:
                break

            iteration += 1
            if iteration >= max_iterations:
                raise ValueError(
                    f"Unable to keep encoded image below {TWITTER_MAX_BYTES // 1024}KB after "
                    f"{max_iterations} iterations. Try a smaller payload or larger image."
                )

            factor = 0.5 if prep == "legacy" else 0.9
            new_width = max(1, int(width * factor))
            new_height = max(1, int(height * factor))
            if new_width >= width and width > 1:
                new_width = width - 1
            if new_height >= height and height > 1:
                new_height = height - 1

            if new_width < 2 or new_height < 2:
                raise ValueError(
                    f"Image too small to compress further (size: {new_width}x{new_height}). "
                    f"Current file size: {output_path.stat().st_size} bytes exceeds limit."
                )

            base_img = base_img.resize((new_width, new_height), resample=Image.LANCZOS)

        output_name = f"encoded{output_format_extension(output_format)}"
        if output_format == "png":
            try:
                encoded_bytes = output_path.read_bytes()
                if prep == "twitterpaint":
                    profile = twitter_png_profile(encoded_bytes)
                    if not profile["colors_ok"]:
                        raise ValueError(
                            "Twitterpaint needs a photographic carrier with at least 257 distinct "
                            "RGB colors so X keeps the true-color PNG path."
                        )
                    if not profile["ready"]:
                        raise ValueError(
                            "Twitterpaint could not produce an opaque PNG within the 680px/900KiB "
                            "survivor profile."
                        )
                return output_name, encoded_bytes
            except ValueError:
                raise
            except Exception as e:
                raise IOError(f"Failed to read encoded image file: {str(e)}")

        converted_path = tmp_dir / output_name
        try:
            _convert_output_image(output_path, output_format, converted_path)
            return output_name, converted_path.read_bytes()
        except Exception as e:
            raise IOError(f"Failed to convert encoded image to {output_format}: {str(e)}")


def _bytes_to_bits(payload: bytes) -> List[int]:
    bits: List[int] = []
    for byte in payload:
        for shift in range(7, -1, -1):
            bits.append((byte >> shift) & 1)
    return bits


def _bits_with_length_prefix(payload: bytes) -> List[int]:
    if len(payload) > 0xFFFF:
        raise ValueError("Payload exceeds 65535 bytes for length-prefixed encoders.")
    length = len(payload)
    length_bits = [(length >> shift) & 1 for shift in range(15, -1, -1)]
    return length_bits + _bytes_to_bits(payload)


def _open_image(image_bytes: bytes) -> Image.Image:
    try:
        return Image.open(io.BytesIO(image_bytes))
    except Exception as e:
        raise ValueError(f"Failed to open image bytes: {str(e)}")


def _image_to_bytes(img: Image.Image, output_format: str, *, quality: int = 95) -> bytes:
    output_format = normalize_output_format(output_format)
    buf = io.BytesIO()
    if output_format == "png":
        img.save(buf, format="PNG", optimize=True)
    else:
        rgb = img.convert("RGB")
        # Pillow/libjpeg's optimize path can under-allocate its buffer and fail
        # on high-entropy carriers. Standard Huffman tables are deterministic
        # and do not change the embedded DCT signs.
        rgb.save(
            buf,
            format="JPEG",
            quality=quality,
            optimize=False,
            subsampling=0,
        )
    return buf.getvalue()


def encode_lsb_payload(
    image_bytes: bytes,
    payload: bytes,
    *,
    channels: str = "RGB",
    bits_per_channel: int = 1,
    output_format: str = "png",
    filename: str = "input.png",
) -> Tuple[str, bytes]:
    if not payload:
        raise ValueError("Payload is empty.")
    if bits_per_channel not in {1, 2, 4}:
        raise ValueError("Bits per channel must be 1, 2, or 4.")

    img = _open_image(image_bytes).convert("RGBA")
    arr = np.array(img)
    channel_map = {"R": 0, "G": 1, "B": 2, "A": 3}
    channels = channels.upper()
    channel_indices = [channel_map[ch] for ch in channels if ch in channel_map]
    if not channel_indices:
        raise ValueError("Channels must include at least one of R, G, B, or A.")

    output_format = normalize_output_format(output_format)
    if output_format != "png":
        raise ValueError("Pixel LSB encoding requires lossless PNG output.")

    bits = _bits_with_length_prefix(payload)
    capacity = arr.shape[0] * arr.shape[1] * len(channel_indices) * bits_per_channel
    if len(bits) > capacity:
        raise ValueError(
            f"Payload too large for LSB capacity ({len(bits)} bits > {capacity} bits)."
        )

    mask = (1 << bits_per_channel) - 1
    clear_mask = 0xFF ^ mask
    flat = arr.reshape(-1, arr.shape[2]).copy()
    bit_idx = 0
    for idx in range(flat.shape[0]):
        for ch in channel_indices:
            if bit_idx >= len(bits):
                break
            chunk = 0
            for _ in range(bits_per_channel):
                chunk = (chunk << 1) | (bits[bit_idx] if bit_idx < len(bits) else 0)
                bit_idx += 1
            # NumPy 2 rejects applying a negative Python mask (``~mask``)
            # directly to an unsigned scalar. Keep the operation explicitly
            # within the byte domain so the encoder behaves consistently
            # across NumPy releases.
            flat[idx, ch] = (int(flat[idx, ch]) & clear_mask) | chunk
        if bit_idx >= len(bits):
            break

    out_img = Image.fromarray(flat.reshape(arr.shape), "RGBA")
    encoded_bytes = _image_to_bytes(out_img, output_format, quality=95)
    output_name = f"encoded{output_format_extension(output_format)}"
    return output_name, encoded_bytes


def _pvd_ranges(kind: str = "wu-tsai") -> List[Tuple[int, int, int]]:
    if kind == "wide":
        return [
            (0, 7, 4),
            (8, 15, 4),
            (16, 31, 5),
            (32, 63, 6),
            (64, 127, 7),
            (128, 255, 7),
        ]
    if kind == "narrow":
        return [
            (0, 7, 2),
            (8, 15, 2),
            (16, 31, 3),
            (32, 63, 4),
            (64, 127, 5),
            (128, 255, 6),
        ]
    return [
        (0, 7, 3),
        (8, 15, 3),
        (16, 31, 4),
        (32, 63, 5),
        (64, 127, 6),
        (128, 255, 7),
    ]


def _pvd_adjust_pair(p1: int, p2: int, diff_new: int) -> Tuple[int, int]:
    total = p1 + p2
    if p1 >= p2:
        p2_new = int(round((total - diff_new) / 2.0))
        p1_new = p2_new + diff_new
        if p1_new > 255:
            p1_new = 255
            p2_new = p1_new - diff_new
        if p2_new < 0:
            p2_new = 0
            p1_new = p2_new + diff_new
    else:
        p1_new = int(round((total - diff_new) / 2.0))
        p2_new = p1_new + diff_new
        if p1_new < 0:
            p1_new = 0
            p2_new = p1_new + diff_new
        if p2_new > 255:
            p2_new = 255
            p1_new = p2_new - diff_new
    return int(np.clip(p1_new, 0, 255)), int(np.clip(p2_new, 0, 255))


def encode_pvd_payload(
    image_bytes: bytes,
    payload: bytes,
    *,
    direction: str = "horizontal",
    range_kind: str = "wu-tsai",
    output_format: str = "png",
    filename: str = "input.png",
) -> Tuple[str, bytes]:
    if not payload:
        raise ValueError("Payload is empty.")
    if direction not in {"horizontal", "vertical", "both"}:
        raise ValueError("PVD direction must be horizontal, vertical, or both.")

    img = _open_image(image_bytes).convert("L")
    y = np.array(img).astype(np.uint8)
    ranges = _pvd_ranges(range_kind)
    bits = _bits_with_length_prefix(payload)

    def embed(values: np.ndarray, bits_local: List[int], start_idx: int) -> int:
        bit_idx = start_idx
        flat = values
        h, w = flat.shape
        for yy in range(h):
            for xx in range(0, w - 1, 2):
                if bit_idx >= len(bits_local):
                    return bit_idx
                p1 = int(flat[yy, xx])
                p2 = int(flat[yy, xx + 1])
                diff = abs(p1 - p2)
                for low, high, width in ranges:
                    if low <= diff <= high:
                        chunk_bits = bits_local[bit_idx : bit_idx + width]
                        if len(chunk_bits) < width:
                            chunk_bits = chunk_bits + [0] * (width - len(chunk_bits))
                        value = 0
                        for bit in chunk_bits:
                            value = (value << 1) | int(bit)
                        diff_new = low + value
                        p1_new, p2_new = _pvd_adjust_pair(p1, p2, diff_new)
                        flat[yy, xx] = p1_new
                        flat[yy, xx + 1] = p2_new
                        bit_idx += width
                        break
        return bit_idx

    bit_idx = 0
    if direction in {"horizontal", "both"}:
        bit_idx = embed(y, bits, bit_idx)
    if direction in {"vertical", "both"} and bit_idx < len(bits):
        y_t = y.T
        bit_idx = embed(y_t, bits, bit_idx)
        y = y_t.T

    if bit_idx < len(bits):
        raise ValueError("Payload too large for PVD capacity.")

    out_img = Image.fromarray(y, "L")
    output_format = "png"
    encoded_bytes = _image_to_bytes(out_img, output_format)
    output_name = f"encoded{output_format_extension(output_format)}"
    return output_name, encoded_bytes


_DCT_MATS: Dict[int, Tuple[np.ndarray, np.ndarray]] = {}


def _dct_matrix(n: int = 8) -> np.ndarray:
    mat = np.zeros((n, n), dtype=np.float32)
    factor = math.pi / (2 * n)
    for k in range(n):
        alpha = math.sqrt(1 / n) if k == 0 else math.sqrt(2 / n)
        for i in range(n):
            mat[k, i] = alpha * math.cos((2 * i + 1) * k * factor)
    return mat


def _dct_mats(n: int) -> Tuple[np.ndarray, np.ndarray]:
    mats = _DCT_MATS.get(n)
    if mats is not None:
        return mats
    mat = _dct_matrix(n)
    mats = (mat, mat.T)
    _DCT_MATS[n] = mats
    return mats


def _dct_coords(block_size: int, robustness: str) -> List[Tuple[int, int]]:
    if robustness == "high":
        base = [(1, 2), (2, 1), (2, 2), (1, 3), (3, 1)]
    elif robustness == "low":
        base = [(5, 6), (6, 5), (6, 6), (5, 5), (4, 6)]
    else:
        base = [(2, 3), (3, 2), (3, 4), (4, 3), (4, 4)]
    scale = max(1, block_size // 8)
    coords: List[Tuple[int, int]] = []
    seen = set()
    for u, v in base:
        cu = min(block_size - 1, u * scale)
        cv = min(block_size - 1, v * scale)
        if (cu, cv) in seen:
            continue
        seen.add((cu, cv))
        coords.append((cu, cv))
    return coords


def _embed_dct_bits(
    channel: np.ndarray,
    bits: List[int],
    *,
    block_size: int = 8,
    robustness: str = "medium",
) -> Tuple[np.ndarray, int]:
    dct_mat, idct_mat = _dct_mats(block_size)
    coords = _dct_coords(block_size, robustness)
    min_mag = {"low": 8.0, "medium": 16.0, "high": 30.0}.get(robustness, 16.0)

    height, width = channel.shape
    height_trim = height - (height % block_size)
    width_trim = width - (width % block_size)
    out = channel.astype(np.float32) - 128.0

    bit_idx = 0
    for y in range(0, height_trim, block_size):
        for x in range(0, width_trim, block_size):
            block = out[y : y + block_size, x : x + block_size]
            dct = dct_mat @ block @ idct_mat
            for u, v in coords:
                if bit_idx >= len(bits):
                    break
                bit = bits[bit_idx]
                mag = abs(dct[u, v])
                if mag < min_mag:
                    mag = min_mag
                dct[u, v] = mag if bit == 1 else -mag
                bit_idx += 1
            block_out = dct_mat.T @ dct @ dct_mat
            out[y : y + block_size, x : x + block_size] = block_out
            if bit_idx >= len(bits):
                break
        if bit_idx >= len(bits):
            break

    out = np.clip(out + 128.0, 0, 255).astype(np.uint8)
    return out, bit_idx


def encode_dct_payload(
    image_bytes: bytes,
    payload: bytes,
    *,
    block_size: int = 8,
    robustness: str = "high",
    output_format: str = "jpeg",
    filename: str = "input.jpg",
) -> Tuple[str, bytes]:
    if not payload:
        raise ValueError("Payload is empty.")
    if block_size not in {8, 16}:
        raise ValueError("DCT block size must be 8 or 16.")
    if robustness not in {"low", "medium", "high"}:
        raise ValueError("DCT robustness must be low, medium, or high.")

    base_img = _open_image(image_bytes).convert("RGB")
    bits = _bits_with_length_prefix(payload)
    output_format = "jpeg"

    for _ in range(20):
        img = base_img.convert("YCbCr")
        arr = np.array(img)
        y_encoded, bit_idx = _embed_dct_bits(
            arr[:, :, 0], bits, block_size=block_size, robustness=robustness
        )
        if bit_idx < len(bits):
            raise ValueError("Payload too large for DCT capacity.")
        arr[:, :, 0] = y_encoded
        out_img = Image.fromarray(arr.astype(np.uint8), "YCbCr").convert("RGB")
        encoded_bytes = _image_to_bytes(out_img, output_format, quality=95)
        if len(encoded_bytes) <= TWITTER_MAX_BYTES:
            output_name = f"encoded{output_format_extension(output_format)}"
            return output_name, encoded_bytes

        width, height = base_img.size
        new_size = (max(1, int(width * 0.9)), max(1, int(height * 0.9)))
        if new_size[0] >= width and width > 1:
            new_size = (width - 1, new_size[1])
        if new_size[1] >= height and height > 1:
            new_size = (new_size[0], height - 1)
        if new_size[0] < block_size or new_size[1] < block_size:
            raise ValueError("Image became too small to keep the DCT output under 900 KB.")
        base_img = base_img.resize(new_size, resample=Image.LANCZOS)

    raise ValueError("Unable to keep the DCT output under 900 KB after 20 iterations.")


def encode_f5_payload(
    image_bytes: bytes,
    payload: bytes,
    *,
    password: Optional[str] = None,
    quality: int = 100,
    output_format: str = "jpeg",
    filename: str = "input.jpg",
) -> Tuple[str, bytes]:
    if not payload:
        raise ValueError("Payload is empty.")

    img = _open_image(image_bytes).convert("YCbCr")
    arr = np.array(img)
    y = arr[:, :, 0].astype(np.float32) - 128.0
    block_size = 8
    dct_mat, idct_mat = _dct_mats(block_size)
    height, width = y.shape
    height_trim = height - (height % block_size)
    width_trim = width - (width % block_size)

    blocks: List[np.ndarray] = []
    positions: List[Tuple[int, int, int]] = []
    for y0 in range(0, height_trim, block_size):
        for x0 in range(0, width_trim, block_size):
            block = y[y0 : y0 + block_size, x0 : x0 + block_size]
            dct = dct_mat @ block @ idct_mat
            block_index = len(blocks)
            blocks.append(dct)
            for u in range(block_size):
                for v in range(block_size):
                    if u == 0 and v == 0:
                        continue
                    # Keep every AC coefficient in the same stable order the
                    # decoder will see, and make its sign survive the JPEG save.
                    if abs(dct[u, v]) < 12.0:
                        dct[u, v] = 12.0 if dct[u, v] >= 0 else -12.0
                    positions.append((block_index, u, v))

    if not positions:
        raise ValueError("No usable DCT coefficients available for F5 encoding.")

    if password:
        rng = random.Random(password)
        rng.shuffle(positions)

    bits = _bits_with_length_prefix(payload)
    k = 2
    n = (1 << k) - 1
    bit_idx = 0
    pos_idx = 0
    total_groups = len(positions) // n
    for _ in range(total_groups):
        if bit_idx >= len(bits):
            break
        if pos_idx + n > len(positions):
            break
        group = positions[pos_idx : pos_idx + n]
        pos_idx += n
        target_bits = bits[bit_idx : bit_idx + k]
        if len(target_bits) < k:
            target_bits = target_bits + [0] * (k - len(target_bits))
        target = 0
        for bit in target_bits:
            target = (target << 1) | int(bit)
        syndrome = 0
        for i, (block_index, u, v) in enumerate(group, start=1):
            if blocks[block_index][u, v] >= 0:
                syndrome ^= i
        if syndrome != target:
            flip_idx = syndrome ^ target
            if 1 <= flip_idx <= len(group):
                b_idx, u_idx, v_idx = group[flip_idx - 1]
                coeff = blocks[b_idx][u_idx, v_idx]
                if coeff == 0:
                    coeff = 1.0
                blocks[b_idx][u_idx, v_idx] = -coeff
        bit_idx += k

    if bit_idx < len(bits):
        raise ValueError("Payload too large for F5 capacity.")

    out = y.copy()
    block_idx = 0
    for y0 in range(0, height_trim, block_size):
        for x0 in range(0, width_trim, block_size):
            dct = blocks[block_idx]
            block_idx += 1
            block_out = dct_mat.T @ dct @ dct_mat
            out[y0 : y0 + block_size, x0 : x0 + block_size] = block_out

    arr[:, :, 0] = np.clip(out + 128.0, 0, 255).astype(np.uint8)
    out_img = Image.fromarray(arr.astype(np.uint8), "YCbCr").convert("RGB")
    output_format = "jpeg"
    encoded_bytes = _image_to_bytes(out_img, output_format, quality=quality)
    output_name = f"encoded{output_format_extension(output_format)}"
    return output_name, encoded_bytes


def encode_spread_spectrum_payload(
    image_bytes: bytes,
    payload: bytes,
    *,
    password: str,
    chip_length: int = 64,
    strength: int = 24,
    output_format: str = "png",
    filename: str = "input.png",
) -> Tuple[str, bytes]:
    if not payload:
        raise ValueError("Payload is empty.")
    if not password:
        raise ValueError("Spread spectrum requires a password.")
    if chip_length <= 0:
        raise ValueError("Spread factor must be positive.")
    if strength <= 0:
        raise ValueError("Strength must be positive.")

    img = _open_image(image_bytes).convert("YCbCr")
    arr = np.array(img)
    y = arr[:, :, 0].astype(np.float32)
    flat = y.reshape(-1)
    bits = _bits_with_length_prefix(payload)

    rng = random.Random(password)
    max_index = len(flat)
    max_bits = max_index // chip_length
    if len(bits) > max_bits:
        raise ValueError("Payload too large for spread spectrum capacity.")

    for bit in bits:
        idxs = rng.sample(range(max_index), chip_length)
        seq = [1.0 if rng.random() > 0.5 else -1.0 for _ in range(chip_length)]
        direction = 1.0 if bit == 1 else -1.0
        for i, idx in enumerate(idxs):
            flat[idx] += direction * seq[i] * float(strength)

    arr[:, :, 0] = np.clip(flat.reshape(y.shape), 0, 255).astype(np.uint8)
    out_img = Image.fromarray(arr.astype(np.uint8), "YCbCr").convert("RGB")
    output_format = normalize_output_format(output_format)
    encoded_bytes = _image_to_bytes(out_img, output_format, quality=95)
    output_name = f"encoded{output_format_extension(output_format)}"
    return output_name, encoded_bytes


def encode_palette_payload(
    image_bytes: bytes,
    payload: bytes,
    *,
    colors: int = 256,
    mode: str = "index",
    output_format: str = "png",
    filename: str = "input.png",
) -> Tuple[str, bytes]:
    if not payload:
        raise ValueError("Payload is empty.")
    if colors not in {32, 64, 128, 256}:
        raise ValueError("Palette colors must be 32, 64, 128, or 256.")

    img = _open_image(image_bytes).convert("RGBA")
    pal_img = img.convert("P", palette=Image.ADAPTIVE, colors=colors)
    base_palette = pal_img.getpalette()
    bits = _bits_with_length_prefix(payload)

    if mode == "index":
        indices = np.array(pal_img)
        capacity = indices.size
        if len(bits) > capacity:
            raise ValueError("Payload too large for palette index capacity.")
        flat = indices.reshape(-1)
        for idx, bit in enumerate(bits):
            val = int(flat[idx])
            if (val & 1) != bit:
                if val == colors - 1:
                    val -= 1
                else:
                    val += 1
            flat[idx] = val
        indices = flat.reshape(indices.shape)
        pal_img = Image.fromarray(indices.astype(np.uint8), mode="P")
        if base_palette:
            pal_img.putpalette(base_palette)
    elif mode == "order":
        palette = pal_img.getpalette() or []
        if not palette:
            raise ValueError("No palette data available for ordering mode.")
        entries = [palette[i : i + 3] for i in range(0, len(palette), 3)]
        capacity = len(entries) // 2
        if len(bits) > capacity:
            raise ValueError("Payload too large for palette ordering capacity.")
        for idx, bit in enumerate(bits):
            e1 = entries[2 * idx]
            e2 = entries[2 * idx + 1]
            lum1 = 0.2126 * e1[0] + 0.7152 * e1[1] + 0.0722 * e1[2]
            lum2 = 0.2126 * e2[0] + 0.7152 * e2[1] + 0.0722 * e2[2]
            if (lum1 <= lum2 and bit == 1) or (lum1 > lum2 and bit == 0):
                entries[2 * idx], entries[2 * idx + 1] = e2, e1
        new_palette: List[int] = []
        for entry in entries:
            new_palette.extend(entry)
        pal_img.putpalette(new_palette)
    else:
        raise ValueError("Palette mode must be 'index' or 'order'.")

    output_format = "png"
    encoded_bytes = _image_to_bytes(pal_img, output_format)
    output_name = f"encoded{output_format_extension(output_format)}"
    return output_name, encoded_bytes


def encode_png_chunks_payload(
    image_bytes: bytes,
    payload: bytes,
    *,
    chunk_type: str = "tEXt",
    keyword: str = "Comment",
    output_format: str = "png",
    filename: str = "input.png",
) -> Tuple[str, bytes]:
    if not payload:
        raise ValueError("Payload is empty.")

    chunk_type = chunk_type.strip()
    if len(chunk_type) != 4:
        raise ValueError("Chunk type must be 4 characters.")
    keyword = keyword.strip() or "Comment"

    img = _open_image(image_bytes).convert("RGBA")
    png_bytes = _image_to_bytes(img, "png")

    text = payload.decode("utf-8", errors="replace")
    try:
        latin_text = text.encode("latin-1")
    except UnicodeEncodeError:
        # PNG tEXt/zTXt are Latin-1 only. Preserve Unicode payloads by using
        # the standard UTF-8 iTXt chunk rather than returning a server error.
        chunk_type = "iTXt"
        latin_text = b""
    if chunk_type == "tEXt":
        chunk_data = keyword.encode("latin-1") + b"\x00" + latin_text
    elif chunk_type == "zTXt":
        compressed = zlib.compress(latin_text)
        chunk_data = keyword.encode("latin-1") + b"\x00" + b"\x00" + compressed
    elif chunk_type == "iTXt":
        chunk_data = (
            keyword.encode("latin-1")
            + b"\x00\x00\x00"
            + b"\x00"
            + b"\x00"
            + text.encode("utf-8")
        )
    else:
        raise ValueError("Chunk type must be tEXt, zTXt, or iTXt.")

    def build_chunk(chunk_name: bytes, data: bytes) -> bytes:
        length = len(data).to_bytes(4, "big")
        crc = zlib.crc32(chunk_name + data) & 0xFFFFFFFF
        return length + chunk_name + data + crc.to_bytes(4, "big")

    new_chunk = build_chunk(chunk_type.encode("latin-1"), chunk_data)
    if not png_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError("Invalid PNG data.")

    offset = 8
    chunks: List[bytes] = [png_bytes[:8]]
    inserted = False
    while offset + 8 <= len(png_bytes):
        length = int.from_bytes(png_bytes[offset : offset + 4], "big")
        ctype = png_bytes[offset + 4 : offset + 8]
        chunk_end = offset + 8 + length + 4
        chunk = png_bytes[offset:chunk_end]
        if ctype == b"IEND" and not inserted:
            chunks.append(new_chunk)
            inserted = True
        chunks.append(chunk)
        offset = chunk_end
        if ctype == b"IEND":
            break

    if not inserted:
        raise ValueError("Failed to insert PNG chunk.")

    output_format = "png"
    encoded_bytes = b"".join(chunks)
    output_name = f"encoded{output_format_extension(output_format)}"
    return output_name, encoded_bytes


def _chroma_bit_pos(intensity: int) -> int:
    mapping = {1: 0, 2: 1, 3: 2, 5: 3}
    return mapping.get(intensity, 0)


def encode_chroma_payload(
    image_bytes: bytes,
    payload: bytes,
    *,
    color_space: str = "ycbcr",
    channel: str = "both",
    intensity: int = 5,
    pattern: str = "sequential",
    output_format: str = "png",
    filename: str = "input.png",
) -> Tuple[str, bytes]:
    from .color_spaces import hsl_to_rgb, lab_to_rgb, rgb_to_hsl, rgb_to_lab

    if not payload:
        raise ValueError("Payload is empty.")
    if channel not in {"both", "cb", "cr"}:
        raise ValueError("Chroma channel must be both, cb, or cr.")
    if pattern not in {"sequential", "checkerboard", "edges"}:
        raise ValueError("Chroma pattern must be sequential, checkerboard, or edges.")

    img = _open_image(image_bytes).convert("RGB")
    rgb = np.array(img)
    height, width = rgb.shape[:2]
    bits = _bits_with_length_prefix(payload)

    yy, xx = np.mgrid[0:height, 0:width]
    if pattern == "checkerboard":
        mask = (xx + yy) % 2 == 0
    elif pattern == "edges":
        gray = (0.299 * rgb[:, :, 0] + 0.587 * rgb[:, :, 1] + 0.114 * rgb[:, :, 2])
        gx = np.abs(np.diff(gray, axis=1, prepend=gray[:, :1]))
        gy = np.abs(np.diff(gray, axis=0, prepend=gray[:1, :]))
        edges = gx + gy
        threshold = np.percentile(edges, 75)
        mask = edges >= threshold
    else:
        mask = np.ones((height, width), dtype=bool)

    bit_pos = _chroma_bit_pos(intensity)
    bit_mask = 1 << bit_pos

    def embed_channel(channel_array: np.ndarray, bits_local: List[int], start_idx: int) -> int:
        bit_idx = start_idx
        flat = channel_array
        for y in range(height):
            for x in range(width):
                if not mask[y, x]:
                    continue
                if bit_idx >= len(bits_local):
                    return bit_idx
                bit = bits_local[bit_idx]
                value = int(flat[y, x])
                flat[y, x] = (value & ~bit_mask) | (bit << bit_pos)
                bit_idx += 1
        return bit_idx

    def embed_both(ch1: np.ndarray, ch2: np.ndarray, bits_local: List[int]) -> int:
        bit_idx = 0
        for y in range(height):
            for x in range(width):
                if not mask[y, x]:
                    continue
                if bit_idx >= len(bits_local):
                    return bit_idx
                bit = bits_local[bit_idx]
                ch1[y, x] = (int(ch1[y, x]) & ~bit_mask) | (bit << bit_pos)
                bit_idx += 1
                if bit_idx >= len(bits_local):
                    return bit_idx
                bit = bits_local[bit_idx]
                ch2[y, x] = (int(ch2[y, x]) & ~bit_mask) | (bit << bit_pos)
                bit_idx += 1
        return bit_idx

    color_space = color_space.lower()
    channel = channel.lower()

    if color_space == "ycbcr":
        ycbcr = np.array(img.convert("YCbCr"))
        cb = ycbcr[:, :, 1].astype(np.uint8)
        cr = ycbcr[:, :, 2].astype(np.uint8)
        if channel == "cb":
            bit_idx = embed_channel(cb, bits, 0)
        elif channel == "cr":
            bit_idx = embed_channel(cr, bits, 0)
        else:
            bit_idx = embed_both(cb, cr, bits)
        ycbcr[:, :, 1] = cb
        ycbcr[:, :, 2] = cr
        out_img = Image.fromarray(ycbcr.astype(np.uint8), "YCbCr").convert("RGB")

        # YCbCr cannot be stored directly in PNG. Correct the RGB result one
        # payload pixel at a time so converting it back to YCbCr preserves the
        # requested chroma bits instead of silently corrupting them.
        corrected = np.array(out_img).copy()
        bit_idx = 0
        for y_pos in range(height):
            for x_pos in range(width):
                if not mask[y_pos, x_pos] or bit_idx >= len(bits):
                    continue
                targets: Dict[int, int] = {}
                if channel in {"cb", "both"}:
                    targets[1] = bits[bit_idx]
                    bit_idx += 1
                if channel in {"cr", "both"} and bit_idx < len(bits):
                    targets[2] = bits[bit_idx]
                    bit_idx += 1

                for radius in range(0, 49):
                    pixel_img = Image.fromarray(corrected[y_pos:y_pos + 1, x_pos:x_pos + 1], "RGB")
                    pixel_ycbcr = np.array(pixel_img.convert("YCbCr"))[0, 0]
                    if all(((int(pixel_ycbcr[ch]) >> bit_pos) & 1) == bit for ch, bit in targets.items()):
                        break
                    if radius == 0:
                        continue
                    found = False
                    for target_channel in targets:
                        rgb_channel = 2 if target_channel == 1 else 0
                        original = int(corrected[y_pos, x_pos, rgb_channel])
                        for sign in (1, -1):
                            corrected[y_pos, x_pos, rgb_channel] = np.uint8(
                                max(0, min(255, original + sign * radius))
                            )
                            test_img = Image.fromarray(
                                corrected[y_pos:y_pos + 1, x_pos:x_pos + 1], "RGB"
                            )
                            test_ycbcr = np.array(test_img.convert("YCbCr"))[0, 0]
                            if all(
                                ((int(test_ycbcr[ch]) >> bit_pos) & 1) == bit
                                for ch, bit in targets.items()
                            ):
                                found = True
                                break
                            corrected[y_pos, x_pos, rgb_channel] = np.uint8(original)
                        if found:
                            break
                    if found:
                        break
        out_img = Image.fromarray(corrected, "RGB")
    elif color_space == "hsl":
        h, s, l = rgb_to_hsl(rgb)
        h_u8 = (h * 255.0).clip(0, 255).astype(np.uint8)
        s_u8 = (s * 255.0).clip(0, 255).astype(np.uint8)
        if channel == "cb":
            bit_idx = embed_channel(s_u8, bits, 0)
        elif channel == "cr":
            bit_idx = embed_channel(h_u8, bits, 0)
        else:
            bit_idx = embed_both(s_u8, h_u8, bits)
        h = (h_u8.astype(np.float32) / 255.0) % 1.0
        s = (s_u8.astype(np.float32) / 255.0).clip(0, 1)
        out_rgb = hsl_to_rgb(h, s, l)
        out_img = Image.fromarray(out_rgb, "RGB")
    elif color_space == "lab":
        l, a, b = rgb_to_lab(rgb)
        a_u8 = (a + 128.0).clip(0, 255).astype(np.uint8)
        b_u8 = (b + 128.0).clip(0, 255).astype(np.uint8)
        if channel == "cb":
            bit_idx = embed_channel(a_u8, bits, 0)
        elif channel == "cr":
            bit_idx = embed_channel(b_u8, bits, 0)
        else:
            bit_idx = embed_both(a_u8, b_u8, bits)
        a = a_u8.astype(np.float32) - 128.0
        b = b_u8.astype(np.float32) - 128.0
        out_rgb = lab_to_rgb(l, a, b)
        out_img = Image.fromarray(out_rgb, "RGB")
    else:
        raise ValueError("Color space must be ycbcr, hsl, or lab.")

    if bit_idx < len(bits):
        raise ValueError("Payload too large for chroma capacity.")

    output_format = "png"
    encoded_bytes = _image_to_bytes(out_img, output_format, quality=95)
    output_name = f"encoded{output_format_extension(output_format)}"
    return output_name, encoded_bytes

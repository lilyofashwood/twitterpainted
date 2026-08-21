"""Flask entrypoint that exposes encoder/decoder endpoints and serves the UI."""

import json
from io import BytesIO
from pathlib import Path
from typing import Optional

from flask import Flask, jsonify, render_template, request
from PIL import Image

from engine.analyzer_catalog import default_selected_for_profile, list_analyzer_catalog
from engine.analysis_profiles import DEFAULT_PROFILE, list_profiles, normalize_profile
from engine.analyzers.simple_lsb import _decode_plane
from engine.decoder import run_analysis
from engine.encoder import (
    TWITTER_MAX_EDGE,
    as_data_url,
    encode_chroma_payload,
    encode_dct_payload,
    encode_f5_payload,
    encode_lsb_payload,
    encode_multi_channel,
    encode_palette_payload,
    encode_payload,
    encode_png_chunks_payload,
    encode_pvd_payload,
    encode_spread_spectrum_payload,
    normalize_carrier_prep,
    normalize_output_format,
    prepare_carrier_bytes,
    twitter_png_profile,
)
from engine.tooling import get_tool_status

app = Flask(__name__, static_folder="static", template_folder="templates")
# Leave room for multipart framing while the route enforces an 8 MiB file cap.
app.config["MAX_CONTENT_LENGTH"] = 9 * 1024 * 1024


@app.errorhandler(413)
def request_entity_too_large(error):
    return jsonify({"error": "Carrier file too large. Maximum upload size is 8MB."}), 413


@app.errorhandler(500)
def internal_server_error(error):
    return jsonify({"error": f"Internal server error: {error}"}), 500


def sniff_image_mime(image_bytes: bytes) -> str:
    if image_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if image_bytes.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    return "application/octet-stream"


def _verify_twitterpaint_export(
    image_bytes: bytes,
    expected_by_plane: dict[str, str],
    *,
    output_format: str,
    twitterpaint_mode: str,
    carrier_prep: str,
) -> dict[str, object]:
    """Decode the just-exported carrier and report exact text round-trip status."""
    profile = twitter_png_profile(image_bytes)
    try:
        image = Image.open(BytesIO(image_bytes)).convert("RGBA")
        recovered = {
            plane: _decode_plane(image, plane)
            for plane in expected_by_plane
        }
        exact = bool(expected_by_plane) and all(
            recovered.get(plane) == expected
            for plane, expected in expected_by_plane.items()
        )
    except Exception:
        exact = False

    survivor_ready = (
        carrier_prep == "twitterpaint"
        and exact
        and bool(profile.get("ready"))
    )
    if survivor_ready:
        message = (
            f"Twitterpaint check passed: every selected {twitterpaint_mode} payload round-trips "
            f"exactly from this opaque PNG, its longest edge is at most {TWITTER_MAX_EDGE}px, "
            "and it is ready for X/Twitter's lossless PNG lane. Decode the posted copy to confirm."
        )
    elif exact and carrier_prep != "twitterpaint":
        message = (
            f"Local payload check passed, but survivor status is off because carrier prep is "
            f"'{carrier_prep}'. Choose Twitterpaint prep before posting to X/Twitter."
        )
    elif exact:
        message = (
            f"Local payload check passed, but this {output_format.upper()} is outside the "
            f"Twitterpaint survivor profile. Use opaque PNG at no more than {TWITTER_MAX_EDGE}px."
        )
    else:
        message = (
            f"Export self-check failed: at least one {twitterpaint_mode} payload did not survive "
            f"this {output_format.upper()} export. Choose PNG or change the carrier before posting."
        )
    return {
        "status": "passed" if survivor_ready else "failed",
        "round_trip": exact,
        "survivor_ready": survivor_ready,
        "output_format": output_format,
        "twitterpaint_mode": twitterpaint_mode,
        "carrier_prep": carrier_prep,
        "checked_planes": list(expected_by_plane),
        "profile": profile,
        "message": message,
    }


def _form_flag(value: Optional[str]) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes", "on"}


def _catalog_backed_profiles():
    """Return profile suggestions from the same catalog that powers checkboxes."""
    profiles = []
    for raw_profile in list_profiles():
        profile = dict(raw_profile)
        catalog = list_analyzer_catalog(str(profile["id"]))
        recommended = [row for row in catalog if row["recommended_in_profile"]]
        profile["internal_tools"] = sorted(
            str(row["id"]) for row in recommended if row["kind"] == "internal"
        )
        profile["external_tools"] = sorted(
            str(row["id"]) for row in recommended if row["kind"] == "external"
        )
        profile["recommended_tools"] = sorted(
            str(row["id"]) for row in recommended
        )
        profiles.append(profile)
    return profiles


@app.route("/")
def index() -> str:
    return render_template("index.html")


@app.get("/api/tools")
def api_tools():
    try:
        return jsonify({"tools": get_tool_status()})
    except Exception as exc:
        return jsonify({"error": f"Failed to get tool status: {str(exc)}"}), 500


@app.get("/api/profiles")
def api_profiles():
    try:
        return jsonify(
            {
                "default_profile": DEFAULT_PROFILE,
                "profiles": _catalog_backed_profiles(),
                "analyzers": list_analyzer_catalog(DEFAULT_PROFILE),
                "default_selected_tools": default_selected_for_profile(DEFAULT_PROFILE),
            }
        )
    except Exception as exc:
        return jsonify({"error": f"Failed to get analysis profiles: {str(exc)}"}), 500


@app.get("/api/analyzers")
def api_analyzers():
    profile = normalize_profile(request.args.get("profile"))
    try:
        return jsonify(
            {
                "profile": profile,
                "analyzers": list_analyzer_catalog(profile),
                "default_selected_tools": default_selected_for_profile(profile),
            }
        )
    except Exception as exc:
        return jsonify({"error": f"Failed to get analyzer catalog: {str(exc)}"}), 500


@app.post("/api/encode")
def api_encode():
    try:
        encode_method = request.form.get("encodeMethod")
        legacy_mode = request.form.get("encodeMode")
        if not encode_method:
            if legacy_mode:
                encode_method = "advanced_lsb" if legacy_mode == "advanced" else "simple_lsb"
            else:
                encode_method = "twitterpaint"
        encode_method = (encode_method or "twitterpaint").strip().lower()
        twitterpaint_request = encode_method == "twitterpaint"
        twitterpaint_mode: Optional[str] = None

        payload_text: Optional[str] = request.form.get("text") or None
        payload_mode = (request.form.get("payloadMode") or "text").strip().lower()
        if payload_mode == "text" and request.files.get("payload") and not payload_text:
            payload_mode = "file"
        channels_json = request.form.get("channels")

        if twitterpaint_request:
            twitterpaint_mode = (request.form.get("twitterpaintMode") or "combined").strip().lower()
            if twitterpaint_mode not in {"combined", "individual"}:
                return jsonify({"error": "twitterpaintMode must be 'combined' or 'individual'."}), 400
            payload_mode = "text"
            if twitterpaint_mode == "combined":
                encode_method = "simple_lsb"
                payload_text = request.form.get("twitterpaintText") or payload_text
            else:
                encode_method = "advanced_lsb"

        payload_file = request.files.get("payload")
        image_file = request.files.get("image")

        if image_file is None:
            return jsonify({"error": "Image file is required"}), 400

        if not image_file.filename:
            return jsonify({"error": "Image file must have a filename"}), 400

        try:
            image_bytes = image_file.read()
        except Exception as e:
            return jsonify({"error": f"Failed to read image file: {str(e)}"}), 400

        if not image_bytes:
            return jsonify({"error": "Image file is empty"}), 400

        # Validate file size (8MB limit as suggested by the frontend)
        max_size = 8 * 1024 * 1024  # 8MB
        if len(image_bytes) > max_size:
            return jsonify({"error": f"Image file too large. Maximum size is {max_size // (1024 * 1024)}MB"}), 400

        filename = image_file.filename or "input.png"
    except Exception as e:
        return jsonify({"error": f"Failed to process request: {str(e)}"}), 400

    try:
        output_format = normalize_output_format(request.form.get("outputFormat", "png"))
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    try:
        carrier_prep = normalize_carrier_prep(
            request.form.get("carrierPrep"),
            default="twitterpaint" if twitterpaint_request else "none",
        )
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    # Advanced LSB per-channel
    if encode_method == "advanced_lsb":
        if not channels_json:
            return jsonify({"error": "Channel payloads are required for advanced_lsb."}), 400
        try:
            channels = json.loads(channels_json)
        except json.JSONDecodeError as e:
            return jsonify({"error": f"Invalid JSON in channels payload: {str(e)}"}), 400
        except Exception as e:
            return jsonify({"error": f"Failed to parse channels payload: {str(e)}"}), 400

        if not isinstance(channels, dict):
            return jsonify({"error": "Channels payload must be a JSON object"}), 400

        if twitterpaint_request and bool((channels.get("A") or {}).get("enabled")):
            return jsonify({"error": "Twitterpaint individual mode supports R, G, and B only; alpha is excluded."}), 400

        channel_payloads = {}
        try:
            allowed_channels = ["R", "G", "B"] if twitterpaint_request else ["R", "G", "B", "A"]
            for ch in allowed_channels:
                cfg = channels.get(ch) or {}
                enabled = bool(cfg.get("enabled"))
                if not enabled:
                    channel_payloads[ch] = {"enabled": False}
                    continue

                payload_type = cfg.get("type")
                if payload_type == "text":
                    channel_payloads[ch] = {
                        "enabled": True,
                        "type": "text",
                        "text": cfg.get("text") or "",
                    }
                elif payload_type == "file" and not twitterpaint_request:
                    file_field = f"file_{ch}"
                    upload = request.files.get(file_field)
                    if not upload:
                        return jsonify({"error": f"Missing file upload for channel {ch}"}), 400
                    try:
                        file_data = upload.read()
                        if not file_data:
                            return jsonify({"error": f"File for channel {ch} is empty"}), 400
                        channel_payloads[ch] = {
                            "enabled": True,
                            "type": "file",
                            "file_data": file_data,
                        }
                    except Exception as e:
                        return jsonify({"error": f"Failed to read file for channel {ch}: {str(e)}"}), 400
                else:
                    if twitterpaint_request:
                        return jsonify({"error": f"Twitterpaint channel {ch} must contain text."}), 400
                    return jsonify({"error": f"Invalid payload type '{payload_type}' for channel {ch}. Must be 'text' or 'file'"}), 400
        except Exception as e:
            return jsonify({"error": f"Failed to process channel payloads: {str(e)}"}), 400

        try:
            encoded_name, encoded_bytes = encode_multi_channel(
                image_bytes,
                channel_payloads,
                filename=filename,
                twitter_safe_preprocess=twitterpaint_request,
                output_format=output_format,
                carrier_prep=carrier_prep,
            )
            output_mime = sniff_image_mime(encoded_bytes)
            response = {"filename": encoded_name, "data_url": as_data_url(encoded_bytes, mime=output_mime)}
            if twitterpaint_request:
                expected = {
                    ch: str(cfg.get("text") or "")
                    for ch, cfg in channel_payloads.items()
                    if cfg.get("enabled")
                }
                response["verification"] = _verify_twitterpaint_export(
                    encoded_bytes,
                    expected,
                    output_format=output_format,
                    twitterpaint_mode="individual",
                    carrier_prep=carrier_prep,
                )
            response["carrier_prep"] = carrier_prep
            return jsonify(response)
        except ValueError as exc:
            return jsonify({"error": f"Encoding failed: {str(exc)}"}), 400
        except Exception as exc:
            return jsonify({"error": f"Unexpected error during encoding: {str(exc)}"}), 500

    # Simple LSB (legacy-compatible)
    if encode_method == "simple_lsb":
        mode = request.form.get("mode") or ("zlib" if payload_mode == "file" else "text")
        plane = request.form.get("plane", "RGB")
        if twitterpaint_request:
            mode = "text"
            plane = "RGB"
        if mode not in {"text", "zlib"}:
            return jsonify({"error": f"Invalid mode '{mode}'. Must be 'text' or 'zlib'"}), 400

        if mode == "text":
            text = payload_text or ""
            if not text:
                return jsonify({"error": "Text payload is required for text mode"}), 400
            file_data = None
        else:  # zlib mode
            if not payload_file:
                return jsonify({"error": "File upload is required for zlib mode"}), 400
            try:
                file_data = payload_file.read()
                if not file_data:
                    return jsonify({"error": "Payload file is empty"}), 400
            except Exception as e:
                return jsonify({"error": f"Failed to read payload file: {str(e)}"}), 400
            text = None

        try:
            encoded_name, encoded_bytes = encode_payload(
                image_bytes,
                filename=filename,
                mode=mode,
                plane=plane,
                text=text,
                file_data=file_data,
                output_format=output_format,
                lossy_output=True,
                twitter_safe_preprocess=twitterpaint_request,
                carrier_prep=carrier_prep,
            )
            output_mime = sniff_image_mime(encoded_bytes)
            response = {"filename": encoded_name, "data_url": as_data_url(encoded_bytes, mime=output_mime)}
            if twitterpaint_request:
                response["verification"] = _verify_twitterpaint_export(
                    encoded_bytes,
                    {"RGB": text or ""},
                    output_format=output_format,
                    twitterpaint_mode="combined",
                    carrier_prep=carrier_prep,
                )
            response["carrier_prep"] = carrier_prep
            return jsonify(response)
        except ValueError as exc:
            return jsonify({"error": f"Encoding failed: {str(exc)}"}), 400
        except Exception as exc:
            return jsonify({"error": f"Unexpected error during encoding: {str(exc)}"}), 500

    # Ste.gg-style encoder methods
    payload: Optional[bytes] = None
    if payload_mode == "file":
        if not payload_file:
            return jsonify({"error": "Payload file is required for file mode"}), 400
        try:
            payload = payload_file.read()
        except Exception as exc:
            return jsonify({"error": f"Failed to read payload file: {str(exc)}"}), 400
        if not payload:
            return jsonify({"error": "Payload file is empty"}), 400
    else:
        text = payload_text or ""
        if not text:
            return jsonify({"error": "Text payload is required for this mode"}), 400
        payload = text.encode("utf-8")

    try:
        prepared_image_bytes = prepare_carrier_bytes(image_bytes, carrier_prep)
    except ValueError as exc:
        return jsonify({"error": f"Carrier preparation failed: {str(exc)}"}), 400

    try:
        if encode_method == "lsb":
            channels = request.form.get("lsbChannels", "RGB")
            bits_per_channel = int(request.form.get("lsbBits", "1"))
            encoded_name, encoded_bytes = encode_lsb_payload(
                prepared_image_bytes,
                payload,
                channels=channels,
                bits_per_channel=bits_per_channel,
                output_format=output_format,
                filename=filename,
            )
        elif encode_method == "pvd":
            direction = request.form.get("pvdDirection", "horizontal")
            range_kind = request.form.get("pvdRange", "wu-tsai")
            encoded_name, encoded_bytes = encode_pvd_payload(
                prepared_image_bytes,
                payload,
                direction=direction,
                range_kind=range_kind,
                output_format=output_format,
                filename=filename,
            )
        elif encode_method == "dct":
            robustness = request.form.get("dctRobustness", "high")
            block_size = int(request.form.get("dctBlockSize", "8"))
            encoded_name, encoded_bytes = encode_dct_payload(
                prepared_image_bytes,
                payload,
                block_size=block_size,
                robustness=robustness,
                output_format="jpeg",
                filename=filename,
            )
        elif encode_method == "f5":
            password = request.form.get("f5Password") or ""
            if not password:
                return jsonify({"error": "F5 requires a password."}), 400
            quality_val = request.form.get("f5Quality", "1.0")
            try:
                quality_float = float(quality_val)
            except ValueError:
                quality_float = 0.95
            quality = int(quality_float * 100) if quality_float <= 1 else int(quality_float)
            encoded_name, encoded_bytes = encode_f5_payload(
                prepared_image_bytes,
                payload,
                password=password,
                quality=quality,
                output_format="jpeg",
                filename=filename,
            )
        elif encode_method == "spread_spectrum":
            password = request.form.get("spreadPassword") or ""
            if not password:
                return jsonify({"error": "Spread spectrum requires a password."}), 400
            chip_length = int(request.form.get("spreadFactor", "64"))
            strength = int(request.form.get("spreadStrength", "24"))
            encoded_name, encoded_bytes = encode_spread_spectrum_payload(
                prepared_image_bytes,
                payload,
                password=password,
                chip_length=chip_length,
                strength=strength,
                output_format=output_format,
                filename=filename,
            )
        elif encode_method == "palette":
            colors = int(request.form.get("paletteColors", "256"))
            mode = request.form.get("paletteMode", "index")
            encoded_name, encoded_bytes = encode_palette_payload(
                prepared_image_bytes,
                payload,
                colors=colors,
                mode=mode,
                output_format="png",
                filename=filename,
            )
        elif encode_method == "chroma":
            color_space = request.form.get("chromaSpace", "ycbcr")
            channel = request.form.get("chromaChannel", "both")
            intensity = int(request.form.get("chromaIntensity", "5"))
            pattern = request.form.get("chromaPattern", "sequential")
            encoded_name, encoded_bytes = encode_chroma_payload(
                prepared_image_bytes,
                payload,
                color_space=color_space,
                channel=channel,
                intensity=intensity,
                pattern=pattern,
                output_format=output_format,
                filename=filename,
            )
        elif encode_method == "png_chunks":
            chunk_type = request.form.get("pngChunkType", "tEXt")
            keyword = request.form.get("pngChunkKeyword", "Comment")
            encoded_name, encoded_bytes = encode_png_chunks_payload(
                prepared_image_bytes,
                payload,
                chunk_type=chunk_type,
                keyword=keyword,
                output_format="png",
                filename=filename,
            )
        else:
            return jsonify({"error": f"Unknown encode method '{encode_method}'"}), 400

        output_mime = sniff_image_mime(encoded_bytes)
        return jsonify(
            {
                "filename": encoded_name,
                "data_url": as_data_url(encoded_bytes, mime=output_mime),
                "carrier_prep": carrier_prep,
            }
        )
    except ValueError as exc:
        return jsonify({"error": f"Encoding failed: {str(exc)}"}), 400
    except Exception as exc:
        return jsonify({"error": f"Unexpected error during encoding: {str(exc)}"}), 500


@app.post("/api/decode")
def api_decode():
    # Keep the multipart field name `image` for API compatibility; the payload
    # itself may be an image, audio/video file, PDF, archive, or binary carrier.
    carrier_file = request.files.get("image")
    if carrier_file is None:
        return jsonify({"error": "Carrier file is required"}), 400

    if not carrier_file.filename:
        return jsonify({"error": "Carrier file must have a filename"}), 400

    try:
        carrier_bytes = carrier_file.read()
    except Exception as e:
        return jsonify({"error": f"Failed to read carrier file: {str(e)}"}), 400

    if not carrier_bytes:
        return jsonify({"error": "Carrier file is empty"}), 400

    # Validate file size (8MB limit)
    max_size = 8 * 1024 * 1024  # 8MB
    if len(carrier_bytes) > max_size:
        return jsonify({"error": f"Carrier file too large. Maximum size is {max_size // (1024 * 1024)}MB"}), 400

    password = request.form.get("password") or None
    deep_analysis = _form_flag(request.form.get("deep", "false"))
    manual_tools = _form_flag(request.form.get("manual", "false"))
    binwalk_extract = _form_flag(request.form.get("binwalkExtract", "false"))
    invisible_unicode = _form_flag(request.form.get("unicodeSweep", "false"))
    unicode_tier1 = _form_flag(request.form.get("unicodeTier1", "false"))
    unicode_separators = _form_flag(request.form.get("unicodeSeparators", "false"))
    unicode_aggressiveness = request.form.get("unicodeAggressiveness") or "balanced"
    decode_option = request.form.get("decodeOption") or None
    spread_enabled = _form_flag(request.form.get("spreadSpectrum", "false"))
    analysis_profile = request.form.get("analysisProfile") or None
    selected_tools: Optional[list[str]] = None
    selected_tools_raw = request.form.get("selectedTools")
    if selected_tools_raw:
        import json

        try:
            parsed = json.loads(selected_tools_raw)
            if not isinstance(parsed, list):
                return jsonify({"error": "selectedTools must be a JSON array."}), 400
            selected_tools = [str(item) for item in parsed]
        except Exception as exc:
            return jsonify({"error": f"Invalid selectedTools payload: {str(exc)}"}), 400

    try:
        analysis = run_analysis(
            carrier_bytes,
            carrier_file.filename or "upload.bin",
            password=password,
            deep_analysis=deep_analysis,
            manual_tools=manual_tools,
            binwalk_extract=binwalk_extract,
            invisible_unicode=invisible_unicode,
            unicode_tier1=unicode_tier1,
            unicode_separators=unicode_separators,
            unicode_aggressiveness=unicode_aggressiveness,
            spread_enabled=spread_enabled,
            decode_option=decode_option,
            analysis_profile=analysis_profile,
            selected_tools=selected_tools,
        )
        return jsonify(analysis)
    except ValueError as exc:
        return jsonify({"error": f"Analysis failed: {str(exc)}"}), 400
    except Exception as exc:
        return jsonify({"error": f"Unexpected error during analysis: {str(exc)}"}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)

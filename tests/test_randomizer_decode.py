import json

from engine.analyzers.randomizer_decode import _decode_randomizer_text, analyze_randomizer_decode


def test_randomizer_decodes_base64_without_splitting_on_letter_w(tmp_path):
    results_path = tmp_path / "results.json"
    results_path.write_text(
        json.dumps(
            {
                "simple_lsb": {
                    "decoded_text": {"RGB": "ZmxhZ3tzZWNyZXR9"},
                }
            }
        ),
        encoding="utf-8",
    )

    analyze_randomizer_decode(tmp_path / "unused.png", tmp_path)

    result = json.loads(results_path.read_text(encoding="utf-8"))["randomizer_decode"]
    assert result["status"] == "ok"
    assert result["details"]["decoded_preview"] == "flag{secret}"
    assert result["details"]["transforms"][0]["transform"] == "base64"


def test_randomizer_preserves_and_decodes_whitespace_separated_tokens():
    decoded, transforms, _, _ = _decode_randomizer_text(
        "ZmxhZ3tzZWNyZXR9 ZmxhZ3thZ2Fpbn0="
    )

    assert decoded == "flag{secret} flag{again}"
    assert [item["transform"] for item in transforms] == ["base64", "base64"]

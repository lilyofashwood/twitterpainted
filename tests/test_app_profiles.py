import json
from io import BytesIO

import app as app_module


def test_single_app_has_no_legacy_mode_routes():
    routes = {rule.rule for rule in app_module.app.url_map.iter_rules()}

    assert "/lite" not in routes
    assert not any(route.startswith("/api/lite") for route in routes)


def test_profile_api_defaults_to_light_and_only_suggests_simple_lsb():
    response = app_module.app.test_client().get("/api/profiles")

    assert response.status_code == 200
    assert response.json["default_profile"] == "light"
    assert response.json["default_selected_tools"] == ["simple_lsb"]

    for profile in response.json["profiles"]:
        recommended = profile["recommended_tools"]
        exposed = sorted(profile["internal_tools"] + profile["external_tools"])
        assert exposed == recommended

        analyzer_response = app_module.app.test_client().get(
            f"/api/analyzers?profile={profile['id']}"
        )
        assert analyzer_response.status_code == 200
        assert recommended == analyzer_response.json["default_selected_tools"]


def test_analyzer_api_normalizes_legacy_profile_without_disabling_tools():
    response = app_module.app.test_client().get("/api/analyzers?profile=simple")

    assert response.status_code == 200
    assert response.json["profile"] == "light"
    assert response.json["default_selected_tools"] == ["simple_lsb"]
    assert all(row["enabled_in_profile"] for row in response.json["analyzers"])


def test_decode_endpoint_forwards_explicit_selection_unchanged(monkeypatch):
    captured = {}

    def fake_run_analysis(_image, _filename, **kwargs):
        captured.update(kwargs)
        return {"results": {}, "artifacts": {}, "meta": {}}

    monkeypatch.setattr(app_module, "run_analysis", fake_run_analysis)
    response = app_module.app.test_client().post(
        "/api/decode",
        data={
            "image": (BytesIO(b"image"), "carrier.png"),
            "analysisProfile": "light",
            "selectedTools": json.dumps(["stegcracker"]),
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 200
    assert captured["analysis_profile"] == "light"
    assert captured["selected_tools"] == ["stegcracker"]


def test_decode_endpoint_leaves_missing_selection_for_profile_defaults(monkeypatch):
    captured = {}

    def fake_run_analysis(_image, _filename, **kwargs):
        captured.update(kwargs)
        return {"results": {}, "artifacts": {}, "meta": {}}

    monkeypatch.setattr(app_module, "run_analysis", fake_run_analysis)
    response = app_module.app.test_client().post(
        "/api/decode",
        data={"image": (BytesIO(b"image"), "carrier.png"), "analysisProfile": "light"},
        content_type="multipart/form-data",
    )

    assert response.status_code == 200
    assert captured["selected_tools"] is None


def test_decode_upload_errors_use_carrier_language():
    client = app_module.app.test_client()

    missing = client.post("/api/decode", data={})
    empty = client.post(
        "/api/decode",
        data={"image": (BytesIO(b""), "carrier.bin")},
        content_type="multipart/form-data",
    )

    assert missing.status_code == 400
    assert missing.json["error"] == "Carrier file is required"
    assert empty.status_code == 400
    assert empty.json["error"] == "Carrier file is empty"

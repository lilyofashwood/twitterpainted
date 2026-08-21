from engine.analysis_profiles import DEFAULT_PROFILE, list_profiles, resolve_profile


def test_profiles_list_has_expected_ids():
    ids = [row["id"] for row in list_profiles()]
    assert ids == ["light", "quick", "balanced", "deep", "forensic"]
    assert DEFAULT_PROFILE == "light"


def test_light_profile_suggests_only_simple_lsb_and_accepts_legacy_simple_alias():
    light = resolve_profile(None)
    legacy = resolve_profile("simple")

    assert light.profile_id == "light"
    assert light.internal_tools == ("simple_lsb",)
    assert legacy is light


def test_profile_resolution_escalates_deep_and_manual_flags():
    deep_profile = resolve_profile("quick", deep_analysis=True, manual_tools=False)
    assert deep_profile.profile_id == "deep"

    forensic_profile = resolve_profile("balanced", deep_analysis=False, manual_tools=True)
    assert forensic_profile.profile_id == "forensic"

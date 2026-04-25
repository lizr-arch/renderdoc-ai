from rdc_analyzer.tools.ui_headless_smoke import _large_filter_check_passes, _pick_search_key


def test_pick_search_key_prefers_non_empty_name():
    assert _pick_search_key("  MainTex  ", "tex_001") == "MainTex"


def test_pick_search_key_falls_back_to_id_when_name_blank():
    assert _pick_search_key("   ", "  tex_001  ") == "tex_001"


def test_pick_search_key_handles_none_inputs():
    assert _pick_search_key(None, None, " shader_42 ") == "shader_42"


def test_pick_search_key_returns_empty_when_all_candidates_empty():
    assert _pick_search_key("  ", "", None) == ""


def test_large_filter_passes_when_large_textures_exist_and_are_visible():
    assert _large_filter_check_passes(large_candidate_count=2, visible_large_filter_count=1) is True


def test_large_filter_passes_when_capture_has_no_large_textures():
    assert _large_filter_check_passes(large_candidate_count=0, visible_large_filter_count=0) is True


def test_large_filter_fails_when_large_textures_are_hidden():
    assert _large_filter_check_passes(large_candidate_count=2, visible_large_filter_count=0) is False

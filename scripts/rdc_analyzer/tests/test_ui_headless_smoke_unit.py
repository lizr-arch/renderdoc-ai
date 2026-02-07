from rdc_analyzer.tools.ui_headless_smoke import _pick_search_key


def test_pick_search_key_prefers_non_empty_name():
    assert _pick_search_key("  MainTex  ", "tex_001") == "MainTex"


def test_pick_search_key_falls_back_to_id_when_name_blank():
    assert _pick_search_key("   ", "  tex_001  ") == "tex_001"


def test_pick_search_key_handles_none_inputs():
    assert _pick_search_key(None, None, " shader_42 ") == "shader_42"


def test_pick_search_key_returns_empty_when_all_candidates_empty():
    assert _pick_search_key("  ", "", None) == ""

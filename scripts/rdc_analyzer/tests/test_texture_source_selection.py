from rdc_analyzer.analyze_rdc import choose_texture_source


def test_choose_texture_source_prefers_manifest():
    manifest = [{"resource_id": 1}]
    replay = [{"resource_id": 2}]
    chunk = [{"resource_id": 3}]

    textures, source = choose_texture_source(manifest, replay, chunk)

    assert source == "manifest"
    assert textures == manifest


def test_choose_texture_source_prefers_replay_over_chunk():
    manifest = []
    replay = [{"resource_id": 2}]
    chunk = [{"resource_id": 3}]

    textures, source = choose_texture_source(manifest, replay, chunk)

    assert source == "replay_api"
    assert textures == replay


def test_choose_texture_source_fallback_chunk():
    textures, source = choose_texture_source([], [], [{"resource_id": 3}])

    assert source == "chunk_parse"
    assert textures == [{"resource_id": 3}]


def test_choose_texture_source_none():
    textures, source = choose_texture_source([], [], [])

    assert source == "none"
    assert textures == []

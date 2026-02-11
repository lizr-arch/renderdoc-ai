import importlib


def test_resolve_full_report_json_prefers_explicit(tmp_path):
    module = importlib.import_module("rdc_analyzer.analyze_rdc")
    rdc_path = tmp_path / "capture.rdc"
    rdc_path.write_text("rdc")
    explicit = tmp_path / "explicit.json"
    explicit.write_text("{}")

    assert module.resolve_full_report_json(str(rdc_path), str(explicit)) == str(explicit)


def test_resolve_full_report_json_finds_sidecar(tmp_path):
    module = importlib.import_module("rdc_analyzer.analyze_rdc")
    rdc_path = tmp_path / "capture.rdc"
    rdc_path.write_text("rdc")
    sidecar = tmp_path / "capture.json"
    sidecar.write_text("{}")

    assert module.resolve_full_report_json(str(rdc_path), None) == str(sidecar)


def test_resolve_full_report_json_finds_data_json(tmp_path):
    module = importlib.import_module("rdc_analyzer.analyze_rdc")
    rdc_path = tmp_path / "capture.rdc"
    rdc_path.write_text("rdc")
    data_json = tmp_path / "capture_data.json"
    data_json.write_text("{}")

    assert module.resolve_full_report_json(str(rdc_path), None) == str(data_json)


def test_normalize_full_report_json_keeps_object(tmp_path):
    module = importlib.import_module("rdc_analyzer.analyze_rdc")
    json_path = tmp_path / "capture_data.json"
    json_path.write_text("{}", encoding="utf-8")

    normalized = module.normalize_full_report_json(str(json_path))

    assert normalized == str(json_path)


def test_normalize_full_report_json_flattens_single_item_list(tmp_path):
    module = importlib.import_module("rdc_analyzer.analyze_rdc")
    json_path = tmp_path / "capture_data.json"
    json_path.write_text("[{\"events\": []}]", encoding="utf-8")

    normalized = module.normalize_full_report_json(str(json_path))

    assert normalized != str(json_path)
    normalized_path = tmp_path / "capture_data_single.json"
    assert normalized == str(normalized_path)
    assert normalized_path.exists()


def test_normalize_full_report_json_rejects_multi_item_list(tmp_path):
    module = importlib.import_module("rdc_analyzer.analyze_rdc")
    json_path = tmp_path / "capture_data.json"
    json_path.write_text("[{\"events\": []}, {\"events\": []}]", encoding="utf-8")

    import pytest

    with pytest.raises(ValueError):
        module.normalize_full_report_json(str(json_path))

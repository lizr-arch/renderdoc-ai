import importlib

import pytest

_generate_real_report = importlib.import_module("rdc_analyzer.generate_real_report")


def test_load_rdc_data_flattens_single_item_list(tmp_path):
    json_path = tmp_path / "capture_data.json"
    json_path.write_text('[{"events": []}]', encoding="utf-8")

    data = _generate_real_report.load_rdc_data(str(json_path))

    assert isinstance(data, dict)
    assert data.get("events") == []


def test_load_rdc_data_rejects_multi_item_list(tmp_path):
    json_path = tmp_path / "capture_data.json"
    json_path.write_text('[{"events": []}, {"events": []}]', encoding="utf-8")

    with pytest.raises(ValueError):
        _generate_real_report.load_rdc_data(str(json_path))

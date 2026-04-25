from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict


ROOT = Path(__file__).resolve().parents[3]
VALIDATOR_DIR = ROOT / "tools" / "eap_validator"
FIXTURES_DIR = VALIDATOR_DIR / "fixtures"
GOLDEN_DIR = FIXTURES_DIR / "golden"
if str(VALIDATOR_DIR) not in sys.path:
    sys.path.insert(0, str(VALIDATOR_DIR))

import eap_validator  # type: ignore


def _load_golden(name: str) -> Dict[str, Any]:
    path = GOLDEN_DIR / f"{name}.validator.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _normalized_validation_result(sidecar_name: str) -> Dict[str, Any]:
    sidecar_path = FIXTURES_DIR / f"{sidecar_name}.rmeta.json"
    result = eap_validator.validate_sidecar(str(sidecar_path), allowlist_dirs=[str(FIXTURES_DIR)])
    normalized = json.loads(json.dumps(result, sort_keys=True))
    if normalized.get("sidecar"):
        normalized["sidecar"]["path"] = "<FIXTURE_PATH>"
    if normalized.get("error"):
        normalized["error"]["path"] = "<FIXTURE_PATH>"
    return normalized


def test_valid_minimal_fixture_matches_golden_summary():
    result = _normalized_validation_result("valid_minimal")

    assert result == _load_golden("valid_minimal")


def test_valid_fullish_fixture_matches_golden_summary():
    result = _normalized_validation_result("valid_fullish")

    assert result == _load_golden("valid_fullish")


def test_invalid_wrong_schema_fixture_matches_golden_error():
    result = _normalized_validation_result("invalid_wrong_schema")

    assert result == _load_golden("invalid_wrong_schema")

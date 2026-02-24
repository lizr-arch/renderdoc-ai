from pathlib import Path


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_embedded_python_36_compatibility():
    root = Path(__file__).resolve().parents[1]
    targets = [
        root / "bridge" / "analysis_to_bundle.py",
        root / "report_from_analysis.py",
    ]

    for target in targets:
        text = _read_text(target)
        assert "from __future__ import annotations" not in text
        assert "set[" not in text

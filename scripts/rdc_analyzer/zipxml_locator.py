#!/usr/bin/env python3
"""Locate ZIP+XML sidecar pairs for a capture.

This helper focuses on practical RenderDoc export naming patterns:
- <capture>.zip + <capture>.zip.xml
- <capture>.zip + <capture>.xml
- <capture>_export.zip + <capture>.xml
- frame.zip + frame.zip.xml
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional, Sequence, Tuple


def _dedupe_paths(items: Sequence[Path]) -> List[Path]:
    seen = set()
    out: List[Path] = []
    for item in items:
        key = str(item).lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def _candidate_zip_paths(capture_path: Path, zip_hint: Optional[Path]) -> List[Path]:
    parent = capture_path.parent
    stem = capture_path.stem

    candidates: List[Path] = []
    if zip_hint is not None:
        candidates.append(Path(zip_hint))

    # Common deterministic names first.
    candidates.extend(
        [
            parent / f"{stem}.zip",
            parent / f"{stem}_export.zip",
            parent / "frame.zip",
        ]
    )

    # Then nearby zips containing stem, then any zip as the last fallback.
    candidates.extend(sorted(parent.glob(f"{stem}*.zip")))
    candidates.extend(sorted(parent.glob("*.zip")))

    return _dedupe_paths(candidates)


def _candidate_xml_paths(zip_path: Path, capture_stem: str, xml_hint: Optional[Path]) -> List[Path]:
    parent = zip_path.parent
    zip_name = zip_path.name

    candidates: List[Path] = []
    if xml_hint is not None:
        candidates.append(Path(xml_hint))

    if zip_name.endswith(".zip"):
        bare = zip_name[:-len(".zip")]
        candidates.extend(
            [
                parent / f"{bare}.zip.xml",
                parent / f"{bare}.xml",
            ]
        )

    candidates.extend(
        [
            zip_path.with_suffix(".zip.xml"),
            zip_path.with_suffix(".xml"),
            parent / f"{capture_stem}.zip.xml",
            parent / f"{capture_stem}.xml",
        ]
    )

    return _dedupe_paths(candidates)


def find_zipxml_sidecar(
    capture_path: Path,
    zip_hint: Optional[Path] = None,
    xml_hint: Optional[Path] = None,
) -> Tuple[Optional[Path], Optional[Path], List[str]]:
    """Find a usable ZIP+XML sidecar pair for a capture.

    Returns:
        (zip_path, xml_path, tried_pairs)
    """

    cap = Path(capture_path)
    tried_pairs: List[str] = []

    if zip_hint is not None and xml_hint is not None:
        if Path(zip_hint).exists() and Path(xml_hint).exists():
            return Path(zip_hint), Path(xml_hint), tried_pairs

    for zip_path in _candidate_zip_paths(cap, zip_hint):
        if not zip_path.exists():
            continue

        for xml_path in _candidate_xml_paths(zip_path, cap.stem, xml_hint):
            tried_pairs.append(f"{zip_path.name} + {xml_path.name}")
            if xml_path.exists():
                return zip_path, xml_path, tried_pairs

    return None, None, tried_pairs

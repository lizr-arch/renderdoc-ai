from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Dict, Iterable


def _normalize_base_name(stem: str) -> str:
    if stem.endswith("_report_xml"):
        return stem[:-11]
    if stem.endswith("_report"):
        return stem[:-7]
    return stem


def compute_capture_id(paths: Iterable[str]) -> str:
    hasher = hashlib.sha256()
    for path_str in paths:
        if not path_str:
            continue
        path = Path(path_str)
        hasher.update(path_str.encode("utf-8"))
        if path.exists() and path.is_file():
            with path.open("rb") as handle:
                while True:
                    chunk = handle.read(4 * 1024 * 1024)
                    if not chunk:
                        break
                    hasher.update(chunk)
    return f"sha256:{hasher.hexdigest()}"


def default_report_links(output_path: Path, kind: str) -> Dict[str, str]:
    base = _normalize_base_name(output_path.stem)
    links = {
        "v3": f"{base}_report.html",
        "texture": f"{base}_report_xml.html",
    }
    if kind == "texture":
        links["texture"] = output_path.name
    if kind == "v3":
        links["v3"] = output_path.name
    return links


def write_report_links(output_dir: Path, links: Dict[str, str]) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "report_links.json"
    path.write_text(json.dumps(links, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def write_manifest(output_dir: Path, manifest: Dict[str, object]) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "rdc_manifest.json"
    path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def write_manifest_bundle(output_path: Path, manifest: Dict[str, object], links: Dict[str, str]) -> None:
    output_dir = output_path.parent
    write_report_links(output_dir, links)
    write_manifest(output_dir, manifest)

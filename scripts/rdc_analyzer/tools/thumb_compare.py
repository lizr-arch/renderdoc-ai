#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""thumb_compare.py

Generate BEFORE/AFTER thumbnail comparisons for Vulkan ZIP+XML exports.

Context
- BEFORE: force eResDeviceMemory + vkBindImageMemory.offset (old path that can show stripes/wrong visuals)
- AFTER:  force eResImage (per-image initial contents, offset=0) (new preferred path)

This tool helps humans visually verify that the eResImage-first policy produces more readable thumbnails.

Example
  py -3 scripts/rdc_analyzer/tools/thumb_compare.py \
    --xml "D:\\backup\\endfield_report\\EndfieldTBeta2_2025.12.18_14.36_frame42231.zip.xml" \
    --zip "D:\\backup\\endfield_report\\EndfieldTBeta2_2025.12.18_14.36_frame42231.zip" \
    -o "docs/analysis/codex_rdc_analyzer/ui_smoke_artifacts/thumb_compare_endfield" \
    --top 20 --size 128
"""

from __future__ import annotations

import argparse
import base64
import io
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple


# Ensure scripts/rdc_analyzer is importable when running from repo root.
RDC_ANALYZER_ROOT = Path(__file__).resolve().parents[1]
if str(RDC_ANALYZER_ROOT) not in sys.path:
    sys.path.insert(0, str(RDC_ANALYZER_ROOT))


try:
    from PIL import Image, ImageChops, ImageDraw, ImageOps, ImageStat
except Exception as exc:  # pragma: no cover
    raise SystemExit(f"Pillow unavailable: {exc}")


from thumbnail_generator import InitialContents, MemoryBinding, ThumbnailGenerator


@dataclass
class PairCandidate:
    score: float
    image_id: int
    name: str
    fmt: str
    dims: Tuple[int, int]
    offset: int
    before_png: bytes
    after_png: bytes


def _is_image_ic(ic: InitialContents) -> bool:
    return "IMAGE" in (ic.resource_type or "").upper()


def _is_memory_ic(ic: InitialContents) -> bool:
    return "MEMORY" in (ic.resource_type or "").upper()


def _sanitize_filename(text: str, limit: int = 60) -> str:
    s = (text or "").strip()
    if not s:
        return "tex"
    s = re.sub(r"[^0-9A-Za-z._-]+", "_", s)
    s = s.strip("._-")
    return (s[:limit] or "tex")


def _decode_data_url_png(data_url: str) -> bytes:
    if not data_url.startswith("data:image"):
        raise ValueError("Not a data URL")
    if "," not in data_url:
        raise ValueError("Malformed data URL")
    b64 = data_url.split(",", 1)[1]
    return base64.b64decode(b64)


def _png_to_rgba(png: bytes) -> Image.Image:
    return Image.open(io.BytesIO(png)).convert("RGBA")


def _fit_to_square(img: Image.Image, size: int) -> Image.Image:
    # Pad to a stable size for diff/scoring.
    return ImageOps.pad(
        img,
        (size, size),
        method=Image.Resampling.LANCZOS,
        color=(0, 0, 0, 255),
        centering=(0.5, 0.5),
    )


def _diff_score(before: Image.Image, after: Image.Image, size: int) -> float:
    a = _fit_to_square(before, size)
    b = _fit_to_square(after, size)
    diff = ImageChops.difference(a, b)
    stat = ImageStat.Stat(diff)
    # Sum of per-channel mean absolute diffs. Range [0, 1020].
    return float(sum(stat.mean))


def _load_names_from_textures_data(path: Path) -> Dict[int, str]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}

    mapping: Dict[int, str] = {}
    if isinstance(data, list):
        for item in data:
            if not isinstance(item, dict):
                continue
            rid = item.get("id")
            name = item.get("display_name") or item.get("name") or ""
            try:
                rid_int = int(rid)
            except Exception:
                continue
            if isinstance(name, str) and name:
                mapping[rid_int] = name
    return mapping


def _write_index_tsv(out_dir: Path, rows: Sequence[Tuple[str, ...]]) -> None:
    out = out_dir / "index.tsv"
    header = (
        "rank",
        "image_id",
        "name",
        "format",
        "width",
        "height",
        "offset",
        "score",
        "before_png",
        "after_png",
        "pair_png",
    )
    lines = ["\t".join(header)]
    lines.extend("\t".join(row) for row in rows)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _make_pair_image(
    before: Image.Image,
    after: Image.Image,
    label: str,
    size: int,
    pad: int = 16,
    header_h: int = 34,
) -> Image.Image:
    before_sq = _fit_to_square(before, size)
    after_sq = _fit_to_square(after, size)

    w = pad + size + pad + size + pad
    h = pad + header_h + size + pad

    bg = (20, 24, 30)
    sheet = Image.new("RGB", (w, h), bg)
    draw = ImageDraw.Draw(sheet)

    # Header text
    draw.text((pad, pad), label, fill=(224, 232, 240))

    y0 = pad + header_h
    x_before = pad
    x_after = pad + size + pad

    sheet.paste(before_sq.convert("RGB"), (x_before, y0))
    sheet.paste(after_sq.convert("RGB"), (x_after, y0))

    # Side tags
    draw.text((x_before + 4, y0 + 4), "BEFORE (memory)", fill=(180, 150, 150))
    draw.text((x_after + 4, y0 + 4), "AFTER (image)", fill=(150, 190, 150))

    # Border
    draw.rectangle([1, 1, w - 2, h - 2], outline=(70, 78, 90), width=1)

    return sheet


def _make_contact_sheet(pairs: Sequence[Image.Image], out_path: Path, pad: int = 16) -> None:
    if not pairs:
        return

    # Stack vertically.
    w = max(im.width for im in pairs)
    h = pad + sum(im.height + pad for im in pairs)
    bg = (16, 18, 22)
    sheet = Image.new("RGB", (w + pad * 2, h), bg)

    y = pad
    for im in pairs:
        x = pad + (w - im.width) // 2
        sheet.paste(im, (x, y))
        y += im.height + pad

    out_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out_path)


def _write_html_index(out_dir: Path, rows: Sequence[Tuple[str, str, str, str]]) -> None:
    # rows: (label, before_name, after_name, pair_name)
    html = [
        "<!doctype html>",
        "<html>",
        "<head>",
        "  <meta charset='utf-8'>",
        "  <meta name='viewport' content='width=device-width, initial-scale=1'>",
        "  <title>Thumbnail BEFORE/AFTER Compare</title>",
        "  <style>",
        "    body { font-family: system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif; margin: 16px; background: #11141a; color: #e6eef8; }",
        "    .card { border: 1px solid #2a3340; border-radius: 10px; padding: 12px; margin: 12px 0; background: #141a22; }",
        "    .label { font-size: 14px; margin-bottom: 8px; opacity: 0.95; }",
        "    .row { display: flex; gap: 12px; flex-wrap: wrap; align-items: flex-start; }",
        "    .col { display: flex; flex-direction: column; gap: 6px; }",
        "    .tag { font-size: 12px; opacity: 0.8; }",
        "    img { image-rendering: auto; border: 1px solid #2a3340; border-radius: 6px; background: #0c0f14; }",
        "  </style>",
        "</head>",
        "<body>",
        "  <h1 style='margin: 0 0 8px 0;'>Thumbnail BEFORE/AFTER Compare</h1>",
        "  <p style='margin: 0 0 12px 0; opacity: 0.85;'>Left: BEFORE (memory). Right: AFTER (image). Click to zoom.</p>",
    ]

    for label, before_name, after_name, pair_name in rows:
        html.extend(
            [
                "  <div class='card'>",
                f"    <div class='label'>{label}</div>",
                "    <div class='row'>",
                "      <div class='col'>",
                "        <div class='tag'>BEFORE (memory)</div>",
                f"        <a href='{before_name}' target='_blank'><img src='{before_name}'></a>",
                "      </div>",
                "      <div class='col'>",
                "        <div class='tag'>AFTER (image)</div>",
                f"        <a href='{after_name}' target='_blank'><img src='{after_name}'></a>",
                "      </div>",
                "      <div class='col'>",
                "        <div class='tag'>PAIR</div>",
                f"        <a href='{pair_name}' target='_blank'><img src='{pair_name}'></a>",
                "      </div>",
                "    </div>",
                "  </div>",
            ]
        )

    html.extend(["</body>", "</html>"])
    (out_dir / "index.html").write_text("\n".join(html) + "\n", encoding="utf-8")


def run(
    xml_path: Path,
    zip_path: Optional[Path],
    out_dir: Path,
    top_n: int,
    size: int,
    max_candidates: int,
    candidate_order: str,
    names_from: Optional[Path],
    write_html: bool,
    verbose: bool,
) -> int:
    xml_path = xml_path.resolve()
    if zip_path is not None:
        zip_path = zip_path.resolve()

    out_dir = out_dir.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    # Optional names mapping for nicer labels.
    name_map: Dict[int, str] = {}
    if names_from is not None:
        name_map = _load_names_from_textures_data(names_from)
    else:
        # Best-effort: if XML sits next to a previously generated report, reuse its textures_data.json.
        auto = xml_path.parent / "textures_data.json"
        name_map = _load_names_from_textures_data(auto)

    gen = ThumbnailGenerator(xml_path, zip_path)
    if not gen.parse():
        print("[ERROR] Failed to parse XML")
        return 2

    image_to_binding = {b.image_id: b for b in gen.bindings}

    # Candidate selection: image has eResImage AND its bound memory has eResDeviceMemory.
    candidates: List[int] = []
    for img_id in gen.images.keys():
        ic_img = gen.initial_contents.get(img_id)
        if not ic_img or not _is_image_ic(ic_img):
            continue
        binding = image_to_binding.get(img_id)
        if not binding:
            continue
        ic_mem = gen.initial_contents.get(binding.memory_id)
        if not ic_mem or not _is_memory_ic(ic_mem):
            continue
        candidates.append(img_id)

    # Candidate ordering matters for runtime.
    # - area_desc: larger textures first (more detail, slower)
    # - area_asc: smaller textures first (much faster for visual smoke runs)
    reverse = candidate_order != "area_asc"
    candidates.sort(key=lambda i: gen.images[i].width * gen.images[i].height, reverse=reverse)
    if max_candidates > 0:
        candidates = candidates[:max_candidates]

    if verbose:
        print(f"[INFO] Images parsed: {len(gen.images)}")
        print(f"[INFO] Bindings parsed: {len(gen.bindings)}")
        print(f"[INFO] InitialContents parsed: {len(gen.initial_contents)}")
        print(f"[INFO] Candidates (image+memory IC): {len(candidates)}")

    # Keep only top N by diff score.
    import heapq

    heap: List[Tuple[float, int, PairCandidate]] = []
    seq = 0

    for img_id in candidates:
        img = gen.images[img_id]
        binding = image_to_binding[img_id]
        ic_img = gen.initial_contents[img_id]
        ic_mem = gen.initial_contents[binding.memory_id]

        before = gen.generate_thumbnail(img, binding, ic_mem, max_size=size)
        after = gen.generate_thumbnail(img, MemoryBinding(img_id, img_id, 0), ic_img, max_size=size)

        if not (before.success and after.success):
            if verbose:
                print(f"[SKIP] id={img_id} before={before.success} after={after.success}")
            continue

        try:
            before_png = _decode_data_url_png(before.base64_data)
            after_png = _decode_data_url_png(after.base64_data)
            before_img = _png_to_rgba(before_png)
            after_img = _png_to_rgba(after_png)
            score = _diff_score(before_img, after_img, size)
        except Exception as exc:
            if verbose:
                print(f"[SKIP] id={img_id} decode/diff failed: {exc}")
            continue

        name = name_map.get(img_id, "")
        cand = PairCandidate(
            score=score,
            image_id=img_id,
            name=name,
            fmt=img.format,
            dims=(img.width, img.height),
            offset=int(binding.offset),
            before_png=before_png,
            after_png=after_png,
        )

        seq += 1
        item = (score, seq, cand)
        if top_n <= 0:
            heapq.heappush(heap, item)
        elif len(heap) < top_n:
            heapq.heappush(heap, item)
        else:
            # Replace smallest if better.
            if score > heap[0][0]:
                heapq.heapreplace(heap, item)

    selected = [t[2] for t in sorted(heap, key=lambda x: x[0], reverse=True)]

    if not selected:
        print("[WARN] No pairs generated. Candidate list may be empty.")
        return 3

    rows_tsv: List[Tuple[str, ...]] = []
    html_rows: List[Tuple[str, str, str, str]] = []
    pair_images: List[Image.Image] = []

    for rank, cand in enumerate(selected, 1):
        safe_name = _sanitize_filename(cand.name or f"id{cand.image_id}")
        before_name = f"{rank:02d}_id{cand.image_id}_{safe_name}_BEFORE_memory.png"
        after_name = f"{rank:02d}_id{cand.image_id}_{safe_name}_AFTER_image.png"
        pair_name = f"{rank:02d}_id{cand.image_id}_{safe_name}_PAIR.png"

        before_path = out_dir / before_name
        after_path = out_dir / after_name
        pair_path = out_dir / pair_name

        before_path.write_bytes(cand.before_png)
        after_path.write_bytes(cand.after_png)

        before_img = _png_to_rgba(cand.before_png)
        after_img = _png_to_rgba(cand.after_png)

        label = (
            f"{rank:02d} | ID {cand.image_id}"
            + (f" | {cand.name}" if cand.name else "")
            + f" | {cand.fmt} | {cand.dims[0]}x{cand.dims[1]} | off={cand.offset} | score={cand.score:.1f}"
        )

        pair_img = _make_pair_image(before_img, after_img, label=label, size=size)
        pair_img.save(pair_path)
        pair_images.append(pair_img)

        rows_tsv.append(
            (
                str(rank),
                str(cand.image_id),
                cand.name or "",
                cand.fmt,
                str(cand.dims[0]),
                str(cand.dims[1]),
                str(cand.offset),
                f"{cand.score:.3f}",
                before_name,
                after_name,
                pair_name,
            )
        )
        html_rows.append((label, before_name, after_name, pair_name))

    _write_index_tsv(out_dir, rows_tsv)

    sheet_path = out_dir / "contact_sheet_pairs.png"
    _make_contact_sheet(pair_images, sheet_path)

    if write_html:
        _write_html_index(out_dir, html_rows)

    print("[OK] Generated pairs:", len(selected))
    print("[OK] Output:", out_dir)
    print("[OK] Contact sheet:", sheet_path)
    if write_html:
        print("[OK] HTML index:", out_dir / "index.html")

    return 0


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Generate BEFORE/AFTER thumbnail comparison artifacts")
    ap.add_argument("--xml", required=True, type=Path, help="Path to zip.xml exported by renderdoccmd convert -c zip.xml")
    ap.add_argument("--zip", type=Path, default=None, help="Path to zip exported by renderdoccmd convert -c zip.xml")
    ap.add_argument("-o", "--out", required=True, type=Path, help="Output directory")
    ap.add_argument("--top", type=int, default=20, help="How many pairs to keep (top by diff score)")
    ap.add_argument("--size", type=int, default=128, help="Thumbnail max size (square) used for diff & display")
    ap.add_argument(
        "--max-candidates",
        type=int,
        default=200,
        help="Max candidate images to evaluate (sorted by area first). 0 = no limit",
    )
    ap.add_argument(
        "--order",
        choices=["area_desc", "area_asc"],
        default="area_desc",
        help="Candidate evaluation order. area_asc is much faster for visual smoke runs.",
    )
    ap.add_argument(
        "--names-from",
        type=Path,
        default=None,
        help="Optional textures_data.json path to map id->name for labels",
    )
    ap.add_argument("--no-html", action="store_true", help="Do not emit index.html")
    ap.add_argument("-v", "--verbose", action="store_true", help="Verbose logging")

    args = ap.parse_args(argv)

    return run(
        xml_path=args.xml,
        zip_path=args.zip,
        out_dir=args.out,
        top_n=args.top,
        size=args.size,
        max_candidates=args.max_candidates,
        candidate_order=args.order,
        names_from=args.names_from,
        write_html=not args.no_html,
        verbose=args.verbose,
    )


if __name__ == "__main__":
    raise SystemExit(main())

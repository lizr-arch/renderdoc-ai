#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
UI Headless Smoke Tool
======================

对 bundle 报告页进行无人工自测：
- 自动打开 textures.html / shaders.html
- 自动执行搜索/筛选/选中等交互
- 自动判断关键可用性指标
- 自动输出截图与 JSON/Markdown 报告

默认面向本地 file:// 报告，无需启动 Web 服务。
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Sequence, Tuple


@dataclass
class ViewportResult:
    viewport: str
    textures_total: int
    textures_visible_before: int
    textures_visible_after_search: int
    textures_visible_large_filter: int
    textures_selected_prop_name: str
    textures_selected_prop_id: str
    textures_list_scroll_height: int
    textures_list_client_height: int
    textures_properties_scroll_height: int
    textures_properties_client_height: int
    textures_grid_mode: bool
    shaders_total: int
    shaders_visible_before: int
    shaders_visible_after_search: int
    shaders_list_scroll_height: int
    shaders_list_client_height: int
    shaders_buttons_overlap: bool
    checks: Dict[str, bool]
    passed: bool


def parse_viewports(raw: str) -> List[Tuple[int, int]]:
    viewports: List[Tuple[int, int]] = []
    for chunk in (part.strip() for part in raw.split(",")):
        if not chunk:
            continue
        if "x" not in chunk:
            raise ValueError(f"Invalid viewport: {chunk}")
        w_str, h_str = chunk.lower().split("x", 1)
        w = int(w_str)
        h = int(h_str)
        if w <= 0 or h <= 0:
            raise ValueError(f"Viewport must be positive: {chunk}")
        viewports.append((w, h))
    if not viewports:
        raise ValueError("No viewport provided")
    return viewports


def _visible_count(page, selector: str) -> int:
    return page.evaluate(
        """
        (selector) => Array.from(document.querySelectorAll(selector))
          .filter(el => !el.classList.contains('hidden') && getComputedStyle(el).display !== 'none')
          .length
        """,
        selector,
    )


def _save_page_shot(page, out_dir: Path, name: str) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(out_dir / name), full_page=False)


def _pick_search_key(*candidates: str) -> str:
    for candidate in candidates:
        value = (candidate or '').strip()
        if value:
            return value
    return ''


def run_smoke(
    report_dir: Path,
    out_dir: Path,
    viewports: Sequence[Tuple[int, int]],
    capture_screenshots: bool = True,
) -> Dict[str, object]:
    try:
        from playwright.sync_api import sync_playwright
    except Exception as exc:  # pragma: no cover
        raise RuntimeError(f"Playwright unavailable: {exc}") from exc

    textures_path = (report_dir / "textures.html").resolve()
    shaders_path = (report_dir / "shaders.html").resolve()
    if not textures_path.exists() or not shaders_path.exists():
        raise FileNotFoundError(
            f"Missing report pages: {textures_path if not textures_path.exists() else ''} "
            f"{shaders_path if not shaders_path.exists() else ''}".strip()
        )

    textures_url = textures_path.as_uri()
    shaders_url = shaders_path.as_uri()

    results: List[ViewportResult] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        for width, height in viewports:
            page.set_viewport_size({"width": width, "height": height})
            vp_tag = f"{width}x{height}"

            # Textures page checks
            page.goto(textures_url, wait_until="domcontentloaded")
            page.wait_for_selector(".texture-item", timeout=15000)
            if capture_screenshots:
                _save_page_shot(page, out_dir, f"textures_{vp_tag}_initial.png")

            textures_total = page.locator(".texture-item").count()
            textures_visible_before = _visible_count(page, ".texture-item")

            first_texture_name = page.locator(".texture-item").first.get_attribute("data-name") or ""
            first_texture_id = page.locator(".texture-item").first.get_attribute("data-id") or ""
            texture_search_key = _pick_search_key(first_texture_name, first_texture_id)
            if texture_search_key:
                page.fill("#textureSearch", texture_search_key)
            page.wait_for_timeout(120)
            textures_visible_after_search = _visible_count(page, ".texture-item")
            if capture_screenshots:
                _save_page_shot(page, out_dir, f"textures_{vp_tag}_search.png")

            page.fill("#textureSearch", "")
            page.click(".filter-chip[data-filter='large']")
            page.wait_for_timeout(120)
            textures_visible_large_filter = _visible_count(page, ".texture-item")

            page.click(".filter-chip[data-filter='all']")
            page.wait_for_timeout(80)
            page.locator(".texture-item").first.click()
            page.wait_for_timeout(80)

            textures_selected_prop_name = page.locator("#propName").inner_text().strip()
            textures_selected_prop_id = page.locator("#propId").inner_text().strip()

            list_scroll = page.evaluate(
                """
                () => {
                    const el = document.getElementById('textureList');
                    return {scrollHeight: el.scrollHeight, clientHeight: el.clientHeight};
                }
                """
            )
            properties_scroll = page.evaluate(
                """
                () => {
                    const el = document.getElementById('propertiesPanel');
                    return {scrollHeight: el.scrollHeight, clientHeight: el.clientHeight};
                }
                """
            )

            page.click("#gridViewBtn")
            page.wait_for_timeout(80)
            textures_grid_mode = page.evaluate(
                "() => document.body.classList.contains('view-mode-grid')"
            )
            if capture_screenshots:
                _save_page_shot(page, out_dir, f"textures_{vp_tag}_selected.png")

            # Shaders page checks
            page.goto(shaders_url, wait_until="domcontentloaded")
            page.wait_for_selector(".shader-item", timeout=15000)
            if capture_screenshots:
                _save_page_shot(page, out_dir, f"shaders_{vp_tag}_initial.png")

            shaders_visible_before = _visible_count(page, ".shader-item")
            shaders_total = page.evaluate(
                """
                () => {
                    const text = (document.getElementById('shaderStats')?.textContent || '0').trim();
                    const parsed = parseInt(text.replace(/\D/g, ''), 10);
                    return Number.isFinite(parsed) ? parsed : 0;
                }
                """
            )
            shaders_list_scroll = page.evaluate(
                """
                () => {
                    const el = document.getElementById('shaderList');
                    return {scrollHeight: el.scrollHeight, clientHeight: el.clientHeight};
                }
                """
            )
            shaders_pager_present = page.locator("#shaderPager").count() > 0

            first_shader_id = page.locator(".shader-item").first.get_attribute("data-id") or ""
            first_shader_name = page.locator(".shader-item").first.get_attribute("data-name") or ""
            search_key = _pick_search_key(first_shader_name, first_shader_id)
            if search_key:
                page.fill("#shaderSearch", search_key)
            page.wait_for_timeout(120)
            shaders_visible_after_search = _visible_count(page, ".shader-item")
            if capture_screenshots:
                _save_page_shot(page, out_dir, f"shaders_{vp_tag}_search.png")

            # 检查“非首屏 Shader 是否可被搜索到”，验证搜索作用于全量数据
            offpage_search_effective = True
            needs_offpage_check = shaders_total > shaders_visible_before
            if needs_offpage_check and shaders_pager_present:
                page.fill("#shaderSearch", "")
                page.wait_for_timeout(80)
                next_btn = page.locator("#shaderPager .pager-btn").nth(1)
                if next_btn.count() > 0 and next_btn.is_enabled():
                    next_btn.click()
                    page.wait_for_timeout(120)
                    offpage_id = page.locator(".shader-item").first.get_attribute("data-id") or ""
                    offpage_name = page.locator(".shader-item").first.get_attribute("data-name") or ""
                    offpage_search_key = _pick_search_key(offpage_name, offpage_id)
                    if offpage_search_key:
                        page.fill("#shaderSearch", offpage_search_key)
                        page.wait_for_timeout(120)
                        offpage_visible = _visible_count(page, ".shader-item")
                        offpage_hits = 0
                        if offpage_id:
                            offpage_hits = page.locator(f'.shader-item[data-id="{offpage_id}"]').count()
                        offpage_search_effective = offpage_visible > 0 and offpage_hits > 0
                    else:
                        offpage_search_effective = False
                else:
                    offpage_search_effective = False

                page.fill("#shaderSearch", "")
                page.wait_for_timeout(80)

            hlsl_box = page.locator("#hlslBtn").bounding_box()
            ai_box = page.locator("#aiOptimizeBtn").bounding_box()
            overlap = False
            if hlsl_box and ai_box:
                overlap = not (
                    hlsl_box["x"] + hlsl_box["width"] <= ai_box["x"]
                    or ai_box["x"] + ai_box["width"] <= hlsl_box["x"]
                    or hlsl_box["y"] + hlsl_box["height"] <= ai_box["y"]
                    or ai_box["y"] + ai_box["height"] <= hlsl_box["y"]
                )

            checks = {
                "textures_has_items": textures_total > 0,
                "textures_search_effective": 0 < textures_visible_after_search <= textures_visible_before,
                "textures_large_filter_effective": textures_visible_large_filter > 0,
                "textures_list_scrollable": list_scroll["scrollHeight"] > list_scroll["clientHeight"],
                "textures_selection_updates_property": textures_selected_prop_id not in ("", "-"),
                "textures_grid_toggle_works": bool(textures_grid_mode),
                "shaders_has_items": shaders_total > 0,
                "shaders_search_effective": 0 < shaders_visible_after_search <= shaders_visible_before,
                "shaders_list_scrollable": shaders_list_scroll["scrollHeight"] > shaders_list_scroll["clientHeight"],
                "shaders_pager_present": bool(shaders_pager_present),
                "shaders_offpage_search_effective": bool(offpage_search_effective),
                "shader_buttons_no_overlap": not overlap,
            }
            passed = all(checks.values())

            results.append(
                ViewportResult(
                    viewport=vp_tag,
                    textures_total=textures_total,
                    textures_visible_before=textures_visible_before,
                    textures_visible_after_search=textures_visible_after_search,
                    textures_visible_large_filter=textures_visible_large_filter,
                    textures_selected_prop_name=textures_selected_prop_name,
                    textures_selected_prop_id=textures_selected_prop_id,
                    textures_list_scroll_height=int(list_scroll["scrollHeight"]),
                    textures_list_client_height=int(list_scroll["clientHeight"]),
                    textures_properties_scroll_height=int(properties_scroll["scrollHeight"]),
                    textures_properties_client_height=int(properties_scroll["clientHeight"]),
                    textures_grid_mode=bool(textures_grid_mode),
                    shaders_total=shaders_total,
                    shaders_visible_before=shaders_visible_before,
                    shaders_visible_after_search=shaders_visible_after_search,
                    shaders_list_scroll_height=int(shaders_list_scroll["scrollHeight"]),
                    shaders_list_client_height=int(shaders_list_scroll["clientHeight"]),
                    shaders_buttons_overlap=bool(overlap),
                    checks=checks,
                    passed=passed,
                )
            )

        browser.close()

    overall_pass = all(item.passed for item in results)
    return {
        "report_dir": str(report_dir),
        "out_dir": str(out_dir),
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "overall_pass": overall_pass,
        "viewports": [asdict(item) for item in results],
    }


def write_reports(result: Dict[str, object], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)

    json_path = out_dir / "ui_smoke_result.json"
    json_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    md_lines = [
        "# UI Headless Smoke Result",
        "",
        f"- report_dir: `{result['report_dir']}`",
        f"- out_dir: `{result['out_dir']}`",
        f"- timestamp: `{result['timestamp']}`",
        f"- overall_pass: `{result['overall_pass']}`",
        "",
        "## Viewports",
        "",
    ]

    for vp in result["viewports"]:  # type: ignore[index]
        md_lines.append(f"### {vp['viewport']}")
        md_lines.append("")
        md_lines.append(f"- textures: total={vp['textures_total']}, visible_after_search={vp['textures_visible_after_search']}, large_filter={vp['textures_visible_large_filter']}")
        md_lines.append(f"- shaders: total={vp['shaders_total']}, visible_after_search={vp['shaders_visible_after_search']}")
        md_lines.append(f"- shader_buttons_overlap={vp['shaders_buttons_overlap']}")
        md_lines.append("- checks:")
        for key, ok in vp["checks"].items():
            md_lines.append(f"  - `{key}`: {'✅' if ok else '❌'}")
        md_lines.append("")

    md_path = out_dir / "ui_smoke_result.md"
    md_path.write_text("\n".join(md_lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Headless UI smoke + screenshot for bundle report")
    parser.add_argument(
        "--report-dir",
        type=Path,
        default=Path(r"D:\backup\endfield_report"),
        help="bundle report 目录（包含 textures.html / shaders.html）",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=None,
        help="输出目录（默认 docs/analysis/codex_rdc_analyzer/ui_smoke_artifacts/<timestamp>）",
    )
    parser.add_argument(
        "--viewports",
        type=str,
        default="1366x768,1536x864,1920x1080",
        help="逗号分隔视口列表，例如 1366x768,1920x1080",
    )
    parser.add_argument(
        "--no-screenshots",
        action="store_true",
        help="仅跑检查，不保存截图",
    )
    parser.add_argument(
        "--no-fail",
        action="store_true",
        help="即使检查失败也返回 0",
    )
    args = parser.parse_args()

    viewports = parse_viewports(args.viewports)

    if args.out_dir is None:
        stamp = datetime.now().strftime("%Y-%m-%d-%H%M%S")
        out_dir = Path("docs/analysis/codex_rdc_analyzer/ui_smoke_artifacts") / stamp
    else:
        out_dir = args.out_dir

    result = run_smoke(
        report_dir=args.report_dir,
        out_dir=out_dir,
        viewports=viewports,
        capture_screenshots=(not args.no_screenshots),
    )
    write_reports(result, out_dir)

    print(f"[UI Smoke] out_dir: {out_dir}")
    print(f"[UI Smoke] overall_pass: {result['overall_pass']}")

    if result["overall_pass"] or args.no_fail:
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bundle 报告资源验证
===================

验证 textures.html / shaders.html 中关键渲染字段是否存在，
避免缩略图与源码被错误处理导致页面空白。
"""

import sys
from pathlib import Path

# 添加 scripts/rdc_analyzer 到路径
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from report_bundle_generator import ReportBundleGenerator  # noqa: E402


def test_texture_thumbnail_path(tmp_path):
    gen = ReportBundleGenerator(output_dir=tmp_path, capture_name="t.rdc")
    gen.set_textures([
        {
            "id": "1",
            "name": "Tex",
            "width": 1,
            "height": 1,
            "thumbnail": "textures/tex_1_1x1.png",
        }
    ])
    outputs = gen.generate_all()
    html = Path(outputs["textures"]).read_text(encoding="utf-8")
    assert "textures/tex_1_1x1.png" in html


def test_map_exported_textures_sets_thumbnail(tmp_path):
    from analyze_xml_report import map_exported_textures

    textures = [
        {
            "id": "1",
            "name": "Tex",
            "width": 4,
            "height": 8,
            "thumbnail": "",
        }
    ]
    export_dir = tmp_path / "textures"
    export_dir.mkdir(parents=True, exist_ok=True)
    (export_dir / "tex_1_4x8.png").write_bytes(b"fake")

    updated = map_exported_textures(textures, export_dir)
    assert updated == 1
    assert textures[0]["thumbnail"] == "textures/tex_1_4x8.png"


def test_load_texture_exporter_fallback(tmp_path):
    from analyze_xml_report import load_texture_exporter

    create_export_engine = load_texture_exporter(force_fallback=True)
    assert callable(create_export_engine)


def test_shader_source_rendered(tmp_path):
    gen = ReportBundleGenerator(output_dir=tmp_path, capture_name="t.rdc")
    gen.set_shaders([
        {
            "id": "1",
            "name": "S",
            "source": "float4 main() : SV_Target { return 0; }",
        }
    ])
    outputs = gen.generate_all()
    html = Path(outputs["shaders"]).read_text(encoding="utf-8")
    assert "float4 main()" in html
    assert "codeBlock" in html


def test_texture_preview_uses_thumbnail(tmp_path):
    gen = ReportBundleGenerator(output_dir=tmp_path, capture_name="t.rdc")
    gen.set_textures([
        {
            "id": "1",
            "name": "Tex",
            "width": 1,
            "height": 1,
            "thumbnail": "data:image/png;base64,AAAA",
        }
    ])
    outputs = gen.generate_all()
    html = Path(outputs["textures"]).read_text(encoding="utf-8")
    assert "previewImg" in html
    assert "texture.thumbnail" in html


def test_textures_no_dynamic_buttons(tmp_path):
    gen = ReportBundleGenerator(output_dir=tmp_path, capture_name="t.rdc")
    gen.set_textures([
        {
            "id": "1",
            "name": "Tex",
            "width": 1,
            "height": 1,
        }
    ])
    outputs = gen.generate_all()
    html = Path(outputs["textures"]).read_text(encoding="utf-8")
    assert "加载缩略图" not in html
    assert "enableThumbnails" not in html
    assert "autoPreloadThumbnails" not in html
    assert "RT_SERVER_BASE" not in html
    assert "thumbStatus" not in html


def test_shader_ui_hlsl_only(tmp_path):
    gen = ReportBundleGenerator(output_dir=tmp_path, capture_name="t.rdc")
    gen.set_shaders([
        {
            "id": "1",
            "name": "S",
            "source_hlsl": "float4 main() : SV_Target { return 0; }",
        }
    ])
    outputs = gen.generate_all()
    html = Path(outputs["shaders"]).read_text(encoding="utf-8")
    assert "查看 HLSL 代码" in html
    assert "AI Shader 优化" in html
    assert "GLSL" not in html and "SPIR-V" not in html and "Disassembly" not in html


def test_shader_list_has_search_attrs(tmp_path):
    gen = ReportBundleGenerator(output_dir=tmp_path, capture_name="t.rdc")
    gen.set_shaders([
        {
            "id": "1",
            "name": "MainVS",
            "type": "vertex",
            "usedBy": [{"eid": 1}],
        }
    ])
    outputs = gen.generate_all()
    html = Path(outputs["shaders"]).read_text(encoding="utf-8")
    assert 'data-name="MainVS"' in html
    assert 'data-type="vertex"' in html
    assert "shader-item-name" in html


def test_shader_toolbar_primary_secondary(tmp_path):
    gen = ReportBundleGenerator(output_dir=tmp_path, capture_name="t.rdc")
    gen.set_shaders([
        {
            "id": "1",
            "name": "S",
            "source_hlsl": "float4 main() : SV_Target { return 0; }",
        }
    ])
    outputs = gen.generate_all()
    html = Path(outputs["shaders"]).read_text(encoding="utf-8")
    assert "toolbar-btn primary" in html
    assert "toolbar-btn secondary" in html
    assert "toolbar-group primary-actions" in html
    assert "app-container fixed" in html


def test_analyze_xml_report_has_auto_rt_flag():
    script_path = Path(__file__).resolve().parents[1] / "analyze_xml_report.py"
    content = script_path.read_text(encoding="utf-8")
    assert "--auto-start-rt-server" in content


def test_analyze_xml_report_has_rdc_path_flag():
    script_path = Path(__file__).resolve().parents[1] / "analyze_xml_report.py"
    content = script_path.read_text(encoding="utf-8")
    assert "--rdc-path" in content

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


def test_texture_thumbnail_data_url(tmp_path):
    gen = ReportBundleGenerator(output_dir=tmp_path, capture_name="t.rdc")
    gen.set_textures([
        {
            "id": "1",
            "name": "Tex",
            "width": 1,
            "height": 1,
            "thumbnail": "AAAA",
        }
    ])
    outputs = gen.generate_all()
    html = Path(outputs["textures"]).read_text(encoding="utf-8")
    assert "data:image/png;base64,AAAA" in html


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


def test_textures_has_enable_thumbnail_button(tmp_path):
    gen = ReportBundleGenerator(output_dir=tmp_path, capture_name="t.rdc")
    gen.set_textures([
        {
            "id": "1",
            "name": "Tex",
            "width": 1,
            "height": 1,
            "thumbnail": "AAAA",
        }
    ])
    outputs = gen.generate_all()
    html = Path(outputs["textures"]).read_text(encoding="utf-8")
    assert "显示缩略图" in html
    assert "enableThumbnails" in html


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

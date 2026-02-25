#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bundle 报告资源验证
===================

验证 textures.html / shaders.html 中关键渲染字段是否存在，
避免缩略图与源码被错误处理导致页面空白。
"""

import re
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


def test_map_exported_textures_prefers_resource_id(tmp_path):
    from analyze_xml_report import map_exported_textures

    textures = [
        {
            "id": "tex_0",
            "resource_id": "123",
            "name": "Tex",
            "width": 4,
            "height": 8,
            "thumbnail": "",
        }
    ]
    export_dir = tmp_path / "textures"
    export_dir.mkdir(parents=True, exist_ok=True)
    (export_dir / "tex_123_4x8.png").write_bytes(b"fake")

    updated = map_exported_textures(textures, export_dir)
    assert updated == 1
    assert textures[0]["thumbnail"] == "textures/tex_123_4x8.png"


def test_load_textures_resource_id():
    from analyze_xml_report import load_textures_if_available

    xml_data = {"textures": [{"resourceId": "321", "name": "T", "width": 1, "height": 1}]}
    textures = load_textures_if_available(None, xml_data)
    assert textures[0]["resource_id"] == "321"


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


def test_textures_list_item_has_dataset_and_thumb_class(tmp_path):
    gen = ReportBundleGenerator(output_dir=tmp_path, capture_name="t.rdc")
    gen.set_textures([
        {
            "id": "tex_0",
            "resource_id": "133",
            "name": "Image_133",
            "width": 4,
            "height": 4,
            "mips": 1,
            "vram": 16,
            "format": "VK_FORMAT_R8G8B8A8_UNORM",
            "thumbnail": "textures/tex_133_4x4.png",
            "issues": [{"level": "warn", "message": "x"}],
        }
    ])
    outputs = gen.generate_all()
    html = Path(outputs["textures"]).read_text(encoding="utf-8")
    assert 'data-name="Image_133"' in html
    assert 'data-format="VK_FORMAT_R8G8B8A8_UNORM"' in html
    assert 'data-width="4"' in html
    assert 'data-height="4"' in html
    assert 'data-mip-levels="1"' in html
    assert 'data-vram="16"' in html
    assert 'data-has-issue="true"' in html
    assert "texture-item-thumb" in html
    assert "app-container fixed" in html


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


def test_analyze_xml_report_uses_texture_export_helper():
    script_path = Path(__file__).resolve().parents[1] / "analyze_xml_report.py"
    content = script_path.read_text(encoding="utf-8")
    assert content.count("load_texture_exporter") >= 2


def test_shader_full_data_query_and_pager_contract(tmp_path):
    gen = ReportBundleGenerator(output_dir=tmp_path, capture_name="t.rdc")
    gen.set_shaders([
        {"id": str(i), "name": f"Shader_{i}", "type": "vertex" if i % 2 == 0 else "pixel", "usedBy": [{"eid": i}]}
        for i in range(1, 6)
    ])
    outputs = gen.generate_all()
    html = Path(outputs["shaders"]).read_text(encoding="utf-8")
    assert 'id="shaderPager"' in html
    assert 'const allShaders = Array.isArray(shaderData) ? shaderData : []' in html
    assert 'let filteredShaders = allShaders.slice();' in html
    assert 'function applyShaderQuery(resetPage)' in html
    assert 'function renderShaderPage()' in html


def test_textures_default_vram_sort_and_auto_select_contract(tmp_path):
    gen = ReportBundleGenerator(output_dir=tmp_path, capture_name="t.rdc")
    gen.set_textures([
        {"id": "1", "resource_id": "1", "name": "Tiny", "width": 4, "height": 4, "vram": 16},
        {"id": "2", "resource_id": "2", "name": "Readable", "width": 1024, "height": 1024, "vram": 1024 * 1024},
    ])
    outputs = gen.generate_all()
    html = Path(outputs["textures"]).read_text(encoding="utf-8")
    assert "sortSelect.value = 'vram'" in html
    assert 'function selectDefaultTexture()' in html
    assert 'selectDefaultTexture();' in html

def test_shader_data_json_escapes_script_end_tag(tmp_path):
    gen = ReportBundleGenerator(output_dir=tmp_path, capture_name="t.rdc")
    gen.set_shaders([
        {
            "id": "1",
            "name": "ScriptEdge",
            "source_hlsl": "float4 main() : SV_Target { return 0; } </script>",
        }
    ])
    outputs = gen.generate_all()
    html = Path(outputs["shaders"]).read_text(encoding="utf-8")
    assert "<\\/script>" in html



def test_shader_mode_badge_contract(tmp_path):
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
    assert 'id="codeModeBadge"' in html
    assert 'function updateCodeModeBadge(text, state)' in html



def test_textures_item_id_vram_badges_contract(tmp_path):
    gen = ReportBundleGenerator(output_dir=tmp_path, capture_name="t.rdc")
    gen.set_textures([
        {
            "id": "tex_0",
            "resource_id": "133",
            "name": "Image_133",
            "width": 4,
            "height": 4,
            "mips": 1,
            "vram": 16,
            "format": "VK_FORMAT_R8G8B8A8_UNORM",
            "thumbnail": "textures/tex_133_4x4.png",
        }
    ])
    outputs = gen.generate_all()
    html = Path(outputs["textures"]).read_text(encoding="utf-8")
    assert "texture-item-submeta" in html
    assert "texture-id-badge" in html
    assert "texture-vram-badge" in html



def test_shader_ai_mode_banner_contract(tmp_path):
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
    assert 'id="analysisModeBanner"' in html
    assert 'function updateAiModeUI()' in html



def test_textures_panel_summary_contract(tmp_path):
    gen = ReportBundleGenerator(output_dir=tmp_path, capture_name="t.rdc")
    gen.set_textures([
        {
            "id": "1",
            "resource_id": "1",
            "name": "Tex",
            "width": 512,
            "height": 512,
            "vram": 1024,
        }
    ])
    outputs = gen.generate_all()
    html = Path(outputs["textures"]).read_text(encoding="utf-8")
    assert 'id="texturePanelSummary"' in html
    assert 'id="visibleTextureCount"' in html
    assert 'id="filterStateHint"' in html
    assert 'id="textureDataHealth"' in html
    assert 'function getTextureFilterLabel()' in html
    assert 'function updateTexturePanelSummary()' in html
    assert 'function updateTextureDataHealthBanner()' in html


def test_shaders_panel_summary_contract(tmp_path):
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
    assert 'id="shaderPanelSummary"' in html
    assert 'id="visibleShaderCount"' in html
    assert 'id="activeShaderFilter"' in html
    assert 'id="shaderDataHealth"' in html
    assert 'function updateShaderPanelSummary()' in html
    assert 'function updateShaderDataHealthBanner()' in html



def test_common_css_typography_tokens_contract():
    css_path = Path(__file__).resolve().parents[1] / "templates" / "common.css"
    css = css_path.read_text(encoding="utf-8")

    assert "--font-micro: 10px" in css
    assert "--font-xs: 11px" in css
    assert "--font-sm: 12px" in css
    assert "--font-md: 14px" in css

    # 中文 fallback 与等宽 fallback 需要明确，避免不同机器显示飘移
    assert "Microsoft YaHei" in css
    assert "Noto Sans CJK SC" in css
    assert "Cascadia Mono" in css


def test_common_css_theme_alias_tokens_contract():
    css_path = Path(__file__).resolve().parents[1] / "templates" / "common.css"
    css = css_path.read_text(encoding="utf-8")

    assert "--accent-cyan:" in css
    assert "--accent-pink:" in css
    assert "--accent:" in css
    assert "--accent-hover:" in css
    assert "--radius:" in css


def test_template_css_vars_defined_contract():
    templates_dir = Path(__file__).resolve().parents[1] / "templates"
    files = ["common.css", "shaders.html", "textures.html"]

    defined = set()
    used = set()
    def_pattern = re.compile(r"(--[a-zA-Z0-9_-]+)\s*:")
    use_pattern = re.compile(r"var\((--[a-zA-Z0-9_-]+)\)")

    for filename in files:
        text = (templates_dir / filename).read_text(encoding="utf-8")
        defined.update(def_pattern.findall(text))
        used.update(use_pattern.findall(text))

    undefined = sorted(var for var in used if var not in defined)
    assert not undefined, f"undefined CSS vars in templates: {', '.join(undefined)}"


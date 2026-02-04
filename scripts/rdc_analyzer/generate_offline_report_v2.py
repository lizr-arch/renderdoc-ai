#!/usr/bin/env python3
"""
生成 100% 离线 HTML 报告 - 无任何外部依赖 (V2 - 模板分离版)

专门用于 D3D11/D3D12/Vulkan 纹理分析，不依赖 CDN 或网络资源。
CSS/JS/HTML 模板存放在 assets/ 和 templates/ 目录。
"""

import json
import base64
import argparse
import io
from pathlib import Path
from datetime import datetime
from string import Template

# ==============================================================================
# 模块路径
# ==============================================================================
_SCRIPT_DIR = Path(__file__).parent
_ASSETS_DIR = _SCRIPT_DIR / "assets"
_TEMPLATES_DIR = _SCRIPT_DIR / "templates"

# ==============================================================================
# 可选组件（动态 CSS/JS 生成器）
# ==============================================================================
try:
    from components.rt_timeline_component import (
        generate_rt_timeline_css,
        generate_rt_timeline_html,
        generate_rt_timeline_js
    )
    HAS_RT_TIMELINE = True
except ImportError:
    HAS_RT_TIMELINE = False

try:
    from components.hotspot_component import (
        generate_hotspot_css,
        generate_hotspot_html,
        generate_hotspot_js
    )
    HAS_HOTSPOT = True
except ImportError:
    HAS_HOTSPOT = False

try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False
    print("  [WARN] Pillow not installed. Run: pip install Pillow")
    print("         RGBA channel separation will be disabled.")


# ==============================================================================
# 资源加载器
# ==============================================================================
def load_css() -> str:
    """加载主 CSS 文件"""
    css_path = _ASSETS_DIR / "styles" / "offline_report.css"
    if css_path.exists():
        return css_path.read_text(encoding="utf-8")
    print(f"  [WARN] CSS not found: {css_path}")
    return "/* CSS not found */"


def load_js() -> str:
    """加载主 JS 文件"""
    js_path = _ASSETS_DIR / "scripts" / "offline_report.js"
    if js_path.exists():
        return js_path.read_text(encoding="utf-8")
    print(f"  [WARN] JS not found: {js_path}")
    return "// JS not found"


def load_html_body() -> str:
    """加载 HTML body 模板"""
    body_path = _TEMPLATES_DIR / "offline_report_body.html"
    if body_path.exists():
        return body_path.read_text(encoding="utf-8")
    print(f"  [WARN] HTML body not found: {body_path}")
    return "<!-- HTML body not found -->"


def load_template() -> str:
    """加载主 HTML 模板"""
    template_path = _TEMPLATES_DIR / "offline_report.html"
    if template_path.exists():
        return template_path.read_text(encoding="utf-8")
    print(f"  [WARN] Template not found: {template_path}")
    return "<!DOCTYPE html><html><body>Template not found</body></html>"


# ==============================================================================
# 图像处理
# ==============================================================================
def generate_channel_images(png_path: Path) -> dict:
    """用 PIL 将 PNG 拆分为 R/G/B/A 四个灰度图"""
    if not HAS_PIL:
        return {}
    
    try:
        img = Image.open(png_path).convert("RGBA")
        r, g, b, a = img.split()
        
        channels = {}
        for name, channel in [("r", r), ("g", g), ("b", b), ("a", a)]:
            extrema = channel.getextrema()
            if extrema[0] == extrema[1]:
                if name == "a" and extrema[0] == 255:
                    channels[name] = None
                continue
            
            buffer = io.BytesIO()
            channel.save(buffer, format="PNG", optimize=True)
            b64_data = base64.b64encode(buffer.getvalue()).decode('utf-8')
            channels[name] = f"data:image/png;base64,{b64_data}"
        
        return channels
    except Exception as e:
        print(f"    [WARN] Failed to split channels for {png_path.name}: {e}")
        return {}


# ==============================================================================
# 纹理加载
# ==============================================================================
def load_textures_from_export(rdc_path: str, enable_channels: bool = True) -> list:
    """从导出目录加载纹理元数据和缩略图"""
    rdc_path = Path(rdc_path)
    capture_name = rdc_path.stem
    
    possible_paths = [
        rdc_path.parent / f"{capture_name}_textures" / "textures.json",
        rdc_path.parent / "textures" / "textures.json",
    ]
    
    for manifest_path in possible_paths:
        if manifest_path.exists():
            with open(manifest_path, 'r', encoding='utf-8') as f:
                manifest = json.load(f)
            
            textures = []
            textures_dir = manifest_path.parent
            tex_list = manifest if isinstance(manifest, list) else manifest.get("textures", [])
            
            for tex in tex_list:
                res_id = tex.get("resource_id") or tex.get("id")
                filename = tex.get("filename") or tex.get("file")
                
                thumbnail_data = ""
                channels = {}
                
                if tex.get("thumbnail"):
                    thumbnail_data = tex["thumbnail"]
                    if not thumbnail_data.startswith("data:"):
                        thumbnail_data = f"data:image/png;base64,{thumbnail_data}"
                elif filename:
                    full_path = textures_dir / filename
                    if full_path.exists():
                        with open(full_path, 'rb') as img_file:
                            img_data = img_file.read()
                            b64_data = base64.b64encode(img_data).decode('utf-8')
                            thumbnail_data = f"data:image/png;base64,{b64_data}"
                        
                        if enable_channels and HAS_PIL:
                            channels = generate_channel_images(full_path)
                
                textures.append({
                    "id": res_id,
                    "name": tex.get("name", ""),
                    "width": tex.get("width", 0),
                    "height": tex.get("height", 0),
                    "depth": tex.get("depth", 1),
                    "format": tex.get("format", "UNKNOWN"),
                    "mips": tex.get("mips", 1),
                    "arrayLayers": tex.get("arrayLayers", 1),
                    "thumbnail": thumbnail_data,
                    "channels": channels
                })
            
            print(f"  [OK] Loaded {len(textures)} textures from {manifest_path}")
            return textures
    
    print("  [WARN] No textures.json found")
    return []


# ==============================================================================
# HTML 生成（核心函数）
# ==============================================================================
def generate_offline_html(
    textures: list,
    rdc_name: str,
    output_path: str,
    duplicate_analysis: dict = None,
    usage_analysis: dict = None,
    event_pass_data: dict = None,
    frame_thumbnail: str = None,
    optimization_data: dict = None,
    performance_data: dict = None,
    rt_tracking_data: dict = None,
    hotspot_data: dict = None,
    shader_data: list = None,
    texture_usage_map: dict = None,
    report_links: dict = None,
    manifest_data: dict = None
):
    """
    生成纯离线 HTML 报告
    
    使用 string.Template 将数据注入到 HTML 模板中。
    CSS/JS 从外部文件加载并嵌入到最终 HTML 中。
    """
    # 1. 加载静态资源
    css_content = load_css()
    js_content = load_js()
    html_body = load_html_body()
    template_str = load_template()
    
    # 2. 准备动态组件
    rt_css = generate_rt_timeline_css() if HAS_RT_TIMELINE and rt_tracking_data else ""
    rt_js = generate_rt_timeline_js() if HAS_RT_TIMELINE and rt_tracking_data else ""
    hotspot_css = generate_hotspot_css() if HAS_HOTSPOT and hotspot_data else ""
    hotspot_js = generate_hotspot_js() if HAS_HOTSPOT and hotspot_data else ""
    hotspot_init = generate_hotspot_html(hotspot_data) if HAS_HOTSPOT and hotspot_data else ""
    
    # 3. 序列化 JSON 数据
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    data_map = {
        "RDC_NAME": rdc_name,
        "TIMESTAMP": timestamp,
        "CSS_CONTENT": css_content,
        "JS_CONTENT": js_content,
        "HTML_BODY": html_body,
        "RT_TIMELINE_CSS": rt_css,
        "RT_TIMELINE_JS": rt_js,
        "HOTSPOT_CSS": hotspot_css,
        "HOTSPOT_JS": hotspot_js,
        "HOTSPOT_INIT": hotspot_init,
        "TEXTURES_JSON": json.dumps(textures, ensure_ascii=False),
        "SHADERS_JSON": json.dumps(shader_data or [], ensure_ascii=False),
        "DUPLICATES_JSON": json.dumps(duplicate_analysis or {}, ensure_ascii=False),
        "USAGE_JSON": json.dumps(usage_analysis or {}, ensure_ascii=False),
        "EVENT_PASS_JSON": json.dumps(event_pass_data or {}, ensure_ascii=False),
        "FRAME_THUMBNAIL_JSON": json.dumps(frame_thumbnail or "", ensure_ascii=False),
        "OPTIMIZATION_JSON": json.dumps(optimization_data or {}, ensure_ascii=False),
        "PERFORMANCE_JSON": json.dumps(performance_data or {}, ensure_ascii=False),
        "RT_TRACKING_JSON": json.dumps(rt_tracking_data or {}, ensure_ascii=False),
        "HOTSPOT_JSON": json.dumps(hotspot_data or {}, ensure_ascii=False),
        "TEXTURE_USAGE_MAP_JSON": json.dumps(texture_usage_map or {}, ensure_ascii=False),
        "REPORT_LINKS_JSON": json.dumps(report_links or {}, ensure_ascii=False),
        "MANIFEST_JSON": json.dumps(manifest_data or {}, ensure_ascii=False),
    }
    
    # 4. 执行模板替换
    template = Template(template_str)
    html = template.safe_substitute(data_map)
    
    # 5. 写入文件
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)
    
    print(f"[OK] Report saved to: {output_path}")


# ==============================================================================
# 辅助函数
# ==============================================================================
def _build_texture_usage_map(event_pass_data: dict) -> dict:
    """构建纹理使用映射（纹理 ID → 使用它的 Event 列表）"""
    texture_usage_map = {}
    texture_descriptor_types = [
        'VK_DESCRIPTOR_TYPE_SAMPLED_IMAGE',
        'VK_DESCRIPTOR_TYPE_STORAGE_IMAGE', 
        'VK_DESCRIPTOR_TYPE_INPUT_ATTACHMENT',
        'VK_DESCRIPTOR_TYPE_COMBINED_IMAGE_SAMPLER'
    ]
    
    events = event_pass_data.get("events", []) if event_pass_data else []
    for evt in events:
        eid = evt.get("eventId") or evt.get("eid")
        evt_name = evt.get("name", "")
        descriptor_sets = evt.get("resourceBindings", {}).get("descriptorSets", [])
        
        for ds in descriptor_sets:
            for binding in ds.get("bindings", []):
                desc_type = binding.get("descriptorType", "")
                if desc_type in texture_descriptor_types:
                    for res in binding.get("resources", []):
                        res_id = res.get("resourceId")
                        if res_id:
                            if res_id not in texture_usage_map:
                                texture_usage_map[res_id] = []
                            texture_usage_map[res_id].append({
                                "eid": eid,
                                "name": evt_name,
                                "slot": binding.get("binding", 0)
                            })
    
    return texture_usage_map


# ==============================================================================
# CLI 入口
# ==============================================================================
def main():
    parser = argparse.ArgumentParser(
        description='Generate offline RDC texture report (V2 - Template-based)'
    )
    parser.add_argument('rdc_path', help='Path to RDC file or textures.json')
    parser.add_argument('-o', '--output', help='Output HTML path', default=None)
    
    args = parser.parse_args()
    
    rdc_path = Path(args.rdc_path)
    if not rdc_path.exists():
        print(f"[ERROR] File not found: {rdc_path}")
        return 1
    
    output_path = args.output or str(rdc_path.with_suffix('.html'))
    
    print(f"\n=== Generating Offline Report (V2) for {rdc_path.name} ===\n")
    
    # 支持直接传入 textures.json
    shaders = []
    event_pass_data = {}
    
    if rdc_path.name == 'textures.json' or rdc_path.suffix == '.json':
        with open(rdc_path, 'r', encoding='utf-8') as f:
            manifest = json.load(f)
        
        tex_list = manifest if isinstance(manifest, list) else manifest.get("textures", [])
        textures = []
        for tex in tex_list:
            res_id = tex.get("resource_id") or tex.get("id")
            textures.append({
                "id": res_id,
                "name": tex.get("name", ""),
                "width": tex.get("width", 0),
                "height": tex.get("height", 0),
                "depth": tex.get("depth", 1),
                "format": tex.get("format", "UNKNOWN"),
                "mips": tex.get("mips", 1),
                "arrayLayers": tex.get("arrayLayers", 1),
                "thumbnail": tex.get("thumbnail", ""),
                "channels": tex.get("channels", {})
            })
        print(f"  [OK] Loaded {len(textures)} textures from {rdc_path}")
        
        if isinstance(manifest, dict) and "shaders" in manifest:
            shaders = manifest.get("shaders", [])
            print(f"  [OK] Loaded {len(shaders)} shaders from {rdc_path}")
        
        if isinstance(manifest, dict) and "events" in manifest:
            event_pass_data = {"events": manifest.get("events", [])}
            print(f"  [OK] Loaded {len(event_pass_data['events'])} events from {rdc_path}")
    else:
        textures = load_textures_from_export(str(rdc_path))
    
    if not textures:
        print("[WARN] No textures found, generating empty report")
    
    # 构建纹理使用映射
    texture_usage_map = _build_texture_usage_map(event_pass_data)
    
    generate_offline_html(
        textures=textures,
        rdc_name=rdc_path.stem,
        output_path=output_path,
        shader_data=shaders,
        event_pass_data=event_pass_data,
        texture_usage_map=texture_usage_map
    )
    
    return 0


if __name__ == '__main__':
    exit(main())

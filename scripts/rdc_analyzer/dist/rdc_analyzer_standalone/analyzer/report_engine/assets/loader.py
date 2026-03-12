"""
Assets Loader - 静态资源加载器

提供加载 CSS 和 JS 模板的功能。
"""
from pathlib import Path
from typing import Dict

# 资源目录
ASSETS_DIR = Path(__file__).parent

# 数据占位符列表（与 generate_offline_report.py 保持同步）
JS_DATA_PLACEHOLDERS = [
    "textures_json",
    "duplicates_json",
    "usage_json",
    "event_pass_json",
    "report_links_json",
    "manifest_json",
    "frame_thumbnail_json",
    "optimization_json",
    "performance_json",
    "shader_json",
    "texture_usage_map_json",
]


def load_css() -> str:
    """加载主 CSS 样式文件"""
    css_path = ASSETS_DIR / "styles.css"
    if not css_path.exists():
        raise FileNotFoundError(f"CSS 文件不存在: {css_path}")
    return css_path.read_text(encoding="utf-8")


def load_js_template() -> str:
    """加载 JS 模板文件（包含数据占位符）"""
    js_path = ASSETS_DIR / "scripts.js"
    if not js_path.exists():
        raise FileNotFoundError(f"JS 模板不存在: {js_path}")
    return js_path.read_text(encoding="utf-8")


def fill_js_template(data: Dict[str, str]) -> str:
    """
    填充 JS 模板中的数据占位符
    
    Args:
        data: 占位符名称 -> JSON 字符串 的映射
              例如 {"textures_json": "[...]", "duplicates_json": "{...}"}
    
    Returns:
        填充后的完整 JS 代码
    """
    template = load_js_template()
    
    for placeholder in JS_DATA_PLACEHOLDERS:
        token = "{" + placeholder + "}"
        value = data.get(placeholder, "null")
        template = template.replace(token, value)
    
    return template


__all__ = [
    "load_css",
    "load_js_template",
    "fill_js_template",
    "JS_DATA_PLACEHOLDERS",
]

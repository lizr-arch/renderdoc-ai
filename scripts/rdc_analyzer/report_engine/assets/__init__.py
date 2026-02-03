"""
Assets - 静态资源模块

CSS 和 JS 文件将放置在此目录下：
    - styles.css: 主样式文件
    - scripts.js: 主脚本模板（包含数据占位符）
    - loader.py: 资源加载器
"""
from .loader import (
    load_css,
    load_js_template,
    fill_js_template,
    JS_DATA_PLACEHOLDERS,
)

__all__ = [
    "load_css",
    "load_js_template",
    "fill_js_template",
    "JS_DATA_PLACEHOLDERS",
]
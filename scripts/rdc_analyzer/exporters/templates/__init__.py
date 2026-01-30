"""
HTML 模板资源包
==============

包含 HTML 报告所需的静态资源：
- styles.css: 核心样式 (~1700 行)
- main.js: 交互逻辑 (~1200 行)
- base.html: HTML 骨架

模块导出:
- TemplateLoader: 模板加载器
- get_template_path(): 获取模板路径
"""

from pathlib import Path
from typing import Optional


def get_template_dir() -> Path:
    """获取模板目录的绝对路径"""
    return Path(__file__).parent


def get_template_path(filename: str) -> Path:
    """获取指定模板文件的路径"""
    return get_template_dir() / filename


# 默认主题配置
DARK_THEME = {
    'bg_primary': '#0d1117',
    'bg_secondary': '#161b22',
    'bg_tertiary': '#21262d',
    'text_primary': '#e6edf3',
    'text_secondary': '#8b949e',
    'border_color': '#30363d',
}

LIGHT_THEME = {
    'bg_primary': '#f6f8fa',
    'bg_secondary': '#ffffff',
    'bg_tertiary': '#f0f3f6',
    'text_primary': '#24292f',
    'text_secondary': '#57606a',
    'border_color': '#d0d7de',
}


class TemplateLoader:
    """模板加载器 - 负责加载和组装 HTML 模板"""
    
    _cache: dict = {}
    
    def __init__(self, cache_enabled: bool = True):
        """
        初始化模板加载器
        
        Args:
            cache_enabled: 是否启用模板缓存（生产环境推荐开启）
        """
        self.cache_enabled = cache_enabled
    
    def load(self, filename: str) -> str:
        """
        加载模板文件内容
        
        Args:
            filename: 模板文件名（相对于 templates/ 目录）
            
        Returns:
            模板内容字符串
            
        Raises:
            FileNotFoundError: 模板文件不存在
        """
        if self.cache_enabled and filename in self._cache:
            return self._cache[filename]
        
        template_path = get_template_path(filename)
        if not template_path.exists():
            raise FileNotFoundError(f"Template not found: {template_path}")
        
        content = template_path.read_text(encoding='utf-8')
        
        if self.cache_enabled:
            self._cache[filename] = content
        
        return content
    
    def load_styles(self, theme: str = 'dark') -> str:
        """
        加载并应用主题的 CSS 样式
        
        Args:
            theme: 'dark' 或 'light'
        """
        css = self.load('styles.css')
        theme_vars = DARK_THEME if theme == 'dark' else LIGHT_THEME
        
        # 替换主题变量
        for key, value in theme_vars.items():
            css = css.replace(f'{{{key}}}', value)
        
        return css
    
    def load_scripts(self) -> str:
        """加载 JavaScript 脚本"""
        return self.load('main.js')
    
    def load_base_html(self) -> str:
        """加载 HTML 基础模板"""
        return self.load('base.html')
    
    def get_theme_colors(self, theme: str = 'dark') -> dict:
        """获取主题颜色配置"""
        return DARK_THEME.copy() if theme == 'dark' else LIGHT_THEME.copy()
    
    def clear_cache(self):
        """清除模板缓存"""
        self._cache.clear()


# 默认加载器实例
default_loader = TemplateLoader()


__all__ = [
    'TemplateLoader',
    'get_template_dir',
    'get_template_path',
    'default_loader',
    'DARK_THEME',
    'LIGHT_THEME',
]

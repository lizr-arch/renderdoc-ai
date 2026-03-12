"""
HTML Renderer - 报告渲染器

将 ReportDataContract 渲染为完整的 HTML 报告。
"""
import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from ..contract import ReportDataContract
from ..assets import load_css, load_js_template, fill_js_template, JS_DATA_PLACEHOLDERS


class HtmlRenderer:
    """
    HTML 报告渲染器
    
    负责将 ReportDataContract 组装为完整的离线 HTML 文件。
    
    Usage:
        contract = ReportDataContract(...)
        renderer = HtmlRenderer()
        html = renderer.render(contract, "my_capture.rdc")
        Path("report.html").write_text(html)
    """
    
    def __init__(self):
        """初始化渲染器，加载静态资源"""
        self._css: Optional[str] = None
        self._js_template: Optional[str] = None
        self._body_template: Optional[str] = None
    
    @property
    def css(self) -> str:
        """延迟加载 CSS"""
        if self._css is None:
            self._css = load_css()
        return self._css
    
    @property
    def js_template(self) -> str:
        """延迟加载 JS 模板"""
        if self._js_template is None:
            self._js_template = load_js_template()
        return self._js_template
    
    @property
    def body_template(self) -> str:
        """延迟加载 HTML body 模板"""
        if self._body_template is None:
            template_path = Path(__file__).parent.parent / "assets" / "body_template.html"
            if template_path.exists():
                self._body_template = template_path.read_text(encoding="utf-8")
            else:
                # 使用最小化 fallback
                self._body_template = '<div class="app-container">报告加载中...</div>'
        return self._body_template
    
    def render(self, contract: ReportDataContract, rdc_name: str = "Unknown") -> str:
        """
        渲染完整的 HTML 报告
        
        Args:
            contract: 报告数据契约
            rdc_name: RDC 文件名（用于显示）
        
        Returns:
            完整的 HTML 字符串
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # 准备 JS 数据
        js_data = self._prepare_js_data(contract)
        js_content = fill_js_template(js_data)
        
        # 渲染 body（替换占位符）
        body_content = self.body_template
        body_content = body_content.replace("{rdc_name}", rdc_name)
        body_content = body_content.replace("{timestamp}", timestamp)
        
        # 组装完整 HTML
        html = self._assemble_html(
            title=f"RDC 纹理报告 - {rdc_name}",
            css=self.css,
            body=body_content,
            js=js_content
        )
        
        return html
    
    def _prepare_js_data(self, contract: ReportDataContract) -> dict:
        """将 Contract 转换为 JS 数据字典"""
        # frame_thumbnail 在 MetaData 中
        frame_thumbnail = ""
        if hasattr(contract.meta, "frame_thumbnail"):
            frame_thumbnail = contract.meta.frame_thumbnail
        elif isinstance(contract.meta, dict):
            frame_thumbnail = contract.meta.get("frame_thumbnail", "")
        
        return {
            "textures_json": json.dumps(contract.textures, ensure_ascii=False),
            "duplicates_json": json.dumps(contract.duplicate_analysis, ensure_ascii=False),
            "usage_json": json.dumps(contract.usage_analysis, ensure_ascii=False),
            "event_pass_json": json.dumps(contract.event_pass_data, ensure_ascii=False),
            "report_links_json": json.dumps(contract.report_links, ensure_ascii=False),
            "manifest_json": json.dumps(contract.manifest_data, ensure_ascii=False),
            "frame_thumbnail_json": json.dumps(frame_thumbnail, ensure_ascii=False),
            "optimization_json": json.dumps(contract.optimization_data, ensure_ascii=False),
            "performance_json": json.dumps(contract.performance, ensure_ascii=False),
            "shader_json": json.dumps(contract.shaders, ensure_ascii=False),
            "texture_usage_map_json": json.dumps(contract.texture_usage_map, ensure_ascii=False),
        }
    
    def _assemble_html(self, title: str, css: str, body: str, js: str) -> str:
        """组装完整的 HTML 文档"""
        return f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <style>
{css}
    </style>
</head>
<body>
{body}
    <script>
{js}
    </script>
</body>
</html>'''
    
    def render_to_file(self, contract: ReportDataContract, output_path: str, 
                       rdc_name: str = "Unknown") -> Path:
        """
        渲染并保存到文件
        
        Args:
            contract: 报告数据契约
            output_path: 输出文件路径
            rdc_name: RDC 文件名
        
        Returns:
            输出文件的 Path 对象
        """
        html = self.render(contract, rdc_name)
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(html, encoding="utf-8")
        return output


__all__ = ["HtmlRenderer"]

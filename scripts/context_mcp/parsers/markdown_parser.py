"""
Markdown 文件解析器

提取标题、内容、元数据
"""
import re
from pathlib import Path
from typing import Dict, List, Optional


class MarkdownParser:
    """Markdown 文件解析器"""
    
    # 标题正则
    HEADING_PATTERN = re.compile(r'^(#{1,6})\s+(.+)$', re.MULTILINE)
    
    # 代码块正则（用于跳过）
    CODE_BLOCK_PATTERN = re.compile(r'```[\s\S]*?```', re.MULTILINE)
    
    def __init__(self, file_path: Path):
        self.file_path = Path(file_path)
        self._content: Optional[str] = None
        self._title: Optional[str] = None
        self._headings: Optional[List[Dict]] = None
    
    @property
    def content(self) -> str:
        """获取原始内容"""
        if self._content is None:
            self._content = self._read_file()
        return self._content
    
    @property
    def title(self) -> str:
        """获取文档标题（第一个 # 标题）"""
        if self._title is None:
            self._extract_headings()
        return self._title or self.file_path.stem
    
    @property
    def headings(self) -> List[Dict]:
        """获取所有标题层级"""
        if self._headings is None:
            self._extract_headings()
        return self._headings
    
    def _read_file(self) -> str:
        """读取文件内容"""
        try:
            return self.file_path.read_text(encoding='utf-8')
        except UnicodeDecodeError:
            # 尝试 GBK
            return self.file_path.read_text(encoding='gbk')
    
    def _extract_headings(self) -> None:
        """提取标题结构"""
        self._headings = []
        self._title = None
        
        # 移除代码块避免干扰
        clean_content = self.CODE_BLOCK_PATTERN.sub('', self.content)
        
        for match in self.HEADING_PATTERN.finditer(clean_content):
            level = len(match.group(1))
            text = match.group(2).strip()
            
            heading = {
                "level": level,
                "text": text,
                "position": match.start(),
            }
            self._headings.append(heading)
            
            # 第一个 h1 作为标题
            if level == 1 and self._title is None:
                self._title = text
    
    def get_text_content(self) -> str:
        """获取纯文本内容（移除格式标记）"""
        text = self.content
        
        # 移除代码块
        text = self.CODE_BLOCK_PATTERN.sub('[CODE BLOCK]', text)
        
        # 移除链接，保留文本
        text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)
        
        # 移除图片
        text = re.sub(r'!\[([^\]]*)\]\([^)]+\)', r'[IMAGE: \1]', text)
        
        # 移除强调符号
        text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)
        text = re.sub(r'\*([^*]+)\*', r'\1', text)
        text = re.sub(r'`([^`]+)`', r'\1', text)
        
        return text.strip()
    
    def get_snippet(self, query: str, context_chars: int = 200) -> Optional[str]:
        """获取包含查询词的摘要片段"""
        text = self.get_text_content().lower()
        query_lower = query.lower()
        
        pos = text.find(query_lower)
        if pos == -1:
            return None
        
        # 获取原始大小写内容
        original = self.get_text_content()
        
        start = max(0, pos - context_chars // 2)
        end = min(len(original), pos + len(query) + context_chars // 2)
        
        snippet = original[start:end]
        
        # 添加省略号
        if start > 0:
            snippet = "..." + snippet
        if end < len(original):
            snippet = snippet + "..."
        
        return snippet
    
    def to_dict(self) -> Dict:
        """转换为字典格式"""
        return {
            "path": str(self.file_path),
            "title": self.title,
            "headings": self.headings,
            "content_length": len(self.content),
        }

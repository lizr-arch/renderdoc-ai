"""
RST (reStructuredText) 文件解析器

支持优雅降级：
- 优先使用 docutils（如果已安装）
- 降级到纯正则解析
"""
import re
from pathlib import Path
from typing import Dict, List, Optional

# 尝试导入 docutils
try:
    from docutils.core import publish_doctree
    from docutils.nodes import Text, title as TitleNode, section
    HAS_DOCUTILS = True
except ImportError:
    HAS_DOCUTILS = False


class RstParser:
    """RST 文件解析器"""
    
    # RST 标题字符（按优先级排序）
    TITLE_CHARS = ['=', '-', '~', '^', '"', "'"]
    
    # 指令正则（用于清理）
    DIRECTIVE_PATTERN = re.compile(
        r'^\.\.\s+\w+::\s*.*?(?=\n(?!\s)|$)', 
        re.MULTILINE | re.DOTALL
    )
    
    # 代码块正则
    CODE_BLOCK_PATTERN = re.compile(
        r'::\s*\n\n((?:\s{3,}.*\n?)+)',
        re.MULTILINE
    )
    
    def __init__(self, file_path: Path):
        self.file_path = Path(file_path)
        self._content: Optional[str] = None
        self._title: Optional[str] = None
        self._headings: Optional[List[Dict]] = None
        self._use_docutils = HAS_DOCUTILS
    
    @property
    def content(self) -> str:
        """获取原始内容"""
        if self._content is None:
            self._content = self._read_file()
        return self._content
    
    @property
    def title(self) -> str:
        """获取文档标题"""
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
            return self.file_path.read_text(encoding='latin-1')
    
    def _extract_headings(self) -> None:
        """提取标题结构"""
        if self._use_docutils:
            self._extract_headings_docutils()
        else:
            self._extract_headings_regex()
    
    def _extract_headings_docutils(self) -> None:
        """使用 docutils 提取标题"""
        self._headings = []
        self._title = None
        
        try:
            doctree = publish_doctree(self.content)
            
            for node in doctree.traverse(TitleNode):
                text = node.astext()
                # 计算层级：基于 section 嵌套深度
                level = 1
                parent = node.parent
                while parent is not None:
                    if isinstance(parent, section):
                        level += 1
                    parent = parent.parent
                
                self._headings.append({
                    "level": level,
                    "text": text,
                    "position": 0,  # docutils 不提供位置
                })
                
                if self._title is None:
                    self._title = text
                    
        except Exception:
            # 降级到正则
            self._extract_headings_regex()
    
    def _extract_headings_regex(self) -> None:
        """使用正则提取标题"""
        self._headings = []
        self._title = None
        
        lines = self.content.split('\n')
        char_levels = {}  # 记录每种字符对应的层级
        
        i = 0
        while i < len(lines):
            line = lines[i]
            
            # 检查下一行是否是标题下划线
            if i + 1 < len(lines):
                next_line = lines[i + 1].strip()
                if next_line and len(set(next_line)) == 1:
                    char = next_line[0]
                    if char in self.TITLE_CHARS and len(next_line) >= len(line.strip()):
                        # 确定层级
                        if char not in char_levels:
                            char_levels[char] = len(char_levels) + 1
                        level = char_levels[char]
                        
                        heading = {
                            "level": level,
                            "text": line.strip(),
                            "position": sum(len(l) + 1 for l in lines[:i]),
                        }
                        self._headings.append(heading)
                        
                        if self._title is None:
                            self._title = line.strip()
                        
                        i += 2
                        continue
            
            # 检查上一行是否是标题上划线（双线标题）
            if i > 0 and i + 1 < len(lines):
                prev_line = lines[i - 1].strip()
                next_line = lines[i + 1].strip()
                if (prev_line and next_line and 
                    len(set(prev_line)) == 1 and 
                    len(set(next_line)) == 1 and
                    prev_line[0] == next_line[0]):
                    # 已在上一轮处理
                    pass
            
            i += 1
    
    def get_text_content(self) -> str:
        """获取纯文本内容（移除 RST 标记）"""
        text = self.content
        
        # 移除指令块
        text = self.DIRECTIVE_PATTERN.sub('', text)
        
        # 移除代码块
        text = self.CODE_BLOCK_PATTERN.sub('[CODE BLOCK]', text)
        
        # 移除内联标记
        text = re.sub(r':[\w:]+:`([^`]+)`', r'\1', text)  # :role:`text`
        text = re.sub(r'``([^`]+)``', r'\1', text)  # ``code``
        text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)  # **bold**
        text = re.sub(r'\*([^*]+)\*', r'\1', text)  # *italic*
        
        # 移除链接
        text = re.sub(r'`([^<`]+)\s*<[^>]+>`_', r'\1', text)  # `text <url>`_
        text = re.sub(r'`([^`]+)`_', r'\1', text)  # `text`_
        
        # 清理多余空行
        text = re.sub(r'\n{3,}', '\n\n', text)
        
        return text.strip()
    
    def get_snippet(self, query: str, context_chars: int = 200) -> Optional[str]:
        """获取包含查询词的摘要片段"""
        text = self.get_text_content().lower()
        query_lower = query.lower()
        
        pos = text.find(query_lower)
        if pos == -1:
            return None
        
        original = self.get_text_content()
        
        start = max(0, pos - context_chars // 2)
        end = min(len(original), pos + len(query) + context_chars // 2)
        
        snippet = original[start:end]
        
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
            "parser": "docutils" if self._use_docutils else "regex",
        }

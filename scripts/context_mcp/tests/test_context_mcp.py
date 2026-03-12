"""
Context MCP 单元测试
"""
import sys
from pathlib import Path

# 添加父目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pytest


class TestMarkdownParser:
    """Markdown 解析器测试"""
    
    def test_parse_heading(self):
        """测试标题解析"""
        from scripts.context_mcp.parsers.markdown_parser import MarkdownParser
        
        # 使用 AGENTS.md 作为测试文件
        test_file = Path(__file__).parent.parent.parent.parent / "AGENTS.md"
        if not test_file.exists():
            pytest.skip("AGENTS.md 不存在")
        
        parser = MarkdownParser(test_file)
        
        assert parser.title is not None
        assert len(parser.headings) > 0
        assert parser.headings[0]["level"] >= 1
    
    def test_get_text_content(self):
        """测试纯文本提取"""
        from scripts.context_mcp.parsers.markdown_parser import MarkdownParser
        
        test_file = Path(__file__).parent.parent.parent.parent / "README.md"
        if not test_file.exists():
            pytest.skip("README.md 不存在")
        
        parser = MarkdownParser(test_file)
        text = parser.get_text_content()
        
        assert len(text) > 0
        # 应该移除了 markdown 链接语法
        assert "](http" not in text or "[" not in text


class TestRstParser:
    """RST 解析器测试"""
    
    def test_parse_rst(self):
        """测试 RST 解析"""
        from scripts.context_mcp.parsers.rst_parser import RstParser
        
        # 查找一个 RST 文件
        docs_dir = Path(__file__).parent.parent.parent.parent / "docs"
        rst_files = list(docs_dir.glob("*.rst"))
        
        if not rst_files:
            pytest.skip("没有找到 RST 文件")
        
        parser = RstParser(rst_files[0])
        
        assert parser.title is not None
        assert parser.content is not None


class TestDocIndex:
    """文档索引测试"""
    
    def test_build_index(self):
        """测试索引构建"""
        from scripts.context_mcp.indexer import get_index
        
        index = get_index()
        index.build()
        
        topics = index.list_topics("all")
        assert len(topics) > 0
    
    def test_search(self):
        """测试搜索功能"""
        from scripts.context_mcp.indexer import get_index
        
        index = get_index()
        
        # 搜索常见词
        results = index.search("RenderDoc")
        assert len(results) > 0
    
    def test_read_doc(self):
        """测试文档读取"""
        from scripts.context_mcp.indexer import get_index
        
        index = get_index()
        
        doc = index.read_doc("AGENTS.md")
        
        if doc is None:
            pytest.skip("AGENTS.md 不在索引路径中")
        
        assert "content" in doc or "error" in doc
    
    def test_project_index(self):
        """测试项目索引"""
        from scripts.context_mcp.indexer import get_index
        
        index = get_index()
        
        project_index = index.get_project_index()
        
        assert "key_files" in project_index
        assert "summary" in project_index


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

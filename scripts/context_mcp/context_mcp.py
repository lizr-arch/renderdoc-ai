"""
RenderDoc Context MCP Server

提供项目文档和官方 Sphinx 文档的检索功能，帮助 AI 快速获取项目上下文。

使用方式:
    mcp dev context_mcp.py
    
或在 CodeMaker 中配置:
    {
        "mcpServers": {
            "RenderDocContext": {
                "command": "py",
                "args": ["-3", "-m", "mcp", "run", "scripts/context_mcp/context_mcp.py"]
            }
        }
    }
"""
import json
import os
import sys
from typing import Optional

from mcp.server.fastmcp import FastMCP

try:
    from .indexer import get_index
except ImportError:
    # Allow running via "mcp run <file>" where no package context exists.
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)
    from scripts.context_mcp.indexer import get_index

# 创建 MCP 服务器
mcp = FastMCP(
    "RenderDoc Context",
    instructions="""RenderDoc 项目上下文加载器 - 帮助 AI 快速获取项目文档和官方 API 文档。

可用工具:
- list_doc_topics: 列出文档主题
- search_docs: 搜索文档内容
- read_doc: 读取完整文档
- get_project_index: 获取项目关键索引

使用场景:
- 会话开始时调用 get_project_index 获取项目概览
- 需要查找特定功能时使用 search_docs
- 需要详细了解某文档时使用 read_doc
"""
)


@mcp.tool()
def list_doc_topics(
    category: str = "all"
) -> str:
    """
    列出可用的文档主题
    
    Args:
        category: 文档类别
            - "project": 项目分析文档 (docs/analysis/, plans/, etc.)
            - "sphinx": 官方 Sphinx 文档 (docs/*.rst)
            - "all": 所有文档
    
    Returns:
        JSON 格式的文档列表，包含路径、标题、标题层级
    """
    index = get_index()
    
    topics = index.list_topics(category)
    
    # 简化输出，只返回关键信息
    result = []
    for topic in topics:
        result.append({
            "path": topic.get("rel_path"),
            "title": topic.get("title"),
            "category": topic.get("category"),
        })
    
    return json.dumps({
        "count": len(result),
        "topics": result,
    }, ensure_ascii=False, indent=2)


@mcp.tool()
def search_docs(
    query: str,
    category: str = "all",
    max_results: int = 10
) -> str:
    """
    搜索文档内容
    
    Args:
        query: 搜索关键词（支持标题、路径、内容匹配）
        category: 文档类别 ("project" | "sphinx" | "all")
        max_results: 最大返回结果数
    
    Returns:
        JSON 格式的搜索结果，包含匹配文档和相关片段
    """
    index = get_index()
    
    results = index.search(query, category, max_results)
    
    # 格式化输出
    output = []
    for r in results:
        item = {
            "path": r.get("rel_path"),
            "title": r.get("title"),
            "score": r.get("score"),
            "category": r.get("category"),
        }
        if "snippet" in r:
            item["snippet"] = r["snippet"]
        output.append(item)
    
    return json.dumps({
        "query": query,
        "count": len(output),
        "results": output,
    }, ensure_ascii=False, indent=2)


@mcp.tool()
def read_doc(
    doc_path: str,
    text_only: bool = False
) -> str:
    """
    读取指定文档的完整内容
    
    Args:
        doc_path: 文档相对路径（如 "docs/analysis/PROJECT_INDEX.md"）
        text_only: 是否只返回纯文本（移除格式标记）
    
    Returns:
        JSON 格式的文档内容，包含标题、结构、正文
    """
    index = get_index()
    
    doc = index.read_doc(doc_path)
    
    if doc is None:
        return json.dumps({
            "error": f"文档不存在: {doc_path}",
        }, ensure_ascii=False)
    
    if "error" in doc:
        return json.dumps(doc, ensure_ascii=False)
    
    # 根据参数选择返回内容
    result = {
        "path": doc.get("path"),
        "title": doc.get("title"),
        "headings": doc.get("headings", []),
    }
    
    if text_only:
        result["content"] = doc.get("text_content", doc.get("content", ""))
    else:
        result["content"] = doc.get("content", "")
    
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool()
def get_project_index() -> str:
    """
    获取项目关键索引
    
    返回 AGENTS.md、PROJECT_INDEX.md 等核心文档的摘要，
    帮助 AI 快速建立项目上下文。
    
    推荐在会话开始时调用此工具。
    
    Returns:
        JSON 格式的项目索引，包含关键文件列表和文档统计
    """
    index = get_index()
    
    project_index = index.get_project_index()
    
    return json.dumps(project_index, ensure_ascii=False, indent=2)


# 启动入口
if __name__ == "__main__":
    mcp.run()

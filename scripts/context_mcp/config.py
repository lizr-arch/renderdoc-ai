"""
Context MCP 配置文件

定义文档扫描路径、索引配置等
"""
from pathlib import Path

# 项目根目录（相对于此文件）
PROJECT_ROOT = Path(__file__).parent.parent.parent

# 文档索引配置
DOC_SOURCES = {
    "project": {
        "name": "项目分析文档",
        "paths": [
            "docs/analysis",
            "docs/research",
            "plans",
            "scripts/rdc_analyzer/docs",
            "scripts/context_mcp/docs",
        ],
        "extensions": [".md"],
    },
    "sphinx": {
        "name": "官方 Sphinx 文档",
        "paths": [
            "docs",
        ],
        "extensions": [".rst"],
        "exclude_patterns": [
            "docs/analysis",  # 避免重复
            "docs/research",
            "docs/debug",
        ],
    },
}

# 关键索引文件（用于 get_project_index）
KEY_INDEX_FILES = [
    "AGENTS.md",
    "docs/analysis/PROJECT_INDEX.md",
    "docs/analysis/codex_rdc_analyzer/DOC_INDEX.md",
    "scripts/rdc_analyzer/docs/INDEX.md",
]

# 搜索配置
SEARCH_CONFIG = {
    "max_results": 20,
    "snippet_length": 200,  # 摘要片段长度（字符）
    "context_lines": 3,     # 匹配行上下文
}

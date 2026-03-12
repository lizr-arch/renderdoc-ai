# RenderDoc Context MCP

帮助 AI 快速获取 RenderDoc 项目文档和官方 API 文档的 MCP 服务器。

## 功能

| 工具 | 说明 |
|------|------|
| `list_doc_topics` | 列出文档主题（项目文档/Sphinx 文档） |
| `search_docs` | 搜索文档内容 |
| `read_doc` | 读取完整文档 |
| `get_project_index` | 获取项目关键索引（推荐会话开始时调用） |

## 使用方式

### 开发测试

```bash
cd scripts/context_mcp
mcp dev context_mcp.py
```

### CodeMaker 配置

在 `.codemaker/mcp.json` 中添加：

```json
{
  "mcpServers": {
    "RenderDocContext": {
      "command": "py",
      "args": ["-3", "-m", "mcp", "run", "scripts/context_mcp/context_mcp.py"],
      "cwd": "d:\\Code\\git\\renderdoc"
    }
  }
}
```

## 数据源

### 项目文档 (category: "project")
- `docs/analysis/` - 项目分析文档
- `docs/research/` - 调研文档
- `plans/` - 开发计划
- `scripts/rdc_analyzer/docs/` - 工具文档

### 官方 Sphinx 文档 (category: "sphinx")
- `docs/*.rst` - 官方文档
- `docs/python_api/*.rst` - Python API 文档

## 依赖

- Python 3.10+
- `mcp[cli]` (FastMCP)
- `docutils` (可选，用于更精确的 RST 解析)

## 文件结构

```
scripts/context_mcp/
├── __init__.py
├── context_mcp.py      # MCP 主入口
├── indexer.py          # 文档索引构建器
├── config.py           # 配置
├── parsers/
│   ├── __init__.py
│   ├── markdown_parser.py
│   └── rst_parser.py
├── plans/              # 开发计划
└── README.md
```

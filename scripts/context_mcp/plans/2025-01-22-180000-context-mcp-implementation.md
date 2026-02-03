# Context MCP 实现计划

> **创建时间**: 2025-01-22  
> **Agent**: Codex-Main  
> **状态**: ✅ 已完成

## Scope

构建 `scripts/context_mcp/` 独立 MCP 服务器，提供项目文档和官方 Sphinx 文档的检索功能。

## Assumptions

1. 使用 FastMCP 框架（与现有 rdc_mcp 一致）
2. RST 解析采用优雅降级：有 docutils 用 docutils，否则用正则
3. 不含代码搜索功能

## Task Checklist

### Phase 1: 基础结构
- [x] 创建目录结构 `scripts/context_mcp/`
- [x] 创建 `config.py` - 路径配置
- [x] 创建 `parsers/__init__.py`
- [x] 创建 `parsers/markdown_parser.py`
- [x] 创建 `parsers/rst_parser.py`（正则 + docutils 降级）

### Phase 2: 核心功能
- [x] 创建 `indexer.py` - 文档索引构建
- [x] 创建 `context_mcp.py` - FastMCP 主入口
- [x] 实现 `list_doc_topics` 工具
- [x] 实现 `search_docs` 工具
- [x] 实现 `read_doc` 工具
- [x] 实现 `get_project_index` 工具

### Phase 3: 测试与文档
- [x] 创建 `tests/test_context_mcp.py`
- [x] 创建 `README.md`
- [x] 验证：`py -3 -m pytest tests/ -v` → 7/7 通过

## Risks/Blockers

| 风险 | 缓解措施 |
|------|----------|
| RST 复杂指令解析不完整 | 正则提取核心内容，忽略高级指令 |
| 大文件索引性能 | 启动时构建缓存，按需刷新 |

## Verification / Acceptance

1. 所有 4 个工具可通过 `mcp dev context_mcp.py` 调用
2. 能正确返回 `docs/analysis/PROJECT_INDEX.md` 内容
3. 能搜索 `docs/python_api/` 下的 RST 文件
4. 单元测试全部通过

## Next Steps

~~执行 `/do` 阶段，按 Checklist 顺序实现。~~

**完成时间**: 2025-01-22
**测试结果**: 7/7 通过

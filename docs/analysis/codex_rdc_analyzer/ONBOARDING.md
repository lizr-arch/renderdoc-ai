# AI 会话快速恢复指南（5 分钟入门）

> **版本**: 1.0.0 | **更新**: 2025-02-05  
> **目标**: 帮助新的大模型对话在 5 分钟内恢复项目上下文

---

## 🚀 第一步：调用 Context MCP

```
→ 调用 get_project_index
```

这会返回项目关键文件索引和文档统计，建立基础上下文。

---

## 📚 必读文档（按优先级排序）

| 优先级 | 文档 | 阅读时间 | 内容 |
|--------|------|----------|------|
| ⭐⭐⭐ | `AGENTS.md` | 3 min | AI 协作规范、命令列表、项目核心目标 |
| ⭐⭐⭐ | `scripts/rdc_analyzer/docs/INDEX.md` | 2 min | 工具文档索引、架构图、功能导航 |
| ⭐⭐ | `DEVELOPMENT_MILESTONES.md` | 5 min | 已完成里程碑 (M1/M2/M3)、功能清单 |
| ⭐⭐ | `EVIDENCE_CHAIN.md` | 2 min | 跨页面导航架构（最新功能） |
| ⭐ | `WORK_SUMMARY_2025-01-21.md` | 1 min | 文档索引总览 |

---

## 🔧 关键入口文件

### 分析脚本

| 脚本 | 用途 | 示例 |
|------|------|------|
| `rdc_to_bundle_report.py` | RDC → 4页报告包 | `py -3 rdc_to_bundle_report.py input.rdc -o output/` |
| `xml_to_bundle.py` | XML → 报告包 | `py -3 xml_to_bundle.py input.xml -o output/` |
| `analyze_xml_report.py` | XML → 单页报告 | `py -3 analyze_xml_report.py input.xml -o report.html` |
| `compare_rdc.py` | 双帧对比 | `py -3 compare_rdc.py base.rdc target.rdc` |

### 导出工具

| 脚本 | 用途 |
|------|------|
| `export_textures.py` | 批量纹理导出 |
| `extract_shaders.py` | Shader 提取 |
| `offline_extract_textures.py` | 无 GPU 纹理提取 |

---

## 🏗️ 当前架构（v2.4.0）

```
┌─────────────────────────────────────────────────────────────┐
│                     Bundle 报告架构                          │
├──────────┬──────────┬──────────┬──────────┬────────────────┤
│ index    │ events   │ textures │ shaders  │ recommendations│
│ .html    │ .html    │ .html    │ .html    │ .html          │
├──────────┴──────────┴──────────┴──────────┴────────────────┤
│                    跨页面证据链导航                          │
│  Texture → Event (M1)                                       │
│  Event → Shader (M2)                                        │
│  Shader → Event/Texture (M3)                                │
├─────────────────────────────────────────────────────────────┤
│               common.css + navigation.js                    │
└─────────────────────────────────────────────────────────────┘
```

---

## 📋 常见任务索引

### 🎯 分析 RDC 文件

```bash
# 步骤 1: RDC → XML
renderdoccmd.exe convert -c xml -o capture.xml capture.rdc

# 步骤 2: XML → Bundle 报告
py -3 scripts/rdc_analyzer/xml_to_bundle.py capture.xml -o output/
```

### 🔍 查找特定功能代码

```bash
# 使用 MCP 搜索文档
→ 调用 search_docs("纹理导出")
→ 调用 search_docs("证据链")

# 使用 rg 搜索代码
rg -n "EvidenceChainBuilder" scripts/rdc_analyzer/
```

### 📝 修改报告模板

- HTML 模板: `scripts/rdc_analyzer/templates/`
- CSS 样式: `scripts/rdc_analyzer/assets/styles/`
- JS 脚本: `scripts/rdc_analyzer/assets/scripts/`

### 🧪 运行测试

```bash
py -3 -m pytest scripts/rdc_analyzer/tests/ -v --tb=short
```

---

## ⚠️ 重要约定

1. **Python 版本**: 必须使用 `py -3`（本机 `python` 指向 2.7）
2. **编辑大文件**: >300 行使用 `replace_in_file`，≤300 行使用 `edit_file`
3. **Git 提交**: 完成功能后立即提交，使用 Conventional Commits 格式
4. **禁止修改**: `renderdoc/3rdparty/`、`build*/` 目录

---

## 🔗 MCP 工具快速参考

| 工具 | 用途 | 调用时机 |
|------|------|----------|
| `get_project_index` | 获取项目索引 | **会话开始必调** |
| `search_docs` | 搜索文档内容 | 查找功能/类/概念 |
| `read_doc` | 读取完整文档 | 深入了解某个主题 |
| `list_doc_topics` | 列出文档主题 | 浏览可用文档 |

---

## 📊 项目状态速查

| 指标 | 数值 |
|------|------|
| 项目文档 | ~181 个 |
| 官方 Sphinx 文档 | ~97 个 |
| 测试用例 | 682+ |
| 里程碑 | M1 + M2 + M3 已完成 |
| 工具版本 | v2.4.0 |

---

## 🎯 快速恢复检查清单

- [ ] 调用 `get_project_index` 建立上下文
- [ ] 确认任务类型（分析/开发/文档）
- [ ] 查找相关文档：`search_docs("关键词")`
- [ ] 确认工作目录：`d:\Code\git\renderdoc`
- [ ] 检查是否有未完成的 plan.md

---

**文档结束** | 如有疑问，使用 `search_docs` 或查阅 `AGENTS.md`

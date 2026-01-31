# RDC Analyzer 文档索引

> **更新日期**: 2026-01-31 | **维护**: Codex Agent

本目录包含 `rdc_analyzer` 工具的技术文档。

---

## 快速导航（按主题）

### 🏗️ 架构与设计
| 文档 | 说明 | 关键词 |
|------|------|--------|
| [ARCHITECTURE_V1.md](ARCHITECTURE_V1.md) | 模块架构与数据流 | 架构, 模块, 数据流 |
| [REFACTOR_ANALYSIS.md](REFACTOR_ANALYSIS.md) | 重构分析与优化建议 | 重构, 分析, 优化 |

### 📊 功能指南
| 文档 | 说明 | 关键词 |
|------|------|--------|
| [TEXTURE_EXTRACTION.md](TEXTURE_EXTRACTION.md) | **纹理提取三方案速查** | 纹理, 导出, SaveTexture, renderdoccmd |
| [UNITY_EXPORT.md](UNITY_EXPORT.md) | Unity 资产导出指南 | Unity, 导出, mesh, shader |
| [MALI_INTEGRATION_SUMMARY.md](MALI_INTEGRATION_SUMMARY.md) | Mali GPU 分析集成 | Mali, GPU, 性能分析 |

### 📝 格式与规范
| 文档 | 说明 | 关键词 |
|------|------|--------|
| [rdc_format_spec.md](rdc_format_spec.md) | RDC 文件格式规范 | RDC, 二进制, Section, Chunk |
| [GPU_COMPATIBILITY_ANALYSIS.md](GPU_COMPATIBILITY_ANALYSIS.md) | **GPU 兼容性分析**：为什么 RDC 无法跨 GPU 解析（源码证据） | GPU, 兼容性, 跨平台, APIHardwareUnsupported |

### 🔧 环境与验证
| 文档 | 说明 | 关键词 |
|------|------|--------|
| [P4_ENVIRONMENT_VERIFICATION.md](P4_ENVIRONMENT_VERIFICATION.md) | P4 环境验证流程 | 环境, P4, 验证 |
| [MILESTONE_SUMMARY.md](MILESTONE_SUMMARY.md) | 里程碑总结 | 里程碑, 进度, 总结 |
| [PROGRESS_REPORT.md](PROGRESS_REPORT.md) | 进度报告 | 进度, 报告 |

### 📋 待办与规划
| 文档 | 说明 | 关键词 |
|------|------|--------|
| [TODO.md](TODO.md) | 待办事项列表 | TODO, 任务, 待办 |

---

## 常见问题速查

| 问题 | 答案位置 |
|------|----------|
| 如何从 RDC 提取纹理？ | [TEXTURE_EXTRACTION.md](TEXTURE_EXTRACTION.md) |
| RDC 文件结构是什么？ | [rdc_format_spec.md](rdc_format_spec.md) |
| 如何导出 Unity 资产？ | [UNITY_EXPORT.md](UNITY_EXPORT.md) |
| Mali 分析如何集成？ | [MALI_INTEGRATION_SUMMARY.md](MALI_INTEGRATION_SUMMARY.md) |
| 代码架构是什么？ | [ARCHITECTURE_V1.md](ARCHITECTURE_V1.md) |
| **为什么 RDC 无法跨 GPU 解析？** | [GPU_COMPATIBILITY_ANALYSIS.md](GPU_COMPATIBILITY_ANALYSIS.md) |

---

## 关联文档（其他目录）

| 路径 | 说明 |
|------|------|
| [docs/analysis/codex_rdc_analyzer/DOC_INDEX.md](../../../docs/analysis/codex_rdc_analyzer/DOC_INDEX.md) | **总索引入口**（推荐先读） |
| [docs/analysis/codex_rdc_analyzer/WORK_SUMMARY_*.md](../../../docs/analysis/codex_rdc_analyzer/) | 工作总结系列文档 |
| [docs/analysis/gpu-replay-architecture.md](../../../docs/analysis/gpu-replay-architecture.md) | GPU 回放架构 |
| [docs/analysis/gpu-dependency-solutions.md](../../../docs/analysis/gpu-dependency-solutions.md) | GPU 依赖解决方案 |

---

## 维护约定

1. **新增文档**必须更新本索引
2. **每条索引**包含：链接、说明、关键词
3. **关键词**用于搜索（`rg "关键词" docs/`）

# WORK_SUMMARY — 索引（RDC Analyzer 总览）

- WHAT: 作为 `codex_rdc_analyzer` 的总索引入口。
- WHY: 原 WORK_SUMMARY 过长，拆分后便于维护与阅读。
- HOW: 按主题分拆为 5 份文档，本页提供阅读顺序与职责说明。

## 推荐阅读顺序
1. `WORK_SUMMARY_ARCH.md` — 架构/模块/文件结构
2. `WORK_SUMMARY_ROUTES.md` — A/B/C 路线 + 导出流程 + 验证状态
3. `WORK_SUMMARY_SCHEMA.md` — Schema / Pipeline / Bridge
4. `WORK_SUMMARY_VERIFICATION.md` — 真实性验证 + CLI 用法
5. `WORK_SUMMARY_ROADMAP.md` — 任务优先级 + 决策 + 参考
6. `WORK_SUMMARY_BUILD.md` — **编译环境 + Python 3.6 + Sphinx 文档**

## 文档索引
- `WORK_SUMMARY_ARCH.md`
- `WORK_SUMMARY_ROUTES.md`
- `WORK_SUMMARY_SCHEMA.md`
- `WORK_SUMMARY_VERIFICATION.md`
- `WORK_SUMMARY_ROADMAP.md`
- `WORK_SUMMARY_BUILD.md`

## 维护约定
- 本索引文件保持 < 200 行。
- 单个主题文档保持 < 800 行。
- 新增内容先归类到主题文档，再更新本索引。

## 迁移说明
- 原 `WORK_SUMMARY_2025-01-21.md` 已拆分，历史内容未删，仅重新分类。
- "RDC → XML → HTML" 流程已集中在 `WORK_SUMMARY_ROUTES.md`。

## 快速入口

### 编译 & 环境
| 操作 | 命令/文档 |
|------|----------|
| **一键编译** | `scripts/_build_renderdoc.bat` |
| **验证 Python API** | `scripts/_test_py36.bat` |
| **构建 Sphinx 文档** | `scripts/_build_sphinx_docs.bat` |
| **查看本地文档** | `start Documentation\html\index.html` |
| **详细指南** | `WORK_SUMMARY_BUILD.md` 第 12 节 |

### Sphinx 是什么？
Sphinx 是 Python 官方文档使用的生成工具，RenderDoc 用它自动从 `renderdoc.pyd` 提取 API 文档。我们已成功在本地构建完整文档，详见 `WORK_SUMMARY_BUILD.md` 第 12 节。

### Python 3.6 为什么必需？
RenderDoc 的 `renderdoc.pyd` 编译时链接了 Python 3.6，不兼容其他版本。详见 `WORK_SUMMARY_BUILD.md` 第 4-6 节。
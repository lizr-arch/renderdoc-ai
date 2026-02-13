# RDC Analyzer 文档索引



> **更新日期**: 2026-02-13 | **版本**: 2.6.4 | **维护**: Codex Agent



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

| [EXPORT_ROUTES.md](EXPORT_ROUTES.md) | **RDC 报告导出路线图** - 新增 one_click 一键导出（zip.xml 优先 + xml 回退 + headless smoke）⭐ | 导出路线, one-click, Bundle, zip.xml, 无GPU |
| [ONE_CLICK_ACCEPTANCE.md](ONE_CLICK_ACCEPTANCE.md) | **One-click 验收清单**（v1.0.0）- 一键导出流程/判定标准/时序图 | one-click, 验收, checklist, smoke |
| [UI_XML_BUNDLE_UPDATE_2026-02-08.md](UI_XML_BUNDLE_UPDATE_2026-02-08.md) | **UI + xml_to_bundle 更新记录**（v2.6.1）- 仪表盘 UI 统一 + ZIP 缩略图 + Vulkan Shader 提取 | UI, dashboard, xml_to_bundle, zip, rdc, spirv-cross |
| [VISUAL_ACCEPTANCE_CHECKLIST.md](VISUAL_ACCEPTANCE_CHECKLIST.md) | **一页式视觉验收清单**（v1.0.0）- 专业仪表盘验收评分 + 缺陷分级模板 | 验收, 视觉, dashboard, UX, checklist |
| [VISUAL_ACCEPTANCE_RESULT_TEMPLATE.md](VISUAL_ACCEPTANCE_RESULT_TEMPLATE.md) | **视觉验收结果填写版**（v1.0.0）- 一页回填评分/缺陷/结论，便于闭环 | 验收, 结果, 模板, checklist |
| [BATCH_EXPORT.md](BATCH_EXPORT.md) | **纹理批量导出 CLI** - 一键导出所有纹理 (v1.4.0) | 批量导出, CLI, gallery, manifest |
| [D3D11_SUPPORT.md](D3D11_SUPPORT.md) | **D3D11 纹理提取** - 支持 DirectX 11 离线提取 (v1.5.0) | D3D11, DirectX, DXGI, 离线提取 |

| [TEXTURE_EXTRACTION.md](TEXTURE_EXTRACTION.md) | **纹理提取三方案速查** | 纹理, 导出, SaveTexture, renderdoccmd |

| [TEXTURE_DECODERS.md](TEXTURE_DECODERS.md) | **纹理解码器模块** (v1.3.0) - 48种格式支持 | 解码, BCn, ASTC, ETC2, PNG, decode_texture |

| [NO_GPU_TEXTURE_EXTRACTION.md](NO_GPU_TEXTURE_EXTRACTION.md) | **无 GPU 纹理提取技术分析** | 无GPU, GetStructuredData, SDFile, buffers |

| [UNITY_EXPORT.md](UNITY_EXPORT.md) | Unity 资产导出指南 | Unity, 导出, mesh, shader |
| [FBX_EXPORT.md](FBX_EXPORT.md) | **FBX 导出流水线**（OBJ 中间态 → Unity/Unreal） | FBX, OBJ, Unity, Unreal |
| [UNITY_IMPORT.md](UNITY_IMPORT.md) | **Unity 导入需求**（官方文档要点） | Unity, 导入, FBX, ShaderLab |
| [UNREAL_IMPORT.md](UNREAL_IMPORT.md) | **Unreal 导入需求**（官方文档要点） | Unreal, 导入, FBX, PBR |
| [MESH_SHADER_EXTRACTION.md](MESH_SHADER_EXTRACTION.md) | Mesh/Shader 导出指南 | mesh, vb, ib, shader |
| [INTERMEDIATE_FORMAT.md](INTERMEDIATE_FORMAT.md) | **XML/ZIP 中间态格式** - 单 Event 输出 | intermediate, schema, zip.xml |
| [ZIPXML_EVENT_EXTRACTION.md](ZIPXML_EVENT_EXTRACTION.md) | **ZIPXML 单事件离线导出指南**（Vulkan）- 数据来源/CLI/schema/限制 | zip.xml, event, vb, ib, offline |
| [EVENT_IMPORT_BUNDLE.md](EVENT_IMPORT_BUNDLE.md) | **Event Import Bundle 导出指南**（single event 闭环） | intermediate, obj, materials, shaders, textures |
| [EVENT_ASSET_ORCHESTRATOR.md](EVENT_ASSET_ORCHESTRATOR.md) | **Event 资产编排器（M1）** - 一条命令串联 intermediate/bundle/fbx + artifact_index | orchestrator, artifact_index, pipeline |
| [FEATURE_COST_BASELINE.md](FEATURE_COST_BASELINE.md) | **功能成本基线**（防重复开发）- 已实现能力 + 成本 + 复用建议 | baseline, cost, capability, reuse |
| [AI_SCRIPT_BOUNDARY.md](AI_SCRIPT_BOUNDARY.md) | **AI 与脚本职责边界** - 明确哪些必须脚本化、哪些可 AI 增强 | ai, boundary, orchestration |
| [SKILL_RDC_EVENT_ASSET_ORCHESTRATOR_SPEC.md](SKILL_RDC_EVENT_ASSET_ORCHESTRATOR_SPEC.md) | **Skill 设计规范** - Event 资产编排器输入输出与失败恢复 | skill, orchestrator, artifact_index |
| [MESSIAH_IMPORT_STATUS.md](MESSIAH_IMPORT_STATUS.md) | **Messiah 导入现状与缺口**（Phase-1 入口） | messiah, import_bundle, repository |

| [MALI_INTEGRATION_SUMMARY.md](MALI_INTEGRATION_SUMMARY.md) | Mali GPU 分析集成 | Mali, GPU, 性能分析 |



### 🚀 无 GPU 纹理提取（新）

| 文档 | 说明 | 关键词 |

|------|------|--------|

| [NO_GPU_TEXTURE_EXTRACTION_ARCHITECTURE.md](NO_GPU_TEXTURE_EXTRACTION_ARCHITECTURE.md) | **架构设计**：问题背景、方案对比、三步提取流程 | 无GPU, 架构, ZIP+XML, InitialContents |

| [RDC_STRUCTURE_DEEP_ANALYSIS.md](RDC_STRUCTURE_DEEP_ANALYSIS.md) | **RDC 结构深度分析**：Chunk/Section 布局、Vulkan 资源映射链路 | RDC, Chunk, SystemChunk, vkCreateImage |

| [NO_GPU_EXTRACTION_IMPLEMENTATION_GUIDE.md](NO_GPU_EXTRACTION_IMPLEMENTATION_GUIDE.md) | **实现指南**：工具使用、API 示例、格式处理、常见问题 | extract_texture_from_zipxml, BC7, 实现 |

| [NO_GPU_EXTRACTION_ROADMAP.md](NO_GPU_EXTRACTION_ROADMAP.md) | **功能路线图**：当前状态、短期/中期/长期目标、技术挑战 | 路线图, v1.x, v2.x, D3D11, 软件回放 |



### 🔗 证据链与交互 (v2.4.0 新增)

| 文档 | 说明 | 关键词 |
|------|------|--------|
| [EVIDENCE_CHAIN.md](EVIDENCE_CHAIN.md) | **跨页面证据链** - M1/M2/M3 里程碑实现 | 证据链, 跨页跳转, URL参数, 高亮 |

**功能摘要**：
- **M1** (Texture → Event)：纹理卡片点击跳转到 Events 页面对应 Draw Call
- **M2** (Event → Shader)：Events 页面跳转到 Shaders 页面对应 Shader
- **M3** (Shader → Event/Texture)：Shader 详情跳转回关联的 Event 或 Texture

**技术实现**：
- URL 参数传递：`?id=468&highlight=true`
- 自动滚动定位 + CSS 脉冲高亮动画
- 支持离线 HTML 报告

### 🎨 高级可视化功能 (v2.6.2 新增)

| 文档 | 说明 | 关键词 |
|------|------|--------|
| [UI_FEATURES_GUIDE.md](UI_FEATURES_GUIDE.md) | **UI 功能使用指南** - M4.1 热力图 / M4.2 Pass 分组 / Phase 7C 外部数据 ⭐ | 热力图, Pass分组, 外部数据, UI, 可视化 |

**功能摘要**：
- **M4.1** 资源绑定热力图：可视化纹理/Buffer 使用模式（FIRST_USE/CONTINUOUS/SPARSE/ISOLATED）
- **M4.2** Pass 分组视图：基于 Debug Markers 的层级事件分组
- **Phase 7C** 外部数据加载：JSON 数据分离，HTML 大小减少 84%

**使用入口**：
- 🔥 绑定热力图 按钮（events.html 顶部）
- 📁 Pass 分组 按钮（events.html 底部）
- `--external-data` CLI 标志

### 🐛 问题诊断与调试

| 文档 | 说明 | 关键词 |
|------|------|--------|
| [VULKAN_TEXTURE_ALIASING_ISSUE.md](VULKAN_TEXTURE_ALIASING_ISSUE.md) | **Vulkan 纹理别名问题**：SaveTexture API 在内存别名场景下返回错误数据的诊断与修复 ⭐ | Vulkan, 内存别名, SaveTexture, ThumbnailGenerator, ef_r8 |

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



### � 统计对比与 CI (v2.5.0 新增)

| 文档 | 说明 | 关键词 |
|------|------|--------|
| [MULTI_FRAME_GUIDE.md](MULTI_FRAME_GUIDE.md) | **多帧统计对比使用指南** - Phase 5 完整功能 ⭐ | 多帧采样, 显著性检测, CI集成, JUnit |
| [API_REFERENCE.md](API_REFERENCE.md) | **API 参考手册** - 模块接口说明 | API, stats, diff, rules, CLI |

**Phase 5 功能摘要**:
- **P5.1** 多帧采样：`--samples N` 收集统计数据
- **P5.2** 显著性检测：Welch's t-test + Cohen's d
- **P5.3** 语义对齐：`--align-strategy marker` 支持新增/删除事件
- **P5.4** CI 集成：`--junit-xml` 生成 JUnit 报告

### �📋 待办与规划

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
| 如何导出 FBX 资产？ | [FBX_EXPORT.md](FBX_EXPORT.md) |
| 如何导入 Unity 资产？ | [UNITY_IMPORT.md](UNITY_IMPORT.md) |
| 如何导入 Unreal 资产？ | [UNREAL_IMPORT.md](UNREAL_IMPORT.md) |
| 如何导出 Mesh/Shader？ | [MESH_SHADER_EXTRACTION.md](MESH_SHADER_EXTRACTION.md) |
| 如何避免重复开发？ | [FEATURE_COST_BASELINE.md](FEATURE_COST_BASELINE.md) |
| 哪些工作该由脚本做、哪些可以交给 AI？ | [AI_SCRIPT_BOUNDARY.md](AI_SCRIPT_BOUNDARY.md) |
| Skill 编排契约在哪里？ | [SKILL_RDC_EVENT_ASSET_ORCHESTRATOR_SPEC.md](SKILL_RDC_EVENT_ASSET_ORCHESTRATOR_SPEC.md) |
| 如何一键串联 intermediate/bundle/fbx？ | [EVENT_ASSET_ORCHESTRATOR.md](EVENT_ASSET_ORCHESTRATOR.md) |
| 如何按引擎目标定制导出（unity/unreal/messiah）？ | [EVENT_ASSET_ORCHESTRATOR.md](EVENT_ASSET_ORCHESTRATOR.md) |

| Mali 分析如何集成？ | [MALI_INTEGRATION_SUMMARY.md](MALI_INTEGRATION_SUMMARY.md) |

| 代码架构是什么？ | [ARCHITECTURE_V1.md](ARCHITECTURE_V1.md) |

| **为什么 RDC 无法跨 GPU 解析？** | [GPU_COMPATIBILITY_ANALYSIS.md](GPU_COMPATIBILITY_ANALYSIS.md) |

| **如何无 GPU 提取纹理？** | [NO_GPU_TEXTURE_EXTRACTION.md](NO_GPU_TEXTURE_EXTRACTION.md) |
| **如何提取 D3D11 纹理？** | [D3D11_SUPPORT.md](D3D11_SUPPORT.md) |

| **无 GPU 提取的详细架构？** | [NO_GPU_TEXTURE_EXTRACTION_ARCHITECTURE.md](NO_GPU_TEXTURE_EXTRACTION_ARCHITECTURE.md) |

| **RDC 内部结构详解？** | [RDC_STRUCTURE_DEEP_ANALYSIS.md](RDC_STRUCTURE_DEEP_ANALYSIS.md) |

| **如何使用提取工具？** | [NO_GPU_EXTRACTION_IMPLEMENTATION_GUIDE.md](NO_GPU_EXTRACTION_IMPLEMENTATION_GUIDE.md) |

| **无 GPU 提取未来规划？** | [NO_GPU_EXTRACTION_ROADMAP.md](NO_GPU_EXTRACTION_ROADMAP.md) |

| **如何解码压缩纹理？** | [TEXTURE_DECODERS.md](TEXTURE_DECODERS.md) |

| **支持哪些纹理格式？** | [TEXTURE_DECODERS.md](TEXTURE_DECODERS.md) (48种: BC1-7, ASTC, ETC2等) |
| **如何选择报告导出路线？** | [EXPORT_ROUTES.md](EXPORT_ROUTES.md) ⭐ |
| **如何一条命令从 RDC 生成 Bundle（含回退）？** | [EXPORT_ROUTES.md](EXPORT_ROUTES.md) (one_click 章节) ⭐ |
| **如何双击直接生成 Endfield 报告？** | [EXPORT_ROUTES.md](EXPORT_ROUTES.md) (one_click 预设入口) |
| **One-click 工作流如何验收/回归？** | [ONE_CLICK_ACCEPTANCE.md](ONE_CLICK_ACCEPTANCE.md) ⭐ |
| **如何进行多帧统计对比？** | [MULTI_FRAME_GUIDE.md](MULTI_FRAME_GUIDE.md) ⭐ |
| **如何集成 CI/CD 回归门禁？** | [MULTI_FRAME_GUIDE.md](MULTI_FRAME_GUIDE.md) (JUnit XML 输出) |
| **API 接口文档在哪？** | [API_REFERENCE.md](API_REFERENCE.md) |
| **本轮 UI / xml_to_bundle 更新说明？** | [UI_XML_BUNDLE_UPDATE_2026-02-08.md](UI_XML_BUNDLE_UPDATE_2026-02-08.md) ⭐ |
| **如何做 Bundle 报告视觉验收？** | [VISUAL_ACCEPTANCE_CHECKLIST.md](VISUAL_ACCEPTANCE_CHECKLIST.md) ⭐ |
| **视觉验收结果怎么记录？** | [VISUAL_ACCEPTANCE_RESULT_TEMPLATE.md](VISUAL_ACCEPTANCE_RESULT_TEMPLATE.md) ⭐ |
| **端到端工作流指南？** | [E2E_WORKFLOW_GUIDE.md](E2E_WORKFLOW_GUIDE.md) ⭐ |
| **数据 Schema 验证？** | [E2E_WORKFLOW_GUIDE.md](E2E_WORKFLOW_GUIDE.md) (JSON Schema 章节) |
| **如何使用热力图功能？** | [UI_FEATURES_GUIDE.md](UI_FEATURES_GUIDE.md) (M4.1 章节) ⭐ |
| **如何使用 Pass 分组？** | [UI_FEATURES_GUIDE.md](UI_FEATURES_GUIDE.md) (M4.2 章节) ⭐ |
| **如何启用外部数据加载？** | [UI_FEATURES_GUIDE.md](UI_FEATURES_GUIDE.md) (Phase 7C 章节) |
| **Vulkan 缩略图显示错误？** | [VULKAN_TEXTURE_ALIASING_ISSUE.md](VULKAN_TEXTURE_ALIASING_ISSUE.md) ⭐ |
| **SaveTexture 返回错误数据？** | [VULKAN_TEXTURE_ALIASING_ISSUE.md](VULKAN_TEXTURE_ALIASING_ISSUE.md) (内存别名章节) |



### 🔒 数据完整性与验证 (v2.6.0 新增)

| 文档 | 说明 | 关键词 |
|------|------|--------|
| [E2E_WORKFLOW_GUIDE.md](E2E_WORKFLOW_GUIDE.md) | **端到端工作流指南** - RDC→XML→Bundle 完整流程 ⭐ | E2E, 工作流, CI/CD, Schema |

**Phase 6 (P0 报告完善) 功能摘要**:
- **P0.1** 纹理缩略图：从 ZIP 提取 + 解码 + 生成 PNG
- **P0.2** Shader 源码：Vulkan SPIR-V → GLSL 转换
- **P0.3** RT 快照：RenderTarget 可视化 (RDC API 路径)
- **P0.4** JSON Schema：数据完整性验证 (`--validate` 选项)

**Schema 文件位置**: `scripts/rdc_analyzer/schema/`
| Schema | 验证目标 |
|--------|----------|
| `textures_data.schema.json` | 纹理数据结构 |
| `events_data.schema.json` | 事件数据结构 |
| `shaders_data.schema.json` | Shader 数据结构 |
| `report_bundle.schema.json` | Bundle 报告结构 |
| `comparison_result.schema.json` | 对比结果结构 |

---



## 关联文档（其他目录）



| 路径 | 说明 |

|------|------|

| [docs/analysis/codex_rdc_analyzer/DOC_INDEX.md](../../../docs/analysis/codex_rdc_analyzer/DOC_INDEX.md) | **总索引入口**（推荐先读） |

| [docs/analysis/codex_rdc_analyzer/WORK_SUMMARY_*.md](../../../docs/analysis/codex_rdc_analyzer/) | 工作总结系列文档 |

| [docs/analysis/gpu-replay-architecture.md](../../../docs/analysis/gpu-replay-architecture.md) | GPU 回放架构 |

| [docs/analysis/gpu-dependency-solutions.md](../../../docs/analysis/gpu-dependency-solutions.md) | GPU 依赖解决方案 |



---



## 📁 Assets 资源目录结构

> **v2.3.0 新增**：CSS/JS 从 Python 中分离，实现关注点分离

```
scripts/rdc_analyzer/assets/
├── styles/                          # CSS 样式文件
│   ├── html_reporter.css            # html_reporter.py 使用
│   ├── simple_report.css            # generate_simple_report.py 使用
│   ├── sample_report.css            # generate_sample_report.py 使用（Mali Shader）
│   └── texture_gallery.css          # export_textures.py 使用
│
├── scripts/                         # JavaScript 文件
│   ├── simple_report.js             # generate_simple_report.py 使用
│   └── sample_report.js             # generate_sample_report.py 使用（Mali Shader）
│
└── fonts/                           # 字体文件（预留）
```

### 资源加载模式

所有独立脚本使用统一的 `_load_asset()` 辅助函数：

```python
from pathlib import Path

_ASSETS_DIR = Path(__file__).parent / "assets"

def _load_asset(relative_path: str, fallback: str = "") -> str:
    """加载 assets 目录下的资源文件"""
    try:
        return (_ASSETS_DIR / relative_path).read_text(encoding='utf-8')
    except FileNotFoundError:
        return fallback
```

**使用示例**：
```python
css = _load_asset("styles/simple_report.css", "/* CSS not found */")
js = _load_asset("scripts/simple_report.js", "// JS not found")
```

---



## 维护约定



1. **新增文档**必须更新本索引

2. **每条索引**包含：链接、说明、关键词

3. **关键词**用于搜索（`rg "关键词" docs/`）



## 自动同步（未归类）

| 文档 | 说明 | 关键词 |
|------|------|--------|
| [ARCHITECTURE_V1.md](ARCHITECTURE_V1.md) | 未标注（原因：源文档无 WHAT 段） | 未标注（原因：源文档无关键词段） |
| [GPU_COMPATIBILITY_ANALYSIS.md](GPU_COMPATIBILITY_ANALYSIS.md) | 未标注（原因：源文档无 WHAT 段） | 未标注（原因：源文档无关键词段） |
| [MALI_INTEGRATION_SUMMARY.md](MALI_INTEGRATION_SUMMARY.md) | 未标注（原因：源文档无 WHAT 段） | 未标注（原因：源文档无关键词段） |
| [MILESTONE_SUMMARY.md](MILESTONE_SUMMARY.md) | 未标注（原因：源文档无 WHAT 段） | 未标注（原因：源文档无关键词段） |
| [NO_GPU_EXTRACTION_IMPLEMENTATION_GUIDE.md](NO_GPU_EXTRACTION_IMPLEMENTATION_GUIDE.md) | 未标注（原因：源文档无 WHAT 段） | 未标注（原因：源文档无关键词段） |
| [NO_GPU_EXTRACTION_ROADMAP.md](NO_GPU_EXTRACTION_ROADMAP.md) | 未标注（原因：源文档无 WHAT 段） | 未标注（原因：源文档无关键词段） |
| [NO_GPU_TEXTURE_EXTRACTION.md](NO_GPU_TEXTURE_EXTRACTION.md) | 未标注（原因：源文档无 WHAT 段） | 未标注（原因：源文档无关键词段） |
| [NO_GPU_TEXTURE_EXTRACTION_ARCHITECTURE.md](NO_GPU_TEXTURE_EXTRACTION_ARCHITECTURE.md) | 未标注（原因：源文档无 WHAT 段） | 未标注（原因：源文档无关键词段） |
| [P4_ENVIRONMENT_VERIFICATION.md](P4_ENVIRONMENT_VERIFICATION.md) | 未标注（原因：源文档无 WHAT 段） | 未标注（原因：源文档无关键词段） |
| [PROGRESS_REPORT.md](PROGRESS_REPORT.md) | 未标注（原因：源文档无 WHAT 段） | 未标注（原因：源文档无关键词段） |
| [rdc_format_spec.md](rdc_format_spec.md) | 未标注（原因：源文档无 WHAT 段） | 未标注（原因：源文档无关键词段） |
| [RDC_STRUCTURE_DEEP_ANALYSIS.md](RDC_STRUCTURE_DEEP_ANALYSIS.md) | 未标注（原因：源文档无 WHAT 段） | 未标注（原因：源文档无关键词段） |
| [REFACTOR_ANALYSIS.md](REFACTOR_ANALYSIS.md) | 未标注（原因：源文档无 WHAT 段） | 未标注（原因：源文档无关键词段） |
| [TEXTURE_EXTRACTION.md](TEXTURE_EXTRACTION.md) | 未标注（原因：源文档无 WHAT 段） | 未标注（原因：源文档无关键词段） |
| [TODO.md](TODO.md) | 未标注（原因：源文档无 WHAT 段） | 未标注（原因：源文档无关键词段） |
| [UNITY_EXPORT.md](UNITY_EXPORT.md) | 未标注（原因：源文档无 WHAT 段） | 未标注（原因：源文档无关键词段） |


### M3 Update (2026-02-10)

- event_asset_orchestrator.py now supports --enable-ai-enrichment.
- New sidecar schema: schema/ai_enrichment.schema.json.
- artifact_index.json now includes optional ai_enrichment summary for downstream tools.

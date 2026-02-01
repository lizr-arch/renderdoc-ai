# 数据来源方式总表（可持续补充）

> **版本**: 1.0.0 | **日期**: 2026-02-01 | **状态**: 维护中

- WHAT：统一记录 RDC Analyzer 的**全部数据来源方式**与可用性/限制，避免“空数据/误期待”。  
- WHY：不同链路（A/C/B）依赖的数据源不同，必须可追溯、可扩展。  
- HOW：按“来源分类 → WHAT/WHY/HOW → 可用性/限制 → 关联入口”记录，后续新增来源只需补表。

**关联文档（双向索引）**  
- `scripts/rdc_analyzer/docs/REPORT_ARCHITECTURE.md`  
- `docs/analysis/codex_rdc_analyzer/WORK_SUMMARY_ROUTES.md`  
- `docs/analysis/codex_rdc_analyzer/WORK_SUMMARY_SCHEMA.md`  
- `docs/analysis/codex_rdc_analyzer/README.md`  

---

## 1. 分类总表（WHAT / WHY / HOW）

> 说明：每条记录都必须包含 WHAT/WHY/HOW。  
> 可用性：A=离线 XML 路线，B=Replay 路线，C=CLI 导出路线。

| 分类 | 来源 | WHAT | WHY | HOW（入口/工具/文件） | 可用性/限制 | 关联入口 |
|---|---|---|---|---|---|---|
| 原始捕获 | `.rdc` | GPU 捕获原始二进制 | 一切分析的唯一源头 | RenderDoc 捕获生成 | A/B/C 基础输入 | `WORK_SUMMARY_ROUTES.md` |
| UI 导出 | XML | 手工导出的结构化事件/资源 | A/C 离线分析主干数据 | RenderDoc UI 导出 XML | ✅A/C；人工步骤 | `README.md` |
| CLI 导出 | XML | 结构化事件/资源/统计 | A/C 离线分析主干数据 | `renderdoccmd convert -c xml` + `analyze_xml_report.py` | ✅A/C；字段不全 | `analyze_xml_report.py` |
| CLI 导出 | `--export-xml`（历史线索） | 可能的 XML 导出入口 | 解释“XML 来源” | `renderdoccmd --export-xml`（文档线索） | ⚠️当前源码未发现实现 | `README.md` |
| CLI 导出 | 纹理/metadata/bindings | 资源与绑定补充数据 | 缓解 XML 字段缺口 | `renderdoccmd`（纹理/metadata/bindings 子命令） | ⚠️命令边界待确认 | `README.md` |
| Replay API | RenderDoc Python | Pipeline/Bindings/Shader 反编译等高保真数据 | 补全 XML 缺失字段 | `renderdoc.OpenCaptureFile()` + `ReplayController` | 需 GPU/驱动/设备 | `WORK_SUMMARY_ROUTES.md` |
| Replay 脚本 | `rdc_to_html.py` | 直接从 `.rdc` 生成 HTML | B 路线主通道 | 依赖 `renderdoc.pyd`/DLL | ⚠️当前环境易缺依赖 | `README.md` |
| Replay 脚本 | `analyze_rdc.py` | `.rdc`→JSON/HTML（Mali） | Shader 深度分析 | 依赖 `renderdoc` + Mali | ⚠️工具链依赖 | `README.md` |
| 离线链路 | `export_textures.py` → `generate_offline_report.py` | 纹理离线导出 + 报告 | 离线兜底 | 先导出纹理，再生成 HTML | ⚠️导出前置依赖 | `README.md` |
| 外部工具 | Mali 报告 | Shader 性能细项 | Shader 深度分析 | `renderdoc_mali_shell.py` → `mali_analysis.json` | 依赖 Mali 工具链 | `REPORT_ARCHITECTURE.md` |
| 结构化契约 | manifest.json | 页面链接 + counts + data_sources | 统一入口与可追溯 | 生成器输出 | ✅A/C | `REPORT_ARCHITECTURE.md` |
| 输出结构 | Analyzer JSON | 单帧分析输出（供对比/验收） | compare 的输入基础 | `export_json_*` | ✅A/C | `WORK_SUMMARY_SCHEMA.md` |
| Compare 输入 | `load_json_data` | 统一输入结构 | 保障 diff 可信度 | `compare_rdc.py` | ✅A/B | `WORK_SUMMARY_SCHEMA.md` |
| Compare 输出 | Diff JSON / HTML | 双帧对比结论 | 形成差异与建议 | `export_json_diff` | ✅A/B | `WORK_SUMMARY_SCHEMA.md` |
| 规则库 | RULES.md | 阈值与问题规则 | 解释“为什么提示” | `scripts/rdc_analyzer/RULES.md` | ✅A/B | `RULES.md` |
| 衍生分析 | Issues/Recommendations | 性能问题与建议 | 建议闭环 | `issue_detector` / analyzer | ✅A/C | `WORK_SUMMARY_VERIFICATION.md` |

---

## 2. 补充规则（新增来源时必须填写）

新增/补充任意数据来源时，请在表格新增一行，并填写以下字段：

1) **来源名称**（稳定且唯一）  
2) **分类**（原始/导出/Replay/外部/结构/规则/衍生）  
3) **WHAT/WHY/HOW**（三要素缺一不可）  
4) **可用性与限制**（A/B/C、依赖条件、是否需要 replay）  
5) **入口位置**（脚本/命令/文档链接）

---

## 3. 已关联文档索引

- `scripts/rdc_analyzer/docs/REPORT_ARCHITECTURE.md`  
  - 说明：页面与 manifest 结构定义（含 data_sources）  
- `docs/analysis/codex_rdc_analyzer/WORK_SUMMARY_ROUTES.md`  
  - 说明：A/B/C 链路边界与依赖  
- `docs/analysis/codex_rdc_analyzer/WORK_SUMMARY_SCHEMA.md`  
  - 说明：输入/输出结构与 compare 可信度  

---

## 4. 维护说明

- 本表为**长期维护表**，后续补充时**只增不删**，避免丢失历史来源。  
- 任何链路变更（A/B/C）都必须同步更新本表。  
- 若来源不可用，必须写明“不可用原因 + 替代路线”。  

---

## 5. 数据丰富度对标（RenderDoc 基线）

> 来源基线：`docs/analysis/codex_rdc_analyzer/2026-01-31-rdc-analyzer-data-richness-baseline.md`  
> 原则：对标 RenderDoc 官方字段全集，标注 **已有/缺失/可扩充/需新增**。

### 5.1 对标基线（官方字段全集）

**ActionDescription（事件/动作）**  
- 官方字段：`eventId, actionId, customName, flags, markerColor, numIndices, numInstances, baseVertex, indexOffset, vertexOffset, instanceOffset, dispatchDimension, dispatchThreadsDimension, dispatchBase, copySource, copyDestination, outputs, depthOut, events, children`

**TextureDescription（纹理元数据）**  
- 官方字段：`format, dimension, type, width, height, depth, resourceId, cubemap, mips, arraysize, creationFlags, msQual, msSamp, byteSize`

**PipeState（通用管线状态）**  
- 官方入口：`renderdoc/api/replay/pipestate.h`（API-specific state 完整快照）

### 5.2 A/C 已覆盖（已有）

- **事件基础字段（A/XML）**：`eid, name, index_count, vertex_count, instance_count, shader_vs/ps, render_targets, depth_target`  
- **事件合并字段（A/XML）**：`type, flags, duration, params, meshInfo, pipelineState, resourceBindings`
- **纹理基础字段（A/XML）**：`id, name, width, height, depth, format, mips, arrayLayers`
- **统计层（C/Compare）**：`summary, textures, shaders, buffers, draw_calls, events, statistics`

### 5.3 缺失字段（没有）

- **ActionDescription 缺口**：`outputs, depthOut, copySource, copyDestination, children, actionId, markerColor`  
- **TextureDescription 缺口**：`resourceId, cubemap, creationFlags, msQual, msSamp, byteSize`  
- **PipeState 缺口**：API-specific state / descriptor 细节 / 完整 bindings 快照  
- **其他缺口**：`buffers/resource details, descriptors, debug messages, counters`

### 5.4 可扩充入口（已有代码）

- `analyze_xml_report.py`：可扩充 XML 字段映射与 coverage 标注  
- `rdc_to_html.py`：Replay 路线入口，可拉取官方字段全集  
- `analyze_rdc.py`：Replay + Mali 分析入口  
- `export_textures.py` → `generate_offline_report.py`：离线纹理导出链路  
- `compare_rdc.py`：`load_json_data` / `export_json_diff`（对比链路结构）

### 5.5 需新增点（无代码 / 需补充）

- **事件树/拷贝/输出字段**：需要 replay 才能完整  
- **纹理完整元数据**：`byteSize/cubemap/msQual` 等  
- **PipelineState 全量**：API-specific state + descriptor 访问  
- **Buffers/Descriptors/DebugMessages/Counters**：需 ReplayController API 接入  

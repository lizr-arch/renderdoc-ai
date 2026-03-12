# RDC Analyzer 功能成本基线（防重复开发）

> 更新日期：2026-02-10  
> 适用范围：`scripts/rdc_analyzer/` 的 Event 资产导出链路（intermediate → import_bundle → FBX）  
> 目标：把“已实现能力、成本、风险、复用入口”固化，避免重复造轮子。

---

## 1. 结论先行

- 当前链路已经具备 **单 Event 资产闭环**：可从 `zip.xml + zip` 或现成 `intermediate/` 产出 Mesh/Material/Shader/Texture，再导出 Unity/Unreal 可消费的 FBX 配套目录。
- 重复开发高风险点不是“缺功能”，而是“重复实现同类编排”：最容易重复的是 Shader 转换路由、纹理状态机、批处理重试逻辑。
- 推荐策略：**先复用现有脚本，再在 orchestrator 层做编排**；不要在新工具中复制解析/导出核心逻辑。

---

## 2. 证据来源（代码锚点）

> 下面这些条目是“事实来源”。新同学要找实现或要扩展功能，优先从这些入口开始。

- `scripts/rdc_analyzer/extract_event_intermediate.py:714`：`extract_event_intermediate(xml_path, zip_path, event_id, out_dir, ...)`
- `scripts/rdc_analyzer/export_event_import_bundle.py:568`：import bundle manifest 校验与落盘（schema）
- `scripts/rdc_analyzer/export_event_import_bundle_batch.py:1`：批处理与失败重跑能力（summary / retry command）
- `scripts/rdc_analyzer/export_fbx_assets.py:365`：`export_fbx_assets(...)`
- `scripts/rdc_analyzer/export_fbx_assets.py:199`：Shader import plan 执行与状态聚合（converted/reconstructed_hlsl/...）
- `scripts/rdc_analyzer/exporters/spirv_cross_bridge.py:1`：SPIR-V → HLSL 桥接（spirv-cross）
- `scripts/rdc_analyzer/exporters/dxbc_bridge.py:1`：DXBC/DXIL dumpbin + HLSL scaffold（fxc/dxc）
- `scripts/rdc_analyzer/schema/*.schema.json`：中间态与导入包 schema 契约（结构验证）
- `scripts/rdc_analyzer/tests/test_export_fbx_assets.py:1`、`scripts/rdc_analyzer/tests/test_export_event_import_bundle.py:1`：关键链路回归测试

---

## 3. 能力-成本矩阵（Baseline）

> 成本评级口径：`L`=低，`M`=中，`H`=高。  
> 重复风险：`低/中/高`，表示最容易被误判为“尚未实现”而重复开发的概率。

| 功能ID | 已实现能力 | 责任脚本 | 输入 | 输出 | 实现成本 | 运行成本 | 维护成本 | 重复风险 | 复用建议 |
|---|---|---|---|---|---|---|---|---|---|
| F-INT-001 | 单 Event 中间态提取 | `extract_event_intermediate.py` | `zip.xml + zip`、`event_id` | `intermediate/mesh/materials/shaders/textures` | H | M | M | 中 | 所有下游流程都以 `intermediate/` 为唯一输入，不再二次解析 xml |
| F-INT-002 | 中间态 schema 校验 | `extract_event_intermediate.py` | `mesh/material/shader/manifest.json` | 校验通过或抛错 | M | L | L | 中 | 新增字段先改 schema，再改消费方 |
| F-BUNDLE-001 | Event Import Bundle 导出 | `export_event_import_bundle.py` | `intermediate/`（或一步式 xml+zip） | `import_bundle/` + `bundle_manifest.json` | M | M | M | 高 | 引擎导入统一消费 import bundle，不要绕过 |
| F-BUNDLE-002 | 外部 RGBA bytes 注入 | `export_event_import_bundle.py` | `rgba_manifest.json` + `*.rgba` | PNG 纹理或状态回退 | M | M | M | 高 | 纹理解码团队只产 RGBA 清单，不改导出主流程 |
| F-BATCH-001 | 批量导出与失败重跑 | `export_event_import_bundle_batch.py` | 根目录或 scan 结果 | summary + retry 命令 + skip 报告 | M | M | M | 中 | 批处理重试逻辑集中在 batch 脚本，避免重复写任务调度器 |
| F-SCAN-001 | Vulkan 事件选点（按纹理/mesh 兼容） | `generate_vulkan_draw_texture_scan.py` | `zip.xml` | `vulkan_draw_texture_scan.json` | M | L | L | 中 | 自动选 event 场景复用 scan，不要重复遍历事件树 |
| F-FBX-001 | OBJ 中间态 → Unity/Unreal FBX 目录 | `export_fbx_assets.py` | `intermediate/` + `event_id` | `obj/` + `fbx/unity` + `fbx/unreal` | H | M | M | 高 | 统一走该入口；新引擎在其后追加 adapter |
| F-SH-SPV-001 | SPIR-V Shader 转 HLSL | `spirv_cross_bridge.py` + `export_fbx_assets.py` | shader bytecode + spirv-cross | `.hlsl` + plan 状态 | M | M | M | 高 | 工具探测与失败状态复用现有 plan 状态机 |
| F-SH-DX-001 | DXBC/DXIL 反汇编 + HLSL scaffold | `dxbc_bridge.py` + `export_fbx_assets.py` | DXBC/DXIL bytecode + fxc/dxc | `.hlsl` + `.asm.txt` + plan 状态 | H | M | M | 高 | 不在新脚本重复实现 dumpbin 解析 |
| F-TEX-STATE-001 | 纹理导出状态机（decoded/raw/missing） | `export_event_import_bundle.py` | texture payload / rgba 覆盖 | `*.png` or `*.bin` + status | M | M | M | 高 | 新导出器直接透传状态，不重发明状态枚举 |
| F-VERIFY-001 | 关键链路单测 | `tests/test_*` | mock intermediate / mock tools | 回归保护 | M | L | M | 低 | 新能力先补测试再改实现 |

---

## 4. 重复开发高风险 Top 5

| 排名 | 风险点 | 常见误区 | 正确做法 |
|---|---|---|---|
| 1 | Shader 转换路由 | “再写一套 SPIR-V / DXBC 处理” | 复用 `export_fbx_assets.py` 的 `shader_import_plan` 与 bridge |
| 2 | 纹理状态管理 | “只输出 PNG，不保留失败状态” | 保留 `decoded_rgba8_png/raw_copy/missing_source` 全状态 |
| 3 | 批处理重跑 | “外层 shell 脚本自己拼 retry” | 复用 `batch_import_bundle_summary.json` + 自动 retry 文件 |
| 4 | intermediate 字段扩展 | “先改消费方再补 schema” | schema 先行，验证失败即阻断 |
| 5 | 事件筛选 | “每个工具都自己扫一遍 draw” | 优先复用 scan 结果（mesh 兼容 + 纹理覆盖） |

---

## 5. 复用优先级（建议执行顺序）

1. **一级复用（必须）**：`extract_event_intermediate.py`、`export_event_import_bundle.py`、`export_fbx_assets.py`。  
2. **二级复用（推荐）**：`export_event_import_bundle_batch.py`、`generate_vulkan_draw_texture_scan.py`。  
3. **三级扩展（新增能力）**：在不修改核心导出脚本的前提下新增 orchestrator/skill 层。

---

## 6. 新需求接入清单（防重复开发检查表）

在新增功能前，先逐项确认：

- [ ] 是否已有同类输出目录结构？
- [ ] 是否已有等价 schema？
- [ ] 是否已有同类状态机（尤其 texture/shader）？
- [ ] 是否已有可复用批处理/重试机制？
- [ ] 是否可通过“新增 adapter”而不是“复制 pipeline”解决？

> 若以上任一项回答为“是”，优先走复用路径。仅在存在硬性差异（输入契约不兼容/性能瓶颈/安全要求）时新增实现。

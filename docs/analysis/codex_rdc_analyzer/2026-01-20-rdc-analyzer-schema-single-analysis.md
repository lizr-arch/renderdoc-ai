# RDC Analyzer 输出口径：单个 RDC（JSON/HTML）Schema 说明

> 覆盖范围：  
> - 新管线 JSON：`scripts/rdc_analyzer/main.py` 的 `_export_reports()`  
> - 旧管线/报告器 JSON：`scripts/rdc_analyzer/reporters/base.py` 的 `ReportData.to_dict()`  
> 目标：解释“你现在到底输出了什么”，以及“为什么这会影响极致分析/对比结论”。  
> 更新时间：2026-01-20

---

## 0) WHY：为什么要把 Schema 当成 P0？

你当前的两个核心目标：
1) 单个 RDC：极致性能分析 + 建议  
2) 两个 RDC：全方位对比 + 结论  

这两件事的共同依赖是：**一份可被复用/可被对比/可被验证的“唯一事实输出”（SSOT / Canonical Schema）**。

- WHAT：Schema 不是“导出 JSON 的字段列表”，而是“工具对外契约”。  
- WHY：如果同一个概念（draw call 数、纹理内存、pass 数）在不同输出里字段/单位/含义不一致，你的 compare 会被迫做“猜字段/补 0”，最终结论不可信。  
- HOW：本文件把“当前现状（as-is）”写清楚，后续你做 P0-1 时可以逐项对照迁移。

---

## 1) 新管线 JSON（main.py 的 `analysis_data`）

### 1.1 WHAT：它的顶层结构是什么？

实现位置：`scripts/rdc_analyzer/main.py` 的 `_export_reports()`  

当前导出的 JSON 结构（抽象骨架）：

```json
{
  "meta": {
    "rdc_path": "…",
    "api": "…",
    "timestamp": "…",
    "version": "2.0.0"
  },
  "summary": {
    "total_events": 0,
    "draw_call_count": 0,
    "texture_count": 0,
    "buffer_count": 0
  },
  "events": [],
  "draw_calls": [],
  "resources": {
    "textures": {},
    "buffers": {}
  },
  "resource_samples": {},
  "issues": [
    {
      "code": "BIND001",
      "severity": "warning",
      "message": "…",
      "eventId": null
    }
  ]
}
```

### 1.1.1 EventPassData（A 路线 HTML Event Browser 契约）

- WHAT：A 路线生成 HTML 时，`eventPassData` 是 Event Browser 的数据契约，最小结构包括：
  - `events[]`：每个事件至少包含 `eid/name/type/params/meshInfo/pipelineState.bindings`
- WHY：Event Browser 的“资源绑定 / Mesh Info / API Call”面板直接读取这些字段，缺失会显示为空。
- HOW：来源于 `parse_rdc_xml` 的事件字段；在 `analyze_xml_report.py` 合并 XML 事件，
  并将 `resourceBindings/pipelineState` 转换为 `pipelineState.bindings`。

### 1.2 WHY：它已经能支撑什么？缺什么会卡住目标 1/2？

它已经能支撑：
- 基于“draw call 数/顶点数/纹理粗统计”的 **快速体检**（适合 A 的第一版）。
- HTML 报告中附带 `performance_report` / `mali_report` 的展示（但注意：JSON 本身不含这两块）。

它缺的会直接卡住：
- **目标 2（对比）**：compare 需要稳定 schema，否则必须猜字段/补 0。  
- **目标 1（极致）**：需要 pipeline snapshot / 资源读写生命周期 / binding 细节；而当前 JSON 里资源生命周期并未显式导出，draw/state 多为简化数据。

### 1.3 HOW：每个关键字段“含义/来源/风险”是什么？

#### `meta`
- WHAT：一次分析的元信息（输入路径、API、生成时间、工具版本）。
- WHY：对比时需要明确“基线/目标”来源；否则输出不可追溯。
- HOW：来自 `AnalysisPipeline` 的运行时字段；建议未来加入：
  - `schema_version`
  - `capture_hash`（可选）
  - `renderdoc_version`（如果可取到）

#### `summary`
- WHAT：粗粒度统计（events/draws/资源数量）。
- WHY：这是报告首页最常用指标，也是回归结论的起点。
- HOW：目前很多指标是“列表长度”：
  - `draw_call_count = len(self._draw_calls)`
  - `texture_count/buffer_count` 来自 `resources` dict 的键数
- 风险：统计口径必须统一（例如 draw_call_count 是否包含 dispatch？是否过滤非 draw 事件？）。

#### `events`
- WHAT：事件列表（用于 drill-down / debug）。
- WHY：极致分析需要可追溯到 event_id；对比也需要 event 级锚点。
- HOW：当前只导出 `self._events[:1000]`（硬限制）。
- 风险：如果 capture 很大，后半段事件被截断，会导致“局部真相”。

#### `draw_calls`
- WHAT：draw call 列表（来自 RenderDoc action/event 抽取）。
- WHY：所有 draw 级分析（小批次、instancing、state/binding）都需要它。
- HOW：由解析/回放阶段填充到 `self._draw_calls`（字段包含 `eventId/name/numIndices/numInstances/...`）。
- 风险：目前 HTML 导出阶段为了适配 exporter，构造了占位 `DrawCallDetail`（见主 scorecard 的冲突点），说明 draw/state 的 SSOT 还没打通。

#### `resources`
- WHAT：资源字典（textures/buffers…），以 `resourceId` 为 key。
- WHY：纹理/Buffer 分析与建议需要它；对比时也需要稳定的资源标识与属性。
- HOW：来自 `ReplayWrapper` 或 controller 资源列表抽取（`_extract_resources` 逻辑）。
- 风险：
  - texture 的 `format` 是字符串，口径可能随 API/驱动变化；
  - 目前 JSON 没有显式的“资源生命周期/读写统计”，难以支撑更极致的建议。

#### `resource_samples`
- WHAT：资源采样（纹理缩略图/Buffer 小段采样，base64）。
- WHY：对报告可视化很有价值；也能帮助定位“异常资源”（例如全黑纹理、buffer 内容明显异常）。
- HOW：由 `_sample_resources` 生成，包含 `type/info/data/size`。
- 风险：采样是可选/可能失败，必须在 schema 中明确其不完整性（例如 `sample_status`/`error`）。

#### `issues`
- WHAT：问题列表（当前主要来自 `BIND001/BIND002` + `PERF00x` 转换而来）。
- WHY：这是“你给出的建议/结论”的直接载体；对比时也需要能对 issue 做 diff。
- HOW：当前 issue 形态是 dict：
  - `code`（规则 id）
  - `severity`（warning/info/error）
  - `message`
  - `eventId`（可为空）
- 风险：
  - issue 的字段与 `core/types.py` 的 `Issue`（dataclass+enum）不是同一套；
  - JSON 目前不含 `performance_report`/`mali_report`，导致“HTML 有但 JSON 无”的口径漂移。

---

## 2) 旧管线/报告器 JSON（`ReportData.to_dict()`）

### 2.1 WHAT：它的顶层结构是什么？

实现位置：`scripts/rdc_analyzer/reporters/base.py` 的 `ReportData.to_dict()`  

骨架如下：

```json
{
  "metadata": { "file_path": "…", "analysis_time": "…", "analyzer_version": "…", "platform": "…", "api": "…" },
  "summary": { "total_issues": 0, "errors": 0, "warnings": 0, "info": 0, "rules_checked": 0, "rules_passed": 0, "rules_failed": 0 },
  "frame_summary": { "draw_call_count": 0, "vertex_count": 0, "texture_memory_mb": 0, "buffer_memory_mb": 0, "rt_switches": 0, "pass_count": 0, "viewport": "…" },
  "issues": [ { "code": "RD_…", "severity": "WARNING", "category": "…", "message": "…", "location": "…", "suggestion": "…" } ],
  "extra": {}
}
```

### 2.2 WHY：它现在的问题是什么？

- 它的优势：结构更“报告化”，`frame_summary`/`issues` 已经非常接近“对外契约”的形态。  
- 它的致命问题：在你当前默认 CLI（main pipeline）里它不是主输出，因此出现 **多套 schema 并存**：
  - `main.py` 的 `analysis_data`（v2）
  - `ReportData.to_dict()`（v1）
  - compare 的输入/输出 schema（又一套）

这会直接导致 compare 只能做兼容/猜字段（详见 compare schema 文档），削弱你“全方位对比 + 结论”的可信度。

### 2.3 HOW：它与新管线的最大不一致点

- metadata vs meta：字段命名不同；版本号系统不同。  
- issues 结构不同：旧管线 issue 用 enum severity/category；新管线 issue 是简化 dict。  
- frame_summary 的字段更完整（texture/buffer memory、viewport、pass_count），而新管线 summary 只有“数量级”。

---

## 3) 我建议你怎么用这份文档（落到行动）

- 如果你要继续走 A（规则+建议）路线：  
  - **把旧 schema 的优点（frame_summary、issues 结构化）吸收到新 canonical schema 里**。  
- 如果你要做目标 2（对比）：  
  - 先明确 compare 的唯一输入：只允许输入 canonical single-analysis JSON；禁止“Phase1/Phase2”混乱兼容。  

这些对应主路线图的 P0-1 / P0-3 / P0-4。


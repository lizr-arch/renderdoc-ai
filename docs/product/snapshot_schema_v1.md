# RenderDoc AI 统一快照契约（Snapshot Schema v1）

> 目标：为 GUI 报告、离线/CI 报告、后续对比能力，以及 Skill 消费，定义同一份事实快照。  
> 不适用：MCP 实时查询响应；MCP 通过 `docs/product/mcp_query_contract_v1.md` 映射到本契约。  
> 设计原则：事实优先、显式可用性、稳定 ID、证据可跳转、AI 只消费不污染事实层。

## 1. 设计原则

1. **事实层与解释层分离**：快照只存确定性事实与规则结果，不存开放式 AI 文本。
2. **来源统一**：`gui`、`offline`、`mcp_export` 都要能映射到同一顶层结构。
3. **可用性显式化**：字段拿不到时必须标记 `partial` / `unavailable`，不能伪造默认值。
4. **证据可追溯**：每条 finding / recommendation 都必须能跳回 `event_id`、`resource_id` 或 `shader_id`。
5. **兼容旧资产**：尽量吸收已有 `analysis.json` / `schema_version=1.0` 经验，但本契约是新的报告快照 SSOT。

## 2. 顶层结构

```json
{
  "schema_version": "snapshot.v1",
  "meta": {},
  "preflight": {},
  "overview": {},
  "timings": {},
  "actions": [],
  "passes": [],
  "resources": {
    "textures": [],
    "buffers": []
  },
  "shaders": [],
  "pipelines": [],
  "findings": [],
  "recommendations": [],
  "evidence_index": {},
  "availability": {}
}
```

## 3. 顶层字段定义

| Key | Type | Required | 说明 |
| --- | --- | --- | --- |
| `schema_version` | string | Y | 固定为 `snapshot.v1` |
| `meta` | object | Y | capture、生成器、来源、时间戳 |
| `preflight` | object | Y | 数据缺口、降级提示、捕获建议 |
| `overview` | object | Y | 帧级摘要与主计数 |
| `timings` | object | N | 帧级 timing 摘要与可信度 |
| `actions` | array | Y | 事件/Draw/Dispatch 列表 |
| `passes` | array | N | pass 或 pass-like 分组 |
| `resources` | object | Y | `textures` / `buffers` |
| `shaders` | array | N | Shader 摘要与资源绑定 |
| `pipelines` | array | N | 事件级或采样级 pipeline 摘要 |
| `findings` | array | Y | 规则引擎输出的问题/风险 |
| `recommendations` | array | Y | 确定性建议与验证步骤 |
| `evidence_index` | object | Y | 页面跳转与交叉引用索引 |
| `availability` | object | Y | 顶层与字段级可用性汇总 |

## 4. `meta` 契约

```json
{
  "source": "gui",
  "capture_name": "sample.rdc",
  "capture_path": "D:/captures/sample.rdc",
  "graphics_api": "Vulkan",
  "frame_number": 42231,
  "generated_at": "2026-03-08T23:30:00+08:00",
  "generator": {
    "kind": "gui_export",
    "version": "1.0"
  },
  "report_surface": "gui_html",
  "availability_summary": {
    "full": 8,
    "partial": 3,
    "unavailable": 1
  }
}
```

字段说明：

- `source`: `gui` / `offline` / `mcp_export`
- `report_surface`: `gui_html` / `offline_html` / `native_qt_snapshot` / `json_only`
- `generator.kind`: `gui_export` / `cli_export` / `mcp_export`

## 5. 通用内嵌类型

### 5.1 Availability

```json
{
  "status": "partial",
  "missing_fields": ["depth_target", "render_targets"],
  "notes": ["Current API did not expose structured RT fields for this event"]
}
```

约束：

- `status` 只能是 `full` / `partial` / `unavailable`
- 任何占位 UI 都必须依据该结构决定显示方式

### 5.2 EvidenceRef

```json
{
  "kind": "event",
  "id": "1034",
  "label": "vkCmdDrawIndexed()",
  "source_ref": "actions/1034",
  "anchor": "event-1034"
}
```

`kind` 允许值：`event` / `pass` / `resource` / `shader` / `marker`

### 5.3 Severity

`findings[].severity` 允许值：`critical` / `high` / `medium` / `low` / `info`

## 6. 分块契约

### 6.1 `preflight`

用于说明捕获质量与数据降级，不得省略。

| Field | Type | Required | 说明 |
| --- | --- | --- | --- |
| `status` | string | Y | `ok` / `warning` / `error` |
| `missing_data` | array | N | 缺失的数据项列表 |
| `degraded_conclusions` | array | N | 哪些结论因此降级 |
| `capture_recommendations` | array | N | 下次抓帧建议 |

### 6.2 `overview`

```json
{
  "summary": {
    "draw_call_count": 337,
    "dispatch_count": 12,
    "texture_count": 145,
    "buffer_count": 62,
    "shader_count": 31,
    "pass_count": 28
  },
  "highlights": [
    {
      "title": "Top GPU hotspot",
      "value": "event 1034 / 0.48 ms",
      "evidence": [{"kind":"event","id":"1034","label":"vkCmdDrawIndexed()","source_ref":"actions/1034","anchor":"event-1034"}]
    }
  ]
}
```

### 6.3 `timings`

| Field | Type | Required | 说明 |
| --- | --- | --- | --- |
| `available` | bool | Y | 是否拿到 timing |
| `usable_count` | int | N | `>0` 的条目数 |
| `zero_or_negative_count` | int | N | 0/负值条目数 |
| `total_gpu_ms` | number | N | 可用条目的总时长 |
| `top_actions` | array | N | Top-N 热点动作 |
| `availability` | object | Y | 字段可用性 |

### 6.4 `actions[]`

最小字段：

| Field | Type | Required | 说明 |
| --- | --- | --- | --- |
| `event_id` | int | Y | 事件 ID |
| `name` | string | Y | Draw/Dispatch/Clear 名称 |
| `kind` | string | Y | `draw` / `dispatch` / `clear` / `marker` |
| `marker_path` | array | N | 所属 marker 层级 |
| `flags` | array | N | Drawcall / Dispatch 等标记 |
| `timing_ms` | number | N | 事件时长 |
| `shader_refs` | array | N | 关联 shader evidence |
| `resource_refs` | array | N | 关联资源 evidence |
| `pipeline_ref` | string | N | 指向 `pipelines[]` 的 ID |
| `availability` | object | Y | 动作级字段可用性 |
| `evidence` | array | Y | 至少包含自身 event evidence |

### 6.5 `passes[]`

`pass` 可以来自 marker，也可以来自启发式分组；必须显式标注来源。

| Field | Type | Required | 说明 |
| --- | --- | --- | --- |
| `pass_id` | string | Y | 稳定 ID |
| `name` | string | N | pass 名称 |
| `source` | string | Y | `marker` / `renderpass` / `heuristic` |
| `start_event_id` | int | Y | 起始事件 |
| `end_event_id` | int | Y | 结束事件 |
| `draw_count` | int | N | Draw 数 |
| `dispatch_count` | int | N | Dispatch 数 |
| `render_target_refs` | array | N | RT evidence 列表 |
| `depth_target_ref` | object | N | 深度附件 evidence |
| `availability` | object | Y | 数据可用性 |

### 6.6 `resources.textures[]` / `resources.buffers[]`

`textures[]` 最小字段：

- `resource_id`
- `name`
- `width` / `height` / `depth`
- `format`
- `sample_count`
- `usage_tags`
- `producer_event_refs`
- `consumer_event_refs`
- `availability`

`buffers[]` 最小字段：

- `resource_id`
- `name`
- `byte_size`
- `usage_tags`
- `bound_event_refs`
- `availability`

### 6.7 `shaders[]`

| Field | Type | Required | 说明 |
| --- | --- | --- | --- |
| `shader_id` | string | Y | 稳定 ID |
| `stage` | string | Y | VS/PS/CS/... |
| `entry_point` | string | N | 入口点 |
| `encoding` | string | N | HLSL / DXIL / SPIR-V / GLSL |
| `source_asm` | string | N | 反汇编 |
| `source_high_level` | string | N | HLSL/GLSL/源码 |
| `resource_bindings` | array | N | CBuffer / SRV / UAV / Sampler |
| `used_by_event_refs` | array | N | 使用该 shader 的事件 |
| `availability` | object | Y | 数据可用性 |

### 6.8 `pipelines[]`

`pipelines[]` 不是完整 API 对象转储，而是报告层可消费的摘要。

| Field | Type | Required | 说明 |
| --- | --- | --- | --- |
| `pipeline_id` | string | Y | 稳定 ID |
| `event_id` | int | Y | 对应事件 |
| `graphics_api` | string | Y | Vulkan / D3D11 / D3D12 |
| `vs_ref` | object | N | Vertex shader evidence |
| `ps_ref` | object | N | Pixel/Fragment shader evidence |
| `render_target_refs` | array | N | RT evidence |
| `depth_target_ref` | object | N | depth evidence |
| `blend` | object | N | Blend 摘要 |
| `depth_stencil` | object | N | 深度/模板摘要 |
| `rasterizer` | object | N | Cull / Fill / Viewport |
| `vertex_layout` | object | N | 顶点布局 |
| `availability` | object | Y | 数据可用性 |

### 6.9 `findings[]`

`findings[]` 只允许确定性规则引擎或已验证指标产出。

```json
{
  "id": "FINDING_DRAW_001",
  "severity": "high",
  "category": "performance",
  "title": "Hot draw call",
  "message": "event 1034 consumes 0.48 ms",
  "evidence": [
    {"kind":"event","id":"1034","label":"vkCmdDrawIndexed()","source_ref":"actions/1034","anchor":"event-1034"}
  ],
  "metrics": {
    "timing_ms": 0.48
  }
}
```

### 6.10 `recommendations[]`

`recommendations[]` 允许确定性建议和验证步骤，但不写 AI 自由发挥的长文。

| Field | Type | Required | 说明 |
| --- | --- | --- | --- |
| `id` | string | Y | 建议 ID |
| `title` | string | Y | 建议标题 |
| `priority` | string | Y | `high` / `medium` / `low` |
| `rationale` | string | Y | 为什么给出该建议 |
| `evidence` | array | Y | 证据链 |
| `verification_steps` | array | N | 如何验证 |

### 6.11 `evidence_index`

用于页面跳转和交叉链接：

```json
{
  "events": {"1034": "events.html#event-1034"},
  "resources": {"176441": "textures.html#resource-176441"},
  "shaders": {"158093": "shaders.html#shader-158093"},
  "passes": {"pass-26": "events.html#pass-26"}
}
```

## 7. 来源差异约束

| 来源 | 强项 | 常见缺口 | 处理方式 |
| --- | --- | --- | --- |
| `gui` | 字段最完整、可跳转、可读 pipeline | 导出耗时较高 | 正常填充，作为 full baseline |
| `offline` | 无 GUI、CI 友好、可批量 | 某些 pipeline / timing / 缩略图缺失 | `availability=partial` + MCP 补数提示 |
| `mcp_export` | 实时、按需、低颗粒 | 非快照式、易缺全局概览 | 仅用于补数或局部导出，不替代完整快照 |

## 8. 与旧 schema 的映射关系

| 旧字段 | 新字段 |
| --- | --- |
| `summary` | `overview.summary` |
| `coverage` | `availability` |
| `events` / `draw_calls` | `actions` |
| `resources.textures` / `resources.buffers` | `resources.*` |
| `issues` | `findings` |
| `suggestions` | `recommendations` |
| `preflight` | `preflight` |
| `pipeline_state[]` | `pipelines[]` |

## 9. 使用规则

1. GUI 和离线导出必须输出符合本契约的 JSON 快照。
2. 模板组件不得直接消费“来源私有字段”，必须走本契约字段。
3. Skill 如果需要 AI 分析，应读取本快照或通过 MCP 查询补充，不得改写本快照原文。
4. 如果未来出现新字段，先在本文件增加 `optional` 字段定义，再进入实现。

## 10. 参考

- `docs/analysis/codex_rdc_analyzer/WORK_SUMMARY_SCHEMA.md`
- `docs/analysis/codex_rdc_analyzer/analysis_report_schema_v1.md`
- `docs/product/gui_report.md`
- `docs/product/offline_report.md`
- `docs/product/mcp_api.md`

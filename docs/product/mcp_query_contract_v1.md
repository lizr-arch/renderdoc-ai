# RenderDoc AI MCP 查询契约（MCP Query Contract v1）

> 目标：冻结本地桌面 MCP 的查询边界、响应 envelope、错误模型，以及与统一快照之间的映射关系。  
> 适用范围：RenderDoc GUI 已加载 capture，MCP bridge 正常工作时的实时查询。  
> 非目标：不定义完整报告导出；不取代 `snapshot.v1`。

## 1. 定位

MCP 的职责只有三件事：

1. 读取已加载 capture 的实时事实。
2. 在 GUI / Offline 快照缺字段时提供补数通道。
3. 给 Skill、脚本和自动化提供低颗粒度、可组合的查询面。

不做的事：

- 不生成整份 HTML 报告。
- 不维护第二套模板。
- 不把 AI 输出混入 MCP 返回。

## 2. 调用前提

客户端应先调用：

- `get_capture_status`

只有在 `loaded=true` 时，才继续发起细粒度查询。

## 3. 统一响应 envelope

```json
{
  "ok": true,
  "contract_version": "mcp-query.v1",
  "data": {},
  "availability": {
    "status": "full",
    "missing_fields": [],
    "notes": []
  },
  "evidence": [],
  "warnings": [],
  "recovery_hint": null
}
```

字段定义：

| Field | Type | Required | 说明 |
| --- | --- | --- | --- |
| `ok` | bool | Y | 是否成功 |
| `contract_version` | string | Y | 固定为 `mcp-query.v1` |
| `data` | object/array | Y | 实际结果 |
| `availability` | object | Y | 与 `snapshot.v1` 一致的可用性结构 |
| `evidence` | array | Y | 本次查询涉及的 evidence 列表 |
| `warnings` | array | N | 非致命警告 |
| `recovery_hint` | string/null | N | 下一步建议 |

## 4. 错误模型

错误响应仍使用同一 envelope，但 `ok=false`：

```json
{
  "ok": false,
  "contract_version": "mcp-query.v1",
  "data": null,
  "availability": {
    "status": "unavailable",
    "missing_fields": [],
    "notes": ["Capture is not loaded"]
  },
  "evidence": [],
  "warnings": [],
  "recovery_hint": "Open a capture in qrenderdoc and retry",
  "error": {
    "code": "capture_not_loaded",
    "message": "No active capture"
  }
}
```

标准错误码：

- `bridge_unavailable`
- `capture_not_loaded`
- `invalid_argument`
- `not_found`
- `data_unavailable`
- `unsupported_api`
- `timeout`
- `internal_error`

## 5. API 分组

| 分组 | 典型接口 | 说明 |
| --- | --- | --- |
| Capture | `get_capture_status`, `list_captures`, `open_capture` | 会话与捕获状态 |
| Actions | `get_draw_calls`, `get_frame_summary`, `get_draw_call_details` | 事件、Draw、Dispatch |
| Timings | `get_action_timings` | 热点、总时长、计时可用性 |
| Search | `find_draws_by_shader`, `find_draws_by_texture`, `find_draws_by_resource` | 反查与交叉引用 |
| Pipeline | `get_pipeline_state`, `get_shader_info` | 关键状态与 Shader 信息 |
| Resources | `get_texture_info`, `get_texture_data`, `get_buffer_contents` | 资源元数据与内容 |

## 6. 分组返回要求

### 6.1 Capture

`get_capture_status.data` 最小字段：

- `loaded`
- `filename`
- `api`
- `frame_number`（如可用）

### 6.2 Actions

`get_draw_calls.data[]` 最小字段：

- `event_id`
- `name`
- `flags`
- `marker_path`

`get_draw_call_details.data` 最小字段：

- `event_id`
- `name`
- `draw_index_count` / `dispatch_dimensions`
- `output_refs`
- `depth_ref`

### 6.3 Timings

`get_action_timings.data` 最小字段：

- `available`
- `count`
- `usable_count`
- `zero_or_negative_count`
- `total_gpu_ms`
- `items[]`：`event_id`, `name`, `duration_ms`

### 6.4 Search

返回结构统一为匹配列表：

- `query`
- `match_count`
- `items[]`

每个 item 至少有：

- `event_id`
- `label`
- `matched_by`
- `evidence`

### 6.5 Pipeline

`get_pipeline_state.data` 最小字段：

- `event_id`
- `graphics_api`
- `vs_ref`
- `ps_ref` / `fs_ref`
- `render_target_refs`
- `depth_target_ref`
- `blend`
- `depth_stencil`
- `rasterizer`
- `vertex_layout`

如果部分字段当前 API 拿不到，必须：

- `availability.status = partial`
- 在 `missing_fields` 中列出具体字段
- 在 `warnings` 中给出原因

### 6.6 Resources

`get_texture_info.data` 最小字段：

- `resource_id`
- `name`
- `width`
- `height`
- `format`
- `sample_count`

`get_texture_data` 与 `get_buffer_contents` 默认不直接返回大块二进制文本，应支持：

- 范围限制
- 大小限制
- 明确的截断说明

## 7. 与快照契约的映射

| MCP 查询 | 快照目标字段 |
| --- | --- |
| `get_capture_status` | `meta.*`, `preflight.*` |
| `get_frame_summary` | `overview.summary` |
| `get_draw_calls` | `actions[]` |
| `get_action_timings` | `timings`, `actions[].timing_ms` |
| `find_draws_by_*` | `evidence_index`, `resource_refs`, `shader_refs` |
| `get_pipeline_state` | `pipelines[]` |
| `get_shader_info` | `shaders[]` |
| `get_texture_info` | `resources.textures[]` |
| `get_buffer_contents` | `resources.buffers[]`（按需补数） |

规则：

- MCP 只负责把“局部事实”补到快照字段模型上。
- MCP 结果不得引入与快照冲突的另一套字段名。

## 8. 过滤、体积与性能

默认策略：

- 所有列表查询都应支持过滤器（marker / flag / event range / keyword）。
- 二进制或大文本内容必须显式请求，默认不返回。
- 当结果被截断时，必须在 `warnings` 中说明，并给出缩小范围的建议。

建议：

- Skill 优先调用摘要接口，再按需下钻。
- 不要把整棵动作树、整份 pipeline dump 直接喂给大模型。

## 9. Skill 调用模式

Skill 使用 MCP 时遵循两段式：

1. **健康与定位**
   - `get_capture_status`
   - `get_action_timings` 或 `get_draw_calls`
2. **按证据下钻**
   - `get_pipeline_state`
   - `find_draws_by_*`
   - `get_shader_info`
   - `get_texture_info`

Skill 的输出应是：

- Markdown 简报
- 命令清单
- 后续验证步骤

而不是另一份“完整报告 HTML”。

## 10. 已知缺口的处理方式

对于当前已知的结构缺口，例如某些事件无法返回 `render_target_refs` / `depth_target_ref`：

- 不得伪造空数组表示“没有 RT”。
- 必须返回 `availability=partial`。
- 必须在 `warnings` 或 `notes` 中标明“当前适配未暴露该字段”。

## 11. 验收要求

- 新增 MCP 接口时，先更新本契约，再更新实现。
- MCP 响应能稳定映射到 `snapshot.v1`。
- 错误响应具有稳定错误码与恢复提示。
- Skill 和脚本能基于本契约构建固定的调用链。

## 12. 参考

- `docs/product/mcp_api.md`
- `docs/product/snapshot_schema_v1.md`
- `docs/learn/evidence/E-004-mcp-scripts.md`
- `docs/learn/evidence/E-005-skill-perf-research.md`

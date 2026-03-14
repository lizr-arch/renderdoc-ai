# RenderDoc AI 报告模板契约（Template Contract v1）

> 目标：冻结 GUI 导出 HTML 与离线/CI HTML 的统一页面结构、组件输入与降级规则。  
> 输入数据：`docs/product/snapshot_schema_v1.md`。  
> 非目标：约束原生 Qt 布局的像素级实现；Qt 侧只需对齐信息架构和证据链。

## 1. 设计目标

1. 统一页面结构，避免 GUI / Offline 各长一套页面。
2. 统一组件输入，避免模板直接绑定来源私有字段。
3. 统一降级方式，让缺失字段时的页面行为一致。
4. 统一证据链，让所有结论都能跳转到事件、资源、Shader。

## 2. 输出文件契约

最小产物：

- `index.html`
- `events.html`
- `textures.html`
- `shaders.html`
- `pipelines.html`
- `manifest.json`

可选产物：

- `assets/`（CSS / JS / 图片）
- `thumbnails/`（纹理缩略图）
- `exports/`（按需导出的 JSON / 源码片段）

约束：

- 导航中的 URL 与 anchor 名称在 GUI 导出和离线导出中必须一致。
- 即使某页没有完整数据，也应输出页面壳或清晰的禁用态，而不是直接消失，避免链接失效。

## 3. 页面清单

| 页面 | 必需 | 主要数据来源 | 目标 |
| --- | --- | --- | --- |
| `index.html` | Y | `meta` / `overview` / `timings` / `findings` | 第一屏定位全局问题 |
| `events.html` | Y | `actions` / `passes` / `evidence_index` | 查看事件树、Pass、热点 |
| `textures.html` | Y | `resources.textures` | 查看 RT / Depth / Texture |
| `shaders.html` | Y | `shaders` | 查看 Shader 与绑定关系 |
| `pipelines.html` | Y | `pipelines` | 查看关键状态摘要与缺失提示 |

## 4. 导航与跳转规则

### 4.1 顶部导航

必须包含：

- Overview
- Events
- Textures
- Shaders
- Pipelines

每个导航项都必须支持：

- 正常态
- 数据不完整态（带 `Partial` 标记）
- 无数据态（带 `Unavailable` 标记）

### 4.2 证据链跳转

每个摘要卡片、finding、recommendation 至少提供一个证据入口：

- 事件：`events.html#event-<event_id>`
- 资源：`textures.html#resource-<resource_id>`
- Shader：`shaders.html#shader-<shader_id>`
- Pass：`events.html#pass-<pass_id>`

不允许“只有文字，没有跳转证据”的摘要组件。

## 5. 组件契约

### 5.1 Overview 页面

必备组件：

| 组件 ID | 输入 | 必需字段 | 缺失时行为 |
| --- | --- | --- | --- |
| `capture-meta` | `meta` | `capture_name`, `graphics_api`, `source` | 以 `Unknown` 占位并保留来源说明 |
| `summary-cards` | `overview.summary` | draw / dispatch / texture / shader 计数 | 缺失项显示 `N/A` |
| `timing-overview` | `timings` | `available`, `top_actions` | 显示 timing unavailable 提示 |
| `finding-list` | `findings` | `severity`, `title`, `evidence` | 无 finding 时显示 empty state |
| `preflight-panel` | `preflight` | `status` | 必须始终渲染 |

### 5.2 Events 页面

必备组件：

- `pass-outline`
- `event-tree`
- `event-filters`
- `event-detail-panel`

规则：

- `event-tree` 至少显示 `event_id`、`name`、`kind`、`marker_path`。
- 若存在 timing，则显示 timing badge；否则显示 `Timing N/A`。
- Detail panel 的 `pipeline` / `resources` / `shader` 链接都来自 `evidence`，不得自行拼接未知字段。

### 5.3 Textures 页面

最小卡片字段：

- `resource_id`
- `name`
- `width x height`
- `format`
- `usage_tags`
- `producer_event_refs` / `consumer_event_refs`

降级规则：

- 无缩略图：显示格式化占位卡片，不阻塞页面结构。
- 无 producer / consumer：显式标记 `No evidence links`。

### 5.4 Shaders 页面

最小卡片字段：

- `shader_id`
- `stage`
- `entry_point`
- `encoding`
- `used_by_event_refs`

可展开内容：

- `source_asm`
- `source_high_level`
- `resource_bindings`

降级规则：

- 只有反汇编时，也必须允许查看和复制。
- 无高层源码时不显示空白代码框，而显示说明：`High-level source unavailable`。

### 5.5 Pipelines 页面

最小卡片字段：

- `event_id`
- `vs_ref` / `ps_ref`
- `render_target_refs`
- `depth_target_ref`
- `blend`
- `depth_stencil`
- `rasterizer`
- `availability`

降级规则：

- 如果 `render_target_refs` / `depth_target_ref` 缺失，必须在卡片顶部显示 `Use MCP query to fill RT/Depth details`。
- 如果整个 `pipelines` 缺失，页面显示统一空态，而不是隐藏导航。

## 6. Manifest 契约

`manifest.json` 至少包含：

```json
{
  "schema_version": "template.v1",
  "snapshot_version": "snapshot.v1",
  "pages": ["index", "events", "textures", "shaders", "pipelines"],
  "source": "gui",
  "generated_at": "2026-03-08T23:30:00+08:00"
}
```

用途：

- 前端自检资源完整性。
- 外部工具判断页面存在性与版本。

## 7. GUI 与离线的一致性规则

### 7.1 必须一致

- 页面名与路由名
- 卡片字段名
- 证据 anchor 规则
- Availability badge 的语义
- Empty state 与 fallback 文案

### 7.2 可以不同

- 生成方式
- 资源打包方式
- 图片/缩略图是否延迟加载
- GUI 内是否额外挂接“Jump to RenderDoc”动作

### 7.3 Native Qt Analyzer Report 的关系

原生 Qt 不是这份 HTML 模板的直接消费者，但应遵守：

- 同样的 section 划分
- 同样的证据链命名
- 同样的 finding / recommendation 事实输入

这样 Qt 与 HTML 可以共享一套事实解释逻辑，而不是共享像素布局。

## 8. Fallback 统一规则

| 场景 | 统一处理 |
| --- | --- |
| 字段缺失 | 使用 `availability` 标记 + 明确文案 |
| 图片缺失 | 展示占位卡，不破坏栅格 |
| timing 缺失 | 以 badge 提示而非删除组件 |
| pipeline 结构缺失 | 给出 MCP 补数建议 |
| 页面无数据 | 页面仍输出，展示 empty state |

## 9. 实现要求

1. 模板组件只读 `snapshot.v1` 字段，不得直接读 XML / ReplayController 私有结构。
2. 如果引入新页面或新组件，必须先更新本契约。
3. 现有 bundle report / WebUI / GUI export 的差异，后续都要回收进这份契约，而不是相互背离。

## 10. 验收清单

- 同一 capture 由 GUI 与离线导出的页面结构一致。
- 所有 finding 和 hotspot 卡片都能至少跳到一个证据对象。
- 缺失数据时页面不崩、导航不丢、文案一致。
- `manifest.json` 可被外部工具稳定消费。

## 11. 参考

- `docs/product/gui_report.md`
- `docs/product/offline_report.md`
- `docs/product/snapshot_schema_v1.md`
- `scripts/rdc_analyzer/docs/REPORT_ARCHITECTURE.md`

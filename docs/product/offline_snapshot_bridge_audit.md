# 离线路径 `snapshot.v1` 桥接审计

> 2026-04-23 delta：本文主体记录的是 2026-03-09 的旧审计基线。
> 其中“共享 renderer 还未落地”“snapshot HTML 仍是未来阶段”的判断已部分过时：
> - `SnapshotTemplateRenderer` 已存在
> - `xml_to_bundle.py` 的 snapshot 路由当前候选页集已对齐 `pipelines.html`
> - legacy `ReportBundleGenerator` 现在应被视作 fallback/兼容路径，而不是新 canonical 主路径
> 最新当前状态请优先读：`docs/product/delivery_surfaces_status.md`

时间：2026-03-09 16:57:03  
负责人：AgentA

## 1. 结论

当前离线路径仍然是“`renderdoccmd XML -> legacy bundle 内部结构 -> HTML`”，还没有真正接到 `snapshot.v1 + template.v1`。

这个问题属于实现/契约层限制，不是理论限制。它可以通过新增一层离线 `snapshot.v1` builder 与共享 renderer 解决，不建议继续在 `xml_to_bundle.py` 和 `report_bundle_generator.py` 上叠加更多产品逻辑。

推荐结论：

1. 保留 `report_bundle_generator.py` 作为 legacy/fallback 路径。
2. 新增离线 `snapshot.v1` 构建层，直接从 XML 解析结果产出统一快照。
3. 新增共享 renderer，只消费 `snapshot.v1`，不再直接消费 XML 私有结构。
4. `xml_to_bundle.py` 第一阶段至少要能稳定输出 `snapshot.v1.json`；HTML 共享模板接入作为下一阶段落地。

## 2. 审计范围与证据

- 产品契约：`docs/product/snapshot_schema_v1.md:19`
- 模板契约：`docs/product/template_contract_v1.md:41`
- 离线路径设计：`docs/product/offline_report.md:1`
- XML 转 bundle 主入口：`scripts/rdc_analyzer/xml_to_bundle.py:1022`
- XML 脚本直接驱动 generator：`scripts/rdc_analyzer/xml_to_bundle.py:1116`
- XML 脚本输出文案仍宣称存在 `events.html`：`scripts/rdc_analyzer/xml_to_bundle.py:1152`
- legacy generator 初始化数据模型：`scripts/rdc_analyzer/report_bundle_generator.py:141`
- legacy generator 的 `performance_data`/`usage_map` 入口：`scripts/rdc_analyzer/report_bundle_generator.py:252`, `scripts/rdc_analyzer/report_bundle_generator.py:293`, `scripts/rdc_analyzer/report_bundle_generator.py:358`, `scripts/rdc_analyzer/report_bundle_generator.py:382`
- legacy generator 实际输出文件：`scripts/rdc_analyzer/report_bundle_generator.py:1541`, `scripts/rdc_analyzer/report_bundle_generator.py:1567`
- legacy generator 已有 `generate_events()` 但未被 `generate_all()` 调用：`scripts/rdc_analyzer/report_bundle_generator.py:1047`, `scripts/rdc_analyzer/report_bundle_generator.py:1567`
- legacy helper 正常使用 `set_*` API，但 `xml_to_bundle.py` 未复用：`scripts/rdc_analyzer/report_bundle_generator.py:1636`

## 3. 当前离线链路实际在做什么

当前链路分成三步：

1. `renderdoccmd convert -c xml` 先把 `.rdc` 导成 XML。
2. `xml_to_bundle.py` 读取 XML，把 `draw_calls` 转成 `events`，把 `textures_raw` 转成 `textures`，可选补纹理缩略图和 Vulkan shader 提取，见 `scripts/rdc_analyzer/xml_to_bundle.py:1022`、`scripts/rdc_analyzer/xml_to_bundle.py:1023`、`scripts/rdc_analyzer/xml_to_bundle.py:1078`。
3. `xml_to_bundle.py` 直接实例化 `ReportBundleGenerator`，把 `events/textures/shaders` 塞进 generator 内部字段，然后手工写统计，再调用 `generate_all()`，见 `scripts/rdc_analyzer/xml_to_bundle.py:1116`、`scripts/rdc_analyzer/xml_to_bundle.py:1119`、`scripts/rdc_analyzer/xml_to_bundle.py:1124`、`scripts/rdc_analyzer/xml_to_bundle.py:1137`。

也就是说，现在离线路径并不是：

`XML -> snapshot.v1 -> template.v1 renderer`

而是：

`XML -> legacy events/textures/shaders dict -> ReportBundleGenerator 私有模板渲染`

## 4. 与 `snapshot.v1` / `template.v1` 的主要偏差

### 4.1 顶层事实结构没有统一

`snapshot.v1` 要求统一顶层块：`meta`、`preflight`、`overview`、`timings`、`actions`、`passes`、`resources`、`shaders`、`pipelines`、`findings`、`recommendations`、`evidence_index`、`availability`，见 `docs/product/snapshot_schema_v1.md:19`。

当前 `xml_to_bundle.py` 只产出三类核心列表：

- `events`
- `textures`
- `shaders`

外加少量统计值，见 `scripts/rdc_analyzer/xml_to_bundle.py:1022`、`scripts/rdc_analyzer/xml_to_bundle.py:1023`、`scripts/rdc_analyzer/xml_to_bundle.py:1124`。

这意味着离线路径还没有统一的：

- `meta`
- `preflight`
- 顶层 `availability`
- `evidence_index`
- `resources.textures[] / resources.buffers[]` 正式分层
- `findings[] / recommendations[]` 结构化输出

### 4.2 模板契约已经漂移

`template_contract_v1` 规定 `events.html` 是必需页面，且它消费 `actions / passes / evidence_index`，见 `docs/product/template_contract_v1.md:41`。

但当前 legacy generator 的 `manifest.json` 页面清单只有：

- `index.html`
- `textures.html`
- `shaders.html`
- `recommendations.html`

见 `scripts/rdc_analyzer/report_bundle_generator.py:1541`。

更关键的是：

- `report_bundle_generator.py` 明明有 `generate_events()`，见 `scripts/rdc_analyzer/report_bundle_generator.py:1047`
- 但 `generate_all()` 并没有写出 `events.html`，见 `scripts/rdc_analyzer/report_bundle_generator.py:1567`
- `xml_to_bundle.py` 结尾却仍然告诉用户 “Pages: index/events/textures/shaders”，见 `scripts/rdc_analyzer/xml_to_bundle.py:1152`

这说明当前离线路径已经出现“代码、manifest、CLI 文案”三者不一致。

### 4.3 `xml_to_bundle.py` 绕过了 generator 的正式接口

`ReportBundleGenerator` 提供了：

- `set_textures()`，见 `scripts/rdc_analyzer/report_bundle_generator.py:252`
- `set_events()`，见 `scripts/rdc_analyzer/report_bundle_generator.py:272`
- `set_shaders()`，见 `scripts/rdc_analyzer/report_bundle_generator.py:293`
- `set_performance_data()`，见 `scripts/rdc_analyzer/report_bundle_generator.py:358`
- `set_resource_usage_index()`，见 `scripts/rdc_analyzer/report_bundle_generator.py:382`

并且 helper `generate_report_bundle()` 会按正式 API 调用它们，见 `scripts/rdc_analyzer/report_bundle_generator.py:1636`。

但 `xml_to_bundle.py` 当前并没有走这条路，而是直接写内部字段：

- `generator.events = events`
- `generator.textures = textures`
- `generator.shaders = shaders`

见 `scripts/rdc_analyzer/xml_to_bundle.py:1119`。

这会带来两个问题：

1. generator 的“数据入口契约”被绕开，后续谁都可以继续往私有字段堆逻辑。
2. `performance_data`、`texture_usage_map`、`resource_usage_index` 这些本应统一注入的事实，没有在 `xml_to_bundle.py` 中形成正式 builder 流程。

### 4.4 离线页面对 `performance_data` 依赖很强，但 XML 脚本没有构建它

index 页面会从 `performance_data` 里读取：

- `api`
- `gpu`
- `resolution`

见 `scripts/rdc_analyzer/report_bundle_generator.py:780`。

recommendations 页面会从 `performance_data` 读取：

- `issues`
- `suggestions / recommendations`

见 `scripts/rdc_analyzer/report_bundle_generator.py:1267`。

但是 `xml_to_bundle.py` 没有调用 `set_performance_data()`，见 `scripts/rdc_analyzer/xml_to_bundle.py:1116` 到 `scripts/rdc_analyzer/xml_to_bundle.py:1137`。

因此当前离线路径其实没有形成一个稳定的“离线 findings/recommendations”事实层，只是把 legacy 页面拼出来了。

### 4.5 当前输出仍然不是“模板只读快照”模式

`template_contract_v1` 明确要求模板组件只读 `snapshot.v1` 字段，不得直接读 XML / ReplayController 私有结构，见 `docs/product/template_contract_v1.md:217`。

而 `ReportBundleGenerator` 现在直接消费它自己的内部 Python dict 模型：

- `self.textures`
- `self.events`
- `self.shaders`
- `self.performance_data`

见 `scripts/rdc_analyzer/report_bundle_generator.py:158` 到 `scripts/rdc_analyzer/report_bundle_generator.py:172`。

这说明当前离线 HTML 还不是“快照驱动”，而是“generator 私有模型驱动”。

## 5. 分层结论

### 第 1 轮：表面分析

离线路径看起来已经能“导出 HTML”，但它输出的是 legacy bundle，不是统一快照报告。

### 第 2 轮：机制验证

真正的数据流是 XML -> `xml_to_bundle_*_dict()` -> generator 私有结构 -> HTML。并没有 `snapshot.v1` builder，也没有 `template.v1` renderer。

### 第 3 轮：限制定位

这是实现/契约限制，不是理论限制。

- XML 数据本身当然不如 GUI 完整，这会导致某些字段只能 `availability=partial`。
- 但“没有统一快照层”“没有共享 renderer”“events 页面漂移”这些，都属于当前实现层的问题。

### 第 4 轮：方案评估

| 方案 | 做法 | 成本 | 风险 | 结论 |
| --- | --- | --- | --- | --- |
| A | 继续在 `xml_to_bundle.py` / `report_bundle_generator.py` 上追加逻辑，慢慢补齐 `snapshot.v1` 语义 | 中 | 高，容易继续形成第二套事实层 | 不推荐 |
| B | 新增 `OfflineSnapshotBuilder`，先稳定输出 `snapshot.v1.json`，再让共享 renderer 只吃快照 | 中 | 低到中，契约清晰 | 推荐 |
| C | 先把 GUI 的 `analysis.json` 当离线输入，再桥接为 `snapshot.v1` | 低 | 高，离线场景本来就不依赖 GUI，路径错误 | 不推荐 |

## 6. 推荐落地顺序

### 6.1 第一阶段：冻结离线统一快照输出

目标：不急着重写所有页面，先把离线路径的事实层钉死。

建议动作：

1. 新增 `OfflineSnapshotBuilder`，输入 XML parser 结果，输出 `snapshot.v1` dict。
2. 在 builder 中明确 `source=offline`、`report_surface=json_only|offline_html`、`availability=partial/full`。
3. `xml_to_bundle.py` 增加 `snapshot.v1.json` 输出，不再只产 legacy bundle。
4. legacy bundle 继续保留，但标记为 fallback/兼容路径。

### 6.2 第二阶段：把 HTML 渲染收束到共享 renderer

目标：让离线 HTML 不再直接读 generator 私有结构。

建议动作：

1. 新增 `SnapshotTemplateRenderer`，输入只有 `snapshot.v1`。
2. 页面产物按 `template_contract_v1` 统一：`index.html`、`events.html`、`textures.html`、`shaders.html`、`pipelines.html`、`manifest.json`。
3. `events.html`、`evidence_index`、`availability`、`preflight` 由 renderer 统一落地。

### 6.3 第三阶段：下沉 legacy generator 的职责

目标：避免两个 HTML 引擎长期并存。

建议动作：

1. 新 renderer 验证稳定后，把 legacy `ReportBundleGenerator` 降级为兼容模式。
2. CLI 默认切到 `snapshot.v1 + template.v1`。
3. legacy 只通过 `--legacy-bundle` 显式启用。

## 7. 对 Dev C 的直接开发要求

Dev C 的第一批任务应当是：

1. 建 builder，不再继续把业务逻辑堆进 `xml_to_bundle.py`。
2. 明确 `actions/resources/findings/recommendations/availability` 在离线路径的最小可用字段集。
3. 让 CLI 至少导出 `snapshot.v1.json`，作为 GUI / Skill / CI 共用输入。
4. 只有在 `snapshot.v1` builder 稳定后，才开始推进共享 HTML renderer。

## 8. 对总方案的影响

这份审计把一件事钉死了：

离线报告不是“继续修 legacy bundle 页面”，而是“先统一快照，再统一模板”。

这会直接降低三个方向的重复开发：

1. Dev B 不需要再对接 XML 私有字段，只对接 `snapshot.v1`。
2. Dev A 的 MCP + Skill 可以直接消费离线快照，并仅在缺口处用 MCP 补数。
3. Dev C 不会再维护一套与 GUI 脱节的事实命名体系。

# RenderDoc AI 开发总纲（v1）

> 状态：冻结产品边界与开发顺序的 SSOT 文档。  
> 适用范围：RenderDoc 魔改、Analyzer Report、HTML 离线报告、MCP、Skill。  
> 相关契约：`docs/product/snapshot_schema_v1.md`、`docs/product/template_contract_v1.md`、`docs/product/mcp_query_contract_v1.md`

## 1. 产品使命

我们要做的不是“再堆几个分析功能”，而是把 RenderDoc 演进成一个面向渲染程序员、游戏程序员、TA 的 **AI Native 图形分析工作台**：

- 在 GUI 内快速定位问题。
- 在无 GUI / CI / 批处理场景稳定导出结果。
- 在已加载捕获上做实时查询与补数。
- 把 AI 用在真正需要理解、归因、对比、生成脚本的地方，而不是复制一套报告系统。

北极星目标：

1. 单帧分析更快：把“打开捕获 -> 找到热点/异常 -> 跳回事件”缩短到分钟级。
2. 报告更可信：所有结论都能回链到 `event_id` / `resource_id` / `shader_id`。
3. 自动化更强：同一套事实数据可被 GUI、CLI、MCP、Skill 复用。
4. 架构更清晰：新需求先判断归属，再开发，不再出现重复导出、重复模板、重复 schema。

## 2. 三条主线

### 2.1 兼容性与采集底座

职责：

- RenderDoc 本体能力与魔改能力。
- 跨平台 / 跨设备 replay 的可用性验证与扩展。
- capture 打开、重放、资源读取、性能计时等底层事实来源。

典型问题：

- PC 上能否回放移动端抓到的 `.rdc`。
- 某 API / 驱动 / GPU 是否能提供所需字段。
- 某类数据缺失是理论限制、实现限制还是配置限制。

### 2.2 报告产品线

职责：

- 统一的 **Analyzer Report 事实引擎**。
- 两种交付路径：
  - GUI 报告：RenderDoc 内的主产品路径。
  - 离线/CI 报告：无 GUI、批量、回归、容灾路径。
- 统一的快照 schema 与统一模板契约。

关键约束：

- GUI 与离线必须复用同一份事实结构。
- GUI 与离线必须复用同一套 HTML 模板契约；原生 Qt Analyzer Report 可以不是 HTML，但信息架构和事实来源必须对齐。
- 报告系统是“确定性事实 + 规则结果”，不是 AI 自由生成文本。

### 2.3 智能协作线

职责：

- MCP：针对已加载 capture 的实时查询与补数接口。
- Skill：安装/自检 + AI 增值分析。

关键约束：

- MCP 不生成整份报告。
- Skill 不复制导出器、不复制模板、不复制确定性规则引擎。
- AI 的价值集中在：归因、解释、对比、脚本生成、行动建议。

## 3. 四大功能点在总架构中的位置

| 功能点 | 归属主线 | 核心产物 | 主要用户动作 | 不做什么 |
| --- | --- | --- | --- | --- |
| RenderDoc 魔改 / replay 扩展 | 底座 | 回放能力、兼容层、采样能力 | 打开 / 回放 / 读取 capture | 不直接承担报告排版 |
| Analyzer Report（GUI + Offline） | 报告 | HTML/Qt 报告、JSON 快照 | 看报告、跳事件、导出 | 不做开放式 AI 对话 |
| MCP | 智能协作 | 实时查询 API、局部 JSON、健康检查 | 询问局部事实、补缺失字段 | 不产整份报告 |
| Skill | 智能协作 | 安装自检、Markdown 简报、命令清单、分析脚本 | 问“为什么慢”“这个 Shader 在干什么” | 不复制报告引擎 |

## 4. Analyzer Report 的产品定位

这里必须统一认知：

- **Analyzer Report 不是与 GUI/离线/MCP/Skill 并列的第五套系统。**
- 它是“报告产品线”的事实引擎与规则引擎。
- GUI 报告、HTML 离线报告、未来的对比报告，都应建立在同一份快照与事实口径之上。

因此：

- `Window -> Analyzer Report` 是 GUI 内的主入口。
- `Export Report` 是 GUI 导出给分享/离线查看的交付方式。
- `renderdoccmd + CLI` 是离线/CI 入口。
- `MCP + Skill` 只消费这些事实，不再各自生成新一套报告页面。

## 5. 职责矩阵（避免重复开发）

| 能力 | GUI 报告 | 离线报告 | MCP | Skill |
| --- | --- | --- | --- | --- |
| 生成完整报告 | 主责 | 主责 | 否 | 否 |
| 批量/CI 运行 | 否 | 主责 | 否 | 可编排，不主责 |
| 实时读取已加载 capture | 可内部使用 | 否 | 主责 | 通过 MCP 使用 |
| 输出统一 JSON 快照 | 主责 | 主责 | 可导出局部，不主责 | 消费 |
| 环境安装/自检 | 否 | 否 | 基础健康检查 | 主责 |
| AI 归因 / 解释 / 脚本生成 | 否 | 否 | 否 | 主责 |
| 缺失字段补数 | 可提示 | 可提示 | 主责 | 通过 MCP 发起 |
| 回归对比 | 后续能力 | 后续主责 | 提供局部数据 | 主责（解释层） |

## 6. 明确不做什么

以下内容一律视为高风险重复开发：

1. 在 MCP 内再做一套完整 HTML 报告。
2. 在 Skill 内再做一套“报告导出器”或“模板系统”。
3. 为 GUI 和离线分别维护两套页面结构、两套字段命名、两套证据链。
4. 把 AI 自由文本直接当成事实数据持久化到基础快照里。
5. 在没有声明主线归属和冗余分析的情况下新增页面、按钮、脚本入口。

## 7. 统一产物与契约

本项目后续开发，统一围绕 4 个核心产物推进：

1. `development_charter.md`：定义产品边界、开发顺序、职责分工。
2. `snapshot_schema_v1.md`：定义 GUI/离线共享的事实快照。
3. `template_contract_v1.md`：定义 HTML 报告的页面与组件输入。
4. `mcp_query_contract_v1.md`：定义 MCP 查询结果与快照之间的映射关系。

约束：

- GUI / Offline / MCP / Skill 的任何新功能，都必须先说明它依赖上述哪份契约。
- 如果一个需求会导致“第二套 schema / 第二套模板 / 第二套报告系统”，默认先停下来回到 `/plan`。

## 8. 里程碑与顺序

### M0：总纲与契约冻结

- 写总纲。
- 写快照 schema。
- 写模板契约。
- 写 MCP 查询契约。
- 更新 `AGENTS.md`。

### M1：底座可用性与兼容性基线

- 梳理 PC replay 移动端 capture 的限制层次与改造路线。
- 明确 Vulkan / D3D11 / D3D12 数据可用性边界。
- 把“哪些字段是底座拿不到”从产品层面标注清楚。

### M2：统一快照与模板

- 把当前 GUI / 离线 / 旧 WebUI 的页面口径收束到统一模板契约。
- 快照先稳定，再做页面重构。

### M3：报告产品线稳定化

- GUI 内 `Analyzer Report` 与导出 HTML 对齐同一事实结构。
- 离线/CI 报告支持轻量 / 全量模式、缺失字段提示、统一证据链。

### M4：MCP 稳定化

- 本地桌面 MCP bridge、健康检查、查询 envelope、过滤与错误模型稳定。
- 面向 Skill 和脚本提供最小而稳定的局部查询面。

### M5：Skill MVP

- 安装/自检。
- 性能热点初步归因。
- Shader 公式/光照路径提取。
- 管线审阅。
- 回归对比摘要与命令清单。

### M6：对比与 CI 体系

- 双帧对比。
- 基于快照的回归判定。
- 报告、MCP、Skill 三线联动的 CI 工作流。

## 9. 三人并行开发分工

| 负责人 | 主线 | 主责任务 | 输入契约 | 输出 |
| --- | --- | --- | --- | --- |
| Dev A | 智能协作线 | MCP、Skill、安装自检、智能分析 | `mcp_query_contract_v1`、`snapshot_schema_v1` | MCP bridge / server / skill 文档与动作 |
| Dev B | 报告产品线（GUI） | GUI Analyzer Report、Export Report、Qt 集成 | `snapshot_schema_v1`、`template_contract_v1` | GUI 面板、导出入口、跳转体验 |
| Dev C | 报告产品线（Offline） | CLI、HTML 模板、统一 bundle | `snapshot_schema_v1`、`template_contract_v1` | 离线报告、模板、manifest |

协作规则：

- Dev C 先冻结快照与模板输入面，Dev B 才能稳定接入 GUI。
- Dev A 的 MCP 字段命名必须映射到快照 schema，不得另起术语体系。
- 跨模块改动时，必须在计划里写清楚受影响的契约与负责人。

## 10. 验收总线

### 产品验收

- 用户能明确区分“看报告”“查实时数据”“让 AI 解读”三类入口。
- 同一个问题不会要求用户在三套完全不同的页面/术语中来回切换。

### 工程验收

- 统一快照字段名稳定，不因 GUI/离线/MCP 来源不同而随意变动。
- 新功能进入开发前必须标注归属主线与依赖契约。
- 关键结论都具备 `event_id` / `resource_id` / `shader_id` 证据链。

### 体验验收

- GUI 主路径适合“快速定位”。
- HTML 离线适合“分享、归档、CI”。
- MCP + Skill 适合“问问题、补数据、做推理”。

## 11. 参考证据

- `docs/product/vision.md`
- `docs/product/gui_report.md`
- `docs/product/offline_report.md`
- `docs/product/mcp_api.md`
- `docs/product/skill_design.md`
- `docs/product/plan_breakdown.md`
- `docs/analysis/codex_rdc_analyzer/PERFORMANCE_REPORT_DESIGN.md`
- `docs/analysis/codex_rdc_analyzer/analysis_report_schema_v1.md`

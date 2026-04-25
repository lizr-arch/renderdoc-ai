# Native Qt `AnalyzerSnapshot` → `snapshot.v1` 对齐审计

> 2026-04-23 delta：本文下面的大部分内容仍然保留“审计时的旧基线”，但其中两条判断已部分过时：
> 1. `AnalyzerExporter` 现在已经可以输出 `snapshot.v1.json` 与 `capture_context.json`，不再只是 legacy 三件套。
> 2. 当前 B 线候选实现已把 GUI HTML 主路径接到 shared snapshot renderer：`AnalyzerReportViewer` -> `render_snapshot_bundle.py` -> `SnapshotTemplateRenderer`。
> 最新当前状态请优先读：`docs/product/delivery_surfaces_status.md`

> 状态：M2 审计文档。  
> 目标：明确当前 Native Qt Analyzer Report 的事实结构，找出它与 `docs/product/snapshot_schema_v1.md` 的差异，并给出最小改造切入点。  
> 适用范围：`qrenderdoc/Code/Analyzer/*`、`qrenderdoc/Windows/AnalyzerReportViewer.cpp`。

## 1. 结论先行

当前 Native Qt Analyzer Report 已经具备一个**可工作的本地事实结构**，但它还不是 `snapshot.v1`：

- 它更像是 `analysis.native.qt.v1`，面向当前 Qt 面板和导出 JSON。
- 它已经覆盖了事件、draw/dispatch、state thrash、pipeline bandwidth、gpu counters、resources、shaders、issues。
- 但它缺少 `snapshot.v1` 要求的统一顶层结构、可用性声明、证据索引、recommendation 独立块、preflight/meta 等关键块。

因此最合理的 M2 路线不是重写 Native Qt，而是：

1. 保留 `AnalyzerSnapshot` 作为 **GUI 内部原始事实结构**。
2. 新增一层 `AnalyzerSnapshot -> snapshot.v1` adapter。
3. 让导出链优先输出 `snapshot.v1`，同时可保留 legacy `analysis.json` 兼容已有脚本。

## 2. 当前 Native Qt 的事实结构

### 2.1 顶层结构

`qrenderdoc/Code/Analyzer/AnalyzerTypes.h:178-190`

当前 `AnalyzerSnapshot` 顶层字段是：

- `schemaVersion = "analysis.native.qt.v1"`
- `summary`
- `events`
- `drawDispatch`
- `stateThrash`
- `pipelineBandwidth`
- `gpuCounters`
- `resources`
- `shaders`
- `issues`

这说明当前结构已经具备“分析结果”的骨架，但还是**按 Native Qt 当前页面需求切分**，不是统一产品契约。

### 2.2 子结构概览

证据：`qrenderdoc/Code/Analyzer/AnalyzerTypes.h:29-176`

- `AnalyzerEvidence`
  - `metric`, `value`, `unit`, `detail`, `hasThreshold`, `threshold`, `comparison`, `source`, `scope`
- `AnalyzerIssue`
  - `code`, `severity`, `category`, `message`, `eventIds`, `resourceIds`, `impactScore`, `confidence`, `evidence`, `recommendation`
- `AnalyzerEventRow`
  - `eid`, `name`, `type`, `drawIndex`, `passIndex`, `vs`, `ps`, `cs`, `rts`, `ds`
- `AnalyzerDrawDispatchRow`
  - `eid`, `name`, `type`, `numIndices`, `numInstances`, `dispatchDim`, `dispatchThreads`, `indirect`
- `AnalyzerStateThrashRow`
  - stage 级状态抖动统计
- `AnalyzerPipelineBandwidthRow`
  - `eid`, `name`, `rtCount`, `samples`, `blendEnabled`, `depthWrite`
- `AnalyzerGpuCounterRow`
  - `gpuTimeMs`, invocation counters, texture samples
- `AnalyzerResourceRow`
  - 资源维度统一放在一个数组里，靠 `kind` 区分
- `AnalyzerShaderRow`
  - shader 基础信息 + Mali 指标
- `AnalyzerSummary`
  - `api`, `frameNumber`, `drawCount`, `dispatchCount`, `textureCount`, `bufferCount`, `passCount`, `textureBytes`, `bufferBytes`

## 3. 当前 JSON 导出的真实结构

### 3.1 导出 JSON 顶层块

`qrenderdoc/Code/Analyzer/AnalyzerContract.cpp:213-272`

当前导出的顶层块是：

- `schema_version`
- `summary`
- `events`
- `draw_dispatch`
- `state_thrash`
- `pipeline_bandwidth`
- `gpu_counters`
- `resources`
- `shaders`
- `issues`

这和 `snapshot.v1` 的目标结构不同：

- 没有 `meta`
- 没有 `preflight`
- 没有 `overview`
- 没有 `timings`
- 没有 `passes`
- 没有 `recommendations`
- 没有 `evidence_index`
- 没有 `availability`

### 3.2 一个关键问题：Evidence 在导出时丢信息

`qrenderdoc/Code/Analyzer/AnalyzerTypes.h:29-40` 定义了 `AnalyzerEvidence` 有这些字段：

- `hasThreshold`
- `threshold`
- `comparison`
- `source`
- `scope`

但 `qrenderdoc/Code/Analyzer/AnalyzerContract.cpp:32-39` 的 `EvidenceToQJson()` 只导出：

- `metric`
- `value`
- `unit`
- `detail`

这意味着当前导出 JSON 是**有损导出**：

- evidence 的阈值来源与比较关系丢失
- 无法直接构成 `snapshot.v1` 中更强的 evidence / availability / verification 语义

这是 M2 很值得优先修的一个点。

## 4. 当前 GUI 生成链

### 4.1 快照构建

`qrenderdoc/Code/Analyzer/FrameAnalyzer.cpp:158-206`

当前 `FrameAnalyzer::Build()` 做的事情：

- 从 `FrameInfo` 填 `summary.api`, `frameNumber`, `drawCount`, `dispatchCount`
- 从 `GetTextures()` / `GetBuffers()` 累计资源数量与 bytes
- 通过 `FlattenActions()` 建立 `events` 和 `passIndex`
- 在 `frame.stats.recorded == false` 时，回退用 `drawDispatch` 重新统计 draw/dispatch 数量
- 补充：
  - `drawDispatch`
  - `stateThrash`
  - `pipelineBandwidth`
  - `gpuCounters`
  - `resources`
  - `shaderUsage`

这说明当前 Native Qt 的事实层不是空壳，已经有相当多可复用内容。

### 4.2 GUI 导出入口

`qrenderdoc/Windows/AnalyzerReportViewer.cpp:1217-1252`

当前 GUI 导出行为：

- 用户在 `Analyzer Report` 窗口点击 Export
- 调用 `m_Exporter.WriteAll(m_Snapshot, outDir, &error)`
- 导出提示明确写的是：
  - `analysis.json`
  - `issues_export.csv`
  - `issues_export.md`

也就是说，当前 GUI 导出不是我们新的“统一快照导出”，而是 Native Qt 自有的 legacy JSON 导出链。

### 4.3 导出器的当前能力

`qrenderdoc/Code/Analyzer/AnalyzerExporter.cpp:32-63`

`AnalyzerExporter::WriteAll()` 当前只做三件事：

- `WriteAnalysisJSON()`
- `WriteIssuesCSV()`
- `WriteIssuesMarkdown()`

没有：

- `snapshot.v1.json`
- `manifest.json`
- 统一 HTML bundle
- 可用性/缺失字段声明

## 5. 与 `snapshot.v1` 的映射关系

### 5.1 可以直接映射的部分

| Native Qt | `snapshot.v1` | 说明 |
| --- | --- | --- |
| `summary` | `overview.summary` | 直接映射 |
| `events` | `actions[]` 的一部分 | 需要字段改名 |
| `drawDispatch` | `actions[]` 的补充字段 | 需要 merge |
| `gpuCounters` | `timings` + `actions[].timing_ms` | 需要拆分 |
| `resources` | `resources.textures[]` / `resources.buffers[]` | 需要按 `kind` 分裂 |
| `shaders` | `shaders[]` | 基础上可映射 |
| `issues` | `findings[]` | 需要规范 severity/evidence 输出 |
| `issue.recommendation` | `recommendations[]` 的种子 | 需要拆出独立结构 |

### 5.2 只能部分映射的部分

| Native Qt | `snapshot.v1` | 差异 |
| --- | --- | --- |
| `pipelineBandwidth` | `pipelines[]` | 当前只有 `rtCount/samples/blendEnabled/depthWrite`，远不够完整 |
| `events.passIndex` | `passes[]` | 只有 pass 编号，没有 pass 对象 |
| `stateThrash` | `findings[]` 或附加分析块 | 需要决定落点 |
| `gpuCounters` | `timings` | 有 timing 与 invocation，但缺 availability 汇总 |

### 5.3 当前完全缺失的部分

| `snapshot.v1` 块 | 当前状态 | 说明 |
| --- | --- | --- |
| `meta` | 缺失 | 没有 source/generator/report_surface |
| `preflight` | 缺失 | 没有数据降级与捕获建议 |
| `availability` | 缺失 | 没有字段级可用性声明 |
| `evidence_index` | 缺失 | 没有全局 anchor 索引 |
| `passes[]` | 缺失 | 只有 `passIndex` |
| `recommendations[]` | 缺失 | recommendation 还嵌在 `issues[]` |
| `resources.textures[]` / `buffers[]` 分离 | 缺失 | 当前统一在 `resources[]` |
| `pipelines[]` 完整摘要 | 缺失 | 当前仅带宽摘要 |

## 6. 关键差异与风险

### 6.1 `actions[]` 需要合并两路数据

当前：

- `events[]` 提供 shader / RT / DS / passIndex
- `drawDispatch[]` 提供 indices / instances / dispatch dims

而 `snapshot.v1.actions[]` 希望每条 action 尽量集中在一个对象里。  
因此 adapter 必须做 merge，而不是简单 rename。

### 6.2 `issues[]` 与 `recommendations[]` 需要拆分

当前：

- recommendation 是 issue 的一个字符串字段

目标：

- `findings[]` 与 `recommendations[]` 分离
- recommendation 需要有自己的 `id`、`priority`、`rationale`、`verification_steps`

这意味着 adapter 初期可以先做“从 issue 派生 recommendation”的过渡实现，但长期应回到事实引擎里显式建模。

### 6.3 资源结构太扁平

当前 `resources[]` 只有：

- id / name / kind / bytes / width / height / depth / mips / array_size / samples / format

但 `snapshot.v1` 还希望有：

- usage_tags
- producer / consumer evidence
- texture / buffer 分离
- availability

说明当前资源层还只是“元数据罗列”，不是报告级资源事实模型。

### 6.4 当前导出缺少 `availability`

这会导致一个产品级风险：

- 用户无法区分“字段是真的没有”还是“当前路径拿不到”。

而这恰恰是我们总纲里最强调要修的事。

## 7. 最小改造切入点

### 7.1 第一阶段：不动 GUI 面板，先加 adapter

建议新增：

- `qrenderdoc/Code/Analyzer/AnalyzerSnapshotAdapter.h`
- `qrenderdoc/Code/Analyzer/AnalyzerSnapshotAdapter.cpp`

职责：

- 输入：`AnalyzerSnapshot`
- 输出：`snapshot.v1` 对应的 `QJsonObject` 或专用中间结构

优点：

- 不破坏 `AnalyzerReportViewer` 的现有 Refresh / Jump / Export 交互
- 不强迫 GUI 页面马上迁移到新模型
- 先把导出事实层统一，风险最小

### 7.2 第二阶段：扩 `AnalyzerExporter`

建议改造：

- `AnalyzerExporter::WriteAll()`

新增输出：

- `snapshot.v1.json`
- 可选保留 `analysis.json` 作为 legacy
- 后续再接 `manifest.json`

### 7.3 第三阶段：再考虑 Qt UI 对齐新契约

Native Qt 不必直接吃 HTML 模板，但应逐步对齐：

- section 结构
- evidence anchor 命名
- finding/recommendation 事实输入

## 8. 建议的落地顺序

1. 修 `AnalyzerEvidence` 的导出丢字段问题。
2. 新增 `AnalyzerSnapshot -> snapshot.v1` adapter。
3. 扩 `AnalyzerExporter` 输出 `snapshot.v1.json`。
4. 审计离线路径，决定是：
   - 直接消费 `snapshot.v1`
   - 还是先从 legacy `analysis.json` 桥接到 `snapshot.v1`

## 9. 对 Dev A / Dev B / Dev C 的直接影响

### Dev A（MCP + Skill）

- 在 `snapshot.v1` 未接入 GUI 之前，不应直接把 Native Qt 的 `analysis.json` 当最终 SSOT。
- 但可以先围绕 `snapshot.v1` 设计 Skill 输入，等待 adapter 落地。

### Dev B（GUI 报告）

- 最应该先做的是 adapter 和 exporter，不是马上改大面积 UI。
- 保持 `AnalyzerReportViewer` 现有主入口稳定。

### Dev C（离线报告 + 模板）

- 需要准备接收 `snapshot.v1`，而不是继续围绕多个 legacy JSON 漂移。

## 10. 参考

- `qrenderdoc/Code/Analyzer/AnalyzerTypes.h`
- `qrenderdoc/Code/Analyzer/AnalyzerContract.cpp`
- `qrenderdoc/Code/Analyzer/AnalyzerExporter.cpp`
- `qrenderdoc/Code/Analyzer/FrameAnalyzer.cpp`
- `qrenderdoc/Windows/AnalyzerReportViewer.cpp`
- `docs/product/snapshot_schema_v1.md`
- `docs/product/template_contract_v1.md`

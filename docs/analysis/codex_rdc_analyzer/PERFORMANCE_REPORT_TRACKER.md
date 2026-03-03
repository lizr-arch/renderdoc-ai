# Native Qt Analyzer Report 7 维度追踪文档（v1）

> 目标：把 7 个风险维度的 **/spec 分析**、**/plan 方案**、**实现进度** 合并到一个可追踪的入口，避免重复开发。  
> 适用范围：qrenderdoc 原生 Analyzer Report。  
> 参考：`docs/analysis/codex_rdc_analyzer/PERFORMANCE_REPORT_DESIGN.md`、`docs/analysis/codex_rdc_analyzer/report_risk_dimensions_v1.md`

---

## 0. 维度总览（状态矩阵）

| # | 维度 | /spec | /plan | 实现状态 | 主要数据源 | 跳转入口 |
|---|------|-------|-------|----------|------------|----------|
| 1 | Draw / Dispatch 密度 | ✅ | ✅ | 待做 | ActionDescription + FrameStatistics | Event Browser |
| 2 | 资源/状态抖动 | ✅ | ✅ | 待做 | FrameStatistics（D3D11） | Event / Pipeline |
| 3 | Pipeline 带宽 | ✅ | ✅ | 待做 | Replay PipeState | Event / Pipeline |
| 4 | Overdraw / Triangle Size | ✅ | ✅ | 待做 | Overlay | Overlay 可视化 |
| 5 | Buffer/Texture 更新与内存压力 | ✅ | ✅ | 待做 | ResourceUpdateStats + Texture/Buffer | Resource / Event |
| 6 | GPU 计时与计数器 | ✅ | ✅ | 待做 | GPUCounter / FetchCounters | Event Browser |
| 7 | Shader 维度（Mali Offline） | ✅ | ✅ | 进行中 | malioc | Shader Viewer |

说明：/plan 文档已按维度拆分，路径见本文件第 2 节。

---

## 1. 六个维度 /spec 分析（证据链 + 结论）

> 只记录事实与可行路径；无法确认处标记 **假设（待验证）**。

### 1. Draw / Dispatch 密度（小批次）
- **证据来源**：`ActionDescription` 提供 `numIndices` / `numInstances` / `dispatchDimension` / `dispatchThreadsDimension`  
  - `renderdoc/api/replay/data_types.h:2072-2126`
- **额外统计**：`FrameStatistics.draws` / `dispatches` 只在 D3D11 记录  
  - `renderdoc/api/replay/data_types.h:1678-1735`
- **现状**：`FrameAnalyzer` 仅记录事件类型与 EID，不含 draw/dispatch 规模  
  - `qrenderdoc/Code/Analyzer/FrameAnalyzer.cpp:115-138`
- **缺口**：需要在 AnalyzerSnapshot 增加 per-event 或聚合字段，用于排序与风险说明  
  - **假设（待验证）**：`numIndices` 对非 indexed draw 表示顶点数（文档写“indices or vertices”）
- **输出建议**：提供“小批次 Top N 列表 + 事件跳转”
- **置信度**：中（RDC 元数据可用，但没有 GPU 时间）

### 2. 资源/状态抖动（绑定频繁）
- **证据来源**：`FrameStatistics` 包含 `resources/samplers/constants/shaders` 与 `outputs/blends/depths/rasters`  
  - `renderdoc/api/replay/data_types.h:1701-1783`
- **现状**：Analyzer 未读取 FrameStatistics  
  - `qrenderdoc/Code/Analyzer/FrameAnalyzer.cpp` 未涉及 `FrameStatistics`
- **缺口**：需从 `IReplayController::GetFrameInfo()` 或 `ICaptureContext::FrameInfo()` 访问 stats 并解析  
  - `renderdoc/api/replay/renderdoc_replay.h:750-756`
- **输出建议**：按“shader/resource 变更次数”降序 + 跳转到首个异常事件
- **置信度**：中（D3D11 专有）

### 3. Pipeline 带宽（MRT / MSAA / Blend）
- **证据来源**：Replay 中 `PipeState` 可读 RT 数、MSAA、Blend 等  
  - `qrenderdoc/Code/Analyzer/FrameAnalyzer.cpp:278-285`（已有 `GetPipelineState()`）
- **现状**：Analyzer 仅提取 VS/PS/CS，不记录 MRT/MSAA/Blend  
  - `qrenderdoc/Code/Analyzer/FrameAnalyzer.cpp:271-283`
- **缺口**：需要扩展 Snapshot 存储 per-event Pipeline 摘要  
  - **假设（待验证）**：各 API 的 PipelineState Viewer 已提供对应字段，可复用读取逻辑
- **输出建议**：MRT 数 / MSAA 等级排序 + 事件跳转
- **置信度**：中（依赖 Replay）

### 4. Overdraw / Triangle Size
- **证据来源**：Overlay 通过 `TextureDisplay.overlay` 驱动  
  - `renderdoc/api/replay/control_types.h:612-616`
- **现状**：Analyzer 未触发 Overlay 采样  
  - 当前 Analyzer 仅收集 events/resources/shaders
- **缺口**：需要从 ReplayOutput/Overlay 路径采样并生成统计  
  - **假设（待验证）**：可复用 Texture Viewer 的 overlay 机制
- **输出建议**：Top N Pass/Draw + Overlay 跳转
- **置信度**：高（可视化直观）

### 5. Buffer/Texture 更新与内存压力
- **证据来源**：`ResourceUpdateStats`（calls/sizes/types）  
  - `renderdoc/api/replay/data_types.h:1265-1306`
- **额外资源规模**：Texture/Buffer bytes 已在 Analyzer 中可得  
  - `qrenderdoc/Code/Analyzer/FrameAnalyzer.cpp:93-103`
- **缺口**：需要把更新频率统计与资源大小结合，形成可排序的风险表  
  - **假设（待验证）**：非 D3D11 捕获缺少更新统计，需降级为“大小排序”
- **输出建议**：按 bytes / update calls 排序 + Resource/事件跳转
- **置信度**：中

### 6. GPU 计时与计数器（热点）
- **证据来源**：`IReplayController::FetchCounters` + `GPUCounter`  
  - `renderdoc/api/replay/renderdoc_replay.h:788-811`  
  - `renderdoc/api/replay/replay_enums.h:3887-3928`
- **现状**：Analyzer 未拉取 counters  
  - `qrenderdoc/Code/Analyzer/FrameAnalyzer.cpp` 未涉及 counters
- **缺口**：需要新增 counter 采样并与事件对齐  
  - **假设（待验证）**：部分平台 counters 不可用时需要降级
- **输出建议**：Top GPU time / invocations + 事件跳转
- **置信度**：高（硬件计数器）

---

## 2. /plan 文档入口（7 份）

> 每个维度对应 1 份 plan 文件（命名含维度编号）。

1. `plans/2026-03-03-210001-Agent01-PerfDim-01-DrawDispatch.md`  
2. `plans/2026-03-03-210002-Agent01-PerfDim-02-StateThrash.md`  
3. `plans/2026-03-03-210003-Agent01-PerfDim-03-PipelineBandwidth.md`  
4. `plans/2026-03-03-210004-Agent01-PerfDim-04-OverdrawTriangle.md`  
5. `plans/2026-03-03-210005-Agent01-PerfDim-05-ResourceUpdates.md`  
6. `plans/2026-03-03-210006-Agent01-PerfDim-06-GPUCounters.md`  
7. `plans/2026-03-03-210007-Agent01-PerfDim-07-ShaderMali.md`

---

## 3. 执行顺序

1. 先完成 **维度 7（Shader/Mali）** 的收尾与验证  
2. 再按 1 → 6 的顺序逐项实施  
3. 每完成一个维度，更新本追踪表与总计划文件

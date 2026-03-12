# Perf Dimension 01 - Draw/Dispatch 密度（小批次）Refine

**Version:** 2026-03-04  
**Owner:** Agent01  
**Plan File:** `plans/2026-03-04-184500-Agent01-PerfDim-01-DrawDispatch-Refine.md`

## Scope / Assumptions

### Scope (In)
- 补齐维度 01 的**分析说明文档**（阈值、排序方式、数据来源、置信度）
- **跨 API** 的 Draw/Dispatch 计数回退（FrameStatistics 未记录时）
- 明确 UI 的**使用方式**（过滤 + 排序找到小批次）

### Scope (Out)
- GPU 时间/计数器（维度 06）
- Dispatch 线程效率的复杂启发式（仅基于现有维度字段）

### Assumptions
- `ActionDescription::numIndices` 对非 indexed draw 表示顶点数  
  证据：`renderdoc/api/replay/data_types.h:2076`  
- 小批次阈值沿用脚本侧默认阈值（100 顶点 / 10%）  
  证据：`scripts/rdc_analyzer/config/thresholds.py:70-71`

---

## Build / Test / Lint Quick Guide (记录，不在 /plan 执行)

### Build (需用户授权)
- `E:\Program Files\Microsoft Visual Studio\2022\Community\MSBuild\Current\Bin\MSBuild.exe renderdoc.sln /p:Configuration=Development /p:Platform=x64 /m`

### Unit
- `D:\Code\git\renderdoc\x64\Development\qrenderdoc.exe --unittest "[analyzer]"`

### Manual Acceptance
- 打开 Vulkan / D3D11 capture → Analyzer Report  
- Draw/Dispatch 表：过滤 `draw` + 按 Indices 升序 → 小批次在前  
- Summary 区：Draw/Dispatch 计数非 0（Vulkan 也能显示）

---

## File List (精确到行号范围)

- `renderdoc/api/replay/data_types.h:2076-2126`（ActionDescription 指标字段）
- `renderdoc/api/replay/data_types.h:1682-1735`（FrameStatistics）
- `qrenderdoc/Code/Analyzer/AnalyzerTypes.h:70-190`（Draw/Dispatch 行与摘要）
- `qrenderdoc/Code/Analyzer/FrameAnalyzer.cpp:166-257`（summary 计数 + Draw/Dispatch 采集）
- `qrenderdoc/Windows/AnalyzerModels.h:98-140`（AnalyzerDrawDispatchModel）
- `qrenderdoc/Windows/AnalyzerModels.cpp:327-483`（表头/排序/展示）
- `qrenderdoc/Windows/AnalyzerReportViewer.cpp:917-975`（默认排序 + 表格布局）
- `docs/analysis/codex_rdc_analyzer/report_risk_dimensions_v1.md:695-740`（维度 01 标准）
- `docs/analysis/codex_rdc_analyzer/PERFORMANCE_REPORT_TRACKER.md:1084-1135`（维度 01 追踪）

---

## Design / Pseudocode (完整实现草案)

### 1) 跨 API Draw/Dispatch 计数回退

```cpp
// FrameAnalyzer.cpp (Build 阶段 after PopulateDrawDispatch)
if(!frame.stats.recorded)
{
  uint32_t drawCount = 0;
  uint32_t dispatchCount = 0;
  for(const AnalyzerDrawDispatchRow &row : snapshot.drawDispatch)
  {
    if(row.type == "draw") drawCount++;
    else if(row.type == "dispatch") dispatchCount++;
  }
  snapshot.summary.drawCount = drawCount;
  snapshot.summary.dispatchCount = dispatchCount;
}
```

### 2) 文档落地（维度 01）

- 风险信号：`numIndices/numInstances` 过小  
- 阈值：默认 `< 100 vertices`（脚本默认）  
- 使用方式：过滤 `draw`，按 Indices **升序** 排序，小批次在前

---

## Impact Analysis

- **Performance**：O(N) 统计（N=Draw/Dispatch 数），可忽略  
- **UX**：Vulkan 也能看到正确 Draw/Dispatch 计数  
- **Consistency**：与脚本阈值对齐，避免规则分裂

---

## Risks / Blockers

1. `numIndices` 在非 indexed draw 语义为“顶点数” → 仍需保持文档说明  
2. Dispatch 小批次阈值暂无统一标准 → 暂不引入硬阈值
3. 缺少 `FrameAnalyzer` 的测试夹具，难以构造“Vulkan capture summary=0”的失败用例

---

## Task Checklist (2-5 分钟粒度, TDD)

- [x] 更新维度 01 文档（阈值 + 使用方式 + 置信度）  
- [x] 更新追踪文档的维度 01 状态与证据链  
- [ ] 写失败用例：Vulkan capture summary 计数为 0（预期 FAIL）  
- [x] 实现计数回退逻辑  
- [x] 运行 unittest，预期 PASS  
- [ ] 手工验收：Draw/Dispatch 计数 + 小批次定位流程  
- [x] 提交（Conventional Commits）

---

## Verification / Acceptance (Definition of Done)

- 文档明确说明小批次阈值与排序方法  
- Vulkan/D3D11 都能显示非 0 Draw/Dispatch 计数  
- `qrenderdoc.exe --unittest "[analyzer]"` 通过  

---

## /do Execution Log

- 2026-03-04
  - 更新维度 01 文档（阈值/排序/使用方式）。
  - 更新追踪文档（补齐 Draw/Dispatch 现状与缺口）。
  - 已实现 Draw/Dispatch 计数回退（FrameStatistics 未记录时）。
  - 单测：缺少 FrameAnalyzer 测试夹具，未能新增失败用例（记录为 blocker）。
  - unittest：`qrenderdoc.exe --unittest "[analyzer]"`（PASS）
  - 提交：`fix(qrenderdoc-analyzer): fallback draw/dispatch counts when stats missing`
  - MSBuild：PASS（Development|x64）

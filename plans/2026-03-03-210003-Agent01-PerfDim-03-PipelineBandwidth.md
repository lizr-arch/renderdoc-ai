# Perf Dimension 03 - Pipeline 带宽（MRT / MSAA / Blend）

**Version:** 2026-03-03  
**Owner:** Agent01  
**Plan File:** `plans/2026-03-03-210003-Agent01-PerfDim-03-PipelineBandwidth.md`

## Scope / Assumptions

### Scope (In)
- 采集每个 draw/dispatch 的 MRT 数量、MSAA 等级、Blend/DepthWrite 状态  
- 生成“Pipeline 带宽风险”排序列表  
- 支持跳转到 Event + Pipeline State

### Scope (Out)
- Overlay 与 GPU Counters（由维度 04/06 处理）

### Assumptions
- `PipeState` 可提供 RT/MSAA/Blend/DepthWrite 等字段（按 API 解析）  
  证据：`qrenderdoc/Code/Analyzer/FrameAnalyzer.cpp:278-285` 已调用 `GetPipelineState()`

---

## Build / Test / Lint Quick Guide (记录，不在 /plan 执行)

### Build (需用户授权)
- `E:\Program Files\Microsoft Visual Studio\2022\Community\MSBuild\Current\Bin\MSBuild.exe renderdoc.sln /p:Configuration=Development /p:Platform=x64 /m`

### Unit
- `D:\Code\git\renderdoc\x64\Development\qrenderdoc.exe --unittest "[analyzer]"`

### Manual Acceptance
- 打开 capture → Analyzer Report → Performance/Pipeline Tab  
- 验证 MRT/MSAA 排序 + 跳转到 Pipeline State

---

## File List (精确到行号范围)

- `qrenderdoc/Code/Analyzer/FrameAnalyzer.cpp:278-285`（GetPipelineState 入口）
- `qrenderdoc/Code/Analyzer/AnalyzerTypes.h:56-133`（新增 PipelineBandwidthRow + Snapshot 扩展）
- `qrenderdoc/Code/Analyzer/FrameAnalyzer.h:31-49`（新增 PopulatePipelineBandwidth）
- `qrenderdoc/Code/Analyzer/FrameAnalyzer.cpp:254-318`（新增 PopulatePipelineBandwidth 实现区）
- `qrenderdoc/Code/Analyzer/AnalyzerContract.cpp:72-175`（导出 pipeline_bandwidth）
- `qrenderdoc/Windows/AnalyzerModels.h:134-197`（新增 AnalyzerPipelineBandwidthModel）
- `qrenderdoc/Windows/AnalyzerModels.cpp:213-774`（model/排序实现）
- `qrenderdoc/Windows/AnalyzerReportViewer.ui:118-570`（新增 Performance/Pipeline Tab）
- `qrenderdoc/Windows/AnalyzerReportViewer.cpp:330-540`（绑定模型 + 跳转）

---

## Design / Pseudocode (完整实现草案)

```cpp
// AnalyzerTypes.h
struct AnalyzerPipelineBandwidthRow
{
  uint32_t eid = 0;
  rdcstr name;
  uint32_t rtCount = 0;
  uint32_t samples = 1;
  bool blendEnabled = false;
  bool depthWrite = false;
};
```

```cpp
// FrameAnalyzer.cpp
void FrameAnalyzer::PopulatePipelineBandwidth(ICaptureContext &ctx, AnalyzerSnapshot &snap,
                                              IReplayController *replay) const
{
  if(!replay)
    return;

  for(const AnalyzerEventRow &event : snap.events)
  {
    if(event.eid == 0 || event.type != "draw")
      continue;

    replay->SetFrameEvent(event.eid, false);
    const PipeState &pipe = replay->GetPipelineState();

    AnalyzerPipelineBandwidthRow row;
    row.eid = event.eid;
    row.name = event.name;
    row.rtCount = pipe.GetOutputTargets().size();
    row.samples = pipe.GetMSAASamples();
    row.blendEnabled = pipe.IsBlendEnabled();
    row.depthWrite = pipe.IsDepthWriteEnabled();
    snap.pipelineBandwidth.push_back(row);
  }
}
```

---

## Impact Analysis

- **Performance**：逐事件读取 PipeState，成本中等  
- **UX**：按 MRT/MSAA 排序，直观定位带宽风险  
- **Maintenance**：不同 API 字段需统一抽象

---

## Risks / Blockers

1. PipeState API 差异 → 需要统一 helper  
2. 频繁 SetFrameEvent 可能增加加载时间

---

## Task Checklist (2-5 分钟粒度, TDD)

- [ ] 新增失败单测：PipelineBandwidth model 排序（rtCount/samples）  
- [ ] 运行 unittest，预期 FAIL  
- [ ] 实现 AnalyzerTypes/FrameAnalyzer/Models/UI  
- [ ] 再跑 unittest，预期 PASS  
- [ ] 手工验收：跳转到 Pipeline State  
- [ ] 提交（Conventional Commits）

---

## Verification / Acceptance (Definition of Done)

- Pipeline 表格可按 MRT/MSAA 排序  
- 跳转到事件 + Pipeline State  
- Build + unittest 通过

---

## /do Execution Log

> 待执行

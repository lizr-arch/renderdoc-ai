# Perf Dimension 06 - GPU 计时与计数器（热点）

**Version:** 2026-03-03  
**Owner:** Agent01  
**Plan File:** `plans/2026-03-03-210006-Agent01-PerfDim-06-GPUCounters.md`

## Scope / Assumptions

### Scope (In)
- FetchCounters 获取 EventGPUDuration / VS/PS/CS invocations  
- 生成热点排序列表（GPU time 优先）  
- 跳转到对应 Event

### Scope (Out)
- Mali Offline（维度 07）

### Assumptions
- `IReplayController::FetchCounters` 支持批量获取  
  证据：`renderdoc/api/replay/renderdoc_replay.h:788-794`  
- 可用 counters 通过 `EnumerateCounters()` 判断  
  证据：`renderdoc/api/replay/renderdoc_replay.h:796-803`

---

## Build / Test / Lint Quick Guide (记录，不在 /plan 执行)

### Build (需用户授权)
- `E:\Program Files\Microsoft Visual Studio\2022\Community\MSBuild\Current\Bin\MSBuild.exe renderdoc.sln /p:Configuration=Development /p:Platform=x64 /m`

### Unit
- `D:\Code\git\renderdoc\x64\Development\qrenderdoc.exe --unittest "[analyzer]"`

### Manual Acceptance
- Analyzer Report → Performance/GPU Counters Tab  
- 按 GPU 时间排序，跳转 Event Browser

---

## File List (精确到行号范围)

- `renderdoc/api/replay/renderdoc_replay.h:788-811`（FetchCounters / EnumerateCounters）
- `renderdoc/api/replay/replay_enums.h:3887-3928`（GPUCounter enum）
- `renderdoc/api/replay/data_types.h:2425-2508`（CounterResult）
- `qrenderdoc/Code/Analyzer/AnalyzerTypes.h:56-133`（新增 GpuCounterRow + Snapshot 扩展）
- `qrenderdoc/Code/Analyzer/FrameAnalyzer.cpp:254-318`（新增 PopulateGpuCounters）
- `qrenderdoc/Code/Analyzer/AnalyzerContract.cpp:72-175`（导出 gpu_counters）
- `qrenderdoc/Windows/AnalyzerModels.h:134-197`（新增 GpuCounterModel）
- `qrenderdoc/Windows/AnalyzerModels.cpp:213-774`（model/排序实现）
- `qrenderdoc/Windows/AnalyzerReportViewer.ui:118-570`（新增 Performance/GPU Counters Tab）
- `qrenderdoc/Windows/AnalyzerReportViewer.cpp:330-540`（绑定模型 + 跳转）

---

## Design / Pseudocode (完整实现草案)

```cpp
// AnalyzerTypes.h
struct AnalyzerGpuCounterRow
{
  uint32_t eid = 0;
  rdcstr name;
  double gpuTimeMs = 0.0;
  uint64_t vsInvocations = 0;
  uint64_t psInvocations = 0;
  uint64_t csInvocations = 0;
};
```

```cpp
// FrameAnalyzer.cpp
void FrameAnalyzer::PopulateGpuCounters(ICaptureContext &ctx, AnalyzerSnapshot &snap,
                                        IReplayController *replay) const
{
  if(!replay)
    return;

  rdcarray<GPUCounter> counters = {
    GPUCounter::EventGPUDuration,
    GPUCounter::VSInvocations,
    GPUCounter::PSInvocations,
    GPUCounter::CSInvocations,
  };

  rdcarray<CounterResult> results = replay->FetchCounters(counters);
  // 汇总到 map[eventId]，填充 AnalyzerGpuCounterRow
}
```

---

## Impact Analysis

- **Performance**：FetchCounters 代价中等，需采样策略  
- **UX**：热点排序直达，置信度最高  
- **Maintenance**：不同 GPU/驱动可用 counters 不一致

---

## Risks / Blockers

1. 部分 capture 不支持 counters → 需显示不可用  
2. counters 采样耗时影响体验

---

## Task Checklist (2-5 分钟粒度, TDD)

- [ ] 新增失败单测：GpuCounter model 排序  
- [ ] 运行 unittest，预期 FAIL  
- [ ] 实现 AnalyzerTypes/FrameAnalyzer/Models/UI  
- [ ] 再跑 unittest，预期 PASS  
- [ ] 手工验收  
- [ ] 提交（Conventional Commits）

---

## Verification / Acceptance (Definition of Done)

- GPU 热点列表可排序  
- 事件跳转有效  
- Build + unittest 通过

---

## /do Execution Log

> 待执行

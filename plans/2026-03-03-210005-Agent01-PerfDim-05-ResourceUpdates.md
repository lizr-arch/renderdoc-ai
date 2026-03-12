# Perf Dimension 05 - Buffer/Texture 更新与内存压力

**Version:** 2026-03-03  
**Owner:** Agent01  
**Plan File:** `plans/2026-03-03-210005-Agent01-PerfDim-05-ResourceUpdates.md`

## Scope / Assumptions

### Scope (In)
- 资源大小排序（Texture/Buffer bytes）  
- 资源更新统计（ResourceUpdateStats calls/sizes/types）  
- 提供资源跳转 + 更新统计摘要

### Scope (Out)
- 逐事件 GPU time（维度 06）

### Assumptions
- `ResourceUpdateStats` 为帧级统计（非 per-resource）  
  证据：`renderdoc/api/replay/data_types.h:1265-1306`

---

## Build / Test / Lint Quick Guide (记录，不在 /plan 执行)

### Build (需用户授权)
- `E:\Program Files\Microsoft Visual Studio\2022\Community\MSBuild\Current\Bin\MSBuild.exe renderdoc.sln /p:Configuration=Development /p:Platform=x64 /m`

### Unit
- `D:\Code\git\renderdoc\x64\Development\qrenderdoc.exe --unittest "[analyzer]"`

### Manual Acceptance
- Analyzer Report → Performance/Resource Pressure Tab  
- 资源大小排序 + 更新统计摘要

---

## File List (精确到行号范围)

- `renderdoc/api/replay/data_types.h:1265-1306`（ResourceUpdateStats）
- `qrenderdoc/Code/Analyzer/FrameAnalyzer.cpp:93-103`（Texture/Buffer bytes 已有）
- `qrenderdoc/Code/Analyzer/AnalyzerTypes.h:56-133`（新增 ResourcePressureRow/UpdateBucketRow）
- `qrenderdoc/Code/Analyzer/FrameAnalyzer.cpp:254-318`（新增 PopulateResourceUpdates）
- `qrenderdoc/Code/Analyzer/AnalyzerContract.cpp:72-175`（导出 resource_pressure）
- `qrenderdoc/Windows/AnalyzerModels.h:134-197`（新增 ResourcePressureModel/UpdateBucketModel）
- `qrenderdoc/Windows/AnalyzerModels.cpp:213-774`（model/排序实现）
- `qrenderdoc/Windows/AnalyzerReportViewer.ui:118-570`（新增 Performance/Resource Pressure Tab）
- `qrenderdoc/Windows/AnalyzerReportViewer.cpp:330-540`（绑定模型 + 跳转）

---

## Design / Pseudocode (完整实现草案)

```cpp
// AnalyzerTypes.h
struct AnalyzerResourcePressureRow
{
  ResourceId id;
  rdcstr name;
  rdcstr kind;
  uint64_t bytes = 0;
};

struct AnalyzerUpdateBucketRow
{
  rdcstr label; // e.g. "0-64KB"
  uint32_t count = 0;
};
```

```cpp
// FrameAnalyzer.cpp
void FrameAnalyzer::PopulateResourceUpdates(ICaptureContext &ctx, AnalyzerSnapshot &snap) const
{
  // 1) 资源大小：直接复用 resources 列表，筛选 Top N
  // 2) 更新统计：FrameStatistics.updates.sizes / types → 生成 bucket 行
}
```

---

## Impact Analysis

- **Performance**：帧级统计解析，开销低  
- **UX**：一眼看出大资源 + 更新热点  
- **Maintenance**：D3D11 专有统计需标注不可用

---

## Risks / Blockers

1. ResourceUpdateStats 非 per-resource → 只能做聚合统计  
2. 非 D3D11 捕获统计缺失

---

## Task Checklist (2-5 分钟粒度, TDD)

- [ ] 新增失败单测：ResourcePressure model 排序  
- [ ] 运行 unittest，预期 FAIL  
- [ ] 实现 AnalyzerTypes/FrameAnalyzer/Models/UI  
- [ ] 再跑 unittest，预期 PASS  
- [ ] 手工验收  
- [ ] 提交（Conventional Commits）

---

## Verification / Acceptance (Definition of Done)

- 资源大小排序正确  
- 更新统计摘要可见  
- Build + unittest 通过

---

## /do Execution Log

> 待执行

# Pipeline Samples 表头明确 + 纹理采样次数（GPU Counters）规划

**Version:** 2026-03-04  
**Owner:** Agent01  
**Plan File:** `plans/2026-03-04-143000-Agent01-PipelineHeader-TextureSamplingCounters.md`

## Scope / Assumptions

### Scope (In)
- Pipeline tab 的 Samples 列改名为 **MSAA Samples (RT/DS)** 并添加 tooltip 解释来源  
- 在维度 06（GPU Counters）中规划/实现“纹理采样次数”列：基于可用 counters 动态检测

### Scope (Out)
- 纹理采样次数的离线估算（Mali offline）  
- 任何跨设备强制可用的“真实采样次数”保证（依赖驱动/硬件提供）

### Assumptions
- `AnalyzerPipelineBandwidthModel::headerData` 支持 `Qt::ToolTipRole`（已有案例）  
  证据：`qrenderdoc/Windows/AnalyzerModels.cpp:92`  
- `EnumerateCounters()` 可用以检测当前 capture 的可用 counters  
  证据：`renderdoc/api/replay/renderdoc_replay.h:801`

---

## Build / Test / Lint Quick Guide (记录，不在 /plan 执行)

### Build (需用户授权)
- `E:\Program Files\Microsoft Visual Studio\2022\Community\MSBuild\Current\Bin\MSBuild.exe renderdoc.sln /p:Configuration=Development /p:Platform=x64 /m`

### Unit
- `D:\Code\git\renderdoc\x64\Development\qrenderdoc.exe --unittest "[analyzer]"`

### Manual Acceptance
- Pipeline tab：列头显示 **MSAA Samples (RT/DS)**，tooltip 明确来源  
- GPU Counters tab：若存在纹理相关 counters，显示“纹理采样次数”列并可排序/跳转

---

## File List (精确到行号范围)

### Pipeline 表头与 tooltip
- `qrenderdoc/Windows/AnalyzerModels.cpp:673-710`（Pipeline headerData：显示名 + tooltip）

### 纹理采样次数（维度 06 扩展）
- `renderdoc/api/replay/renderdoc_replay.h:794-811`（EnumerateCounters/FetchCounters）  
- `renderdoc/api/replay/data_types.h:2329-2468`（CounterDescription/CounterResult）  
- `qrenderdoc/Code/Analyzer/AnalyzerTypes.h:56-133`（新增字段，GpuCounterRow 扩展）  
- `qrenderdoc/Code/Analyzer/FrameAnalyzer.cpp:254-318`（PopulateGpuCounters 扩展：动态选择纹理 counters）  
- `qrenderdoc/Code/Analyzer/AnalyzerContract.cpp:72-175`（导出 gpu_counters 新字段）  
- `qrenderdoc/Windows/AnalyzerModels.h:134-197`（GpuCounterModel 新列）  
- `qrenderdoc/Windows/AnalyzerModels.cpp:213-774`（显示/排序逻辑）  
- `qrenderdoc/Windows/AnalyzerReportViewer.ui:118-570`（GPU Counters tab 列更新）  
- `qrenderdoc/Windows/AnalyzerReportViewer.cpp:330-540`（模型绑定 + 排序）

---

## Design / Pseudocode

### A) Pipeline Samples 表头与 tooltip
```cpp
// AnalyzerPipelineBandwidthModel::headerData
if(role == Qt::DisplayRole && section == ColSamples)
  return QObject::tr("MSAA Samples (RT/DS)");
if(role == Qt::ToolTipRole && section == ColSamples)
  return QObject::tr("Max MSAA samples among RT/DS. From texture msSamp / pipeline multisample.");
```

### B) 纹理采样次数动态检测（维度 06）
```cpp
bool IsTextureSampleCounter(const CounterDescription &desc)
{
  rdcstr text = (desc.name + " " + desc.category + " " + desc.description).lower();
  return text.contains("texture") || text.contains("texel") || text.contains("sampler");
}

// PopulateGpuCounters:
available = replay->EnumerateCounters();
for(c in available) desc = replay->DescribeCounter(c);
pick first texture-related counter; if none -> mark N/A
```

---

## Impact Analysis

- **UX**：避免误解 “Samples” = 纹理采样次数；明确 MSAA 来源  
- **Accuracy**：纹理采样次数仅当 counters 可用时显示，否则 N/A  
- **Performance**：EnumerateCounters + FetchCounters 代价中等，按需采样

---

## Risks / Blockers

1. 部分 Vulkan 驱动不提供纹理相关 counters → 需要显示 N/A  
2. 仅靠名字匹配可能误判 → 需记录来源与 counter 名称用于排查

---

## Task Checklist (2-5 分钟粒度, TDD)

- [x] 更新 Pipeline Samples 列标题 + tooltip  
- [x] 追加 GPU Counters 的纹理采样次数列（动态检测）  
- [x] 新增/更新排序单测  
- [x] Build + unittest  
- [x] 手工验收

---

## Verification / Acceptance (Definition of Done)

- Pipeline 表头明确显示 **MSAA Samples (RT/DS)**，tooltip 说明来源  
- GPU Counters tab 能显示纹理采样次数（可用时）或 N/A（不可用时）  
- Build + unittest 通过

---

## /do Execution Log

- 2026-03-04 16:22
  - 完成 Pipeline Samples 表头明确与 tooltip。
  - 完成 GPU Counters 维度：EventGPU/VS/PS/CS + 纹理采样计数器（动态检测）。
  - Build 失败：`LNK1168`，`D:\Code\git\renderdoc\x64\Development\renderdoc.dll` 被占用。
  - 2026-03-04 16:49 重新构建通过，unittest 通过。
- 2026-03-04
  - 用户验收通过。

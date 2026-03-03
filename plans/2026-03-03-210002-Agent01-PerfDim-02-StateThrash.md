# Perf Dimension 02 - 资源/状态抖动（绑定频繁）

**Version:** 2026-03-03  
**Owner:** Agent01  
**Plan File:** `plans/2026-03-03-210002-Agent01-PerfDim-02-StateThrash.md`

## Scope / Assumptions

### Scope (In)
- 解析 `FrameStatistics` 的 shader/resource/sampler/constant 绑定统计  
- 生成“状态抖动”排序列表（高频切换优先）  
- 支持跳转到首个异常事件（fallback to Event Browser）

### Scope (Out)
- GPU Counters（由维度 06 处理）

### Assumptions
- `FrameStatistics` 仅在 D3D11 捕获有效  
  证据：`renderdoc/api/replay/data_types.h:1678-1700`

---

## Build / Test / Lint Quick Guide (记录，不在 /plan 执行)

### Build (需用户授权)
- `E:\Program Files\Microsoft Visual Studio\2022\Community\MSBuild\Current\Bin\MSBuild.exe renderdoc.sln /p:Configuration=Development /p:Platform=x64 /m`

### Unit
- `D:\Code\git\renderdoc\x64\Development\qrenderdoc.exe --unittest "[analyzer]"`

### Manual Acceptance
- 打开 D3D11 capture → Analyzer Report → Performance/State Thrash Tab  
- 验证排序与跳转

---

## File List (精确到行号范围)

- `renderdoc/api/replay/data_types.h:1678-1783`（FrameStatistics 字段）
- `qrenderdoc/Code/Analyzer/AnalyzerTypes.h:56-133`（新增 StateThrashRow + Snapshot 扩展）
- `qrenderdoc/Code/Analyzer/FrameAnalyzer.cpp:82-113`（读取 FrameInfo.stats）
- `qrenderdoc/Code/Analyzer/FrameAnalyzer.cpp:254-318`（新增 PopulateStateThrash 实现区）
- `qrenderdoc/Code/Analyzer/AnalyzerContract.cpp:72-175`（导出 state_thrash）
- `qrenderdoc/Windows/AnalyzerModels.h:134-197`（新增 AnalyzerStateThrashModel）
- `qrenderdoc/Windows/AnalyzerModels.cpp:213-774`（model/排序实现）
- `qrenderdoc/Windows/AnalyzerReportViewer.ui:118-570`（新增 Performance/StateThrash Tab）
- `qrenderdoc/Windows/AnalyzerReportViewer.cpp:330-540`（绑定模型 + 跳转）

---

## Design / Pseudocode (完整实现草案)

```cpp
// AnalyzerTypes.h
struct AnalyzerStateThrashRow
{
  rdcstr stage; // VS/PS/CS/...
  uint32_t shaderChanges = 0;
  uint32_t resourceBinds = 0;
  uint32_t samplerBinds = 0;
  uint32_t constantBinds = 0;
  uint32_t redundantShaderBinds = 0;
  bool available = false;
};
```

```cpp
// FrameAnalyzer.cpp
void FrameAnalyzer::PopulateStateThrash(ICaptureContext &ctx, AnalyzerSnapshot &snap) const
{
  const FrameStatistics &stats = ctx.FrameInfo().stats;
  if(!stats.recorded)
    return;

  for(int s = 0; s < stats.shaders.count(); s++)
  {
    AnalyzerStateThrashRow row;
    row.stage = ToStr(ShaderStage(s));
    row.shaderChanges = stats.shaders[s].binds;
    row.redundantShaderBinds = stats.shaders[s].redundant;
    row.resourceBinds = stats.resources[s].binds;
    row.samplerBinds = stats.samplers[s].binds;
    row.constantBinds = stats.constants[s].binds;
    row.available = true;
    snap.stateThrash.push_back(row);
  }
}
```

---

## Impact Analysis

- **Performance**：仅解析 FrameStatistics，开销低  
- **UX**：新增 StateThrash Tab，默认按变更次数降序  
- **Maintenance**：D3D11 专有数据需明确标记“不可用”

---

## Risks / Blockers

1. 非 D3D11 捕获无统计 → 必须显示“Not Available”  
2. 统计为帧级而非 event 级，跳转只能给出参考事件

---

## Task Checklist (2-5 分钟粒度, TDD)

- [ ] 新增失败单测：StateThrash model 排序  
- [ ] 运行 unittest，预期 FAIL  
- [ ] 实现 AnalyzerTypes/FrameAnalyzer/Models/UI  
- [ ] 再跑 unittest，预期 PASS  
- [ ] 手工验收（D3D11 capture）  
- [ ] 提交（Conventional Commits）

---

## Verification / Acceptance (Definition of Done)

- D3D11 capture 显示 StateThrash 列表  
- 非 D3D11 显示不可用提示  
- 排序与跳转有效  
- Build + unittest 通过

---

## /do Execution Log

> 待执行

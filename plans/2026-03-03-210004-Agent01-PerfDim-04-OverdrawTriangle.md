# Perf Dimension 04 - Overdraw / Triangle Size

**Version:** 2026-03-03  
**Owner:** Agent01  
**Plan File:** `plans/2026-03-03-210004-Agent01-PerfDim-04-OverdrawTriangle.md`

## Scope / Assumptions

### Scope (In)
- 通过 Overlay 获取 Overdraw / Triangle Size 统计  
- 生成风险排序列表（高 overdraw / 小三角形优先）  
- 一键跳转到 Overlay 可视化

### Scope (Out)
- GPU Counters（维度 06）  

### Assumptions
- Overlay 由 `TextureDisplay.overlay` 驱动  
  证据：`renderdoc/api/replay/control_types.h:612-616`
- Overlay 结果可从 ReplayOutput 读取  
  证据：`renderdoc/replay/replay_controller.h:61-71`

---

## Build / Test / Lint Quick Guide (记录，不在 /plan 执行)

### Build (需用户授权)
- `E:\Program Files\Microsoft Visual Studio\2022\Community\MSBuild\Current\Bin\MSBuild.exe renderdoc.sln /p:Configuration=Development /p:Platform=x64 /m`

### Unit
- `D:\Code\git\renderdoc\x64\Development\qrenderdoc.exe --unittest "[analyzer]"`

### Manual Acceptance
- 打开 capture → Analyzer Report → Performance/Overdraw Tab  
- 点击条目 → Texture Viewer overlay 自动切换  

---

## File List (精确到行号范围)

- `renderdoc/api/replay/control_types.h:612-616`（TextureDisplay.overlay）
- `renderdoc/replay/replay_controller.h:61-71`（ReplayOutput overlay 接口）
- `qrenderdoc/Code/Analyzer/AnalyzerTypes.h:56-133`（新增 OverdrawRow + Snapshot 扩展）
- `qrenderdoc/Code/Analyzer/FrameAnalyzer.h:31-49`（新增 PopulateOverdraw）
- `qrenderdoc/Code/Analyzer/FrameAnalyzer.cpp:254-318`（新增 PopulateOverdraw 实现区）
- `qrenderdoc/Code/Analyzer/AnalyzerContract.cpp:72-175`（导出 overdraw）
- `qrenderdoc/Windows/AnalyzerModels.h:134-197`（新增 AnalyzerOverdrawModel）
- `qrenderdoc/Windows/AnalyzerModels.cpp:213-774`（model/排序实现）
- `qrenderdoc/Windows/AnalyzerReportViewer.ui:118-570`（新增 Performance/Overdraw Tab）
- `qrenderdoc/Windows/AnalyzerReportViewer.cpp:330-540`（绑定模型 + Overlay 跳转）

---

## Design / Pseudocode (完整实现草案)

```cpp
// AnalyzerTypes.h
struct AnalyzerOverdrawRow
{
  uint32_t eid = 0;
  rdcstr name;
  rdcstr overlayType; // quad_overdraw / triangle_size
  double metric = 0.0; // 平均 overdraw 或平均三角形像素面积
};
```

```cpp
// FrameAnalyzer.cpp
void FrameAnalyzer::PopulateOverdraw(ICaptureContext &ctx, AnalyzerSnapshot &snap,
                                      IReplayController *replay) const
{
  if(!replay)
    return;

  // 伪代码：对关键 draw 生成 overlay 并 readback，统计均值
  for(const AnalyzerEventRow &event : snap.events)
  {
    if(event.type != "draw")
      continue;
    // 1) SetFrameEvent
    // 2) 设置 TextureDisplay.overlay = QuadOverdraw or TriangleSize
    // 3) ReadbackOutputTexture → 统计均值
    // 4) 填充 AnalyzerOverdrawRow
  }
}
```

---

## Impact Analysis

- **Performance**：overlay readback 成本高，需要采样策略  
- **UX**：提供视觉直观的热点定位  
- **Maintenance**：overlay 与 TextureViewer 路径耦合

---

## Risks / Blockers

1. Overlay readback 性能成本高 → 需要 Top N 采样  
2. 不同 API 的 overlay 输出格式差异

---

## Task Checklist (2-5 分钟粒度, TDD)

- [ ] 新增失败单测：Overdraw model 排序  
- [ ] 运行 unittest，预期 FAIL  
- [ ] 实现 AnalyzerTypes/FrameAnalyzer/Models/UI  
- [ ] 再跑 unittest，预期 PASS  
- [ ] 手工验收：overlay 自动切换  
- [ ] 提交（Conventional Commits）

---

## Verification / Acceptance (Definition of Done)

- Overdraw/Triangle Size 列表可排序  
- 点击条目能切换到 Overlay  
- Build + unittest 通过

---

## /do Execution Log

> 待执行

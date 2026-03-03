# Perf Dimension 07 - Shader 维度（Mali Offline）

**Version:** 2026-03-03  
**Owner:** Agent01  
**Plan File:** `plans/2026-03-03-210007-Agent01-PerfDim-07-ShaderMali.md`

## Scope / Assumptions

### Scope (In)
- Mali Offline Compiler 输出字段展示（保持原始命名）  
- Shader 表格排序（有效值置顶）  
- 跳转到 Shader Viewer

### Scope (Out)
- GPU Counters（维度 06）

### Assumptions
- malioc 由本地安装或内置路径提供  
  证据：`qrenderdoc/Windows/AnalyzerReportViewer.cpp` Mali 相关逻辑

---

## Build / Test / Lint Quick Guide (记录，不在 /plan 执行)

### Build (需用户授权)
- `E:\Program Files\Microsoft Visual Studio\2022\Community\MSBuild\Current\Bin\MSBuild.exe renderdoc.sln /p:Configuration=Development /p:Platform=x64 /m`

### Unit
- `D:\Code\git\renderdoc\x64\Development\qrenderdoc.exe --unittest "[analyzer]"`

### Manual Acceptance
- Run Mali Analysis → Shader 表格数值填充  
- 升/降序排序  
- Jump to Shader

---

## File List (精确到行号范围)

- `qrenderdoc/Code/Analyzer/AnalyzerTypes.h:85-112`（AnalyzerShaderRow 字段）
- `qrenderdoc/Code/Analyzer/FrameAnalyzer.cpp:254-340`（shader 使用统计 + byteSize）
- `qrenderdoc/Code/Analyzer/AnalyzerContract.cpp:111-140`（shader JSON 导出）
- `qrenderdoc/Windows/AnalyzerModels.h:134-197`（Shader 表列定义）
- `qrenderdoc/Windows/AnalyzerModels.cpp:533-789`（Shader 表显示/排序）
- `qrenderdoc/Windows/AnalyzerReportViewer.cpp:1370-1760`（Mali 解析/匹配/跳转）

---

## Design / Pseudocode (完整实现草案)

```cpp
// AnalyzerTypes.h（已存在，仅示意）
struct AnalyzerShaderRow
{
  ResourceId id;
  rdcstr name;
  rdcstr stage;
  uint32_t byteSize = 0;
  // Mali 字段保持原名
};
```

```cpp
// FrameAnalyzer.cpp（已存在，仅示意）
shader.byteSize = ComputeShaderByteSize(replay, shaderId, resolvedStage, pipelineId);
```

---

## Impact Analysis

- **Performance**：Mali 分析在外部进程执行，耗时可控  
- **UX**：最直观的 Shader 复杂度排序与跳转  
- **Maintenance**：需跟踪 malioc 版本变动

---

## Risks / Blockers

1. malioc 版本输出格式变化  
2. Shader hash/entry 匹配失败导致 N/A

---

## Task Checklist (2-5 分钟粒度, TDD)

- [ ] 新增失败单测：Shader 模型排序（有效值置顶）  
- [ ] 运行 unittest，预期 FAIL  
- [ ] 实现/修复 Mali 匹配、byte size、UI 列  
- [ ] 再跑 unittest，预期 PASS  
- [ ] 手工验收：Run Mali Analysis  
- [ ] 提交（Conventional Commits）

---

## Verification / Acceptance (Definition of Done)

- Mali status 显示匹配统计  
- Shader 表格填充数值并可排序  
- Jump to Shader 正常  
- Build + unittest 通过

---

## /do Execution Log

> 待执行（当前多数项已完成，待手工验收确认）

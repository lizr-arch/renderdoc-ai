# Plan: Shader Risk Dimension (Mali Offline) + Risk Dimensions Doc
> Date: 2026-02-26 15:45:00
> Agent: Agent01
> Stage: /plan
> Context: Native Qt Analyzer Report (RenderDoc)

## Scope / Assumptions
- 目标：先补齐“风险维度文档”，再在原生 Analyzer Report 中落地 **Shader 维度**（Mali Offline 复杂度）。
- Shader 维度先聚焦 **Vulkan SPIR-V**（Mali Offline 可用）；非 Vulkan 只展示基础信息并标注不支持。
- Mali 分析通过现有脚本 `scripts/rdc_analyzer/analyze_rdc.py --json` 产出 JSON，Qt 侧解析并映射到 Shader 行。
- 只改动本任务相关文件；不碰 `renderdoc/3rdparty/`、`build*/`。
- MCP 不可用 → 结论基于本地 `rg`/文件阅读（需在文档注明）。

## Build / Test / Lint Quick Guide (记录，不执行)
- Build (MSBuild, Windows):
  - WSL 路径：`"/mnt/e/Program Files/Microsoft Visual Studio/2022/Community/MSBuild/Current/Bin/MSBuild.exe" renderdoc.sln /p:Configuration=Development /p:Platform=x64 /m`
  - PowerShell 路径：`"E:\Program Files\Microsoft Visual Studio\2022\Community\MSBuild\Current\Bin\MSBuild.exe" renderdoc.sln /p:Configuration=Development /p:Platform=x64 /m`
  - Expected: `Build succeeded.`
- Unit tests:
  - `D:\Code\git\renderdoc\x64\Development\qrenderdoc.exe --unittest`
  - Expected: `All tests passed`

## File List (line refs for planned edits)
- `qrenderdoc/Code/Analyzer/AnalyzerTypes.h:80` (extend `AnalyzerShaderRow` with Mali metrics/hash)
- `qrenderdoc/Code/Analyzer/FrameAnalyzer.cpp:201` (shader usage population; optional hash computation helper)
- `qrenderdoc/Code/Analyzer/AnalyzerContract.cpp:111` (export Mali metrics to JSON)
- `qrenderdoc/Windows/AnalyzerModels.h:129` (add Shader columns for Mali metrics)
- `qrenderdoc/Windows/AnalyzerModels.cpp:472` (headers/data/sort for Mali columns)
- `qrenderdoc/Windows/AnalyzerReportViewer.h:44` (UI members + Mali analysis entrypoints)
- `qrenderdoc/Windows/AnalyzerReportViewer.cpp:295` (run Mali analysis, parse JSON, update table)
- `qrenderdoc/Windows/AnalyzerReportViewer.ui:155` (GPU selector + “Run Mali” button + status)
- `docs/analysis/codex_rdc_analyzer/report_risk_dimensions_v1.md` (new doc)
- `docs/analysis/codex_rdc_analyzer/DOC_INDEX.md` (add doc entry)

## Pseudo-code (核心逻辑示例)
```cpp
// AnalyzerTypes.h
struct AnalyzerShaderRow
{
  ResourceId id;
  rdcstr name;
  rdcstr stage;
  uint32_t useCount = 0;
  uint32_t firstEID = 0;
  uint32_t lastEID = 0;
  rdcstr maliHash;        // sha256(spirv)[:16], Vulkan-only
  rdcstr maliGpu;
  bool maliValid = false;
  float maliCycles = 0.0f;
  uint32_t maliWorkRegs = 0;
  uint32_t maliSpillCount = 0;
  float maliCost = 0.0f;  // cycles + reg penalty + spill penalty
  rdcstr maliError;
};

// AnalyzerReportViewer.cpp
static rdcstr ComputeSpirvHash(const bytebuf &bytes)
{
  QByteArray data((const char *)bytes.data(), bytes.count());
  QByteArray digest = QCryptographicHash::hash(data, QCryptographicHash::Sha256);
  return ToStr(QString::fromLatin1(digest.toHex().left(16)));
}

void AnalyzerReportViewer::RunMaliAnalysis()
{
  // 1) QProcess: py -3 scripts/rdc_analyzer/analyze_rdc.py <rdc> --core <gpu> --json <tmp>
  // 2) Parse JSON via JSONToVariant -> results[0]["shaders"] list
  // 3) Build map: key = hash + "|" + stage
  // 4) For each AnalyzerShaderRow:
  //    - compute maliHash from SPIR-V (ShaderReflection.rawBytes, encoding == SPIRV)
  //    - if match: fill mali fields + maliCost
  // 5) Refresh shader model + default sort by maliCost desc when available
}
```

## Impact Analysis
- **UI**: Shaders tab新增 GPU 选择与 Mali 运行按钮；表格新增 Mali 列（可排序）。
- **Data**: Snapshot 扩展 Mali 指标字段；导出 JSON 增加 Mali 字段（兼容旧消费者）。
- **Performance**: Mali 分析为显式触发（按钮/可选自动）；避免刷新时强制运行。
- **Risk**: 依赖 `py -3` 与 `malioc`；缺失时需提示并降级为 N/A。

## Task Checklist (2–5 min granularity)
- [x] 创建风险维度文档 `report_risk_dimensions_v1.md`（含：风险维度→证据→排序→跳转→置信度）
- [x] 更新 `DOC_INDEX.md` 收录新文档
- [x] 扩展 `AnalyzerShaderRow`（Mali 字段 + hash）
- [x] `AnalyzerContract` 导出 Mali 字段到 analysis.json
- [x] Shader model 增加 Mali 列 + 排序逻辑 + N/A 展示
- [x] Shaders Tab UI：GPU 选择 + “Run Mali” 按钮 + 状态文本
- [x] 实现 Mali 分析流程（QProcess 调用 + JSON 解析 + hash 映射）
- [x] 增加 unit test：Mali Cost 列排序

## Risks / Blockers
- `malioc` 未安装或路径不可用 → 需要显式提示与降级。
- `py -3` 不可用 → Mali 分析入口失效（仅展示基础列）。
- Vulkan 之外的 API 无 SPIR-V → 无法计算 hash/映射。
- LNK1168：`qrenderdoc.exe` 被占用，无法完成本轮 MSBuild 与 unittest 验证。

## Decisions
- Mali 分析来源采用 `scripts/rdc_analyzer/analyze_rdc.py --json`（复用现有链路）。
- Shader 复杂度排序优先使用 `longest_path` cycles + reg/spill 惩罚（对齐 `scripts/rdc_analyzer/mali_analyzer.py`）。

## Verification / Acceptance (DoD)
- Shaders 表新增 Mali 列，数据可排序（升/降序）。
- 选择 Mali GPU 后可运行分析并更新表格。
- Mali 不可用时明确提示且不阻塞报告刷新。
- `analysis.json` 导出包含 Mali 字段（如有）。
- `qrenderdoc.exe --unittest` 通过（含新增 test）。

## Next Steps
- 等用户批准后进入 /do 实现与验证。

# Native Qt Perfect Report Rebuild Plan (No WebUI, Full qrenderdoc C++)

**Version:** 2026-02-25  
**Owner:** Agent01  
**Last Updated:** 2026-02-25 17:41:02  
**Plan File:** `plans/2026-02-25-174102-Agent01-NativeQt-PerfectReport.md`

## Goal

在 RenderDoc GUI 内实现“完全原生 Qt 报告系统”，替代当前 WebUI 报告承载路径：

- 报告内容 100% 由 `qrenderdoc` C++ 窗口渲染（不依赖 `QWebEngineView`/外部浏览器）
- 保持 `analysis.json` 作为数据契约 SSOT（可导出、可追溯）
- 保留并增强“问题 -> 事件/资源/Shader -> GUI 定位”证据链
- 单帧分析报告在 GUI 内达到“可审查、可定位、可导出、可复核”完整闭环

## Architecture (Locked)

### A. Data Plane (C++)
- `FrameAnalyzer`: 从 `ICaptureContext + IReplayController` 采集帧事实数据
- `IssueEngine`: 规则执行与问题归因（severity/confidence/evidence）
- `AnalyzerSnapshot`: 统一内存数据模型（支持 GUI + 导出）

### B. Presentation Plane (Qt Widgets)
- `AnalyzerReportViewer`（新窗口）
- `QAbstractItemModel` + `QSortFilterProxyModel` 驱动 Issues/Events/Resources/Shaders
- 原生 Tabs + Splitter + Details Panel，支持大数据量过滤/排序/跳转

### C. Integration Plane
- `CaptureContext` 新增 `Get/Has/ShowAnalyzerReportViewer`
- `MainWindow` 新增菜单动作 `Analyzer Report`
- 事件联动使用 `CaptureContext::SetEventID()`、`ViewShader()`、`GetTextureViewer()->ViewTexture()`

### D. Export Plane
- 从 `AnalyzerSnapshot` 导出：`analysis.json`（SSOT）、`issues_export.csv`、`issues_export.md`
- 导出和 GUI 展示共享同一套 contract，杜绝双口径

---

## Scope / Assumptions

### Scope (In)
- 全原生 Qt 报告页（Overview / Issues / Events / Resources / Shaders / Performance / Pipeline / Uniforms）
- 全原生证据链跳转
- 数据提取、规则引擎、导出链路 C++ 化并与 GUI 集成
- 旧 WebUI 在 GUI 路径下退役（保留离线脚本工具链）

### Scope (Out)
- 本计划不包含“新外部前端框架”
- 本计划不包含“引入新的第三方 UI 库（如 QtCharts 之外新依赖）”
- 本计划不包含“部署/发布流程”

### Assumptions
- `analysis.json` 继续为 SSOT（对齐 `analysis_report_schema_v1.md`）
- 可接受修改 `QRDInterface` 并触发 SWIG 绑定更新
- 当前会话未发现可用 `renderdoc_context MCP` 资源（**假设（待验证）**：本次基于本地源码与文档索引完成规划）

---

## Build / Test / Lint Quick Guide (记录，不在 /plan 执行)

### Build (需用户授权)
1. `cmake -S . -B build -DCMAKE_BUILD_TYPE=Debug`  
   预期: `Configuring done` + `Generating done`
2. `cmake --build build --target qrenderdoc -j`  
   预期: `build-qrenderdoc` 成功，产物包含 `qrenderdoc(.exe)`
3. `msbuild renderdoc.sln /p:Configuration=Development /p:Platform=x64 /m`  
   预期: `Build succeeded`

### Unit / Regression (允许执行)
4. `build/bin/qrenderdoc --unittest "[analyzer]"`  
   预期: 新增 Analyzer 测试全部 PASS
5. `build/bin/qrenderdoc --unittest "[helpers],[analyzer]"`  
   预期: 既有 helpers + 新增 analyzer 全绿
6. `py -3 -m pytest scripts/rdc_analyzer/tests/test_report_schemas.py -v --tb=short`  
   预期: PASS（契约兼容未回归）
7. `py -3 -m pytest scripts/rdc_analyzer/tests/test_report_issue_export.py -v --tb=short`  
   预期: PASS（导出口径兼容）

### Manual Acceptance
8. 打开任一 capture -> `Window -> Analyzer Report`  
   预期: 原生报告窗口出现，非 WebUI 页面
9. 在 Issues 页点击跳转  
   预期: Event/Texture/Shader 在 GUI 内正确定位
10. 点击导出
   预期: 输出 `analysis.json` + `issues_export.csv` + `issues_export.md`

---

## File List (精确到行号范围)

### Existing files to modify
1. `qrenderdoc/Code/Interface/QRDInterface.h`
- `1131-1210`: 新增 `IAnalyzerReportViewer` 接口定义（参考 `IStatisticsViewer`）
- `2540-2628`: 新增 `GetAnalyzerReportViewer()`
- `2706-2773`: 新增 `HasAnalyzerReportViewer()` / `ShowAnalyzerReportViewer()`

2. `qrenderdoc/Code/CaptureContext.h`
- `40-57`: 新增前置声明 `AnalyzerReportViewer`
- `213-260`: 新增 Get/Has/Show 接口实现声明
- `438-455`: 新增 `AnalyzerReportViewer *m_AnalyzerReportViewer = NULL;`

3. `qrenderdoc/Code/CaptureContext.cpp`
- `42-64`: 新增 include `Windows/AnalyzerReportViewer.h`
- `2375-2433`: 新增 `GetAnalyzerReportViewer()` 创建与 dock 初始化
- `2435-2508`: 新增 `ShowAnalyzerReportViewer()`
- `2694-2753`: `CreateBuiltinWindow()` 增加 `"analyzerReportViewer"`
- `2756-2788`: `BuiltinWindowClosed()` 增加窗口回收

4. `qrenderdoc/Windows/MainWindow.ui`
- `156-170`: Window 菜单挂载 `action_Analyzer_Report`
- `416-445`: 新增 action 定义（文本、shortcut）

5. `qrenderdoc/Windows/MainWindow.h`
- `130-145`: 新增 `showAnalyzerReportViewer()`
- `165-190`: 新增 slot `on_action_Analyzer_Report_triggered()`

6. `qrenderdoc/Windows/MainWindow.cpp`
- `2948-2966` 附近: 新增 `on_action_Analyzer_Report_triggered()`（窗口拉起/聚焦）

7. `qrenderdoc/qrenderdoc.pro`
- `188-257`: 注册新增 `Windows/AnalyzerReportViewer.cpp` 与 `Code/Analyzer/*.cpp`
- `277-346`: 注册新增 headers
- `347-393`: 注册新增 `Windows/AnalyzerReportViewer.ui`

8. `scripts/rdc_analyzer/ui_extension/analyzer_extension.py`
- `724-752`: GUI 打开逻辑标注 legacy（不再作为主入口）
- `879-881`: 菜单文案改为 legacy（避免与原生入口冲突）

9. `scripts/rdc_analyzer/docs/WEBUI_AND_UI_EXTENSION.md`
- `7-20`: 标记 WebUI 在 GUI 场景为 legacy
- `141-147`: 更新已知限制与迁移说明

10. `docs/analysis/codex_rdc_analyzer/report_ui_optimization_v1.md`
- `14-41`: 增补“原生 Qt 版页面映射与交互规范”

### New files to create
11. `qrenderdoc/Code/Analyzer/AnalyzerTypes.h`
12. `qrenderdoc/Code/Analyzer/AnalyzerContract.h`
13. `qrenderdoc/Code/Analyzer/AnalyzerContract.cpp`
14. `qrenderdoc/Code/Analyzer/FrameAnalyzer.h`
15. `qrenderdoc/Code/Analyzer/FrameAnalyzer.cpp`
16. `qrenderdoc/Code/Analyzer/IssueEngine.h`
17. `qrenderdoc/Code/Analyzer/IssueEngine.cpp`
18. `qrenderdoc/Code/Analyzer/AnalyzerExporter.h`
19. `qrenderdoc/Code/Analyzer/AnalyzerExporter.cpp`
20. `qrenderdoc/Windows/AnalyzerModels.h`
21. `qrenderdoc/Windows/AnalyzerModels.cpp`
22. `qrenderdoc/Windows/AnalyzerReportViewer.h`
23. `qrenderdoc/Windows/AnalyzerReportViewer.cpp`
24. `qrenderdoc/Windows/AnalyzerReportViewer.ui`

---

## Design / Pseudocode (完整实现草案)

### 1) Analyzer Contract (SSOT in-memory + export)

```cpp
// qrenderdoc/Code/Analyzer/AnalyzerTypes.h
#pragma once

#include "api/replay/rdcarray.h"
#include "api/replay/rdcstr.h"
#include "api/replay/replay_enums.h"
#include "api/replay/basic_types.h"

struct AnalyzerEvidence
{
  rdcstr metric;
  double value = 0.0;
  rdcstr unit;
  rdcstr detail;
};

struct AnalyzerIssue
{
  rdcstr code;
  rdcstr severity;          // critical/warning/info
  rdcstr category;          // texture/shader/pass/state/bandwidth
  rdcstr message;
  rdcarray<uint32_t> eventIds;
  rdcarray<ResourceId> resourceIds;
  double impactScore = 0.0;
  rdcstr confidence;        // high/medium/low
  rdcarray<AnalyzerEvidence> evidence;
  rdcstr recommendation;
};

struct AnalyzerEventRow
{
  uint32_t eid = 0;
  rdcstr name;
  rdcstr type;              // draw/dispatch/clear/marker
  uint32_t drawIndex = 0;
  uint32_t passIndex = 0;
  ResourceId vs;
  ResourceId ps;
  rdcarray<ResourceId> rts;
  ResourceId ds;
};

struct AnalyzerSummary
{
  rdcstr api;
  uint32_t frameNumber = 0;
  uint32_t drawCount = 0;
  uint32_t dispatchCount = 0;
  uint32_t textureCount = 0;
  uint32_t bufferCount = 0;
  uint32_t passCount = 0;
  uint64_t textureBytes = 0;
  uint64_t bufferBytes = 0;
};

struct AnalyzerSnapshot
{
  rdcstr schemaVersion = "analysis.native.qt.v1";
  AnalyzerSummary summary;
  rdcarray<AnalyzerEventRow> events;
  rdcarray<AnalyzerIssue> issues;
  // textures/shaders/passes/pipeline/uniforms 省略声明
};
```

### 2) Frame extraction with replay thread safety

```cpp
// qrenderdoc/Code/Analyzer/FrameAnalyzer.cpp
AnalyzerSnapshot FrameAnalyzer::Build(ICaptureContext &ctx)
{
  AnalyzerSnapshot out;

  out.summary.api = ToStr(ctx.APIProps().pipelineType);
  out.summary.frameNumber = ctx.FrameInfo().frameNumber;

  const rdcarray<ActionDescription> &roots = ctx.CurRootActions();
  FlattenActions(roots, out.events);

  const rdcarray<TextureDescription> &textures = ctx.GetTextures();
  const rdcarray<BufferDescription> &buffers = ctx.GetBuffers();
  out.summary.textureCount = textures.count();
  out.summary.bufferCount = buffers.count();

  for(const TextureDescription &t : textures)
    out.summary.textureBytes += t.byteSize;

  for(const BufferDescription &b : buffers)
    out.summary.bufferBytes += b.length;

  // Replay thread: collect per-event pipeline snapshots and shader/resource bindings.
  ctx.Replay().BlockInvoke([&](IReplayController *r) {
    for(size_t i = 0; i < out.events.size(); i++)
    {
      AnalyzerEventRow &evt = out.events[i];
      if(evt.eid == 0)
        continue;

      r->SetFrameEvent(evt.eid, false);
      const PipeState &pipe = r->GetPipelineState();

      evt.vs = pipe.GetShaderResourceId(ShaderStage::Vertex);
      evt.ps = pipe.GetShaderResourceId(ShaderStage::Pixel);
      evt.rts = ExtractColorTargets(pipe);
      evt.ds = ExtractDepthTarget(pipe);
    }
  });

  return out;
}
```

### 3) Rule engine (deterministic, evidence-first)

```cpp
// qrenderdoc/Code/Analyzer/IssueEngine.cpp
rdcarray<AnalyzerIssue> IssueEngine::Evaluate(const AnalyzerSnapshot &snap)
{
  rdcarray<AnalyzerIssue> out;

  EvaluateDrawCallPressure(snap, out);      // PERF_DC_001
  EvaluateRTSwitchDensity(snap, out);       // PERF_RT_001
  EvaluateOversizedTextures(snap, out);     // TEX_SIZE_001
  EvaluateTextureFormatRisk(snap, out);     // TEX_FMT_001
  EvaluateShaderHotspots(snap, out);        // SHDR_COST_001
  EvaluateStateThrashing(snap, out);        // STATE_SWITCH_001

  std::sort(out.begin(), out.end(), [](const AnalyzerIssue &a, const AnalyzerIssue &b) {
    if(a.severity != b.severity)
      return SeverityRank(a.severity) < SeverityRank(b.severity);
    return a.impactScore > b.impactScore;
  });

  return out;
}
```

### 4) Native Qt models for large data

```cpp
// qrenderdoc/Windows/AnalyzerModels.cpp
int AnalyzerIssueModel::rowCount(const QModelIndex &) const
{
  return m_Rows.count();
}

QVariant AnalyzerIssueModel::data(const QModelIndex &idx, int role) const
{
  if(!idx.isValid() || idx.row() >= m_Rows.count())
    return QVariant();

  const AnalyzerIssue &issue = m_Rows[idx.row()];

  if(role == Qt::DisplayRole)
  {
    switch(idx.column())
    {
      case ColSeverity: return ToQStr(issue.severity);
      case ColCode: return ToQStr(issue.code);
      case ColMessage: return ToQStr(issue.message);
      case ColImpact: return issue.impactScore;
      case ColConfidence: return ToQStr(issue.confidence);
      default: break;
    }
  }

  if(role == Qt::UserRole)
    return QVariant::fromValue((uint32_t)idx.row());

  return QVariant();
}
```

### 5) Viewer orchestration + jump

```cpp
// qrenderdoc/Windows/AnalyzerReportViewer.cpp
void AnalyzerReportViewer::OnCaptureLoaded()
{
  StartBuild();
}

void AnalyzerReportViewer::StartBuild()
{
  ShowBusy(true, tr("Building native analyzer report..."));

  m_Ctx.Replay().AsyncInvoke("analyzer-build", [this](IReplayController *) {
    AnalyzerSnapshot snap = m_FrameAnalyzer.Build(m_Ctx);
    snap.issues = m_IssueEngine.Evaluate(snap);

    GUIInvoke::call(this, [this, snap]() {
      m_Snapshot = snap;
      BindAllModels();
      RenderOverviewCards();
      ShowBusy(false, QString());
    });
  });
}

void AnalyzerReportViewer::JumpToIssueRow(int row)
{
  if(row < 0 || row >= m_Snapshot.issues.count())
    return;

  const AnalyzerIssue &issue = m_Snapshot.issues[row];
  if(!issue.eventIds.empty())
  {
    uint32_t eid = issue.eventIds[0];
    m_Ctx.SetEventID({}, eid, eid, true);
    return;
  }

  if(!issue.resourceIds.empty())
  {
    ResourceId res = issue.resourceIds[0];
    if(m_Ctx.GetTexture(res))
    {
      m_Ctx.ShowTextureViewer();
      m_Ctx.GetTextureViewer()->ViewTexture(res, CompType::Typeless, true);
      return;
    }
  }
}
```

### 6) Export from same snapshot

```cpp
// qrenderdoc/Code/Analyzer/AnalyzerExporter.cpp
bool AnalyzerExporter::WriteAll(const AnalyzerSnapshot &snap, const rdcstr &dir)
{
  if(!WriteAnalysisJSON(snap, dir + "/analysis.json"))
    return false;

  if(!WriteIssuesCSV(snap.issues, dir + "/issues_export.csv"))
    return false;

  if(!WriteIssuesMarkdown(snap.issues, dir + "/issues_export.md"))
    return false;

  return true;
}
```

---

## Impact Analysis

### API / ABI impact
- `QRDInterface` 新增 Viewer 接口和 `ICaptureContext` 方法，SWIG 绑定会变化。
- Python 脚本若使用 `dir(CaptureContext)` 将看到新增接口（向后兼容，不破坏旧调用）。

### Performance impact
- 全量事件快照采集会增加首开耗时。
- 通过 `Replay().AsyncInvoke("analyzer-build", ...)` + UI 增量刷新控制阻塞。
- 模型层使用 `QAbstractItemModel`，避免 `QTableWidget` 大数据性能问题。

### UX impact
- GUI 内统一体验，不再依赖 PySide2/QtWebEngine 和外部浏览器。
- 跳转链路在一个进程内完成，稳定性和可调试性更高。

### Maintenance impact
- 报告核心转入 qrenderdoc C++，与渲染回放主链同版本演进。
- WebUI 保留为离线分享/历史兼容，不再承载 GUI 主路径。

---

## Decisions

1. 路线锁定为 **C++ 全原生 Qt**，不再以 WebUI 作为 GUI 宿主。
2. `analysis.json` 继续作为 SSOT，但生成者从 Python 主导迁移为 C++ 主导（可双写过渡）。
3. GUI 主入口从 `Window` 菜单提供内建 `Analyzer Report`。
4. Python 扩展中的 `Open WebUI` 标记为 legacy，避免用户路径混淆。

---

## Risks / Blockers

1. **长帧首开耗时高**：全事件 `SetFrameEvent` 采样可能慢。  
   Mitigation: 首屏先展示 summary + issues，重数据页后台增量加载。
2. **规则迁移偏差**：Python 与 C++ 规则输出可能不一致。  
   Mitigation: 建立 parity 对比测试（同 capture，对比 code/severity/eid）。
3. **接口变更影响扩展**：新增接口引起 SWIG 变更。  
   Mitigation: 保持新增 API 只增不改，不删除旧接口。
4. **构建链路复杂**：`qrenderdoc.pro` 与 CMake 双维护。  
   Mitigation: 每个新文件同步更新 `qrenderdoc.pro`，并保留 CMake 路径验证。
5. **本轮尚未执行构建/手工 UI 验证**：当前已完成接线与窗口骨架，但缺少编译与点击路径确认。  
   Mitigation: 下一批先执行授权后的构建 + 最小手工验收，再继续补模型与规则引擎。

---

## Task Checklist (2-5 分钟粒度, TDD 强制)

### Task 1: Analyzer Contract + serialization
- [x] `[3m]` 新增 `AnalyzerTypes.h`，定义 Summary/Event/Issue/Snapshot 结构体
- [ ] `[3m]` 新增失败单测 `TEST_CASE("Analyzer contract serializes required keys", "[analyzer]")`
- [ ] `[2m]` 执行 `qrenderdoc --unittest "[analyzer]"`，预期 FAIL（缺实现）
- [x] `[4m]` 实现 `AnalyzerContract.cpp` 的 JSON 序列化函数
- [ ] `[2m]` 再跑测试，预期 PASS
- [ ] `[2m]` 提交  
  `git commit -m "feat(qrenderdoc-analyzer): add native analyzer contract and JSON serialization"`

### Task 2: Frame facts extraction base
- [ ] `[3m]` 新增失败单测：`FlattenActions` 结果包含 draw/dispatch 基本字段
- [ ] `[2m]` 运行单测，预期 FAIL
- [x] `[5m]` 实现 `FrameAnalyzer::Build()` 的 summary/events/texture/buffer 基础采集
- [ ] `[3m]` 运行单测，预期 PASS
- [ ] `[2m]` 提交  
  `git commit -m "feat(qrenderdoc-analyzer): implement base frame data extraction"`

### Task 3: Per-event pipeline snapshot extraction
- [ ] `[3m]` 新增失败单测：事件快照应包含 shader/resource binding
- [ ] `[2m]` 运行单测，预期 FAIL
- [ ] `[5m]` 在 `Replay().BlockInvoke` 中实现按 EID 的 `SetFrameEvent` 扫描并提取 bindings
- [ ] `[3m]` 运行单测，预期 PASS
- [ ] `[2m]` 提交  
  `git commit -m "feat(qrenderdoc-analyzer): add per-event pipeline snapshots"`

### Task 4: IssueEngine rule set migration
- [ ] `[3m]` 新增失败单测：`PERF_DC_001` / `TEX_SIZE_001` / `STATE_SWITCH_001` 触发与排序
- [ ] `[2m]` 运行单测，预期 FAIL
- [x] `[5m]` 实现 `IssueEngine` 规则与 severity+impact 排序（当前为首版 3 条规则）
- [ ] `[3m]` 运行单测，预期 PASS
- [ ] `[2m]` 提交  
  `git commit -m "feat(qrenderdoc-analyzer): implement native issue engine and rule ordering"`

### Task 5: Qt models for Issues/Events/Resources/Shaders
- [ ] `[3m]` 新增失败单测：`AnalyzerIssueModel` 行列与排序角色输出正确
- [ ] `[2m]` 运行单测，预期 FAIL
- [x] `[5m]` 实现 `AnalyzerModels.{h,cpp}`，完成四类模型 + proxy model（已覆盖 Issues/Events，Resources/Shaders 待补）
- [ ] `[3m]` 运行单测，预期 PASS
- [ ] `[2m]` 提交  
  `git commit -m "feat(qrenderdoc-analyzer): add native Qt table models for analyzer pages"`

### Task 6: AnalyzerReportViewer shell UI
- [x] `[3m]` 新增 `AnalyzerReportViewer.ui`（tabs + splitters + toolbars）
- [ ] `[2m]` 新增失败单测：viewer 初始化后包含核心页签
- [x] `[5m]` 实现 `AnalyzerReportViewer` 构造、模型绑定、busy/progress 状态（已完成窗口骨架 + summary/issues 基础绑定，busy/progress 仍待补全）
- [ ] `[3m]` 运行单测，预期 PASS
- [ ] `[2m]` 提交  
  `git commit -m "feat(qrenderdoc-analyzer): create native analyzer report viewer window"`

### Task 7: Jump chain (Issue -> Event/Texture/Shader)
- [ ] `[3m]` 新增失败单测：双击 issue 时触发 `SetEventID` 或资源查看器行为
- [ ] `[2m]` 运行单测，预期 FAIL
- [x] `[5m]` 实现 issue/event/resource/shader 跳转 slot（首版：issue->EID->EventBrowser）
- [ ] `[3m]` 运行单测，预期 PASS
- [ ] `[2m]` 提交  
  `git commit -m "feat(qrenderdoc-analyzer): wire native issue-to-gui jump chain"`

### Task 8: Export parity from native snapshot
- [ ] `[3m]` 新增失败单测：导出 `analysis.json` 与 `issues_export.csv/md` 文件存在且字段完整
- [ ] `[2m]` 运行单测，预期 FAIL
- [x] `[5m]` 实现 `AnalyzerExporter` 三类导出
- [ ] `[3m]` 运行单测，预期 PASS
- [ ] `[2m]` 提交  
  `git commit -m "feat(qrenderdoc-analyzer): export analysis and issue artifacts from native snapshot"`

### Task 9: CaptureContext + MainWindow integration
- [x] `[3m]` 在 `QRDInterface.h` 增加 `IAnalyzerReportViewer` 与 Get/Has/Show 方法
- [x] `[3m]` 在 `CaptureContext` 新增 viewer 生命周期管理
- [x] `[3m]` 在 `MainWindow.ui/.h/.cpp` 新增 `Analyzer Report` 菜单动作
- [ ] `[2m]` 手工验证：菜单拉起窗口成功
- [ ] `[2m]` 提交  
  `git commit -m "feat(qrenderdoc): integrate native analyzer report into main window and capture context"`

### Task 10: Legacy WebUI downgrade in GUI flow
- [x] `[3m]` 修改 Python 扩展菜单文案为 legacy
- [x] `[3m]` 文档更新：GUI 主路径为 native analyzer
- [ ] `[2m]` 验证：GUI 主入口不再依赖 WebUI
- [ ] `[2m]` 提交  
  `git commit -m "docs(rdc-analyzer): mark webui gui path as legacy after native qt integration"`

### Task 11: Parity validation with existing schema/tests
- [ ] `[3m]` 新增 parity 测试：native export 与现有 schema 关键键一致
- [ ] `[3m]` 运行 Python schema/export tests，预期 PASS
- [ ] `[3m]` 记录差异字段（若有）并补齐 mapping
- [ ] `[2m]` 提交  
  `git commit -m "test(qrenderdoc-analyzer): add native-vs-schema parity checks"`

### Task 12: Final gate
- [ ] `[3m]` 运行 `qrenderdoc --unittest "[analyzer]"` + `"[helpers],[analyzer]"`
- [ ] `[3m]` 运行 `pytest` 的报告契约用例
- [ ] `[3m]` 手工验收 10 条（打开窗口/筛选/排序/跳转/导出）
- [ ] `[2m]` 更新计划复盘与风险残留
- [ ] `[2m]` 提交  
  `git commit -m "chore(qrenderdoc-analyzer): finalize native analyzer report gate"`

---

## Verification / Acceptance (Definition of Done)

1. GUI 内可直接打开 `Analyzer Report` 原生窗口，无 WebUI 宿主。
2. 页面具备专业分析最小闭环：Overview/Issues/Events/Resources/Shaders/Performance。
3. 问题条目支持一键跳转到 EID/Texture/Shader。
4. 导出产物可用：`analysis.json`、`issues_export.csv`、`issues_export.md`。
5. 新增 analyzer 单元测试通过，既有 helpers/report schema 不回归。
6. 文档明确“native 主路径 + webui legacy 路径”。

---

## Ready Signal

该计划为“高成本但最完美”路线，已锁定全原生 C++/Qt 实施。  
收到 `/do` 后按上述 Task 1 -> Task 12 顺序执行，并在同一计划文件中持续勾选与记录偏差。

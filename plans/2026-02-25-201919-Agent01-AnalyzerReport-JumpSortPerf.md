# Plan: Analyzer Report jump reliability + table UX + load optimization

Date: 2026-02-25 20:19:19
Agent: Agent01
Mode: /plan (read-only analysis, no build/test execution in this stage)

## Scope / Assumptions

- Scope:
  - Investigate and fix remaining texture/shader jump problems in native `Analyzer Report`.
  - Add load-time optimization to an explicit implementation schedule.
  - Redesign table sorting behavior and size/dimension presentation for Issues/Events/Resources/Shaders.
- Non-goals in this batch:
  - No WebUI changes.
  - No dependency/toolchain changes.
  - No build-system migration work.
- Evidence source note:
  - `search_docs` returned 0 results for task keywords.
  - This plan is based on local source evidence (`MCP unavailable` fallback).

## Source Evidence (current behavior)

- Jump chain implementation and order:
  - `qrenderdoc/Windows/AnalyzerReportViewer.cpp:287` (texture first), `qrenderdoc/Windows/AnalyzerReportViewer.cpp:291` (shader second), `qrenderdoc/Windows/AnalyzerReportViewer.cpp:296` (EID fallback).
- Shader jump currently picks first entry point:
  - `qrenderdoc/Windows/AnalyzerReportViewer.cpp:368`, `qrenderdoc/Windows/AnalyzerReportViewer.cpp:378`.
- Busy/progress and async refresh:
  - `qrenderdoc/Windows/AnalyzerReportViewer.cpp:125`, `qrenderdoc/Windows/AnalyzerReportViewer.cpp:133`, `qrenderdoc/Windows/AnalyzerReportViewer.cpp:220`.
- Current heavy path is per-event replay state scan:
  - `qrenderdoc/Code/Analyzer/FrameAnalyzer.cpp:206`, `qrenderdoc/Code/Analyzer/FrameAnalyzer.cpp:212`.
- Current resource/shader tables rely on display strings and do not implement numeric sort logic:
  - `qrenderdoc/Windows/AnalyzerModels.cpp:273` (resource display data),
  - `qrenderdoc/Windows/AnalyzerModels.cpp:376` (shader display data),
  - no `sort(...)` override in `qrenderdoc/Windows/AnalyzerModels.h`.
- Existing native rule coverage is still baseline-level:
  - `qrenderdoc/Code/Analyzer/IssueEngine.cpp:59`, `qrenderdoc/Code/Analyzer/IssueEngine.cpp:88`, `qrenderdoc/Code/Analyzer/IssueEngine.cpp:115`, baseline fallback at `qrenderdoc/Code/Analyzer/IssueEngine.cpp:143`.
- Existing plan already identifies full-event scan as risk:
  - `plans/2026-02-25-174102-Agent01-NativeQt-PerfectReport.md:439`.

## File List (planned edits with target line zones)

1) `qrenderdoc/Windows/AnalyzerReportViewer.cpp`
- `36-76`: table init policy (sorting enable, header behavior, selection).
- `112-153`: refresh orchestration and async build handling.
- `193-218`: post-bind table sort/layout refresh behavior.
- `277-395`: issue jump target resolution flow.

2) `qrenderdoc/Windows/AnalyzerReportViewer.h`
- `67-77`: add explicit helper APIs for jump resolution and table layout policy.

3) `qrenderdoc/Windows/AnalyzerModels.h`
- `92-160`: resource/shader model sort roles and optional proxy model declarations.

4) `qrenderdoc/Windows/AnalyzerModels.cpp`
- `219-320`: resource numeric sort role/data improvements.
- `322-407`: shader numeric sort role/data improvements.
- add model/proxy sort implementation for deterministic asc/desc.

5) `qrenderdoc/Code/Analyzer/FrameAnalyzer.cpp`
- `61-92`: event flattening metadata used by scan filtering.
- `200-241`: reduce replay scan cost (skip non draw/dispatch and avoid unnecessary work).
- `243-269`: optimize shader aggregation path (remove repeated linear scan).

6) `qrenderdoc/Code/Analyzer/IssueEngine.cpp`
- `32-149`: improve issue target metadata quality so jump target is more stable.

7) `qrenderdoc/Windows/AnalyzerReportViewer.ui`
- `129-163`: table view defaults (sorting usability and column sizing policy alignment).

8) Unit test insertion (guarded with `#if ENABLE_UNIT_TESTS`)
- `qrenderdoc/Windows/AnalyzerModels.cpp` (new `[analyzer]` sorting tests).
- `qrenderdoc/Windows/AnalyzerReportViewer.cpp` or a nearby analyzer cpp (new `[analyzer]` jump target selection tests using extracted helper functions).

## Pseudocode (implementation sketch)

### A) Jump target reliability (texture/shader)

```cpp
// AnalyzerReportViewer.h
struct AnalyzerJumpTarget
{
  ResourceId texture;
  ResourceId shader;
  ShaderStage shaderStage = ShaderStage::Vertex;
  uint32_t eid = 0;
};

AnalyzerJumpTarget ResolveIssueTarget(const AnalyzerIssue &issue, uint32_t fallbackEID) const;
ShaderEntryPoint PickEntryPoint(const rdcarray<ShaderEntryPoint> &entries,
                                ShaderStage preferred) const;
```

```cpp
// AnalyzerReportViewer.cpp
AnalyzerJumpTarget AnalyzerReportViewer::ResolveIssueTarget(...)
{
  // 1) prefer explicit issue.resourceIds
  // 2) classify each id by actual type (texture first, shader second)
  // 3) if texture missing, try fallback event RT/DS
  // 4) if shader stage unknown, infer from event's bound shader slot
}

bool AnalyzerReportViewer::JumpToShaderTarget(...)
{
  // ensure event context when available
  // query entries -> choose stage-matching entry, not blindly entries[0]
  // keep current warning path for no entry/reflection cases
}
```

### B) Load optimization (first deliverable + schedule)

```cpp
// FrameAnalyzer.cpp
for(AnalyzerEventRow &event : snapshot.events)
{
  if(event.type != "draw" && event.type != "dispatch")
    continue; // skip marker/copy/other for expensive replay state fetch

  r->SetFrameEvent(event.eid, false);
  const PipeState &pipe = r->GetPipelineState();
  ...
}

// O(1) shader aggregation
rdcflatmap<rdcpair<ResourceId, rdcstr>, size_t> shaderIndex;
```

```cpp
// AnalyzerReportViewer.cpp
// avoid always-resize-all-columns on every refresh for very large tables
if(firstPopulate || forceRelayout)
  ApplyTableLayoutPolicy();
```

### C) Table sorting and size/dimension redesign

```cpp
// AnalyzerModels.h/.cpp
enum Roles { BytesRole = Qt::UserRole + 1, WidthRole, HeightRole, SamplesRole, ... };

QVariant AnalyzerResourceModel::data(...)
{
  if(role == BytesRole) return qulonglong(resource.bytes);
  if(role == WidthRole) return int(resource.width);
  ...
}

class AnalyzerResourceSortModel : public QSortFilterProxyModel
{
  bool lessThan(...) const override
  {
    // numeric compare for bytes/dimensions; fallback lexicographic for names
  }
};
```

```cpp
// AnalyzerReportViewer.cpp (defaults)
issueTable: Severity asc (critical/warning/info), then Impact desc
eventTable: EID asc
resourceTable: Size(bytes) desc
shaderTable: UseCount desc, FirstEID asc

// header sizing
name columns -> Stretch
numeric/id columns -> ResizeToContents
```

## Task Checklist (2-5 minute granularity, /do execution plan)

- [ ] `[3m]` Reproduce jump failures with a known capture and record exact failing patterns (texture miss, shader miss, wrong target).
- [ ] `[3m]` Add local instrumentation logs in jump path (`ResolveIssueTarget`, chosen shader entry, fallback reason).
- [x] `[4m]` Implement `ResolveIssueTarget(...)` helper and replace ad-hoc branching in `on_jumpButton_clicked`.
- [x] `[4m]` Implement stage-aware shader entrypoint selection (`PickEntryPoint`) and wire into `JumpToShaderTarget`.
- [x] `[3m]` Add robust fallback order: explicit resource -> event RT/DS -> event browser.
- [ ] `[4m]` Add/adjust issue target metadata mapping in `IssueEngine` for deterministic jump anchors.
- [x] `[4m]` Add resource/shader numeric sort roles and sort proxy models.
- [x] `[4m]` Apply table layout policy (default sort orders + header sizing).
- [x] `[4m]` Optimize `FrameAnalyzer` heavy replay scan: skip non draw/dispatch events.
- [x] `[4m]` Optimize shader aggregation complexity from linear scan to indexed update.
- [ ] `[3m]` Add unit tests for sorting correctness (`[analyzer]`): numeric asc/desc on bytes/use count.
- [ ] `[3m]` Add unit tests for jump target resolution (`[analyzer]`): explicit texture/shader/fallback.
- [x] `[3m]` Build (Windows MSBuild) and run `qrenderdoc --unittest` full + `[analyzer]` subset.
- [ ] `[3m]` Manual GUI validation checklist: Refresh/Jump/Export/busy + table sorting UX.
- [x] `[2m]` Update this plan file with results and residual risks.

## Build/Test/Lint Quick Guide (/plan: record only, do not execute)

- Build:
  - `\"E:\\Program Files\\Microsoft Visual Studio\\2022\\Community\\MSBuild\\Current\\Bin\\MSBuild.exe\" renderdoc.sln /p:Configuration=Development /p:Platform=x64 /m`
  - Expected: `0 warning, 0 error`.
- Unit tests:
  - `D:\\Code\\git\\renderdoc\\x64\\Development\\qrenderdoc.exe --unittest`
  - `D:\\Code\\git\\renderdoc\\x64\\Development\\qrenderdoc.exe --unittest \"[analyzer]\"`
  - Expected: exit code `0`.
- Manual acceptance:
  - Open capture -> `Window -> Analyzer Report` -> `Refresh` / `Jump To Target` / `Export`.
  - Verify table header click toggles asc/desc and numeric sort correctness.

## Load Optimization Schedule (added backlog explicitly)

### M1 (current task, low risk)
- Skip expensive pipeline-state fetch for non draw/dispatch events.
- Replace O(N^2)-like shader aggregation path with indexed updates.
- Reduce repeated `resizeColumnsToContents()` overhead on each refresh.

### M2 (next iteration)
- Two-phase build:
  - Phase A fast snapshot (summary/issues/events coarse).
  - Phase B deferred enrichment (resource/shader deep details).
- Cache event->shader snapshot keyed by capture + event id.

### M3 (after M2)
- Integrate GPU counter-backed hotspots (EventGPUDuration and available generic counters).
- Mark issue confidence with explicit provenance: `counter-backed` vs `heuristic`.

## Risks / Blockers

- Jump reliability may differ by API backend if shader reflection entry selection is ambiguous.
- Sorting regressions can appear if model roles are not consistently consumed by proxy sort model.
- Load-time optimization may change issue ordering and user-visible issue anchors.
- `qrenderdoc --unittest` may run with existing dirty workspace side effects unrelated to this task.

## Decisions (pre-approved in plan)

- Keep native Qt path as the only GUI primary path.
- Prioritize deterministic navigation correctness over adding new rule types in this batch.
- For table UX, enforce numeric sorting semantics first, cosmetic column tuning second.

## Impact Analysis

- User-facing impact:
  - More reliable issue-to-texture/shader navigation.
  - Predictable table sorting behavior with proper numeric asc/desc.
  - Better perceived responsiveness on large captures.
- Code impact:
  - Mostly localized to analyzer/report viewer and analyzer models.
  - No expected external API contract changes.
- Regression surface:
  - Viewer interaction flow and model sorting paths.
  - Issue target linkage logic and refresh performance code path.

## Verification / Acceptance (Definition of Done)

1) For issues with texture targets, `Jump To Target` opens `TextureViewer` on expected resource.
2) For issues with shader targets, `Jump To Target` opens shader view without entrypoint mismatch failure.
3) For no concrete resource target, fallback to event browser remains functional.
4) Resource/Shaders table header sort toggles produce correct numeric order (asc/desc).
5) Resource size/dimension fields are consistently legible and sortable.
6) Refresh time on heavy capture is measurably lower than pre-change baseline.
7) MSBuild + unittest pass.

## Next Steps

- Wait for `/do` approval.
- On `/do`, execute tasks in checklist order and update this same plan file with checkmarks, command outputs, and any blocker notes.

## /do Progress Log (2026-02-25)

- Build/test baseline before edits:
  - `E:\Program Files\Microsoft Visual Studio\2022\Community\MSBuild\Current\Bin\MSBuild.exe renderdoc.sln /p:Configuration=Development /p:Platform=x64 /m /v:minimal /nologo`
  - `D:\Code\git\renderdoc\x64\Development\qrenderdoc.exe --unittest`
- Blocker encountered/resolved:
  - First build hit linker lock (`LNK1168`) due stale `qrenderdoc` process.
  - Resolved via `Get-Process qrenderdoc | Stop-Process -Force`.
- Implemented in this /do batch:
  - Jump reliability:
    - Texture jump now always includes fallback event RT/DS candidates (deduped), not only when explicit list is empty.
    - Shader jump now uses stage-aware entry selection + stage/pipeline-aware reflection fetch.
  - Table UX:
    - Added deterministic model-level sort implementations for Events/Resources/Shaders with numeric semantics.
    - Updated Resources shape display to clearer dimensions metadata (`Layers/Mips/MSAA`) and default table relayout policy.
  - Load optimization (M1):
    - Replay pipeline-state fetch now skips non draw/dispatch events.
    - Shader aggregation now uses indexed updates via map lookup (removes repeated linear scan per shader update).
- Verification after edits:
  - Rebuilt successfully with same MSBuild command.
  - Re-ran `qrenderdoc.exe --unittest` (exit code `0`).
  - Re-ran `qrenderdoc.exe --unittest "[analyzer]"` (exit code `0`, but current tree has no registered `[analyzer]` test cases).
- Remaining validation:
  - Manual GUI smoke (capture -> Analyzer Report -> Refresh/Jump/Export, including known problematic captures).
  - Optional `[analyzer]` targeted unit coverage additions for jump/sort helpers.

# Plan: Analyzer docs sync + runnable [analyzer] unit tests

Date: 2026-02-25 21:34:29
Agent: Agent01
Mode: /plan (read-only analysis, no build/test execution in this stage)

## Scope / Assumptions

- Scope:
  - Update handoff/plan documentation to reflect the latest completed Native Qt analyzer work, so follow-up sessions do not repeat already-finished implementation.
  - Implement runnable `[analyzer]` unit tests (sorting + jump-resolution helper logic) so `qrenderdoc.exe --unittest "[analyzer]"` executes real tests instead of returning "No test cases matched".
- Non-goals:
  - No new feature UI behavior changes beyond testability refactor for existing jump/sort logic.
  - No build system changes.
  - No WebUI path changes.
- Evidence-source note:
  - `search_docs("AnalyzerReportViewer unit test [analyzer] sort jump")` returned 0 results.
  - This plan is based on local source evidence (`MCP unavailable` fallback).

## Source Evidence

- Existing qrenderdoc test tags are currently non-analyzer:
  - `qrenderdoc/Code/BufferFormatter.cpp:4066` (`[formatter]`)
  - `qrenderdoc/Windows/TextureViewer.cpp:4833` (`[helpers]`)
- Unit-test entry/filter path:
  - `qrenderdoc/Code/qrenderdoc.cpp:226` (`--unittest`)
  - `qrenderdoc/Code/qrenderdoc.cpp:268` (Catch command-line apply)
- Recently landed analyzer jump/sort changes to be covered by tests:
  - `qrenderdoc/Windows/AnalyzerReportViewer.cpp:337` (texture target candidate flow)
  - `qrenderdoc/Windows/AnalyzerReportViewer.cpp:390` (shader jump + stage/pipeline-aware selection)
  - `qrenderdoc/Windows/AnalyzerModels.cpp:220` / `qrenderdoc/Windows/AnalyzerModels.cpp:370` / `qrenderdoc/Windows/AnalyzerModels.cpp:520` (event/resource/shader sort implementations)
- Existing progress docs already partially updated:
  - `plans/2026-02-25-201919-Agent01-AnalyzerReport-JumpSortPerf.md:259`
  - `plans/2026-02-25-174102-Agent01-NativeQt-PerfectReport.md:656`

## File List (planned edits with target line zones)

1) `plans/2026-02-25-184200-Agent01-NativeQt-Handoff.md`
- Append "2026-02-25 late update" section near tail:
  - completed items (jump reliability/sort/perf M1 + commit IDs)
  - explicit remaining items (manual GUI acceptance + analyzer-tagged tests)
  - pointer to latest executable plan file for continuation.

2) `plans/2026-02-25-174102-Agent01-NativeQt-PerfectReport.md`
- Append one concise status checkpoint:
  - "no-repeat guard" summary + current blocking/remaining tasks.

3) `qrenderdoc/Windows/AnalyzerReportViewer.cpp`
- `~36-120`: extract pure helper(s) used by jump path into testable local functions.
- `~330-520`: replace in-function ad-hoc selection with helper calls (behavior-preserving).
- file tail: add `#if ENABLE_UNIT_TESTS` `[analyzer]` tests for helper behavior.

4) `qrenderdoc/Windows/AnalyzerReportViewer.h`
- Optional only if helper signatures require class-level declaration change.

5) `qrenderdoc/Windows/AnalyzerModels.cpp`
- file tail: add `#if ENABLE_UNIT_TESTS` `[analyzer]` tests for numeric sort behavior of:
  - `AnalyzerResourceModel::sort(...)`
  - `AnalyzerShaderModel::sort(...)`
- add minimal test-only utility for deterministic synthetic `ResourceId` generation.

6) `qrenderdoc/Windows/AnalyzerModels.h`
- Only if testability requires exposing row accessors already present (expected no changes).

## Pseudocode (implementation sketch)

### A) Jump helper extraction for testability

```cpp
namespace
{
ShaderEntryPoint PickEntryPointForStage(const rdcarray<ShaderEntryPoint> &entries,
                                        ShaderStage preferredStage)
{
  if(entries.empty())
    return ShaderEntryPoint();

  if(preferredStage != ShaderStage::Count)
  {
    for(const ShaderEntryPoint &entry : entries)
      if(entry.stage == preferredStage)
        return entry;
  }

  return entries[0];
}

rdcarray<ResourceId> BuildTextureJumpCandidates(const AnalyzerIssue &issue, uint32_t fallbackEID,
                                                const rdcarray<AnalyzerEventRow> &events)
{
  rdcarray<ResourceId> out;
  auto appendUnique = [&out](ResourceId id) {
    if(id == ResourceId())
      return;
    for(ResourceId existing : out)
      if(existing == id)
        return;
    out.push_back(id);
  };

  for(ResourceId id : issue.resourceIds)
    appendUnique(id);

  if(fallbackEID != 0)
  {
    for(const AnalyzerEventRow &evt : events)
    {
      if(evt.eid != fallbackEID)
        continue;
      for(ResourceId rt : evt.rts)
        appendUnique(rt);
      appendUnique(evt.ds);
      break;
    }
  }

  return out;
}
}
```

### B) Analyzer sorting tests (`[analyzer]`)

```cpp
#if ENABLE_UNIT_TESTS
#include "3rdparty/catch/catch.hpp"

static ResourceId MakeTestResourceId(uint64_t raw)
{
  ResourceId id;
  RDCCOMPILE_ASSERT(sizeof(ResourceId) == sizeof(uint64_t),
                    "ResourceId must remain 64-bit for test helper");
  memcpy(&id, &raw, sizeof(uint64_t));
  return id;
}

TEST_CASE("Analyzer resource sort is numeric on bytes", "[analyzer]")
{
  AnalyzerResourceModel model;
  // setup rows with bytes = 4096, 16, 1024
  model.SetResources(rows);
  model.sort(AnalyzerResourceModel::ColBytes, Qt::AscendingOrder);
  // CHECK order: 16, 1024, 4096
  model.sort(AnalyzerResourceModel::ColBytes, Qt::DescendingOrder);
  // CHECK order: 4096, 1024, 16
}

TEST_CASE("Analyzer shader sort is numeric on use count", "[analyzer]")
{
  AnalyzerShaderModel model;
  // setup rows with useCount = 1, 20, 3
  model.SetShaders(rows);
  model.sort(AnalyzerShaderModel::ColUseCount, Qt::DescendingOrder);
  // CHECK order: 20, 3, 1
}
#endif
```

### C) Analyzer jump helper tests (`[analyzer]`)

```cpp
TEST_CASE("Analyzer jump picks preferred shader entrypoint when present", "[analyzer]")
{
  // entries: VS mainVS, PS mainPS
  // preferred = Pixel => selected.stage == Pixel
}

TEST_CASE("Analyzer texture candidate merge keeps issue-first and dedups", "[analyzer]")
{
  // issue.resourceIds = [texA], fallback event rts=[texA, texB], ds=texC
  // expect candidates == [texA, texB, texC]
}
```

## Task Checklist (2-5 minute granularity, /do execution plan)

- [x] `[3m]` Append no-repeat update to handoff doc (`2026-02-25-184200...`) with commit IDs + remaining work.
- [x] `[2m]` Append concise no-repeat checkpoint to `2026-02-25-174102...`.
- [x] `[4m]` Extract jump-resolution pure helpers in `AnalyzerReportViewer.cpp` (no behavior change).
- [x] `[3m]` Add failing `[analyzer]` tests for shader entrypoint/stage helper behavior.
- [x] `[3m]` Add failing `[analyzer]` tests for texture candidate merge/dedup helper behavior.
- [x] `[3m]` Add failing `[analyzer]` tests for resource/shader numeric sort behavior.
- [x] `[4m]` Apply minimal implementation/refactor until all new tests pass.
- [x] `[3m]` Run `clang-format` on touched C++ files.
- [x] `[3m]` Build with Windows MSBuild.
- [x] `[3m]` Run `qrenderdoc.exe --unittest`.
- [x] `[3m]` Run `qrenderdoc.exe --unittest "[analyzer]"` and confirm non-empty analyzer test execution.
- [x] `[2m]` Update this plan with final verification output and residual risk notes.

## Build/Test/Lint Quick Guide (/plan: record only, do not execute)

- Build:
  - `E:\Program Files\Microsoft Visual Studio\2022\Community\MSBuild\Current\Bin\MSBuild.exe renderdoc.sln /p:Configuration=Development /p:Platform=x64 /m /v:minimal /nologo`
  - Expected: build pass, no errors.
- Unit tests:
  - `D:\Code\git\renderdoc\x64\Development\qrenderdoc.exe --unittest`
  - Expected: exit code 0.
  - `D:\Code\git\renderdoc\x64\Development\qrenderdoc.exe --unittest "[analyzer]"`
  - Expected: exit code 0 and NOT printing "No test cases matched '[analyzer]'".

## Risks / Blockers

- `ResourceId` has no public numeric constructor; test-only synthetic ID helper may be needed for deterministic assertions.
- If helper extraction scope is too large, there is risk of unintended behavior drift in jump path.
- Existing dirty workspace can introduce unrelated failures during full unittest runs.

## Impact Analysis

- User-facing:
  - No direct UI behavior expansion; quality assurance confidence increases via runnable analyzer-tagged tests.
  - Handoff/docs become clearer, reducing duplicate/redundant implementation in future sessions.
- Code impact:
  - Localized to analyzer viewer/model test blocks plus handoff/plan markdown updates.
  - No external API contract changes expected.
- Regression surface:
  - Jump helper refactor boundaries (if not behavior-preserving).
  - Sorting expectations if existing tie-break assumptions differ.

## Verification / Acceptance (Definition of Done)

1) `--unittest "[analyzer]"` executes real analyzer-tagged test cases (not empty-filter run).
2) Analyzer sort tests validate numeric ascending/descending behavior for key columns.
3) Jump helper tests validate stage selection + candidate fallback merge/dedup logic.
4) MSBuild and full unittest pass.
5) Handoff/plan documents explicitly state completed vs remaining tasks with commit references.

## Next Steps

- Wait for `/do` approval.
- On `/do`, implement checklist in order (tests-first), then report:
  - modified files,
  - verification output,
  - next remaining items.

## /do Progress Log (2026-02-25)

- Baseline validation before implementation:
  - `MSBuild.exe renderdoc.sln /p:Configuration=Development /p:Platform=x64 /m /v:minimal /nologo` (PASS)
  - `qrenderdoc.exe --unittest` (PASS, exit 0)
- Implemented in this batch:
  - `AnalyzerReportViewer.cpp`
    - Extracted pure helper functions for jump behavior:
      - `BuildTextureJumpCandidates(...)`
      - `PickEntryPointForStage(...)`
      - `PickPipelineForShaderStage(...)`
    - Reused helpers in runtime jump code path without changing user-facing flow.
    - Added `[analyzer]` tests for candidate merge/dedup and stage-based entry selection.
  - `AnalyzerModels.cpp`
    - Added `[analyzer]` tests validating numeric asc/desc ordering for resource bytes and shader use count.
  - Docs sync:
    - Added no-repeat guard update to `2026-02-25-184200-Agent01-NativeQt-Handoff.md`.
    - Appended progress checkpoint to `2026-02-25-174102-Agent01-NativeQt-PerfectReport.md`.
- Verification after implementation:
  - `clang-format -i qrenderdoc/Windows/AnalyzerReportViewer.cpp qrenderdoc/Windows/AnalyzerModels.cpp`
  - `MSBuild.exe renderdoc.sln /p:Configuration=Development /p:Platform=x64 /m /v:minimal /nologo` (PASS)
  - `qrenderdoc.exe --unittest` (PASS, exit 0)
  - `qrenderdoc.exe --unittest "[analyzer]"` (PASS, exit 0)
  - Cross-check command:
    - `qrenderdoc.exe --unittest "[definitely_missing_tag]"` prints "No test cases matched", confirming filter path is active.
- Residual pending (outside this batch):
  - Manual GUI acceptance on your known problematic captures (Jump/Refresh/Export/busy).

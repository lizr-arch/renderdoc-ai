# Plan: Lead / Post-Reconvergence Hardening

Time: 2026-04-23 13:26:25 | Owner: Lead

## Scope / Assumptions

- Goal: finish the next control-plane phase after DBCA reconvergence by delivering three non-merge tasks:
  - formalize the verified real-RDC `B -> A` regression path as a repo-native smoke entry,
  - harden `A`-line stale-IPC / false-timeout diagnosis without creating a second protocol,
  - lock root-repo dirty-tree handling into explicit control rules so future candidate evaluation stays clean.
- Business baseline remains `renderdoc-ai/main@87c5a0b7a176a6fae40775b0b43d1e21c7740409`.
- No merge or push is included in this plan.
- Prefer Python/docs/control changes only. If a later implementation step requires C++ rebuild, stop and request build approval first.
- Real validation capture stays `D:\backup\EndfieldTBeta2_2025.12.18_14.36_frame42231.rdc`.
- Existing working `qrenderdoc.exe` binary is assumed at `D:\Code\git\renderdoc-agentb-r3\x64\Development\qrenderdoc.exe`.

## Mainline / Contract Guardrails

- Mainline ownership:
  - `B`: GUI report product line.
  - `A`: MCP + Skill consumer line.
  - `Lead`: docs/control only.
- Contract guardrails:
  - keep `snapshot.v1`, `template.v1`, `mcp-query.v1` unchanged,
  - do not add a second report/template/schema system,
  - keep MCP as query/supplement only,
  - keep candidate evaluation on explicit SHA only.

## Build / Test / Lint Quick Guide

- `/plan` phase: record only, do not execute build.
- Expected `/do` validation commands:
  - `py -3 -m pytest D:\Code\git\renderdoc-agenta-r3\tools\mcp\tests\test_snapshot_consumer.py -q`
  - `py -3 D:\Code\git\renderdoc-agentc-r3\scripts\rdc_analyzer\tools\real_rdc_gui_snapshot_smoke.py --qrenderdoc D:\Code\git\renderdoc-agentb-r3\x64\Development\qrenderdoc.exe --capture D:\backup\EndfieldTBeta2_2025.12.18_14.36_frame42231.rdc --out-dir %TEMP%\renderdoc_real_smoke`
  - `py -3 D:\Code\git\renderdoc-agenta-r3\scripts\rdc_analyzer\mcp_examples\run_query.py --method get_capture_status --params "{}"`
  - `py -3 D:\Code\git\renderdoc-agenta-r3\scripts\rdc_analyzer\mcp_examples\run_query.py --method get_frame_summary --params "{}"`
  - `py -3 D:\Code\git\renderdoc-agenta-r3\scripts\rdc_analyzer\mcp_examples\snapshot_consume.py --snapshot %TEMP%\renderdoc_real_smoke\snapshot.v1.json --execute --out-json %TEMP%\renderdoc_real_smoke\consumer.execute.json --out-md %TEMP%\renderdoc_real_smoke\consumer.execute.md --out-cmd %TEMP%\renderdoc_real_smoke\consumer.execute.cmds.txt`
  - `git -C D:\Code\git\renderdoc status --short --branch`
  - `git -C D:\Code\git\renderdoc worktree list --porcelain`

## File List

### Existing evidence / implementation anchors

- `D:\Code\git\renderdoc-agentb-r3\qrenderdoc\Windows\AnalyzerReportViewer.cpp:543-674`
  - `OnCaptureLoaded()` resets UI state only; `RefreshReport()` performs async build and calls `TryAutoExport()`.
- `D:\Code\git\renderdoc-agentb-r3\qrenderdoc\Windows\AnalyzerReportViewer.cpp:1271-1294`
  - auto-export writes `analysis.json`, `snapshot.v1.json`, `capture_context.json`, and issue exports.
- `D:\Code\git\renderdoc-agentb-r3\qrenderdoc\Code\Interface\QRDInterface.h:1155-1167`
  - `IAnalyzerReportViewer::RefreshReport()` is scriptable from Python.
- `D:\Code\git\renderdoc-agenta-r3\scripts\rdc_analyzer\mcp_examples\run_query.py:1-56`
  - thin CLI wrapper over `snapshot_consumer` helpers.
- `D:\Code\git\renderdoc-agenta-r3\scripts\rdc_analyzer\mcp_examples\snapshot_consume.py:1-96`
  - CLI entry for `snapshot_consumer.analyze_snapshot(...)`.
- `D:\Code\git\renderdoc-agenta-r3\tools\mcp\mcp_server\bridge\client.py:1-79`
  - raw file-IPC client; current timeout comes from waiting on `response.json`.
- `D:\Code\git\renderdoc-agenta-r3\tools\mcp\snapshot_consumer.py:335-394`
  - bridge-state inspection and error-payload builder.
- `D:\Code\git\renderdoc-agenta-r3\tools\mcp\snapshot_consumer.py:675-760`
  - error classification, `recovery_hint`, and stale-IPC notes.
- `D:\Code\git\renderdoc\scripts\rdc_analyzer\tools\renderdoc_shell_analyze.py:1-53`
  - pattern for repo-native helper tool with a callable `run(...)`.
- `D:\Code\git\renderdoc\scripts\rdc_analyzer\tools\ui_headless_smoke.py:1-240`
  - pattern for opt-in smoke tooling under `scripts/rdc_analyzer/tools`.
- `D:\Code\git\renderdoc\scripts\rdc_analyzer\tests\test_renderdoc_shell_script.py:1-10`
  - pattern for lightweight tool export smoke.
- `D:\Code\git\renderdoc\scripts\rdc_analyzer\tests\test_ui_headless_smoke.py:1-52`
  - pattern for opt-in integration smoke via env-gated pytest.
- `D:\Code\git\renderdoc\plans\r2_takeover_2026-03-14\R2_BRANCH_STRATEGY_COMMANDS.md:1-25`
  - existing rule: root branch is docs/control only, future D/B/C/A work must start from `renderdoc-ai/main` in new worktrees.
- `D:\Code\git\renderdoc\plans\r2_takeover_2026-03-14\CURRENT_CONTROL_BASELINE.md:1-45`
  - existing rule: root repo is not a business merge source; active candidates are `D-r3 / B-r3 / C-r3 / A-r3`.

### Planned write set for `/do`

- `D:\Code\git\renderdoc-agentc-r3\scripts\rdc_analyzer\tools\renderdoc_gui_refresh_export.py`
  - repo-native `--python` helper that waits for capture load, opens Analyzer Report, calls `RefreshReport()`, and writes a state file.
- `D:\Code\git\renderdoc-agentc-r3\scripts\rdc_analyzer\tools\real_rdc_gui_snapshot_smoke.py`
  - top-level CLI wrapper that launches `qrenderdoc.exe`, sets env vars, polls export outputs, optionally runs `A`-line `snapshot_consume.py`, and emits a summary JSON/MD.
- `D:\Code\git\renderdoc-agentc-r3\scripts\rdc_analyzer\tests\test_real_rdc_gui_snapshot_smoke.py`
  - opt-in integration test guarded by env vars for local-only real-RDC execution.
- `D:\Code\git\renderdoc-agenta-r3\tools\mcp\mcp_server\bridge\client.py`
  - minimal stale-IPC diagnostics before or during timeout reporting.
- `D:\Code\git\renderdoc-agenta-r3\tools\mcp\snapshot_consumer.py`
  - enrich timeout notes/hints with stale-request age and GUI-not-running guidance while keeping `mcp-query.v1` envelope unchanged.
- `D:\Code\git\renderdoc\plans\r2_takeover_2026-03-14\CURRENT_CONTROL_BASELINE.md`
  - update current control rules for dirty-root isolation.
- `D:\Code\git\renderdoc\plans\r2_takeover_2026-03-14\R2_BRANCH_STRATEGY_COMMANDS.md`
  - add explicit root-dirty audit grouping and candidate-surface cleanup commands.

## Pseudo-code / Implementation Sketch

### Stream 1: Formal real-RDC regression entry

1. Add `renderdoc_gui_refresh_export.py`.
2. In that helper:
   - wait for `pyrenderdoc.IsCaptureLoaded()`,
   - call `pyrenderdoc.ShowAnalyzerReportViewer()`,
   - obtain `viewer = pyrenderdoc.GetAnalyzerReportViewer()`,
   - call `viewer.RefreshReport()`,
   - poll for `%RENDERDOC_ANALYZER_AUTO_EXPORT_DIR%\\snapshot.v1.json`,
   - write `state.json` with `capture_loaded`, `viewer_present`, `refresh_called`, `snapshot_exists`.
3. Add `real_rdc_gui_snapshot_smoke.py`.
4. In that wrapper:
   - validate `--qrenderdoc`, `--capture`, and output dir,
   - set `RENDERDOC_ANALYZER_AUTO_EXPORT_DIR`,
   - start `qrenderdoc.exe --python <repo_helper> <capture>`,
   - poll `state.json` and export directory,
   - run `run_query.py get_capture_status`,
   - run `run_query.py get_frame_summary`,
   - run `snapshot_consume.py --execute`,
   - aggregate everything into one summary JSON/Markdown,
   - ensure launched process is closed on completion/error.
5. Add opt-in pytest wrapper patterned after `test_ui_headless_smoke.py`.

### Stream 2: A-line stale-IPC / false-timeout hardening

1. Keep `run_query.py` thin unless a CLI-only clarification is strictly needed.
2. In `client.py`, add lightweight stale-IPC context capture:
   - request/response existence,
   - request/response ages,
   - whether GUI is likely absent vs replay-thread blocked.
3. In `snapshot_consumer.py`:
   - reuse existing `inspect_bridge_state()` / `_build_error_notes()` / `recovery_hint_for_error()`,
   - extend `timeout` path to distinguish:
     - no IPC dir,
     - IPC dir with stale `request.json` and no active response,
     - likely replay-thread blocked while GUI is alive,
   - keep all output inside existing `mcp-query.v1` `availability.notes` + `recovery_hint`.
4. Ensure `snapshot_consume.py --execute` inherits the improved hints through the same helper path.

### Stream 3: Root dirty-tree isolation and candidate-surface cleanup

1. Do not revert or rewrite any root dirty files.
2. Record dirty-root groups explicitly:
   - `qrenderdoc/Code/Interface/*`
   - `qrenderdoc/Windows/Dialogs/*`
   - `renderdoc/android/*`
   - root `plans/*`
3. Update control docs so future execution follows:
   - root repo is docs/control only,
   - all business candidates must come from `r3` worktrees,
   - candidate review must use `git diff --name-only renderdoc-ai/main...HEAD`,
   - old banned line `d66d0f73b` remains historical only.
4. Add a small audit command block for future turns:
   - root status grouping,
   - `r3` status/diff audit,
   - banned-lane spot check,
   - no-merge default.

## Impact Analysis

- `B` impact:
  - expected change is tooling only, not GUI C++ product code,
  - reduces future false blocker reports on GUI export.
- `A` impact:
  - expected change is Python MCP client/consumer diagnostics only,
  - improves operator recovery without changing contract shape.
- `Lead` / root impact:
  - docs/control only,
  - no business merge source change,
  - future candidate reviews become cheaper and less ambiguous.
- Contract impact:
  - no new schema keys are required,
  - no template/report duplication is introduced.

## Task Checklist

- [x] T1-1: capture repo-native helper file design for `renderdoc_gui_refresh_export.py`.
- [x] T1-2: capture repo-native wrapper design for `real_rdc_gui_snapshot_smoke.py`.
- [x] T1-3: define opt-in test contract and env vars for local-only execution.
- [x] T2-1: pinpoint exact stale-IPC logic insertions in `client.py`.
- [x] T2-2: pinpoint exact `snapshot_consumer.py` note/hint extensions while preserving `mcp-query.v1`.
- [x] T2-3: define verification matrix for `bridge_unavailable` / stale IPC / healthy GUI.
- [x] T3-1: classify current root dirty files into non-DBCA groups.
- [x] T3-2: define docs/control updates for root isolation and candidate cleanup.
- [x] T3-3: record future audit commands for root + `r3` worktrees.
- [x] T4-1: during `/do`, keep all edits out of business C++ unless a new blocker invalidates the Python/docs path.
- [x] T4-2: during `/do`, run real-RDC smoke end-to-end and attach absolute-path evidence.

## Risks / Blockers

- The formal smoke depends on an existing built `qrenderdoc.exe`; if binaries drift or disappear, `/do` must stop and request build approval.
- The real capture file is outside the repo; smoke must treat it as user-provided local input and never copy it into the repo.
- Root dirty-tree isolation is a control measure, not an actual cleanup of unrelated changes. It reduces merge risk but does not sanitize the root worktree itself.
- `git branch --contains d66d0f73b` will still list historical branches; candidate exclusion must continue to rely on explicit SHA and diff surface, not branch name alone.

## Verification / Acceptance

- Definition of Done:
  - [x] A repo-native smoke CLI exists under `scripts/rdc_analyzer/tools/`.
  - [x] The smoke can launch `qrenderdoc.exe`, trigger `RefreshReport()`, and confirm `snapshot.v1.json` + `analysis.json` + `capture_context.json`.
  - [x] The smoke can run `A`-line `get_capture_status`, `get_frame_summary`, and `snapshot_consume.py --execute`.
  - [x] `snapshot_consumer.py` still emits a single `mcp-query.v1` envelope and improved timeout notes/hints.
  - [x] `pytest D:\Code\git\renderdoc-agenta-r3\tools\mcp\tests\test_snapshot_consumer.py -q` remains green.
  - [x] Root control docs explicitly state that root dirty files are not DBCA business candidates.
  - [x] No new schema/template/report surface is added.
  - [x] Merge/push decisions stay on explicit candidate SHA only.
  - [x] Merge/push is executed only after explicit user approval.

## Next Steps

1. Move to `/do` and implement Stream 1 first, because it gives the highest-confidence regression harness for both `B` and `A`.
2. Implement Stream 2 second, using the new smoke harness to validate stale-IPC diagnostics against real GUI states.
3. Finish Stream 3 last as docs/control hardening, then re-run root + `r3` audit commands and stop for merge guidance.

## /do Execution Log (Lead, 2026-04-23 - Post-Reconvergence Hardening)

- Stream 1: formal real-RDC GUI smoke
  - New files:
    - `D:\Code\git\renderdoc-agentc-r3\scripts\rdc_analyzer\tools\renderdoc_gui_refresh_export.py`
    - `D:\Code\git\renderdoc-agentc-r3\scripts\rdc_analyzer\tools\real_rdc_gui_snapshot_smoke.py`
    - `D:\Code\git\renderdoc-agentc-r3\scripts\rdc_analyzer\tests\test_real_rdc_gui_snapshot_smoke.py`
  - Fast validation:
    - `py -3 -m py_compile D:\Code\git\renderdoc-agentc-r3\scripts\rdc_analyzer\tools\renderdoc_gui_refresh_export.py D:\Code\git\renderdoc-agentc-r3\scripts\rdc_analyzer\tools\real_rdc_gui_snapshot_smoke.py D:\Code\git\renderdoc-agentc-r3\scripts\rdc_analyzer\tests\test_real_rdc_gui_snapshot_smoke.py`
      - result: pass
    - `py -3 -m pytest D:\Code\git\renderdoc-agentc-r3\scripts\rdc_analyzer\tests\test_real_rdc_gui_snapshot_smoke.py -q`
      - result: `1 passed, 1 skipped`
  - End-to-end smoke:
    - command:
      - `py -3 D:\Code\git\renderdoc-agentc-r3\scripts\rdc_analyzer\tools\real_rdc_gui_snapshot_smoke.py --capture D:\backup\EndfieldTBeta2_2025.12.18_14.36_frame42231.rdc --out-dir C:\Users\lizhirui01\AppData\Local\Temp\renderdoc_real_smoke_r3 --qrenderdoc D:\Code\git\renderdoc-agentb-r3\x64\Development\qrenderdoc.exe --run-query D:\Code\git\renderdoc-agenta-r3\scripts\rdc_analyzer\mcp_examples\run_query.py --snapshot-consume D:\Code\git\renderdoc-agenta-r3\scripts\rdc_analyzer\mcp_examples\snapshot_consume.py`
      - result: `success=true`
    - state file:
      - `C:\Users\lizhirui01\AppData\Local\Temp\renderdoc_real_smoke_r3\gui_state.json`
      - result: `phase=done`, `capture_loaded=true`, `viewer_present=true`, `refresh_called=true`
    - exports:
      - `snapshot.v1.json` -> `1821262` bytes
      - `analysis.json` -> `804710` bytes
      - `capture_context.json` -> `851` bytes
    - summary:
      - `C:\Users\lizhirui01\AppData\Local\Temp\renderdoc_real_smoke_r3\real_rdc_gui_snapshot_smoke.summary.json`
      - result:
        - `mcp.get_capture_status.json.ok=true`
        - `mcp.get_frame_summary.json.ok=true`
        - `consumer.json.enrichment.status=executed`
        - `consumer.json.health_probe.ok=true`
  - Follow-up hardening on 2026-04-23:
    - `real_rdc_gui_snapshot_smoke.py` now clears stale `%TEMP%\renderdoc_mcp\{request,response,lock}` files before launch.
    - `real_rdc_gui_snapshot_smoke.py` now retries `get_capture_status` / `get_frame_summary` within the configured query timeout window instead of assuming MCP readiness immediately after GUI export.
    - Validation:
      - `py -3 -m py_compile D:\Code\git\renderdoc-agentc-r3\scripts\rdc_analyzer\tools\real_rdc_gui_snapshot_smoke.py`
        - result: pass
      - `py -3 -m pytest D:\Code\git\renderdoc-agentc-r3\scripts\rdc_analyzer\tests\test_real_rdc_gui_snapshot_smoke.py -q`
        - result: `1 passed, 1 skipped`
  - Additional hardening and blocker isolation on 2026-04-23:
    - Reproduced that synchronous `InvokeOntoUIThread(...)+Event.wait()` is not viable for the startup helper:
      - command:
        - `py -3 D:\Code\git\renderdoc-agentc-r3\scripts\rdc_analyzer\tools\real_rdc_gui_snapshot_smoke.py --capture D:\backup\EndfieldTBeta2_2025.12.18_14.36_frame42231.rdc --out-dir C:\Users\lizhirui01\AppData\Local\Temp\renderdoc_real_smoke_r3 --qrenderdoc D:\Code\git\renderdoc-agentb-r3\x64\Development\qrenderdoc.exe --run-query D:\Code\git\renderdoc-agenta-r3\scripts\rdc_analyzer\mcp_examples\run_query.py --snapshot-consume D:\Code\git\renderdoc-agenta-r3\scripts\rdc_analyzer\mcp_examples\snapshot_consume.py`
      - result:
        - `C:\Users\lizhirui01\AppData\Local\Temp\renderdoc_real_smoke_r3\gui_state.json` reached `phase=error`
        - `error=RuntimeError('Timed out waiting for UI-thread RefreshReport dispatch',)`
    - Based on local source inspection (MCP unavailable), confirmed startup `--python` scripts receive raw `ICaptureContext`, not the PythonShell UI-thread marshalling wrapper; therefore `RefreshReport()` must be dispatched onto the UI thread, but the helper must not synchronously wait for that Python callback to run.
    - Updated `renderdoc_gui_refresh_export.py`:
      - `gui_state.json` now writes via temp file + `os.replace(...)` with retry to avoid Windows read/replace races.
      - `RefreshReport()` is now dispatched asynchronously onto the UI thread, and state notes record:
        - `dispatching RefreshReport on UI thread`
        - `RefreshReport entered on UI thread`
        - `RefreshReport returned on UI thread`
    - Updated `real_rdc_gui_snapshot_smoke.py`:
      - `gui_state.json` reads now tolerate transient partial JSON / empty-file windows via retry.
      - stale cleanup now also removes `gui_state.json.tmp` and old `issues_export.{csv,md}`.
    - Added wrapper regression test:
      - `D:\Code\git\renderdoc-agentc-r3\scripts\rdc_analyzer\tests\test_real_rdc_gui_snapshot_smoke.py`
      - new unit case covers partial `gui_state.json` recovery.
    - Validation:
      - `py -3 -m py_compile D:\Code\git\renderdoc-agentc-r3\scripts\rdc_analyzer\tools\renderdoc_gui_refresh_export.py D:\Code\git\renderdoc-agentc-r3\scripts\rdc_analyzer\tools\real_rdc_gui_snapshot_smoke.py D:\Code\git\renderdoc-agentc-r3\scripts\rdc_analyzer\tests\test_real_rdc_gui_snapshot_smoke.py`
        - result: pass
      - `py -3 -m pytest D:\Code\git\renderdoc-agentc-r3\scripts\rdc_analyzer\tests\test_real_rdc_gui_snapshot_smoke.py -q`
        - result: `2 passed, 1 skipped`
    - Current live blocker after hardening:
      - command:
        - `py -3 D:\Code\git\renderdoc-agentc-r3\scripts\rdc_analyzer\tools\real_rdc_gui_snapshot_smoke.py --capture D:\backup\EndfieldTBeta2_2025.12.18_14.36_frame42231.rdc --out-dir C:\Users\lizhirui01\AppData\Local\Temp\renderdoc_real_smoke_r3 --qrenderdoc D:\Code\git\renderdoc-agentb-r3\x64\Development\qrenderdoc.exe --run-query D:\Code\git\renderdoc-agenta-r3\scripts\rdc_analyzer\mcp_examples\run_query.py --snapshot-consume D:\Code\git\renderdoc-agenta-r3\scripts\rdc_analyzer\mcp_examples\snapshot_consume.py`
      - live state after 60s:
        - `C:\Users\lizhirui01\AppData\Local\Temp\renderdoc_real_smoke_r3\gui_state.json`
          - `capture_loaded=true`
          - `viewer_present=true`
          - `refresh_called=true`
          - notes contain `RefreshReport entered on UI thread` and `RefreshReport returned on UI thread`
          - `analysis.json / capture_context.json / snapshot.v1.json` all still absent
        - `Get-Process qrenderdoc -ErrorAction SilentlyContinue | Select-Object Id,ProcessName,StartTime,Path`
          - `qrenderdoc.exe` still alive
      - interpretation:
        - harness-side dispatch/race issues are now mostly cleared,
        - the remaining blocker is inside the `AnalyzerReportViewer::RefreshReport() -> AsyncInvoke(...) -> GUIInvoke::call(...) -> TryAutoExport()` chain, or a downstream analyzer build step such as replay-event walks / GPU counter fetch,
        - this likely requires `B`-line C++ inspection and then a rebuild, which is outside the current no-build change set.
        - result: `1 passed, 1 skipped`
    - Current blocker:
      - latest real-RDC smoke reaches `get_capture_status.ok=true` and `get_frame_summary.ok=true`, but `snapshot_consume.py --execute` remains blocked.
      - evidence:
        - `C:\Users\lizhirui01\AppData\Local\Temp\renderdoc_real_smoke_r3\real_rdc_gui_snapshot_smoke.summary.json`
        - `mcp.get_capture_status.attempt_count=4`
        - `mcp.get_capture_status.json.ok=true`
        - `mcp.get_frame_summary.attempt_count=1`
        - `mcp.get_frame_summary.json.ok=true`
        - `consumer.json.enrichment.status=blocked`
        - `consumer.json.health_probe.error.code=timeout`

- Stream 2: stale IPC / false-timeout hardening
  - Updated files:
    - `D:\Code\git\renderdoc-agenta-r3\tools\mcp\mcp_server\bridge\client.py`
    - `D:\Code\git\renderdoc-agenta-r3\tools\mcp\snapshot_consumer.py`
  - Implementation notes:
    - `client.py` now appends current/preexisting IPC state to timeout errors.
    - `snapshot_consumer.py` now parses bridge diagnostics, emits `state_hint`, request/response ages, and recognizes stale preexisting IPC in `availability.notes` + `recovery_hint`.
    - Contract remains `mcp-query.v1`; no second envelope was introduced.
  - Validation:
    - `py -3 -m pytest D:\Code\git\renderdoc-agenta-r3\tools\mcp\tests\test_snapshot_consumer.py -q`
      - result: `10 passed`
    - synthetic stale IPC probe:
      - `py -3 -c "... build_error_payload(code='timeout', message='Request timed out while waiting for RenderDoc MCP response. current_... preexisting_request_present=true ...')"`
      - result:
        - `notes` includes `state_hint=awaiting_response`
        - `notes` includes `stale_ipc_detected=true`
        - `recovery_hint` points to restarting RenderDoc or clearing temp bridge files
    - live no-GUI probe:
      - `py -3 D:\Code\git\renderdoc-agenta-r3\scripts\rdc_analyzer\mcp_examples\run_query.py --method get_capture_status --params "{}"`
      - result:
        - `error.code=timeout`
        - `availability.notes` includes `state_hint=awaiting_response`
        - `availability.notes` includes `request_age_seconds=30.039...`
        - `preexisting_request_present=false`
  - Follow-up hardening on 2026-04-23:
    - `snapshot_consumer.py` now adds OS-process heuristic notes for `qrenderdoc` presence while preserving the same `mcp-query.v1` envelope.
    - Validation:
      - `py -3 -m py_compile D:\Code\git\renderdoc-agenta-r3\tools\mcp\snapshot_consumer.py D:\Code\git\renderdoc-agenta-r3\tools\mcp\tests\test_snapshot_consumer.py`
        - result: pass
      - `py -3 -m pytest D:\Code\git\renderdoc-agenta-r3\tools\mcp\tests\test_snapshot_consumer.py -q`
        - result: `11 passed`
      - live no-GUI probe:
        - `py -3 D:\Code\git\renderdoc-agenta-r3\scripts\rdc_analyzer\mcp_examples\run_query.py --method get_capture_status --params "{}"`
        - result:
          - `availability.notes` includes `state_hint=gui_not_running`
          - `availability.notes` includes `renderdoc_gui_running=false`
          - stale IPC is surfaced when present via `stale_ipc_detected=true`

- Stream 3: root docs/control hardening
  - Updated files:
    - `D:\Code\git\renderdoc\plans\r2_takeover_2026-03-14\CURRENT_CONTROL_BASELINE.md`
    - `D:\Code\git\renderdoc\plans\r2_takeover_2026-03-14\R2_BRANCH_STRATEGY_COMMANDS.md`
  - Result:
    - root repo explicitly documented as docs/control only
    - candidate source constrained to `r3` worktrees or explicit SHA
    - dirty-root grouping and future audit commands recorded
  - Validation:
    - `git -C D:\Code\git\renderdoc diff --check -- plans\r2_takeover_2026-03-14\CURRENT_CONTROL_BASELINE.md plans\r2_takeover_2026-03-14\R2_BRANCH_STRATEGY_COMMANDS.md`
      - result: pass

- Late-session continuation on 2026-04-23:
  - B-line rollback and rebuild:
    - reverted the temporary `serial mismatch -> DelayedCallback retry` experiment in:
      - `D:\Code\git\renderdoc-agentb-r3\qrenderdoc\Windows\AnalyzerReportViewer.cpp`
    - rebuilt successfully:
      - `E:\Program Files\Microsoft Visual Studio\2022\Community\MSBuild\Current\Bin\MSBuild.exe D:\Code\git\renderdoc-agentb-r3\qrenderdoc\qrenderdoc_local.vcxproj /p:Configuration=Development /p:Platform=x64 /p:SolutionDir=D:\Code\git\renderdoc-agentb-r3\`
      - result: `0 warning / 0 error`
    - recovered the old stable blocker once:
      - `C:\Users\lizhirui01\AppData\Local\Temp\renderdoc_real_smoke_r3\gui_state.json`
        - notes included:
          - `dispatching RefreshReport on UI thread`
          - `RefreshReport entered on UI thread`
          - `RefreshReport returned on UI thread`
        - `replay_processing_seconds` dropped from `>0` back to `0.0`
        - `analysis.json / snapshot.v1.json / capture_context.json` still absent
  - B-line trace instrumentation:
    - added auto-export trace emission to:
      - `D:\Code\git\renderdoc-agentb-r3\qrenderdoc\Windows\AnalyzerReportViewer.cpp`
    - trace file:
      - `C:\Users\lizhirui01\AppData\Local\Temp\renderdoc_real_smoke_r3\analyzer_auto_export_trace.log`
    - trace evidence on the stable-helper run:
      - `event=OnCaptureLoaded`
      - `event=OnCaptureClosed`
      - `event=RefreshReport.enter`
      - `event=RefreshReport.dispatch`
      - no later `gui_callback_enter / serial_mismatch / success_before_auto_export / TryAutoExport.enter` line was observed even after helper-side `replay_processing_seconds=0.0`
    - added one more trace layer around:
      - `event=RefreshReport.replay_build_done`
      - `event=RefreshReport.gui_invoke_queued`
    - rebuilt successfully again:
      - result: `0 warning / 0 error`
  - C-line helper stabilization:
    - updated:
      - `D:\Code\git\renderdoc-agentc-r3\scripts\rdc_analyzer\tools\renderdoc_gui_refresh_export.py`
      - `D:\Code\git\renderdoc-agentc-r3\scripts\rdc_analyzer\tools\real_rdc_gui_snapshot_smoke.py`
    - changes:
      - require analyzer viewer visibility on 2 consecutive polls before treating it as ready
      - retry UI-thread `RefreshReport` dispatch up to 3 times
      - fail fast if helper never observes `RefreshReport` entry within 5 seconds per dispatch attempt
      - cleanup now also removes `analyzer_auto_export_trace.log`
    - validation:
      - `py -3 -m py_compile D:\Code\git\renderdoc-agentc-r3\scripts\rdc_analyzer\tools\renderdoc_gui_refresh_export.py D:\Code\git\renderdoc-agentc-r3\scripts\rdc_analyzer\tools\real_rdc_gui_snapshot_smoke.py`
        - result: pass
  - New blocker after helper stabilization:
    - latest smoke again fails before export, but now the symptom shifted:
      - `C:\Users\lizhirui01\AppData\Local\Temp\renderdoc_real_smoke_r3\gui_state.json`
        - `phase="viewer_requested"`
        - `viewer_present=true`
        - `refresh_called=false`
        - `notes=[]`
      - matching trace file still only contains:
        - `event=OnCaptureLoaded`
        - `event=OnCaptureClosed`
      - `qrenderdoc.exe` exits before wrapper completion:
        - wrapper result remains `RuntimeError: qrenderdoc exited before smoke completed`
    - current interpretation:
      - there are at least two distinct live races:
        - helper-side UI dispatch/viewer readiness can fail before `RefreshReport()` is entered
        - when helper-side dispatch does succeed, the B-line `RefreshReport -> AsyncInvoke -> GUIInvoke -> TryAutoExport` chain can still fail to reach `TryAutoExport()`
  - Root-cause reclassification and recovery:
    - source review confirmed the startup-script path was wrong for this regression harness:
      - `Get-Content D:\Code\git\renderdoc-agentb-r3\qrenderdoc\Code\qrenderdoc.cpp | Select-Object -Skip 620 -First 130`
        - result: `--python` executes `py.ctx().executeFile(...)` before `ctx.Begin(...)`
      - `Get-Content D:\Code\git\renderdoc-agentb-r3\qrenderdoc\Code\CaptureContext.cpp | Select-Object -Skip 230 -First 70`
        - result: `ctx.Begin(..., scriptFilename)` shows the main window, loads the capture, and only then calls `ShowPythonShell()` + `RunScript()`
      - `Get-Content D:\Code\git\renderdoc-agentb-r3\qrenderdoc\Windows\PythonShell.cpp | Select-Object -Skip 1080 -First 90`
        - result: `RunScript()` executes on the Python shell worker after UI startup
      - `Get-Content D:\Code\git\renderdoc-agentb-r3\qrenderdoc\Windows\PythonShell.cpp | Select-Object -Skip 1610 -First 70`
        - result: the bound `pyrenderdoc` object is the UI-marshalled thread context
    - conclusion:
      - the old `--python` helper path was a lifecycle mismatch for analyzer auto-export,
      - the harness must use `--ui-python` so that capture load, viewer creation, and `RefreshReport()` run against the intended UI state.
  - Final successful recovery on 2026-04-23:
    - updated helper launch path to `--ui-python` and kept the helper synchronous:
      - `D:\Code\git\renderdoc-agentc-r3\scripts\rdc_analyzer\tools\renderdoc_gui_refresh_export.py`
      - `D:\Code\git\renderdoc-agentc-r3\scripts\rdc_analyzer\tools\real_rdc_gui_snapshot_smoke.py`
    - validation:
      - `py -3 -m pytest D:\Code\git\renderdoc-agentc-r3\scripts\rdc_analyzer\tests\test_real_rdc_gui_snapshot_smoke.py -q`
        - result: `2 passed, 1 skipped`
      - `py -3 -m pytest D:\Code\git\renderdoc-agenta-r3\tools\mcp\tests\test_snapshot_consumer.py -q`
        - result: `11 passed`
      - repeated real-RDC smoke:
        - `py -3 D:\Code\git\renderdoc-agentc-r3\scripts\rdc_analyzer\tools\real_rdc_gui_snapshot_smoke.py --capture D:\backup\EndfieldTBeta2_2025.12.18_14.36_frame42231.rdc --out-dir C:\Users\lizhirui01\AppData\Local\Temp\renderdoc_real_smoke_r3 --qrenderdoc D:\Code\git\renderdoc-agentb-r3\x64\Development\qrenderdoc.exe --run-query D:\Code\git\renderdoc-agenta-r3\scripts\rdc_analyzer\mcp_examples\run_query.py --snapshot-consume D:\Code\git\renderdoc-agenta-r3\scripts\rdc_analyzer\mcp_examples\snapshot_consume.py`
        - result: `success=true`
      - GUI state:
        - `C:\Users\lizhirui01\AppData\Local\Temp\renderdoc_real_smoke_r3\gui_state.json`
        - result: `phase=done`, `capture_loaded=true`, `viewer_present=true`, `refresh_called=true`, `replay_processing_seconds=0.0`
      - auto-export trace:
        - `C:\Users\lizhirui01\AppData\Local\Temp\renderdoc_real_smoke_r3\analyzer_auto_export_trace.log`
        - result includes:
          - `event=RefreshReport.replay_build_done`
          - `event=RefreshReport.gui_invoke_queued`
          - `event=RefreshReport.gui_callback_enter`
          - `event=RefreshReport.success_before_auto_export`
          - `event=TryAutoExport.write_result success=1`
      - exported files:
        - `C:\Users\lizhirui01\AppData\Local\Temp\renderdoc_real_smoke_r3\snapshot.v1.json` -> `1821130` bytes
        - `C:\Users\lizhirui01\AppData\Local\Temp\renderdoc_real_smoke_r3\analysis.json` -> `804591` bytes
        - `C:\Users\lizhirui01\AppData\Local\Temp\renderdoc_real_smoke_r3\capture_context.json` -> `851` bytes
      - MCP + consumer:
        - `C:\Users\lizhirui01\AppData\Local\Temp\renderdoc_real_smoke_r3\real_rdc_gui_snapshot_smoke.summary.json`
        - result:
          - `commands.gui_launch` uses `qrenderdoc.exe --ui-python ...renderdoc_gui_refresh_export.py ...`
          - `mcp.get_capture_status.ok=true`
          - `mcp.get_frame_summary.ok=true`
          - `consumer.json.enrichment.status=executed`
          - `consumer.json.enrichment.health_probe.ok=true`
      - process cleanup:
        - `Get-Process qrenderdoc -ErrorAction SilentlyContinue`
        - result: no remaining `qrenderdoc` process
    - status:
      - the live blocker for `.rdc -> GUI auto-export -> MCP -> snapshot_consume --execute` is cleared,
      - remaining work is candidate-surface cleanup and Gate preparation, not functional recovery.
  - B-line trace contraction after recovery:
    - refined:
      - `D:\Code\git\renderdoc-agentb-r3\qrenderdoc\Windows\AnalyzerReportViewer.cpp`
    - intent:
      - keep only the minimum formal diagnostic surface:
        - `RefreshReport.replay_build_done`
        - `RefreshReport.serial_mismatch`
        - `TryAutoExport.mkdir_failed`
        - `TryAutoExport.write_result success=0/1`
      - gate `qInfo()` behind `m_AutoExportDir` so normal GUI paths do not receive unsolicited trace noise.
    - validation:
      - `E:\Program Files\Microsoft Visual Studio\2022\Community\MSBuild\Current\Bin\MSBuild.exe D:\Code\git\renderdoc-agentb-r3\qrenderdoc\qrenderdoc_local.vcxproj /p:Configuration=Development /p:Platform=x64 /p:SolutionDir=D:\Code\git\renderdoc-agentb-r3\`
        - result: `0 warning / 0 error`
      - repeated real-RDC smoke after trace contraction:
        - `py -3 D:\Code\git\renderdoc-agentc-r3\scripts\rdc_analyzer\tools\real_rdc_gui_snapshot_smoke.py --capture D:\backup\EndfieldTBeta2_2025.12.18_14.36_frame42231.rdc --out-dir C:\Users\lizhirui01\AppData\Local\Temp\renderdoc_real_smoke_r3 --qrenderdoc D:\Code\git\renderdoc-agentb-r3\x64\Development\qrenderdoc.exe --run-query D:\Code\git\renderdoc-agenta-r3\scripts\rdc_analyzer\mcp_examples\run_query.py --snapshot-consume D:\Code\git\renderdoc-agenta-r3\scripts\rdc_analyzer\mcp_examples\snapshot_consume.py`
        - result: `success=true`
      - contracted trace evidence:
        - `C:\Users\lizhirui01\AppData\Local\Temp\renderdoc_real_smoke_r3\analyzer_auto_export_trace.log`
        - result includes only:
          - `event=RefreshReport.replay_build_done`
          - `event=TryAutoExport.write_result success=1`
      - GUI state remained healthy:
        - `C:\Users\lizhirui01\AppData\Local\Temp\renderdoc_real_smoke_r3\gui_state.json`
        - result: `phase=done`, `capture_loaded=true`, `viewer_present=true`, `refresh_called=true`, `replay_processing_seconds=0.0`
    - candidate-surface note:
      - `git -C D:\Code\git\renderdoc-agentb-r3 diff --stat renderdoc-ai/main -- qrenderdoc/Windows/AnalyzerReportViewer.cpp`
        - result: `69 insertions(+), 3 deletions(-)` after contraction
      - `git -C D:\Code\git\renderdoc-agentb-r3 status --porcelain=v1 -b`
        - result: worktree still dirty, so there is still no explicit B-line candidate SHA.

- Candidate creation and mainline reconvergence:
  - explicit candidate SHAs created from the `r3` worktrees:
    - `git -C D:\Code\git\renderdoc-agentb-r3 commit -m "fix(gui-analyzer): keep minimal auto-export trace surface"`
      - result: `70ff751cd9756108dd085d24d38d9825d8b60421`
    - `git -C D:\Code\git\renderdoc-agentc-r3 commit -m "feat(rdc-analyzer): add real rdc gui smoke harness"`
      - result: `d508e23e6e2a0717b8db4f43fe5c5979489fea20`
    - `git -C D:\Code\git\renderdoc-agenta-r3 commit -m "fix(mcp): enrich gui timeout diagnostics"`
      - result: `103b4e458da17ba15c43bd6638ca5677a5f790df`
  - mainline merge workspace:
    - `D:\Code\git\renderdoc-main-merge`
    - `git -C D:\Code\git\renderdoc-main-merge switch -c codex/main-gate5-merge-20260423`
    - `git -C D:\Code\git\renderdoc-main-merge cherry-pick 70ff751cd9756108dd085d24d38d9825d8b60421`
      - result: `4890c41de...`
    - `git -C D:\Code\git\renderdoc-main-merge cherry-pick d508e23e6e2a0717b8db4f43fe5c5979489fea20`
      - result: `34bff320c...`
    - `git -C D:\Code\git\renderdoc-main-merge cherry-pick 103b4e458da17ba15c43bd6638ca5677a5f790df`
      - result: `cae519d0d814dc2da24843408768fbb8d22e8673`
    - `git -C D:\Code\git\renderdoc-main-merge status --porcelain=v1 -b`
      - result: `## codex/main-gate5-merge-20260423`
  - approved push to remote main:
    - `git -C D:\Code\git\renderdoc-main-merge push renderdoc-ai codex/main-gate5-merge-20260423:main`
      - result: `87c5a0b7a..cae519d0d  codex/main-gate5-merge-20260423 -> main`
    - `git -C D:\Code\git\renderdoc ls-remote renderdoc-ai refs/heads/main`
      - result: `cae519d0d814dc2da24843408768fbb8d22e8673 refs/heads/main`

- Post-push status freeze on 2026-04-23:
  - `DBCA` completion state:
    - `B`: merged to `renderdoc-ai/main` at `70ff751cd9756108dd085d24d38d9825d8b60421`.
    - `C`: merged to `renderdoc-ai/main` at `d508e23e6e2a0717b8db4f43fe5c5979489fea20`.
    - `A`: merged to `renderdoc-ai/main` at `103b4e458da17ba15c43bd6638ca5677a5f790df`.
    - `D`: code branch remains `87c5a0b7a176a6fae40775b0b43d1e21c7740409` on `codex/agentd/m0c-android-regression-r3`; no additional business patch was required for this gate.
  - `D` regression gap remains open:
    - source plan:
      - `D:\Code\git\renderdoc-agentd-r3\plans\2026-03-11-170659-AgentD-M0C-Android-Launch-Diagnose.md`
    - `rg -n "已完成真机闭环|未完成真机闭环|JDWPFailure|AndroidLayerConfFailed" D:\Code\git\renderdoc-agentd-r3\plans\2026-03-11-170659-AgentD-M0C-Android-Launch-Diagnose.md`
      - result:
        - completed on real device: successful `Launch + Capture`, `AndroidAPKInstallFailed`, `InjectionFailed(timeout)`, `InjectionFailed(non-timeout)`
        - still missing fresh device evidence: `JDWPFailure`, `AndroidLayerConfFailed`
    - `adb devices -l`
      - result: no attached Android device, so fresh device-side closure could not be executed in this turn
  - `r3` source worktrees are not yet cleaned:
    - `git -C D:\Code\git\renderdoc-agentd-r3 status --porcelain=v1 -b`
      - result: `behind 3`, plan file dirty
    - `git -C D:\Code\git\renderdoc-agentb-r3 status --porcelain=v1 -b`
      - result: `ahead 1, behind 3`
    - `git -C D:\Code\git\renderdoc-agentc-r3 status --porcelain=v1 -b`
      - result: `ahead 2, behind 3`
    - `git -C D:\Code\git\renderdoc-agenta-r3 status --porcelain=v1 -b`
      - result: `ahead 1, behind 3`, plan file dirty
    - control note:
      - source worktrees should stay read-only audit objects until an explicit cleanup instruction authorizes branch retirement and/or worktree removal.

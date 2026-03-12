# P0/P1/P2 End-to-End Verification Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Version:** 2026-02-17  
**Owner:** Agent02  
**Last Updated:** 2026-02-17  

**Goal:** Prove P0/P1/P2 are end-to-end reproducible with executable evidence and documented outputs.

**Architecture:** Run targeted + full pytest, execute Gate-1 3-command chain on a real RDC sample, generate HTML outputs, and document evidence in a verification report. Update trackers only if results diverge from docs.

**Tech Stack:** Python (py -3), pytest, RenderDoc CLI (renderdoccmd), PowerShell, RDC Analyzer scripts.

**Success Criteria (measurable):**
- All specified pytest commands exit 0 with no warnings.
- Gate-1 3-command chain runs end-to-end on a real sample and produces HTML + JSON + chunk counts.
- HTML review artifacts exist (headless run folder or manual review notes).

**Acceptance Criteria:**
- Verification report includes timestamps, commands, and output paths for each P0/P1/P2 item.
- Any mismatch is explicitly recorded as a blocker or updated in trackers with rationale.

**Verification Commands:**
- py -3 -m pytest scripts/rdc_analyzer/tests/test_dod_compliance.py::TestVerificationPlanSchema -v (Expected: PASS)
- py -3 -m pytest scripts/rdc_analyzer/tests -q -rs -p no:cacheprovider (Expected: PASS, no warnings)
- Gate-1 chain (from WORK_SUMMARY_VERIFICATION.md):
  - py -3 scripts/rdc_analyzer/rdc_parser.py 'D:/backup/EndfieldTBeta2_2025.12.18_14.36_frame42231.rdc' --chunk-counts (Expected: chunk counts printed)
  - py -3 scripts/rdc_analyzer/analyze_rdc.py 'D:/backup/EndfieldTBeta2_2025.12.18_14.36_frame42231.rdc' --json 'D:/backup/EndfieldTBeta2_2025.12.18_14.36_frame42231_data.json' -o 'D:/backup/EndfieldTBeta2_2025.12.18_14.36_frame42231_report_lite_tmp.html' (Expected: HTML created)
  - py -3 scripts/rdc_analyzer/analyze_rdc.py 'D:/backup/EndfieldTBeta2_2025.12.18_14.36_frame42231.rdc' --html-mode full -o 'D:/backup/EndfieldTBeta2_2025.12.18_14.36_frame42231_report_full.html' (Expected: HTML created)
- Bundle HTML chain:
  - 
renderdoccmd.exe convert -c xml -o '<CAPTURE>.xml' '<CAPTURE>.rdc' (Expected: XML created)
  - py -3 scripts/rdc_analyzer/xml_to_bundle.py '<CAPTURE>.xml' -o '<OUT_DIR>' (Expected: index/events/textures/shaders + manifest.json)
- Headless HTML review (if script exists):
  - pwsh -File scripts/_tmp_html_ui_review_cdp.ps1 -Html '<ABS_HTML>' -OutDir 'docs/analysis/codex_rdc_analyzer/html_review' -LogFile 'edge_log' (Expected: run_YYYY... folder with screenshots/logs)

**Evidence:**
- docs/analysis/codex_rdc_analyzer/2026-02-17-p0p1p2-verification.md
- docs/analysis/codex_rdc_analyzer/html_review/ (if headless review used)
- Output HTML/JSON/log files in sample directory

**Estimation:**
- Effort: 1.5-2.5h (depends on sample availability)
- Story Points: 2
- Original Estimate: 2h

**Risk Register (impact/likelihood/mitigation):**
| Risk | Impact | Likelihood | Mitigation |
|---|---|---|---|
| Real RDC sample not available | High | Medium | Use user-provided sample path |
| renderdoccmd missing | High | Medium | Verify 
renderdoccmd.exe exists before running convert |
| User request  no commits conflicts with project rule | Medium | Medium | Treat as blocker and ask for explicit resolution before /do |
| Headless review script missing or requires GUI | Medium | Medium | Record manual review notes and mark as partial evidence |

## Game Dev: Memory & Resource Budget (Leak Checks)
- Not in scope for verification-only tasks; if needed, use OS perf tools to monitor RAM/VRAM during replay and record deltas.

## Game Dev: Asset Pipeline
- Verification uses existing capture assets; no asset build pipeline changes planned.

## Game Dev: Crash Repro + Dumps/Symbols
- Repro steps: record exact command and sample path.
- Dump/Core: not expected; if crash occurs, capture minidump/core as available.
- Symbols: use existing PDB/ELF if provided by environment.
- Build identity: record git commit hash in report if a crash occurs.

---

## Scope
- Verify P0/P1/P2 end-to-end using executable commands and document evidence.
- Do not modify core code unless verification fails and user approves fixes.

## Assumptions
- py -3 is available and required (system python may be 2.7).
- A valid RDC sample exists (preferred: user-provided sample path).
- Build/compile commands are not run without explicit approval.

## Repo / File List (with line ranges)
- docs/analysis/codex_rdc_analyzer/WORK_SUMMARY_ROADMAP.md:11-39 (P0/P1/P2 roadmap items)
- docs/analysis/codex_rdc_analyzer/WORK_SUMMARY_VERIFICATION.md:178-485 (Gate-1 + HTML review commands)
- docs/analysis/codex_rdc_analyzer/TASK_TRACKER.md:14-66 (Phase completion summary)
- docs/analysis/codex_rdc_analyzer/2026-02-17-p0p1p2-verification.md (update with results, new or existing)
- plans/2026-02-17-152600-Agent02-P0P1P2-EndToEnd-Verification.md (this plan)

## Approach (Pseudo-code)
``
select sample_rdc
assert renderdoccmd exists
run pytest (p0 schema)
run pytest (full suite, warnings)
run Gate-1 chain (chunk-counts, lite HTML, full HTML)
convert rdc -> xml -> bundle HTML
run headless or manual HTML review
append evidence to verification report
if mismatch -> stop and return to /plan for fixes
`

## Build/Test/Lint Quick Guide (commands only, do not execute here)
- py -3 -m pytest scripts/rdc_analyzer/tests/test_dod_compliance.py::TestVerificationPlanSchema -v
- py -3 -m pytest scripts/rdc_analyzer/tests -q -rs -p no:cacheprovider
- py -3 scripts/rdc_analyzer/rdc_parser.py '<RDC>' --chunk-counts
- py -3 scripts/rdc_analyzer/analyze_rdc.py '<RDC>' --json '<RDC>_data.json' -o '<RDC>_report_lite_tmp.html'
- py -3 scripts/rdc_analyzer/analyze_rdc.py '<RDC>' --html-mode full -o '<RDC>_report_full.html'
- 
renderdoccmd.exe convert -c xml -o '<CAPTURE>.xml' '<CAPTURE>.rdc'
- py -3 scripts/rdc_analyzer/xml_to_bundle.py '<CAPTURE>.xml' -o '<OUT_DIR>'
- pwsh -File scripts/_tmp_html_ui_review_cdp.ps1 -Html '<ABS_HTML>' -OutDir 'docs/analysis/codex_rdc_analyzer/html_review' -LogFile 'edge_log'

## Task Checklist (2-5 min each)

### Task 1: Locate sample(s) and renderdoccmd
**Files:**
- Modify: docs/analysis/codex_rdc_analyzer/2026-02-17-p0p1p2-verification.md (add sample + env section)

**Step 1: Find RDC samples (preferred)**
- Run: es.exe *.rdc
- Expected: list of RDC files (pick one)
- Fallback: 
g --files -g '*.rdc'

**Step 2: Confirm renderdoccmd exists**
- Run: 
g --files -g 'rrenderdoccmd.exe'
- Expected: at least one path (record it)

**Step 3: Record sample + tool paths in report**
`
## Environment
- sample_rdc: <ABS_PATH>
- renderdoccmd: <ABS_PATH>
`

### Task 2: P0-NEW-3 schema test (pytest)
**Files:**
- Modify: docs/analysis/codex_rdc_analyzer/2026-02-17-p0p1p2-verification.md

**Step 1: Run schema test**
- Run: py -3 -m pytest scripts/rdc_analyzer/tests/test_dod_compliance.py::TestVerificationPlanSchema -v
- Expected: PASS (exit code 0)

**Step 2: Record output**
`
### P0-NEW-3
- cmd: py -3 -m pytest scripts/rdc_analyzer/tests/test_dod_compliance.py::TestVerificationPlanSchema -v
- result: PASS
`

### Task 3: P1-NEW-2 warnings cleanup (full pytest)
**Files:**
- Modify: docs/analysis/codex_rdc_analyzer/2026-02-17-p0p1p2-verification.md

**Step 1: Run full tests**
- Run: py -3 -m pytest scripts/rdc_analyzer/tests -q -rs -p no:cacheprovider
- Expected: PASS, no warnings summary

**Step 2: Record output**
`
### P1-NEW-2
- cmd: py -3 -m pytest scripts/rdc_analyzer/tests -q -rs -p no:cacheprovider
- result: PASS (no warnings)
`

### Task 4: Gate-1 3-command chain (end-to-end)
**Files:**
- Modify: docs/analysis/codex_rdc_analyzer/2026-02-17-p0p1p2-verification.md

**Step 1: Chunk counts**
- Run: py -3 scripts/rdc_analyzer/rdc_parser.py '<RDC>' --chunk-counts
- Expected: chunk counts printed

**Step 2: Lite HTML**
- Run: py -3 scripts/rdc_analyzer/analyze_rdc.py '<RDC>' --json '<RDC>_data.json' -o '<RDC>_report_lite_tmp.html'
- Expected: lite HTML created

**Step 3: Full HTML**
- Run: py -3 scripts/rdc_analyzer/analyze_rdc.py '<RDC>' --html-mode full -o '<RDC>_report_full.html'
- Expected: full HTML created

**Step 4: Record outputs**
`
### Gate-1
- chunk_counts: <PATH>
- lite_html: <PATH>
- full_html: <PATH>
`

### Task 5: Bundle HTML chain (renderdoccmd + xml_to_bundle)
**Files:**
- Modify: docs/analysis/codex_rdc_analyzer/2026-02-17-p0p1p2-verification.md

**Step 1: Convert RDC to XML**
- Run: 
renderdoccmd.exe convert -c xml -o '<CAPTURE>.xml' '<CAPTURE>.rdc'
- Expected: XML created

**Step 2: Generate bundle**
- Run: py -3 scripts/rdc_analyzer/xml_to_bundle.py '<CAPTURE>.xml' -o '<OUT_DIR>'
- Expected: index/events/textures/shaders + manifest.json

**Step 3: Verify outputs (python snippet)**
`python
from pathlib import Path
out_dir = Path(r'<OUT_DIR>')
required = ['index.html', 'events.html', 'textures.html', 'shaders.html', 'manifest.json']
missing = [f for f in required if not (out_dir / f).exists()]
assert not missing, f'Missing: {missing}'
print('bundle_ok')
`

### Task 6: Headless HTML review (if available)
**Files:**
- Modify: docs/analysis/codex_rdc_analyzer/2026-02-17-p0p1p2-verification.md

**Step 1: Run headless review**
- Run: pwsh -File scripts/_tmp_html_ui_review_cdp.ps1 -Html '<ABS_HTML>' -OutDir 'docs/analysis/codex_rdc_analyzer/html_review' -LogFile 'edge_log'
- Expected: run_YYYY... folder with screenshots/logs

**Step 2: Record evidence**
`
### P1-NEW-3
- html_review_dir: <PATH>
- notes: <manual or script output>
`

### Task 7: Consolidate verification report
**Files:**
- Modify: docs/analysis/codex_rdc_analyzer/2026-02-17-p0p1p2-verification.md

**Step 1: Add summary table**
`
## Summary
| Item | Result | Evidence |
|---|---|---|
| P0-NEW-3 | PASS/FAIL | <path/cmd> |
| P1-NEW-2 | PASS/FAIL | <path/cmd> |
| P1-NEW-3 | PASS/FAIL | <path/cmd> |
| P2-renderdoccmd | PASS/FAIL | <path/cmd> |
| P2-Adreno | PASS/FAIL | <path/cmd> |
| P2-TileBased | PASS/FAIL | <path/cmd> |
`

### Task 8: Handle mismatches (if any)
**Files:**
- Potential modify: docs/analysis/codex_rdc_analyzer/TASK_TRACKER.md
- Potential modify: docs/analysis/codex_rdc_analyzer/WORK_SUMMARY_ROADMAP.md

**Step 1: If mismatch found**
- Stop and return to /plan for fixes and approvals.

## Risks & Blockers
- No commits request conflicts with project auto-commit rule (needs resolution before /do).
- Gate-1 sample path may not exist on this machine.
- Headless review script may be absent or require GUI.

## Decisions
- Option C selected: full end-to-end verification.

## Verification / DoD
- All commands listed in Verification Commands executed with expected outputs.
- Verification report updated with timestamps and evidence paths.

## Open Questions
- Sample path confirmed: D:/backup/EndfieldTBeta2_2025.12.18_14.36_frame42231.rdc
- Commit policy: ask user before each commit.

## Next Steps
- Await approval to proceed with /do and confirm sample path(s).


## Progress Log
- [x] Task 1: Located sample(s) and renderdoccmd (es.exe *.rdc; es.exe renderdoccmd.exe)
- [x] Task 2: P0-NEW-3 schema test PASS (pytest 4 passed)
- [!] Task 3: Full pytest FAIL at test_xml_to_bundle_vulkan_rt_mapping (expected depth_target == IMG_DEPTH)


## Plan Amendment: Fix test_xml_to_bundle_vulkan_rt_mapping (2026-02-17)

### Debug File List (with line ranges)
- scripts/rdc_analyzer/tests/test_xml_to_bundle_vulkan_rt_mapping.py:12-77
- scripts/rdc_analyzer/xml_to_bundle.py:96,519-532
- scripts/rdc_analyzer/analyze_xml_report.py:1290
- scripts/rdc_analyzer/parsers/rdc_xml_parser.py:92
- scripts/rdc_analyzer/core/rt_tracker.py:434-438

### Debug Approach (Pseudo-code)
`
read failing test expectations
trace depth_target from XML parser -> bundle output
compare actual output shape vs expected shape
form root-cause hypothesis with evidence
update code or test (only after evidence)
re-run failing test + full pytest
`

### Debug Task Checklist (2-5 min each)

#### Task D1: Capture evidence for expected vs actual
**Files:**
- Modify: docs/analysis/codex_rdc_analyzer/2026-02-17-p0p1p2-verification.md
- Read: scripts/rdc_analyzer/tests/test_xml_to_bundle_vulkan_rt_mapping.py:12-77

**Step 1: Re-run failing test only**
- Run: py -3 -m pytest scripts/rdc_analyzer/tests/test_xml_to_bundle_vulkan_rt_mapping.py::test_simple_xml_parser_tracks_vulkan_render_targets -v
- Expected: FAIL (current)

**Step 2: Record exact failure line + assertion**

#### Task D2: Trace data shape in xml_to_bundle pipeline
**Files:**
- Read: scripts/rdc_analyzer/xml_to_bundle.py:96,519-532
- Read: scripts/rdc_analyzer/analyze_xml_report.py:1290
- Read: scripts/rdc_analyzer/parsers/rdc_xml_parser.py:92

**Step 1: Identify source of depth_target**
**Step 2: Identify transformation to depthTarget payload**
**Step 3: Document evidence chain**

#### Task D3: Decide correct schema + implement minimal fix
**Files:**
- Modify: scripts/rdc_analyzer/xml_to_bundle.py (or test file)

**Step 1: Update logic or test expectation based on evidence**
**Step 2: Run failing test**
**Step 3: Run full pytest**
**Step 4: Commit (after asking user)**

### Impact Analysis
- Potentially changes bundle schema for depth_target; risk to downstream consumers.
- If test expectation is outdated, update test to match current schema and document change.

### Risks & Blockers (Amendment)
- Root cause may be schema drift between XML parser and bundle exporter.
- Need explicit user approval before any commit.
- [x] Task 4: Gate-1 chain PASS (chunk-counts + lite/full HTML)
- [x] Task 5: renderdoccmd convert + xml_to_bundle PASS (bundle generated)
- [x] Task 6: Headless review PASS (bundle external data supported; content_ok=True)

## Progress Updates (2026-02-19)
- [x] TDD: add `scripts/_tmp_html_review_tdd_test.py` and run RED on bundle events.html (content_ok false).
- [x] Update `scripts/_tmp_html_ui_review_cdp.ps1` to load external bundle data (events/textures/shaders) with awaitPromise.
- [x] Re-run TDD test GREEN on bundle events.html (content_ok true).
- [x] Update verification report: P1-NEW-3 headless review PASS with bundle-compatible logic.

## Deviations / Notes
- Plan originally allowed manual review fallback for headless HTML; chose to fix the script to keep evidence automated.

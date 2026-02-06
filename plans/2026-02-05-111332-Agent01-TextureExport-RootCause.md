# Texture Export Failure Root Cause Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Version:** 2026.02.05
**Owner:** Agent01 (Codex)
**Last Updated:** 2026-02-05
**Plan File:** `plans/2026-02-05-111332-Agent01-TextureExport-RootCause.md`

**Goal:** Identify the concrete root cause of “texture export always fails” with an evidence-backed diagnosis and a minimal fix (if needed).

**Architecture:** Treat texture export as two independent pipelines (GPU replay vs XML+ZIP offline). Collect logs per pipeline, verify prerequisites, isolate the failing stage, then apply the smallest code/usage correction.

**Tech Stack:** Python (rdc_analyzer), RenderDoc CLI/SDK, pytest, PowerShell.

**Success Criteria (measurable):**
- We can state a single root cause with direct evidence (log line + file/line reference).
- We can reproduce the failure (or confirm it was not a failure) with a deterministic command.
- If a fix is needed, the same command succeeds after the fix.

**Acceptance Criteria:**
- A log excerpt pinpoints the failure stage (module missing / local replay unsupported / ZIP assets missing / decoder missing / decode error).
- A clear remediation or usage correction is documented.

**Verification Commands:**
- `py -3 -m rdc_analyzer analyze "<rdc_path>" -o "<out_dir>"` (Expected: logs show success or a specific failure stage)
- `py -3 scripts/rdc_analyzer/analyze_xml_report.py "<xml_path>" -o "<out_dir>\\report.html" --ui-version bundle` (Expected: `[Texture Export]` summary line present)
- `py -3 scripts/rdc_analyzer/export_textures.py "<rdc_path>" -o "<out_dir>\\textures"` (Expected: TextureExporter logs, or explicit failure reason)

**Evidence:**
- `scripts/rdc_analyzer/run_log.txt`
- Output dir logs and manifest: `<out_dir>\\textures\\` + `<out_dir>\\manifest.json`
- Console output from commands above

**Estimation:**
- Effort: 1–2 hours
- Story Points: 2
- Original Estimate: 1.5 hours

**Risk Register (impact/likelihood/mitigation):**
- GPU replay unsupported (High/Medium) → fall back to XML+ZIP path + document limitations.
- Missing ZIP assets for XML route (High/Medium) → verify `.zip`/`*_assets` presence; re-export if missing.
- Decoder unavailable (Medium/Low) → log the dependency and provide a supported export format or path.

## Game Dev: Memory & Resource Budget (Leak Checks)
- No runtime leak changes; focus on batch export size and disk usage.

## Game Dev: Asset Pipeline
- Verify ZIP/assets co-location with XML and naming conventions.

## Game Dev: Crash Repro + Dumps/Symbols
- If native crash occurs during replay export, capture repro steps and keep logs with build id.

## Scope
**In scope**
- Inspect task logs and export pipeline logs.
- Determine which pipeline fails and why.
- Provide minimal fix or corrected usage path.

**Out of scope**
- Large refactor of exporters.
- Performance optimization beyond minimal diagnosis.

## Assumptions
- Failing case is reproducible with a specific command and input.
- Export logs are accessible in console or `run_log.txt`.

## Repo / File List (line ranges)
- `scripts/rdc_analyzer/export_textures.py:165-240` (GPU replay export path)
- `scripts/rdc_analyzer/analyze_xml_report.py:1860-1935` (XML+ZIP export path)
- `scripts/rdc_analyzer/exporters/texture_batch_exporter.py:148-260` (export_all + decode)
- `scripts/rdc_analyzer/run_log.txt` (task log)

## Approach (Pseudo-code)
1) Determine pipeline used by the failing run.
2) Collect logs and verify preconditions (renderdoc module, GPU replay support, ZIP assets).
3) Map failure to a single stage and confirm via minimal repro.
4) Apply the smallest fix or usage correction and re-run.

## Build/Test/Lint Quick Guide
- `py -3 -m pytest scripts/rdc_analyzer/tests/test_bundle_report_assets.py -v --tb=short`

## Decisions
- Root cause must be evidenced by log + code location.
- Prefer usage correction over code change unless code is clearly wrong.

## Task Checklist (2-5 min each, TDD-style)
- [x] **Write failing repro script (baseline).**
  - Create `scripts/_tmp_texture_export_probe.py` to run one pipeline and print a tagged summary.
  - Code:
    ```python
    from pathlib import Path
    import subprocess, sys

    rdc = r"<rdc_path>"
    out_dir = Path(r"<out_dir>")
    out_dir.mkdir(parents=True, exist_ok=True)

    cmd = ["py", "-3", "scripts/rdc_analyzer/export_textures.py", rdc, "-o", str(out_dir / "textures")]
    print("[PROBE] CMD:", " ".join(cmd))
    sys.exit(subprocess.call(cmd))
    ```
- [x] **Run baseline repro and capture failure.**
  - Command:
    ```bash
    py -3 scripts/_tmp_texture_export_probe.py
    ```
- [x] **Identify failing stage from logs.**
  - Inspect:
    - `scripts/rdc_analyzer/run_log.txt`
    - Console output of the probe
    - `<out_dir>\textures\` and `<out_dir>\manifest.json`
- [x] **Apply minimal fix or usage correction.**
  - Examples (choose one based on evidence):
    - If `renderdoc module not available` → switch to XML+ZIP route.
    - If `Local replay not supported` → use compatible GPU or software replay.
    - If ZIP missing → re-export XML+ZIP assets.
    - If `Decoder not available` → confirm decoder dependency.
  - Outcome: Headless run hits explicit `renderdoc module not available` and cannot proceed without
    RenderDoc Python bindings or RenderDoc UI Python Shell. (Usage correction recorded below.)
- [x] **Implement auto ZIP+XML conversion for headless route.**
  - Added renderdoccmd auto-discovery + RDC→ZIP+XML conversion in `analyze_xml_report.py`.
  - Fixed renderdoccmd CLI flags (`-f`, `-o`) after first failure.
- [ ] **Re-run probe to confirm success.**
  - Command:
    ```bash
    py -3 scripts/_tmp_texture_export_probe.py
    ```
  - Result: full headless report generation started; long-running export in progress.
- [ ] **Commit (if code changed).**
  - Template:
    ```bash
    git add <files>
    git commit -m "fix(rdc-analyzer): explain/fix texture export failure

    - root-cause log evidence
    - minimal fix or usage correction"
    ```

## Verification / Acceptance (Definition of Done)
- Repro command succeeds or produces a single explicit, documented failure reason.
- Root cause summarized with file/line evidence.

## Next Steps
- If failure is environmental, add a short README note for the chosen route.

## Blockers / Findings (Current)
- Headless `export_textures.py` fails because `renderdoc` resolves to a namespace package from
  the repo source tree (no Python bindings). This triggers the script-level guard and aborts.
- No XML/ZIP assets found for `EndfieldTBeta2_2025.12.18_14.36_frame42231` in `D:\backup`,
  so the no-GPU ZIP+XML extraction path cannot proceed without generating assets.
- `renderdoccmd.exe` is not on PATH in this environment (needs install/path or explicit location).
- `renderdoccmd convert` on this machine requires `-f`/`-o` flags (positional args rejected).
- Full ZIP+XML export for Endfield produced `~1.09 GB` zip; report generation may take minutes.

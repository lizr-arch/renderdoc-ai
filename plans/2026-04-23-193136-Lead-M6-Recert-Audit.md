# Plan: Lead / M6 Recert Audit

Time: 2026-04-23 19:31:36 | Owner: Lead

## Scope / Assumptions

- Goal:
  - audit the current `M6` compare/CI state against the released mainline,
  - distinguish validated compare capabilities from remaining recert gaps,
  - record the minimum next steps before `M6` can be called fully re-certified.
- Released mainline is `renderdoc-ai/main@cae519d0d814dc2da24843408768fbb8d22e8673`.
- Historical integration reference remains `codex/integration/renderdoc-ai-20260311@a961caccec5fef47f5d78cb165dc96347d5c0706`.
- This is a read-heavy control audit. No business code is changed in this document.

## Main Findings

- `M6` core assets are present on mainline:
  - `scripts/rdc_analyzer/compare_rdc.py`
  - `scripts/rdc_analyzer/parsers/snapshot_compare_adapter.py`
  - `scripts/rdc_analyzer/diff/junit_exporter.py`
  - compare-focused tests:
    - `test_snapshot_compare_adapter.py`
    - `test_compare_rdc.py`
    - `test_compare_ci.py`
    - `test_junit_exporter.py`
- Current mainline test evidence is green for the focused `M6` surface:
  - `test_snapshot_compare_adapter.py` -> `3 passed`
  - `test_compare_rdc.py` -> `14 passed`
  - `test_compare_ci.py` -> `3 passed`
  - `test_junit_exporter.py` -> `20 passed`
- Standalone compare CLI is functionally working:
  - `compare_rdc.py --help` exposes:
    - `--json`
    - `--junit`
    - exit codes `0/1/2/3`
  - a real smoke run against two temporary `snapshot.v1` payloads:
    - wrote `compare.json`
    - wrote `compare.junit.xml`
    - returned `exit code 2`
    - emitted `status=critical`
- Package compare entry is now functionally working on the current checkout:
  - `python -m rdc_analyzer compare ... --json --junit-xml ...`
  - current smoke result:
    - wrote `pkg.compare.json`
    - wrote `pkg.compare.junit.xml`
    - returned `exit code 2`
    - printed `status=critical exit_code=2`
- The previously observed package-wrapper drift was confirmed and then fixed in:
  - `scripts/rdc_analyzer/__main__.py`
  - root cause:
    - package entry was still calling `export_json_diff(...)` using the old signature and mixing compare types across module identities.

## What Is Already Validated

- `snapshot.v1 -> CaptureData` adapter path works.
- `compare_rdc.py` can compare `snapshot.v1` inputs.
- `compare_rdc.py` can export:
  - JSON diff
  - JUnit XML
- compare CI verdict generation works and returns non-zero exit codes for regressions.
- direct compare smoke evidence:
  - `compare.json` includes:
    - `compat_mode = snapshot_aliases`
    - `status = critical`
    - `exit_code = 2`
  - `compare.junit.xml` contains:
    - `<testsuite ...>`
    - `<testcase ...>`
    - `<failure ...>`
    - `<error ...>`
- package-entry compare smoke evidence:
  - `pkg.compare.json` includes:
    - `compat_mode = snapshot_aliases`
    - `status = critical`
    - `exit_code = 2`
  - `pkg.compare.junit.xml` exists and contains:
    - `<testsuite ...>`
    - `<failure ...>`
    - `<error ...>`

## Open Gaps After Current-Cycle Recert

- `G1`: broad compare-related pytest invocation needs care
  - running a broad filtered collection from `scripts/rdc_analyzer` using:
    - `py -3 -m pytest ... -k "compare or junit_exporter or snapshot_compare_adapter"`
  - surfaced unrelated import-collection errors in:
    - `tests/test_issue_detector.py`
    - `tests/test_report_ui.py`
  - this is not evidence that `M6` itself is broken,
  - but it means the recert command set should stay targeted until test-package import boundaries are cleaned up.

## Minimum Next Steps

- `S1`: keep the package compare wrapper aligned with the compare core contract.
- `S2`: keep the recert command set targeted until broad compare-related pytest collection is cleaned up.
- `S3`: if broad-suite hygiene becomes a release requirement, isolate and fix the unrelated import-collection failures in:
  - `tests/test_issue_detector.py`
  - `tests/test_report_ui.py`

## Audit Evidence

- Current SHAs:
  - `git -C D:\Code\git\renderdoc ls-remote renderdoc-ai refs/heads/main`
    - `cae519d0d814dc2da24843408768fbb8d22e8673 refs/heads/main`
  - `git -C D:\Code\git\renderdoc rev-parse codex/integration/renderdoc-ai-20260311`
    - `a961caccec5fef47f5d78cb165dc96347d5c0706`
- compare core anchors:
  - `scripts/rdc_analyzer/compare_rdc.py`
    - `run_comparison`
    - `export_json_diff`
    - `export_junit_report`
    - `main`
  - `scripts/rdc_analyzer/__main__.py`
    - compare parser with `--junit-xml`
    - `cmd_compare()`
- focused test evidence:
  - `py -3 -m pytest D:\Code\git\renderdoc\scripts\rdc_analyzer\tests\test_snapshot_compare_adapter.py -q`
    - `3 passed`
  - `py -3 -m pytest D:\Code\git\renderdoc\scripts\rdc_analyzer\tests\test_compare_rdc.py -q`
    - `14 passed`
  - `py -3 -m pytest D:\Code\git\renderdoc\scripts\rdc_analyzer\tests\test_compare_ci.py -q`
    - `3 passed`
  - `py -3 -m pytest D:\Code\git\renderdoc\scripts\rdc_analyzer\tests\test_junit_exporter.py -q`
    - `20 passed`
- standalone compare smoke:
  - baseline:
    - `C:\Users\lizhirui01\AppData\Local\Temp\renderdoc_compare_smoke\baseline.snapshot.json`
  - target:
    - `C:\Users\lizhirui01\AppData\Local\Temp\renderdoc_compare_smoke\target.snapshot.json`
  - outputs:
    - `C:\Users\lizhirui01\AppData\Local\Temp\renderdoc_compare_smoke\compare.json`
    - `C:\Users\lizhirui01\AppData\Local\Temp\renderdoc_compare_smoke\compare.junit.xml`
  - result:
    - `status=critical`
    - `exit_code=2`
- package CLI failure:
  - previous failure:
    - `export_json_diff() missing 3 required positional arguments: 'baseline_data', 'target_data', and 'ci_verdict'`
  - repaired package-entry smoke:
    - command:
      - `py -3 -m rdc_analyzer compare C:\Users\lizhirui01\AppData\Local\Temp\renderdoc_compare_smoke\baseline.snapshot.json C:\Users\lizhirui01\AppData\Local\Temp\renderdoc_compare_smoke\target.snapshot.json --json C:\Users\lizhirui01\AppData\Local\Temp\renderdoc_compare_smoke\pkg.compare.json --junit-xml C:\Users\lizhirui01\AppData\Local\Temp\renderdoc_compare_smoke\pkg.compare.junit.xml -q`
    - result:
      - `exit code 2`
      - output files exist
      - package entry reaches the same `critical` verdict as standalone compare

## Task Checklist

- [x] T1: verify compare core files exist on mainline.
- [x] T2: rerun focused `M6` tests on current checkout.
- [x] T3: verify standalone compare CLI behavior on current checkout.
- [x] T4: verify package compare entry behavior on current checkout.
- [x] T5: record the smallest remaining `M6` closure gap.

## Risks / Blockers

- The package compare wrapper drift is fixed on released mainline, but future edits must keep wrapper and compare core signatures aligned.
- Broad compare-related pytest commands can be noisy because unrelated tests fail collection under current import assumptions.
- The current recommended recert path should stay targeted and explicit until the package entry and collection surface are aligned.

## Verification / Acceptance

- Definition of Done for this audit document:
  - [x] focused `M6` tests are re-run on current checkout,
  - [x] standalone compare CLI is re-run with real artifacts,
  - [x] package compare entry is explicitly checked and repaired,
  - [x] one explicit current-cycle golden recert record is added,
  - [x] remaining `M6` gap is reduced to broad-suite hygiene only.

## 2026-04-23 Candidate Update

- A fresh candidate worktree was created from released mainline:
  - `D:\Code\git\renderdoc-m6-fix`
  - base: `renderdoc-ai/main@cae519d0d814dc2da24843408768fbb8d22e8673`
  - candidate branch: `codex/lead/m6-compare-wrapper-fix`
  - candidate commit: `7d4ae1e89e967aa32433da68e946cc9ab2db4e7d`
- Candidate diff against released mainline is intentionally minimal:
  - `scripts/rdc_analyzer/__main__.py`
  - `scripts/rdc_analyzer/tests/test_compare_rdc.py`
- Re-verified in the clean candidate worktree:
  - `py -3 -m py_compile D:\Code\git\renderdoc-m6-fix\scripts\rdc_analyzer\__main__.py D:\Code\git\renderdoc-m6-fix\scripts\rdc_analyzer\tests\test_compare_rdc.py`
  - `py -3 -m pytest D:\Code\git\renderdoc-m6-fix\scripts\rdc_analyzer\tests\test_snapshot_compare_adapter.py -q`
    - `3 passed`
  - `py -3 -m pytest D:\Code\git\renderdoc-m6-fix\scripts\rdc_analyzer\tests\test_compare_rdc.py -q`
    - `15 passed`
  - `py -3 -m pytest D:\Code\git\renderdoc-m6-fix\scripts\rdc_analyzer\tests\test_compare_ci.py -q`
    - `3 passed`
  - `py -3 -m pytest D:\Code\git\renderdoc-m6-fix\scripts\rdc_analyzer\tests\test_junit_exporter.py -q`
    - `20 passed`
- Package-entry smoke in the clean worktree requires the documented import path configuration:
  - `D:\Code\git\renderdoc-m6-fix\scripts\rdc_analyzer\README.md`
  - evidence anchors:
    - `README.md:207`
    - `README.md:210`
  - command:
    - `$env:PYTHONPATH='D:\Code\git\renderdoc-m6-fix\scripts'; py -3 -m rdc_analyzer compare ... --json ... --junit-xml ... -q`
  - result:
    - exit code `2`
    - `pkg.compare.json` contains `compat_mode=snapshot_aliases`, `status=critical`, `exit_code=2`
    - `pkg.compare.junit.xml` contains `<testsuite>`, `<failure>`, `<error>`
- Current closure statement:
  - wrapper drift is repaired and isolated in a clean candidate SHA,
  - at that candidate stage, the remaining `M6` gap was one current-cycle golden recert record plus broad-suite hygiene.

## 2026-04-23 Main-Merge Verification Update

- Approved candidate `7d4ae1e89e967aa32433da68e946cc9ab2db4e7d` was cherry-picked into:
  - `D:\Code\git\renderdoc-main-merge`
  - merge branch: `codex/main-gate5-merge-20260423`
  - merge-worktree commit: `5f0c1ca11f586970c2690f8f01cae94a9ef9acd6`
- Post-cherry-pick diff against `renderdoc-ai/main` remains minimal:
  - `scripts/rdc_analyzer/__main__.py`
  - `scripts/rdc_analyzer/tests/test_compare_rdc.py`
- Pre-merge verification re-run in `D:\Code\git\renderdoc-main-merge`:
  - `py -3 -m py_compile D:\Code\git\renderdoc-main-merge\scripts\rdc_analyzer\__main__.py D:\Code\git\renderdoc-main-merge\scripts\rdc_analyzer\tests\test_compare_rdc.py`
  - `py -3 -m pytest D:\Code\git\renderdoc-main-merge\scripts\rdc_analyzer\tests\test_snapshot_compare_adapter.py -q`
    - `3 passed`
  - `py -3 -m pytest D:\Code\git\renderdoc-main-merge\scripts\rdc_analyzer\tests\test_compare_rdc.py -q`
    - `15 passed`
  - `py -3 -m pytest D:\Code\git\renderdoc-main-merge\scripts\rdc_analyzer\tests\test_compare_ci.py -q`
    - `3 passed`
  - `py -3 -m pytest D:\Code\git\renderdoc-main-merge\scripts\rdc_analyzer\tests\test_junit_exporter.py -q`
    - `20 passed`
  - `$env:PYTHONPATH='D:\Code\git\renderdoc-main-merge\scripts'; py -3 -m rdc_analyzer compare ... --json ... --junit-xml ... -q`
    - exit code `2`
    - `pkg.compare.json` keeps `compat_mode=snapshot_aliases`, `status=critical`, `exit_code=2`
    - `pkg.compare.junit.xml` keeps `<testsuite>`, `<failure>`, `<error>`
- Gate statement:
  - this candidate passed push review and was pushed after explicit user approval.

## 2026-04-23 Push Update

- Push command executed from:
  - `D:\Code\git\renderdoc-main-merge`
  - branch: `codex/main-gate5-merge-20260423`
  - pushed commit: `5f0c1ca11f586970c2690f8f01cae94a9ef9acd6`
- Push result:
  - `git -C D:\Code\git\renderdoc-main-merge push renderdoc-ai HEAD:refs/heads/main`
  - remote accepted:
    - `cae519d0d..5f0c1ca11  HEAD -> main`
- Remote verification:
  - `git -C D:\Code\git\renderdoc ls-remote renderdoc-ai refs/heads/main`
    - `5f0c1ca11f586970c2690f8f01cae94a9ef9acd6 refs/heads/main`
- Current state:
  - the `M6` package compare wrapper repair is now on released mainline,
  - the remaining program-level open items are outside this push:
    - `D` real-device evidence for `JDWPFailure`
    - `D` real-device evidence for `AndroidLayerConfFailed`

## 2026-04-23 Golden Recert Update

- Archived current-cycle golden recert evidence in:
  - `D:\Code\git\renderdoc\docs\debug\session_archives\2026-04-23-m6-golden-recert`
- Archived artifacts:
  - `baseline.snapshot.json`
  - `target.snapshot.json`
  - `standalone.compare.json`
  - `standalone.compare.junit.xml`
  - `package.compare.json`
  - `package.compare.junit.xml`
  - `command_summary.txt`
  - `README.md`
- Commands executed from `D:\Code\git\renderdoc-main-merge`:
  - `py -3 ...\compare_rdc.py <baseline> <target> --json <standalone.compare.json> --junit <standalone.compare.junit.xml> -q`
  - `$env:PYTHONPATH='D:\Code\git\renderdoc-main-merge\scripts'; py -3 -m rdc_analyzer compare <baseline> <target> --json <package.compare.json> --junit-xml <package.compare.junit.xml> -q`
- Golden recert result:
  - `standalone_exit_code = 2`
  - `package_exit_code = 2`
  - both JSON artifacts keep:
    - `compat_mode = snapshot_aliases`
    - `status = critical`
    - `exit_code = 2`
  - both JUnit artifacts keep:
    - `tests = 9`
    - `failures = 5`
    - `errors = 1`
  - `git diff --no-index` confirms the only observed payload drift is timestamp metadata:
    - JSON: `metadata.generated_at`
    - JUnit XML: `<testsuite timestamp="...">`
- Closure statement:
  - `G1` current-cycle golden recert is now closed,
  - remaining `M6` open gap is `G2` broad-suite hygiene only.

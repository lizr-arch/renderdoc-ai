# Archive Summary - Gate Closure Only (2026-02-12)

## Archive Scope

This archive includes only the purpose-driven 5-Gate closure outputs:
- Gate-1 truthfulness closure (logic-level unblock + revalidation)
- Gate-2 regression gate pass
- Gate-3 schema/template contract consistency
- Gate-4 deterministic test behavior
- Gate-5 SSOT docs consistency

## Included Snapshot Files

- docs/analysis/codex_rdc_analyzer/GATE_ACCEPTANCE_REPORT_2026-02-11.md
- plans/2026-02-10-184349-Agent01-PurposeDriven-GateClosure.md
- docs/analysis/codex_rdc_analyzer/TASK_TRACKER.md
- docs/analysis/codex_rdc_analyzer/WORK_SUMMARY_ROADMAP.md
- docs/analysis/codex_rdc_analyzer/WORK_SUMMARY_VERIFICATION.md

All files are copied under `files/` with repository-relative paths preserved.

## Gate Result Snapshot

- Gate-1: pass_core_logic
- Gate-2: pass
- Gate-3: pass
- Gate-4: pass
- Gate-5: pass

Primary acceptance artifact:
- docs/analysis/codex_rdc_analyzer/GATE_ACCEPTANCE_REPORT_2026-02-11.md

## Relevant Commits (Gate Closure Track)

- 95046195c  fix(rdc-analyzer): restore Gate-1 parser/full-report execution paths
- 2e27e8707  docs(rdc-analyzer): sync Gate baselines and record Gate-1 revalidation
- 754dc035d  docs(plan): mark D3 complete after conventional commits
- 31e37acfc  docs(rdc-analyzer): add final five-gate acceptance report

## Explicitly Excluded From This Archive

To keep this archive strictly gate-focused, the following are excluded:
- One-click workflow feature/documentation commits
- Unrelated working tree modifications
- Generated test output folders and screenshots

## Reproduction Commands (Reference)

- `py -3 -m pytest scripts/rdc_analyzer/tests -q -rs -p no:cacheprovider`
- `py -3 scripts/rdc_analyzer/rdc_parser.py "D:\renderdoc\goog pixel-9\g145-battle-2.rdc" --chunk-counts`
- `py -3 scripts/rdc_analyzer/analyze_rdc.py "D:\renderdoc\goog pixel-9\g145-battle-2.rdc" --json "D:\renderdoc\goog pixel-9\g145-battle-2_data.json" -o "D:\renderdoc\goog pixel-9\g145-battle-2_report_lite_tmp.html"`
- `py -3 scripts/rdc_analyzer/analyze_rdc.py "D:\renderdoc\goog pixel-9\g145-battle-2.rdc" --html-mode full -o "D:\renderdoc\goog pixel-9\g145-battle-2_report_full.html"`

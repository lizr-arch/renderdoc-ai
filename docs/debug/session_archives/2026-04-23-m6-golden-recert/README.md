# 2026-04-23 M6 Golden Recert

## Scope

- Worktree used:
  - `D:\Code\git\renderdoc-main-merge`
- Released mainline at execution time:
  - `renderdoc-ai/main@5f0c1ca11f586970c2690f8f01cae94a9ef9acd6`
- Goal:
  - add one explicit current-cycle golden recert record for `M6`,
  - verify standalone compare and package compare agree on:
    - `JSON`
    - `JUnit`
    - `exit code`
    - golden sample stability

## Inputs

- `baseline.snapshot.json`
- `target.snapshot.json`

## Outputs

- `standalone.compare.json`
- `standalone.compare.junit.xml`
- `package.compare.json`
- `package.compare.junit.xml`
- `command_summary.txt`

## Commands

- Standalone compare:
  - `py -3 D:\Code\git\renderdoc-main-merge\scripts\rdc_analyzer\compare_rdc.py D:\Code\git\renderdoc\docs\debug\session_archives\2026-04-23-m6-golden-recert\baseline.snapshot.json D:\Code\git\renderdoc\docs\debug\session_archives\2026-04-23-m6-golden-recert\target.snapshot.json --json D:\Code\git\renderdoc\docs\debug\session_archives\2026-04-23-m6-golden-recert\standalone.compare.json --junit D:\Code\git\renderdoc\docs\debug\session_archives\2026-04-23-m6-golden-recert\standalone.compare.junit.xml -q`
- Package compare:
  - `$env:PYTHONPATH='D:\Code\git\renderdoc-main-merge\scripts'; py -3 -m rdc_analyzer compare D:\Code\git\renderdoc\docs\debug\session_archives\2026-04-23-m6-golden-recert\baseline.snapshot.json D:\Code\git\renderdoc\docs\debug\session_archives\2026-04-23-m6-golden-recert\target.snapshot.json --json D:\Code\git\renderdoc\docs\debug\session_archives\2026-04-23-m6-golden-recert\package.compare.json --junit-xml D:\Code\git\renderdoc\docs\debug\session_archives\2026-04-23-m6-golden-recert\package.compare.junit.xml -q`

## Result

- `standalone_exit_code=2`
- `package_exit_code=2`
- `standalone.compare.json` and `package.compare.json` are equivalent except:
  - `metadata.generated_at`
- `standalone.compare.junit.xml` and `package.compare.junit.xml` are equivalent except:
  - `<testsuite timestamp="...">`
- Shared semantic result:
  - `compat_mode = snapshot_aliases`
  - `status = critical`
  - `exit_code = 2`
  - JUnit summary:
    - `tests = 9`
    - `failures = 5`
    - `errors = 1`

## Conclusion

- The current-cycle `M6` golden sample recert is complete.
- Standalone compare and package compare agree on the golden sample outcome.
- Remaining `M6` work is reduced to non-functional compare-suite hygiene, not compare-core behavior.

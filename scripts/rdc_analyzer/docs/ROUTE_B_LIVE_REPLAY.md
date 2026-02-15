# Route-B Live Replay Runbook

This runbook documents how to preflight Route-B (ReplayController-based live replay)
and what to do when local replay is not available.

## 1) When to use

Use this before Route-B extraction to check replay viability:

```bash
py -3.6 scripts/rdc_analyzer/route_b_live_check.py <capture.rdc> --mode auto
```

The tool reports:
- local replay support (`Supported` / `SuggestRemote` / `Unsupported`)
- local/software/remote open-capture attempts
- structured JSON result with recommended actions

## 2) Prerequisites

- Python 3.6 (RenderDoc Python bindings are commonly built for this)
- `x64/Development` in `PATH`
- `x64/Development/pymodules` in `sys.path`
- optional remote RenderDoc server for remote mode

By default, the script injects repo-relative RenderDoc paths. Override with CLI args if needed.

## 3) Commands

### 3.1 Local / auto preflight

```bash
py -3.6 scripts/rdc_analyzer/route_b_live_check.py D:/captures/sample.rdc --mode auto --json-out route_b_report.json
```

### 3.2 Software replay attempt

```bash
py -3.6 scripts/rdc_analyzer/route_b_live_check.py D:/captures/sample.rdc --mode software --try-software
```

### 3.3 Remote replay

Start remote server on a compatible GPU host:

```bash
renderdoccmd remoteserver --listen 0.0.0.0 --port 39920
```

Then run preflight from local machine:

```bash
py -3.6 scripts/rdc_analyzer/route_b_live_check.py D:/captures/sample.rdc \
  --mode remote \
  --remote-url <host:39920> \
  --copy-to-remote
```

## 4) Status guide

Success:
- `ok_local`
- `ok_software`
- `ok_remote`

Common failures:
- `module_missing`
- `file_not_found`
- `needs_remote`
- `unsupported`
- `open_capture_failed`
- `remote_connect_failed`
- `remote_copy_failed`
- `remote_open_capture_failed`

## 5) Test integration

Opt-in live test:
- `scripts/rdc_analyzer/tests/test_resource_inspector.py::TestResourceInspectorReplay::test_route_b_live_preflight`
- marker: `routeb_live`

Manual run:

```bash
set RDC_ROUTE_B_LIVE=1
set RDC_ROUTE_B_SAMPLE_PATH=D:/captures/sample.rdc
py -3 -m pytest scripts/rdc_analyzer/tests/test_resource_inspector.py -m routeb_live -q
```

## 6) Fallback policy

If Route-B still fails:
1. Apply `recommended_actions` from JSON output.
2. Try remote replay on a compatible host.
3. If still blocked, continue with Route-A / Route-C and document the limitation.

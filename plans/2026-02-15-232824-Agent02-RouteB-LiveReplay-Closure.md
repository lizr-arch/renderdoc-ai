# Plan: Route-B Live Replay Closure (Preflight + Optional Remote/Software)

- Time: 2026-02-15 23:28:24
- Agent: Agent02
- Spec: docs/analysis/codex_rdc_analyzer/ROUTE_B_LIVE_REPLAY_SPEC.md
- Goal: make Route-B (ReplayController) reproducible via a preflight tool + opt-in tests + docs.

## Scope / Assumptions

### In scope
- Add a **Route-B preflight CLI tool** that:
  - sets up the correct RenderDoc Python environment (Python 3.6 + renderdoc.pyd + DLL PATH),
  - attempts local replay (and optionally software/remote replay),
  - outputs structured JSON + human summary,
  - classifies failures into actionable buckets.
- Convert replay-dependent tests from "always skip" to "opt-in pass/fail".
- Add documentation that gives the exact next actions when replay is not possible locally.

### Out of scope
- Not provisioning remote servers automatically.
- Not changing RenderDoc core replay logic in C++.
- Not expanding A/C routes (user says #1 already in progress).

### Key assumption
- Cross-vendor Vulkan replay is often impossible (e.g. Mali capture on Nvidia). The plan optimizes for:
  - fast diagnosis,
  - deterministic classification,
  - recommended routing (RemoteServer / Software / fallback).

## Navigation Evidence (Codemap First)

codemap queries (max 3):
1) codemap "scripts/rdc_analyzer/extractors/replay_wrapper.py SetFrameEvent GetPipelineState" -Num 20
2) codemap "test_resource_inspector live controller skip" -Num 20
3) codemap "OpenCaptureFile OpenCapture ReplayOptions" -Num 20

candidate hits (>=3):
- [renderdoc] scripts/rdc_analyzer/extractors/replay_wrapper.py:195
  - status, controller = self._cap.OpenCapture(rd.ReplayOptions(), None)
- [renderdoc] scripts/rdc_analyzer/extractors/replay_wrapper.py:314
  - self._controller.SetFrameEvent(event_id, True)
- [renderdoc] scripts/rdc_analyzer/extractors/replay_wrapper.py:336
  - state = self._controller.GetPipelineState(); return state.GetVulkan()
- [renderdoc] scripts/rdc_analyzer/tests/test_resource_inspector.py:290
  - skip: Requires RenderDoc Python environment with live controller
- [renderdoc] scripts/rdc_analyzer/rdc_to_html.py:250-257
  - checks LocalReplaySupport and calls cap.OpenCapture

follow-ups (1-2) and why:
- scripts/rdc_analyzer/extractors/replay_wrapper.py:171-206 (open capture decision point; currently treats SuggestRemote as replayable)
- scripts/rdc_analyzer/tests/test_resource_inspector.py:233-315 (convert placeholder skip into opt-in reproducible live test)

next step:
- OpenGrok xref:
  - http://127.0.0.1:8080/source/xref/renderdoc/scripts/rdc_analyzer/extractors/replay_wrapper.py#171
  - http://127.0.0.1:8080/source/xref/renderdoc/scripts/rdc_analyzer/tests/test_resource_inspector.py#233

## File List (targets)

New:
- scripts/rdc_analyzer/route_b_live_check.py (new CLI tool, ~250-400 lines)
- scripts/rdc_analyzer/tests/test_route_b_live_check_unit.py (unit tests, no renderdoc dependency)
- scripts/rdc_analyzer/docs/ROUTE_B_LIVE_REPLAY.md (user-facing runbook)

Modify:
- scripts/rdc_analyzer/tests/test_resource_inspector.py:233-315
  - fix LocalReplaySupport boolean misuse
  - add opt-in routeb_live test path
- scripts/rdc_analyzer/pytest.ini:1-30
  - register new marker: routeb_live
- scripts/rdc_analyzer/docs/INDEX.md (add link entry)

Optional (only if needed after tool exists):
- scripts/rdc_analyzer/extractors/replay_wrapper.py:171-206
  - improve error classification and guidance for SuggestRemote

## Design (Pseudo-code + full code snippets)

### 1) Tool API surface

- Primary CLI:
  - py -3.6 scripts/rdc_analyzer/route_b_live_check.py <capture.rdc> [--mode auto|local|software|remote]
  - outputs: human summary to stdout + optional --json output path

- Key env/flags:
  - --renderdoc-bin-dir (defaults to x64/Development relative to repo)
  - --renderdoc-pymodules-dir (defaults to x64/Development/pymodules)
  - --remote-url (optional, host:port)
  - --copy-to-remote (bool, default true when remote mode)
  - --software (shortcut for --mode software)

### 2) Output JSON contract (v1)

```json
{
  "schema_version": "1.0",
  "input": {"rdc_path": "...", "mode": "auto"},
  "env": {
    "python": {"version": "3.6.x", "exe": "..."},
    "renderdoc": {"import_ok": true, "pyd_path": "..."}
  },
  "local": {
    "open_file": "Succeeded",
    "local_replay_support": "Supported|SuggestRemote|Unsupported",
    "open_capture": {"result": "Succeeded|...", "message": "..."}
  },
  "remote": {
    "attempted": false,
    "url": null,
    "copy_to_remote": null,
    "open_capture": null
  },
  "software": {"attempted": false, "open_capture": null},
  "final": {
    "status": "ok|needs_remote|needs_software|unsupported|module_missing|error",
    "recommended_actions": ["..."]
  }
}
```

### 3) Core implementation sketch (complete snippet)

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple


def _prepend_env_path(dir_path: str) -> None:
    if not dir_path:
        return
    cur = os.environ.get('PATH', '')
    if dir_path not in cur.split(os.pathsep):
        os.environ['PATH'] = dir_path + os.pathsep + cur


def configure_renderdoc_env(bin_dir: str, pymodules_dir: str) -> None:
    # renderdoc.pyd depends on renderdoc.dll and python36.dll in bin_dir
    _prepend_env_path(bin_dir)
    if pymodules_dir and pymodules_dir not in sys.path:
        sys.path.insert(0, pymodules_dir)


def import_renderdoc() -> Tuple[bool, Optional[Any], str]:
    try:
        import renderdoc as rd  # type: ignore
        return True, rd, getattr(rd, '__file__', '')
    except Exception as e:
        return False, None, str(e)


def classify_local_support(rd: Any, support: Any) -> str:
    # support is rd.ReplaySupport enum
    try:
        if support == rd.ReplaySupport.Supported:
            return 'Supported'
        if support == rd.ReplaySupport.SuggestRemote:
            return 'SuggestRemote'
        if support == rd.ReplaySupport.Unsupported:
            return 'Unsupported'
    except Exception:
        pass
    return str(support)


def open_capture_local(rd: Any, rdc_path: str, replay_opts: Any) -> Dict[str, Any]:
    cap = rd.OpenCaptureFile()
    try:
        r = cap.OpenFile(rdc_path, '', None)
        out = {
            'open_file': str(r),
            'driver_name': getattr(cap, 'DriverName', lambda: '')(),
            'local_replay_support': None,
            'open_capture': None,
        }

        support = cap.LocalReplaySupport()
        out['local_replay_support'] = classify_local_support(rd, support)

        if support != rd.ReplaySupport.Supported:
            # do not attempt OpenCapture here; report needs remote/software
            out['open_capture'] = {'result': None, 'message': 'Local replay not supported'}
            return out

        result, controller = cap.OpenCapture(replay_opts, None)
        out['open_capture'] = {'result': str(result), 'message': str(result)}
        if result == rd.ResultCode.Succeeded:
            # minimal sanity checks
            try:
                roots = controller.GetRootActions()
                out['root_actions'] = len(roots)
            except Exception as e:
                out['root_actions_error'] = str(e)
            controller.Shutdown()
        return out
    finally:
        cap.Shutdown()


def open_capture_remote(rd: Any, rdc_path: str, remote_url: str, replay_opts: Any, copy_to_remote: bool) -> Dict[str, Any]:
    result, remote = rd.CreateRemoteServerConnection(remote_url)
    out: Dict[str, Any] = {'connect': str(result), 'url': remote_url}
    if result != rd.ResultCode.Succeeded:
        out['open_capture'] = None
        return out

    try:
        remote_path = rdc_path
        if copy_to_remote:
            copy_res = remote.CopyCaptureToRemote(rdc_path, None)
            out['copy_to_remote'] = str(copy_res)
            # CopyCaptureToRemote returns the remote path string. Use it for remote OpenCapture.
            remote_path = copy_res

        res, controller = remote.OpenCapture(rd.RemoteServer.NoPreference, remote_path, replay_opts, None)
        out['open_capture'] = {'result': str(res), 'message': str(res)}
        if res == rd.ResultCode.Succeeded:
            controller.Shutdown()
        return out
    finally:
        remote.ShutdownServerAndConnection()


def build_recommendations(local_support: str, local_open_capture_result: Optional[str]) -> Tuple[str, list]:
    actions = []
    if local_support == 'Supported' and local_open_capture_result == 'Succeeded':
        return 'ok', actions
    if local_support == 'SuggestRemote':
        actions.append('Start a compatible remote replay server (renderdoccmd remoteserver) and rerun with --remote-url')
        return 'needs_remote', actions
    if local_support == 'Unsupported':
        actions.append('Local replay unsupported. Use RemoteServer or offline routes (A/C).')
        return 'unsupported', actions
    actions.append('If this is a Vulkan capture, try --mode software (forceGPUVendor=Software) when available.')
    actions.append('Otherwise use offline routes (A/C) and record the limitation.')
    return 'error', actions


def main(argv: Optional[list] = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('rdc', help='Path to .rdc capture')
    ap.add_argument('--mode', choices=['auto', 'local', 'software', 'remote'], default='auto')
    ap.add_argument('--renderdoc-bin-dir', default=os.path.join('x64', 'Development'))
    ap.add_argument('--renderdoc-pymodules-dir', default=os.path.join('x64', 'Development', 'pymodules'))
    ap.add_argument('--remote-url', default=None)
    ap.add_argument('--copy-to-remote', action='store_true', default=False)
    ap.add_argument('--json', dest='json_out', default=None)

    ns = ap.parse_args(argv)

    configure_renderdoc_env(ns.renderdoc_bin_dir, ns.renderdoc_pymodules_dir)
    ok, rd, rd_info = import_renderdoc()

    report: Dict[str, Any] = {
        'schema_version': '1.0',
        'timestamp': time.strftime('%Y-%m-%dT%H:%M:%S'),
        'input': {'rdc_path': ns.rdc, 'mode': ns.mode},
        'env': {
            'python': {'version': sys.version, 'exe': sys.executable},
            'renderdoc': {'import_ok': ok, 'info': rd_info},
        },
    }

    if not ok or rd is None:
        report['final'] = {
            'status': 'module_missing',
            'recommended_actions': ['Run with py -3.6 and set PATH to x64/Development and sys.path to pymodules'],
        }
        _emit(report, ns.json_out)
        return 30

    rd.InitialiseReplay(rd.GlobalEnvironment(), [])
    try:
        opts = rd.ReplayOptions()
        report['local'] = open_capture_local(rd, ns.rdc, opts)

        local_support = report['local'].get('local_replay_support')
        open_capture_res = None
        if report['local'].get('open_capture'):
            open_capture_res = report['local']['open_capture'].get('result')

        # Optional remote attempt
        if ns.remote_url:
            report['remote'] = open_capture_remote(rd, ns.rdc, ns.remote_url, opts, ns.copy_to_remote)
        else:
            report['remote'] = {'attempted': False}

        status, actions = build_recommendations(local_support, open_capture_res)
        report['final'] = {'status': status, 'recommended_actions': actions}
        _emit(report, ns.json_out)

        return 0 if status == 'ok' else 10
    finally:
        rd.ShutdownReplay()


def _emit(report: Dict[str, Any], json_out: Optional[str]) -> None:
    s = json.dumps(report, indent=2, sort_keys=True)
    if json_out:
        with open(json_out, 'w', encoding='utf-8') as f:
            f.write(s + '\n')
    print(s)


if __name__ == '__main__':
    raise SystemExit(main())
```

Notes:
- Remote copy semantics in v1 will use the returned remote path from CopyCaptureToRemote and surface it in JSON output.
- Software replay path will be added in implementation by setting: `opts.forceGPUVendor = rd.GPUVendor.Software`.

## Task Checklist (2-5 minute steps)

- [x] T1: Identify and document the exact Route-B failure taxonomy used by the tool (Supported/SuggestRemote/Unsupported + OpenCapture error buckets).
- [x] T2: Create `scripts/rdc_analyzer/route_b_live_check.py` with:
  - [x] env bootstrap (PATH + sys.path)
  - [x] local OpenFile + LocalReplaySupport classification
  - [x] optional OpenCapture attempt gated by LocalReplaySupport == Supported
  - [x] optional software mode (forceGPUVendor=Software)
  - [x] optional remote mode (CreateRemoteServerConnection + CopyCaptureToRemote + OpenCapture)
  - [x] JSON output + stable exit codes
- [x] T3: Add unit tests `scripts/rdc_analyzer/tests/test_route_b_live_check_unit.py`:
  - [x] LocalReplaySupport classification mapping
  - [x] Recommendation routing
  - [x] JSON schema minimal validation (keys exist)
- [x] T4: Update pytest markers in `scripts/rdc_analyzer/pytest.ini`:
  - [x] add `routeb_live: opt-in live replay tests`
- [x] T5: Update `scripts/rdc_analyzer/tests/test_resource_inspector.py`:
  - [x] replace boolean `if not cap.LocalReplaySupport():` with enum check against `rd.ReplaySupport.Supported`
  - [x] replace unconditional skip with env-gated behavior:
    - if env var not set -> skip with reason + instructions
    - else -> run `route_b_live_check.py` under `py -3.6` and assert exit code == 0 (preflight)
- [x] T6: Add runbook doc `scripts/rdc_analyzer/docs/ROUTE_B_LIVE_REPLAY.md`:
  - prerequisites (py -3.6, PATH/pymodules)
  - tool usage examples
  - RemoteServer commands (`renderdoccmd remoteserver --listen ... --port ...`)
  - software renderer notes (SwiftShader/WARP) + limitations
- [x] T7: Update `scripts/rdc_analyzer/docs/INDEX.md` to link the new runbook.

## Impact Analysis

### Behavior changes
- Default pytest run remains unchanged (Route-B tests still skipped unless enabled).
- Route-B tool is additive and does not affect existing analyze/compare unless explicitly invoked.

### Risks
- RemoteServer path depends on network/firewall and remote filesystem semantics.
- Software renderer may still fail for captures requiring unsupported Vulkan extensions.

### Mitigations
- Tool reports exact failure classification and recommended next action.
- Keep remote/software modes opt-in.

## Verification / Acceptance (Definition of Done)

Commands (record only; user runs):

1) Unit tests (no renderdoc):
- py -3 -m py_compile scripts/rdc_analyzer/route_b_live_check.py
- py -3 -m pytest scripts/rdc_analyzer/tests/test_route_b_live_check_unit.py -q

2) Local replay preflight (py36 + local DLLs):
- py -3.6 scripts/rdc_analyzer/route_b_live_check.py "D:\\path\\to\\capture.rdc" --mode local
  - Expected:
    - JSON includes local.local_replay_support
    - If SuggestRemote: final.status == needs_remote and exit code == 10

3) Software mode (if SwiftShader/WARP available):
- py -3.6 scripts/rdc_analyzer/route_b_live_check.py "...capture.rdc" --mode software
  - Expected: either ok or clear unsupported classification

4) RemoteServer mode (when remote is available):
- On remote: renderdoccmd remoteserver --listen 0.0.0.0 --port 39920
- Local: py -3.6 scripts/rdc_analyzer/route_b_live_check.py "...capture.rdc" --mode remote --remote-url "host:39920" --copy-to-remote
  - Expected: remote.connect == Succeeded OR clear network error; open_capture result recorded.

## Approval Required

Stop here after /plan. Wait for user approval before any code/doc edits beyond this plan.



## Progress Log

- 2026-02-16: Implemented Route-B preflight tool + opt-in pytest marker/test + runbook.
- Verified (local, no renderdoc):
  - `py -3 -m py_compile scripts/rdc_analyzer/route_b_live_check.py scripts/rdc_analyzer/tests/test_route_b_live_check_unit.py scripts/rdc_analyzer/tests/test_resource_inspector.py`
  - `py -3 -m pytest scripts/rdc_analyzer/tests/test_route_b_live_check_unit.py -q` -> 8 passed
  - `py -3 -m pytest scripts/rdc_analyzer/tests/test_resource_inspector.py -q` -> 2 passed, 1 skipped

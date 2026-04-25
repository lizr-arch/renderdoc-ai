# EAP Progress Checklist

Generated: 2026-04-25

Scope: current working tree at `D:/Code/git/renderdoc`. This checklist records the current EAP
progress state for this RenderDoc fork/tooling workspace only. It does not implement runtime EAP
emission, does not modify RenderDoc core, and does not change rendering behavior.

Evidence note: Context MCP tools were not exposed in this session, so this checklist is based on
local `rg`, targeted file reads, and verification commands.

---

## 1. Repository Classification

Classification: `renderdoc_fork`.

This repository is RenderDoc source plus qrenderdoc/renderdoccmd/analyzer/MCP tooling. It is not the
engine repository that owns render graph passes, draw submission, GPU resource lifetime, materials,
shaders, assets, or capture-time engine runtime hooks.

Evidence:

| Evidence | What it proves |
|---|---|
| `CMakeLists.txt:201` | Top-level CMake project is `RenderDoc CXX C`. |
| `CMakeLists.txt:486`, `CMakeLists.txt:513`, `CMakeLists.txt:517` | Build tree adds `renderdoc`, `qrenderdoc`, and `renderdoccmd`. |
| `renderdoc.sln:8`, `renderdoc.sln:21` | Windows solution contains `qrenderdoc` and `renderdoccmd` projects. |
| `docs/EAP/EAP_IMPLEMENTATION_MAP.md:16` | Existing EAP map classifies this checkout as RenderDoc core/tooling, not an engine/RHI repository. |
| `tools/eap_scout/README.md:57` | `renderdoc_fork` means: do not implement engine-side EAP emission here. |

Working-tree scope warning: many EAP docs and tools are currently untracked/dirty in this checkout.
The evidence in this document is current working tree evidence, not committed-release evidence.

---

## 2. Task Completion Matrix

Status counts:

| Status | Count |
|---|---:|
| `done` | 5 |
| `partial` | 3 |
| `missing` | 0 |
| `not_applicable` | 10 |
| Total | 18 |

Current task-state matrix:

| ID | Status | Local interpretation | Evidence / reason |
|---|---|---|---|
| T00 | `done` | Repository reconnaissance and boundary map. | `docs/EAP/EAP_IMPLEMENTATION_MAP.md` exists and states scope is reconnaissance only. |
| T01 | `done` | EAP protocol/specification docs. | `docs/EAP/02_EAP_PROTOCOL_SPEC.md` defines annotations plus `.rmeta.json` sidecar. |
| T02 | `done` | RenderDoc app API annotation support review. | `renderdoc/api/app/renderdoc_app.h:717`, `:831`, `:832`. |
| T03 | `not_applicable` | Engine-side runtime module. | Requires engine ownership, not present in this repo. |
| T04 | `not_applicable` | Engine-side RenderDoc app bridge implementation. | Should live in an engine diagnostics/runtime module, not RenderDoc core/tooling. |
| T05 | `not_applicable` | Engine EAP core runtime types. | Requires engine build/runtime integration surface. |
| T06 | `not_applicable` | Engine render graph/pass/draw/resource hooks. | No render graph/material/resource ownership in this checkout. |
| T07 | `partial` | Tooling-side rule/provider groundwork. | Provider/rules availability and validator CLI exist, but no full rule CLI. |
| T08 | `not_applicable` | Engine sidecar writer. | Current repo can load/consume sidecar; it should not emit engine sidecars. |
| T09 | `not_applicable` | Engine capture lifecycle hook. | Capture-side engine lifecycle is outside this repo. |
| T10 | `partial` | Read-only MCP/provider sidecar surface. | `get_data_availability` and `load_eap_sidecar` exist, but this is provider/tooling support, not full EAP runtime. |
| T11 | `not_applicable` | Render graph semantic extraction inside engine. | Requires pass graph and renderer code. |
| T12 | `not_applicable` | Material/shader/asset hook emission. | Requires material/shader/asset systems not owned here. |
| T13 | `not_applicable` | Resource lifetime annotation in engine. | Requires engine resource creation/lifetime ownership. |
| T14 | `not_applicable` | Runtime performance/budget integration. | Hot-path budget enforcement belongs in engine runtime. |
| T15 | `done` | EAP Validator CLI. | `tools/eap_validator/eap_validator.py` validates one explicit `.rmeta.json` using the existing sidecar loader. |
| T16 | `partial` | Validator fixtures/golden validation package. | Focused unit/CLI tests exist under `tools/eap_validator/tests`; no external golden fixture package yet. |
| T17 | `done` | Read-only provider and sidecar loader tests. | Focused pytest passes: `44 passed in 0.30s`. |

Interpretation: current EAP Level remains `2 / 6` for the full product because engine-side runtime,
emission, and hook work is still outside this repo. Tooling readiness improved: protocol, scout, MCP
sidecar/provider support, and the first validator CLI are now present for controlled consumer work.

---

## 3. Runtime API Review

Status in this repository: `missing` / `not_applicable`.

RenderDoc exposes a suitable application API, but this repository is the API provider and tooling
consumer, not the engine process that should call the API during frame capture.

Evidence:

| Evidence | What it proves |
|---|---|
| `renderdoc/api/app/renderdoc_app.h:717` | API version `eRENDERDOC_API_Version_1_7_0` exists. |
| `renderdoc/api/app/renderdoc_app.h:748` | API 1.7.0 adds rich object/command annotations. |
| `renderdoc/api/app/renderdoc_app.h:831-832` | API table exposes `SetObjectAnnotation` and `SetCommandAnnotation`. |
| `docs/in_application_api.rst:10-14` | Applications should dynamically fetch `RENDERDOC_GetAPI`; static linking is not recommended. |
| `util/test/demos/test_common.cpp:631-652` | Demo code dynamically locates RenderDoc and requests API 1.7.0. |

Layered conclusion:

| Layer | Finding | Bypass / implementation path |
|---|---|---|
| Theory | Rich annotations are supported by RenderDoc API 1.7.0. | No theory blocker. |
| Implementation | The current repo does not contain the game/engine runtime caller. | Implement a small runtime module in the real engine repo. |
| Configuration | Older installed RenderDoc builds may not expose 1.7.0. | Dynamic version check; no-op annotation emission when unavailable; keep sidecar-only fallback. |

Recommended real engine layout:

```text
Source/Runtime/RenderDocEAP/
  Public/
    EAPRenderDocBridge.h
    EAPTypes.h
    EAPContext.h
  Private/
    EAPRenderDocBridge.cpp
    EAPContext.cpp
    EAPKeyValidation.cpp
```

If the target engine already has a graphics diagnostics/developer runtime module, use that equivalent
module instead of creating a parallel runtime stack.

---

## 4. RenderDoc Bridge Review

Status in this repository: `not_applicable here`.

The bridge concept is valid, but the bridge must be engine-side: it should dynamically obtain
`RENDERDOC_API_1_7_0` and expose no-op-safe calls such as `AnnotateCommand` and `AnnotateObject`.
This repo should only provide reference evidence and consumer/validation tooling.

Evidence:

| Evidence | What it proves |
|---|---|
| `docs/EAP/03_TASK_RENDERDOC_BRIDGE.md:3` | Bridge target is a safe no-op C++ bridge for RenderDoc in-application API 1.7.0. |
| `docs/EAP/03_TASK_RENDERDOC_BRIDGE.md:39-44` | Bridge behavior must be dynamic, platform-aware, and no-op on missing API/runtime disable. |
| `docs/EAP/EAP_IMPLEMENTATION_MAP.md:33-35` | `renderdoc_app.h` is the bridge header; `renderdoc/replay/app_api.cpp` is reference only. |
| `docs/EAP/EAP_IMPLEMENTATION_MAP.md:107` | Existing Python `RenderDocBridge` name is MCP IPC, not the C++ app API bridge. |

Do not create `RenderDocAppBridge` under `renderdoc/**` or `qrenderdoc/**` in this repo for the EAP
runtime. That would move an engine responsibility into RenderDoc core/tooling and would risk
duplicating the actual runtime integration surface.

Preferred naming if implemented in the real engine: `EAPRenderDocAppBridge` or
`RenderDocEAPBridge`, explicitly separate from `tools/mcp/mcp_server/bridge/client.py`.

---

## 5. Sidecar Review

Status in this repository: consumer/provider `partial`; engine writer `not_applicable`.

This repo has controlled read-only sidecar loading and provider availability support. It does not
have and should not add an engine-side sidecar writer here.

Existing consumer/tooling evidence:

| Evidence | What it proves |
|---|---|
| `docs/EAP/02_EAP_PROTOCOL_SPEC.md:229-310` | EAP sidecar naming and top-level structure are specified. |
| `tools/mcp/providers/sidecar_loader.py:23-71` | Controlled `.rmeta.json` loader validates extension, allowlist, existence, size, JSON, root object, and EAP shape. |
| `tools/mcp/providers/eap_sidecar_provider.py:15-58` | `eap_sidecar` provider reports sidecar availability and capabilities from a preloaded dict. |
| `tools/mcp/tests/test_sidecar_loader.py:45-150` | Loader tests cover valid sidecar, invalid suffix, missing path, directory, oversize, invalid JSON, bad payload, allowlist, and registry compatibility. |

Missing engine-side writer:

| Item | Status | Reason |
|---|---|---|
| `SidecarWriter` runtime class | `not_applicable here` | Needs engine frame/capture lifecycle. |
| Atomic sidecar write next to `.rdc` | `not_applicable here` | Needs capture path resolution in the engine process. |
| Redaction at data-source level | `not_applicable here` | Needs engine asset/material/shader path ownership. |

Safe next consumer path in this repo: validate sidecar files and provider output. Unsafe path here:
inventing engine writer code without engine hooks.

---

## 6. Engine Hook Review

Status: all engine hooks are `not_applicable` in this repository.

Reason: the current checkout lacks ownership of the systems that should emit EAP facts:

| Hook family | Status here | Correct owner |
|---|---|---|
| Render graph / pass begin/end | `not_applicable` | Engine renderer / render graph module. |
| Draw / dispatch submission | `not_applicable` | Engine RHI or command recording layer. |
| Resource creation / lifetime | `not_applicable` | Engine RHI resource manager. |
| Material / shader / asset mapping | `not_applicable` | Engine material, shader compiler, asset registry. |
| Capture lifecycle / sidecar flush | `not_applicable` | Engine diagnostics/capture integration module. |

The existing RenderDoc backend code is useful as a consumer/reference for how annotations are stored
and replayed, but it is not the correct source of engine semantics.

Boundary rule: do not patch `renderdoc/driver/**`, `renderdoc/core/**`, shader paths, resource
loading paths, or qrenderdoc UI code to synthesize EAP facts for this milestone.

---

## 7. Current Tooling Inventory

Tooling currently available or partially available:

| Surface | Status | Evidence |
|---|---|---|
| EAP Scout CLI | `done` | `tools/eap_scout/README.md:3-9`; `py -3 tools\eap_scout\eap_scout.py --help` succeeds. |
| EAP protocol docs | `done` | `docs/EAP/02_EAP_PROTOCOL_SPEC.md`. |
| Provider availability model | `partial/done for availability` | `tools/mcp/providers/base.py:42`, `tools/mcp/providers/registry.py:37-49`. |
| EAP sidecar loader | `done as loader` | `tools/mcp/providers/sidecar_loader.py:23-71`. |
| Read-only provider MCP wrapper | `partial` | `tools/mcp/mcp_server/provider_readonly_server.py:20-50`. |
| Dedicated EAP Validator CLI | `done` | `tools/eap_validator/README.md`; `py -3 -m pytest tools\eap_validator\tests -q` succeeds. |

Important distinction: a loader/provider that reads an existing `.rmeta.json` is not the same thing
as a runtime sidecar writer that produces `.rmeta.json` during capture.

---

## 8. Recommended Next Minimal Task

Recommended next task: T16/T07 follow-up, validator golden fixtures plus rule CLI planning.

Why this is the right next step:

1. It is inside this repo's safe ownership: tooling, validation, and read-only consumer behavior.
2. It builds on existing sidecar schema, loader, provider, and validator tests.
3. It avoids forbidden runtime/hook work in the RenderDoc fork.
4. It gives future engine-side work a stronger acceptance gate for generated `.rmeta.json` files.
5. T15 now provides the user-facing CLI; the next useful increment is durable fixtures and rule
   validation planning without changing RenderDoc core.

Current T15 shape:

```text
tools/eap_validator/
  eap_validator.py
  README.md
  tests/
    test_eap_validator.py
```

Current commands are read-only validation only, for example:

```powershell
py -3 tools\eap_validator\eap_validator.py validate path\to\capture.rmeta.json
py -3 -m pytest tools\eap_validator\tests -q
```

Do not implement capture, upload, deletion, remote execution, arbitrary file reads, or RenderDoc core
patches as part of T16/T07 follow-up.

---

## 9. Verification

Commands run for this checklist:

| Command | Result |
|---|---|
| `git status --short` | Dirty/untracked working tree exists before this doc; this task only adds `docs/EAP/EAP_PROGRESS_CHECKLIST.md`. |
| `git rev-parse --show-toplevel` | `D:/Code/git/renderdoc`. |
| `git branch --show-current` | `codex/local-clean-main`. |
| `py -3 tools\eap_scout\eap_scout.py --help` | Succeeded; printed `scan`, `prompt`, `summarize` commands. |
| `py -3 -m py_compile tools\eap_scout\eap_scout.py tools\mcp\providers\sidecar_loader.py tools\mcp\providers\eap_sidecar_provider.py tools\mcp\mcp_server\provider_tools.py tools\mcp\mcp_server\provider_readonly_server.py` | Succeeded with no output. |
| `py -3 -m pytest tools\eap_scout\tests\test_eap_scout.py tools\mcp\tests\test_sidecar_loader.py tools\mcp\tests\test_provider_registry.py tools\mcp\tests\test_provider_routing.py tools\mcp\tests\test_provider_mcp_tools.py tools\mcp\tests\test_provider_readonly_server.py -q` | `44 passed in 0.30s`. |
| `py -3 -m py_compile tools\eap_validator\eap_validator.py tools\eap_validator\tests\test_eap_validator.py` | Succeeded with no output. |
| `py -3 -m pytest tools\eap_validator\tests -q` | `9 passed in 1.35s`. |

Build status: not run. This task is Python tooling plus documentation only and does not touch C++
build inputs or RenderDoc runtime behavior.

---

## 10. Current Completion Summary

Current EAP Level: `2 / 6`.

Meaning:

- Protocol docs exist.
- Scout/analyzer planning support exists.
- Read-only MCP provider/sidecar loader tooling exists and has focused tests.
- EAP Validator CLI exists and has focused unit/CLI tests.
- Engine runtime, bridge, sidecar writer, render hooks, and semantic emission are not implemented in
  this repository.
- This round changed no RenderDoc core code and no rendering behavior.

This checklist intentionally treats engine-side work as `not_applicable` rather than `missing` for
this repo. The work is still missing for a complete EAP product, but its correct implementation
surface is the real engine repository.

---

## 11. Next-Round Codex Prompt

Use this prompt for the next Codex session if continuing after T15:

```text
You are working in D:\Code\git\renderdoc on branch codex/local-clean-main.

Goal:
Implement a T16/T07 follow-up for validator golden fixtures and rule CLI planning as tooling only.
Do not implement engine runtime, RenderDoc core changes, render graph hooks, sidecar writer
emission, capture, upload, delete, or remote execution.

Read first:
- docs/EAP/EAP_PROGRESS_CHECKLIST.md
- docs/EAP/02_EAP_PROTOCOL_SPEC.md
- docs/EAP/EAP_MCP_DATA_MODEL.md
- docs/EAP/EAP_MCP_PROVIDER_REFACTOR_PLAN.md
- tools/mcp/providers/sidecar_loader.py
- tools/mcp/providers/eap_sidecar_provider.py
- tools/mcp/tests/test_sidecar_loader.py
- tools/eap_validator/eap_validator.py
- tools/eap_validator/tests/test_eap_validator.py

Allowed files:
- docs/EAP/EAP_PROGRESS_CHECKLIST.md
- tools/eap_validator/**
- tools/eap_validator/tests/**
- narrow docs/tests updates directly required for validator fixtures or read-only rule planning

Forbidden files and behaviors:
- Do not modify renderdoc/**
- Do not modify qrenderdoc/**
- Do not modify shader/resource/rendering paths
- Do not add MCP write tools
- Do not add arbitrary file read tools
- Do not add shell/exec/upload/delete/capture/remote capabilities
- Do not make existing MCP depend on EAP
- Do not parse .rdc binary in the validator

Implementation target:
- Add durable golden sidecar fixtures or fixture generators for the existing validator.
- Keep validator reads explicit and allowlisted; do not add directory scanning by default.
- Preserve deterministic machine-readable JSON and stable SidecarLoadError codes.
- If planning a rule CLI, document scope first; do not implement write/upload/capture behavior.
- Run py_compile and focused pytest.

Completion report:
- List modified files.
- Report exact verification commands and outputs.
- State explicitly that RenderDoc core and rendering behavior were not modified.
```

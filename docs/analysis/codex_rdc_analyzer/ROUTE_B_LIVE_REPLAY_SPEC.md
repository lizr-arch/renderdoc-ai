# /spec: Route-B Live Replay Reproducibility & Gate Readiness

- Date: 2026-02-15
- Focus: scripts/rdc_analyzer Route-B (RenderDoc Replay API) 
- Goal: make Route-B replay verifiable, diagnosable, and reproducible (not "it works on my machine").

## 1) Background / SSOT

Project SSOT:
- Single-frame deep analysis (from .rdc/XML) with actionable suggestions.
- Two-frame comparison (baseline vs target) with differences and conclusions.

Ref:
- AGENTS.md:13
- AGENTS.md:14

Route-B meaning in this repo:
- Open capture via RenderDoc Python API (renderdoc.pyd) and create a ReplayController.
- Use SetFrameEvent() / GetPipelineState() / GetTextures() to fetch replay-level truth.

Ref:
- docs/analysis/codex_rdc_analyzer/WORK_SUMMARY_ROUTES.md:104
- docs/analysis/codex_rdc_analyzer/WORK_SUMMARY_ROUTES.md:185

## 2) Current State (Evidence)

### 2.1 Code paths exist

ReplayWrapper already calls the key ReplayController APIs:
- scripts/rdc_analyzer/extractors/replay_wrapper.py:182 (OpenFile)
- scripts/rdc_analyzer/extractors/replay_wrapper.py:195 (OpenCapture)
- scripts/rdc_analyzer/extractors/replay_wrapper.py:314 (SetFrameEvent)
- scripts/rdc_analyzer/extractors/replay_wrapper.py:336 (GetPipelineState -> Vulkan)

Other scripts also rely on OpenCapture:
- scripts/rdc_analyzer/rdc_to_html.py:257
- scripts/rdc_analyzer/export_textures.py:212

### 2.2 Tests indicate Route-B is not default-reproducible

Replay-dependent tests are skipped by default:
- scripts/rdc_analyzer/tests/test_resource_inspector.py:290 (skip: requires live controller)
- scripts/rdc_analyzer/tests/test_rdc_loader.py:230 (skip: no sample RDC)

### 2.3 Real-world failure mode is GPU replay incompatibility

Observed on 2026-02-15 (local machine):
- Python 3.6 + renderdoc.pyd can be imported when PATH + pymodules are set.
- A real Vulkan capture (Pixel 9 / Mali-G715) fails to OpenCapture on RTX 4070 Ti.
  - LocalReplaySupport reports SuggestRemote.
  - OpenCapture fails with missing Vulkan extension (VK_EXT_fragment_density_map2) / cross-vendor replay mismatch.

This is expected and documented:
- scripts/rdc_analyzer/docs/GPU_COMPATIBILITY_ANALYSIS.md:1
- scripts/rdc_analyzer/docs/GPU_COMPATIBILITY_ANALYSIS.md:152 (RemoteServer as solution)

## 3) Problem Statement

Route-B is implemented, but the project lacks a "replay preflight" that:
- (a) deterministically diagnoses environment + replay feasibility,
- (b) classifies failure into actionable buckets (missing module vs hardware incompatibility vs missing sample),
- (c) provides a standard, reproducible next-step (RemoteServer and/or software renderer and/or offline fallback).

Without this, Route-B remains "partially validated" in docs but not operationally reproducible.

## 4) Spec-level Definition of Done (DoD)

DOD-B1: Preflight tool exists
- A CLI tool (script) takes an RDC path and outputs structured diagnosis (human + JSON).

DOD-B2: Clear classification + recommendation
- Distinguish at least:
  - renderdoc module not available
  - capture open failed
  - local replay unsupported / suggest remote
  - OpenCapture hardware/API incompatibility
- For each, show the recommended next action.

DOD-B3: Opt-in live replay tests
- Add a pytest marker or env-gated test group for Route-B.
- Default CI remains unchanged; but when enabled, tests are pass/fail with clear errors.

DOD-B4: Backward-compatible
- Existing analyze/compare behavior remains unchanged unless Route-B is explicitly requested.

## 5) Design Direction (Constraints-driven)

Given cross-GPU replay is inherently unreliable, the spec favors "diagnose + route" rather than "force".

Preferred routing order ("auto" mode):
1) Local replay if supported.
2) If SuggestRemote or hardware mismatch:
   - If remote server configured: try RemoteServer replay.
   - Else: report "remote required" and provide exact commands.
3) Optional: software renderer attempt (SwiftShader/WARP) if user explicitly enables.
4) Else: degrade to offline routes (A/C) with explicit limitation.

References:
- docs/analysis/gpu-dependency-solutions.md:1142 (remote GPU server)
- util/test/rdtest/analyse.py:11 (remote OpenCapture fallback pattern)

## 6) Out of Scope

- Not implementing full remote server provisioning.
- Not guaranteeing portability of Vulkan captures across GPU vendors.
- Not changing RenderDoc core replay logic.

## 7) Plan Inputs (what /plan must decide)

- Exact file set to modify/add (tool, tests, docs).
- Output JSON schema and exit codes for the preflight tool.
- Environment variables / CLI flags for remote URL, software replay, and sample paths.


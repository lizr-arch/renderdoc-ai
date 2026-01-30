## Design Summary
- Version: v1
- Owner: Codex (Agent01)
- Last Updated: 2026-01-30
- Problem: Export a drawcall (by eventId) from an .rdc capture into Unity China 1.6.9-ready assets (mesh, textures, shader), with D3D11 + Vulkan first.
- Users: Graphics analysis / reverse engineering pipeline users who need to reassemble a character draw in Unity.
- Constraints:
  - Must read from RenderDoc .rdc via existing Python API.
  - No edits in renderdoc/3rdparty or build outputs.
  - No new dependencies unless explicitly approved.
  - Target engines: D3D11 + Vulkan now; D3D12 + GLES later.
- Success Criteria (measurable):
  - For 1 capture each of D3D11 and Vulkan, given an eventId, the exporter produces mesh + textures + shader assets that can be assembled in Unity China 1.6.9 without manual conversion or shader edits, and renders the character draw correctly.
- Evaluation Plan (baseline / sample / pass threshold):
  - Sample size: 2 captures (D3D11, Vulkan).
  - Steps: Run exporter → import outputs into Unity 1.6.9 → assemble with provided manifest → render.
  - Pass: both samples render correctly at the target event without additional conversion.
- Value Check (Desirability / Feasibility / Viability):
  - Desirability: High
  - Feasibility: Medium (shader translation + .max export risk)
  - Viability: Medium
- Non-goals:
  - Full capture export; focus on a single draw/event.
  - D3D12/GLES support in the first iteration.
  - Automated Unity validation inside this repo.
- Reasoning Trace: Focus on Python-level extraction to minimize C++ core changes and reduce scope.
- Pre-mortem: Primary risks are .max export feasibility and shader translation to HLSL for Vulkan/GLES; mitigation is to output intermediate formats and confirm external tooling requirements.

## Options (2-3)
- Option A: Extend existing `scripts/rdc_analyzer` pipeline (rdc_parser + exporters) to add per-event Unity export.
- Option B: New standalone script `export_unity_assets.py` using RenderDoc Python API to export event assets into a Unity-ready folder.
- Option C: Implement exporter in C++ replay layer and expose via Python (highest effort, most robust).

## Trade-offs & Recommendation
- Trade-offs:
  - A: Strong integration but more coupling and refactor cost.
  - B: Fast iteration, minimal risk to core; easiest to scope for D3D11 + Vulkan.
  - C: Best performance and fidelity but high effort, more invasive changes.
- Recommendation: Option B (standalone script), with a clear manifest and incremental per-API support.

## Open Questions
- Is direct .max output mandatory, or is an intermediate mesh format acceptable with a separate MaxScript conversion?
- Is shader translation to HLSL required for Vulkan/GLES (SPIR-V/GLSL), and can external tooling be used?

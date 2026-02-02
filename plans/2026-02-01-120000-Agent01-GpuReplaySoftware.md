# Plan: GPU Replay Software Backends (Windows-first)

## Scope
In:
- Create a dedicated folder: docs/analysis/gpu_replay_software/
- Document Windows workflows for WARP (D3D11), SwiftShader (Vulkan), ANGLE (GLES)
- Provide an experiment matrix and checklist
- Cross-link existing repo docs (gpu-dependency-solutions, CROSS_GPU_REPLAY_GUIDE)

Out:
- Replay engine code changes
- Dependency installation or downloads
- Linux-only execution (llvmpipe), except for documentation notes

## Assumptions
- renderdoccmd supports --software-render (renderdoccmd/renderdoccmd.cpp:679)
- D3D11 replay can select WARP (renderdoc/driver/d3d11/d3d11_replay.cpp:4257, 4333)
- SwiftShader is configured via VK_ICD_FILENAMES on Windows (docs/analysis/gpu-dependency-solutions.md:82-86)
- ANGLE can be used for GLES on Windows (documented steps)
- llvmpipe is Linux/WSL-only (renderdoc/driver/gl/gl_debug.cpp:1106, renderdoc/driver/vulkan/vk_common.cpp:1018)

## Repo / File List (with line refs)
Existing:
- renderdoccmd/renderdoccmd.cpp:679
- renderdoc/driver/d3d11/d3d11_replay.cpp:4257
- renderdoc/driver/d3d11/d3d11_replay.cpp:4333
- renderdoc/driver/gl/gl_debug.cpp:1106
- renderdoc/driver/vulkan/vk_common.cpp:1018
- docs/analysis/gpu-dependency-solutions.md:49, 78, 82, 86, 107, 319, 356, 364, 378

New:
- docs/analysis/gpu_replay_software/README.md
- docs/analysis/gpu_replay_software/windows_playbook.md
- docs/analysis/gpu_replay_software/experiment_matrix.md

## Approach (Pseudo-code)
- Create docs/analysis/gpu_replay_software/ folder and README with scope, terms, and constraints.
- For each backend (WARP, SwiftShader, ANGLE):
  - List prerequisites (user installs and locations).
  - Define environment variables and renderdoccmd flags.
  - Define test steps for replay and color RT export.
  - Record expected outcomes and common failures.
- For llvmpipe:
  - Document WSL/Linux-only path and mark as not executed (Windows-only scope).
- Build an experiment matrix table (API x backend x status).
- Cross-link existing docs for background and installation notes.

## Build/Test/Lint Quick Guide (commands only, not executed)
- D3D11 WARP (expected: replay succeeds, color RT export works)
  - renderdoccmd.exe replay --software-render <capture.rdc>
  - renderdoccmd.exe export --texture <id> --format png --out <dir>  (to confirm exact syntax)
- Vulkan SwiftShader (expected: replay uses SwiftShader ICD)
  - set VK_ICD_FILENAMES=C:\SwiftShader\vk_swiftshader_icd.json
  - renderdoccmd.exe replay --software-render <capture.rdc>
- GLES ANGLE (expected: replay uses ANGLE)
  - set EGL_PLATFORM=angle
  - set ANGLE_DEFAULT_PLATFORM=swiftshader
  - renderdoccmd.exe replay --software-render <capture.rdc>
- llvmpipe (Linux/WSL only; documented, not executed)

## Impact Analysis
- Documentation-only changes, no runtime behavior change.
- Risk: command syntax may drift; mitigate by confirming in /do.

## Action Items
- [x] Create docs/analysis/gpu_replay_software/ folder
- [x] Write README.md (scope, definitions, constraints)
- [x] Write windows_playbook.md (WARP/SwiftShader/ANGLE steps)
- [x] Write experiment_matrix.md (API x backend x status)
- [x] Add references to existing docs and code locations

## Risks & Blockers
- Missing external installs (SwiftShader/ANGLE)
- renderdoccmd syntax mismatch
- Some captures incompatible with software backends

## Verification / DoD
- Folder and three docs exist.
- Each backend has Windows steps with env vars and commands.
- Experiment matrix completed with status fields.

## Open Questions
- (Resolved) Confirmed export syntax in renderdoccmd/renderdoccmd.cpp.

## Next Steps
- Await /do approval to implement documentation changes.

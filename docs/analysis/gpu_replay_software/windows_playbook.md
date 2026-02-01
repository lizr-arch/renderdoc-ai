# Windows Playbook (WARP / SwiftShader / ANGLE)

This playbook focuses on Windows-only steps to run RenderDoc replay with software backends and
export color RTs as PNG. All commands are examples and should be verified with
`renderdoccmd --help` in your environment.

## Common replay flow
1) Ensure the capture opens and events are visible.
2) Replay using a software backend.
3) Export color RTs as PNG.

## D3D11: WARP
Purpose: D3D11 software rasterizer on Windows.

Steps:
1) Replay with software rendering:
   - `renderdoccmd.exe replay --software-render <capture.rdc>`
2) Export color RTs (verify exact flags):
   - `renderdoccmd.exe export --help`
   - `renderdoccmd.exe export --texture <id> --format png --out <dir>`  (ASSUMPTION)

Expected:
- Replay runs without a hardware GPU dependency.
- Performance is slower than hardware replay.

## Vulkan: SwiftShader
Purpose: Vulkan software backend.

Prereq:
- Install SwiftShader Vulkan ICD on Windows.
- Set environment variable to the ICD JSON (example):
  - `set VK_ICD_FILENAMES=C:\SwiftShader\vk_swiftshader_icd.json`  (verify your path)

Steps:
1) Replay with software rendering:
   - `renderdoccmd.exe replay --software-render <capture.rdc>`
2) Export color RTs (verify exact flags):
   - `renderdoccmd.exe export --help`
   - `renderdoccmd.exe export --texture <id> --format png --out <dir>`  (ASSUMPTION)

Expected:
- Replay uses SwiftShader ICD.
- Performance is significantly slower than hardware replay.

## GLES: ANGLE
Purpose: GLES via ANGLE on Windows, optionally with a software backend.

Prereq:
- Install an ANGLE build that provides EGL/GLES on Windows.
- If available, set ANGLE to a software backend (example vars below; verify for your build):
  - `set EGL_PLATFORM=angle`  (ASSUMPTION)
  - `set ANGLE_DEFAULT_PLATFORM=swiftshader`  (ASSUMPTION)

Steps:
1) Replay with software rendering:
   - `renderdoccmd.exe replay --software-render <capture.rdc>`
2) Export color RTs (verify exact flags):
   - `renderdoccmd.exe export --help`
   - `renderdoccmd.exe export --texture <id> --format png --out <dir>`  (ASSUMPTION)

Expected:
- Replay uses ANGLE (software backend if configured).

## Notes
- If replay still fails on different GPUs, consider remote replay on the capture machine.
- For Vulkan cross-GPU issues, see docs/analysis/CROSS_GPU_REPLAY_GUIDE.md.

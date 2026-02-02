# Windows Playbook (WARP / SwiftShader / ANGLE)

This playbook focuses on Windows-only steps to run RenderDoc replay with software backends and
export color RTs as PNG. Commands below are aligned with the current `renderdoccmd export` options
(see `renderdoccmd/renderdoccmd.cpp`).

## Common replay flow
1) Ensure the capture opens and events are visible.
2) Replay using a software backend.
3) Export textures as PNG, then filter for color RTs.

## D3D11: WARP
Purpose: D3D11 software rasterizer on Windows.

Steps:
1) Replay with software rendering:
   - `renderdoccmd.exe replay --software-render <capture.rdc>`
2) Export textures (PNG):
   - `renderdoccmd.exe export --out <dir> --format png --max-size 0 --software-render <capture.rdc>`
   - Optional: `--metadata`, `--bindings`, `--remote-host <host>`

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
2) Export textures (PNG):
   - `renderdoccmd.exe export --out <dir> --format png --max-size 0 --software-render <capture.rdc>`
   - Optional: `--metadata`, `--bindings`, `--remote-host <host>`

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
2) Export textures (PNG):
   - `renderdoccmd.exe export --out <dir> --format png --max-size 0 --software-render <capture.rdc>`
   - Optional: `--metadata`, `--bindings`, `--remote-host <host>`

Expected:
- Replay uses ANGLE (software backend if configured).

## Notes
- If replay still fails on different GPUs, consider remote replay on the capture machine.
- For Vulkan cross-GPU issues, see docs/analysis/CROSS_GPU_REPLAY_GUIDE.md.

# Experiment Matrix (Windows-first)

## Status legend
- Ready: known steps and dependencies available
- Planned: steps drafted, needs validation
- Out of scope: not Windows

## Matrix
| API   | Backend        | Windows | Status   | Notes |
|------|----------------|---------|----------|-------|
| D3D11 | WARP          | Yes     | Planned  | Uses software-render flag |
| Vulkan | SwiftShader  | Yes     | Planned  | Requires SwiftShader ICD |
| GLES | ANGLE          | Yes     | Planned  | Requires ANGLE build |
| Vulkan | llvmpipe     | No      | Out of scope | Linux/WSL only |
| GLES | llvmpipe       | No      | Out of scope | Linux/WSL only |

## Test checklist (per backend)
- [ ] Capture opens and events list is visible
- [ ] Replay runs with software backend enabled
- [ ] Color RTs export to PNG successfully
- [ ] Manual visual check passes

## Experiment log (fill in)
| Date | Capture | API | Backend | Result | Notes |
|------|---------|-----|---------|--------|-------|
|      |         |     |         |        |       |

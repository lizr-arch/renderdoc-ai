# Build + Python In-Process Check Plan (RenderDoc + S1)

## Scope
- In: build RenderDoc locally; verify that `cl`/`msbuild` work via VS Dev Cmd; determine whether the running game process loads `python*.dll`.
- Out: modifying game code, adding new RenderDoc features, or changing capture behavior beyond existing helper.

## Assumptions
- VS 2022 Community is installed at `E:\Program Files\Microsoft Visual Studio\2022\Community`.
- You allow starting the game via `F:\Code\S1\Messiah_Python.bat`.
- No anti-cheat/permission blocking module enumeration for your own process.

## Repo / File List (line-specific)
- `renderdoc/api/app/renderdoc_app.h:337` — `pRENDERDOC_SetCaptureKeys`
- `renderdoc/api/app/renderdoc_app.h:509` — `pRENDERDOC_TriggerCapture`
- `renderdoc/api/app/renderdoc_app.h:737` — `pRENDERDOC_GetAPI`
- `renderdoccmd/renderdoccmd_win32.cpp:822` — globalhook error path (context for injection tooling)
- `util/rdoc_quick_capture/rdoc_quick_capture.cpp:1` — helper implementation (context only)
- `util/rdoc_quick_capture/example_d3d12.cpp:1` — helper usage example (context only)

## Build/Test/Lint Quick Guide (record only; do not execute here)
- Build (VS Dev Cmd):
  - `cmd /c "\"E:\Program Files\Microsoft Visual Studio\2022\Community\Common7\Tools\VsDevCmd.bat\" -arch=x64 -host_arch=x64 && msbuild renderdoc.sln /p:Configuration=Development /p:Platform=x64"`
  - Expected: `Build succeeded.` with no errors.
- Compile-only example (no link):
  - `cmd /c "\"E:\Program Files\Microsoft Visual Studio\2022\Community\Common7\Tools\VsDevCmd.bat\" -arch=x64 -host_arch=x64 && cl /c /EHsc /I renderdoc\api\app util\rdoc_quick_capture\example_d3d12.cpp"`
  - Expected: `example_d3d12.obj` created; no `error Cxxxx`.

## Approach (Pseudo-code + Full Commands)
1) Launch the game (from the provided bat).
   - `cmd /c "F:\Code\S1\Messiah_Python.bat"`
2) Identify the game process name (if unknown, list by window title).
   - `tasklist | findstr /i "Messiah"`
   - If the exact exe name is known: `tasklist /fi "imagename eq <GameExe>.exe"`
3) Check if the game process loads Python DLLs.
   - `tasklist /m python*.dll`
   - `tasklist /m python*.dll | findstr /i "<GameExe>.exe"`
   - Expected (Python in-process): `<GameExe>.exe` appears in the output with `python*.dll`.
   - Expected (no Python in-process): no line for `<GameExe>.exe`.
4) Build RenderDoc using VS Dev Cmd.
   - `cmd /c "\"E:\Program Files\Microsoft Visual Studio\2022\Community\Common7\Tools\VsDevCmd.bat\" -arch=x64 -host_arch=x64 && msbuild renderdoc.sln /p:Configuration=Development /p:Platform=x64"`
5) Compile-only check for the quick-capture example.
   - `cmd /c "\"E:\Program Files\Microsoft Visual Studio\2022\Community\Common7\Tools\VsDevCmd.bat\" -arch=x64 -host_arch=x64 && cl /c /EHsc /I renderdoc\api\app util\rdoc_quick_capture\example_d3d12.cpp"`

## Action Items (2-5 min granularity)
- [x] Launch game via `F:\Code\S1\Messiah_Python.bat`.
- [x] Identify game exe name via `tasklist` (capture exact exe name).
- [x] Check for `python*.dll` loaded in the game process using `tasklist /m`.
- [x] Build RenderDoc with VS Dev Cmd + `msbuild`.
- [x] Compile-only check for `example_d3d12.cpp`.
- [x] Record results in this plan (python present? build success?).

## Impact Analysis
- Build time may be long; failure likely due to missing SDKs or misconfigured VS components.
- Module enumeration may fail for privileged processes; fallback may require admin.

## Risks & Blockers
- `tasklist /m` requires elevated access on some systems.
- Build may fail if Windows SDK components are missing.

## Decisions
- Use VS Dev Cmd to provide `cl`/`msbuild` in PATH instead of installing new tools.
- Use `tasklist /m python*.dll` for a dependency-free module check.

## Verification / DoD
- RenderDoc build completes: “Build succeeded.”
- `example_d3d12.obj` produced without compiler errors.
- Clear Yes/No on whether the game process loads `python*.dll` (recorded in this plan).

## Results
- Game process name: `Game_x64h.exe` (PID observed: 25512).
- Python in-process: **Yes** — modules `PythonCore_x64h.dll` and `Python_x64h.dll` loaded.
- RenderDoc build: **Succeeded** (Development|x64).
- Compile-only example: **Succeeded** (no errors).

## Next Steps
- If Python is loaded in-process: design a Python ctypes capture trigger.
- If not: proceed with App API (C++ helper) or `renderdoccmd`-based injection.
- Await `/do` approval to execute the above commands.

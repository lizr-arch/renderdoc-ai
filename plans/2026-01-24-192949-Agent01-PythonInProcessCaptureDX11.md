# Python In-Process Capture Plan (DX11)

## Scope
- In: add a Python ctypes helper that runs **inside the game process** to call RenderDoc App API (TriggerCapture) and optionally set capture path/title.
- Out: modifying game C++ code, changing RenderDoc core capture internals, or adding new UI in qrenderdoc.

## Assumptions
- Game process already loads Python (`PythonCore_x64h.dll`, `Python_x64h.dll`) — confirmed.
- Game runs DX11 (`--dx11`) and Python can execute inside the process (e.g., `--start=Python`).
- `renderdoc.dll` is accessible to the process (either already loaded or loadable by path).

## Repo / File List
- New (repo):
  - `docs/analysis/rdoc_quick_capture_python.md` (integration guide)
- New (external, game package):
  - `F:\Code\S1\Package\rdoc_quick_capture\rdoc_inprocess_capture.py` (Python helper)
- Reference:
  - `renderdoc/api/app/renderdoc_app.h:622` — `RENDERDOC_API_1_6_0` layout
  - `renderdoc/api/app/renderdoc_app.h:509` — `pRENDERDOC_TriggerCapture`
  - `renderdoc/api/app/renderdoc_app.h:405` — `pRENDERDOC_SetCaptureFilePathTemplate`
  - `renderdoc/api/app/renderdoc_app.h:37` — `RENDERDOC_CC __cdecl`

## Approach (Pseudo-code + Full Snippet)
We load `renderdoc.dll`, call `RENDERDOC_GetAPI` to retrieve the function table, then call `TriggerCapture()` when your target UI state is reached. This avoids needing device pointers (DX11-specific) and avoids relying on RenderDoc hotkeys.

```python
# scripts/rdoc_quick_capture/rdoc_inprocess_capture.py
import ctypes
import os

# RENDERDOC_Version
RENDERDOC_API_VERSION_1_6_0 = 10600

# Function pointer helpers (cdecl)
CFN_void = ctypes.CFUNCTYPE(None)
CFN_void_ccharp = ctypes.CFUNCTYPE(None, ctypes.c_char_p)

class RENDERDOC_API_1_6_0(ctypes.Structure):
    _fields_ = [
        ("GetAPIVersion", ctypes.c_void_p),
        ("SetCaptureOptionU32", ctypes.c_void_p),
        ("SetCaptureOptionF32", ctypes.c_void_p),
        ("GetCaptureOptionU32", ctypes.c_void_p),
        ("GetCaptureOptionF32", ctypes.c_void_p),
        ("SetFocusToggleKeys", ctypes.c_void_p),
        ("SetCaptureKeys", ctypes.c_void_p),
        ("GetOverlayBits", ctypes.c_void_p),
        ("MaskOverlayBits", ctypes.c_void_p),
        ("RemoveHooks", ctypes.c_void_p),
        ("UnloadCrashHandler", ctypes.c_void_p),
        ("SetCaptureFilePathTemplate", ctypes.c_void_p),
        ("GetCaptureFilePathTemplate", ctypes.c_void_p),
        ("GetNumCaptures", ctypes.c_void_p),
        ("GetCapture", ctypes.c_void_p),
        ("TriggerCapture", ctypes.c_void_p),
        ("IsTargetControlConnected", ctypes.c_void_p),
        ("LaunchReplayUI", ctypes.c_void_p),
        ("SetActiveWindow", ctypes.c_void_p),
        ("StartFrameCapture", ctypes.c_void_p),
        ("IsFrameCapturing", ctypes.c_void_p),
        ("EndFrameCapture", ctypes.c_void_p),
        ("TriggerMultiFrameCapture", ctypes.c_void_p),
        ("SetCaptureFileComments", ctypes.c_void_p),
        ("DiscardFrameCapture", ctypes.c_void_p),
        ("ShowReplayUI", ctypes.c_void_p),
        ("SetCaptureTitle", ctypes.c_void_p),
    ]

class RenderDocInProcess:
    def __init__(self, dll_path=None):
        self._api = None
        if dll_path and os.path.exists(dll_path):
            rdoc = ctypes.CDLL(dll_path)
        else:
            rdoc = ctypes.CDLL("renderdoc.dll")

        getapi = rdoc.RENDERDOC_GetAPI
        getapi.restype = ctypes.c_int
        getapi.argtypes = [ctypes.c_int, ctypes.POINTER(ctypes.c_void_p)]

        api_ptr = ctypes.c_void_p()
        ok = getapi(RENDERDOC_API_VERSION_1_6_0, ctypes.byref(api_ptr))
        if ok and api_ptr.value:
            self._api = ctypes.cast(api_ptr, ctypes.POINTER(RENDERDOC_API_1_6_0)).contents

    def is_available(self):
        return self._api is not None

    def set_capture_path(self, path):
        if not self._api or not path:
            return
        fn = CFN_void_ccharp(self._api.SetCaptureFilePathTemplate)
        fn(path.encode("utf-8"))

    def trigger_capture(self):
        if not self._api:
            return
        fn = CFN_void(self._api.TriggerCapture)
        fn()

# Example usage inside game Python update:
# rdoc = RenderDocInProcess(r"F:\Code\S1\RenderDoc\renderdoc.dll")
# if rdoc.is_available() and in_target_ui:
#     rdoc.set_capture_path(r"F:\Code\S1\RenderDocCaptures\capture")
#     rdoc.trigger_capture()
```

## Impact Analysis
- Low risk to RenderDoc core; helper is standalone Python script.
- Key risk: `renderdoc.dll` load failure or missing export `RENDERDOC_GetAPI`.
- DX11-specific device pointers are not required because we use `TriggerCapture()`.

## Action Items (2-5 min granularity)
- [x] Add in-game Python helper at `F:\Code\S1\Package\rdoc_quick_capture\rdoc_inprocess_capture.py` (fixed syntax + version fallback).
- [x] Add `docs/analysis/rdoc_quick_capture_python.md` with integration steps and troubleshooting (content verified, UTF-8).
- [ ] Verify the script in-game: call `RenderDocInProcess(...).trigger_capture()` in target UI.
- [ ] Optional: mirror helper into repo for versioning (if you want it tracked).

## Risks & Blockers
- `renderdoc.dll` not loadable in-process (path or access issue).
- Python hook point in game is limited (no per-frame callback).

## Verification / DoD
- In target UI, invoking `trigger_capture()` produces a `.rdc` in the configured path.
- The `.rdc` opens in RenderDoc and shows the captured frame.

## Open Questions
- Placement confirmed: `F:\Code\S1\Package`.

## Next Steps
- Run in-game verification on target UI and confirm `.rdc` output path.

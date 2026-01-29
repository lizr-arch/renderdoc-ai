# Py27 RenderDoc In-Process Capture Extension Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

## Plan Metadata
- Version: 0.2
- Owner: Agent01
- Last Updated: 2026-01-26
- Plan File: `plans/2026-01-24-192949-Agent01-PythonInProcessCaptureDX11.md`

## Goal
- Build a minimal **Python 2.7 C extension (.pyd)** that can load RenderDoc in-process and trigger frame capture without `ctypes`.

## Architecture
- Provide a tiny native Python module (`rdoc_capture`) that wraps RenderDoc App API: load `renderdoc.dll`, call `RENDERDOC_GetAPI`, then expose `trigger_capture()` and `set_capture_path/title()` to game scripts.
- Copy the compiled `.pyd` into a directory already on the embedded Python `sys.path` so imports work without extra path tweaks.

## Tech Stack
- C/C++ (MSVC)
- RenderDoc App API (`renderdoc/api/app/renderdoc_app.h`)
- Python 2.7 C API (embedded in game)
- Windows x64

## Success Criteria (measurable)
- In the game console, `import rdoc_capture` succeeds.
- `rdoc_capture.is_available()` returns `True`.
- `rdoc_capture.trigger_capture()` creates an `.rdc` under the configured path.

## Acceptance Criteria
- A capture taken from the target UI loads in RenderDoc and contains expected draw calls.

## Verification Commands
- `cmd /c "tasklist /m renderdoc.dll | findstr /i Game_x64h.exe"` (Expected: line showing `Game_x64h.exe` with `renderdoc.dll`)
- In-game console:
  - `import rdoc_capture; print(rdoc_capture.is_available())` (Expected: `True`)
  - `rdoc_capture.set_capture_path(r"F:\Code\S1\RenderDocCaptures\capture"); rdoc_capture.trigger_capture()` (Expected: new `.rdc`)

## Evidence
- Screenshot/log of in-game console output showing `True`
- `.rdc` file path under `F:\Code\S1\RenderDocCaptures\`

## Estimation
- Effort: 0.5–1.0 day
- Story Points: 2
- Original Estimate: 1 day

## Risk Register
| Risk | Impact | Likelihood | Mitigation |
|---|---|---|---|
| Python 2.7 dev headers/libs not found | High | Medium | Locate headers/libs in S1 tools; if missing, generate import lib from python27.dll or add a minimal SDK |
| ABI mismatch (MSC version) | High | Medium | Use MSVC toolchain matching `sys.version` (MSC v.1940) |
| renderdoc.dll load fails | Medium | Medium | Use absolute path; ensure DLL is present and accessible |
| Anti-cheat or sandbox blocks DLL load | Medium | Low | Test in QA2 branch and verify logs |
| In-game verification pending | Medium | Medium | User runs console commands to validate import and capture |

## Game Dev: Memory & Resource Budget (Leak Checks)
- Captures can be large; confirm `RenderDocCaptures` has enough disk space.
- Avoid frequent captures; gate with a UI state and one-shot flag.

## Game Dev: Asset Pipeline
- Treat `.rdc` outputs as debug artifacts; store under a dedicated `RenderDocCaptures/` directory.
- Do not package `.rdc` into release builds.

## Game Dev: Crash Repro + Dumps/Symbols
- Repro steps: enter target UI, call `trigger_capture()`.
- Dump/Core: minidump (if native crash occurs).
- Symbols: PDB for game + RenderDoc build.
- Build identity: record engine version + script version + git commit if available.

---

## Scope
- In: add a **Python 2.7 native extension** to call RenderDoc App API.
- Out: modifying game C++ code, changing RenderDoc core, or relying on `ctypes`.

## Assumptions
- Embedded Python is 2.7.18 (MSC v.1940) and can load `.pyd` modules.
- We can place `.pyd` into a directory already on `sys.path`.
- Python headers available at `F:\Code\S1\doc\tools\Formation_Toos\venv\Include` (2.7.12 headers).
- Python runtime DLL at `F:\Code\S1\Engine\Binaries\Win64\capture_texture\python27.dll` (2.7.18).

## Repo / File List
- Reference:
  - `renderdoc/api/app/renderdoc_app.h:720-737` — `pRENDERDOC_GetAPI` typedef
  - `renderdoc/replay/app_api.cpp:320-340` — `RENDERDOC_GetAPI` export
  - `docs/in_application_api.rst:16-39` — signature and sample usage
- New (repo):
  - `util/rdoc_quick_capture_py27/rdoc_capture_py27.cpp`
  - `util/rdoc_quick_capture_py27/build_py27_capture.cmd`
  - `docs/analysis/rdoc_quick_capture_py27.md` (how-to + troubleshooting)
- External (game package):
  - `F:\Code\S1\Package\Script\Python\engine\Lib\rdoc_capture.pyd`

## Approach (Pseudo-code + Full Snippet)

Pseudo-flow:
1) `LoadLibraryW(renderdoc.dll)` or `GetModuleHandleW(renderdoc.dll)`
2) `GetProcAddress("RENDERDOC_GetAPI")`
3) Call `RENDERDOC_GetAPI(eRENDERDOC_API_Version_1_6_0, &api)`
4) Expose Python functions: `is_available()`, `set_capture_path()`, `set_capture_title()`, `trigger_capture()`

Core C++ skeleton (full snippet):
```cpp
// util/rdoc_quick_capture_py27/rdoc_capture_py27.cpp
#include <Windows.h>
#include "renderdoc/api/app/renderdoc_app.h"
#include <Python.h>

static const char *g_last_error = "";
static RENDERDOC_API_1_6_0 *g_rdoc = NULL;
static HMODULE g_rdoc_module = NULL;

static PyObject *rdoc_load(PyObject *, PyObject *args)
{
  const char *dllPath = NULL;
  if(!PyArg_ParseTuple(args, "|s", &dllPath))
    return NULL;

  if(!g_rdoc_module)
  {
    g_rdoc_module = dllPath ? LoadLibraryA(dllPath) : GetModuleHandleA("renderdoc.dll");
    if(!g_rdoc_module)
      g_rdoc_module = LoadLibraryA("renderdoc.dll");
  }

  if(!g_rdoc_module)
  {
    g_last_error = "renderdoc.dll not loaded";
    Py_RETURN_FALSE;
  }

  pRENDERDOC_GetAPI getapi = (pRENDERDOC_GetAPI)GetProcAddress(g_rdoc_module, "RENDERDOC_GetAPI");
  if(!getapi)
  {
    g_last_error = "RENDERDOC_GetAPI not found";
    Py_RETURN_FALSE;
  }

  int ret = getapi(eRENDERDOC_API_Version_1_6_0, (void **)&g_rdoc);
  if(!ret || !g_rdoc)
  {
    g_last_error = "RENDERDOC_GetAPI failed";
    Py_RETURN_FALSE;
  }

  Py_RETURN_TRUE;
}

static PyObject *rdoc_is_available(PyObject *, PyObject *)
{
  if(g_rdoc)
    Py_RETURN_TRUE;
  Py_RETURN_FALSE;
}

static PyObject *rdoc_set_capture_path(PyObject *, PyObject *args)
{
  const char *path = NULL;
  if(!PyArg_ParseTuple(args, "s", &path))
    return NULL;
  if(g_rdoc && path)
    g_rdoc->SetCaptureFilePathTemplate(path);
  Py_RETURN_NONE;
}

static PyObject *rdoc_set_capture_title(PyObject *, PyObject *args)
{
  const char *title = NULL;
  if(!PyArg_ParseTuple(args, "s", &title))
    return NULL;
  if(g_rdoc && title)
    g_rdoc->SetCaptureTitle(title);
  Py_RETURN_NONE;
}

static PyObject *rdoc_trigger_capture(PyObject *, PyObject *)
{
  if(g_rdoc)
    g_rdoc->TriggerCapture();
  Py_RETURN_NONE;
}

static PyObject *rdoc_last_error(PyObject *, PyObject *)
{
  return PyString_FromString(g_last_error ? g_last_error : "");
}

static PyMethodDef RDocMethods[] = {
    {"load", rdoc_load, METH_VARARGS, "Load renderdoc and get API"},
    {"is_available", rdoc_is_available, METH_NOARGS, "Check API availability"},
    {"set_capture_path", rdoc_set_capture_path, METH_VARARGS, "Set capture path template"},
    {"set_capture_title", rdoc_set_capture_title, METH_VARARGS, "Set capture title"},
    {"trigger_capture", rdoc_trigger_capture, METH_NOARGS, "Trigger capture"},
    {"last_error", rdoc_last_error, METH_NOARGS, "Last error string"},
    {NULL, NULL, 0, NULL}};

PyMODINIT_FUNC initrdoc_capture(void)
{
  Py_InitModule("rdoc_capture", RDocMethods);
}
```

---

## Task Checklist (2–5 min each)

## Progress Checklist
- [x] Task 1: Locate Python 2.7 headers and python27.dll paths.
- [x] Task 2: Add native extension source + build script + def generator.
- [x] Task 3: Build and deploy `rdoc_capture.pyd` into `engine\Lib`.
- [x] Task 4: Add Py27-specific guide doc.

### Task 1: Locate Python 2.7 dev headers/libs (embedded)
**Files:**
- Inspect (external): possible Python headers in `F:\Code\S1\tools\...`

**Step 1: Write the failing test**
```python
# In-game console
import rdoc_capture
```

**Step 2: Run test to verify it fails**
- Expected: `ImportError: No module named rdoc_capture`

**Step 3: Locate correct Python.h / libs**
- Use Everything search for `Python.h`, `python27.dll`, `python27.lib`.
- Verify version by reading `patchlevel.h` (expected 2.7.18, MSC v.1940).

**Step 4: Document header/lib paths**
- Record include/lib paths in plan or README.

**Step 5: Commit**
- `git commit -m "chore(plan): document py27 headers and libs"`

### Task 2: Add native extension source + build script (repo)
**Files:**
- Create: `util/rdoc_quick_capture_py27/rdoc_capture_py27.cpp`
- Create: `util/rdoc_quick_capture_py27/build_py27_capture.cmd`

**Step 1: Write the failing test**
```python
# In-game console
import rdoc_capture
print(rdoc_capture.is_available())
```

**Step 2: Run test to verify it fails**
- Expected: `ImportError` or `False`

**Step 3: Write minimal implementation**
- Add the C++ module above.
- Build with a cmd script that calls `cl /LD` with proper include/lib.

**Step 4: Run test to verify it passes**
- Expected: `import rdoc_capture` succeeds and `is_available()` returns `True` after `load()`.

**Step 5: Commit**
```bash
git add util/rdoc_quick_capture_py27/rdoc_capture_py27.cpp util/rdoc_quick_capture_py27/build_py27_capture.cmd
git commit -m "feat(rdoc): add py27 capture extension source and build script"
```

### Task 3: Deploy `.pyd` into game package
**Files:**
- Copy to: `F:\Code\S1\Package\Script\Python\engine\Lib\rdoc_capture.pyd`

**Step 1: Write the failing test**
```python
import rdoc_capture
```

**Step 2: Run test to verify it fails**
- Expected: ImportError (before copy)

**Step 3: Copy compiled module**
- Copy `rdoc_capture.pyd` into `engine\Lib` (already on `sys.path`).

**Step 4: Run test to verify it passes**
- Expected: import succeeds

**Step 5: Commit**
- (No repo files changed)

### Task 4: Update guide doc (Py27-specific)
**Files:**
- Create: `docs/analysis/rdoc_quick_capture_py27.md`

**Step 1: Write the failing test**
- N/A (doc-only)

**Step 2: Write minimal content**
- Explain why ctypes is missing and how to use `rdoc_capture`.

**Step 3: Verify**
- Review for accuracy vs plan.

**Step 4: Commit**
```bash
git add docs/analysis/rdoc_quick_capture_py27.md
git commit -m "docs(rdoc): add py27 in-process capture guide"
```

---

## Impact Analysis
- Low impact on RenderDoc core (external extension only).
- Main risk is ABI mismatch with embedded Python 2.7.
- If Python headers/libs are not available, we must generate an import lib from `python27.dll`.

## Verification / DoD
- In target UI, `rdoc_capture.trigger_capture()` produces a `.rdc`.
- The `.rdc` opens in RenderDoc and shows the captured frame.

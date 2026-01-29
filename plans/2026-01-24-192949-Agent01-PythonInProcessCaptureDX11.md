# Enable .pyd Dynamic Modules in Embedded Py27 (RenderDoc Capture)

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

## Plan Metadata
- Version: 0.3
- Owner: Agent01
- Last Updated: 2026-01-29
- Plan File: `plans/2026-01-24-192949-Agent01-PythonInProcessCaptureDX11.md`

## Goal
- 在嵌入式 Python 2.7 中**启用 .pyd 动态模块加载**，使 `rdoc_capture.pyd` 可被 import，从而在游戏内触发 RenderDoc 截帧。

## Architecture
- 目标是让 `imp.get_suffixes()` 返回 `.pyd`：这取决于 PythonCore 构建是否包含 **dynload_win/importdl**。
- 在引擎侧定位 Python 初始化与补丁点（例如 `MPython.cpp`, `PythonPatch.cpp`），确认是否禁用了动态模块表 `_PyImport_DynLoadFiletab`。
- 重新构建嵌入式 Python 或修复其构建配置，使 `.pyd` 后缀被注册并可加载。

## Tech Stack
- S1 Engine (C++)
- Embedded Python 2.7.18 (MSC v.1940)
- PythonCore 2.7.18 源码 (`Engine/Sources/External/PythonCore`)
- Windows x64

## Success Criteria (measurable)
- 游戏内 `imp.get_suffixes()` 包含 `.pyd`
- `import rdoc_capture` 成功
- `rdoc_capture.trigger_capture()` 生成 `.rdc`

## Acceptance Criteria
- 目标 UI 内触发的 `.rdc` 可被 RenderDoc 打开并包含 drawcall。

## Verification Commands
- In-game console:
  - `import imp; print(imp.get_suffixes())`  
    Expected: 包含 `('.pyd', ...)`
  - `import rdoc_capture; print(rdoc_capture.is_available())`  
    Expected: `True`
  - `rdoc_capture.set_capture_path(...); rdoc_capture.trigger_capture()`  
    Expected: 新 `.rdc` 输出
- Shell:
  - `tasklist /m renderdoc.dll | findstr /i Game_x64h.exe`  
    Expected: 行内包含 `renderdoc.dll`

## Evidence
- 控制台输出截图（suffixes + is_available）
- `.rdc` 文件路径 `F:\Code\S1\RenderDocCaptures\*.rdc`

## Estimation
- Effort: 0.5–1.5 days
- Story Points: 3
- Original Estimate: 1.5 days

## Risk Register
| Risk | Impact | Likelihood | Mitigation |
|---|---|---|---|
| PythonCore 构建缺失 dynload/importdl | High | Medium | 检查并补齐 dynload_win.c/importdl.c 参与编译 |
| ABI/编译器不匹配 | High | Medium | 使用与游戏一致的工具链 (MSC v.1940) |
| 引擎禁用了动态模块 | High | Medium | 在初始化补丁点恢复动态模块表 |
| 验证依赖用户环境 | Medium | Medium | 明确验证步骤与预期输出 |

## Game Dev: Memory & Resource Budget (Leak Checks)
- `.rdc` 体积大，建议一次性触发，避免频繁捕获。

## Game Dev: Asset Pipeline
- `.rdc` 只作调试产物，固定输出目录 `RenderDocCaptures/`。

## Game Dev: Crash Repro + Dumps/Symbols
- Repro steps: 进入 UI → `rdoc_capture.trigger_capture()`
- Dump/Core: minidump
- Symbols: PDB
- Build identity: 引擎版本 + 脚本版本 + commit

---

## Navigation Evidence (Codemap)

**Queries used**
1) `codemap "PyImport_AppendInittab" -Num 20 -Repo engine_s1`
2) `codemap "PyImport_ExtendInittab" -Num 20 -Repo engine_s1`
3) `codemap "PyImport_ImportModule" -Num 20 -Repo engine_s1`

**Candidate hits (3+)**
- `[engine_s1] Engine/Sources/Programs/PythonMain/PythonMain.cpp:231`  
  `PyImport_AppendInittab("MPythonMain", &PyInit_MPythonMain);`
- `[engine_s1] Engine/Sources/Runtime/Plugins/Python/Source/MPython.cpp:480`  
  `int ret = PyImport_ExtendInittab(_ExtendInittab);`
- `[engine_s1] Engine/Sources/External/PythonCore/Patch/PythonPatch.cpp:150`  
  `PyImport_ExtendInittab(_Builtin_Inittab);`

**Dynload queries used (2026-01-29)**
1) `codemap "PyImport_DynLoadFiletab" -Num 20 -Repo engine_s1`
2) `codemap "PythonCore" -Num 20 -Repo engine_s1`

**Dynload candidate hits (3+)**
- `[engine_s1] Engine/Sources/External/PythonCore/Patch/PythonPatch.cpp:166`  
  `const struct filedescr _PyImport_DynLoadFiletab[] = {`
- `[engine_s1] Engine/Sources/External/PythonCore/Python-2.7.18/Python/dynload_win.c:18`  
  `const struct filedescr _PyImport_DynLoadFiletab[] = {`
- `[engine_s1] Engine/Sources/External/PythonCore/PythonCore.Build.py:11`  
  `class PythonCoreBuildModule(BuildProject.ExternalProject):`

**Follow-up targets**
- `MPython.cpp`（引擎侧 Python 初始化入口）
- `PythonPatch.cpp`（补丁点，可能影响动态模块表）
- `PythonCore.Build.py`（确认 dynload/importdl 编译）
- `PC/pyconfig.h`（确认 HAVE_DYNAMIC_LOADING 宏）

**OpenGrok xref**
- http://127.0.0.1:8080/source/xref/engine_s1/Engine/Sources/Runtime/Plugins/Python/Source/MPython.cpp#480
- http://127.0.0.1:8080/source/xref/engine_s1/Engine/Sources/External/PythonCore/Patch/PythonPatch.cpp#150
- http://127.0.0.1:8080/source/xref/engine_s1/Engine/Sources/External/PythonCore/PythonCore.Build.py#11
- http://127.0.0.1:8080/source/xref/engine_s1/Engine/Sources/External/PythonCore/Python-2.7.18/PC/pyconfig.h#582

---

## Repo / File List

**Engine (likely changes)**
- `Engine/Sources/Runtime/Plugins/Python/Source/MPython.cpp:480`
- `Engine/Sources/External/PythonCore/Patch/PythonPatch.cpp:150`
- `Engine/Sources/External/PythonCore/Python-2.7.18/Python/import.c` (check dynload table)
- `Engine/Sources/External/PythonCore/Python-2.7.18/PC/dynload_win.c` (ensure compiled)
- `Engine/Sources/External/PythonCore/Python-2.7.18/PC/pyconfig.h` (HAVE_DYNAMIC_LOADING)
- `Engine/Sources/External/PythonCore/PythonCore.Build.py` (dynload/importdl build list)

**RenderDoc repo (reference only)**
- `docs/analysis/rdoc_quick_capture_py27.md` (usage)

---

## Approach (Pseudo-code + Full Snippet)

**Check dynamic module support**
```python
import imp
print(imp.get_suffixes())
# Expect to see .pyd
```

**Engine-side fix concept**
```
Ensure dynload_win.c/importdl.c are built into PythonCore.
Ensure _PyImport_DynLoadFiletab is not empty.
Rebuild engine Python runtime.
Enable HAVE_DYNAMIC_LOADING in PC/pyconfig.h.
```

---

## Task Checklist (2–5 min each)

### Task 1: Inspect Python init & patch points
**Files:**
- Read: `Engine/Sources/Runtime/Plugins/Python/Source/MPython.cpp:480`
- Read: `Engine/Sources/External/PythonCore/Patch/PythonPatch.cpp:150`

**Step 1: Write the failing test**
```python
import imp
print(imp.get_suffixes())
```

**Step 2: Verify failure**
- Expected: only `.py` / `.pyc`

**Step 3: Identify where dynamic modules are disabled**
- Note any custom inittab or stripped dynload tables.

**Step 4: Commit (doc-only if applicable)**
```bash
git commit -m "chore(engine): document py27 dynload entry points"
```

### Task 2: Enable dynload/importdl in PythonCore build
**Files:**
- Modify: `Engine/Sources/External/PythonCore/Python-2.7.18/PC/pyconfig.h`
- Verify: `Engine/Sources/External/PythonCore/PythonCore.Build.py`
- Verify: `PC/dynload_win.c` is compiled

**Step 1: Write failing test**
```python
import imp
print(imp.get_suffixes())
```

**Step 2: Enable dynload (root cause)**
- Define `HAVE_DYNAMIC_LOADING` in `PC/pyconfig.h` (**done**)
- Confirm `dynload_win.c` and `importdl.c` stay in build list

**Step 3: Rebuild engine**
- Build command per engine pipeline

**Step 4: Verify**
- Expected: suffix list includes `.pyd`

**Step 5: Commit**
```bash
git commit -m "fix(engine): enable py27 dynload for .pyd"
```

### Task 3: Validate `rdoc_capture.pyd` import
**Files:**
- Use existing `rdoc_capture.pyd` in `engine\Lib`

**Step 1: Run test**
```python
import rdoc_capture
print(rdoc_capture.is_available())
```

**Step 2: Verify capture**
```python
rdoc_capture.set_capture_path(r"F:\Code\S1\RenderDocCaptures\capture")
rdoc_capture.trigger_capture()
```

**Step 3: Evidence**
- `.rdc` output path

---

## Impact Analysis
- 修改引擎 PythonCore 构建配置，风险集中在 Python 运行时行为变化。
- 如果引擎禁用了动态模块加载作为安全策略，需评估安全风险。

## Verification / DoD
- `imp.get_suffixes()` 返回 `.pyd`
- `import rdoc_capture` 成功
- `.rdc` 捕获成功并可回放

# Malioc 2026.0 Integration + Shader Metrics Expansion Plan

**Date:** 2026-02-26  
**Owner:** Agent01  
**Stage:** /do  
**Scope:** Upgrade malioc path/version, fix GPU list discovery, expand Mali shader metrics in native Analyzer Report UI

> MCP unavailable (Transport closed). This plan is based on local `rg` + file reads.

## Scope / Assumptions

**In scope**
- Vendor tool copy into repo (user approved): `tools/malioc/2026.0/`
- malioc path resolution: repo-first, then system install fallback
- Fix GPU list discovery to use `malioc --list` (v8.8.1)
- Expand Mali shader metrics in native Qt report (fields + columns + export)
- Update docs to explain local malioc usage and limitations

**Out of scope**
- Adding new GPU counter backends or HW performance counters
- Changing replay pipeline or shader extraction logic

**Assumptions**
- Redistribution of Arm Performance Studio binaries in repo is acceptable (user confirmed)
- Repo may contain large binary payloads; no automated compression
- We keep analyzer JSON contract backward compatible (new fields additive)

## Build / Test / Lint Quick Guide (record only, no execution in /plan)

**Build (Windows, required by user)**
```
"E:\Program Files\Microsoft Visual Studio\2022\Community\MSBuild\Current\Bin\MSBuild.exe" renderdoc.sln /p:Configuration=Development /p:Platform=x64 /m
# Expect: Build succeeded, 0 errors
```

**Unit tests**
```
D:\Code\git\renderdoc\x64\Development\qrenderdoc.exe --unittest
# Expect: exit code 0
```

**Manual acceptance (after /do)**
- Open capture → Window → Analyzer Report
- Shaders tab: run Mali analysis, verify columns and sorting

## File List (precise locations)

1) `scripts/rdc_analyzer/mali_analyzer.py`
- `22`: DEFAULT_MALIOC_PATH
- `95-116`: `_validate_malioc()`
- `461-474`: `get_available_gpu_cores()` (currently uses `--list-cores`)

2) `qrenderdoc/Windows/AnalyzerReportViewer.cpp`
- `129-173`: `MaliShaderMetrics` struct
- `354-364`: `PopulateMaliGpuList()` (static list)
- `587-695`: `ApplyMaliAnalysisResults()` JSON parsing + field mapping

3) `qrenderdoc/Code/Analyzer/AnalyzerTypes.h`
- `80-107`: `AnalyzerShaderRow` Mali fields

4) `qrenderdoc/Windows/AnalyzerModels.h`
- `126-156`: `AnalyzerShaderModel::Columns`

5) `qrenderdoc/Windows/AnalyzerModels.cpp`
- `504-533`: shader column display values
- `583-606`: sort comparators
- `720-765`: mali cost sorting test

6) `qrenderdoc/Code/Analyzer/AnalyzerContract.cpp`
- `120-127`: Mali JSON export fields

7) New docs
- `tools/malioc/README.md` (new)
- `scripts/rdc_analyzer/docs/MALI_INTEGRATION_SUMMARY.md` (update path + version)

## Design / Pseudocode

### 1) Malioc path resolution (repo-first)
```py
# scripts/rdc_analyzer/mali_analyzer.py
REPO_ROOT = Path(__file__).resolve().parents[2]
REPO_MALIOC = REPO_ROOT / "tools" / "malioc" / "2026.0" / "mali_offline_compiler" / "malioc.exe"
DEFAULT_MALIOC_PATH = str(REPO_MALIOC)

def _resolve_malioc_path():
    env = os.environ.get("MALIOC_PATH")
    if env and Path(env).exists():
        return env
    if REPO_MALIOC.exists():
        return str(REPO_MALIOC)
    # fallbacks
    for p in [
        r"C:\Program Files\Arm\Arm Performance Studio 2026.0\mali_offline_compiler\malioc.exe",
        r"D:\Program Files\Arm\Arm Performance Studio 2025.3\mali_offline_compiler\malioc.exe",
    ]:
        if Path(p).exists():
            return p
    return str(REPO_MALIOC)  # fallback for error message
```

### 2) GPU core list from `--list`
```py
def get_available_gpu_cores(malioc_path: str = None) -> List[str]:
    malioc = malioc_path or _resolve_malioc_path()
    result = subprocess.run([malioc, "--list"], capture_output=True, text=True, timeout=10)
    cores = []
    for line in result.stdout.splitlines():
        line = line.strip()
        if not line or "architecture" in line or line.startswith("="):
            continue
        if "(" in line:
            name = line.split("(")[0].strip()
            cores.append(name)
    return cores
```

### 3) Extend Mali fields in AnalyzerShaderRow
```cpp
// AnalyzerTypes.h
float maliTotalCycles = 0.0f;
float maliShortestPath = 0.0f;
float maliLongestPath = 0.0f;
float maliFmaCycles = 0.0f;
float maliCvtCycles = 0.0f;
float maliSfuCycles = 0.0f;
float maliLoadStoreCycles = 0.0f;
float maliTextureCycles = 0.0f;
float maliVaryingCycles = 0.0f;
uint32_t maliUniformRegs = 0;
rdcstr maliBound; // A/LS/T/V, computed by max cycle bucket
```

### 4) Parse JSON fields & compute bound
```cpp
// AnalyzerReportViewer.cpp
struct MaliShaderMetrics
{
  bool valid = false;
  double totalCycles = 0.0;
  double shortestPath = 0.0;
  double longestPath = 0.0;
  double fmaCycles = 0.0;
  double cvtCycles = 0.0;
  double sfuCycles = 0.0;
  double loadStoreCycles = 0.0;
  double textureCycles = 0.0;
  double varyingCycles = 0.0;
  uint32_t workRegs = 0;
  uint32_t uniformRegs = 0;
  uint32_t spillCount = 0;
  rdcstr error;
};

static rdcstr ComputeMaliBound(const MaliShaderMetrics &m)
{
  double arith = m.fmaCycles + m.cvtCycles + m.sfuCycles;
  double ls = m.loadStoreCycles;
  double tex = m.textureCycles;
  double var = m.varyingCycles;
  double maxVal = arith;
  const char *bound = "A";
  if(ls > maxVal) { maxVal = ls; bound = "LS"; }
  if(tex > maxVal) { maxVal = tex; bound = "T"; }
  if(var > maxVal) { maxVal = var; bound = "V"; }
  return bound;
}
```

### 5) Update model columns + export
```cpp
// AnalyzerModels.h Columns (add)
ColMaliTotalCycles,
ColMaliShortestPath,
ColMaliLongestPath,
ColMaliUniformRegs,
ColMaliFmaCycles,
ColMaliCvtCycles,
ColMaliSfuCycles,
ColMaliLoadStoreCycles,
ColMaliTextureCycles,
ColMaliVaryingCycles,
ColMaliBound,

// AnalyzerContract.cpp (add fields)
"mali_total_cycles", "mali_shortest_path", "mali_longest_path",
"mali_uniform_registers", "mali_fma_cycles", "mali_cvt_cycles",
"mali_sfu_cycles", "mali_load_store_cycles", "mali_texture_cycles",
"mali_varying_cycles", "mali_bound"
```

## Impact Analysis

- **Binary size**: repo grows due to malioc binaries; expect large diff.
- **UI width**: shader table becomes wide; header auto-fit + manual resize already enabled.
- **Backwards compatibility**: new fields are additive; existing JSON readers unaffected.
- **Performance**: parsing more fields is O(n shaders), negligible compared to malioc runtime.

## Task Checklist (2–5 min steps, full code)

### Task 1 — Copy malioc 2026.0 into repo
- [x] Create `tools/malioc/2026.0/` and copy full `mali_offline_compiler` folder
- [x] Add `tools/malioc/README.md` with version, usage, and path

### Task 2 — mali_analyzer.py path + list fix
- [x] Implement `_resolve_malioc_path()` (env → repo → system)
- [x] Update `DEFAULT_MALIOC_PATH` to repo path
- [x] Change `get_available_gpu_cores()` to `--list` parsing
- [x] Update CLI output to show resolved path

### Task 3 — Expand AnalyzerShaderRow
- [x] Add new Mali fields (cycles, regs, bound) in `AnalyzerTypes.h`

### Task 4 — Parse extra JSON metrics
- [x] Extend `MaliShaderMetrics` + parsing in `ApplyMaliAnalysisResults()`
- [x] Compute `maliBound` from A/LS/T/V buckets

### Task 5 — UI columns + sorting
- [x] Add columns to `AnalyzerShaderModel` (header + data)
- [x] Extend sorting comparators for numeric columns
- [x] Update analyzer tests for new column sorting (at least one new column)

### Task 6 — Export contract
- [x] Add new fields to `AnalyzerContract.cpp` shader JSON export

### Task 7 — Docs
- [x] Update `scripts/rdc_analyzer/docs/MALI_INTEGRATION_SUMMARY.md` to reference repo path + v8.8.1
- [x] Note `malioc --list` usage and bound interpretation (A/LS/T/V)

## Decisions / Risks

**Decisions**
1) Repo-first malioc path; system install is fallback.
2) Bound is derived from cycle buckets (A/LS/T/V) and marked as derived.

**Risks**
- Redistribution/EULA risk: if Arm license disallows rehosting, we must remove binaries and document install.
- Large binary payload could slow repo operations.

## Verification / Acceptance (Definition of Done)

1) `malioc` resolved from repo path and `--version` passes.
2) GPU list in UI includes new 2026.0 cores (e.g. Mali G1 / Immortalis-G925).
3) Shader table shows full Mali metrics and can sort by major numeric columns.
4) Analyzer JSON export includes new fields.
5) `qrenderdoc.exe --unittest` passes.

## /do Execution Log

### 2026-02-26 23:54 (Agent continuation)

- [x] **Malioc 2026.0 repo integration + shader metrics expansion completed**
  - Repo-first malioc resolution + `MALIOC_PATH` override + system fallback
  - GPU core list now parsed from `malioc --list`
  - Shader rows include full Mali metrics + bound classification + sortable columns
  - JSON export extended with new Mali fields (kept backward alias `mali_cycles`)
- [x] **Verification**
  - MSBuild (Development|x64): PASS (`0 warning, 0 error`)
  - `qrenderdoc.exe --unittest`: PASS (exit 0)
  - `py -3 -m py_compile scripts/rdc_analyzer/mali_analyzer.py`: PASS
- [ ] **Next pending**
  - Manual GUI validation: Shaders tab shows new Mali columns, sorting works, GPU list includes 2026.0 cores

## Next Step
- Manual GUI validation by you, then we can commit and proceed to next dimension work.

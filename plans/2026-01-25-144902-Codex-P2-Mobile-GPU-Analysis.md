# P2 Mobile GPU Analysis Implementation Plan

## Plan Metadata
- Version: 2026.01.25
- Owner: Codex
- Last Updated: 2026-01-25
- Plan File: plans/2026-01-25-144902-Codex-P2-Mobile-GPU-Analysis.md

## Goal
- 按顺序完成 P2-3 Tile-Based 分析、P2-2 Adreno 启发式分析、P2-2 Adreno Profiler 集成，并接入现有 A-first 管线输出。

## Architecture
- 在现有 `AnalysisPipeline` 上新增 Tile-Based 与 Adreno 两个分析分支；Tile-Based 通过 Pass/RT/纹理/绘制数据做启发式检测并输出 CanonicalIssue；Adreno 分析先走启发式，Profiler 集成以“可选 CLI”方式降级运行。
- Tile-Based 规则在 `rules/` 中注册，确保 `RULES.md` 自动生成；`TileBasedAnalyzer` 负责准备数据与将规则结果转为 CanonicalIssue。

## Tech Stack
- Python 3.x (py -3), RenderDoc Python API (可选), rdc_analyzer 现有 Analyzer/Rule/Schema 体系。

## Success Criteria (measurable)
- CLI 支持 `--enable-tile-analysis` 与 `--tile-gpu`，并能生成非空的 Tile-Based issues（在模拟数据测试中）。
- Adreno 启发式分析在无外部工具时可运行且输出 issues；Profiler CLI 缺失时可降级并产生可追踪提示。
- `RULES.md` 自动生成后包含 TILE 规则条目。
- `py -3 -m pytest scripts/rdc_analyzer/tests -q -rs` 0 failures。

## Acceptance Criteria
- JSON 输出中 issues 包含 TILE_001..006 与 ADRENO_001..003（至少在单元测试里验证）。
- 文档更新清单 4 项完成：README、RULES、WORK_SUMMARY_2025-01-21、ARCHITECTURE_V1。

## Verification Commands
- `py -3 -m pytest scripts/rdc_analyzer/tests/test_tile_based_analyzer.py -v` (Expected: all PASS)
- `py -3 -m pytest scripts/rdc_analyzer/tests/test_adreno_analyzer.py -v` (Expected: all PASS)
- `py -3 -m pytest scripts/rdc_analyzer/tests -q -rs` (Expected: 0 failures)
- `py -3 -m rdc_analyzer.scripts.generate_rules_doc --write` (Expected: RULES.md updated, no errors)

## Evidence
- 测试输出日志（pytest）。
- 更新后的 `scripts/rdc_analyzer/RULES.md`、README、ARCHITECTURE、WORK_SUMMARY。

## Estimation
- Effort: 2-3 days (Tile-Based) + 1-2 days (Adreno heuristic) + 3-5 days (Profiler integration research)
- Story Points: 8-13
- Original Estimate: P2 design doc

## Risk Register
| Risk | Impact | Likelihood | Mitigation |
|---|---|---|---|
| RenderPass/Load-Store 数据不足 | Tile 规则误报/漏报 | High | 先做启发式 + truthful degradation，Profiler/Replay 有数据时再升级 |
| Snapdragon Profiler CLI 不可用 | Profiler 集成不可验证 | Medium | 提供可选路径，缺失时降级并提示 |
| 规则与现有 Mobile/Pass 规则重复 | 规则重复或冲突 | Medium | 在规则实现中去重/合并阈值，文档标注差异 |
| 规则文档生成遗漏 | 文档与实现不一致 | Low | 强制走 generate_rules_doc 更新 |

## Decisions
- 2026-01-25：启用 TDD（RED → GREEN → REFACTOR），后续实现先写失败测试。
- 2026-01-25：执行顺序调整为“先补充 Tile/Adreno 单测 → 再实现对应分析器与集成”。

## Game Dev: Memory & Resource Budget (Leak Checks)
- 关注 tile memory 估算与 RT 资源字节数；验证阶段记录 tile memory 估算值与阈值对比。

## Game Dev: Asset Pipeline
- 不新增资产；仅增加分析规则与文档。若引入新样本，放入 tests/fixtures 并通过 conftest_local.py 引用。

## Game Dev: Crash Repro + Dumps/Symbols
- Repro steps: 运行单测 + 可选带样本的 analyze 命令
- Dump/Core: (minidump | core dump) N/A (Python-only)
- Symbols: (PDB | dSYM | ELF | DWARF) N/A
- Build identity: (build id | commit hash | git commit) 记录当前提交

## Scope
- In: Tile-Based Analyzer, Adreno Analyzer (heuristic + optional CLI), CLI 参数、规则与文档更新、测试覆盖。
- Out: RenderDoc C++ 侧修改、实时 GPU Profiling 深度集成、真实硬件测量精度对齐。

## Assumptions
- 现有 CaptureData / PassAnalyzer 可提供最小 pass/RT 信息；缺失字段采用 estimated/missing 降级。
- 用户可提供 Snapdragon Profiler CLI 或接受启发式模式。

## Repo / File List (line-specific)
- Modify: `scripts/rdc_analyzer/main.py:36-106` (AnalysisOptions: tile/adreno flags)
- Modify: `scripts/rdc_analyzer/main.py:640-720` (analysis pipeline: run tile/adreno)
- Modify: `scripts/rdc_analyzer/main.py:845-1120` (add _run_tile_based_analysis/_run_adreno_analysis)
- Modify: `scripts/rdc_analyzer/main.py:1179-1340` (export report: include tile/adreno summary if needed)
- Modify: `scripts/rdc_analyzer/main.py:1495-1690` (coverage details: tile/adreno)
- Modify: `scripts/rdc_analyzer/__main__.py:57-131` (CLI args for analyze)
- Modify: `scripts/rdc_analyzer/__main__.py:425-520` (cmd_analyze -> AnalysisOptions)
- Modify: `scripts/rdc_analyzer/__main__.py:1211-1235` (alternate entry -> AnalysisOptions)
- Modify: `scripts/rdc_analyzer/config/thresholds.py:64-210` (tile thresholds)
- Modify: `scripts/rdc_analyzer/config.py:16-171` (Adreno profiler path/env)
- Modify: `scripts/rdc_analyzer/rules/__init__.py:29-44` (import tile_based rules)
- Create: `scripts/rdc_analyzer/analyzers/tile_based_analyzer.py` (new)
- Create: `scripts/rdc_analyzer/analyzers/tile_based_rules.py` (new data table)
- Create: `scripts/rdc_analyzer/core/tile_memory.py` (new)
- Create: `scripts/rdc_analyzer/rules/tile_based.py` (RuleRegistry entries)
- Create: `scripts/rdc_analyzer/analyzers/adreno_analyzer.py` (new)
- Create: `scripts/rdc_analyzer/tests/test_tile_based_analyzer.py` (new)
- Create: `scripts/rdc_analyzer/tests/test_adreno_analyzer.py` (new)
- Modify: `scripts/rdc_analyzer/README.md:5-140` (usage + CLI)
- Modify: `docs/analysis/codex_rdc_analyzer/WORK_SUMMARY_2025-01-21.md:7-30` (结构索引更新)
- Modify: `scripts/rdc_analyzer/docs/ARCHITECTURE_V1.md:133-140` (analyzers 列表)
- Modify: `scripts/rdc_analyzer/docs/ARCHITECTURE_V1.md:271-280` (分析模块表)
- Modify: `scripts/rdc_analyzer/RULES.md:1-400` (auto-generated)

## Approach (Pseudo-code)

### Tile-Based Analyzer (P2-3)
```
class TileBasedAnalyzer:
  def analyze(capture):
    pass_info = derive_passes(capture)  # 现有 PassAnalyzer + draw_calls
    tile_cfg = TileMemoryConfig.for_gpu(tile_gpu)
    for pass in pass_info:
      overdraw = estimate_overdraw(pass, frame_summary)
      tile_bytes = estimate_tile_memory(pass, tile_cfg)
      load_store = estimate_load_store(pass)  # 若无数据 -> skip/estimated
      issues += evaluate_tile_rules(overdraw, tile_bytes, load_store, thresholds)
    return issues
```

### Adreno Analyzer (P2-2 heuristic)
```
class AdrenoHeuristicAnalyzer:
  def analyze(capture):
    issues = []
    issues += check_gmem_bandwidth(capture)
    issues += check_texture_decompress(capture)
    issues += estimate_alu_pressure(capture)
    return issues
```

### Adreno Profiler CLI (P2-2 profiler)
```
if profiler_cli_available:
  run_profiler(shader_sources, gpu)
  parse json/xml -> issues
else:
  add info issue (tool missing) + continue
```

## Impact Analysis
- 新规则会增加 issues 输出数量，可能影响报告评分与建议生成。
- Tile-Based 规则在数据缺失时使用估算，需在 evidence 中标记 estimated/missing。
- Profiler CLI 依赖外部工具，默认需要降级路径。

## Action Items (checkbox)
- [x] Task 1: 扩展 AnalysisOptions + CLI 参数
  - Files: `scripts/rdc_analyzer/main.py:36-106`, `scripts/rdc_analyzer/__main__.py:57-131`, `scripts/rdc_analyzer/__main__.py:425-520`
  - Code: add flags `enable_tile_analysis`, `tile_gpu`, `enable_adreno_analysis`, `adreno_mode`, `adreno_profiler_path`
  - Commit: `feat(rdc-analyzer): add tile/adreno analysis options`

- [x] Task 2: Tile Memory 模型与规则表
  - Files: create `core/tile_memory.py`, `analyzers/tile_based_rules.py`, modify `config/thresholds.py:64-210`
  - Code: `TileMemoryConfig.for_gpu()` + thresholds (`tile_overdraw_ratio`, `tile_memory_kb`, `tile_rt_bytes`)
  - Commit: `feat(rdc-analyzer): add tile memory model and thresholds`

- [x] Task 3: Tile-Based 规则实现
  - Files: create `rules/tile_based.py`, modify `rules/__init__.py:29-44`
  - Code (example):
    ```
    class TileOverdrawRule(BaseRule):
      rule_id = "TILE_001"
      def check(self):
        ratio = compute_overdraw(self.context)
        if ratio > threshold: issue(...)
    ```
  - Commit: `feat(rdc-analyzer): add tile-based rules`

- [x] Task 4: Tile-Based Analyzer 集成
  - Files: create `analyzers/tile_based_analyzer.py`, modify `main.py:640-720,845-1120`
  - Steps:
    1) Build pass summary from context
    2) Compute tile metrics
    3) Emit issues into self._issues
  - Commit: `feat(rdc-analyzer): integrate tile-based analyzer`

- [x] Task 5: Adreno Heuristic Analyzer
  - Files: create `analyzers/adreno_analyzer.py`, modify `main.py:640-720,845-1120`, `config.py:16-171`
  - Include GPU list + heuristic issue map (`ADRENO_001..003`)
  - Commit: `feat(rdc-analyzer): add adreno heuristic analyzer`

- [x] Task 6: Adreno Profiler CLI integration (optional path)
  - Files: `analyzers/adreno_analyzer.py`, `main.py`
  - Add CLI path detection + parse stub output
  - Commit: `feat(rdc-analyzer): add adreno profiler cli hook`

- [x] Task 7: Tests
  - Files: `scripts/rdc_analyzer/tests/test_tile_based_analyzer.py`, `.../test_adreno_analyzer.py`
  - Commands:
    - `py -3 -m pytest scripts/rdc_analyzer/tests/test_tile_based_analyzer.py -v`
    - `py -3 -m pytest scripts/rdc_analyzer/tests/test_adreno_analyzer.py -v`
  - Commit: `test(rdc-analyzer): add tile/adreno analyzer tests`

- [x] Task 8: 文档更新 + RULES 生成
  - Files: `README.md:5-140`, `WORK_SUMMARY_2025-01-21.md:7-30`, `ARCHITECTURE_V1.md:133-140,271-280`, `RULES.md`
  - Command: `py -3 -m rdc_analyzer.scripts.generate_rules_doc --write`
  - Commit: `docs(rdc-analyzer): update tile/adreno docs and rules`

## Verification / DoD
- pytest 全绿
- RULES.md 自动生成包含 TILE 规则
- CLI help 输出包含新增参数

## Open Questions
- Snapdragon Profiler CLI 是否可用？其输出格式（JSON/XML）确定吗？
- Tile memory 阈值与 overdraw 阈值是否需要与现有 mobile 规则统一？
- 是否需要在 HTML 报告中新增 Tile/Adreno 专区（或仅 issues 列表即可）？

## Progress Log
- 2026-01-26: 补齐 P2 设计缺口（RenderPass 解析→PassInfo→Tile 规则对齐）
  - 连接 XML renderPassInfos 到 ParsedData/PassAnalyzer；补充 marker/attachment 字段
  - Tile 规则与设计对齐：TILE_003~006 分别为 Load/Store、MSAA Resolve、Transient、Debug Marker
  - Adreno GPU 列表补全（A5xx/A6xx/A7xx），CLI 入口保留降级提示
  - 文档：P2 设计状态与 ROADMAP 勾选完成；RULES.md 重新生成
  - 验证：pytest tile/adreno 单测通过

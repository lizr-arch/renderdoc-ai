# Continue2 P0 收敛 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Version:** 2026-01-23  
**Owner:** Codex  
**Last Updated:** 2026-01-23  
**Plan File:** `plans/2026-01-23-224804-Codex-Continue2-P0-Implementation-Plan.md`  

**Goal:** 将 `scripts/rdc_analyzer` 的单帧/对比链路收敛到统一 Canonical Schema，并补齐“证据链 + 建议 + 验证计划”的最小闭环。  

**Architecture:** 以 `main.py` 作为唯一主链路，统一输出 Canonical Schema；compare 接受 `.rdc` 或 Canonical JSON 并统一 diff 输出；RuleRunner/阈值注入/真实数据链作为主链路必经步骤。  

**Tech Stack:** Python 3, RenderDoc Python API, pytest, rdc_analyzer modules.  

**Success Criteria (measurable):**
- `python -m rdc_analyzer analyze` 输出的 JSON 与 compare 输入结构一致（无 Phase1 兼容分支触发）。
- compare 对 `.rdc` 或 Canonical JSON 生成的 diff 不再包含“空列表占位/估算字段补齐”路径。
- 覆盖率/生命周期/管线状态不再标记为 `estimated`（至少在回放可用时）。

**Acceptance Criteria:**
- 单帧结果与对比结果字段一致，可机器消费。
- 建议包含统一 `verification_plan` 字段，可直接落地验证。
- 规则输出由 RuleRunner 统一产出 canonical issues。

**Verification Commands:**
- `cd scripts/rdc_analyzer && py -3 -m pytest -q -rs`  
  Expected: `all tests passed`（无新增失败）
- `cd scripts/rdc_analyzer && py -3 -m rdc_analyzer analyze <sample.rdc> -o output --format json`  
  Expected: `analysis.json` 含 `schema_version` 与 `coverage/issues/suggestions/preflight`
- `cd scripts/rdc_analyzer && py -3 -m rdc_analyzer compare <baseline.rdc> <target.rdc> -o compare_out`  
  Expected: 生成 `compare_*.html` 与 `diff_*.json`

**Evidence:**
- 产物路径：`docs/analysis/codex_rdc_analyzer/2026-01-23-rdc-analyzer-continue2-report.md`

**Estimation:**
- Effort: 2-3 days
- Story Points: 8
- Original Estimate: 2 days

**Risk Register (impact/likelihood/mitigation):**
- 高：回放依赖 GPU/驱动环境不可用 → 提供 mock/最小样例 + 降级策略说明。
- 中：历史 Phase1/Phase2 schema 共存 → 明确迁移期策略与弃用时间点。
- 中：规则/阈值口径不一致 → 添加 schema/thresholds 单测锁定。

## Game Dev: Memory & Resource Budget (Leak Checks)
- 需要检查 Replay/资源跟踪的内存增长：使用固定 1-2 个 capture 重复跑 10 次，记录 `analysis.json` size 与内存占用变化。

## Game Dev: Asset Pipeline
- 资源路径需统一：`output/` 作为唯一产物目录；compare 输出与 analyze 输出采用固定命名规范，避免脚本各自写不同目录。

## Game Dev: Crash Repro + Dumps/Symbols
- 回放崩溃需保留 capture、日志与渲染 API 信息；若触发 native crash，记录 RenderDoc 版本与驱动版本，保留堆栈或 minidump。

---

## File List（精确到行号范围）
- `scripts/rdc_analyzer/main.py:1050-1790`（schema 输出、coverage、suggestions、preflight）  
- `scripts/rdc_analyzer/main.py:450-620`（_analyze_rules / performance analysis）  
- `scripts/rdc_analyzer/pipeline.py:23-120`（旧管线入口与 context 创建）  
- `scripts/rdc_analyzer/parsers/base.py:59-70`（thresholds 注入）  
- `scripts/rdc_analyzer/compare_rdc.py:120-210`（Phase1/Phase2 兼容分支）  
- `scripts/rdc_analyzer/__main__.py:527-650`（cmd_compare 主入口）  
- `scripts/rdc_analyzer/extractors/replay_wrapper.py:109-200`（ReplayWrapper 基本能力）  
- `scripts/rdc_analyzer/rules/base.py:15-160` & `rules/runner.py:14-120`（RuleRunner 体系）

## Pseudocode（关键改动示意）
```python
# 1) Canonical schema 作为唯一输出
analysis = AnalysisPipeline(...).run()
canonical = build_canonical_schema(analysis)  # 统一字段
write_json(canonical, output_path)

# 2) compare 支持 rdc -> canonical -> diff
baseline = load_capture_file(baseline_path)  # 如果是 .rdc
target = load_capture_file(target_path)
baseline_json = to_canonical(baseline)
target_json = to_canonical(target)
diff = DiffEngine().compare(baseline_json, target_json)
```

## Impact Analysis
- 正面：单帧与对比链路一致，证据链可被自动化验证。
- 负面：迁移期需要处理旧输出的兼容，可能影响历史数据复用。

## Task Checklist（2-5 分钟粒度，含 TDD）

### P0-1 Canonical Schema 统一
- [x] 写失败测试：compare 读取 `analysis.json` 不再触发 Phase1 分支  
- [x] 运行失败测试（确认失败原因）  
- [x] 最小实现：输出统一字段并移除 Phase1 兼容分支  
- [x] 运行测试：`py -3 -m pytest -q -rs`  
- [x] 提交：`feat(rdc-analyzer): unify canonical schema for analyze/compare`

### P0-2 真实数据链接入
- [x] 写失败测试：pipeline_state/resource_lifecycle 不再为 `estimated`  
- [x] 运行失败测试  
- [x] 最小实现：接入 ReplayWrapper/ResourceTracker  
- [x] 运行测试：`py -3 -m pytest -q -rs`  
- [x] 提交：`feat(rdc-analyzer): wire replay-backed state into pipeline`

### P0-3 规则输出统一
- [x] 写失败测试：RuleRunner 输出能被 canonicalize  
- [x] 运行失败测试  
- [x] 最小实现：_analyze_rules 接入 RuleRunner  
- [x] 运行测试：`py -3 -m pytest -q -rs`  
- [x] 提交：`feat(rdc-analyzer): unify rule output pipeline`

### P0-4 compare 入口闭环化
- [x] 写失败测试：compare 直接接受 `.rdc` 输出 diff  
- [x] 运行失败测试  
- [x] 最小实现：cmd_compare 内部分析 -> canonical -> diff  
- [x] 运行测试：`py -3 -m pytest -q -rs`  
- [x] 提交：`feat(rdc-analyzer): compare accepts rdc and canonical json`

### P0-5 verification_plan 字段标准化
- [x] 写失败测试：verification_plan 字段一致性  
- [x] 运行失败测试  
- [x] 最小实现：统一命名与枚举值  
- [x] 运行测试：`py -3 -m pytest -q -rs`  
- [x] 提交：`feat(rdc-analyzer): standardize verification_plan schema`

### P0-6 thresholds 注入一致性
- [x] 写失败测试：AnalysisContext 总有 thresholds  
- [x] 运行失败测试  
- [x] 最小实现：统一使用 create_context 或显式传入 thresholds  
- [x] 运行测试：`py -3 -m pytest -q -rs`  
- [x] 提交：`fix(rdc-analyzer): ensure thresholds are always injected`

---

**Approval:** WAIT for user confirmation before entering /do.

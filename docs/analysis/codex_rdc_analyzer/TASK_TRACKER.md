# RDC Analyzer 任务追踪表

> **创建日期**: 2025-01-20  
> **最后更新**: 2025-01-23  
> **目标**: 完成单帧极致分析 + 双帧全方位对比  
> **环境**: Windows PC + D3D11/D3D12 RDC 文件

---

## 📊 总体进度

| 阶段 | 状态 | 进度 |
|------|:----:|------|
| Phase 1: 工程治理 | ✅ 已完成 | 3/3 |
| Phase 2: 单帧分析增强 | ✅ 已完成 | 4/4 |
| Phase 3: 双帧对比 | ✅ 已完成 | 3/3 |
| Phase 4: 真实数据集成 | ✅ 已完成 | 2/2 |
| **A-first 闭环** | ✅ **已完成** | 11/11 |
| Phase 5: B-mode 统计对比 | ✅ 已完成 | 4/4 |

---

## ✅ A-first 闭环已完成（2025-01-23 复审）

> **结论**: 验证链缺口已补齐，A-first 作为可验收基线成立。  
> **当前验证记录**:
> - `py -3 -m pytest -q -rs`（在 `scripts/rdc_analyzer` 下执行）  
> - 实测：**501 passed, 8 skipped**  
> **执行计划**: `plans/2025-01-20-152300-Codex-A-first-execution-plan.md`

### Blockers（必须先补齐）

1) **P0-NEW-5 测试归属缺口**：`scripts/rdc_analyzer/tests/test_rdc_loader.py`、`test_schema_bridge.py` 未纳入 Git → 结果不可复现。  
2) **P0-NEW-6 默认验证遗漏关键测试**：P0-NEW-2 / PipelineSampler 测试在 `tests/` 根目录，默认 `scripts/rdc_analyzer` pytest 不会覆盖。  
3) **P0-NEW-7 集成测试被跳过**：`test_bridge_integration.py` 存在 import/skip 风险，需修复。

### DoD 完成清单（功能实现层面）

| DoD | 状态 | 关键实现 |
|-----|:----:|----------|
| 7.1 CLI 端到端贯通 | ✅ | `analyze` + `compare` 命令完整 |
| 7.2 Schema 稳定 | ✅ | `schema_version: "1.0"` + 6 个标准块 |
| 7.3 DataQuality/Confidence | ✅ | `_build_coverage_report()` 加权算法 |
| 7.4 Evidence Chain | ✅ | `_canonicalize_issues()` → event_ids/resource_ids |
| 7.5 Playbook 建议 | ✅ | steps/expected_impact/risk/engine_howto |
| 7.6 验证方法 | ✅ | verification_plan 集成到 suggestion |
| 7.7 Capture Preflight | ✅ | `_build_preflight()` 检测缺失 Markers |
| 7.8 工程质量底线 | ✅ | 501 passed (2025-01-23) + test_dod_compliance.py |

> 注：7.8 的“测试全绿”在功能实现层面已满足，但**验证链**仍受 P0-NEW-5/6/7 影响（可复现性/覆盖范围需补齐）。

---

## Phase 0: 验证链完整性（P0）✅ 已完成

### TASK-P0-01: 测试归属与可复现性（P0-NEW-5）

| 字段 | 内容 |
|------|------|
| **状态** | ✅ 已完成 |
| **WHAT** | 让 `scripts/rdc_analyzer/tests/test_rdc_loader.py`、`test_schema_bridge.py` 被 Git 跟踪 |
| **WHY** | 当前结果依赖本地未提交文件，别人无法复现同样的测试通过结论 |
| **HOW** | 调整 `.gitignore` 允许追踪测试文件，或迁移到 `tests/rdc_analyzer/` 并更新 pytest discovery |
| **验证** | `py -3 -m pytest scripts/rdc_analyzer/tests -q` |

### TASK-P0-02: 默认验证覆盖关键集成测试（P0-NEW-6）

| 字段 | 内容 |
|------|------|
| **状态** | ✅ 已完成 |
| **WHAT** | 将 `tests/test_schema_bridge_integration.py` 与 `tests/test_pipeline_sampler.py` 纳入默认验证 |
| **WHY** | 这两项直接证明 “bridge→diff” 与 “pipeline sampling” 的可信性，缺失会导致闭环不可验 |
| **HOW** | 通过 `pytest.ini` 将根 `tests/` 纳入默认 `testpaths`，实现单命令验证 |
| **验证** | `py -3 -m pytest -q -rs`（在 `scripts/rdc_analyzer` 下执行，pytest.ini 已包含根 tests） |

### TASK-P0-03: 修复 bridge 集成测试跳过（P0-NEW-7）

| 字段 | 内容 |
|------|------|
| **状态** | ✅ 已完成 |
| **WHAT** | 修复 `test_bridge_integration.py` 的 import/skip 问题，确保默认可跑 |
| **WHY** | XML→Context 是 A-first 证据链的重要一环，跳过即断链 |
| **HOW** | 统一为绝对导入 `rdc_analyzer.core.*`，减少动态加载的路径不确定性 |
| **验证** | `py -3 -m pytest scripts/rdc_analyzer/tests/test_bridge_integration.py -q -rs` |

---

## Phase 1: 工程治理（基础设施）✅ 已完成

### TASK-P1-01: 修复测试红灯 [P0-5] ✅

| 字段 | 内容 |
|------|------|
| **状态** | ✅ 已完成 (2025-01-20) |
| **完成记录** | 导出 HTML_TEMPLATE + 重命名 integration 测试 |
| **验收结果** | 370 passed, 5 skipped |

---

### TASK-P1-02: 统一 Issue 数据结构 [P0-3] ✅

| 字段 | 内容 |
|------|------|
| **状态** | ✅ 已完成 (2025-01-20) |
| **完成记录** | 添加 `CanonicalIssue` dataclass + `to_canonical()` 方法 |
| **代码入口** | `scripts/rdc_analyzer/core/types.py:CanonicalIssue` |

---

### TASK-P1-03: 激活 36 条 RD_* 规则 ✅

| 字段 | 内容 |
|------|------|
| **状态** | ✅ 已完成 (2025-01-20) |
| **完成记录** | `pipeline.py` 集成 RuleRunner，所有规则已激活 |
| **验证** | 14/14 规则测试通过 |

---

## Phase 2: 单帧分析增强 ✅ 已完成

### TASK-P2-01: 定义 Canonical Schema [P0-1] ✅

| 字段 | 内容 |
|------|------|
| **状态** | ✅ 已完成 (2025-01-20) |
| **完成记录** | `schema_version: "1.0"` + meta/summary/coverage/issues/suggestions/preflight |
| **代码入口** | `scripts/rdc_analyzer/main.py:_export_reports()` |

---

### TASK-P2-02: 阈值体系平台化 [P1-1] ✅

| 字段 | 内容 |
|------|------|
| **状态** | ✅ 已完成 |
| **完成记录** | 规则使用统一的 thresholds 配置，支持 pc/mobile |

---

### TASK-P2-03: 移除 main.py 占位实现 [P0-2] ✅

| 字段 | 内容 |
|------|------|
| **状态** | ✅ 已完成 (2025-01-20) |
| **完成记录** | 添加 `_pipeline_state_samples` 跟踪 + coverage 加权算法 |
| **代码入口** | `scripts/rdc_analyzer/main.py:_build_coverage_report()` |

---

### TASK-P2-04: 完善 OptimizationAdvisor 建议覆盖 ✅

| 字段 | 内容 |
|------|------|
| **状态** | ✅ 已完成 (2025-01-21) |
| **完成记录** | `_build_suggestions()` 覆盖 DrawCall/纹理/顶点等多维度 |

---

## Phase 3: 双帧对比（核心目标 2）✅ 已完成

### TASK-P3-01: Compare CLI 子命令 [P0-4] ✅

| 字段 | 内容 |
|------|------|
| **状态** | ✅ 已完成 (2025-01-20) |
| **完成记录** | `py -3 -m rdc_analyzer compare baseline target` 可用 |
| **代码入口** | `scripts/rdc_analyzer/__main__.py:cmd_compare()` |

---

### TASK-P3-02: 统一 Compare 输入口径 ✅

| 字段 | 内容 |
|------|------|
| **状态** | ✅ 已完成 |
| **完成记录** | 支持 .rdc/.xml/.json 三种输入格式 |

---

### TASK-P3-03: 增强回归检测证据链 ✅

| 字段 | 内容 |
|------|------|
| **状态** | ✅ 已完成 (2025-01-21) |
| **完成记录** | Evidence Chain 已集成到所有 issues |

---

## Phase 4: 真实数据集成 ✅ 已完成

### TASK-P4-01: 验证 D3D11 Replay 环境 ✅

| 字段 | 内容 |
|------|------|
| **状态** | ✅ 已完成 |
| **完成记录** | ReplayWrapper 封装 + 12/12 单元测试通过 |

---

### TASK-P4-02: 集成真实 PipelineSnapshot [P0-2] ✅

| 字段 | 内容 |
|------|------|
| **状态** | ✅ 已完成 |
| **完成记录** | analyze 命令已集成真实 Pipeline State 采样 |

---

## Phase 5: B-mode 统计对比 ✅ 已完成 (4/4)

> **目标**: 增强对比能力，支持 CI 回归门禁

### TASK-P5-01: 多帧统计采样 ✅ 已完成

| 字段 | 内容 |
|------|------|
| **状态** | ✅ 已完成 |
| **优先级** | 🔴 P0 |
| **完成日期** | 2025-02-06 |
| **验收标准** | 支持 N 帧采样，输出均值/中位数/分位数 |

**实现位置**:
- [x] `stats/sampler.py`: `MultiFrameSampler` 类
- [x] `stats/sampler.py`: `MetricStatistics` dataclass (mean/median/std/min/max/p95/p99)
- [x] CLI `--samples N` 参数

---

### TASK-P5-02: 统计显著性检测 ✅ 已完成

| 字段 | 内容 |
|------|------|
| **状态** | ✅ 已完成 |
| **优先级** | 🟡 P1 |
| **完成日期** | 2025-02-06 |
| **验收标准** | 区分"正常波动"与"真实回归" |

**实现位置**:
- [x] `stats/summary.py`: `StatisticalSummary` 类
- [x] Z-score (Welch's t-test) 置信区间计算
- [x] Cohen's d 效应量分析
- [x] `significance` 输出 (HIGH/MEDIUM/LOW)
- [x] CLI `--confidence-level` 参数 (90%/95%/99%)

---

### TASK-P5-03: Marker/Pass 对齐增强 ✅ 已完成

| 字段 | 内容 |
|------|------|
| **状态** | ✅ 已完成 |
| **优先级** | 🟡 P1 |
| **完成日期** | 2025-02-06 |
| **验收标准** | 按 marker/pipeline signature 对齐，减少噪声 |

**实现位置**:
- [x] `diff/diff_engine.py`: 4 阶段对齐算法 (marker+shader → marker → signature → fallback)
- [x] CLI `--align-strategy {order,signature,marker}` 参数
- [x] `compare_rdc.py`: 参数透传到 DiffEngine
- [x] 13 个单元测试验证 (`test_marker_alignment.py`)

---

### TASK-P5-04: CI 集成支持 ✅ 已完成

| 字段 | 内容 |
|------|------|
| **状态** | ✅ 已完成 |
| **优先级** | 🟢 P2 |
| **完成日期** | 2025-02-06 |
| **验收标准** | 输出 JUnit XML / exit code / GitHub Action 示例 |

**实现位置**:
- [x] `stats/junit_reporter.py`: `JUnitReporter` 类
- [x] CLI `--junit-xml <path>` 参数
- [x] 回归检测 → exit code 1
- [x] GitHub Action 示例 (`docs/E2E_WORKFLOW_GUIDE.md` + `MULTI_FRAME_GUIDE.md`)

---

## ✅ 已完成任务汇总

| 任务 | 完成日期 | 说明 |
|------|---------|------|
| 方向 B: Shader 源码提取 | 2025-01-19 | 9a8a06a27 |
| 方向 C: 渲染目标追踪 | 2025-01-19 | 6def8b85b |
| 方向 F: 性能热点分析 | 2025-01-20 | 749852014 |
| A-first 闭环 (DoD 7.1-7.8) | 2025-01-21 | 370 passed |
| Phase 1-4 全部任务 | 2025-01-21 | 见上方各任务 |

---

## 📝 附录：文件索引

### 核心分析链路
| 文件 | 职责 |
|------|------|
| `main.py` | 端到端 pipeline (CLI 主入口) |
| `pipeline.py` | 模块化 pipeline (有 RuleRunner) |
| `compare_rdc.py` | 对比核心逻辑 |
| `__main__.py` | CLI 入口 (analyze/compare) |

### 规则与建议
| 文件 | 职责 |
|------|------|
| `rules/runner.py` | RuleRunner (执行 36 条规则) |
| `rules/*.py` | RD_DC_*, RD_TEX_*, RD_BUF_* 等规则 |
| `core/optimization_advisor.py` | 优化建议生成 |

### 深度分析模块
| 文件 | 职责 |
|------|------|
| `extractors/replay_wrapper.py` | RenderDoc API 封装 |
| `analysis/call_analyzer.py` | 调用级绑定分析 |
| `analysis/resource_tracker.py` | 资源生命周期追踪 |

### 对比与回归
| 文件 | 职责 |
|------|------|
| `diff/diff_engine.py` | 结构化差异计算 |
| `diff/regression_detector.py` | 回归检测 |
| `diff/regression_types.py` | REG001~REG007 规则 |

---

## 🎯 下一阶段执行顺序 (B-mode)

```
1. TASK-P5-01 (多帧统计采样) ← 降噪基础
      ↓
2. TASK-P5-02 (显著性检测) ← 减少误报
      ↓
3. TASK-P5-03 (Marker 对齐) ← 提升对比精度
      ↓
4. TASK-P5-04 (CI 集成) ← 产品化
```

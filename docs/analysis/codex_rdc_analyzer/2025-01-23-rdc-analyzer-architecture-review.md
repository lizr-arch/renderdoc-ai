# RDC Analyzer 架构复审 & A-first 缺口清单（2025-01-23）

> 目标：根据 `scripts/rdc_analyzer/` 的真实代码结构，评估架构是否需要重构，并给出“目标功能 vs 现状”的横向对比与下一阶段任务。  
> 约束：单文件 <= 800 行；结论必须落到 WHAT/WHY/HOW。

---

## 1) 架构总览（WHAT / WHY / HOW）

### 1.1 入口层（CLI + Pipeline）

- WHAT: CLI 入口在 `scripts/rdc_analyzer/__main__.py:23`，`analyze` **默认已走** `main.py` 的 AnalysisPipeline（仅在 ImportError 时回退旧管线）。  
- WHY: 入口决定“用户看到的结果是哪条管线”，主干已统一可避免“功能已实现但用户不可见”。  
- HOW: 保持 `main.py` 为默认主干，并明确标注 legacy 回退路径。

### 1.2 数据来源（3 条并行路径）

- WHAT: 至少三条数据路径并存  
  1) RenderDoc API 回放：`main.py` / `extractors/replay_wrapper.py`  
  2) XML 离线解析：`parse_rdc_xml.py` + `core/bridge.py`  
  3) 二进制解析：`parsers/binary_parser.py` / `rdc_parser.py`  
- WHY: 多路径有利于覆盖不同环境，但**必须统一到 Canonical Schema**，否则 A/B 结论不一致。  
- HOW: 确定单一 Schema（v1.0 已存在），任何路径输出都必须通过桥接层映射到统一字段。

### 1.3 核心模型（Canonical Schema）

- WHAT: `core/types.py:231` 提供 `CanonicalIssue` 等规范化数据结构。  
- WHY: A/B/C 共享“事实来源（SSOT）”，避免 compare 误判与规则漂移。  
- HOW: 在输出层强制使用 CanonicalIssue / coverage / suggestions / preflight 的同一结构，并由测试锁定。

### 1.4 模块体量（功能规模客观统计）

- WHAT: `scripts/rdc_analyzer` 共 **168** 个 Python 文件（统计日期：2025-01-23）。  
- WHY: 功能体量大、入口多，容易产生分叉与重复实现。  
- HOW: 通过“唯一入口 + 统一 schema + 统一测试入口”控制复杂度。

**模块数量快照（py 文件数）**

| 模块 | 数量 | 说明 |
|---|---:|---|
| analyzers | 9 | 性能/资源/Pass 等分析器 |
| rules | 9 | 36 条规则定义 |
| reporters | 7 | JSON/HTML/CSV/Console |
| exporters | 4 | HTML 输出与模板 |
| diff | 7 | 对比与回归检测 |
| extractors | 7 | RenderDoc 回放与抽取 |
| parsers | 15 | XML/二进制解析 |
| core | 16 | 数据模型与桥接 |
| tests | 34 | 但存在“路径分散 + 未纳入 Git”问题 |

---

## 2) 架构不符合规范/需要重构的点（WHAT / WHY / HOW）

### 2.1 CLI 主干已指向 A-first（已验证）

- WHAT: CLI analyze 默认已走 `main.py:157`，旧管线仅为 fallback。  
- WHY: 已消除“入口不一致”的风险，但需保证 fallback 不被误用。  
- HOW: 保持默认路径不变，并在文档中明确 legacy 路径。

### 2.2 多条管线并存导致“口径漂移”

- WHAT: `pipeline.py` 与 `main.py` 各自维护 AnalysisPipeline。  
- WHY: 对同一 rdc 可能生成不同字段/统计口径，compare 的可信度下降。  
- HOW: 明确 “主干输出 = main.py canonical schema”；其他管线输出必须桥接或废弃。

### 2.3 测试分散且未纳入 Git（验证链不完整）

- WHAT: `scripts/rdc_analyzer/tests` 中存在未纳入 Git 的测试文件；P0-NEW-2 / PipelineSampler 测试在 repo 根 `tests/`。  
- WHY: “通过测试”的结论不可复现；默认验证不会覆盖关键集成测试。  
- HOW: 新增 P0-NEW-5/6/7（统一测试归属 + 默认验证路径 + 修复 skip）。

### 2.4 大文件/强耦合风险（长期重构成本）

- WHAT: `main.py` 体量大，集成了 parse/analysis/report/coverage/suggestions 多个职责。  
- WHY: 功能扩展会进一步放大耦合，维护与测试成本高。  
- HOW: 以“子模块化”拆分（coverage_builder / suggestion_builder / report_builder），保持稳定接口。

---

## 3) 目标功能 vs 现状（横向对比）

### 3.1 A：单帧极致分析（目标 1）

| 目标能力 | 现状（证据） | 状态 | 缺口 |
|---|---|---|---|
| 证据链（event/resource） | `CanonicalIssue` + `_canonicalize_issues()`（`core/types.py:231`, `main.py:1483`） | ✅ 功能有 | 需验证链锁定（P0‑NEW‑5/6/7） |
| Playbook 建议 | `_build_suggestions()`（`main.py:1558`） | ✅ 功能有 | 需验证链锁定（P0‑NEW‑5/6/7） |
| 验证计划 | `verification_plan`（`main.py:1608` 起） | ✅ 功能有 | 测试覆盖分散 |
| DataQuality/Confidence | `_build_coverage_report()`（`main.py:1264`） | ✅ 功能有 | 需默认验证锁定 |
| PipelineSnapshot | `extractors/pipeline_sampler.py` | ✅ 功能有 | 测试入口分散 |
| CLI 一键输出 | `__main__.py:435` | ✅ | 保留 legacy fallback 即可 |

### 3.2 B：双帧全方位对比（目标 2）

| 目标能力 | 现状（证据） | 状态 | 缺口 |
|---|---|---|---|
| DiffEngine | `diff/diff_engine.py` | ✅ | 依赖输入 schema 一致 |
| RegressionDetector | `diff/regression_detector.py` | ✅ | 缺统计稳定性（后续 B 阶段） |
| Bridge→Diff 端到端证明 | `tests/test_schema_bridge_integration.py` | ⚠️ | 不在默认验证路径 |

---

## 4) 重复/冗余功能清单（WHAT / WHY / HOW）

### 4.1 两套 AnalysisPipeline（main.py vs pipeline.py）
- WHAT: 两个 `AnalysisPipeline` 同名但实现不同。  
- WHY: 用户/测试/文档容易混用，导致结论不一致。  
- HOW: 标准化一条主干（main.py），旧版标记 legacy，仅保留兼容路径。

### 4.2 多套解析入口（API / XML / Binary）
- WHAT: `APIParser`、`parse_rdc_xml`、`binary_parser` 均能产出数据。  
- WHY: 同一场景可能出现多种字段口径，影响 compare。  
- HOW: 强制输出统一 Canonical Schema；没有数据则用 coverage 标记降级，不补零伪造。

### 4.3 多个报告/导出分支
- WHAT: reporters + exporters + offline report scripts 并存。  
- WHY: 同一结果多套展示，容易“只修一种输出，另一种坏掉”。  
- HOW: 收敛到 canonical JSON，所有报告从同一 JSON 渲染。

---

## 5) A-first 最小闭环状态（证据链 + Playbook + 验证计划）

### 5.1 证据链（Evidence Chain）
- WHAT: issue 必须关联 event/resource，支持定位问题来源（`main.py:1483`）。  
- WHY: 无证据链 = 只能给“泛泛建议”，说服力不足。  
- HOW: `CanonicalIssue` + `_canonicalize_issues()` 输出 `event_ids/resource_ids`（`core/types.py:231`）。

### 5.2 Playbook 建议
- WHAT: 每条建议包含 steps/expected_impact/risk/engine_howto。  
- WHY: A 模式强调“可执行建议”，否则无法指导真实优化。  
- HOW: `_build_suggestions()` 中统一生成结构化建议（`main.py:1558`）。

### 5.3 验证计划
- WHAT: 每条建议附 verification_plan（metrics/expected_direction/how_to_capture）。  
- WHY: 没有验证计划，无法形成闭环（改了也不知道是否有效）。  
- HOW: `_build_suggestions()` 内统一生成 verification_plan 字段（`main.py:1608`）。

### 5.4 结论
> **功能面：已具备。  
> 验证面：已闭合（2025-01-23 验证通过）。**  
关键缺口已通过 P0-NEW-5/6/7 解决。

---

## 6) P0 闭环任务（WHAT / WHY / HOW）

### P0-NEW-5：测试归属与可复现性
- WHAT: 让 `scripts/rdc_analyzer/tests` 的新增测试进入 Git。  
- WHY: 否则 A-first 的“全绿”不可复现。  
- HOW: 解除 `.gitignore` 对该路径的忽略或迁移测试到 repo 根并更新 pytest.ini。

### P0-NEW-6：默认验证覆盖关键集成测试
- WHAT: `test_schema_bridge_integration.py` 与 `test_pipeline_sampler.py` 纳入默认验证。  
- WHY: 这两项直接证明 A/B 结论可信。  
- HOW: 移动到 `scripts/rdc_analyzer/tests/` 或更新默认验证命令。

### P0-NEW-7：修复 bridge 集成测试跳过
- WHAT: 让 `test_bridge_integration.py` 在默认 pytest 下可运行。  
- WHY: XML→Context 是 A-first 的证据链来源之一。  
- HOW: 统一绝对导入，避免相对导入路径错误。

## 7) A-first 测试点（已验证）

1) **默认验证（主路径）**  
   - `py -3 -m pytest -q -rs`（在 `scripts/rdc_analyzer` 下执行，pytest.ini 已包含根 tests）  
   - 实测：**501 passed, 8 skipped**（2025-01-23）
2) **CLI 闭环（单帧 + 对比）**  
   - `py -3 -m rdc_analyzer analyze <sample.rdc> -o ./output --format json`  
   - `py -3 -m rdc_analyzer compare baseline.json target.json -o ./compare_output`

---

## 8) 备注（game_mode_sel_v1）

当前仓库内未搜索到 `game_mode_sel_v1` 相关文档或代码引用。  
如果需要修订，请提供**具体文档路径或截图位置**，我会在本仓库内同步更新。

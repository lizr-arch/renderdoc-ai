# A-first 执行计划 - RDC Analyzer 第一闭环

> **创建时间**: 2025-01-20 15:23:00  
> **执行者**: Codex AI  
> **状态**: 🔄 进行中  
> **验收依据**: `docs/analysis/codex_rdc_analyzer/2026-01-20-abc-modes-market-and-a-first-loop.md` 的 DoD 7.1-7.8

---

## 1. 背景理解

### 1.1 核心目标（SSOT）

根据 `docs/analysis/codex_rdc_analyzer/README.md` 和 `capability-scorecard.md`，本项目有两大核心能力：

| # | 目标 | 说明 |
|---|------|------|
| 1 | **单个 RDC 极致分析 + 建议** | 性能瓶颈定位 + 可执行建议 |
| 2 | **双 RDC 全方位对比 + 结论** | baseline vs target 回归检测 |

**决策**: A（规则+建议驱动）作为第一闭环，B/C 后续演进。

### 1.2 当前技术债（P0 断链）

| 断链 | 代码位置 | 风险说明 |
|------|----------|----------|
| 占位 DrawCallDetail | `main.py:1005` | 用 `type()` 动态造假数据 |
| 占位资源生命周期 | `main.py:1041-1043` | `read_count=1` 硬编码 |
| 三套管线并存 | `main.py` vs `pipeline.py` vs `analysis/*` | Schema 不一致 |
| Issue 模型分裂 | `Issue`/`BindingIssue`/`RTIssue` | exporter 需特判拼装 |

### 1.3 A-first DoD 验收标准

| # | DoD | 验收条件 |
|---|-----|----------|
| 7.1 | CLI 贯通 | 一条命令 `analyze` → HTML+JSON |
| 7.2 | Schema 稳定 | 有 `schema_version` + 标准顶层块 |
| 7.3 | DataQuality | `confidence` + 缺数据降级 |
| 7.4 | Evidence Chain | issue 有 `event_ids`/`resource_ids` |
| 7.5 | Playbook 建议 | `steps/impact/risk/engine_howto` |
| 7.6 | 验证方法 | `verification_plan` |
| 7.7 | Preflight | 缺数据时提示抓帧方法 |
| 7.8 | 工程质量 | 测试全绿 + 输出稳定 |

---

## 2. 任务分解与追踪

### 2.1 P0 任务（必须先做）

#### P0-1: 统一 Canonical Schema
- [ ] **完成状态**: 未开始
- **涉及文件**: 
  - `scripts/rdc_analyzer/main.py`
  - `scripts/rdc_analyzer/exporters/json_exporter.py`
  - `docs/analysis/codex_rdc_analyzer/2026-01-20-rdc-analyzer-schema-single-analysis.md`
- **具体任务**:
  - [ ] 在 JSON 输出中添加 `schema_version: "1.0"`
  - [ ] 确保 JSON 包含 `meta/summary/issues/suggestions/coverage` 顶层块
  - [ ] 统一 `main.py` 和 `pipeline.py` 的输出结构
- **验收方式**: 同一 capture 多次运行，JSON 字段语义一致
- **完成记录**: （待填写）

---

#### P0-2: 打通真实 DrawCallDetail/PipelineSnapshot
- [ ] **完成状态**: 未开始
- **涉及文件**:
  - `scripts/rdc_analyzer/main.py:1005` (占位代码)
  - `scripts/rdc_analyzer/extractors/replay_wrapper.py`
  - `scripts/rdc_analyzer/core/pipeline_state.py`
- **具体任务**:
  - [ ] 移除 `main.py` 中的 `type('DrawCallDetail', ...)` 占位实现
  - [ ] 使用 `ReplayWrapper` 获取真实 pipeline state
  - [ ] 将真实数据喂给 `CallAnalyzer`/`ResourceTracker`
- **验收方式**: issue 能引用真实字段（RT 格式/尺寸/绑定情况）
- **完成记录**: （待填写）

---

#### P0-3: 统一 Issue/Rule/Suggestion 数据结构
- [ ] **完成状态**: 未开始
- **涉及文件**:
  - `scripts/rdc_analyzer/core/types.py` (Issue)
  - `scripts/rdc_analyzer/analysis/call_analyzer.py` (BindingIssue)
  - `scripts/rdc_analyzer/rules/base.py` (RuleResult)
- **具体任务**:
  - [ ] 定义统一 Issue 字段: `code/severity/category/message/event_id/resource_ids/evidence/suggestion_steps`
  - [ ] `RuleRunner` 输出统一 Issue 格式
  - [ ] 添加 `issue_fingerprint` 用于跨 capture 匹配
- **验收方式**: 所有 issues 在 JSON/HTML 中格式统一
- **完成记录**: （待填写）

---

#### P0-4: compare 做成一级 CLI 命令
- [ ] **完成状态**: 未开始
- **涉及文件**:
  - `scripts/rdc_analyzer/__main__.py`
  - `scripts/rdc_analyzer/compare_rdc.py`
  - `scripts/rdc_analyzer/diff/diff_engine.py`
- **具体任务**:
  - [ ] 添加 `python -m rdc_analyzer compare baseline.rdc target.rdc` 命令
  - [ ] 输出 `compare.json` + 可选 `compare.html`
  - [ ] 支持对两份 `analysis.json` 做 diff（无需 RenderDoc 环境）
- **验收方式**: compare 输出每条回归能追溯到证据字段
- **完成记录**: （待填写）

---

#### P0-5: 修复测试红灯
- [x] **完成状态**: ✅ 已完成 (2025-01-20)
- **涉及文件**:
  - `scripts/rdc_analyzer/exporters/html_exporter.py`
  - `scripts/rdc_analyzer/tests/test_shader_extractor.py`
  - `scripts/rdc_analyzer/tests/test_resource_inspector.py`
- **完成任务**:
  - [x] 导出 `HTML_TEMPLATE` 聚合变量
  - [x] 重命名 `test_resource_inspector_with_replay` → `_run_resource_inspector_with_replay`
  - [x] 添加 pytest 包装类隔离 integration 测试
- **验收结果**: `356 passed, 8 skipped, 0 errors`
- **完成记录**: 
  - 修改 `html_exporter.py` 添加 `HTML_TEMPLATE` 导出
  - 修改 `test_resource_inspector.py` 使用下划线前缀隐藏函数

---

### 2.2 A-first DoD 任务（7.1-7.8）

#### DoD-7.1: CLI 端到端贯通
- [ ] **完成状态**: 未开始
- **涉及文件**:
  - `scripts/rdc_analyzer/__main__.py`
  - `scripts/rdc_analyzer/main.py`
- **具体任务**:
  - [ ] `py -3 -m rdc_analyzer analyze <capture.rdc> -o <out_dir> --format html,json` 跑通
  - [ ] 错误时返回非 0 exit code
  - [ ] 输出目录自动创建，文件命名稳定
- **验收方式**: 命令返回码为 0，输出 HTML+JSON
- **完成记录**: （待填写）

---

#### DoD-7.2: Schema 稳定 (Canonical Schema v1)
- [ ] **完成状态**: 未开始
- **依赖**: P0-1
- **具体任务**:
  - [ ] JSON 包含 `schema_version`
  - [ ] 包含 `meta/summary/issues/suggestions/coverage`
  - [ ] 更新 schema 文档
- **验收方式**: 文档与输出一致
- **完成记录**: （待填写）

---

#### DoD-7.3: DataQuality/Confidence
- [ ] **完成状态**: 未开始
- **涉及文件**:
  - `scripts/rdc_analyzer/main.py`
  - `scripts/rdc_analyzer/exporters/html_exporter.py`
- **具体任务**:
  - [ ] 输出 `coverage/data_quality` (present/missing/estimated)
  - [ ] 每条 issue/suggestion 带 `confidence` + `confidence_reasons`
  - [ ] 低置信度时降级输出
- **验收方式**: 缺数据的 capture 仍能输出，但结论降级
- **完成记录**: （待填写）

---

#### DoD-7.4: Evidence Chain
- [ ] **完成状态**: 未开始
- **依赖**: P0-2, P0-3
- **具体任务**:
  - [ ] 每条 issue 包含 `event_ids` 或 `resource_ids` 或 `pass_path`
  - [ ] 聚合类 issue 输出 Top-K
  - [ ] HTML 中从 issue 能跳到证据
- **验收方式**: 随机点 1 条 issue，能回溯到具体 event/resource
- **完成记录**: （待填写）

---

#### DoD-7.5: Playbook 建议
- [ ] **完成状态**: 未开始
- **涉及文件**:
  - `scripts/rdc_analyzer/core/optimization_advisor.py`
  - `scripts/rdc_analyzer/analyzers/performance_analyzer.py`
- **具体任务**:
  - [ ] 统一 suggestion 结构: `steps/expected_impact/risk/engine_howto`
  - [ ] 先覆盖 2-3 个最常见问题（小批次/未压缩纹理/过多全屏 pass）
  - [ ] 不同引擎 HOW 分开写
- **验收方式**: 至少 3 类问题有带 steps 的 suggestion
- **完成记录**: （待填写）

---

#### DoD-7.6: 验证方法
- [ ] **完成状态**: 未开始
- **具体任务**:
  - [ ] 每条 suggestion 输出 `verification_plan`
  - [ ] 包含 `metrics` + `expected_direction` + `how_to_capture`
  - [ ] HTML 展示"下一步怎么做"
- **验收方式**: 1 条建议列出关注指标和预期变化
- **完成记录**: （待填写）

---

#### DoD-7.7: Capture Preflight
- [ ] **完成状态**: 未开始
- **具体任务**:
  - [ ] 关键数据缺失时输出 preflight 区块
  - [ ] 明确"缺什么导致哪些结论降级"
  - [ ] 链接到 Unity/UE 官方抓帧指南
- **验收方式**: 缺 markers 时 Preflight 出现
- **完成记录**: （待填写）

---

#### DoD-7.8: 工程质量底线
- [x] **完成状态**: ✅ 部分完成
- **已完成**:
  - [x] `py -3 -m pytest -m 'not integration'` 通过 (356 passed)
- **待完成**:
  - [ ] 同一输入多次运行输出稳定（排序稳定）
  - [ ] 建立基准样例集验证方式
- **完成记录**: 测试修复已完成

---

## 3. 执行顺序建议

```
阶段 1: 基础设施 (P0)
├── P0-5 ✅ 修复测试红灯 (已完成)
├── P0-1 统一 Canonical Schema
└── P0-3 统一 Issue 模型

阶段 2: 数据真实性 (P0)
└── P0-2 打通真实 state

阶段 3: CLI 完善 (P0 + DoD)
├── P0-4 compare 一级命令
├── DoD-7.1 CLI 贯通
└── DoD-7.2 Schema 稳定

阶段 4: 可信度增强 (DoD)
├── DoD-7.3 DataQuality
├── DoD-7.4 Evidence Chain
└── DoD-7.7 Preflight

阶段 5: 建议可执行 (DoD)
├── DoD-7.5 Playbook
└── DoD-7.6 验证方法

阶段 6: 工程收尾 (DoD)
└── DoD-7.8 输出稳定性 + 样例集
```

---

## 4. 风险与阻塞

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| ReplayWrapper 依赖真实 RenderDoc 环境 | P0-2 可能无法在 CI 验证 | 标记 integration，本地验证 |
| 三套管线改动范围大 | 可能引入回归 | 先加测试再重构 |
| Schema 变更影响下游 | compare/diff 需同步更新 | 保持向后兼容 |

---

## 5. 验收核对表

完成本计划后，用以下问题核对：

1. [ ] 理解了两大核心目标（单帧极致分析 + 双帧对比）？
2. [ ] 识别了 4 个关键断链（占位 state/三套管线/Issue 分裂/compare 非一级）？
3. [ ] 理解了 A-first DoD 7.1-7.8 的验收标准？
4. [ ] 任务按优先级分解，有明确的文件落点？
5. [ ] 每个任务有验收方式和完成记录？

---

## 6. 变更日志

| 日期 | 变更内容 | 执行者 |
|------|----------|--------|
| 2025-01-20 | 创建计划文档 | Codex |
| 2025-01-20 | P0-5 测试修复已完成 | Codex |

# A-first Execution Plan Audit (Reviewer Report)

Date: 2025-01-21  
Scope: `plans/2025-01-20-152300-Codex-A-first-execution-plan.md` vs current repo state under `scripts/rdc_analyzer/`  
Role: "Highest reviewer" — focus on **evidence**, **trustworthiness**, and **DoD validity**.

---

## 0) Executive Verdict (TL;DR)

结论：**计划表里的“✅ 已完成”在“基础框架/输出结构”层面基本成立，但在“数据真实性（真实 state / evidence chain / compare 输入一致性）”层面仍有明显缺口；并且“工程质量底线(全绿)”在当前工作区并不成立**。

你现在处于一个典型的状态：
- **A-first 的骨架已经搭好**（CLI、导出、schema_version、coverage/preflight、compare 管线大体能跑）。
- 但 **A-first 的“可信闭环”还没有闭合**：HTML/报告仍包含“模拟/估算数据”，关键字段存在命名不一致，compare 与新 schema 的兼容关系不清晰。
- **测试集目前被新的 audit 测试阻断**（不是核心功能逻辑崩了，而是 import 路径不对导致 25 个用例直接失败）。

---

## 1) Evidence (What I actually verified)

### 1.1 Test suite status (2025-01-21)

**Command (full suite in `scripts/rdc_analyzer`):**
```powershell
Set-Location scripts/rdc_analyzer
py -3 -m pytest tests -q
```

**Observed result:** `25 failed, 425 passed, 8 skipped, 5 warnings`  
Failure root cause is consistent: `tests/test_audit.py` imports `scripts.rdc_analyzer...` which is not importable in this repo layout.

Key evidence (first error):
- `scripts/rdc_analyzer/tests/test_audit.py:19` → `ModuleNotFoundError: No module named 'scripts.rdc_analyzer'`

---

### 1.2 Core suite status (excluding new audit tests)

**Command:**
```powershell
Set-Location scripts/rdc_analyzer
py -3 -m pytest tests -q --ignore=tests/test_audit.py
```

**Observed result:** `425 passed, 8 skipped, 5 warnings`

Interpretation:
- 计划表中 P0-4 compare、P0-1/P0-3 的大部分“结构性目标”是可用的；
- 但 **DoD-7.8 “测试全绿”不成立**，因为默认执行会收集 `test_audit.py` 并失败。

---

## 2) Plan Items Audit (P0 + DoD 7.1-7.8)

评分说明（0-10）：
- 10 = 完全满足计划文字 + 有自动化验证 + 输出可信（无假数据）
- 7-9 = 功能基本满足，但存在小范围偏差/测试不足/可接受的估算
- 4-6 = 主要结构在，但关键可信链缺口明显，或 spec/实现不一致
- 0-3 = 计划目标本质未实现/输出不可信/关键路径缺失

---

### P0-1: 统一 Canonical Schema (Score: 7/10)

**WHAT (Plan):**
- JSON 输出含 `schema_version: "1.0"`，并包含 `meta/summary/issues/suggestions/coverage` 顶层块。  
Plan ref: `plans/2025-01-20-152300-Codex-A-first-execution-plan.md:52`

**WHAT (Repo reality):**
- `scripts/rdc_analyzer/main.py:948` `_export_reports()` 构建 `analysis_data`：
  - `schema_version: "1.0"` ✅ (`scripts/rdc_analyzer/main.py:981-1012`)
  - 顶层包含：`meta/summary/coverage/issues/suggestions/preflight` ✅
  - 同时还包含：`events/draw_calls/resources/resource_samples`（计划未提，但不是坏事）

**WHY (Why it matters):**
- schema 是后续 compare / report / CI 的“契约”。结构稳定，才能做跨版本 diff、前端渲染、以及长期积累规则库。
- 但如果 schema 的“必需字段”缺少自动化测试，未来改动很容易“静悄悄”破坏兼容性。

**HOW (How to validate / improve):**
- 加一个非常便宜、但收益巨大的测试：验证 `analysis_data` 顶层 key 集合和基本类型（dict/list/str）稳定。
- 重点校验：`schema_version/meta/summary/coverage/issues/suggestions/preflight` 必须存在。

Gap:
- 计划提到 `exporters/json_exporter.py`，但当前新管线 JSON 直接 `json.dump()`（`scripts/rdc_analyzer/main.py:1014-1021`），两个 schema 体系并存，有维护风险。

---

### P0-2: 打通真实 DrawCallDetail/PipelineSnapshot (Score: 3/10)

**WHAT (Plan):**
- “真实 state”贯通，coverage 能基于真实回放采样体现 present/partial/estimated。  
Plan ref: `plans/2025-01-20-152300-Codex-A-first-execution-plan.md:86`

**WHAT (Repo reality):**
- `scripts/rdc_analyzer/main.py:_extract_states()` 只提取 textures/buffers 元数据（`scripts/rdc_analyzer/main.py:366-406`），并没有构建 `DrawCallDetail/PipelineSnapshot`。
- `pipeline_state` 的采样计数 `_pipeline_state_samples` 只在 Mali 分析中递增（`scripts/rdc_analyzer/main.py:708-717`），而 Mali 分析通常是可选项（`scripts/rdc_analyzer/main.py:445-449`）。
- HTML 导出阶段存在明显的“模拟数据”：
  - **模拟 DrawCallDetail**：`type('DrawCallDetail', (), {...})()`（`scripts/rdc_analyzer/main.py:1051-1069`）
  - **资源生命周期假设整帧活跃**：`first_access_event=1`、`last_access_event=len(events)`、`read_count=1`（`scripts/rdc_analyzer/main.py:1086-1102`）

**WHY (Why it matters):**
- 你核心目标 1 是“单个 rdc 的极致性能分析并给建议”。这件事的可信度 80% 来自：
  - 能不能把问题定位到具体 draw/event + pipeline state 证据；
  - 输出里有没有“看起来很真但其实是假设”的字段。
- 一旦 HTML/报告里混入模拟数据，团队会产生“工具不可信”的第一印象，后续推行会非常难。

**HOW (How to validate / improve):**
- 最低成本闭环路径（建议作为 A-first 的真闭环补齐）：
  1) 抽样 N 个 draw call（比如 50/100），对每个 draw call 做 `SetFrameEvent + GetPipelineState()`，构建最小 `PipelineSnapshot`（shader id/rt/ds/viewport/scissor/topology 等）。
  2) 在 `coverage.details.pipeline_state` 中标注真实采样率（现在的字段基本正确，但触发条件不合理）。
  3) HTML 导出禁止使用“假 draw detail / 假 lifetime”，宁可显示为 missing/estimated。

---

### P0-3: 统一 Issue/Rule/Suggestion 数据结构 (Score: 6/10)

**WHAT (Plan):**
- 定义 `CanonicalIssue`，各类 issue 能统一转换，输出稳定。  
Plan ref: `plans/2025-01-20-152300-Codex-A-first-execution-plan.md:128`

**WHAT (Repo reality):**
- `CanonicalIssue` 存在 ✅：`scripts/rdc_analyzer/core/types.py:230-279`
- `_canonicalize_issues()` 存在 ✅：`scripts/rdc_analyzer/main.py:1374-1441`

关键缺口（Evidence chain 真正影响点）：
- `_analyze_rules()` 生成的 dict issue 使用 `eventId`（大写 I）（`scripts/rdc_analyzer/main.py:412-429`）。
- `_canonicalize_issues()` 只识别 `event_id/event_ids/related_events`，不识别 `eventId`（`scripts/rdc_analyzer/main.py:1392-1399`）。

**WHY (Why it matters):**
- 计划 DoD-7.4 的核心是“证据链可回溯”。如果 event id 键名不统一，最后输出会出现：
  - issue 看起来有 code/message，但无法定位到事件；
  - compare/回归结论无法链接到具体 draw call；
  - 这会直接降低“建议可信度”。

**HOW (How to validate / improve):**
- 统一命名：内部统一用 `event_id`，输入兼容 `eventId`（作为 legacy alias）。
- 为 `_canonicalize_issues()` 增加一条测试：传入只包含 `eventId` 的 issue，期望输出 `event_ids` 非空。

---

### P0-4: compare 做成一级 CLI 命令 (Score: 6/10)

**WHAT (Plan):**
- `python -m rdc_analyzer compare ...` 可用，输出 html/json diff；支持 `.rdc/.xml/.json`；并宣称可对两份 `analysis.json` 做 diff。  
Plan ref: `plans/2025-01-20-152300-Codex-A-first-execution-plan.md:188`

**WHAT (Repo reality):**
- compare 子命令存在 ✅：`scripts/rdc_analyzer/__main__.py:527-698`
- 支持 `.rdc/.xml/.json` 加载 ✅：`scripts/rdc_analyzer/parsers/rdc_loader.py:227-271`
- DiffEngine 输入期望更接近 “CaptureData” 格式（textures/shaders/buffers/events/statistics）：
  - `scripts/rdc_analyzer/diff/diff_engine.py:65-123`
- 关键兼容风险：`.json` 输入如果是**新的 analyze 输出**（Canonical Schema v1），loader 会 `return data`，而 DiffEngine 不会用到 `resources` 字典（只看 `textures` list），导致对比维度退化甚至误判。

**WHY (Why it matters):**
- 你核心目标 2 是“对比两个 rdc，全方位，并给出结论”。如果 compare 不能直接消费 analyze 输出，就会出现：
  - 用户先 analyze 两次得到 json，再 compare 反而对比不到 texture/shader/buffer；
  - 输出结论不完整，降低工具一体化价值。

**HOW (How to validate / improve):**
- 明确 compare 的输入契约：
  - 方案 A（推荐）：提供 `analysis.json (Canonical Schema v1)` → `CaptureData` 的桥接转换（或者让 DiffEngine 直接支持 Canonical Schema）。
  - 方案 B：在 compare CLI 中检测 `schema_version == "1.0"` 时走转换逻辑，否则按旧逻辑。

---

### P0-5: 修复测试红灯 (Score: 5/10)

**WHAT (Plan):** 测试全绿。  
Plan ref: `plans/2025-01-20-152300-Codex-A-first-execution-plan.md:236`

**WHAT (Repo reality):**
- 如果忽略新加入的 `tests/test_audit.py`，测试是绿的（425 passed）。✅
- 但默认执行测试会失败（25 failed），所以“工程质量底线”在当前工作区仍然不成立。❌

**WHY (Why it matters):**
- 对团队协作：CI 一旦红，大家会停止相信“main/master 可用”。  
- 对你目标 2：compare 是典型 CI/回归检测场景，测试红会阻止它进入流水线。

**HOW (How to validate / improve):**
- 修复 `tests/test_audit.py` 的 import 路径（见 DoD-7.8 章节）。

---

## 3) DoD 7.1 - 7.8 Audit

### DoD-7.1: CLI 端到端贯通 (Score: 5/10)

**WHAT (Plan):** analyze 命令可在真实 capture 上生成 HTML+JSON。  
Plan ref: `plans/2025-01-20-152300-Codex-A-first-execution-plan.md:255`

**WHAT (Repo reality):**
- analyze CLI 存在 ✅：`scripts/rdc_analyzer/__main__.py:300-399`
- repo 内 `scripts/rdc_analyzer/test_captures/test_game.rdc` 仅 3 bytes（占位），无法作为真实 E2E 验证样本。

**WHY:**  
没有真实样本，DoD-7.1 的“可用性”只能靠单元测试推断，无法证明“对真实 rdc 能跑通”。

**HOW:**  
建议放一个最小可公开的真实 capture（或录屏说明如何生成），作为本地 E2E check；CI 可跳过。

---

### DoD-7.2: Schema 稳定 (Score: 6/10)

**WHAT:** 顶层块必须稳定 + 文档/输出一致。  
**Repo:** 输出包含该结构（`scripts/rdc_analyzer/main.py:981-1012`）。  
**Gap:** 当前 `tests/test_dod_compliance.py` 没有对“顶层块集合”做断言（只有 CanonicalIssue 的字段测试）。  

**HOW:** 新增 `TestDOD72`：构造最小 `analysis_data` or mock pipeline，断言 key 存在。

---

### DoD-7.3: DataQuality/Confidence (Score: 4/10)

**WHAT:** coverage 反映 present/partial/estimated，并给出理由。  
**Repo:** coverage 结构存在（`scripts/rdc_analyzer/main.py:1155-1296`）。  

关键问题：
- `resource_lifecycle_tracked` 从未置 True（仅初始化/读取，`scripts/rdc_analyzer/main.py:201-202`, `scripts/rdc_analyzer/main.py:1245`），导致 lifecycle 永远无法达到 present。
- `pipeline_state` 采样只在 Mali 分析中发生（`scripts/rdc_analyzer/main.py:708-717`），逻辑上会“误判 coverage”（不开 Mali 时永远 estimated）。

---

### DoD-7.4: Evidence Chain (Score: 4/10)

**WHAT:** issue 必须可定位到 event/resource。  
**Repo:** canonicalize 框架有，但 eventId/命名不一致会断链（详见 P0-3）。

---

### DoD-7.5/7.6: Playbook + 验证方法 (Score: 5/10)

**Repo reality:**
- suggestions 确实包含 steps/expected_impact/risk/engine_howto/verification_plan（`scripts/rdc_analyzer/main.py:1469-1591`）
- 但 `verification_plan` 字段命名与计划不一致：
  - 计划倾向 `how_to_capture`
  - 代码使用 `how_to_verify`，且 `expected_direction` 用 `down`（不是 increase/decrease）

**WHY:**  
建议结构如果不稳定，前端展示/compare 结论聚合会很快腐烂。

---

### DoD-7.7: Capture Preflight (Score: 8/10)

**Repo:** `_build_preflight()` 实现完整，逻辑清晰，包含 Unity/Unreal/Custom 指导与 docs link。  
Ref: `scripts/rdc_analyzer/main.py:1298-1372`

---

### DoD-7.8: 工程质量底线 (Score: 3/10)

**WHAT:** 测试全绿 + 输出稳定。  
**Repo reality:** 默认跑测试失败（`tests/test_audit.py` 25 fail），因此不满足。

**HOW (Minimal fix):**
- 将 `scripts/rdc_analyzer/tests/test_audit.py` 的 import 从：
  - `from scripts.rdc_analyzer.audit...`
  改为：
  - `from rdc_analyzer.audit...`
- 或者（不推荐）把 repo 根的 `scripts/` 变成 Python package（加 `scripts/__init__.py`），会影响很多路径约定。

---

## 4) Highest-Priority Gaps (Blocking A-first Trust)

按“影响可信度/阻断团队使用”的优先级排序：

1) **禁止 HTML/报告里的“模拟 state/lifetime”**
   - WHAT: `_export_html()` 当前构造 fake DrawCallDetail + fake lifetime。
   - WHY: 这会让团队第一眼就觉得工具在“编故事”。
   - HOW: 用 missing/estimated 显式标注；或尽快补齐最小 pipeline snapshot 抽样。

2) **修复 issue 的 eventId 命名不一致**
   - WHAT: `eventId` vs `event_id` 断链。
   - WHY: Evidence chain 是你“给建议”的底层信用。
   - HOW: canonicalize 支持别名 + 内部统一 event_id。

3) **compare 与 analyze 输出的 schema 对齐**
   - WHAT: compare 对 Canonical Schema v1 的支持不完整/不明确。
   - WHY: 你目标 2 需要“一体化工具链”。
   - HOW: 增加 bridge/适配层，并写 1-2 个 golden test。

4) **让默认测试全绿（修复 test_audit import）**
   - WHAT: 当前 CI 红灯风险。
   - WHY: 团队协作的基本盘。
   - HOW: 修复 import 或调整 sys.path 方案（推荐修测试）。

---

## 5) Suggested Reading Order for the Team (fast ramp-up)

1) `docs/analysis/codex_rdc_analyzer/README.md`  
2) `docs/analysis/codex_rdc_analyzer/2025-01-20-a-first-dod-repo-checklist.md`  
3) This audit report: `docs/analysis/codex_rdc_analyzer/2025-01-21-a-first-plan-audit.md`  
4) Compare schema notes: `docs/analysis/codex_rdc_analyzer/2025-01-20-rdc-analyzer-schema-compare.md`


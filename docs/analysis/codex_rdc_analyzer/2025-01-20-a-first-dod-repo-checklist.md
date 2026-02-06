# A-first DoD → Repo 执行清单（逐项勾选版）

> 目标：把 `2025-01-20-abc-modes-market-and-a-first-loop.md` 里的 A-first DoD（7.1~7.8）  
> **映射到你当前仓库 `scripts/rdc_analyzer/` 的具体模块/文件**，让执行的人可以逐项勾选落地。  
> 约束：不讨论 B/C 的实现细节（保留接口/数据结构即可）。  
> 更新时间：2025-01-20

---

## 0) 使用方法（建议）

- 先读 DoD 原文：`docs/analysis/codex_rdc_analyzer/2025-01-20-abc-modes-market-and-a-first-loop.md` 的 `## 7)`  
- 然后用本清单逐项勾选；每完成一项，建议补充：  
  - “变更了哪些文件”  
  - “怎么验证”  
  - “是否引入 schema 变更（schema_version 是否需要 +1）”

---

## 1) A-first 总体落点（你现在仓库里“应该以谁为主干”）

**建议主干（CLI 默认已指向主干）**
- `scripts/rdc_analyzer/__main__.py`：CLI 入口（`python -m rdc_analyzer analyze ...`）
- `scripts/rdc_analyzer/main.py`：新端到端 `AnalysisPipeline`（A-first 主干，CLI 默认已走它）
- `scripts/rdc_analyzer/exporters/html_exporter.py`：HTML 报告呈现（需要真实 DrawCallDetail 才能“极致”）
- `scripts/rdc_analyzer/exporters/json_exporter.py`：结构化 JSON 导出能力（更接近 canonical schema 的长期方向）

**已知断链（执行清单会反复触达）**
- `scripts/rdc_analyzer/main.py` 的 HTML 导出适配里存在“占位 DrawCallDetail/占位资源生命周期”，会直接伤害 A 的可信度。  
  - 这不是“写更多规则”能解决的，而是必须把真实 state 数据喂给 exporter。
- CLI analyze 已走主干，仅在 ImportError 时回退旧管线（注意不要误用 legacy）。

---

## 2) DoD 7.1：一条命令跑通（端到端可用性）

**涉及文件（入口/主干）**
- `scripts/rdc_analyzer/__main__.py`（`cmd_analyze()`）
- `scripts/rdc_analyzer/main.py`（`AnalysisPipeline.run()`、`_export_reports()`）
- `scripts/rdc_analyzer/exporters/html_exporter.py`（HTML 输出）

**勾选清单**
- [ ] WHAT：`py -3 -m rdc_analyzer analyze <capture.rdc> -o <out_dir> --format html,json` 能跑通  
      WHY：A 的第一价值就是“一条命令拿到结果”，否则团队不会每天用  
      HOW：确保 CLI 参数 → `AnalysisOptions` → pipeline → 输出文件链路贯通（见入口文件）
- [ ] WHAT：错误时返回非 0 exit code（且有明确错误信息）  
      WHY：否则自动化脚本/批量运行无法可靠判定失败  
      HOW：统一异常捕获策略（CLI 层可兜底；pipeline 层输出错误上下文）
- [ ] WHAT：输出目录自动创建，输出文件命名稳定（可带 timestamp，但可预测）  
      WHY：便于脚本化收集与归档  
      HOW：集中在 `main.py:_export_reports()` 处理

---

## 3) DoD 7.2：输出契约稳定（Canonical Schema v1）

**涉及文件（schema 产出点）**
- `scripts/rdc_analyzer/main.py`（当前直接 `analysis_data = {...}` dump）
- `scripts/rdc_analyzer/exporters/json_exporter.py`（更结构化的 JSON 能力，长期应成为 canonical 输出）
- `docs/analysis/codex_rdc_analyzer/2025-01-20-rdc-analyzer-schema-single-analysis.md`（文档契约）

**勾选清单**
- [ ] WHAT：JSON 顶层明确包含 `schema_version`  
      WHY：否则未来 B/C 或工具迭代会出现“字段漂移但没人知道”的灾难  
      HOW：在唯一输出点（建议 `main.py:_export_reports()`）写入；必要时把 schema_version 提升为常量
- [ ] WHAT：JSON 至少具备 `meta/summary/issues/suggestions/coverage(data_quality)`  
      WHY：A 要能说服人，必须“可追溯 + 可执行建议 + 数据质量声明”  
      HOW：把 `performance_report.recommendations`、`OptimizationAdvisor` 等统一映射到 `suggestions`
- [ ] WHAT：字段含义/单位/统计口径在文档中有明确说明（并同步更新）  
      WHY：否则团队会把同一字段当成不同含义（例如 vertices 是 indices 还是 verts）  
      HOW：更新 schema 文档并在 JSON 里记录 `units`（可选）或 `definitions`（更轻量）

---

## 4) DoD 7.3：DataQuality/Confidence 一等输出（防玄学）

**涉及文件（事实采集与降级策略）**
- `scripts/rdc_analyzer/main.py`（能检测“当前数据是否缺失/是否占位”）
- `scripts/rdc_analyzer/extractors/replay_wrapper.py`（真实事实来源候选）
- `scripts/rdc_analyzer/exporters/html_exporter.py`（报告中展示 data quality）

**勾选清单**
- [ ] WHAT：输出 `coverage/data_quality`（present/missing/estimated + 原因）  
      WHY：你当前主链路存在占位 state 风险；没有这层输出，用户会误信结论  
      HOW：在 pipeline 完成采集后生成 `DataQualityReport` 并写入 JSON/HTML
- [ ] WHAT：每条 issue/suggestion 携带 `confidence` + `confidence_reasons`  
      WHY：避免把启发式结论当事实；也方便后续 B 做门禁阈值（只对 High 置信的项 fail）  
      HOW：issue 生成点统一附带 confidence（例如：缺真实 pipeline state → 只能 Medium/Low）
- [ ] WHAT：低置信度时“降级输出”（只报你能保证正确的部分）  
      WHY：A 的可信度比“更多结论”更重要  
      HOW：把规则分为 `requires_strong_evidence` 与 `heuristic_ok` 两类

---

## 5) DoD 7.4：Issue 必须有证据链（Evidence Chain）

**涉及文件（证据来源）**
- `scripts/rdc_analyzer/analysis/call_analyzer.py`（BindingIssue 自带 event_id/details）
- `scripts/rdc_analyzer/analysis/resource_tracker.py`（lifetimes/dependencies）
- `scripts/rdc_analyzer/core/pipeline_state.py`（DrawCallDetail/PipelineSnapshot，证据的结构化载体）
- `scripts/rdc_analyzer/main.py`（当前 issues 是简化 dict，需要升级）

**勾选清单**
- [ ] WHAT：每条 issue 至少包含 `event_ids` 或 `resource_ids` 或 `pass_path`（至少其一）  
      WHY：没有证据链就不可行动，A 会退化成“统计报表”  
      HOW：把 issue 模型统一成“可引用证据”的结构（不要只留 message）
- [ ] WHAT：聚合类 issue 输出 Top-K（例如 top 5 draws/resources）  
      WHY：数量级告警不够；Top-K 是“可执行性”的最低成本路径  
      HOW：在采集阶段保存排序指标（vertex count、texture size、pass cost proxy 等）
- [ ] WHAT：HTML 中从 issue 能跳到证据（至少是列表定位/过滤）  
      WHY：A 的核心体验是“从结论跳到证据”  
      HOW：在 HTML 的 JS 里支持按 event_id/resource_id 过滤高亮（exporter 侧即可）

---

## 6) DoD 7.5：建议必须是 Playbook（不是一句话）

**涉及文件（建议生成器与格式统一）**
- `scripts/rdc_analyzer/core/optimization_advisor.py`（纹理建议较强）
- `scripts/rdc_analyzer/analyzers/performance_analyzer.py` 或 `main.py:_run_performance_analysis()`（recommendations 现有雏形）
- `scripts/rdc_analyzer/rules/*`（RD_* 规则若要参与建议，需要统一 suggestion 输出结构）

**勾选清单**
- [ ] WHAT：统一 `suggestion` 结构：`steps/expected_impact/risk/engine_howto`  
      WHY：你要说服人，“怎么做”比“发现问题”更值钱  
      HOW：定义一个统一 dataclass 或 dict schema，并让所有建议来源都输出到同一结构
- [ ] WHAT：先覆盖 2–3 个最常见高收益问题（作为 A-first MVP）  
      WHY：不要一上来铺满 36 条规则；先把最常见场景做成“敢用”  
      HOW：优先建议题材：小批次、未压缩纹理/缺 mip、过多全屏 pass
- [ ] WHAT：不同引擎 HOW 分开写（Unity/Unreal/自研）  
      WHY：同一个问题的落地方式差异巨大；模板化输出能显著提高落地率  
      HOW：先做 `engine_howto` 的文本模板，后续再做更精细的项目集成

---

## 7) DoD 7.6：每条建议必须带验证方法（A 的闭环闭环）

**涉及文件（建议输出与对比提示）**
- 建议结构定义处（建议集中在一个地方）
- `scripts/rdc_analyzer/main.py`（summary/metrics 的稳定产出）

**勾选清单**
- [ ] WHAT：每条 suggestion 输出 `verification_plan`（关注指标 + 预期方向 + 推荐对比方式）  
      WHY：最强说服力来自“可验证”；这是 A 变成 B 的桥梁  
      HOW：先做最小字段：`metrics`（列表）、`expected_direction`（down/up）、`how_to_capture`（一段文字）
- [ ] WHAT：HTML 报告中把验证方法展示成“下一步怎么做”  
      WHY：让用户照着做，才能形成闭环  
      HOW：在 exporter 模板里新增“Verify”模块（不要求复杂交互）

---

## 8) DoD 7.7：Capture Preflight（把“如何抓到可分析数据”纳入产品）

**涉及文件（检测 + 文案 + 链接）**
- `scripts/rdc_analyzer/main.py`（检测缺失项）
- `scripts/rdc_analyzer/exporters/html_exporter.py`（展示 preflight）
- 文档参考（可链接到外部官方文档）：Unity/UE RenderDoc integration

**勾选清单**
- [ ] WHAT：当关键数据缺失（markers/state/bindings）时，输出 preflight 区块  
      WHY：输入不足是“分析不准”的最主要根因；必须把抓帧标准化写进产品  
      HOW：定义缺失项 → 生成建议文案（含链接）→ 写入 JSON/HTML
- [ ] WHAT：Preflight 明确“缺什么会导致哪些结论降级”  
      WHY：让用户理解你为什么不给更强结论（保护信任）  
      HOW：把 coverage 项与 issue confidence 关联起来

---

## 9) DoD 7.8：工程质量底线（让 A 成为可长期用的工具）

**涉及文件（测试与稳定性）**
- `scripts/rdc_analyzer/tests/`（单测）
- `scripts/rdc_analyzer/pytest.ini`（markers：integration 等）
- `scripts/rdc_analyzer/main.py` / `exporters/json_exporter.py`（输出稳定性：排序/去随机）

**勾选清单**
- [ ] WHAT：`py -3 -m pytest -m 'not integration' scripts/rdc_analyzer/tests` 通过  
      WHY：没有测试的 A 无法长期演进；每次改动都会让结果漂移  
      HOW：修复 fixture/标记 integration；把需要 renderdoc 环境的用例隔离
- [ ] WHAT：同一输入多次运行，除 timestamp 外输出稳定（排序稳定）  
      WHY：否则 B/C 无法复用；A 的对比验证也会被噪声污染  
      HOW：对 JSON 输出排序、对列表按稳定 key 排序（event_id/resource_id）
- [ ] WHAT：建立一个“基准样例集”的验证方式（可以不提交大文件）  
      WHY：A 的回归验证必须有样例；否则只能靠人工直觉  
      HOW：用内部路径/CI artifact 管理 sample capture，并固定一套验证命令

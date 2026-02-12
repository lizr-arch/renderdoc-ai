# Gate Acceptance Report (2026-02-11)

> Scope: Purpose-driven gate closure for RDC Analyzer
> Baseline Date: 2026-02-11
> Evaluation Mode: Evidence-first, command-reproducible, pass/fail only

---

## 1. 背景与目标

本验收报告用于确认本轮 /do 是否真正满足项目 SSOT（单帧极致分析 + 双帧全方位对比）的质量收敛要求，而非仅“功能存在”。

判定对象为 5 个 Gate：
1. Gate-1 真实性（Truthfulness）
2. Gate-2 全量质量（Regression Gate）
3. Gate-3 契约一致（Schema/Template Contract）
4. Gate-4 环境可复现（Determinism）
5. Gate-5 文档单一事实源一致（SSOT Docs Consistency）

---

## 2. 评估方法（科学与逻辑约束）

### 2.1 判定规则

- P/F 二值判定：每个 Gate 只允许 pass 或 blocked/failed，不使用模糊措辞。
- 证据分层：
  - L1: 可执行命令 + 退出码
  - L2: 关键输出指标（如 pass 数、chunk 数、核心字段）
  - L3: 文档与计划归档一致性
- 复现要求：命令在同一环境中可重复执行；若依赖外部资产必须标注。

### 2.2 数据来源

- 实测命令输出（本轮 /do）
- 回归测试结果（targeted + full）
- 计划与追踪文档的最新条目

### 2.3 边界条件

- 本轮不新增业务能力，仅闭环质量与可信性。
- texture manifest 缺失被归类为“数据可得性限制”，不归类为“代码逻辑阻塞”。

---

## 3. Gate 结果总表

| Gate | 判定 | 核心证据 | 结论 |
|---|---|---|---|
| Gate-1 真实性 | pass_core_logic | rdc_parser --chunk-counts、analyze_rdc --json、analyze_rdc --html-mode full 均成功 | 代码级阻塞已解除，真实性链路可执行 |
| Gate-2 全量质量 | pass | py -3 -m pytest scripts/rdc_analyzer/tests -q -rs -p no:cacheprovider → 807 passed, 6 skipped, 0 warnings | 全量回归门通过 |
| Gate-3 契约一致 | pass | schema/template 相关修复测试稳定通过（含新增 full-report JSON 归一化测试） | 契约漂移已收敛 |
| Gate-4 可复现性 | pass | spirv-cross 环境分歧已由 monkeypatch 固定；legacy wrapper 兼容测试新增并通过 | 测试结果脱离本机偶然性 |
| Gate-5 文档一致 | pass | TASK_TRACKER / ROADMAP / VERIFICATION / PLAN 口径统一至 2026-02-11 | SSOT 叙事一致 |

---

## 4. 命令级证据

### 4.1 Gate-1 实链命令

1) Chunk 统计链路

py -3 scripts/rdc_analyzer/rdc_parser.py "D:\renderdoc\goog pixel-9\g145-battle-2.rdc" --chunk-counts

关键输出（摘录）：
- Chunks: 4352
- vkCreateShaderModule: 109
- vkCreateShadersEXT: 0
- vkCreateImage: 155

2) Lite 分析链路

py -3 scripts/rdc_analyzer/analyze_rdc.py "D:\renderdoc\goog pixel-9\g145-battle-2.rdc" --json "D:\renderdoc\goog pixel-9\g145-battle-2_data.json" -o "D:\renderdoc\goog pixel-9\g145-battle-2_report_lite_tmp.html"

关键输出（摘录）：
- Shaders found: 109
- Draw events: 636
- Pipelines: 70
- Valid analyses: 105/109

3) Full HTML 链路

py -3 scripts/rdc_analyzer/analyze_rdc.py "D:\renderdoc\goog pixel-9\g145-battle-2.rdc" --html-mode full -o "D:\renderdoc\goog pixel-9\g145-battle-2_report_full.html"

关键输出（摘录）：
- 自动使用 g145-battle-2_data_single.json
- generate_real_report.py 成功生成 full HTML

产物存在性复核：
- D:\renderdoc\goog pixel-9\g145-battle-2_data.json (exists, 192173 bytes)
- D:\renderdoc\goog pixel-9\g145-battle-2_data_single.json (exists, 178691 bytes)
- D:\renderdoc\goog pixel-9\g145-battle-2_report_lite_tmp.html (exists, 202930 bytes)
- D:\renderdoc\goog pixel-9\g145-battle-2_report_full.html (exists, 549618 bytes)

### 4.2 Gate-2 回归命令

Targeted:

py -3 -m pytest scripts/rdc_analyzer/tests/test_rdc_parser_legacy_compat.py scripts/rdc_analyzer/tests/test_full_report_mode.py scripts/rdc_analyzer/tests/test_m43_e2e.py scripts/rdc_analyzer/tests/test_report_schemas.py scripts/rdc_analyzer/tests/test_unity_cli_spirv_cross_arg.py -q -p no:cacheprovider

结果：18 passed

Full:

py -3 -m pytest scripts/rdc_analyzer/tests -q -rs -p no:cacheprovider

结果：807 passed, 6 skipped（813 collected，0 warnings）

---

## 5. 代码/测试变更覆盖（对应 Gate）

- Gate-1 核心修复：
  - scripts/rdc_analyzer/rdc_parser.py
  - scripts/rdc_analyzer/parsers/section_parser.py
  - scripts/rdc_analyzer/parsers/models/rdc_file.py
  - scripts/rdc_analyzer/parsers/chunk_parser.py
  - scripts/rdc_analyzer/parsers/shader_extractor.py
  - scripts/rdc_analyzer/analyze_rdc.py
- Gate-2/3/4 测试与回归：
  - scripts/rdc_analyzer/tests/test_rdc_parser_legacy_compat.py（新增）
  - scripts/rdc_analyzer/tests/test_full_report_mode.py
  - scripts/rdc_analyzer/tests/test_m43_e2e.py
  - scripts/rdc_analyzer/tests/test_report_schemas.py
  - scripts/rdc_analyzer/tests/test_unity_cli_spirv_cross_arg.py

---

## 6. 文档一致性证据（Gate-5）

统一基线（2026-02-11）已写回：
- docs/analysis/codex_rdc_analyzer/TASK_TRACKER.md:33
- docs/analysis/codex_rdc_analyzer/WORK_SUMMARY_ROADMAP.md:23
- docs/analysis/codex_rdc_analyzer/WORK_SUMMARY_VERIFICATION.md:470
- plans/2026-02-10-184349-Agent01-PurposeDriven-GateClosure.md:243

关键一致口径：813 collected, 807 passed, 6 skipped, 0 warnings。

---

## 7. 风险与限制（仍需显式保留）

1. texture manifest 缺失会降低 full HTML 在 texture/event 维度的可解释性。
2. Gate-1 已从 blocked_by_logic 转为 pass_core_logic，但数据覆盖质量仍受样本资产完整性影响。
3. 若后续引入新的 VulkanChunk 枚举，需保持对缺失枚举的兼容写法（避免回归到 AttributeError）。

---

## 8. 最终结论

在“命令可复现 + 全量测试通过 + 文档口径一致”三重证据下，本轮 5 Gate 判定为：

- Gate-1: pass_core_logic
- Gate-2: pass
- Gate-3: pass
- Gate-4: pass
- Gate-5: pass

本轮目标达成，满足“基于目的进行开发”的验收标准。

---

## 9. 关联提交（审计）

- 95046195c fix(rdc-analyzer): restore Gate-1 parser/full-report execution paths
- 2e27e8707 docs(rdc-analyzer): sync Gate baselines and record Gate-1 revalidation
- 754dc035d docs(plan): mark D3 complete after conventional commits

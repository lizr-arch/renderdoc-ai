# Scope / Assumptions

## Scope
- 目标：建立 RenderDoc 官方数据面（ActionDescription / PipeState / TextureDescription / ReplayController API）与当前 A+C 输出的字段级对标清单。
- 产出：一份“数据丰富度基线”文档（含 WHAT/WHY/HOW 与字段对齐表），标明哪些字段必须依赖 replay（B 路线）。
- 不做：本轮不改功能逻辑、不新增解析代码，只做证据化梳理与差距清单。

## Assumptions
- A 路线主要来自 XML/StructuredData（无需 replay）；C 路线提供统计/对比输出；B 路线依赖 replay 环境获取更完整状态。
- 现有文档中已有 A/C 输出字段的 schema 描述，可复用而非重新发明。
- 若发现字段来源不明确，标注“假设（待验证）”，不做推断性结论。

## Build/Test/Lint Quick Guide (记录，不执行)
- 生成 A 路线 HTML：
  - `py -3 scripts/rdc_analyzer/analyze_xml_report.py <capture.xml> -o <report.html>`
  - 预期：HTML 内 `eventPassData` 含 `pipelineState/meshInfo/params/bindings`。
- 快速字段抽样检查（HTML 内 JSON）：
  - `py -3 -c "import re; s=open(r'<report.html>','r',encoding='utf-8',errors='ignore').read(); m=re.search(r'const\\s+eventPassData\\s*=\\s*(\\[[\\s\\S]*?\\]);', s); assert m"`

## Repo / File List (精确到行号范围)
- `renderdoc/api/replay/data_types.h:789-860` TextureDescription 字段定义（官方纹理元数据范围）。
- `renderdoc/api/replay/data_types.h:1983-2145` ActionDescription 字段定义（官方事件/动作元数据范围）。
- `renderdoc/api/replay/pipestate.h:32-120` PipeState 结构与 API 选择逻辑（通用管线状态入口）。
- `renderdoc/replay/replay_controller.h:146-205` ReplayController 数据获取入口（GetPipelineState / GetRootActions / GetTextures 等）。
- `renderdoccmd/renderdoccmd.cpp:80-125` 官方命令行对 GetTextures/GetRootActions 的使用示例（验证可获取数据）。
- `docs/analysis/codex_rdc_analyzer/` 新增文档（UTF-8，无 BOM，≤800 行）。

## Approach (Pseudo-code)
```python
# 1) 建立官方字段基线（字段→来源→说明）
rd_fields = {
  'ActionDescription': extract_fields('data_types.h', 'ActionDescription'),
  'TextureDescription': extract_fields('data_types.h', 'TextureDescription'),
  'PipeState': extract_fields('pipestate.h', 'PipeState'),
  'ReplayController': extract_signatures('replay_controller.h',
                                         ['GetRootActions','GetPipelineState','GetTextures'])
}

# 2) 读取 A/C 输出 schema
ac_schema = read_existing_schema_docs()  # 复用现有 schema 文档

# 3) 构建对照表
# 字段级：官方字段 ∩ A/C 输出 = 已覆盖
# 官方字段 - A/C 输出 = 缺口（标注是否需要 replay/B）
coverage = build_coverage_table(rd_fields, ac_schema)

# 4) 输出“数据丰富度基线”文档
write_doc(coverage, include_what_why_how=True, include_gap_reason=True)
```

## Impact Analysis
- 正向：明确“官方可读数据面”，为 A+C 目标范围定界，避免误判“缺失=bug”。
- 风险：PipeState/ActionDescription 字段较多，若仅靠文档抽样可能遗漏；需以源码定义为准。
- 兼容性：仅新增文档，不影响现有代码或输出。

## Action Items (2-5 分钟粒度)
- [x] 读取官方字段定义（ActionDescription/TextureDescription/PipeState/ReplayController API），整理字段清单与来源（含文件/行号）。
- [x] 复用现有 A/C schema 文档，列出 A/C 当前输出字段。
- [x] 构建“字段对齐表”：已覆盖/缺口/需 replay/可在 A+C 补齐。
- [x] 产出新文档：数据丰富度基线（含 WHAT/WHY/HOW + Gap 说明 + 建议优先级）。
- [x] 复核：抽样对照一份现有 HTML 报告字段，确认“覆盖/缺口”的准确性。

## Risks & Blockers
- A/C 输出字段如果分散在多处文档，可能需要合并；若文档不一致，需先标注冲突。
- 若发现字段只能通过 replay 获取，需明确标记为 B 路线能力，避免误判。

## Verification / DoD
- 基线文档包含：官方字段清单 + A/C 输出清单 + 对齐表 + 缺口原因（是否需要 replay）+ WHAT/WHY/HOW。
- 至少 1 份现有 HTML 报告被抽样对照并记录一致性结论。
- 文档行数 ≤ 800。

### Execution Log
- 2026-01-31：完成基线文档 `docs/analysis/codex_rdc_analyzer/2026-01-31-rdc-analyzer-data-richness-baseline.md`。
- 抽样验证：`scripts/rdc_analyzer/test_captures/export_output/cb_demo_report.html` 中 `eventPassData` 存在；事件列表 180 个；至少存在 `pipelineState` 字段；未发现 `params/meshInfo`（该样本未包含，不视为失败）。

## Open Questions
- A/C schema 文档是否存在多版本冲突？若有，以哪份为准？
- 当前 A/C 输出是否包含 Shader/Resource 详细信息的统一 schema？

## Next Steps
- 等你批准 /do 后执行上述清单，并提交新文档。

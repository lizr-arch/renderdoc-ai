# Scope / Assumptions

## Scope
- 自动同步文档索引：扫描 `docs/analysis/codex_rdc_analyzer/` 与 `scripts/rdc_analyzer/docs/` 及 `.ai/INDEX.md`，把新文档自动纳入索引并校正阅读顺序。
- 按“数据丰富度基线”优化 A/C 输出：仅使用**明确来源字段**（XML/已解析数据），不做近似；缺失字段必须给出**原因**。
- 产出：同步脚本 + 数据丰富度覆盖/缺口输出（HTML/JSON 内含覆盖信息）+ 对应文档更新。

## Assumptions
- 文档索引有固定格式（DOC_INDEX/WORK_SUMMARY/rdc_analyzer docs index），可通过脚本安全更新。
- A 路线数据上限由 `parse_rdc_xml.py` 与 XML 内容决定；不可凭空补字段。
- “不允许近似” => 任何估算字段必须明确标注“无法计算/需 replay”。

## Build/Test/Lint Quick Guide (记录，不执行)
- 文档索引同步脚本：
  - `py -3 scripts/rdc_analyzer/tools/sync_doc_indexes.py`
  - 预期：更新 DOC_INDEX / WORK_SUMMARY / rdc_analyzer docs index，输出变更统计。
- A 路线 HTML 生成：
  - `py -3 scripts/rdc_analyzer/analyze_xml_report.py <capture.xml> -o <report.html>`
  - 预期：HTML 内包含 `dataRichness`/`coverage` 字段并列出缺失原因。

---

## Repo / File List (精确到行号范围)

### 索引同步相关
- `docs/analysis/codex_rdc_analyzer/DOC_INDEX.md:9` 阅读顺序段
- `docs/analysis/codex_rdc_analyzer/WORK_SUMMARY_2025-01-21.md:25` 推荐阅读顺序段
- `docs/analysis/codex_rdc_analyzer/WORK_SUMMARY_2025-01-21.md:61` 文档清单段
- `scripts/rdc_analyzer/docs/INDEX.md:9` 快速导航段
- `scripts/rdc_analyzer/.ai/INDEX.md:9` 项目索引概览段

### 数据丰富度对标与输出相关
- `scripts/rdc_analyzer/parse_rdc_xml.py:524` XML 解析主入口
- `scripts/rdc_analyzer/core/bridge.py:28` XMLToContextBridge
- `scripts/rdc_analyzer/analyze_xml_report.py:313` HTML 数据生成入口
- `scripts/rdc_analyzer/analyze_xml_report.py:427` 纹理元数据加载
- `scripts/rdc_analyzer/generate_real_report.py:175` 资源绑定转换
- `scripts/rdc_analyzer/generate_real_report.py:418` pipelineState bindings 转换

### 标准基线文档
- `docs/analysis/codex_rdc_analyzer/2026-01-31-rdc-analyzer-data-richness-baseline.md:1`

---

## Approach (Pseudo-code)

### A) 文档索引自动同步（脚本）
```python
# scripts/rdc_analyzer/tools/sync_doc_indexes.py
DOC_ROOT = Path("docs/analysis/codex_rdc_analyzer")
TOOL_DOC_ROOT = Path("scripts/rdc_analyzer/docs")

def scan_docs(root: Path) -> list[Doc]:
    # 仅收集 .md 文件，跳过 WORK_SUMMARY_*.md / TASK_TRACKER / 目录索引本身
    # 读取首个 H1 作为标题；若未找到关键词/路线信息 -> 标注 "未提供"
    return docs

def update_doc_index(docs: list[Doc]):
    # 更新 DOC_INDEX 的“阅读顺序”与“文档条目”
    # 无法解析的字段必须写明原因，如 "关键词：未标注（原因：源文档无关键词段）"
    pass

def update_work_summary(docs: list[Doc]):
    # 更新推荐阅读顺序与文档清单
    pass

def update_tool_docs_index(tool_docs: list[Doc]):
    # 更新 scripts/rdc_analyzer/docs/INDEX.md
    pass

def update_ai_index(docs: list[Doc]):
    # 更新 scripts/rdc_analyzer/.ai/INDEX.md 里的外部索引入口
    pass
```

### B) 数据丰富度对齐（A/C 输出）
```python
# scripts/rdc_analyzer/schema/data_richness_baseline.py
ACTION_FIELDS = ["eventId","actionId","customName","flags","numIndices","numInstances",
                 "baseVertex","indexOffset","vertexOffset","instanceOffset",
                 "dispatchDimension","dispatchThreadsDimension","dispatchBase",
                 "copySource","copyDestination","outputs","depthOut","events","children"]
TEXTURE_FIELDS = ["format","dimension","type","width","height","depth",
                  "resourceId","cubemap","mips","arraysize","creationFlags",
                  "msQual","msSamp","byteSize"]

def compute_missing(expected: list[str], actual_keys: set[str], reason: str) -> list[dict]:
    return [{"field": f, "reason": reason} for f in expected if f not in actual_keys]
```

```python
# scripts/rdc_analyzer/analyze_xml_report.py
from schema.data_richness_baseline import ACTION_FIELDS, TEXTURE_FIELDS, compute_missing

# 在事件合并后：
event["coverage"] = {
  "missing": compute_missing(ACTION_FIELDS, set(event.keys()),
                             "Not in XML / requires replay"),
}

# 在 textures 输出后：
texture["coverage"] = {
  "missing": compute_missing(TEXTURE_FIELDS, set(texture.keys()),
                             "Not in XML / requires replay"),
}
```

> 规则：**不允许近似**。若缺失字段不可计算，必须输出 `reason`。

---

## Impact Analysis
- 正向：索引自动同步减少漏文档风险；A/C 输出有明确“缺失原因”可解释。
- 风险：索引脚本需确保幂等性（多次运行不抖动）。
- 兼容性：新增字段应为“附加字段”，避免破坏现有 HTML 结构。

---

## Action Items (2-5 分钟粒度)
- [x] 实现 `sync_doc_indexes.py`：扫描/同步 DOC_INDEX + WORK_SUMMARY + 工具索引 + AI 索引。
- [x] 为基线字段建立代码常量模块（Action/Texture 字段列表）。
- [x] A 路线事件输出增加 `coverage.missing[]` 与原因（严格不近似）。
- [x] A 路线纹理输出增加 `coverage.missing[]` 与原因（严格不近似）。
- [x] 更新 DOC_INDEX/WORK_SUMMARY/工具索引说明“数据丰富度基线”为标准入口。
- [x] HTML V3 报告补充 DataTables 缺失时的渲染兜底（避免列表为空）。
- [x] 添加回归测试：HTML 若使用 DataTable 则必须有兜底渲染函数。
- [x] 抽样 HTML 输出验证：确认 coverage/missing 原因正确出现。

---

## Risks & Blockers
- 如果 XML 实际缺少字段，需要明确标注“requires replay”，不能填 0 或估值。
- 索引文档编码混杂，需保持原编码写回（UTF-8/GB18030）。

---

## Verification / DoD
- 索引同步脚本运行后：DOC_INDEX / WORK_SUMMARY / scripts/rdc_analyzer/docs/INDEX.md / .ai/INDEX.md 均包含新文档。
- A 路线 HTML：事件与纹理对象包含 `coverage.missing[]` 且理由明确。
- 任何缺失字段**没有**估算值，原因注明“Not in XML / requires replay”。

### Execution Log
- 2026-01-31：新增 `scripts/rdc_analyzer/tools/sync_doc_indexes.py` 并运行完成索引同步。
- 2026-01-31：新增 `schema/data_richness_baseline.py`，A 路线事件/纹理输出增加 `coverage`。
- 2026-01-31：`analyze_rdc.py` 增加 DataTables 缺失兜底渲染，避免 shader/texture 列表为空。
- 2026-01-31：运行 `py -3 -m pytest scripts/rdc_analyzer/tests/test_datatables_fallback.py` ✅
- 2026-01-31：抽样验证 `g145_battle2_report_xml.html`（events=625/coverage 缺失原因存在；textures=155/coverage 缺失原因存在）。

---

## Open Questions
- 无（已确认：纳入自动同步；两项都做；不允许近似，缺失给原因）。

---

## Next Steps
- 等你批准 /do 后执行以上清单并提交。

# Report Professionalism Max-Out Plan (Single-Frame, WebUI + Offline)

**Version:** 2026-02-25  
**Owner:** Agent01  
**Last Updated:** 2026-02-25 17:02:51  
**Plan File:** `plans/2026-02-25-170251-Agent01-Report-Professionalism-Max.md`

## Scope / Assumptions

### Scope (In)
- 提升单帧报告的“专业度可信闭环”：
  - 统一 `suggestions` / `recommendations` 报告契约
  - 报告首页显式展示 `coverage` / `data_richness` / `preflight`
  - Canonical issue 渲染优先使用 `code/message/event_ids/resource_ids/evidence`
  - 对估算指标增加“估算值/假设来源”标识，避免误导为实测
  - 增加契约测试，防止回归

### Scope (Out)
- 不新增新的大页面（如单独 Pipeline/Uniforms 新页面）
- 不改多帧对比引擎
- 不改 RenderDoc C++ 核心回放逻辑

### Assumptions
- `analysis.json` 继续作为 SSOT。
- 报告仍由 `report_from_analysis.py -> ReportBundleGenerator` 生成。
- WebUI/离线共用模板机制不变（只增强字段与展示）。

---

## Build / Test / Lint Quick Guide (记录，不在 /plan 执行)

### Python Tests
1. `py -3 -m pytest scripts/rdc_analyzer/tests/test_report_issue_export.py -v --tb=short`  
   预期: `PASSED`
2. `py -3 -m pytest scripts/rdc_analyzer/tests/test_report_issue_jump_links.py -v --tb=short`  
   预期: `PASSED`
3. `py -3 -m pytest scripts/rdc_analyzer/tests/test_webui_server.py -k jump -v --tb=short`  
   预期: `PASSED`
4. `py -3 -m pytest scripts/rdc_analyzer/tests/test_webui_jump_queue.py -v --tb=short`  
   预期: `PASSED`
5. `py -3 -m pytest scripts/rdc_analyzer/tests/test_dod_compliance.py -k "coverage or preflight or verification_plan" -v --tb=short`  
   预期: `PASSED`
6. `py -3 -m pytest scripts/rdc_analyzer/tests/test_report_schemas.py -v --tb=short`  
   预期: `PASSED`
7. `py -3 -m pytest scripts/rdc_analyzer/tests/test_report_professionalism_contract.py -v --tb=short`  
   预期: `PASSED`

### Optional Full Gate
8. `py -3 -m pytest scripts/rdc_analyzer/tests -v --tb=short`  
   预期: 全绿（或仅已知与本次无关用例失败并记录）

---

## File List (精确到行号范围)

### Core implementation
1. `scripts/rdc_analyzer/report_bundle_generator.py`
- `307-319`: `set_performance_data()`（契约统一入口）
- `539-639`: index 问题列表渲染（canonical 字段优先）
- `646-678`: index replacements（新增质量卡字段）
- `1127-1180`: `generate_recommendations()`（读取 suggestions 兼容 recommendations）
- `1408-1434`: manifest stats 扩展（可选写入质量摘要）
- `1036-1054`, `1372-1387`: dynamicMetrics 默认值处（估算标记）

2. `scripts/rdc_analyzer/report_from_analysis.py`
- `96-113`: 生成入口（透传 data 完整字段给 generator，保持 issues 导出）
- `18-51`: issue 归一化（保留 canonical 字段优先级）

3. `scripts/rdc_analyzer/templates/index.html`
- `377-544` 附近：新增“数据可信度卡片/Preflight 状态区块”占位和样式位

4. `scripts/rdc_analyzer/templates/shaders.html`
- `1549-1562`: 加权成本公式展示说明（1080p 假设提示）
- `2055-2060` 附近：dynamicMetrics fallback 处加 `estimated` 标记消费

5. `scripts/rdc_analyzer/templates/recommendations.html`
- `736-788` 附近：证据链中补充 confidence/估算提示入口（若字段存在）

### Tests / docs
6. `scripts/rdc_analyzer/tests/test_report_schemas.py`
- 增加质量字段与新契约断言（非仅 schema 文件存在）

7. `scripts/rdc_analyzer/tests/test_report_issue_jump_links.py`
- 增加 `coverage/preflight` 入口链接或标识存在性断言

8. `scripts/rdc_analyzer/tests/test_report_professionalism_contract.py` (new)
- 新增专业度契约测试（建议字段/可信度/估算标识）

9. `scripts/rdc_analyzer/docs/WEBUI_AND_UI_EXTENSION.md`
- 更新“已知限制/验收项”：加入可信度面板与估算值标识验收点

---

## Design / Pseudocode (完整实现草案)

### A. 统一建议契约（`suggestions` as SSOT, `recommendations` 兼容）

```python
# report_bundle_generator.py

def _normalize_suggestions(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
    raw = data.get("suggestions")
    if not raw:
        raw = data.get("recommendations", [])

    normalized = []
    for i, item in enumerate(raw or []):
        if not isinstance(item, dict):
            normalized.append({
                "id": f"SUG-{i+1:03d}",
                "severity": "info",
                "category": "general",
                "title": str(item)[:80],
                "description": str(item),
                "suggestion": "",
                "impact": "",
                "verification_plan": {},
                "confidence": "unknown",
                "estimated": False,
            })
            continue

        normalized.append({
            "id": item.get("id") or item.get("rule_id") or f"SUG-{i+1:03d}",
            "severity": item.get("severity") or item.get("priority") or "info",
            "category": item.get("category", "general"),
            "title": item.get("title") or item.get("message") or "",
            "description": item.get("description") or item.get("detail") or item.get("message") or "",
            "suggestion": item.get("suggestion") or item.get("action") or "",
            "impact": item.get("impact") or item.get("expected_impact", ""),
            "verification_plan": item.get("verification_plan", {}),
            "confidence": item.get("confidence", "unknown"),
            "estimated": bool(item.get("estimated", False)),
        })

    return normalized


def set_performance_data(self, data: Dict):
    self.performance_data = data or {}
    issues = data.get("issues", [])
    self.stats["issues"] = issues
    self.stats["issues_count"] = len(issues)

    suggestions = self._normalize_suggestions(self.performance_data)
    self.stats["suggestions"] = suggestions
    # backward compatibility, existing render paths may still read recommendations
    self.stats["recommendations"] = suggestions

    self.stats["coverage"] = self.performance_data.get("coverage", {})
    self.stats["data_richness"] = self.performance_data.get("data_richness", {})
    self.stats["preflight"] = self.performance_data.get("preflight", {})
```

### B. Canonical issue 渲染优先级

```python
# report_bundle_generator.py

def _canonical_issue_title(issue: Dict[str, Any]) -> str:
    code = issue.get("code") or issue.get("rule") or issue.get("rule_id")
    msg = issue.get("message") or issue.get("title") or "Unknown Issue"
    return f"[{code}] {msg}" if code else msg


def _canonical_issue_desc(issue: Dict[str, Any]) -> str:
    evs = issue.get("event_ids") or issue.get("eventIds") or []
    res = issue.get("resource_ids") or issue.get("resourceIds") or []
    parts = []
    if evs:
        parts.append(f"EID: {','.join(str(v) for v in evs[:3])}")
    if res:
        parts.append(f"RES: {','.join(str(v) for v in res[:2])}")
    evidence = issue.get("evidence")
    if isinstance(evidence, dict) and evidence:
        parts.append("含证据")
    return " | ".join(parts)
```

### C. 首页新增“数据可信度卡”

```python
# report_bundle_generator.py -> generate_index replacements

coverage = self.stats.get("coverage", {})
preflight = self.stats.get("preflight", {})
richness = self.stats.get("data_richness", {})

quality_level = coverage.get("overall", "unknown")
preflight_status = preflight.get("status", "unknown")
missing_count = len(preflight.get("missing_data", []))
confidence_reasons = coverage.get("confidence_reasons", [])[:3]

replacements.update({
    "QUALITY_LEVEL": str(quality_level),
    "PREFLIGHT_STATUS": str(preflight_status),
    "PREFLIGHT_MISSING_COUNT": str(missing_count),
    "QUALITY_REASONS": "<br>".join(confidence_reasons) if confidence_reasons else "无",
    "RICHNESS_ROUTE_A": str((richness.get("routes", {}).get("A", {}).get("coverage", "unknown"))),
    "RICHNESS_ROUTE_C": str((richness.get("routes", {}).get("C", {}).get("coverage", "unknown"))),
})
```

### D. 估算指标显式标识

```python
# report_bundle_generator.py dynamicMetrics 注入处
shader_copy["dynamicMetrics"] = {
    "drawCount": draw_count,
    "pixelCoverage": round(estimated_coverage, 2),
    "viewportWidth": 1920,
    "viewportHeight": 1080,
    "estimated": True,
    "assumption": "viewport=1920x1080; coverage=heuristic-by-pass-name",
}
```

```javascript
// shaders.html
const est = dynamicMetrics?.estimated === true;
const assumption = dynamicMetrics?.assumption || '';
if (est) {
  showMetricBadge('Estimated', `估算指标: ${assumption}`);
}
```

### E. recommendations 页统一读取 suggestions

```python
# report_bundle_generator.py -> generate_recommendations()
issues = self.performance_data.get("issues", []) if self.performance_data else []
suggestions = self.performance_data.get("suggestions")
if not suggestions:
    suggestions = self.performance_data.get("recommendations", [])

for rec in suggestions:
    # mapping 同 _normalize_suggestions
    ...
```

---

## Task Checklist (2-5 分钟粒度, TDD 强制)

### Slice 1: 契约统一（suggestions/recommendations）
- [x] `[3m]` 新增测试骨架 `test_report_professionalism_contract.py`，写入 `suggestions 优先` 失败用例
- [ ] `[2m]` 运行单测确认失败（期望: assertion fail）【阻塞：当前 WSL 环境缺少 pytest】
- [x] `[4m]` 在 `set_performance_data()` 增加 `_normalize_suggestions()` 最小实现
- [ ] `[3m]` 运行单测确认通过【阻塞：当前 WSL 环境缺少 pytest】
- [x] `[2m]` 提交 `feat(rdc-analyzer): unify suggestions contract for bundle report`（合并提交见 `99e9cadd9`）

### Slice 2: Canonical issue 渲染
- [x] `[3m]` 新增失败测试：issue 仅有 `code/message/event_ids` 时首页仍可渲染标题和 EID
- [x] `[4m]` 修改 `generate_index()` fallback 渲染优先 canonical 字段
- [ ] `[2m]` 运行对应测试并确认通过【阻塞：当前 WSL 环境缺少 pytest】
- [x] `[2m]` 提交 `fix(rdc-analyzer): prioritize canonical issue fields in index rendering`（合并提交见 `99e9cadd9`）

### Slice 3: 可信度面板（coverage/data_richness/preflight）
- [x] `[3m]` 新增失败测试：`index.html` 渲染包含 `QUALITY_LEVEL/PREFLIGHT_STATUS`
- [x] `[4m]` 修改 `index.html` 模板，加入质量卡 UI 占位
- [x] `[4m]` 修改 `generate_index()` replacements 注入质量字段
- [ ] `[2m]` 运行测试确认通过【阻塞：当前 WSL 环境缺少 pytest】
- [x] `[2m]` 提交 `feat(rdc-analyzer): surface coverage and preflight in overview`（合并提交见 `99e9cadd9`）

### Slice 4: 估算值强标识
- [x] `[3m]` 新增失败测试：`shaders_data` 中 `dynamicMetrics.estimated==true`
- [x] `[4m]` 修改 `report_bundle_generator.py` dynamicMetrics 输出 `estimated/assumption`
- [x] `[3m]` 修改 `shaders.html` 显示 estimated badge + assumption tooltip
- [ ] `[2m]` 运行测试确认通过【阻塞：当前 WSL 环境缺少 pytest】
- [x] `[2m]` 提交 `feat(rdc-analyzer): label heuristic shader metrics as estimated`（合并提交见 `99e9cadd9`）

### Slice 5: 文档与回归
- [x] `[3m]` 更新 `WEBUI_AND_UI_EXTENSION.md` 验收项（可信度卡 + 估算标识）
- [ ] `[3m]` 运行回归集（issue export/jump/schema/dod + 新增契约测试）【阻塞：当前 WSL 环境缺少 pytest】
- [x] `[2m]` 汇总结果并更新 plan 勾选状态
- [ ] `[2m]` 提交 `docs(rdc-analyzer): add professionalism acceptance items`

---

## Risks / Blockers

1. 旧报告数据仍只产出 `recommendations`。
- 影响: 新逻辑可能空列表。
- 缓解: 双读（`suggestions` 优先，`recommendations` 回退）并加测试锁定。

2. 质量字段在部分 route 缺失。
- 影响: 质量卡空值或模板异常。
- 缓解: 全部字段走默认值；缺失时显示 `unknown` + 文案提示。

3. 估算标识可能引发“分值下降”感知。
- 影响: 用户视觉上感觉问题更多。
- 缓解: 明确“估算≠错误”，并给出提升数据质量的 preflight 建议。

4. 测试环境差异（WSL 无 `py` / 无 pytest）。
- 影响: 本地无法直接跑回归。
- 缓解: 计划中保留 Windows `py -3` 标准命令，由用户环境执行；若在 WSL 则 `python3 -m pytest`。

5. /do 实际阻塞记录（2026-02-25）。
- 已尝试: `python3 -m pytest ...`，报错 `No module named pytest`。
- 已做替代验证: `python3 -m py_compile ...` + 运行时 smoke（`generate_index/generate_shaders/generate_recommendations`）通过。
- 后续建议: 在可用 Python 测试环境执行本计划中的 pytest 回归命令。

---

## Impact Analysis

### Data Contract
- 正向: 统一建议结构，减少“数据有但页面不显示”。
- 兼容: 保留 `recommendations` 回退，不破坏老数据。
- 风险: 映射错误导致字段丢失，靠新增契约测试覆盖。

### UI / UX
- 正向: 用户可直接判断结论可信度（high/medium/low + preflight warning/error）。
- 正向: 估算指标明确标识，提高报告可信性与专业口径。
- 风险: 首页信息密度增加，需要控制卡片层级和默认折叠。

### Test / Maintenance
- 正向: 从“按钮存在”提升到“契约正确 + 专业标识正确”的回归保障。
- 风险: 新测试较依赖模板文案，建议断言关键 data-attribute 而不是整段文本。

---

## Decisions

1. **SSOT 决策**：建议字段以 `suggestions` 为主，`recommendations` 仅兼容读取。  
2. **可信度优先**：报告首页必须先回答“结论可信到什么程度”。  
3. **估算值可见**：任何启发式/默认分辨率推导，必须显式标记 `estimated`。  
4. **不扩页先补质**：先补契约和可信度，再考虑新增 Pipeline/Uniforms 独立页。

---

## Verification / Acceptance (Definition of Done)

### Functional DoD
- [x] 报告在仅有 `suggestions`、无 `recommendations` 时仍完整显示优化建议。
- [x] 首页出现“数据可信度”区块，显示 coverage/preflight/richness 摘要。
- [x] issue 列表对 canonical issue（`code/message/event_ids/resource_ids/evidence`）渲染正确。
- [x] shaders 页对启发式指标显示 `Estimated` 标识及假设说明。
- [ ] `/api/jump` 与 issues 导出能力不回退。

### Test DoD
- [ ] 新增 `test_report_professionalism_contract.py` 全绿。（阻塞：当前环境缺少 pytest）
- [ ] `test_report_issue_export.py` / `test_report_issue_jump_links.py` / `test_report_schemas.py` / 关键 `test_dod_compliance.py` 全绿。（阻塞：当前环境缺少 pytest）
- [ ] 若执行全量测试，失败项需在 plan 中记录并标注是否与本改动相关。

### Quality DoD
- [x] 页面上不存在“估算值伪装成实测值”的文案。
- [x] 关键数据缺失时，用户能从 preflight 文案知道“如何重抓”。

---

## Next Steps

1. 用户确认本 plan。  
2. 进入 `/do` 按 Slice 1~5 执行并逐项勾选。  
3. 每个独立 Slice 完成后立即按 Conventional Commits 提交。

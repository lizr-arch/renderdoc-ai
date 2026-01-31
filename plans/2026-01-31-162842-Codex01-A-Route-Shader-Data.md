# A 路线补齐 Shader/事件数据 + 目标写入 Agents.md Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Version:** 2026-01-31  
**Owner:** Codex01  
**Last Updated:** 2026-01-31  
**Plan File:** plans/2026-01-31-162842-Codex01-A-Route-Shader-Data.md

**Goal:**  
1) A 路线 HTML 报告默认包含 Shader 列表与 Event Browser 的 shader 绑定信息；  
2) 将项目“核心目标”写入 `Agents.md`，作为全局规范。

**Scope:** 仅修复 A 路线“接线缺失”与文档目的说明；不新增解析功能。  
**Out of Scope:** B 路线回放 / C 路线导出 / RenderDoc UI 导出。

**Success Criteria (measurable):**
- A 路线 HTML 中 `shaderData` 不为空（来自 XML 的 `shaders` 字段）。
- A 路线 HTML 中事件 `shader_vs/shader_ps` 至少一项非空。
- `Agents.md` 中新增“项目核心目标”说明，且与文档 SSOT 一致。

**Acceptance Criteria:**
- `D:\backup\rdc_reports\大远景\大远景_report.html` 的 `shaderData` 长度 > 0  
- `eventPassData.events` 中至少一条事件 `shader_vs` 或 `shader_ps` 非空  
- `Agents.md` 出现“单帧极致分析 / 双帧全方位对比”目标描述

---

## Scope / Assumptions
- A 路线 XML 已包含 `shaders` 字段（见 `parse_rdc_xml.py`）。
- A 路线 Event Browser 依赖 `draw_call.vs_id/ps_id`。
- 目标来源 SSOT：`WORK_SUMMARY_ARCH.md` 与 `capability-scorecard.md`。

## Build/Test/Lint Quick Guide（仅记录，不执行）
- 本任务不需要构建；只重跑 `analyze_xml_report.py` 验证 HTML。

## Repo / File List（精确到行号范围）
- `scripts/rdc_analyzer/analyze_xml_report.py:422-505`  
  - A 路线 HTML 生成入口（需补传 shader_data）。
- `scripts/rdc_analyzer/core/bridge.py:147-486`  
  - `draw_call.vs_id/ps_id` 提取与 `_extract_shader_id` 映射逻辑。
- `docs/analysis/codex_rdc_analyzer/WORK_SUMMARY_ARCH.md:11-20`  
  - 目标 SSOT 来源（单帧极致分析 / 双帧全方位对比）。
- `docs/analysis/codex_rdc_analyzer/2026-01-19-rdc-analyzer-capability-scorecard.md:20-28`  
  - 两大核心目标与验收口径。
- `Agents.md:8-30`  
  - 项目简介区新增“核心目标”说明。

---

## Approach (Pseudo-code)
```
1) 从 xml_data 读取 shaders 列表，传入 generate_offline_html(shader_data=...)
2) XMLToContextBridge._extract_shader_id 同时识别大小写 key（VS/PS 与 vs/ps）
3) Agents.md 写入核心目标（与 WORK_SUMMARY_ARCH / capability-scorecard 对齐）
4) 重跑 analyze_xml_report.py 生成大远景_report.html 做验证
```

---

## Task Checklist
- [x] TASK-01: A 路线 HTML 接入 shader_data
- [x] TASK-02: A 路线事件 shader 绑定修复（大小写映射）
- [x] TASK-03: Agents.md 写入项目核心目标（SSOT）
- [x] TASK-04: 重跑 A 路线 HTML 并验证

---

### Task 1: A 路线 HTML 接入 shader_data

**WHAT**：把 `parse_rdc_xml` 的 `shaders` 列表传给 `generate_offline_html`。  
**WHY**：当前 HTML `shaderData = []`，导致 Shader 列表为空。  
**HOW**：在 `analyze_xml_report.py` 生成 HTML 时新增 `shader_data=xml_data.get('shaders', [])`。

**Code (完整片段)：**
```python
# scripts/rdc_analyzer/analyze_xml_report.py
shader_data = xml_data.get('shaders', [])
generate_offline_html(
    textures=textures,
    rdc_name=xml_path.stem,
    output_path=output_path,
    event_pass_data=performance_data,
    shader_data=shader_data,
)
```

---

### Task 2: A 路线事件 shader 绑定修复（大小写映射）

**WHAT**：`XMLToContextBridge._extract_shader_id` 支持小写键（vs/ps/…）。  
**WHY**：`parse_rdc_xml` pipelineState 使用小写 key，导致 `vs_id/ps_id` 为空。  
**HOW**：在 `_extract_shader_id` 内部对 key 增加 `.lower()` 变体匹配。

**Code (完整片段)：**
```python
# scripts/rdc_analyzer/core/bridge.py
def _extract_shader_id(cls, shaders: Dict, *keys: str) -> str:
    for key in keys:
        for variant in (key, key.lower()):
            if variant in shaders:
                shader = shaders[variant]
                if isinstance(shader, dict):
                    return str(shader.get('resourceId', '') or shader.get('id', ''))
                return str(shader)
    return ""
```

---

### Task 3: Agents.md 写入项目核心目标（SSOT）

**WHAT**：在 `Agents.md` 项目简介区新增“核心目标”。  
**WHY**：防止偏离“单帧极致分析 + 双帧全方位对比”的项目目的。  
**HOW**：引用 `WORK_SUMMARY_ARCH.md` 与 `capability-scorecard.md` 的目标描述。

**Code (完整片段)：**
```markdown
## 项目核心目标（SSOT）
1. 单帧极致分析：从 .rdc/XML 中提取性能问题并生成可执行建议
2. 双帧全方位对比：baseline vs target 差异分析与结论
```

---

### Task 4: 重跑 A 路线 HTML 并验证

**WHAT**：对 `大远景.xml` 重新生成 HTML 并验证 shader 数据。  
**WHY**：这是你指出的空数据样本，必须闭环验证。  
**HOW**：运行 `analyze_xml_report.py` 并检测 HTML 中 `shaderData`/`eventPassData`。

**Verification Commands:**
```powershell
py -3 scripts\rdc_analyzer\analyze_xml_report.py "D:\backup\rdc_reports\大远景\大远景.xml" -o "D:\backup\rdc_reports\大远景\大远景_report.html"

# 验证 shaderData 非空
py -3 -c "import re,json; t=open(r'D:\backup\rdc_reports\大远景\大远景_report.html',encoding='utf-8').read(); m=re.search(r'const shaderData = (\\[.*?\\]);', t, re.S); print('shaderData_len=', len(json.loads(m.group(1))))"

# 验证事件中存在 shader_vs/ps 非空
py -3 -c "import re,json; t=open(r'D:\backup\rdc_reports\大远景\大远景_report.html',encoding='utf-8').read(); m=re.search(r'const eventPassData = (\\{.*?\\});', t, re.S); data=json.loads(m.group(1)); ok=any(e.get('shader_vs') or e.get('shader_ps') for e in data.get('events',[])); print('event_shader_any=', ok)"
```
Expected:
- `shaderData_len > 0`
- `event_shader_any = True`

---

## Risks & Blockers
- XML pipelineState 中 shader 字段缺失 → 需回溯 XML 导出格式或补解析规则。
- Vulkan 事件可能仅有 Pipeline 对象 ID，不含 shader 绑定 → 需追加解析策略。

## Decisions
- A 路线应默认包含 Shader 列表与 Event Browser Shader 绑定（对标 RenderDoc 数据可视化）。
- 先做“接线补齐”，不做新解析功能。

## Verification / DoD
- HTML 中 `shaderData` 非空，事件 shader 字段存在。
- Agents.md 明确记录核心目标。

## Next Steps
- 等待 `/do` 执行该计划。

---

## Execution Log

### 2026-01-31

- TASK-01 完成：`analyze_xml_report.py` 传入 `shader_data=xml_data.get('shaders', [])`
- TASK-02 完成：`_extract_shader_id` 支持小写键（vs/ps/…）
- TASK-03 完成：`Agents.md` 写入项目核心目标（SSOT）
- TASK-04 完成：重跑 `大远景_report.html` 验证
  - `shaderData_len=339`
  - `event_shader_any=True`

**Deviations:** 无。

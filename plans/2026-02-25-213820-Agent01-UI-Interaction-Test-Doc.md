# 2026-02-25-213820-Agent01-UI-Interaction-Test-Doc

date: 2026-02-25 21:38:20  
agent: Agent01  
stage: /plan

## Scope / Assumptions
- Scope: index/textures/shaders/recommendations 4 个页面（已移除 events 页面）交互盘点、分类、功能说明与测试步骤文档化。
- Output: 新增测试规范文档 + 更新文档索引。
- Assumption: 以模板 HTML/JS 作为交互源数据（静态扫描 + 人工核对）。

## File List (line ranges)
- `scripts/rdc_analyzer/templates/index.html`: 395-525 (导航与统计卡片)
- `scripts/rdc_analyzer/templates/textures.html`: 707-920, 1200-1290, 1530-1605 (搜索/筛选/操作/使用列表)
- `scripts/rdc_analyzer/templates/shaders.html`: 1180-1445, 2030-2280, 2370-2405 (搜索/筛选/代码/使用列表/操作)
- `scripts/rdc_analyzer/templates/recommendations.html`: 486-530, 690-780 (筛选/动作/资源标签)
- `scripts/rdc_analyzer/docs/INDEX.md`: 功能指南段落（新增索引条目）
- `scripts/rdc_analyzer/docs/UI_INTERACTION_TEST_MATRIX.md`: 新文档（待创建）

## Pseudocode
```
run inventory script -> counts by page
for each page in [index, textures, shaders, recommendations]:
  list controls grouped by category:
    - Navigation/Entry
    - Search & Filter
    - Sorting
    - View/Display toggles
    - Selection & Detail
    - Actions (export, compare, jump to GUI)
  for each control:
    record {功能点, 操作, 目标效果, 依赖/数据, 备注}
append "测试步骤" checklist per page using the above controls
write doc + update docs index
```

## Build/Test/Lint Quick Guide (commands only)
- N/A (文档新增)

## Task Checklist (2-5 min each)
- [x] 收集模板中的交互控件（按钮/输入/下拉/链接/事件绑定），并跑脚本得到数量基线。
- [x] 按页面分类整理交互项，补充“功能点/操作/目标效果/依赖数据”说明。
- [x] 在新文档中追加“测试步骤（按页面）”，形成可执行 checklist。
- [x] 更新 `scripts/rdc_analyzer/docs/INDEX.md` 增加新文档索引条目。

## Impact Analysis
- 形成稳定的 UI 交互测试规范，后续测试可按文档执行。
- 不改动业务逻辑，仅文档与索引更新。

## Risks / Blockers
- 模板与运行态差异：动态渲染/条件显示可能导致实际交互数量不同。
- 依赖数据不足时，部分交互需要标注“需数据支撑”。

## Decisions
- 新建文档而不改写历史审计报告（`UI_INTERACTION_AUDIT.md` 作为历史版本保留）。

## Verification / Acceptance (Definition of Done)
- 新文档包含 4 个页面的交互分类、功能描述、操作步骤与预期效果。
- 每个页面至少包含：导航、筛选/搜索、主要操作按钮、列表/详情交互。
- 文档索引新增条目可检索到新文档。

## Next Steps
- 如需把 events 页纳入测试或恢复为可选项，再单独补充附录。

## /do Update (2026-02-26)
- 新增 `scripts/rdc_analyzer/docs/UI_INTERACTION_TEST_MATRIX.md`。
- 更新 `scripts/rdc_analyzer/docs/INDEX.md` 索引条目。
- 运行 `py -3 scripts/_tmp_ui_interaction_inventory.py` 获取静态控件基线。

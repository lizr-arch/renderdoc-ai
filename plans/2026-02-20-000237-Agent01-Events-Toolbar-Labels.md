## Plan Metadata
- Version: 1.0
- Owner: Agent01 (Codex)
- Last Updated: 2026-02-20
- Plan File: plans/2026-02-20-000237-Agent01-Events-Toolbar-Labels.md

## Goal
- 让事件页工具栏按钮语义清晰：用直观文案替代 “A / DBG”，新手能理解功能含义。

## Architecture
- 只改事件页 `events.html` 的按钮文本与 tooltip，不改按钮行为与逻辑。
- 保持现有 JS 绑定与样式，必要时仅小幅调整提示文案。

## Tech Stack
- HTML/CSS/JavaScript（模板文件：`scripts/rdc_analyzer/templates/events.html`）

## Success Criteria (measurable)
- 事件页工具栏不再出现 “A / DBG” 纯缩写按钮文本。
- hover 提示明确表达功能（忽略 Alpha / 显示调试信息）。

## Acceptance Criteria
- 首次使用者可从按钮文本/提示理解功能，不需额外解释。
- 按钮交互保持原样（toggle 与 debug 折叠逻辑不变）。

## Verification Commands
- `py -3 scripts/rdc_analyzer/one_click_bundle_report.py "D:\backup\EndfieldTBeta2_2025.12.18_14.36_frame42231.rdc" -o "D:\backup\endfield_report" --force-texture-export --texture-max-size 512`
  - Expected: 生成 `D:\backup\endfield_report\events.html`

## Evidence
- 视觉验证：`file:///D:/backup/endfield_report/events.html`

## Estimation
- Effort: 10–20 分钟
- Story Points: 1
- Original Estimate: 0.5 天以内

## Risk Register
| Risk | Impact | Likelihood | Mitigation |
|---|---|---|---|
| 按钮文本变长导致工具栏拥挤 | Low | Low | 若拥挤，缩短文案或减小 padding |

## Game Dev: Memory & Resource Budget (Leak Checks)
- 不涉及运行时资源分配变化；无需额外泄漏检查。

## Game Dev: Asset Pipeline
- 不改资源导出/加载链路，仅改 HTML 文案。

## Game Dev: Crash Repro + Dumps/Symbols
- Repro steps: 打开 events.html 观察按钮文案
- Dump/Core: 不适用
- Symbols: 不适用
- Build identity: 当前工作区 commit

## Scope / Assumptions
- Scope: 事件页工具栏按钮文案与提示（A / DBG）。
- Out: 纹理/Shader 页面、渲染逻辑、数据格式。
- 假设：事件页工具栏可容纳更长按钮文本（若不行则缩短文案）。

## Repo / File List (含行号)
- `scripts/rdc_analyzer/templates/events.html:1641`（ignoreAlpha 按钮文本与 title）
- `scripts/rdc_analyzer/templates/events.html:1642`（debugToggle 按钮文本与 title）
- `scripts/rdc_analyzer/templates/events.html:3233`（ignoreAlpha 按钮绑定，确认逻辑不改）
- `scripts/rdc_analyzer/templates/events.html:3253`（debugToggle 按钮绑定，确认逻辑不改）

## Approach (Pseudo-code / 关键实现片段)
1) **替换按钮文案与 tooltip**
```
<button id="ignoreAlphaBtn" title="忽略 Alpha 通道（便于观察颜色）">忽略透明度</button>
<button id="debugToggleBtn" title="显示/隐藏调试信息">调试信息</button>
```
2) **保持 JS 绑定不变**
```
document.getElementById('ignoreAlphaBtn') // 仅验证存在
document.getElementById('debugToggleBtn') // 仅验证存在
```

## Impact Analysis
- 体验：新手可理解按钮用途，减少误操作。
- 风险：按钮变长可能影响布局（低风险）。

## Task Checklist (2-5 分钟粒度)
- [x] 更新 events.html 的 ignoreAlpha 按钮文本与 title（写入明确文案）
- [x] 更新 events.html 的 debugToggle 按钮文本与 title（写入明确文案）
- [x] 生成报告并打开 events.html 进行人工验收
- [x] 记录结果并提交（Conventional Commits）

## Verification / DoD
- events.html 中不再显示 “A / DBG”
- hover 提示清楚（忽略 Alpha / 调试信息）
- 按钮 toggle 行为不变

## Next Steps
- 你确认 /do 后开始实现

---
title: Ignore Alpha Onload Fix (Events UI)
date: 2026-02-18 23:54:21
agent: Agent01
stage: /plan
---

# Ignore Alpha Onload Fix Implementation Plan

> **For Codex:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Version:** 2026-02-18
**Owner:** Agent01
**Last Updated:** 2026-02-18

## Plan Metadata
- Version: 2026-02-18
- Owner: Agent01
- Last Updated: 2026-02-18
- Plan File: D:/Code/git/renderdoc/plans/2026-02-18-235421-Agent01-Ignore-Alpha-Onload-Fix.md

## Goal
- 修复“忽略 Alpha”切换时不生效的问题：当 image 已缓存/不触发 onload 时，也能立即应用 ignoreAlpha 视图。

## Architecture
- 在 toggle 事件中检测 `outputImg.complete`，直接调用 `applyIgnoreAlphaView(img)`。
- 在 `updateOutputPreview` 设置 `img.src` 后，如果 `img.complete` 为 true，立即调用 `applyIgnoreAlphaView(img)`，不依赖 onload 事件。
- 在 `displayRTSnapshot` 中同样适配上述逻辑，确保从服务加载的快照也可立即忽略 Alpha。

## Tech Stack
- HTML/CSS/Vanilla JS（events.html 模板内联）
- Canvas 2D API

## Success Criteria (measurable)
- EID 3461 的 Color2：点击 “A” 后立即显示 RGB 内容（无需重新选择事件）。
- ignoreAlpha 关闭后立即恢复原始透明显示。

## Acceptance Criteria
- 切换按钮后不依赖 img.onload 触发，能即时显示/隐藏 ignoreAlpha 视图。
- 不影响 Color0/1/3/4 的显示与缩放/翻转。

## Verification Commands
- `py -3 scripts/rdc_analyzer/one_click_bundle_report.py "D:\backup\EndfieldTBeta2_2025.12.18_14.36_frame42231.rdc" -o "D:\backup\endfield_report"` (Expected: “Bundle Report Generated Successfully!”)

## Evidence
- `file:///D:/backup/endfield_report/events.html` (EID 3461, Color2 开关即时生效)

## Estimation
- Effort: 0.25–0.5 day
- Story Points: 1
- Original Estimate: 0.25 day

## Risk Register
| Risk | Impact | Likelihood | Mitigation |
|---|---|---|---|
| img.complete 状态与渲染不同步 | 中 | 低 | 先调用 applyIgnoreAlphaView，再保留 onload fallback |
| Canvas 处理导致卡顿 | 低 | 低 | 仅在 toggle/加载时处理 |

## Game Dev: Memory & Resource Budget (Leak Checks)
- Canvas 操作仅在切换/加载时触发，不缓存大图。
- 验证：多次切换 ignoreAlpha，不出现明显内存增长。

## Game Dev: Asset Pipeline
- 不改变缩略图导出链路，仅前端显示逻辑改变。

## Game Dev: Crash Repro + Dumps/Symbols
- Repro steps: 打开 events.html → 选 EID 3461 → 反复点击 A → 观察显示与切换即时性
- Dump/Core: (minidump | core dump) N/A
- Symbols: (PDB | dSYM | ELF | DWARF) N/A
- Build identity: git commit hash

## Repo / File List (with line numbers)
- Modify: `scripts/rdc_analyzer/templates/events.html:2593` (updateOutputPreview 入口)
- Modify: `scripts/rdc_analyzer/templates/events.html:3049` (ignoreAlphaBtn click handler)
- Modify: `scripts/rdc_analyzer/templates/events.html:3494` (displayRTSnapshot)

## Approach (Pseudo-code)
```js
ignoreAlphaBtn.onclick = () => {
  outputIgnoreAlpha = !outputIgnoreAlpha;
  ignoreAlphaBtn.classList.toggle('active', outputIgnoreAlpha);
  if (currentEvent) {
    const img = document.getElementById('outputImg');
    if (img && img.complete) {
      applyIgnoreAlphaView(img);   // 直接应用
    } else {
      updateOutputPreview(currentEvent, currentOutputKey);
    }
  }
}

function updateOutputPreview(...) {
  img.onload = () => { analyzeOutputAlpha(img); applyIgnoreAlphaView(img); }
  img.src = ...
  if (img.complete) { applyIgnoreAlphaView(img); }
}

function displayRTSnapshot(...) {
  img.onload = () => { analyzeOutputAlpha(img); applyIgnoreAlphaView(img); }
  img.src = base64
  if (img.complete) { applyIgnoreAlphaView(img); }
}
```

## Impact Analysis
- 正面：ignoreAlpha 点击后即时生效，避免“看不到”的误判。
- 风险：无新增后端依赖，仅前端逻辑调整。

## Action Items (2–5 分钟粒度)
- [x] 在 ignoreAlpha 点击处理里加入 `img.complete` 即时应用逻辑
- [x] 在 updateOutputPreview 设置 src 后加入 `img.complete` 快速路径
- [x] 在 displayRTSnapshot 设置 src 后加入 `img.complete` 快速路径
- [x] 运行 one_click_bundle_report 生成报告
- [ ] 视觉验证 EID 3461 Color2（点击 A 即时生效）
- [x] Git commit（Conventional Commits）

## Verification / DoD
- Color2 在 click A 后无需重选事件即可显示
- ignoreAlpha 关闭后恢复透明显示
- 无控制台错误

## Open Questions
- ignoreAlpha 模式是否需要在 AlphaHint 中追加“即时应用模式”的提示？

## Next Steps
- 等用户批准进入 /do。

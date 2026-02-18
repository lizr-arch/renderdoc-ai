---
title: Ignore Alpha Output Preview (Events UI)
date: 2026-02-18 23:23:45
agent: Agent01
stage: /plan
---

# Ignore Alpha Output Preview Implementation Plan

> **For Codex:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Version:** 2026-02-18
**Owner:** Agent01
**Last Updated:** 2026-02-18

## Plan Metadata
- Version: 2026-02-18
- Owner: Agent01
- Last Updated: 2026-02-18
- Plan File: D:/Code/git/renderdoc/plans/2026-02-18-232345-Agent01-Ignore-Alpha-Output-Preview.md

## Goal
- 在事件页输出预览中新增“忽略 Alpha”开关：开启后将渲染图像的 Alpha 强制为 1，以便在 Alpha=0 时仍可肉眼检查 RGB 内容。

## Architecture
- 现有预览使用 `<img id=outputImg>`；新增一个 `<canvas id=outputCanvas>` 用于“忽略 Alpha”模式渲染。
- 当 ignoreAlpha=true 且图片加载完成时，绘制到 canvas 并将 alpha 通道设为 255；同时隐藏 img，显示 canvas。
- 关闭 ignoreAlpha 时恢复 img 渲染，不改变原始缩略图数据。

## Tech Stack
- HTML/CSS/Vanilla JS（events.html 模板内联）
- Canvas 2D API（getImageData/putImageData）

## Success Criteria (measurable)
- EID 3461 的 Color2 在关闭开关时为空白，在开启“忽略 Alpha”后可看到可辨识 RGB 纹理。
- 其他 Color0/1/3/4 在开关切换时能稳定显示（无崩溃、无控制台错误）。

## Acceptance Criteria
- 事件页工具栏出现“忽略 Alpha”按钮，状态可切换且视觉反馈清晰。
- 切换按钮时，输出预览即时切换（不刷新页面）。
- Alpha 提示条显示“当前为忽略 Alpha 视图”或等效提示。

## Verification Commands
- `py -3 scripts/rdc_analyzer/one_click_bundle_report.py "D:\backup\EndfieldTBeta2_2025.12.18_14.36_frame42231.rdc" -o "D:\backup\endfield_report"` (Expected: “Bundle Report Generated Successfully!”)

## Evidence
- `file:///D:/backup/endfield_report/events.html` (EID 3461, Color2 关闭/开启对比截图)

## Estimation
- Effort: 0.5–1.0 day
- Story Points: 1
- Original Estimate: 0.5 day

## Risk Register
| Risk | Impact | Likelihood | Mitigation |
|---|---|---|---|
| Canvas 读取失败（权限/安全） | 中 | 低 | 失败时提示并回退到 img 视图 |
| 性能开销（大图） | 低 | 低 | 仅在 toggle 开启且图片加载时处理 |
| UI 状态不一致 | 中 | 低 | 统一入口：updateOutputPreview 里处理 |

## Game Dev: Memory & Resource Budget (Leak Checks)
- Canvas 操作仅在用户切换时触发；不持久缓存大图像数据。
- 验证：在同一事件多次切换，观察内存无明显增长。

## Game Dev: Asset Pipeline
- 缩略图来源不变（renderTargets 缩略图/RT snapshot）；仅改变浏览器端显示方式。

## Game Dev: Crash Repro + Dumps/Symbols
- Repro steps: 打开 events.html → 选择 EID 3461 → 切换“忽略 Alpha” → 观察输出。
- Dump/Core: (minidump | core dump) N/A
- Symbols: (PDB | dSYM | ELF | DWARF) N/A
- Build identity: git commit hash

## Repo / File List (with line numbers)
- Modify: `scripts/rdc_analyzer/templates/events.html:1569` (toolbar 区域新增 toggle 按钮)
- Modify: `scripts/rdc_analyzer/templates/events.html:1603` (输出预览区域新增 canvas)
- Modify: `scripts/rdc_analyzer/templates/events.html:2533` (updateOutputPreview 加入 ignoreAlpha 渲染逻辑)
- Modify: `scripts/rdc_analyzer/templates/events.html:2958` (applyZoom 与 canvas 同步缩放/翻转)

## Approach (Pseudo-code)
```js
let outputIgnoreAlpha = false;

function renderOutputIgnoreAlpha(img) {
  const canvas = outputCanvas;
  const ctx = canvas.getContext('2d');
  canvas.width = img.naturalWidth;
  canvas.height = img.naturalHeight;
  ctx.drawImage(img, 0, 0);
  const data = ctx.getImageData(0, 0, canvas.width, canvas.height);
  for (i=3; i<data.data.length; i+=4) data.data[i] = 255;
  ctx.putImageData(data, 0, 0);
}

function updateOutputPreview(...) {
  // 现有 img.src 设置
  img.onload = () => {
     analyzeOutputAlpha(img);
     if (outputIgnoreAlpha) { renderOutputIgnoreAlpha(img); showCanvasHideImg(); }
     else { showImgHideCanvas(); }
  }
}

ignoreAlphaBtn.onclick = () => {
  outputIgnoreAlpha = !outputIgnoreAlpha;
  if (currentEvent) updateOutputPreview(currentEvent, currentOutputKey);
}
```

## Impact Analysis
- 正面：可视化验证 Alpha=0 的纹理内容，减少“看不见就是错”的误判。
- 风险：Canvas 处理可能稍慢；但仅在切换/加载时触发，影响可接受。
- 兼容：仅前端模板改动，不影响数据导出。

## Action Items (2–5 分钟粒度)
- [x] 在 events.html 工具栏添加“忽略 Alpha”按钮与激活态样式
- [x] 在输出预览区域加入 `<canvas id="outputCanvas">` 并默认隐藏
- [x] 在 updateOutputPreview 的 img.onload 中实现 ignoreAlpha 渲染逻辑
- [x] 在 applyZoom 中同步 canvas 的缩放与翻转
- [x] 增加提示文案（例如：outputAlphaHint 显示“忽略 Alpha 视图”）
- [x] 运行 one_click_bundle_report 生成报告
- [ ] 视觉验证 EID 3461 Color2（关闭/开启对比）
- [x] Git commit（Conventional Commits）

## Verification / DoD
- events.html 中 Color2 在 ignoreAlpha=on 可见
- toggle 不影响 Color0/1/3/4 的显示
- 无控制台错误

## Open Questions
- ignoreAlpha 模式下是否需要禁用 Alpha 覆盖率提示，或显示“忽略 Alpha 视图”？

## Next Steps
- 等用户批准进入 /do。

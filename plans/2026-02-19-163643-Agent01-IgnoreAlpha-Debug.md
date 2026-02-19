## Scope / Assumptions
- Scope: 诊断并修复 events.html 中 “A(忽略 Alpha)” 仍看不到 Color2 的问题，只针对事件页输出预览链路。
- In: `outputImg/outputCanvas` 渲染、ignore-alpha 逻辑、必要的 UI/调试信息。
- Out: 其它页面（textures/shaders）与后端导出逻辑不改。
- 假设（待验证）: PNG 实际内容正确但 alpha 全 0；问题在浏览器端渲染/显示链路。

## Build / Test / Lint Quick Guide (记录命令，不自动执行)
- 生成报告（如需）：`py -3 scripts/rdc_analyzer/one_click_bundle_report.py "D:\backup\EndfieldTBeta2_2025.12.18_14.36_frame42231.rdc" -o D:\backup\endfield_report`
- 视觉验证：打开 `D:\backup\endfield_report\events.html`，EID 3461 → Color2 → 点击 A

## Repo / File List (含行号范围)
- `scripts/rdc_analyzer/templates/events.html:946-1165`（输出预览区 CSS，含 `.output-preview-container` / `.preview-canvas`）
- `scripts/rdc_analyzer/templates/events.html:1588-1616`（输出预览 HTML，`outputImg`/`outputCanvas`）
- `scripts/rdc_analyzer/templates/events.html:2536-2695`（ignore-alpha 相关函数）
- `scripts/rdc_analyzer/templates/events.html:3061-3071`（忽略 Alpha 按钮事件）
- `scripts/rdc_analyzer/templates/events.html:3511-3528`（`displayRTSnapshot`）
- `scripts/rdc_analyzer/templates/common.css:1294-1332`（`canvas-viewport` / `preview-img`，必要时微调）

## Approach (Pseudo-code / 关键实现片段)
目标：先拿到**根因证据**，再改逻辑。为避免依赖 DevTools，加入轻量 Debug 视图（默认隐藏）。

伪代码（拟加入 events.html）：
```
// 1) 轻量 Debug 面板（默认隐藏，仅在 ignore-alpha 激活时显示）
function updateIgnoreAlphaDebug(img, canvas, errorMsg) {
  const el = document.getElementById('outputDebug');
  if (!el) return;
  const state = {
    ignore: outputIgnoreAlpha,
    imgComplete: !!(img && img.complete),
    imgSize: img ? `${img.naturalWidth}x${img.naturalHeight}` : '-',
    canvasSize: canvas ? `${canvas.width}x${canvas.height}` : '-',
    imgHidden: img ? img.classList.contains('hidden') : '-',
    canvasHidden: canvas ? canvas.classList.contains('hidden') : '-',
    error: errorMsg || ''
  };
  el.textContent = JSON.stringify(state, null, 2);
  el.classList.toggle('hidden', !outputIgnoreAlpha);
}

// 2) renderOutputIgnoreAlpha 增加 try/catch，捕获 tainted canvas / 其它异常
function renderOutputIgnoreAlpha(img) {
  const canvas = getOutputCanvas();
  if (!canvas || !img) return false;
  const ctx = canvas.getContext('2d');
  if (!ctx) return false;
  const width = img.naturalWidth || img.width;
  const height = img.naturalHeight || img.height;
  if (!width || !height) return false;
  canvas.width = width;
  canvas.height = height;
  try {
    ctx.drawImage(img, 0, 0, width, height);
    const imageData = ctx.getImageData(0, 0, width, height);
    const data = imageData.data;
    for (let i = 3; i < data.length; i += 4) data[i] = 255;
    ctx.putImageData(imageData, 0, 0);
    updateIgnoreAlphaDebug(img, canvas, '');
    return true;
  } catch (e) {
    updateIgnoreAlphaDebug(img, canvas, e.message || String(e));
    return false;
  }
}
```

补充：当前 `applyIgnoreAlphaView` 失败分支会覆盖真实错误，需改为“仅在无真实 error 时再给默认提示”，以暴露根因。

## Impact Analysis
- 正面：明确是否为 `getImageData`/跨域/尺寸为 0/hidden 造成的失败。
- 负面：Debug UI 可能影响页面美观 → 默认隐藏，仅在 ignore-alpha 时显示。
- 风险：若根因在 CSS stacking 或 zoom transform，可能需要进一步调整 `applyZoom` 或 canvas 样式（需证据）。

## Task Checklist (2-5 分钟粒度)
- [x] 记录现状证据：确认 Color2 缩略图文件存在且内容非空（已在本地打开过）
- [x] 在 `events.html` 中加入 `outputDebug` 面板与 CSS（默认隐藏）
- [x] 在 `renderOutputIgnoreAlpha` 中加入 try/catch 与 debug 更新
- [x] 在 `applyIgnoreAlphaView`/`updateOutputPreview` 中调用 debug 更新
- [x] 保留真实错误信息（避免被 `render ignore-alpha failed` 覆盖）
- [x] debug 追加输出 `img.currentSrc` + `naturalWidth/Height`
- [ ] 生成报告并用 EID 3461 → Color2 → A 复现，读取 debug 状态
- [ ] 根据真实 error 锁定根因，提出最小修复方案
- [ ] 更新本 plan 的 Risks/Decisions，并在 /do 完成后提交

## TDD 步骤（轻量）
- [ ] 失败用例：打开 `events.html` → EID 3461 → Color2 → 点击 A，仍不可见
- [ ] 验证失败：debug 显示 canvas/size/error 信息
- [ ] 最小修复：只改导致失败的那一处
- [ ] 验证通过：A 后可见 Color2（或明确报错并给出可接受替代）

## Risks / Blockers
- 如果 `getImageData` 抛出 tainted canvas 错误，需确认 file:// 环境限制（可能需要引导使用本地 http 服务）。
- 若 `applyZoom` 仅作用于 `preview-img`，可能需要扩展到 `preview-canvas`（需证据）。

## Decisions
- 使用页面内 Debug 面板替代 DevTools，以符合“无需手动环节”的偏好。
- 先证据后修复；不进行无依据的 CSS/JS 盲改。
- 为避免手动生成报告，已同步修改 `D:\backup\endfield_report\events.html` 便于直接验证。

## Verification / DoD
- A 开启后，Color2 缩略图可见（非纯透明）。
- Debug 面板显示：`imgSize` 与 `canvasSize` 非 0，且无 error。
- 不影响 Color0/Color1 的正常显示与缩放。

## Next Steps
- 等你确认 /do 后按计划执行并更新本文件勾选状态。

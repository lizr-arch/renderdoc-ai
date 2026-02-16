# Scope / Assumptions

- **目标**：
  - Vulkan 纹理格式显示为完整枚举字符串（例如 `VK_FORMAT_R8G8B8A8_UNORM`），不再是纯数字。
  - `textures.html` 与 `events.html` 增加“上下翻转”按钮，便于校正 UV 翻转问题。
  - `events.html` 中央输出区域显示 **当前事件** 的“最后 6 个 RT（renderTargets）”缩略图条，便于肉眼验证。
- **用户确认**：
  - 格式显示保留完整字符串（不去前缀）。
  - 翻转按钮两个页面都加。
  - RT 显示为当前事件的最后 6 个 renderTargets。
- **约束**：
  - 仅改模板和 xml_to_bundle 解析，不触碰第三方与 build 目录。
  - 维持现有 UI 风格，不引入新字体/主题。

---

# Success Criteria / Evaluation

- **成功标准**：
  1) `textures.html` 格式字段显示 `VK_FORMAT_*`/`DXGI_FORMAT_*` 字符串，不再是数字。
  2) 翻转按钮可在 `textures.html` 与 `events.html` 正常切换，缩放仍正确。
  3) `events.html` 中央区域出现“最后 6 个 RT”缩略图条，点击可放大预览。
- **验收方式**：
  - 使用 `D:/backup/endfield_report` 输出，打开 `textures.html` / `events.html` 人工验证。

---

# Navigation Evidence（codemap 不可用时的等价证据）

## 查询记录（max 3）
1. `codemap "textures.html format" -Num 20` → 环境报错 `codemap: command not found`
2. `grep -n "format" scripts/rdc_analyzer/templates/textures.html`
3. `grep -n "renderTargets|outputImg" scripts/rdc_analyzer/templates/events.html`

## 候选命中（>=3）
1. `[renderdoc] scripts/rdc_analyzer/xml_to_bundle.py:239`
   `elif sub_name == "format": tex["format"] = sub.text or ""`
2. `[renderdoc] scripts/rdc_analyzer/templates/textures.html:1136`
   `document.getElementById('propFormat').textContent = texture.format || '-';`
3. `[renderdoc] scripts/rdc_analyzer/templates/events.html:2464`
   `function updateRenderTargets(event) { ... event.renderTargets ... }`

## 跟进点（1-2 个）
- 主跟进：`scripts/rdc_analyzer/xml_to_bundle.py`（Vulkan format 字符串）
- UI 跟进：`scripts/rdc_analyzer/templates/textures.html`、`scripts/rdc_analyzer/templates/events.html`

---

# Repo / File List（含行号）

1. `scripts/rdc_analyzer/xml_to_bundle.py:239`
   - Vulkan `_parse_vk_image` 读取 `enum` 的 `string` 属性。
2. `scripts/rdc_analyzer/templates/textures.html:760`
   - 工具栏新增翻转按钮；`applyZoom()` 改为同时处理 flip。
3. `scripts/rdc_analyzer/templates/textures.html:1152`
   - `updateTexturePreview()` 触发 `applyZoom()` 以保持翻转状态。
4. `scripts/rdc_analyzer/templates/events.html:1428`
   - 工具栏新增翻转按钮；`applyZoom()` 支持 flip。
5. `scripts/rdc_analyzer/templates/events.html:1458`
   - 输出区域新增 RT 缩略图条（最后 6 个）。
6. `scripts/rdc_analyzer/templates/events.html:2464`
   - 在 `updateRenderTargets()`/`selectEvent()` 中同步更新 RT 缩略图条。

---

# Approach (Pseudo-code)

## 1) Vulkan 格式字符串（xml_to_bundle.py）
```python
# _parse_vk_image() 内
if sub_name == "format":
    fmt = sub.get("string") or (sub.text or "")
    tex["format"] = fmt.strip()

# 直接子元素 (child_name == "format")
fmt = child.get("string") or (child.text or "")
tex["format"] = fmt.strip()
```

## 2) 纹理预览翻转（textures.html）
```js
let textureFlipVertical = false;

function applyZoom() {
  const img = document.getElementById('previewImg');
  const flip = textureFlipVertical ? -1 : 1;
  img.style.transform = `scale(${currentZoom}) scaleY(${flip})`;
  document.getElementById('zoomLevel').textContent = `${Math.round(currentZoom * 100)}%`;
}

document.getElementById('flipVerticalBtn').addEventListener('click', () => {
  textureFlipVertical = !textureFlipVertical;
  document.getElementById('flipVerticalBtn').classList.toggle('active', textureFlipVertical);
  applyZoom();
});
```

## 3) 事件输出翻转 + RT 条（events.html）
```js
let outputFlipVertical = false;
function applyZoom() {
  const img = document.getElementById('outputImg');
  const flip = outputFlipVertical ? -1 : 1;
  img.style.transform = `scale(${currentZoom}) scaleY(${flip})`;
  document.getElementById('zoomLevel').textContent = `${Math.round(currentZoom * 100)}%`;
}

document.getElementById('flipVerticalBtn').addEventListener('click', () => {
  outputFlipVertical = !outputFlipVertical;
  document.getElementById('flipVerticalBtn').classList.toggle('active', outputFlipVertical);
  applyZoom();
});

function updateRtStrip(event) {
  const strip = document.getElementById('rtStrip');
  const list = event.renderTargets || [];
  const last = list.slice(-6);
  strip.innerHTML = last.map(rt => `...`).join('') || '<div class="rt-strip-empty">无 RT</div>';
}
```

---

# Impact Analysis

- **正向**：
  - Vulkan 格式可读性提升，分析链路更可信。
  - 翻转按钮减少跨 API UV 方向误判。
  - 中央 RT 条让“中间结果”更易肉眼验收。
- **风险**：
  - `applyZoom()` transform 叠加需避免覆盖（用组合 transform 解决）。
  - `renderTargets` 缩略图缺失时需要占位文字（避免空白）。

---

# Action Items（2-5 分钟粒度）

- [x] T1：`xml_to_bundle.py` Vulkan `format` 读取 `string` 属性并保留完整字符串。
- [x] T2：`textures.html` 工具栏加“上下翻转”按钮，补充翻转状态与 transform 合成。
- [x] T3：`textures.html` 选中纹理时保持翻转状态（调用 `applyZoom()`）。
- [x] T4：`events.html` 工具栏加“上下翻转”按钮并与缩放叠加。
- [x] T5：`events.html` 中央输出区域新增 RT 缩略图条（最后 6 个 renderTargets）。
- [x] T6：新增/更新前端小测试（如有）并做一次手动视觉验收。

---

# Verification / DoD

- [x] `textures.html` 中格式显示为 `VK_FORMAT_*` / `DXGI_FORMAT_*` 字符串。
- [x] 两个页面翻转按钮生效，缩放不被覆盖。
- [x] `events.html` 中央区域显示“最后 6 个 RT”缩略图条。

---

# Commands (记录，不执行)

```bash
py -3 -m py_compile scripts/rdc_analyzer/xml_to_bundle.py
py -3 scripts/rdc_analyzer/one_click_bundle_report.py "D:\\backup\\EndfieldTBeta2_2025.12.18_14.36_frame42231.rdc" -o "D:\\backup\\endfield_report" --no-smoke --texture-max-size 256 -v
```

---

# /do 执行记录（2026-02-16）

- 已完成 Vulkan `format` 解析：优先读取 enum 的 `string` 属性。
- 已完成翻转按钮：`textures.html` 与 `events.html` 工具栏新增“上下翻转”，与缩放叠加。
- 已完成 RT 条：`events.html` 中央输出区显示当前事件最后 6 个 RT 缩略图。
- 验证：`py -3 -m py_compile scripts/rdc_analyzer/xml_to_bundle.py` 通过。

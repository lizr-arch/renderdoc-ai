# Scope / Assumptions

- **目标**：
  - 输出区 **Color tabs 动态化**：根据 `renderTargets` 数量生成 `Color0..ColorN`。
  - **Depth / Stencil 仍保留两个 tab**，但能显示是否具备 Stencil（并写入对应信息）。
  - 明确 **renderTargets ↔ ColorN** 映射：`renderTargets[N] -> ColorN`。
  - “从 RDC 加载快照”按钮意义明确：离线时禁用/提示在线方式。
- **用户确认**：
  - Color tabs 可动态拆分多个。
  - Depth/Stencil 保留两个 tab，但要写入信息（可视提示/元数据）。
- **约束**：
  - 不引入新后端；仅前端模板 + 必要数据字段。
  - 维持现有 UI 风格。

---

# Success Criteria / Evaluation

- **成功标准**：
  1) `events.html` 输出区 Color tabs 与当前事件 `renderTargets` 数量一致（N≥2时显示 Color0..ColorN）。
  2) Depth/Stencil tabs 均存在，并显示是否有 Stencil（例如“Depth (Depth/Stencil)”）。
  3) 无快照时 ColorN 自动使用 `renderTargets[N]` 缩略图；并显示“资源缩略图（非事件快照）”提示。
  4) RT 服务离线时，按钮明确提示并禁用（避免用户点击失败）。
- **验收方式**：
  - 使用 `D:/backup/endfield_report/events.html` 选择有多个 RT 的事件进行验证。

---

# Navigation Evidence（codemap 不可用时的等价证据）

## 查询记录（max 3）
1. `codemap "events.html output color0 renderTargets" -Num 20` → 环境报错 `codemap: command not found`
2. `grep -n "output-tabs|selectOutput|updateOutputPreview" scripts/rdc_analyzer/templates/events.html`
3. `grep -n "depthTarget|renderTargets" scripts/rdc_analyzer/xml_to_bundle.py`

## 候选命中（>=3）
1. `[renderdoc] scripts/rdc_analyzer/templates/events.html:1512`
   `output-tabs` 静态 Color0/Color1/Depth/Stencil
2. `[renderdoc] scripts/rdc_analyzer/templates/events.html:2389`
   `updateOutputPreview()` 输出预览入口
3. `[renderdoc] scripts/rdc_analyzer/templates/events.html:2700`
   `selectOutput()` 切换输出 tab
4. `[renderdoc] scripts/rdc_analyzer/xml_to_bundle.py:96`
   `dc["depth_target"] = active_rt_state["depth"]`（当前仅 id，无 aspect）

## 跟进点（1-2 个）
- `scripts/rdc_analyzer/templates/events.html`（动态 tabs + fallback + 按钮状态）
- `scripts/rdc_analyzer/xml_to_bundle.py`（depthTarget aspect 信息写入）

---

# Repo / File List（含行号）

1. `scripts/rdc_analyzer/templates/events.html:1512`
   - 替换静态输出 tabs 为动态容器（JS 填充）。
2. `scripts/rdc_analyzer/templates/events.html:2389`
   - `updateOutputPreview()`：使用 `renderTargets[N]` 作为 ColorN fallback。
3. `scripts/rdc_analyzer/templates/events.html:2700`
   - `selectOutput()`：适配动态 tabs 与 currentOutputKey。
4. `scripts/rdc_analyzer/templates/events.html:1005`
   - RT load 按钮：根据服务在线状态禁用/提示。
5. `scripts/rdc_analyzer/xml_to_bundle.py:295`
   - depthTarget 写入 `aspect`（Depth/Stencil 信息）。

---

# Approach (Pseudo-code)

```js
// 1) 动态 tabs
function buildOutputTabs(event) {
  const count = (event.renderTargets || []).length;
  const tabs = [];
  for (let i = 0; i < Math.max(1, count); i++) tabs.push(`color${i}`);
  tabs.push('depth', 'stencil');
  renderTabs(tabs);
}

// 2) fallback 逻辑（ColorN）
function getColorFallback(event, key) {
  if (!event?.renderTargets) return null;
  const idx = parseInt(key.replace('color',''), 10);
  return Number.isFinite(idx) ? event.renderTargets[idx] : null;
}

// 3) Depth/Stencil 显示信息
// depthTarget: { id, aspect }，aspect 包含 DEPTH/STENCIL
// UI label: Depth (Depth) / Depth (Depth/Stencil)
```

```python
# xml_to_bundle.py
# 当识别到 depth view 时：保存 depthTarget = {"id": image_id, "aspect": aspect}
# xml_to_bundle_events_dict: depthTarget 透传 aspect 字段
```

---

# Impact Analysis

- **正向**：
  - 多 RT 场景的 ColorN 可视化完整，避免 Color0/1 信息丢失。
  - Depth/Stencil 状态可读，降低误判。
  - RT 服务离线时 UI 体验更可控。
- **风险**：
  - 动态 tabs 需与已有 `selectOutput` 逻辑一致，避免空 tab。
  - depthTarget aspect 在 XML 中缺失时需回退为 “Depth”。

---

# Action Items（2-5 分钟粒度）

- [x] T1：`events.html` 输出 tabs 改为动态生成（基于 renderTargets 数量 + Depth/Stencil）。
- [x] T2：`selectOutput()` 与 `updateOutputPreview()` 适配 ColorN fallback。
- [x] T3：`xml_to_bundle.py` depthTarget 透传 `aspect` 信息。
- [x] T4：RT load 按钮离线禁用 + 提示文案。
- [x] T5：本地生成报告并人工验证。

---

# Verification / DoD

- [x] Color tabs 数量与 renderTargets 数一致（N≥2 时显示 Color0..ColorN）。
- [x] Depth/Stencil tabs 有清晰的“Depth / Depth+Stencil”信息。
- [x] 无快照时 ColorN 自动显示 renderTargets[N] 缩略图。
- [x] RT 服务离线时按钮不可用且提示明确。

---

# /do 执行记录（2026-02-16）

- 已完成动态 Color tabs：根据 renderTargets 数量生成 Color0..ColorN。
- 已完成 Depth/Stencil 标签：基于 depthTarget.aspect 标注 D/S。
- 已完成 ColorN fallback：无快照时使用 renderTargets[N] 缩略图。
- 已完成 RT 按钮离线禁用与提示文案。
- 已运行：`py -3 scripts/rdc_analyzer/one_click_bundle_report.py "D:\\backup\\EndfieldTBeta2_2025.12.18_14.36_frame42231.rdc" -o "D:\\backup\\endfield_report" --no-smoke --texture-max-size 256 -v`

---

# Commands (记录，不执行)

```bash
py -3 scripts/rdc_analyzer/one_click_bundle_report.py "D:\\backup\\EndfieldTBeta2_2025.12.18_14.36_frame42231.rdc" -o "D:\\backup\\endfield_report" --no-smoke --texture-max-size 256 -v
```

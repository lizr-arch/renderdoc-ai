# Scope / Assumptions

- **目标**：
  - 明确 `Color0/Color1` 与 `renderTargets` 的映射关系，并在事件输出区落地可视化规则。
  - 当 `event.output.*` 或 `rtSnapshot` 缺失时，**中间画布使用 renderTargets 作为 fallback** 显示。
  - 在画布内明确标识“资源缩略图（非事件快照）”，避免误解。
- **用户确认**：
  - 保持 `Color0/Color1` 语义为输出通道，但允许用 RT 资源缩略图做 fallback。
  - renderTargets 与 Color0/Color1 的关系按 Slot 对齐（0→Color0，1→Color1）。
- **约束**：
  - 不引入新后端服务或 GUI 手动步骤。
  - 仅调整前端模板与必要的事件数据关联逻辑。

---

# Success Criteria / Evaluation

- **成功标准**：
  1) `events.html` 中央画布在无快照时，Color0/Color1 能显示 `renderTargets[0/1]` 的缩略图。
  2) 画布明确显示“资源缩略图（非事件快照）”提示。
  3) 右侧 RT 列表与下方 RT 条保持不变。
- **验收方式**：
  - 使用 `D:/backup/endfield_report/events.html` 打开后，选择有 RT 的事件验证。

---

# Navigation Evidence（codemap 不可用时的等价证据）

## 查询记录（max 3）
1. `codemap "events.html output color0 renderTargets" -Num 20` → 环境报错 `codemap: command not found`
2. `grep -n "selectOutput|outputImg|rtSnapshot|renderTargets" scripts/rdc_analyzer/templates/events.html`
3. `grep -n "renderTargets" scripts/rdc_analyzer/templates/events.html`

## 候选命中（>=3）
1. `[renderdoc] scripts/rdc_analyzer/templates/events.html:2699`
   `if (currentEvent && currentEvent.output && currentEvent.output[output]) { ... }`
2. `[renderdoc] scripts/rdc_analyzer/templates/events.html:2487`
   `if (event.output && event.output.color0) { ... } else if (event.rtSnapshot) { ... } ...`
3. `[renderdoc] scripts/rdc_analyzer/templates/events.html:2601`
   `updateRtStrip(event)`（已用于显示当前事件 RT 条）

## 跟进点（1-2 个）
- `scripts/rdc_analyzer/templates/events.html`（输出区 fallback 逻辑）

---

# Repo / File List（含行号）

1. `scripts/rdc_analyzer/templates/events.html:1488`
   - 中央输出区域：新增“fallback 标签/提示”元素。
2. `scripts/rdc_analyzer/templates/events.html:2685`
   - `applyZoom()` / `selectOutput()`：加 fallback 选择逻辑。
3. `scripts/rdc_analyzer/templates/events.html:3118`
   - `displayRTSnapshot()`：保留现有快照优先级。

---

# Approach (Pseudo-code)

```js
function getFallbackOutput(event, outputKey) {
  if (!event || !event.renderTargets) return null;
  if (outputKey === 'color0') return event.renderTargets[0] || null;
  if (outputKey === 'color1') return event.renderTargets[1] || null;
  return null;
}

function selectOutput(outputKey) {
  // 1) 优先 event.output[outputKey]
  // 2) 其次 rtSnapshot (仅 color0)
  // 3) 再 fallback -> renderTargets[slot]
  // 4) 若 fallback 生效，显示“资源缩略图（非事件快照）”标签
}
```

---

# Impact Analysis

- **正向**：
  - 无需 RT 服务即可看到 Color0/Color1 的近似输出，便于肉眼验证。
  - 中间画布不再“空白”。
- **风险**：
  - renderTargets 缩略图 ≠ 真正输出快照（只是资源预览）。需明显标注。

---

# Action Items（2-5 分钟粒度）

- [x] T1：`events.html` 添加输出 fallback 标签（仅在 fallback 时显示）。
- [x] T2：`selectOutput()` 中加入 renderTargets fallback 逻辑（Color0/Color1）。
- [x] T3：确保 `applyZoom()` / flip 逻辑不被 fallback 覆盖。
- [x] T4：本地生成报告并人工验证。

---

# Verification / DoD

- [x] Color0/Color1 在无快照时自动显示 renderTargets[0/1] 缩略图。
- [x] 画布出现“资源缩略图（非事件快照）”提示。

---

# /do 执行记录（2026-02-16）

- 已完成输出 fallback 逻辑：Color0/Color1 在无快照时使用 renderTargets[0/1] 缩略图。
- 已完成输出区提示：显示“资源缩略图（非事件快照）”徽标。
- 已保持翻转与缩放叠加：fallback 预览同样应用 `applyZoom()`。
- 已运行：`py -3 scripts/rdc_analyzer/one_click_bundle_report.py "D:\\backup\\EndfieldTBeta2_2025.12.18_14.36_frame42231.rdc" -o "D:\\backup\\endfield_report" --no-smoke --texture-max-size 256 -v`

---

# Commands (记录，不执行)

```bash
py -3 scripts/rdc_analyzer/one_click_bundle_report.py "D:\\backup\\EndfieldTBeta2_2025.12.18_14.36_frame42231.rdc" -o "D:\\backup\\endfield_report" --no-smoke --texture-max-size 256 -v
```

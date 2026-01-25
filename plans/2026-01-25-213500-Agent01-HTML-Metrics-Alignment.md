## Scope
- In: 修复 HTML 中“事件总数 vs 列表数量”口径不一致、补充纹理内存统计口径（估算 vs 资源统计）并可追溯展示。
- Out: 不改动 RenderDoc 核心、不过度重构 HTML 生成器、不开新分析算法。

## Assumptions
- `eventPassData` 与 `performanceData` 均由 `generate_real_report.py` 生成并注入 HTML（单帧报告）。
- `usage_analysis.total_vram_bytes` 代表“资源统计口径”的纹理内存总量。
- 允许在 HTML 中新增 1–2 个统计项与 tooltip 文案。

## Build / Test / Lint Quick Guide (命令仅记录不执行)
- 生成 HTML（单帧，含纹理导出）:
  - `py -3 scripts/rdc_analyzer/generate_real_report.py <json_path> <output_html> --textures <texture_dir> --bindings <bindings_json>`
  - 预期输出: 控制台包含 `Total texture memory:`、`Generated ... suggestions`，并生成 `<output_html>`.
- 校验 HTML 中关键字段:
  - `rg -n "Events \\(reported\\)" <output_html>`
  - `rg -n "Events \\(listed\\)" <output_html>`
  - `rg -n "texture_memory_vram_mb" <output_html>`

## Repo / File List (精确到行号范围)
- `scripts/rdc_analyzer/generate_real_report.py:1408-1460`（texture 统计、`usage_analysis`、`total_mem_mb`）
- `scripts/rdc_analyzer/generate_real_report.py:1515-1565`（`performance_data.metrics` 组装）
- `scripts/rdc_analyzer/generate_real_report.py:740-780`（`event_data` 统计字段）
- `scripts/rdc_analyzer/generate_offline_report.py:6518-6545`（Event Browser 头部统计 DOM）
- `scripts/rdc_analyzer/generate_offline_report.py:9216-9240`（Event Browser 头部统计渲染）
- `scripts/rdc_analyzer/generate_offline_report.py:8716-8765`（Performance 面板 metrics 渲染）

## Approach (Pseudo-code)
1) **纹理内存口径**  
   - WHAT: 增加 `texture_memory_vram_mb`（资源统计口径），保留现有 `texture_memory`（估算口径）。
   - WHY: 解决“HTML 显示值 ≠ 资源统计值”的困惑，并让口径可追溯。
   - HOW: 在 `generate_real_report.py` 复用 `usage_analysis.total_vram_bytes` 计算 MB，并注入到 `performance_data.metrics`。

2) **事件数量口径**  
   - WHAT: 同时展示 `Events (reported)` 与 `Events (listed)`。
   - WHY: 当 `eventPassData.totalEvents` 与 `eventPassData.events.length` 不一致时，避免误解。
   - HOW: 在 HTML 头部新增一个统计 span，并在 JS 渲染时同时赋值。

3) **性能面板可追溯说明**  
   - WHAT: 在 `renderPerformancePanel()` 中为新增的纹理内存项提供 tooltip 说明。
   - WHY: 让读者知道数据来源与计算方式，形成“标准可追溯”闭环。
   - HOW: 为特定 key 加 label/desc 映射，并用 `title` 注入。

## Action Items (2–5 分钟粒度, 含完整代码片段)
- [x] **Step 1 — generate_real_report.py: 补齐资源统计口径**
  - WHAT: 统一 `total_mem_mb` 变量，写入 `performance_data.metrics.texture_memory_vram_mb`。
  - WHY: 直接暴露“资源统计口径”的数值。
  - HOW (完整片段，替换/插入在对应位置):
```python
    # 在 texture 处理段落前设置默认值
    total_mem_mb = 0.0

    # ... if rdc_textures: 分支中
        total_mem_mb = usage_analysis.get("total_vram_bytes", 0) / (1024 * 1024)
        print(f"  Total texture memory: {total_mem_mb:.2f} MB")
```
```python
        performance_data = {
            "overall_score": round(perf_report.overall_score, 1),
            "metrics": {
                "draw_calls": perf_report.total_draw_calls,
                "triangles": perf_report.total_triangles,
                "shader_changes": perf_report.total_shader_changes,
                "rt_changes": perf_report.total_rt_changes,
                "unique_textures": perf_report.unique_textures,
                "texture_memory": f"{perf_report.total_texture_memory_mb:.1f} MB",
                "texture_memory_vram_mb": f"{total_mem_mb:.1f} MB",
            },
            "metrics_meta": {
                "texture_memory": {
                    "label": "Texture Memory (Est)",
                    "desc": "Estimated from analyzer using texture formats; may differ from exported byte sizes."
                },
                "texture_memory_vram_mb": {
                    "label": "Texture Memory (Resources)",
                    "desc": "Sum of texture byteSize from export/JSON; resource统计口径。"
                }
            },
            "issues": [
                {
                    "rule_id": issue.rule_id,
                    "severity": issue.severity,
                    "title": issue.title,
                    "message": issue.message,
                    "suggestion": issue.suggestion,
                }
                for issue in perf_report.issues
            ],
            "recommendations": perf_report.recommendations,
        }
```

- [x] **Step 2 — generate_offline_report.py: Event 统计展示一致化**
  - WHAT: 增加 `Events (listed)` 显示项。
  - WHY: 让“统计口径差异”可视化。
  - HOW (完整片段，替换 Event Browser 头部):
```html
            <div class="frame-stats">
                <span>Events (reported): <span class="stat-value" id="eventTotalCount">0</span></span>
                <span>Events (listed): <span class="stat-value" id="eventListCount">0</span></span>
                <span>Draws: <span class="stat-value" id="eventDrawCount">0</span></span>
                <span>Dispatches: <span class="stat-value" id="eventDispatchCount">0</span></span>
                <span>Frame: <span class="stat-value" id="eventFrameDuration">0 ms</span></span>
            </div>
```
```javascript
            const listCount = (eventPassData.events && eventPassData.events.length) ? eventPassData.events.length : 0;
            const reportedTotal = (eventPassData.totalEvents !== undefined && eventPassData.totalEvents !== null)
                ? eventPassData.totalEvents : listCount;

            document.getElementById('eventTotalCount').textContent = reportedTotal;
            document.getElementById('eventListCount').textContent = listCount;
            document.getElementById('eventDrawCount').textContent = eventPassData.totalDraws || 0;
            document.getElementById('eventDispatchCount').textContent = eventPassData.totalDispatches || 0;
            document.getElementById('eventFrameDuration').textContent = (eventPassData.frameDuration || 0).toFixed(2) + ' ms';
```

- [x] **Step 3 — generate_offline_report.py: 性能指标说明（tooltip）**
  - WHAT: 为纹理内存指标增加来源说明（估算 vs 资源统计）。
  - WHY: 满足“标准可追溯 + WHAT/WHY/HOW 元数据闭环”要求。
  - HOW (完整片段，替换 metrics 渲染段落):
```javascript
            const metrics = performanceData.metrics || {};
            const metricsMeta = performanceData.metrics_meta || {
                "texture_memory": {
                    "label": "Texture Memory (Est)",
                    "desc": "Estimated from analyzer using texture formats; may differ from exported byte sizes."
                },
                "texture_memory_vram_mb": {
                    "label": "Texture Memory (Resources)",
                    "desc": "Sum of texture byteSize from export/JSON; resource统计口径。"
                }
            };
            const metricsHtml = Object.entries(metrics).map(([key, val]) => {
                const meta = metricsMeta[key] || {};
                const label = meta.label || key.replace(/_/g, ' ').toUpperCase();
                const titleAttr = meta.desc ? ` title="${meta.desc}"` : '';
                return `
                    <div class="performance-metric"${titleAttr}>
                        <div class="performance-metric-value">${val}</div>
                        <div class="performance-metric-label">${label}</div>
                    </div>
                `;
            }).join('');
```

## Impact Analysis
- 风险: 新增指标会改变 UI 排列顺序；需确认用户是否接受双口径展示。
- 兼容: 保留 `texture_memory` 字段避免旧逻辑断裂。
- 回滚: 仅局部模板/JS 变更，回滚成本低。

## Verification / Acceptance (DoD)
- HTML 头部显示 **Events (reported)** 与 **Events (listed)** 两项，数值可区分。
- 性能面板中同时出现 **Texture Memory (Est)** 与 **Texture Memory (Resources)**。
- HTML 中新增 tooltip 文案可通过鼠标悬停触发（描述来源）。

### Verification Results (2026-01-25)
- Command: `py -3 scripts/rdc_analyzer/generate_real_report.py scripts/rdc_analyzer/g145_data.json scripts/rdc_analyzer/test_output/g145_report.html --textures scripts/rdc_analyzer/test_output`
  - Output: 生成 HTML 成功（[OK] Report saved），并打印 `Total texture memory: 108.60 MB`。
- Command: `rg -n "Events \(reported\)|Events \(listed\)|Texture Memory \(Est\)|Texture Memory \(Resources\)" scripts/rdc_analyzer/test_output/g145_report.html`
  - Output: 命中 `Events (reported)` / `Events (listed)` 与 metrics_meta labels，证明 HTML 注入成功。

## Risks & Blockers
- 若 `eventPassData.events` 为空但 `totalEvents` 非空，需确认是否仍展示 listed=0。

## Decisions
- 保留旧字段 `texture_memory`，新增 `texture_memory_vram_mb` 而非替换。

## Next Steps
- 用户确认 UI 文案风格与口径命名。
- 进入 `/do` 执行改动并按 DoD 验证。

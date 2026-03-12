# RDC Analyzer 开发里程碑 (统一追踪)

> **版本**: 2.3.0 | **更新日期**: 2025-02-08  
> **创建日期**: 2025-01-24  
> **目的**: 统一追踪所有待办开发任务，避免会话遗忘  
> **使用方法**: 完成一个任务后，将 `[ ]` 改为 `[x]` 并提交

---

## 📚 源文档索引（必读，防止遗忘）

> **强制规则**: 每次开发前，必须先阅读相关源文档，确保上下文一致。

| 文档 | 路径 | 职责 |
|------|------|------|
| **证据链开发计划** | `docs/analysis/codex_rdc_analyzer/EVIDENCE_CHAIN_DEVELOPMENT_PLAN.md` | M1-M4 详细任务分解 |
| **证据链 UX 设计** | `docs/analysis/codex_rdc_analyzer/EVIDENCE_CHAIN_UX_DESIGN.md` | 数据模型定义、UI 交互规范 |
| **UI 交互审计** | `docs/analysis/codex_rdc_analyzer/UI_INTERACTION_AUDIT.md` | 77 个交互组件盘点、数据缺口 |
| **架构评估** | `docs/analysis/codex_rdc_analyzer/ARCHITECTURE_ASSESSMENT.md` | 技术方案决策、优先级 |
| **性能报告设计** | `docs/analysis/codex_rdc_analyzer/PERFORMANCE_REPORT_DESIGN.md` | GPU 计时、性能规则 |
| **任务追踪表** | `docs/analysis/codex_rdc_analyzer/TASK_TRACKER.md` | Phase 1-5 完成状态 |
| **路线图** | `docs/analysis/codex_rdc_analyzer/WORK_SUMMARY_ROADMAP.md` | P0/P1/P2 待办与决策 |
| **工具文档索引** | `scripts/rdc_analyzer/docs/INDEX.md` | 脚本使用指南 |

---

## 📊 总体进度

| 阶段 | 状态 | 进度 | 说明 |
|------|:----:|------|------|
| Phase 1-4 (A-first) | ✅ 已完成 | 11/11 | 后端分析闘环 |
| **M1: ResourceUsageIndex** | ✅ 已完成 | 10/10 | 资源反向索引 |
| **M2: EvidenceChain** | ✅ 已完成 | 12/12 | 证据链生成 |
| **M3: UI 跳转/高亮** | ✅ 已完成 | 13/13 | 跨页面证据链导航 |
| **M4: 高级可视化** | ✅ 已完成 | 6/6 | M4.1 热力图 + M4.2 Pass 分组 |
| Phase 5: B-mode 对比 | ✅ 完成 | 4/4 | 多帧统计 + CI 集成 |
| **Phase 6: P0 报告完善** | ✅ 完成 | 4/4 | Schema/缩略图/Shader/RT |
| **Phase 7: 端到端验证** | ✅ 完成 | 3/3 | E2E测试/文档/性能优化 |
| P0-NEW-3: Schema 规范 | ✅ 完成 | 1/1 | 已规范化 (2025-02-05) |

---

## ✅ M1: 数据基础层 (ResourceUsageIndex) — 已完成

> **状态**: ✅ 已完成 (2025-01-24)  
> **实现位置**: `core/types.py`, `core/resource_usage_builder.py`, `rdc_to_bundle_report.py`

### M1.1 数据结构定义

- [x] **M1.1.1** 在 `core/types.py` 新增 `UsageRecord` 数据类
- [x] **M1.1.2** 在 `core/types.py` 新增 `ResourceUsageIndex` 数据类

### M1.2 构建逻辑

- [x] **M1.2.1** 新建 `core/resource_usage_builder.py`
- [x] **M1.2.2** 实现 `ResourceUsageBuilder.build()` 方法
- [x] **M1.2.3** 实现纹理用途推断 `infer_texture_purpose()`

### M1.3 集成

- [x] **M1.3.1** 修改 `report_bundle_generator.py` 调用构建器
- [x] **M1.3.2** 更新 JSON Schema，纹理对象包含 `usedBy`

### M1.4 验证

- [x] **M1.4.1** 编写单元测试
- [x] **M1.4.2** 生成测试报告验证功能

### M1 验收标准 ✅
```
textures.html 选中纹理后，右侧面板显示 DrawCall 使用列表
```

---

## ✅ M2: 证据链生成 (EvidenceChain) — 已完成

> **状态**: ✅ 已完成 (2025-01-24)  
> **实现位置**: `core/types.py`, `core/evidence_chain_builder.py`, `analyzers/performance_analyzer.py`

### M2.1 数据结构定义

- [x] **M2.1.1** 在 `core/types.py` 新增 `EvidenceChain` 数据类 (Line 973)
- [x] **M2.1.2** 新增 `ContextEvidence` 数据类 (Line 931)
- [x] **M2.1.3** 新增 `Action` 数据类 (Line 886)

### M2.2 证据构建器

- [x] **M2.2.1** 新建 `core/evidence_chain_builder.py`
- [x] **M2.2.2** 实现 `_build_perf004()` (大纹理证据)
- [x] **M2.2.3** 实现 `_build_perf002()` (状态冗余证据)
- [x] **M2.2.4** 实现 `_build_perf001-007()` (所有 PERF 规则)

### M2.3 集成到分析器

- [x] **M2.3.1** `PerformanceIssue` 类已有 `evidence_chain` 字段 (Line 463)
- [x] **M2.3.2** `PerformanceAnalyzer._build_evidence_chains()` 集成 (Line 645)
- [x] **M2.3.3** `EvidenceChain.to_dict()` JSON 序列化 (Line 1042)

### M2.4 验证

- [x] **M2.4.1** 23 个单元测试全部通过 (`test_performance_analyzer.py`)
- [x] **M2.4.2** 手动验证 JSON 输出包含完整证据

### M2 验收标准 ✅
```
PerformanceIssue 对象包含 evidence_chain 字段
evidence_chain.to_dict() 输出完整 JSON
```

---

## ✅ M3: UI 增强（跳转与证据展示）— 已完成

> **状态**: ✅ 已完成 (2025-02-05)  
> **实现位置**: `templates/*.html`, `assets/scripts/navigation.js`, `assets/styles/common.css`  
> **文档**: `scripts/rdc_analyzer/docs/EVIDENCE_CHAIN.md`

### M3.1 URL 参数解析

- [x] **M3.1.1** 在各 HTML 页面新增 `parseUrlParams()` 函数
  ```javascript
  function parseUrlParams() {
      const params = new URLSearchParams(window.location.search);
      return {
          id: params.get('id'),
          highlight: params.get('highlight') === 'true',
          range: params.get('range')  // "100-150" 事件范围
      };
  }
  ```

- [x] **M3.1.2** 实现 `highlightAndScrollTo(id)` 函数
  - 滚动到目标元素
  - 播放高亮动画 (CSS pulse)
- [x] **M3.1.3** 在页面 `DOMContentLoaded` 时调用
  ```javascript
  document.addEventListener('DOMContentLoaded', () => {
      const params = parseUrlParams();
      if (params.id && params.highlight) {
          highlightAndScrollTo(params.id);
      }
  });
  ```

### M3.2 跳转按钮实现

- [x] **M3.2.1** 更新 `textures.html` 使用情况列表
  - 点击 DrawCall → 跳转到 `events.html?eventId=xxx&highlight=true`
- [x] **M3.2.2** 更新 `shaders.html` 使用情况列表
  - 点击 DrawCall → 跳转到 `events.html?eventId=xxx&highlight=true`
- [x] **M3.2.3** 更新 `index.html` (recommendations) 操作按钮
  - 渲染 `issue.actions[]` 为可点击按钮
- [x] **M3.2.4** 更新 `index.html` 问题卡片
  - 添加 "跳转到资源" / "跳转到事件" 按钮

### M3.3 证据展示面板

- [x] **M3.3.1** 在 `index.html` 问题区域新增证据区块
  ```html
  <div class="evidence-panel">
      <div class="evidence-row">
          <span class="label">实际值:</span>
          <span class="value actual">{{actual_value}}</span>
      </div>
      <div class="evidence-row">
          <span class="label">阈值:</span>
          <span class="value threshold">{{threshold}}</span>
      </div>
      <div class="evidence-context">
          {{#each context}}
          <span class="context-item">{{label}}: {{value}}</span>
          {{/each}}
      </div>
  </div>
  ```

- [x] **M3.3.2** 新增证据面板样式到 `common.css`
  ```css
  .evidence-panel { /* ... */ }
  .evidence-row .actual { color: #ff6b6b; }
  .evidence-row .threshold { color: #4ecdc4; }
  .pulse-highlight { animation: pulse 0.5s ease-in-out 3; }
  ```

- [x] **M3.3.3** 新增使用情况摘要区块
  ```html
  <div class="usage-summary">
      <h4>使用情况 ({{usageCount}} 次)</h4>
      <ul class="usage-list">
          {{#each usedBy}}
          <li>
              <a href="events.html?id={{event_id}}&highlight=true">
                  #{{event_id}} {{event_name}}
              </a>
              <span class="binding-info">{{binding_type}} @ {{shader_stage}}</span>
          </li>
          {{/each}}
      </ul>
  </div>
  ```

### M3.4 端到端测试

- [x] **M3.4.1** 端到端测试：从 index.html 跳转到 events.html
- [x] **M3.4.2** 验证高亮动画正常播放
- [x] **M3.4.3** 验证 textures.html 使用列表可点击

### M3 验收标准 ✅
```
1. ✅ 点击 Issue 中的 "跳转到事件" → events.html 打开并定位到目标行
2. ✅ 目标行播放 3 次高亮动画 (pulse-highlight CSS)
3. ✅ textures.html 右侧面板点击 DrawCall 链接可跳转
```

### M3 技术实现摘要

| 组件 | 文件 | 说明 |
|------|------|------|
| URL 参数解析 | `navigation.js` | `parseUrlParams()` + 自动滚动 |
| 高亮动画 | `common.css` | `.pulse-highlight` 脉冲动画 |
| Texture→Event | `textures.html` | 点击纹理卡片跳转到使用事件 |
| Event→Shader | `events.html` | 点击 Draw Call 跳转到绑定 Shader |
| Shader→Event | `shaders.html` | 显示反向引用链接 |

---

## ✅ M4: 高级可视化（可选）— 已完成

> **状态**: ✅ 已完成 (2025-02-08，文档追溯补录)  
> **优先级**: P2 (可选)  
> **预估工时**: 2 天  
> **源文档**: `EVIDENCE_CHAIN_DEVELOPMENT_PLAN.md` 第 335-365 行

### M4.1 资源绑定热力图 ✅ 已完成

> **状态**: ✅ 已完成 (2025-02-08，文档追溯补录)  
> **实现位置**: `core/heatmap_builder.py`, `report_bundle_generator.py`, `events.html`

- [x] **M4.1.1** 在 `events.html` 时间线新增热力图图层
  - 实现文件: `templates/events.html` 第 2557-2808 行
  - 功能: 热力图切换按钮、资源选择器、颜色图例
- [x] **M4.1.2** 实现 `renderBindingHeatmap(resource_id)` 函数
  - JS 函数: `renderHeatmap()`, `onHeatmapResourceChange()`, `toggleHeatmap()`
  - 后端: `HeatmapBuilder.build_for_resource()` in `core/heatmap_builder.py`
- [x] **M4.1.3** 冗余绑定区域标红，正常绑定标绿
  - 模式颜色: FIRST_USE(蓝), CONTINUOUS(绿), SPARSE(黄), ISOLATED(红)
  - Schema: `schema/report_heatmap_data.schema.json`
  - 单元测试: `tests/test_heatmap_builder.py` (11/11 通过)

### M4.2 Pass 分组视图 ✅ 已完成

> **状态**: ✅ 已完成 (2025-02-08，文档追溯补录)  
> **实现位置**: `templates/events.html`

- [x] **M4.2.1** 在 `events.html` 新增 Pass 分组视图
  - 切换按钮: 第 1334 行 `<button id="passModeToggle">`
  - 构建逻辑: 第 2005 行 `buildPassGroups()` - 基于 marker_push/pop
  - 嵌套支持: 使用栈结构处理嵌套 Pass
- [x] **M4.2.2** 实现 Pass 折叠/展开
  - 单个切换: 第 2127 行 `togglePassExpand(passKey)`
  - 全部展开: 第 2137 行 `expandAllPasses()`
  - 全部折叠: 第 2148 行 `collapseAllPasses()`
  - 状态保持: `passExpandState` 对象记录每个 Pass 状态
- [x] **M4.2.3** 显示 Pass 级别的 GPU 时间统计
  - 时间计算: 第 2038-2040 行 `currentPass.gpuTime = children.reduce(...)`
  - Draw 计数: 第 2041-2043 行 `currentPass.drawCount = children.filter(...)`
  - UI 显示: 第 1739 行 `formatGpuTime(pass.gpuTime)` + 第 1747-1757 行统计面板

---

## 🔵 Phase 5: B-mode 统计对比

> **目标**: 增强双帧对比能力，支持 CI 回归门禁  
> **源文档**: `TASK_TRACKER.md` 第 210-268 行

### Phase 5.1 多帧统计采样 ✅ 完成

- [x] **P5.1.1** 添加 `--samples N` 参数到 compare 命令
- [x] **P5.1.2** 实现多帧数据聚合逻辑 (`stats/sampler.py`: `MultiFrameSampler`)
- [x] **P5.1.3** 输出统计摘要 (mean/median/p95) (`MetricStatistics` dataclass)

### Phase 5.2 统计显著性检测 ✅ 完成

- [x] **P5.2.1** 引入置信区间计算 (`stats/summary.py`: Z-score + Welch's t-test)
- [x] **P5.2.2** 输出 `significance` (high/medium/low) + Cohen's d 效应量
- [x] **P5.2.3** 添加 `--confidence-level` 参数 (支持 90%/95%/99%)

### Phase 5.3 Marker/Pass 对齐 ✅ 完成

- [x] **P5.3.1** 实现按 marker 名称对齐 (`--align-strategy marker`)
- [x] **P5.3.2** 实现按 pipeline signature 对齐 (`--align-strategy signature`)
- [x] **P5.3.3** CLI 参数透传到 DiffEngine

### Phase 5.4 CI 集成 ✅ 完成

- [x] **P5.4.1** 输出 JUnit XML 格式 (`stats/junit_reporter.py`)
- [x] **P5.4.2** 实现合理的 exit code (回归检测 → exit 1)
- [x] **P5.4.3** 编写 GitHub Action 示例 (`docs/E2E_WORKFLOW_GUIDE.md`)

---

## ✅ Phase 6: P0 报告完善 — 已完成

> **状态**: ✅ 已完成 (2025-02-07)  
> **目标**: 完善报告生成能力，确保数据完整性  
> **文档**: `scripts/rdc_analyzer/docs/E2E_WORKFLOW_GUIDE.md`

### Phase 6.1 纹理缩略图 (P0.1) ✅ 完成

- [x] **P0.1.1** 在 `xml_to_bundle.py` 添加 `--zip` 参数
- [x] **P0.1.2** 实现 `generate_thumbnails_from_zip()` 函数
- [x] **P0.1.3** 自动检测同名 ZIP 文件

### Phase 6.2 Shader 源码提取 (P0.2) ✅ 完成

- [x] **P0.2.1** 在 `xml_to_bundle.py` 添加 `--rdc` 参数
- [x] **P0.2.2** 实现 `extract_vulkan_shaders_from_rdc()` 函数
- [x] **P0.2.3** 添加 `--spirv-cross` SPIR-V 转 GLSL 支持

### Phase 6.3 RT 快照功能 (P0.3) ✅ 已有实现

- [x] **P0.3.1** 分析确认 RDC API 路径已支持 RT 导出
- [x] **P0.3.2** `rdc_to_bundle_standalone.py` 已支持 `--export-rt`
- [x] **P0.3.3** `events.html` 已支持 rtSnapshot 展示

### Phase 6.4 JSON Schema 验证 (P0.4) ✅ 完成

- [x] **P0.4.1** 分析现有 Schema 体系 (`scripts/rdc_analyzer/schema/`)
- [x] **P0.4.2** 创建 4 个核心 Schema 文件:
  - `textures_data.schema.json`
  - `events_data.schema.json`
  - `report_bundle.schema.json`
  - `comparison_result.schema.json`
- [x] **P0.4.3** 在 `report_bundle_generator.py` 集成 Schema 验证
- [x] **P0.4.4** 添加 `--validate` CLI 选项

### Phase 6 验收标准 ✅
```
1. ✅ xml_to_bundle.py --validate 执行无错误
2. ✅ 纹理缩略图从 ZIP 正确提取
3. ✅ Vulkan Shader 源码可转换为 GLSL
4. ✅ 所有核心 Schema 文件齐全
```

---

## ✅ Phase 7: 端到端验证与性能优化 — 已完成

> **状态**: ✅ 已完成 (2025-02-08)  
> **目标**: 真实数据验证 + 文档完善 + 性能优化  
> **文档**: `scripts/rdc_analyzer/docs/E2E_WORKFLOW_GUIDE.md`

### Phase 7A: 真实 RDC 端到端测试 ✅ 完成

- [x] **P7A.1** RDC → XML 转换测试 (renderdoccmd)
- [x] **P7A.2** XML → Bundle 报告生成测试
- [x] **P7A.3** 数据完整性验证 (manifest.json)
- [x] **P7A.4** 多帧对比 + JUnit XML 输出测试

### Phase 7B: 文档完善 ✅ 完成

- [x] **P7B.1** 创建 `E2E_WORKFLOW_GUIDE.md` 工作流指南
- [x] **P7B.2** 更新 `INDEX.md` 至 v2.6.0
- [x] **P7B.3** 创建 `MULTI_FRAME_GUIDE.md` 多帧统计指南
- [x] **P7B.4** 创建 `API_REFERENCE.md` API 参考手册

### Phase 7C: 性能优化 ✅ 完成

- [x] **P7C.1** 流式 XML 解析 (iterparse) - `rdc_xml_parser.py`
- [x] **P7C.2** 进度回调机制 - `zipxml_event_parser.py`
- [x] **P7C.3** JSON 流式加载文档标注 - `API_REFERENCE.md` (ijson)
- [x] **P7C.4** HTML 数据外置 + 异步加载 - `--external-data` 参数

### Phase 7C.4 优化效果

| 文件 | 优化前 | 优化后 | 减少 |
|------|--------|--------|------|
| `events.html` | 724 KB | 116 KB | **-84%** |
| `textures.html` | 219 KB | 184 KB | -16% |
| `shaders.html` | 139 KB | 125 KB | -10% |

### Phase 7 验收标准 ✅
```
1. ✅ 真实 RDC (game_frame3996.rdc) 完整分析流程通过
2. ✅ 文档索引更新至 v2.6.0
3. ✅ --external-data 参数正常工作，HTML 大小显著减少
4. ✅ 异步加载机制测试通过
```

---

## ✅ 快速修复项 — 已完成

### P0-NEW-3: verification_plan schema 规范化 ✅

> **状态**: ✅ 已完成 (2025-02-05)  
> **源文档**: `WORK_SUMMARY_ROADMAP.md` 第 13-16 行

- [x] 统一 `how_to_verify` → `how_to_capture` 字段命名
- [x] 统一 `expected_direction` 枚举值 (`increase`/`decrease`/`unchanged`)
- [x] 更新 `main.py:_build_suggestions()` 函数
- [x] DOD 测试: `test_dod_compliance.py::TestVerificationPlanSchema` 4/4 通过

---

## 📝 开发约定

### Git 提交格式
```bash
# 每完成一个开发点后提交
git add <files>
git commit -m "feat(evidence-chain): M1.1.1 完成 - UsageRecord 数据类

- 新增 UsageRecord dataclass
- 包含 event_id, binding_type, shader_stage 等字段"
```

### 验证命令
```bash
# 在 scripts/rdc_analyzer 目录下执行
py -3 -m pytest -q -rs

# 生成测试报告
py -3 -m rdc_analyzer analyze test.rdc -o output/
```

### 文档更新
每完成一个里程碑后，更新本文件：
1. 将 `[ ]` 改为 `[x]`
2. 更新顶部进度表
3. 提交: `git commit -m "docs: 更新 M1 完成状态"`

---

## 🔗 相关链接

- [RenderDoc Python API](https://renderdoc.org/docs/python_api/index.html)
- [项目 README](../../../scripts/rdc_analyzer/README.md)
- [规则文档](../../../scripts/rdc_analyzer/RULES.md)

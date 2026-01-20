# RDC Analyzer 任务追踪表

> **创建日期**: 2025-01-20  
> **目标**: 完成单帧极致分析 + 双帧全方位对比  
> **环境**: Windows PC + D3D11/D3D12 RDC 文件

---

## 📊 总体进度

| 阶段 | 状态 | 进度 |
|------|:----:|------|
| Phase 1: 工程治理 | 🔄 进行中 | 0/3 |
| Phase 2: 单帧分析增强 | ⏳ 待开始 | 0/4 |
| Phase 3: 双帧对比 | ⏳ 待开始 | 0/3 |
| Phase 4: 真实数据集成 | ⏳ 待开始 | 0/2 |

---

## Phase 1: 工程治理（基础设施）

> **目标**: 修复测试、清理技术债，为后续开发打好基础

### TASK-P1-01: 修复测试红灯 [P0-5]

| 字段 | 内容 |
|------|------|
| **状态** | ⏳ 待开始 |
| **优先级** | 🔴 P0 (阻塞后续开发) |
| **预估工时** | 1-2h |
| **问题描述** | 当前 4 failed + 1 error |
| **失败项** | 1. `test_shader_extractor.py:243` - HTML_TEMPLATE 常量缺失 (x4)<br>2. `test_resource_inspector.py:99` - controller fixture 缺失 |
| **验收标准** | `py -3 -m pytest -m 'not integration'` 全绿 (0 failed, 0 error) |

**修复方案**:
- [ ] 修复 HTML_TEMPLATE 相关测试（使用 TemplateLoader 或 mock）
- [ ] 将需要 Replay 环境的测试标记为 `@pytest.mark.integration`

---

### TASK-P1-02: 统一 Issue 数据结构 [P0-3]

| 字段 | 内容 |
|------|------|
| **状态** | ⏳ 待开始 |
| **优先级** | 🔴 P0 |
| **预估工时** | 3-4h |
| **问题描述** | 存在多套 Issue 模型：`core.types.Issue` vs `main.py` dict vs `BindingIssue` |
| **验收标准** | 所有分析模块输出统一的 `core.types.Issue` |

**修复方案**:
- [ ] 让 `main.py` 的 `_analyze_rules()` 调用 `RuleRunner`
- [ ] 将 BIND*/PERF* 也输出为 `Issue` dataclass
- [ ] 统一字段：`code`, `severity`, `category`, `message`, `event_id`, `resource_ids`

---

### TASK-P1-03: 激活 36 条 RD_* 规则

| 字段 | 内容 |
|------|------|
| **状态** | ⏳ 待开始 |
| **优先级** | 🟡 P1 |
| **预估工时** | 2h |
| **问题描述** | 新 `main.py` pipeline 没有调用 `RuleRunner`，36条规则未生效 |
| **证据** | `main.py:403` 直接 append dict，未调用 `register_all_rules()` |
| **验收标准** | analyze 输出包含 RD_DC_*, RD_TEX_*, RD_BUF_* 等规则结果 |

**修复方案**:
- [ ] 在 `main.py._analyze_rules()` 中调用 `register_all_rules()` + `RuleRunner`
- [ ] 合并 RuleRunner 输出到 `self._issues`

---

## Phase 2: 单帧分析增强

> **目标**: 提升单帧分析的深度和可信度

### TASK-P2-01: 定义 Canonical Schema [P0-1]

| 字段 | 内容 |
|------|------|
| **状态** | ⏳ 待开始 |
| **优先级** | 🔴 P0 |
| **预估工时** | 3-4h |
| **问题描述** | 多条链路输出字段口径不一致，compare 无法做同口径对比 |
| **验收标准** | 定义 `analysis.schema.json`，所有导出遵循此 schema |

**输出 Schema 结构**:
```json
{
  "schema_version": "2.0.0",
  "meta": { "rdc_path", "api", "platform", "timestamp" },
  "stats": { "draw_call_count", "texture_count", "buffer_count", ... },
  "events": [{ "event_id", "marker_path", "action_type", ... }],
  "resources": {
    "textures": [...],
    "buffers": [...],
    "shaders": [...]
  },
  "issues": [{ "code", "severity", "category", "message", "event_id", ... }],
  "suggestions": [...]
}
```

---

### TASK-P2-02: 阈值体系平台化 [P1-1]

| 字段 | 内容 |
|------|------|
| **状态** | ⏳ 待开始 |
| **优先级** | 🟡 P1 |
| **预估工时** | 2-3h |
| **问题描述** | 规则阈值 key 与 config/thresholds.py 不一致 |
| **证据** | `DrawCallCountRule` 用 `draw_call_count`(默认2000)，config 用 `max_draw_calls`(PC=3000) |
| **验收标准** | 所有规则使用统一的 thresholds key，支持 pc/mobile 切换 |

---

### TASK-P2-03: 移除 main.py 占位实现 [P0-2 简化版]

| 字段 | 内容 |
|------|------|
| **状态** | ⏳ 待开始 |
| **优先级** | 🟡 P1 |
| **预估工时** | 4h |
| **问题描述** | `main.py:1005` 用动态 type 造假 DrawCallDetail，`main.py:1043` 资源生命周期全是假设 |
| **验收标准** | 在无 Replay 环境时，明确标注数据为"估算值"而非伪装成真实数据 |

**修复方案**:
- [ ] 添加 `is_estimated: bool` 字段区分真实/估算数据
- [ ] 在报告中标注数据来源（Replay API / 启发式估算）

---

### TASK-P2-04: 完善 OptimizationAdvisor 建议覆盖

| 字段 | 内容 |
|------|------|
| **状态** | ⏳ 待开始 |
| **优先级** | 🟢 P2 |
| **预估工时** | 3h |
| **问题描述** | 当前建议偏纹理维度，缺少 DrawCall/Shader/State 维度建议 |
| **验收标准** | 建议覆盖：纹理、DrawCall、Shader、Buffer、Pass |

---

## Phase 3: 双帧对比（核心目标 2）

> **目标**: 完成全方位双帧对比 + 回归检测

### TASK-P3-01: Compare CLI 子命令 [P0-4]

| 字段 | 内容 |
|------|------|
| **状态** | ⏳ 待开始 |
| **优先级** | 🔴 P0 |
| **预估工时** | 2-3h |
| **问题描述** | compare 不是一级 CLI 命令，产品形态弱 |
| **验收标准** | `python -m rdc_analyzer compare baseline.rdc target.rdc` 可用 |

**实现方案**:
- [ ] 在 `__main__.py` 添加 `compare` 子命令
- [ ] 支持输入：两个 RDC 文件 / 两个 analysis.json
- [ ] 输出：`compare.json` + `compare.html`

---

### TASK-P3-02: 统一 Compare 输入口径

| 字段 | 内容 |
|------|------|
| **状态** | ⏳ 待开始 |
| **优先级** | 🔴 P0 |
| **预估工时** | 3h |
| **问题描述** | `compare_rdc.py:118` 的 Phase1→Phase2 兼容层会把关键字段填 0 |
| **证据** | `compare_rdc.py:154` 强制 `totalVertices=0, events=[]` |
| **验收标准** | compare 只接受 Canonical Schema (TASK-P2-01)，不再做猜字段 |

---

### TASK-P3-03: 增强回归检测证据链

| 字段 | 内容 |
|------|------|
| **状态** | ⏳ 待开始 |
| **优先级** | 🟡 P1 |
| **预估工时** | 4h |
| **问题描述** | RegressionDetector 只输出数值变化，缺少根因定位 |
| **验收标准** | 每条回归结论绑定：marker_path + event_id + 关键资源变化 |

---

## Phase 4: 真实数据集成

> **目标**: 连接 RenderDoc Replay API，获取真实 Pipeline State

### TASK-P4-01: 验证 D3D11 Replay 环境

| 字段 | 内容 |
|------|------|
| **状态** | ⏳ 待开始 |
| **优先级** | 🟡 P1 |
| **预估工时** | 2h |
| **前置条件** | 需要 RenderDoc Python 模块 + D3D11 RDC 文件 |
| **验收标准** | 能成功打开 RDC 并读取 Pipeline State |

**验证步骤**:
- [ ] 确认 `import renderdoc` 可用
- [ ] 测试 `ReplayWrapper.open()` 打开 D3D11 RDC
- [ ] 验证 `get_pipeline_state()` 返回真实数据

---

### TASK-P4-02: 集成真实 PipelineSnapshot [P0-2]

| 字段 | 内容 |
|------|------|
| **状态** | ⏳ 待开始 |
| **优先级** | 🔴 P0 (但依赖 P4-01) |
| **预估工时** | 8-12h |
| **问题描述** | 主 pipeline 用占位对象，深度模块（CallAnalyzer/ResourceTracker）无真实输入 |
| **验收标准** | 关键 draw/dispatch 有真实 snapshot，规则/建议基于真实数据 |

---

## ✅ 已完成任务

| 任务 | 完成日期 | Commit |
|------|---------|--------|
| 方向 B: Shader 源码提取 | 2025-01-19 | 9a8a06a27 |
| 方向 C: 渲染目标追踪 | 2025-01-19 | 6def8b85b |
| 方向 F: 性能热点分析 | 2025-01-20 | 749852014 |
| Milestone 4: UX 交互增强 | 2025-01-18 | - |

---

## 📝 附录：文件索引

### 核心分析链路
| 文件 | 职责 |
|------|------|
| `main.py` | 新端到端 pipeline (CLI 主入口) |
| `pipeline.py` | 旧模块化 pipeline (有 RuleRunner) |
| `compare_rdc.py` | 对比脚本 (待升级为 CLI) |

### 规则与建议
| 文件 | 职责 |
|------|------|
| `rules/runner.py` | RuleRunner (执行 36 条规则) |
| `rules/*.py` | RD_DC_*, RD_TEX_*, RD_BUF_* 等规则 |
| `core/optimization_advisor.py` | 优化建议生成 |

### 深度分析模块
| 文件 | 职责 |
|------|------|
| `extractors/replay_wrapper.py` | RenderDoc API 封装 |
| `analysis/call_analyzer.py` | 调用级绑定分析 |
| `analysis/resource_tracker.py` | 资源生命周期追踪 |

### 对比与回归
| 文件 | 职责 |
|------|------|
| `diff/diff_engine.py` | 结构化差异计算 |
| `diff/regression_detector.py` | 回归检测 |
| `diff/regression_types.py` | REG001~REG007 规则 |

---

## 🎯 推荐执行顺序

```
1. TASK-P1-01 (修复测试) ← 最低成本，解锁后续开发
      ↓
2. TASK-P1-02 (统一 Issue) + TASK-P1-03 (激活规则)
      ↓
3. TASK-P3-01 (Compare CLI) ← 产品化双帧对比
      ↓
4. TASK-P2-01 (Canonical Schema) + TASK-P3-02 (统一输入)
      ↓
5. TASK-P4-01 (验证环境) → TASK-P4-02 (真实数据)
```

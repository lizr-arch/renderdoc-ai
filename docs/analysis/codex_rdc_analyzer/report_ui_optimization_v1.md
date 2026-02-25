# Report UI Optimization v1 (Jump‑First)

> **目标**：定义离线报告/WebUI 的 UI 优化清单（P0/P1/P2），并明确“默认不全量导出纹理/RT，跳转优先”的策略。

## 1. 默认策略（必须遵守）

- **默认不全量导出纹理/RT**：报告只展示元数据 + 跳转（EID / 资源 ID）。
- **导出缩略图仅作为可选增强**：只允许 Top‑N 或高风险资源（按内存/绑定/RT 切换频次）。
- **全量导出仅用于离线分享**：需显式开关启用（非默认）。
- **事件跳转优先**：UI 中所有列表必须能定位到 EID。

## 2. 页面级优化清单（P0 必做）

### 2.1 Overview
- 顶部指标卡：Draw/Dispatch、Shader 数、Texture/RT 数、Pass 数
- 风险摘要：Top 5 Issues（若无 Issues，显示“暂无规则命中”）
- 热点提示：RT 切换最频繁的 Pass/事件

### 2.2 Events / Passes
- Pass 分组 + 事件搜索/过滤（marker、类型、RT 变化）
- 每个 Pass 显示：Draw/Dispatch/RT/DS 绑定计数
- 支持 **EID 一键复制** + **Jump to GUI**（可用时）

### 2.3 Shaders
- 分组：按 Stage（VS/PS/CS/GS…）
- 列表列：入口、字节码大小、绑定资源数量、使用频次
- 支持跳转：Shader → 使用事件列表（EID）

### 2.4 Textures / RT
- 关键列：格式/尺寸/内存估算/RT/DS 标识/绑定次数
- 支持过滤：RT‑only / Depth‑only / MSAA
- 支持关联：首次/末次使用事件

### 2.5 Pipeline State
- 统计“状态切换密度”（Blend/Depth/Raster）
- 列表提供事件级状态快照（可筛选）

### 2.6 Uniforms / CBuffers
- 统计常量缓冲绑定数量、更新频次（若可用）
- 关联 Shader + 事件

## 3. P1 / P2 增强清单

### P1（Mali Offline Compiler）
- Shader 列表增加 Mali 指标列（cycles/寄存器/警告）
- 支持按 Mali 指标排序（寻找最贵 shader）

### P2（外部 profiler 占位）
- 列表添加 `external.<tool>` 列占位（RGP/Nsight/PIX）
- 仅展示占位提示，不阻塞 P0

## 4. 交互与可用性规范

- **统一筛选栏**：Events/Shaders/Textures 共享过滤逻辑
- **列表排序默认规则**：
  - Shaders：使用频次/绑定数量
  - Textures：内存估算/RT 切换频次
  - Passes：Draw 数/RT 切换
- **跳转兼容**：
  - 内嵌 WebUI server 可用 → 显示 Jump 按钮
  - 外部 WebUI server → 隐藏/禁用 Jump 并提示
- **问题导出**：
  - 报告目录输出 `issues_export.json` + `issues_export.csv`
  - 每个问题条目包含 `severity/message/event_id/resource_id`

## 5. 字段映射（参考 schema）

| UI 区域 | 字段来源（analysis.json） |
| --- | --- |
| Overview | `summary`, `issues`, `suggestions` |
| Events/Passes | `events`, `passes` |
| Shaders | `shaders` |
| Textures/RT | `textures` |
| Pipeline State | `pipeline_state` |
| Uniforms | `uniforms` |

> Schema 参考：`analysis_report_schema_v1.md`

## 6. 缺口与 TODO

- `uniforms` 在 D3D11/D3D12 的可用性待验证
- `pipeline_state` 是否覆盖所有状态切换（需核对 DrawCallInfo）
- RT/DS 绑定细节在 XML 模式下的完整性待核验

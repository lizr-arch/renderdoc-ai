# 00_README_FEED_ORDER — Codex 投喂顺序与总约束

版本：v0.2  
日期：2026-04-24  
用途：把 Engine Annotation Protocol，简称 EAP，拆成可由本地 Codex 顺序执行的开发任务。

---

## 1. 总目标

在现有游戏引擎中接入一套 **Engine Annotation Protocol**，让 RenderDoc capture 从低语义 API 事件变成带公司/引擎语义的工程证据。

首版目标不是重写 RenderDoc，也不是立刻做 AI，而是先交付这几个能力：

1. 引擎运行时能动态发现 RenderDoc in-application API。
2. 能通过 RenderDoc v1.43+ 的 rich annotation API 写入 per-command / per-object typed annotations。
3. 能在每帧 capture 同步生成 `*.rmeta.json` sidecar。
4. 能把 render graph、pass、draw/dispatch、resource、material、shader、PSO、asset path 关联起来。
5. 能提供最小规则检查和只读分析入口，供后续 MCP/AI/CI 使用。

---

## 2. 为什么要拆成多份文档

本地 Codex 最怕“超长需求 + 多目标 + 未限定改动范围”。本包按开发顺序拆分：

| 顺序 | 文件 | 用途 |
|---:|---|---|
| 00 | `00_README_FEED_ORDER.md` | 投喂顺序、总约束、验收方式 |
| 01 | `01_REPO_RECON_AND_BOUNDARIES.md` | 先让 Codex 侦察仓库，不写代码 |
| 02 | `02_EAP_PROTOCOL_SPEC.md` | 协议、key、类型、sidecar 数据模型 |
| 03 | `03_TASK_RENDERDOC_BRIDGE.md` | 动态加载 RenderDoc API 1.7.0，封装 annotation 调用 |
| 04 | `04_TASK_EAP_CORE_TYPES.md` | EAP typed data、校验、采样、RAII context |
| 05 | `05_TASK_ENGINE_HOOKS.md` | 接入 render graph / draw / dispatch / resource hooks |
| 06 | `06_TASK_SIDECAR_WRITER.md` | `*.rmeta.json` 生成、原子写入、脱敏 |
| 07 | `07_TASK_RULE_ENGINE_MVP.md` | 第一批规则检查与报告结构 |
| 08 | `08_TASK_ANALYZER_CLI.md` | 本地分析 CLI，输出 summary / rule results |
| 09 | `09_TASK_UI_MINIMAL.md` | 最小 UI/调试面板，不强依赖 qrenderdoc 修改 |
| 10 | `10_TASK_MCP_READONLY_SERVER.md` | 后置只读 MCP server 设计 |
| 11 | `11_VALIDATION_TEST_SECURITY.md` | 单测、集成测试、性能、安全验收 |
| 12 | `12_CODEX_MASTER_PROMPTS.md` | 可复制给 Codex 的逐步 prompt |

---

## 3. 推荐投喂方式

### 第 0 轮：只做仓库侦察

投喂：

- `00_README_FEED_ORDER.md`
- `01_REPO_RECON_AND_BOUNDARIES.md`

要求 Codex：

- 只读代码；
- 找出渲染后端、render graph、draw submission、resource creation、shader/material 系统、构建系统；
- 输出 `EAP_IMPLEMENTATION_MAP.md`；
- 不改代码。

### 第 1 轮：协议和 RenderDoc Bridge

投喂：

- `02_EAP_PROTOCOL_SPEC.md`
- `03_TASK_RENDERDOC_BRIDGE.md`

要求 Codex：

- 新增 RenderDoc bridge 模块；
- 不接业务逻辑；
- 单测动态加载失败、API 缺失、no-op、annotation 参数校验。

### 第 2 轮：EAP core types

投喂：

- `02_EAP_PROTOCOL_SPEC.md`
- `04_TASK_EAP_CORE_TYPES.md`

要求 Codex：

- 新增 EAP 数据结构；
- 实现 key/value 校验；
- 实现 scope/context；
- 不改渲染路径。

### 第 3 轮：接入引擎 hooks

投喂：

- `05_TASK_ENGINE_HOOKS.md`
- 第 0 轮生成的 `EAP_IMPLEMENTATION_MAP.md`

要求 Codex：

- 在 render graph pass、draw/dispatch、resource creation 附近写 EAP 数据；
- 所有代码必须可编译；
- 没有 RenderDoc 时必须零功能影响。

### 第 4 轮：sidecar

投喂：

- `06_TASK_SIDECAR_WRITER.md`

要求 Codex：

- capture 期间收集 EAP 事件；
- capture 结束后写 `*.rmeta.json`；
- 使用 atomic write；
- 加基本 redaction。

### 第 5 轮：规则与 CLI

投喂：

- `07_TASK_RULE_ENGINE_MVP.md`
- `08_TASK_ANALYZER_CLI.md`

要求 Codex：

- 支持对 sidecar 运行规则；
- 输出机器可读 JSON 和人类可读摘要；
- 可被 CI 调用。

### 第 6 轮：UI / MCP 后置

投喂：

- `09_TASK_UI_MINIMAL.md`
- `10_TASK_MCP_READONLY_SERVER.md`
- `11_VALIDATION_TEST_SECURITY.md`

要求 Codex：

- 只做最小可用 UI/命令入口；
- MCP 只读；
- 写操作全部后置。

---

## 4. 全局开发约束

Codex 必须遵守：

1. **不要重写 RenderDoc core。** 第一阶段只从引擎侧接入 RenderDoc API 和 sidecar。
2. **没有 RenderDoc 时必须 no-op。** 不能影响正常游戏运行、编辑器运行、自动化测试。
3. **默认只在 development/editor/profile build 启用。** Shipping build 默认禁用。
4. **所有数据采集必须可开关。** 至少提供 compile-time flag + runtime CVar/setting。
5. **不要在热路径做堆分配。** draw 级 annotation 必须限流、缓存或只在 capture 时启用。
6. **sidecar 写入必须原子化。** 先写临时文件，再 rename。
7. **不要上传任何数据。** Capture Hub/MCP 上传后置，首版只写本地文件。
8. **不要把完整资产内容写入 sidecar。** 只写 ID、路径、hash、尺寸、格式、mip 等元数据。
9. **不要让 LLM 直接读 RDC 二进制。** 后续 AI 只读 sidecar、规则结果、受控 API。
10. **每一步都要有单测或最小集成测试。** 无法真实 capture 时，也要有 mock bridge 测试。

---

## 5. 总体目录建议

Codex 应根据仓库实际结构适配。若仓库没有明显约定，采用以下目录：

```text
Source/Runtime/RenderDocEAP/
  Public/
    EAPConfig.h
    EAPIds.h
    EAPTypes.h
    EAPKeys.h
    EAPRenderDocBridge.h
    EAPContext.h
    EAPSidecar.h
    EAPRuleEngine.h
  Private/
    EAPRenderDocBridge.cpp
    EAPContext.cpp
    EAPKeyValidation.cpp
    EAPSidecarWriter.cpp
    EAPRedaction.cpp
    EAPRuleEngine.cpp
  Tests/
    EAPBridgeTests.cpp
    EAPKeyValidationTests.cpp
    EAPSidecarTests.cpp
    EAPRuleEngineTests.cpp
Tools/EAPAnalyzer/
  main.cpp
  README.md
Docs/EAP/
  EAP_PROTOCOL.md
  EAP_CAPTURE_EXAMPLES.md
```

如果是 Unreal 风格仓库，可以放成模块：

```text
Engine/Source/Developer/RenderDocEAP/
Engine/Source/Developer/EAPAnalyzer/
```

如果是自研引擎单体仓库，优先放到 graphics diagnostics / tools / developer runtime 相关目录。

---

## 6. 总体架构

```text
Game / Editor / Engine
  ↓
EAP Runtime Module
  ├─ RenderDocBridge              # 调用 RenderDoc annotation API，可 no-op
  ├─ EAPContext                   # 当前 frame/pass/draw/resource 上下文
  ├─ SidecarWriter                # capture sidecar JSON
  ├─ RuleEngine                   # 本地规则检查
  └─ BackendAdapters              # D3D12/Vulkan/GL resource handle 适配
  ↓
RenderDoc Capture (.rdc) + EAP Sidecar (.rmeta.json)
  ↓
Analyzer CLI / UI / MCP / CI / Capture Hub
```

---

## 7. 首版成功标准

完成第 1–4 轮后，首个真实验收是：

1. 启动开发版游戏或编辑器。
2. RenderDoc attach 或通过 RenderDoc 启动。
3. 抓一帧。
4. 在 RenderDoc event/object annotation 中能看到：
   - pass name；
   - render graph node id；
   - draw/dispatch kind；
   - material id/name/path；
   - shader hash/permutation；
   - PSO hash；
   - mesh id/LOD；
   - resource asset path/format/size/mip。
5. 同目录生成 `capture_name.rmeta.json`。
6. `eap-analyze capture_name.rmeta.json --summary` 能输出 pass/draw/resource 概览。
7. 关闭 RenderDoc 或关闭 EAP 后，游戏行为和性能不受明显影响。

---

## 8. 首版不做

以下全部后置：

- 完整 Capture Hub；
- 云端 replay；
- 自动上传；
- 修改 qrenderdoc 深层 UI；
- 自动创建 Jira；
- AI 自动改 shader；
- 写入型 MCP tools；
- 跨项目资产解密；
- 把全部 material 参数展开进 RDC；
- 抓任意第三方商业程序。


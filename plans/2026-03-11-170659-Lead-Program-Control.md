# 计划：Lead / RenderDoc AI Program Control

时间：2026-03-11 17:06:59 | 负责人：Lead

## Scope / Assumptions

- 目标：把当前 RenderDoc AI 项目收束为可由 `2-4` 位 Codex 并行执行的稳定任务包，避免再靠聊天记录维持上下文。
- 本计划只负责产品设计、任务拆分、进度控制、验收标准与合流顺序，不包含任何代码实现。
- 负责人角色固定为：产品经理 + 架构负责人 + 项目负责人；当前轮不参与代码开发。
- 负责人同时负责 `git` 协作方案设计：基线冻结、分支策略、worktree 拓扑、合流顺序与操作指引。
- 事实边界以 `docs/product/development_charter.md`、`docs/product/snapshot_schema_v1.md`、`docs/product/template_contract_v1.md`、`docs/product/mcp_query_contract_v1.md` 为准。

## Program Goals

1. 固定三条主线：`底座 / 报告 / 智能`。
2. 固定四大功能点边界：`RenderDoc 魔改`、`Analyzer Report`、`MCP`、`Skill`。
3. 固定并行开发边界：每位 Codex 只负责一个稳定写入集合。
4. 固定合流顺序：先收束事实层，再扩智能层。
5. 固定新对话恢复入口：先读 handoff，再读总纲，再读各自 plan。
6. 固定 `git` 操作模型：不允许多个执行 Codex 共用同一工作区开发。

## Workstreams

### Stream D：Android Launch Diagnose（M0-C）

- 负责人：`AgentD`
- 范围：Android launch 失败分类统一、用户可读原因、修复建议映射、详细诊断入口。
- 写入边界：`qrenderdoc/Windows/MainWindow.*`
- 禁止越界：不重做 preflight，不重做 analyzer 导出，不碰 `tools/mcp/` 与 `scripts/rdc_analyzer/`。

### Stream B：GUI Snapshot

- 负责人：`AgentB`
- 范围：GUI `AnalyzerSnapshot -> snapshot.v1` adapter 与导出接线。
- 写入边界：`qrenderdoc/Code/Analyzer/*`、`qrenderdoc/Windows/AnalyzerReportViewer.*`
- 禁止越界：不改 Android launch 流程，不改 MCP/Skill。

### Stream C：Offline Snapshot + Renderer

- 负责人：`AgentC`
- 范围：离线 `snapshot.v1` builder、共享 renderer、legacy bundle fallback。
- 写入边界：`scripts/rdc_analyzer/*`
- 禁止越界：不碰 `qrenderdoc` C++ GUI，不在 renderer 里直接读 XML 私有结构作为长期方案。

### Stream A：MCP + Skill Snapshot Consumer

- 负责人：`AgentA`
- 范围：`snapshot.v1` 缺口识别、MCP 补数、Markdown 简报 + 命令清单。
- 写入边界：`tools/mcp/*`、`scripts/rdc_analyzer/mcp_examples/*`、必要的 provider 层。
- 禁止越界：不生成完整报告，不复制模板，不要求 legacy `analysis.json`。

## Ownership Matrix

| Stream | Owner | Primary Deliverable | Depends On |
| --- | --- | --- | --- |
| D | AgentD | Android launch diagnose unification | 已有 M0-B preflight |
| B | AgentB | GUI `snapshot.v1.json` | `snapshot_schema_v1` |
| C | AgentC | Offline `snapshot.v1.json` + renderer | `snapshot_schema_v1` + `template_contract_v1` |
| A | AgentA | Snapshot gap detector + enricher | GUI/Offline `snapshot.v1` 出口 |

## Git Collaboration Model

### Role of Lead

负责人负责以下 `git` 协作设计与指引：

- 检查当前工作区是否存在需要冻结的未提交基线。
- 决定是否先创建集成分支，再切分执行分支。
- 决定每位执行 Codex 是否使用独立 `worktree`。
- 指引操作者按顺序创建分支、分配工作目录、回收提交、执行 `cherry-pick` 合流。
- 在出现冲突或脏工作区时，要求先停下并重新确认基线。

### Required Topology

- `1` 个集成分支：负责最终合流与验收。
- `N` 个执行分支：每位 Codex 一条分支。
- `N` 个独立 `worktree`：每位 Codex 一份独立工作目录。
- Lead 自己不进入执行分支写代码，只做检查与指挥。

### Recommended Branch Layout

- 集成分支：`integration/renderdoc-ai-<date>`
- `AgentD`：`agentd/m0c-android-launch`
- `AgentB`：`agentb/gui-snapshot-v1`
- `AgentC`：`agentc/offline-snapshot-v1`
- `AgentA`：`agenta/mcp-skill-snapshot-consumer`

### Required Operator Flow

1. 负责人先检查 `git status --short`，确认当前工作区是否需要冻结基线。
2. 若现有未提交内容属于本轮共同起点，负责人先指导操作者创建基线提交。
3. 负责人再指导操作者创建集成分支和各自 `worktree`。
4. 每位执行 Codex 只在自己的 `worktree` 中开发。
5. 负责人验收每条线后，再指导操作者按既定顺序把提交 `cherry-pick` 到集成分支。

### Why This Is Mandatory

- 多个执行 Codex 共用同一工作区会互相污染未提交改动。
- 多个执行 Codex 共用同一分支会让责任边界与回滚边界都失效。
- 当前 4 条执行线虽然边界清晰，但仍存在潜在共享目录，尤其是 `scripts/rdc_analyzer/*`，必须用分支和 `worktree` 再做一层隔离。

## Milestone Gates

### Gate 0：边界冻结

- [x] 三条主线与四大功能点边界已冻结。
- [x] 禁止重复开发项已在总纲写明。
- [x] 每条执行线已有独立 plan。

### Gate 1：Android Capture 入口闭环

- [ ] Android launch 失败不再只弹泛化错误。
- [ ] `JDWPFailure / AndroidLayerConfFailed / AndroidAPKInstallFailed / InjectionFailed` 具备稳定映射。
- [ ] GUI 中存在“查看详细诊断”或等价入口。

### Gate 2：统一快照出口

- [ ] GUI 导出稳定写出 `snapshot.v1.json`。
- [ ] Offline 导出稳定写出 `snapshot.v1.json`。
- [ ] GUI 与 Offline 顶层字段命名一致。

### Gate 3：智能层接入

- [ ] MCP + Skill 只消费 `snapshot.v1`。
- [ ] 字段完整时不发冗余 MCP 请求。
- [ ] 字段缺失时给出明确补数命令与原因。

### Gate 4：总体验收

- [ ] 未引入第二套 schema。
- [ ] 未引入第二套模板系统。
- [ ] MCP / Skill 未复制报告导出能力。
- [ ] 新对话可在 5 分钟内恢复上下文并继续推进。

## Merge Order

1. `AgentD` 完成 M0-C，收束 Android launch 诊断闭环。
2. `AgentB` 落地 GUI `snapshot.v1.json`。
3. `AgentC` 落地 Offline `snapshot.v1.json` 与最小 renderer。
4. `AgentA` 基于稳定 `snapshot.v1` 接入 MCP + Skill。
5. Lead 做跨线验收，确认字段口径、入口边界与禁止项未被破坏。

## Git Merge Procedure

负责人必须指导操作者按以下顺序执行：

1. 进入集成分支工作区。
2. 确认当前分支干净、可接收新提交。
3. 先合入 `AgentD` 的提交。
4. 再合入 `AgentB` 的提交。
5. 再合入 `AgentC` 的提交。
6. 最后合入 `AgentA` 的提交。
7. 每次 `cherry-pick` 后做最小验证，避免把冲突累计到最后一起处理。

## Report Format

每位执行 Codex 的阶段汇报固定为：

- `Done`：本轮已完成项
- `Verification`：跑过的命令、手工验证结论
- `Blockers`：阻塞点与证据
- `Next`：下一步

## Risks / Blockers

- `MainWindow.cpp` 是 Android launch 失败处理的单点入口，若再让 GUI 线改这部分，冲突概率高。
- `snapshot.v1` 仍在落地期，如果 AgentB 和 AgentC 各自发明字段名，会直接破坏 AgentA 的消费链。
- 如果 AgentA 在 `snapshot.v1` 未稳定前扩张高阶 AI 分析，会再次形成“第二套事实层”。
- 如果不提供 handoff，新对话仍会反复追问“Analyzer Report / MCP / Skill 到底谁负责什么”。
- 如果多个执行 Codex 共用同一分支或同一工作区开发，未提交改动和冲突定位会迅速失控。

## Verification / Acceptance

- [ ] 已存在 1 份负责人 handoff 文档，可作为新对话入口。
- [ ] 已存在 4 条执行线的唯一 plan 文档。
- [ ] 每条执行线都能明确回答：负责什么、写哪里、不准碰什么。
- [ ] 合流顺序清晰，无两位 Codex 同时改同一块主逻辑的安排。
- [ ] 负责人能够给出完整的 `git` 协作方案与操作顺序，而不是让操作者自己猜。
- [ ] 执行 Codex 使用独立分支与独立 `worktree`。

## Next Steps

1. 负责人先检查当前仓库 `git status`，判断是否需要冻结共同基线。
2. 负责人给操作者输出分支与 `worktree` 创建方案。
3. 创建负责人 handoff 文档并纳入 `session_archives`。
4. 创建 `AgentD` 的 M0-C 专属 plan。
5. 将本计划与 handoff 一起交给新对话作为恢复入口。
6. 新会话中优先派发 `AgentD`、`AgentB`、`AgentC`、`AgentA` 四条线。

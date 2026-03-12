# AI Agent 入职引导

> **版本**: 1.0.0 | **最后更新**: 2025-01-19
>
> 📋 **用途**: 快速引导新 AI Agent 接入项目并开始任务

---

## 使用说明

将下方模板复制给新 AI，根据需要选择简洁版或完整版。

---

## 📋 简洁版（推荐日常使用）

```markdown
你将接手 RenderDoc RDC Analyzer 项目的一个开发任务。

【必读文档】请按顺序阅读：
1. 项目索引: scripts/rdc_analyzer/.ai/INDEX.md
2. 任务入口: scripts/rdc_analyzer/.ai/TASK_INDEX.md  
3. 开发规范: scripts/rdc_analyzer/.ai/CONVENTIONS.md

【你的任务】
请认领 TASK-XXX: [任务名称]
（替换为具体任务编号和名称）

【工作流程】
1. 阅读上述 3 个文档
2. 找到今日任务文件 (tasks/YYYY-MM-DD.md)
3. 按 CONVENTIONS.md 规范认领任务
4. 开发完成后提交 Git

请先阅读文档，然后告诉我你的理解和计划。
```

---

## 📋 完整版（新手或复杂任务）

```markdown
你将作为 AI Agent 加入 RenderDoc RDC Analyzer 项目。

【项目简介】
这是一个从 RenderDoc .rdc 捕获文件生成离线 HTML 分析报告的工具，
支持 D3D11/D3D12/Vulkan/OpenGL，可在浏览器中查看纹理、事件、Pipeline 等数据。

【项目位置】
d:\Code\git\renderdoc\scripts\rdc_analyzer\

【必读文档 - 按顺序阅读】
1. .ai/INDEX.md        → 了解项目架构、模块、数据流
2. .ai/TASK_INDEX.md   → 找到今日任务文件
3. .ai/CONVENTIONS.md  → 开发规范、Git 提交规则、任务认领协议
4. .ai/tasks/YYYY-MM-DD.md → 今日任务详情（替换日期）

【你的任务】
认领: TASK-XXX [任务名称]
（替换为具体任务）

【关键约束】
- 使用 Agent ID 格式: Agent-YYYYMMDD-HHmmss
- 创建锁文件防止冲突: .ai/locks/TASK-XXX.lock
- 每完成一个功能立即 Git commit
- 遵循 Conventional Commits 格式

【开始前请确认】
1. 你已阅读并理解项目架构
2. 你已查看任务详情和验收标准
3. 你已检查 locks/ 目录无冲突
4. 告诉我你的开发计划

请开始。
```

---

## 📋 极简版（老手 / 小任务）

```markdown
项目: d:\Code\git\renderdoc\scripts\rdc_analyzer\
文档: .ai/INDEX.md, .ai/TASK_INDEX.md, .ai/CONVENTIONS.md
任务: TASK-XXX [任务名称]

阅读文档后认领任务开始开发。
```

---

## 📋 指定多任务版

```markdown
你将接手 RenderDoc RDC Analyzer 项目的开发任务。

【必读文档】
- 项目索引: scripts/rdc_analyzer/.ai/INDEX.md
- 任务入口: scripts/rdc_analyzer/.ai/TASK_INDEX.md  
- 开发规范: scripts/rdc_analyzer/.ai/CONVENTIONS.md

【你的任务清单】按优先级排序：
1. TASK-001: Pipeline 选项卡数据解析 (高优先级)
2. TASK-002: Mesh Info 选项卡数据解析 (高优先级)
3. TASK-003: 资源绑定选项卡数据解析 (中优先级)

【工作流程】
1. 阅读文档，理解项目架构
2. 一次只认领一个任务
3. 完成后再认领下一个

请先阅读文档，选择第一个任务并告诉我你的计划。
```

---

## 📋 代码审查版

```markdown
你将对 RenderDoc RDC Analyzer 项目进行代码审查。

【项目位置】
d:\Code\git\renderdoc\scripts\rdc_analyzer\

【必读文档】
- 项目索引: .ai/INDEX.md
- 开发规范: .ai/CONVENTIONS.md

【审查范围】
- 文件: parse_rdc_xml.py, generate_real_report.py
- 重点: 代码质量、错误处理、性能

【输出要求】
1. 列出发现的问题（按严重程度排序）
2. 提供具体修复建议
3. 如有必要，创建新任务到 TASK_INDEX.md

请开始审查。
```

---

## 变量说明

| 占位符 | 说明 | 示例 |
|--------|------|------|
| `TASK-XXX` | 任务编号 | TASK-001, TASK-002 |
| `[任务名称]` | 任务标题 | Pipeline 选项卡数据解析 |
| `YYYY-MM-DD` | 日期 | 2025-01-19 |

---

## 预期响应

新 AI 阅读文档后应该回复类似：

```
我已阅读项目文档，理解如下：

【项目概述】
RDC Analyzer 从 .rdc 文件生成 HTML 报告，包含纹理、事件、Pipeline 数据。

【当前状态】
- 核心流程已完成 (XML解析 → JSON → HTML)
- 待完善: Pipeline/Mesh/Binding 选项卡数据

【我的任务】
TASK-001: Pipeline 选项卡数据解析

【开发计划】
1. 分析 parse_rdc_xml.py 中 relatedCalls 结构
2. 提取 RSSetViewports, OMSetBlendState 等调用
3. 构建 pipelineState 数据结构
4. 更新 E2E 测试验证

【确认】
- locks/ 目录为空，无冲突
- 我的 Agent ID: Agent-20250119-163000

是否可以开始？
```

---

## 常见问题

### Q: 新 AI 说找不到文件？
**A**: 确认工作目录是 `d:\Code\git\renderdoc`，文档在 `scripts/rdc_analyzer/.ai/` 下。

### Q: 新 AI 不遵守规范？
**A**: 强调必须先阅读 CONVENTIONS.md，这是"宪法"级别的约束文档。

### Q: 多个 AI 同时工作会冲突？
**A**: 通过 locks/ 目录的锁文件机制避免，每个 AI 认领任务前必须检查。

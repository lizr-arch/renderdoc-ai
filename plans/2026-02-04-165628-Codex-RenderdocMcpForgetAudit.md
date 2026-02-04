# RenderDoc MCP Forget-Audit Rules Implementation Plan

> For Claude: REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

Version: v1
Owner: Codex
Last Updated: 2026-02-04

## Plan Metadata
- Version: v1
- Owner: Codex
- Last Updated: 2026-02-04
- Plan File: D:/Code/git/renderdoc/plans/2026-02-04-165628-Codex-RenderdocMcpForgetAudit.md

## Goal
- 在 Agents.md 中加入 MCP 触发规则与任务结束遗忘审计(0%遗漏)强制流程，防止已实现功能被遗忘。

## Architecture
- 仅修改 Agents.md 两个区域：
  1) Context MCP 段落新增触发规则和频率底线。
  2) /do 阶段强制加入遗忘审计步骤与模板。

## Tech Stack
- Markdown 文档编辑(Agents.md)。

## Success Criteria (measurable)
- Agents.md 明确规定 MCP 触发规则与最小调用频率。
- /do 阶段强制遗忘审计(0%遗漏)模板与结论。

## Acceptance Criteria
- 关键功能遗漏率=0% 的审计模板可直接复用。
- 任意完成声明前必须执行遗忘审计(写入规则)。

## Verification Commands
- rg -n 遗忘审计 D:/Code/git/renderdoc/Agents.md (Expected: 命中新增审计章节)
- rg -n MCP 触发规则 D:/Code/git/renderdoc/Agents.md (Expected: 命中新增触发规则章节)

## Evidence
- D:/Code/git/renderdoc/Agents.md 相关行号引用。

## Estimation
- Effort: 0.5h
- Story Points: 1
- Original Estimate: 0.5h

## Risk Register
| Risk | Impact | Likelihood | Mitigation |
|---|---|---|---|
| MCP 调用过频导致上下文膨胀 | Low | Medium | 仅在规定触发点调用，避免无关重复检索 |
| 规则过严导致完成阻塞 | Medium | Low | 仅要求 0% 关键功能遗漏，不限制内容长度 |

---

### Task 1: 扩展 Context MCP 触发规则
- [x] Completed

Files:
- Modify: D:/Code/git/renderdoc/Agents.md:27-61

Step 1: 在工具表后新增 触发规则 小节
- 新增标题：### MCP 触发规则（防遗忘强制）
- 内容要求：
  - 会话开始必须调用 get_project_index。
  - 进入 /spec 或 /plan 前，至少一次 search_docs(用 1-3 个任务关键词)。
  - 涉及 既有功能/脚本/规范/结论 时，必须 search_docs 或 read_doc 并给出证据路径。
  - 连续 10+ 轮未调用 mcp__renderdoc_context 且仍在 RenderDoc 任务中，强制一次 search_docs。
  - 无检索结果时必须标注 假设(待验证)。

Step 2: 增加频率底线
- 明确 每次会话至少 1 次 get_project_index + 1 次 search_docs。

---

### Task 2: 在 /do 阶段加入遗忘审计
- [x] Completed

Files:
- Modify: D:/Code/git/renderdoc/Agents.md:124-134

Step 1: 在 Mandatory Actions 列表新增步骤
- 新增第 8 条：完成声明前必须执行 遗忘审计(0%遗漏)。

Step 2: 在 /do 段落后新增审计模板
- 新增小节标题：### 任务结束遗忘审计（强制，0%遗漏）
- 模板内容：
  - Key Functions Checklist:
  - Evidence Map: 必须引用文档/源码路径或 MCP 检索证据
  - Omission Rate: 0%
  - Verdict: PASS/FAIL
  - 若非 0%：禁止宣称完成，必须回到检索或补充

---

## Next Steps
- 等待 /do 执行实际修改。

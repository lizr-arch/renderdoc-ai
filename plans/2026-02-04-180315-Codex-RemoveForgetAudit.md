# Remove Forget-Audit Rules Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Version:** v1
**Owner:** Codex
**Last Updated:** 2026-02-04

## Plan Metadata
- Version: v1
- Owner: Codex
- Last Updated: 2026-02-04
- Plan File: D:/Code/git/renderdoc/plans/2026-02-04-180315-Codex-RemoveForgetAudit.md

## Goal
- 移除 /do 阶段“遗忘审计(0%遗漏)”强制门槛，改为任务完成后基于聊天记录的非阻塞遗忘分析总结。

## Architecture
- 仅修改 `Agents.md`：删除遗忘审计强制步骤与模板，新增“任务后遗忘分析（非阻塞）”说明。

## Tech Stack
- Markdown 文档编辑（`Agents.md`）。

## Success Criteria (measurable)
- `Agents.md` 不再包含“遗忘审计(0%遗漏)”强制条款。
- `Agents.md` 明确“任务完成后由助手基于聊天记录做遗忘分析总结（非阻塞）”。

## Acceptance Criteria
- /do Mandatory Actions 列表中不再出现遗忘审计条目。
- “任务结束遗忘审计（强制）”小节被移除。
- 新增“任务后遗忘分析（非阻塞）”小节，说明其不影响完成判定。

## Verification Commands
- `rg -n 遗忘审计 D:/Code/git/renderdoc/Agents.md` (Expected: 不含强制审计条目)
- `rg -n 任务后遗忘分析 D:/Code/git/renderdoc/Agents.md` (Expected: 命中新小节)

## Evidence
- `D:/Code/git/renderdoc/Agents.md` 相关行号引用。

## Estimation
- Effort: 0.5h
- Story Points: 1
- Original Estimate: 0.5h

## Risk Register
| Risk | Impact | Likelihood | Mitigation |
|---|---|---|---|
| 遗忘分析变为非阻塞导致遗漏未被立即纠正 | Medium | Low | 在完成后总结中明确指出潜在遗漏与证据缺口 |
| 文档规则变更影响已有执行习惯 | Low | Medium | 仅移除强制门槛，保留事后总结提醒 |

---

### Task 1: 删除遗忘审计强制项与模板
- [x] Completed

**Files:**
- Modify: `D:/Code/git/renderdoc/Agents.md:141-196`

**Step 1: 移除 /do Mandatory Actions 第 8 条**
- 删除“完成声明前必须执行 遗忘审计(0%遗漏)”。

**Step 2: 移除遗忘审计模板小节**
- 删除“### 任务结束遗忘审计（强制，0%遗漏）”及其要点。

---

### Task 2: 新增非阻塞遗忘分析说明
- [x] Completed

**Files:**
- Modify: `D:/Code/git/renderdoc/Agents.md:190-205`

**Step 1: 添加新小节**
- 标题：`### 任务后遗忘分析（非阻塞）`
- 内容要点：
  - 任务完成后由助手基于聊天记录/证据回顾关键功能覆盖情况。
  - 仅用于总结与提示，不作为完成门槛。
  - 若发现遗漏，建议在后续轮次补充。

---

## Game Dev: Memory & Resource Budget (Leak Checks)
- 不涉及（纯文档规则修改）。

## Game Dev: Asset Pipeline
- 不涉及（纯文档规则修改）。

## Game Dev: Crash Repro + Dumps/Symbols
- 不涉及（纯文档规则修改）。

---

## Next Steps
- 等待 /do 执行实际修改。

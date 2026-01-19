# 多 AI 协同开发规范

> **版本**: 1.1.0 | **最后更新**: 2025-01-19
>
> ⚠️ **强制遵守**: 所有参与开发的 AI Agent 必须遵守本规范

---

## 0. Agent ID 规则

每个 AI Agent 必须使用唯一标识符，格式：

```
Agent-YYYYMMDD-HHmmss
```

**示例**: `Agent-20250119-153000`

**生成规则**:
- 使用会话开始时的时间戳（精确到秒）
- 时区: 本地时间（北京时间 UTC+8）
- 此 ID 用于锁文件、CHANGELOG、任务认领等所有场景

**如何获取当前时间**:
```python
from datetime import datetime
agent_id = f"Agent-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
```

---

## 1. 会话启动协议

每个 AI 会话开始时，**必须**执行以下步骤：

```
┌─────────────────────────────────────────────────┐
│ 1. 读取 .ai/INDEX.md      → 了解项目架构         │
│ 2. 读取 .ai/TASKS.md      → 查看任务状态         │
│ 3. 检查 .ai/locks/        → 确认哪些任务被锁定   │
│ 4. 向用户确认             → 明确本次会话目标     │
└─────────────────────────────────────────────────┘
```

**示例开场白**：
```
我已阅读项目索引和任务看板。当前状态：
- 待认领任务: 6 个
- 进行中任务: 0 个

请问您希望我处理哪个任务？或者有新的需求？
```

---

## 2. 任务认领协议

### 2.1 认领前检查

```bash
# 检查锁文件是否存在
ls .ai/locks/TASK-xxx.lock
```

- ✅ 锁文件不存在 → 可以认领
- ❌ 锁文件存在且未过期 → 不可认领，选择其他任务
- ⚠️ 锁文件存在但已过期（>2小时）→ 可以接管，需在 TASKS.md 中说明

### 2.2 认领步骤

1. **创建锁文件**:
```json
// .ai/locks/TASK-001.lock
{
  "task_id": "TASK-001",
  "claimed_by": "Agent-A",
  "session_id": "会话标识或时间戳",
  "claimed_at": "2025-01-19T15:30:00Z",
  "expires_at": "2025-01-19T17:30:00Z"
}
```

2. **更新 TASKS.md**:
   - 将任务从"待认领"移到"进行中"
   - 填写认领者、时间、预计完成时间

3. **Git 提交**:
```bash
git add .ai/locks/TASK-001.lock .ai/TASKS.md
git commit -m "chore(ai): claim TASK-001 - Pipeline 选项卡数据解析"
```

---

## 3. 开发过程协议

### 3.1 代码修改规则

| 规则 | 说明 |
|------|------|
| 单一职责 | 每次只修改与当前任务相关的文件 |
| 增量提交 | 每完成一个小功能点立即 commit |
| 保持兼容 | 不破坏现有功能 |
| 添加注释 | 复杂逻辑必须添加注释 |

### 3.2 代码风格

**Python**:
- 缩进: 4 空格
- 编码: UTF-8
- 行宽: 100 字符
- 命名: snake_case (函数/变量), PascalCase (类)

**提交信息** (Conventional Commits):
```
<type>(<scope>): <简短描述>

<详细说明>

<关联任务>
```

类型:
- `feat`: 新功能
- `fix`: 修复 Bug
- `refactor`: 重构
- `docs`: 文档
- `chore`: 构建/工具

**示例**:
```
feat(parser): 添加 Pipeline State 解析

- 解析 RSSetViewports 获取 Viewport 数据
- 解析 OMSetBlendState 获取混合状态
- 支持 D3D11 和 Vulkan 两种 API

Task: TASK-001
```

### 3.3 进度更新

开发过程中，每完成一个验收标准，更新 TASKS.md:

```markdown
### TASK-001: Pipeline 选项卡数据解析
- **进度**: 
  - [x] 分析 relatedCalls 结构
  - [x] 实现 viewport 解析
  - [ ] 实现 blendState 解析  ← 当前进度
  - [ ] 测试 D3D11
```

---

## 4. 任务完成协议

### 4.1 完成检查清单

- [ ] 所有验收标准已满足
- [ ] 代码已提交到 Git
- [ ] 运行 E2E 测试通过
- [ ] 更新相关文档

### 4.2 完成步骤

1. **最终代码提交**:
```bash
git add <修改的文件>
git commit -m "feat(xxx): 完成 TASK-001"
```

2. **更新 TASKS.md**:
   - 将任务移到"已完成"区域
   - 填写完成时间、产出、测试结果

3. **更新 CHANGELOG.md**:
```markdown
## 2025-01-19

### Agent-A (会话 xxx)
- **15:45** TASK-001: 完成 Pipeline 选项卡数据解析
  - 修改: `parse_rdc_xml.py` (+45 行), `generate_real_report.py` (+20 行)
  - Commit: `feat(parser): add pipeline state extraction`
```

4. **删除锁文件**:
```bash
rm .ai/locks/TASK-001.lock
git add -A .ai/
git commit -m "chore(ai): complete TASK-001"
```

---

## 5. 冲突处理协议

### 5.1 文件冲突

如果发现要修改的文件被其他任务锁定：

1. **停止修改**
2. **检查锁文件** 确认是哪个任务
3. **评估依赖** 是否需要等待
4. **通知用户** 说明冲突情况

### 5.2 任务依赖

如果任务有依赖关系：

```markdown
### TASK-004: Pipeline State 脚本集成
- **依赖**: TASK-001
```

必须等待 TASK-001 完成后才能开始 TASK-004。

### 5.3 接管过期任务

锁文件超过 2 小时视为过期，可以接管：

1. 删除旧锁文件
2. 创建新锁文件
3. 在 TASKS.md 中说明接管原因

---

## 6. 通信协议

### 6.1 进度通知

通过更新 Git 仓库中的文档进行异步通知：

- `TASKS.md` - 任务状态变更
- `CHANGELOG.md` - 完成记录
- `locks/` - 任务锁定状态

### 6.2 阻塞通知

如果遇到阻塞问题，在 TASKS.md 中记录：

```markdown
### TASK-001: Pipeline 选项卡数据解析
- **状态**: 🔴 阻塞
- **阻塞原因**: 需要确认 Vulkan vkCmdSetViewport 参数格式
- **阻塞时间**: 2025-01-19 16:00
- **需要**: 用户提供 Vulkan 捕获样本
```

---

## 7. 质量标准

### 7.1 代码质量

- 无语法错误 (`py -3 -m py_compile <file>`)
- 无明显逻辑错误
- 处理边界情况 (空数据、缺失字段)

### 7.2 测试要求

每个功能完成后必须验证：

```bash
# 运行端到端测试
cd scripts/rdc_analyzer
py -3 test_e2e_real_data.py "测试文件.rdc" output/test
```

### 7.3 文档要求

- 更新 INDEX.md 中的模块状态
- 新增功能需添加使用说明
- 复杂逻辑需添加代码注释

---

## 8. 禁止行为

| 禁止行为 | 原因 |
|----------|------|
| ❌ 不读取 INDEX.md 直接开发 | 可能重复实现或破坏现有功能 |
| ❌ 不检查锁文件直接认领 | 导致多人同时修改同一文件 |
| ❌ 修改非任务相关文件 | 可能与其他任务冲突 |
| ❌ 不提交 Git 就完成任务 | 其他 Agent 无法看到进度 |
| ❌ 删除其他 Agent 的锁文件 | 除非明确过期 |
| ❌ 批量完成多个任务 | 难以追踪和回滚 |

---

## 9. 任务文件结构

### 9.1 目录结构

```
.ai/
├── INDEX.md              # 项目索引（AI 必读）
├── TASK_INDEX.md         # 📋 任务总索引（入口）
├── CONVENTIONS.md        # 开发规范（本文件）
├── CHANGELOG.md          # 变更日志
│
├── tasks/                # 每日任务文件
│   ├── TEMPLATE.md       # 任务模板
│   ├── 2025-01-19.md     # 按日期存放
│   └── ...
│
├── archive/              # 历史归档（按月）
│   └── 2025-01.md
│
└── locks/                # 任务锁文件
    └── TASK-xxx.lock
```

### 9.2 任务查找流程

```
1. 打开 TASK_INDEX.md
      ↓
2. 找到"当前活跃"表格
      ↓
3. 点击对应日期的任务文件链接
      ↓
4. 在每日任务文件中认领任务
```

### 9.3 新一天的任务创建

当开始新的一天工作时：
1. 复制 `tasks/TEMPLATE.md` 为 `tasks/YYYY-MM-DD.md`
2. 更新 `TASK_INDEX.md` 的"当前活跃"表格
3. Git 提交: `chore(ai): create task file for YYYY-MM-DD`

### 9.4 月末归档

每月结束时：
1. 将已完成任务汇总到 `archive/YYYY-MM.md`
2. 更新 `TASK_INDEX.md` 的统计数据
3. 可以删除或保留每日任务文件

---

## 10. 快速参考卡

```
┌─────────────────────────────────────────────────────────┐
│                    AI 协同开发速查                       │
├─────────────────────────────────────────────────────────┤
│ Agent ID:                                               │
│   格式: Agent-YYYYMMDD-HHmmss                           │
│   示例: Agent-20250119-153000                           │
├─────────────────────────────────────────────────────────┤
│ 开始会话:                                               │
│   1. 读 INDEX.md                                        │
│   2. 读 TASK_INDEX.md → 找到今日任务文件                │
│   3. 检查 locks/ 目录                                   │
│   4. 向用户确认任务                                     │
├─────────────────────────────────────────────────────────┤
│ 认领任务:                                               │
│   1. 创建 locks/TASK-xxx.lock                           │
│   2. 更新 tasks/YYYY-MM-DD.md                           │
│   3. git commit "chore(ai): claim TASK-xxx"             │
├─────────────────────────────────────────────────────────┤
│ 完成任务:                                               │
│   1. git commit "feat(xxx): 功能描述"                   │
│   2. 更新 tasks/YYYY-MM-DD.md + CHANGELOG.md            │
│   3. 更新 TASK_INDEX.md 统计                            │
│   4. 删除 locks/TASK-xxx.lock                           │
│   5. git commit "chore(ai): complete TASK-xxx"          │
├─────────────────────────────────────────────────────────┤
│ 遇到冲突:                                               │
│   1. 停止修改                                           │
│   2. 检查锁文件                                         │
│   3. 通知用户                                           │
└─────────────────────────────────────────────────────────┘
```

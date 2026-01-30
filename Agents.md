# Codex Project Configuration: RenderDoc (Graphics Debugger / C++)

> **Version**: 1.0.0 | **Updated**: 2025-01-16 | **For**: Codex Executor
> 
> **项目简介**: RenderDoc 是一个开源的帧捕获图形调试器，支持 Vulkan、D3D11、D3D12、OpenGL 和 OpenGL ES。
>
> **文档目标**: 本配置专为 **RDC 文件分析 MCP/Skill 开发** 优化，重点关注：
> - 理解 `.rdc` 文件的二进制结构和 Section 布局
> - 掌握 Replay 机制和各图形 API 驱动的解析入口
> - 使用 Python API 实现自动化分析脚本

## 索引文档
- 项目索引与贡献指南：`docs/CONTRIBUTING.md`
- 编译说明：`docs/CONTRIBUTING/Compiling.md`
- 开发指南：`docs/CONTRIBUTING/Developing-Change.md`
- 代码结构说明：`docs/CONTRIBUTING/Code-Explanation.md`
- **阅读总览（优先阅读/持续更新）**：`docs/analysis/codex_rdc_analyzer/WORK_SUMMARY_2025-01-21.md`
  - 说明：该文件已改为“索引页”，指向 5 份主题文档（架构/路线/Schema/验证/路线图）。

## 0. COMMANDS (Executable Quick List)
> 以下命令仅记录，不自动执行；执行前需确认权限与路径。构建类命令需用户授权。更多约束见下方 "Shell Protocol / 命令执行权限"。

### Build (需用户授权)
```powershell
# Windows (Visual Studio)
msbuild renderdoc.sln /p:Configuration=Development /p:Platform=x64

# Linux/Mac (CMake)
cmake -DCMAKE_BUILD_TYPE=Debug -Bbuild -H.
make -C build

# Android
cmake -DBUILD_ANDROID=On -DANDROID_ABI=armeabi-v7a -Bbuild-android -H.
make -C build-android
```

### Search (PowerShell)
- Text: `rg -n "pattern" renderdoc/`
- Syntax (sg if available): `sg -g "*.cpp" 'class_spec(name == "ReplayController")'`

## 0.1 AGENT ROLES
角色文件：`~/.codex/prompts/`，调用：`/prompts:<name>`（新建后需重启生效）
- `role-docs` / `role-test` / `role-lint`

## 1. CORE WORKFLOW PROTOCOL (The 3-Step Cycle)

**Stage-Gated**: 只有收到 `/spec` `/plan` `/do` 明确指令才进入对应阶段；需求变更→回退上一阶段确认。

### Phase 1: /spec (Specification & Context)
- **Goal**: Understand requirement, map codebase.
- **Permissions**: READ-ONLY.
- **Mandatory Actions**:
  1. Search (rg/sg) 定位相关代码。
  2. 阅读关键文件，理解数据结构和调用关系。
  3. 总结需求和发现。

### Phase 2: /plan (Architecture & Strategy)
- **Goal**: Design solution.
- **Permissions**: READ-ONLY.
- **Mandatory Actions**:
  1. File List (精确到行号范围).
  2. Pseudo-code.
  3. Impact Analysis.
  4. Approval: WAIT for user.
  5. 产物：`plans/YYYY-MM-DD-HHmmss-<AgentID>-<title>.md`（时间精确到秒 + Agent标识），含任务 checkbox、风险/问题；/do 期间在同一文件勾选并追加问题，禁止另起副本或修订历史。
  6. 如需生成 XML 任务文档：`.codex/tasks/<timestamp>-<AgentID>-<title>.xml`，与 plan.md 对齐，覆盖式更新。
  7. 推荐模板（放入 plan.md 开头）：Scope/Assumptions、Build/Test/Lint Quick Guide（**命令仅记录不执行**）、Task Checklist（checkbox）、Risks/Blockers、Decisions、Verification/Acceptance（Definition of Done）、Next Steps。
- **[增强] 计划粒度要求**:
  - **2-5分钟粒度**：每个步骤应能在 2-5 分钟内完成
  - **完整代码**：计划中含完整代码片段，不写"添加验证逻辑"这种模糊描述
  - **精确命令**：测试/验证命令写全，含预期输出（**由用户手动执行**）
  - **TDD 步骤模板**：写失败测试 → 验证失败 → 写最小实现 → 验证通过 → 提交
- **[多 Agent 并行] 文件命名防冲突**:
  - 格式：`YYYY-MM-DD-HHmmss-<AgentID>-<title>.md`
  - 示例：`2025-12-24-143052-Agent01-ExportFeature.md`
  - 每个 Agent 必须使用唯一标识（如 Agent01/Agent02 或会话ID前6位）

#### /plan 50字模板（速用）
参见：`docs/templates/plan-template.md`（Scope/Steps/Impact/Risks/Verification）

### Phase 3: /do (Implementation)
- **Goal**: Apply changes.
- **Permissions**: WRITE ALLOWED (代码文件), **可执行验证命令** (测试/lint).
- **Mandatory Actions**:
  1. Incremental Edits.
  2. Encoding Check (GBK vs UTF-8).
  3. 同步更新 plan.md：勾选完成项，记录阻塞/偏差。
  4. 若需求或范围变化：立即暂停 /do，回退 /plan 更新同一 plan.md，获批后再继续。
  5. 自检：按 plan.md 的 Definition of Done 勾选，**自主运行验证命令确认结果**。
  6. 遇阻流程：同一问题尝试不超过 3 次；记录已尝试方法/错误/推测原因/备选方案到 plan.md 的 Risks/Blockers，再决定等待指示或调整方案。
  7. **Git 自动提交**：每完成一个独立功能/任务后立即提交到 Git。

- **[强制] Git 自动提交规则**:
  - **触发时机**：完成一个可验证的功能/修复/任务后
  - **提交格式**：遵循 Conventional Commits
    ```
    <type>(<scope>): <简短描述>
    
    - 详细说明修改内容
    - 涉及的文件列表
    ```
  - **类型 (type)**:
    | 类型 | 说明 |
    |------|------|
    | `feat` | 新功能 |
    | `fix` | 修复 Bug |
    | `docs` | 文档更新 |
    | `refactor` | 重构（无功能变化） |
    | `style` | 代码格式化 |
    | `chore` | 构建/工具变更 |
  - **示例**:
    ```bash
    git add scripts/rdc_analyzer/extract_pipeline.py
    git commit -m "feat(rdc-analyzer): 添加 Pipeline State 提取功能

    - 新增 extract_pipeline.py 脚本
    - 支持从 RDC 提取 Shader、Viewport、Blend State
    - 输出 JSON 格式供 HTML 报告使用"
    ```
  - **禁止行为**:
    - ❌ 累积多个任务后批量提交
    - ❌ 使用模糊的提交信息（如 "update", "fix"）
    - ❌ 忘记提交就开始下一个任务

- **[增强] 批次执行与汇报**:
  - **默认批次**：每完成 3 个任务进行总结是否存在疑问、不确定，如果存在就汇报进度，等待反馈
  - **汇报格式**：已完成项 + 验证结果 + "Ready for feedback."
  - **遇阻立停**：不猜测，立即汇报并请求帮助
- **[命令执行权限]**:
  - ✅ **允许执行（验证类，只读）**:
    - 测试命令：`pytest`, `npm test`, `cargo test`, `dotnet test`, `go test` 等
    - Lint/Format 检查：`eslint`, `prettier --check`, `ruff check`, `mypy`, `clang-tidy` 等
    - 类型检查：`tsc --noEmit`, `pyright` 等
  - ⚠️ **需用户授权执行（构建类）**:
    - 构建命令：`msbuild`, `cmake --build`, `make` 等
    - RenderDoc 构建：`msbuild renderdoc.sln`, `cmake -Bbuild && make -C build`
    - 首次执行前需用户确认，授权后本会话内可重复执行
  - ❌ **禁止执行**:
    - 部署/发布：`npm publish`, `docker push`, `deploy` 等
    - 破坏性 git：`git push --force`, `git reset --hard`, `git clean -fd`
    - 依赖变更：`npm install`, `pip install`（除非用户显式授权）

### $autonomous-skill 模式

当 `$autonomous-skill` 技能激活时，`$spec-plan-do` 失效，**Stage-Gated**无需用户确认，AI 内部静默遵循 spec→plan→do 三阶段方法论。

---

## 1.1 IRON LAWS (铁律)

以下原则在源码分析过程中**强制执行**。

### 铁律 1: 系统分析 (Systematic Analysis)
```
无证据支持，不下结论
```
- **先搜索后断言**：任何关于代码行为的结论必须基于源码证据
- **标注不确定性**：无法确认时使用「**假设（待验证）**」标注
- **3 次规则**：同一问题搜索 3 次未找到 → 停止猜测，向用户说明缺失信息

### 铁律 2: 验证优先 (Verification First)
```
无验证，不宣称完成
```
- 分析结论需引用具体文件和行号
- 代码路径推断需追踪到实际函数调用
- 禁止模糊宣称（"可能是..."、"应该是..."）

### 铁律快速参考卡
```
┌─────────────────────────────────────────────────┐
│ ANALYZE: 先搜索源码，再下结论                    │
│ VERIFY:  引用文件:行号作为证据                   │
│ UNCERTAIN: 标注「假设」，说明缺失信息            │
│ 3-STRIKE: 搜索3次未果 → 停止，请求帮助           │
└─────────────────────────────────────────────────┘
```

---

## 2. CRITICAL SYSTEM INSTRUCTIONS

### Safety & Permissions
- **DESTRUCTIVE COMMANDS**: ASK permission for git reset, clean, rm -rf.
- **Protected Directories**: 禁止修改 `renderdoc/3rdparty/`（第三方库）、`build*/`（构建输出）目录。
- **Dependencies**: 禁止自动安装/升级依赖；如需新增包由用户手动执行或显式授权。
- **Team/Personal Guides**: 可选 `.codex/agents_team.md`（团队级偏好）与 `.codex/agents.md`（个人偏好）；不得弱化本文件的安全/禁编译等硬约束。

### Shell Protocol
- **Windows**: PowerShell 7 (pwsh) 或 cmd.exe。
- **Everything CLI (es.exe)**: `D:\ES-1.1.0.30.x64\es.exe`（已加入 PATH 时可直接 `es.exe`），用于文件名/路径快速搜索（优先于 `rg --files`）。
- **Linux/WSL**: CMake + make 构建；Android 构建推荐在 bash shell (cygwin/msys2/WSL) 中执行。
- **Command Transparency**: 运行终端前在对话声明 intent + 命令，再执行。

#### Codex/Pwsh 已知现象（避免“卡住”）
- 在本仓库的 Codex CLI 执行环境里，`pwsh -Command` 的 **PowerShell 变量赋值**（如 `$x=...`）可能被执行器错误解析，出现 `=Get-Date` / `=Join-Path` 之类报错，并导致命令等待输入，看起来像“卡住”。
- **建议规避**：优先用 `apply_patch` 改文件；需要脚本时优先 `python -c ...`；`pwsh` 尽量使用**无 `$var` 的单条命令** + 绝对路径。

#### Python 版本
- **强制 `py -3`**：本机 `python` 默认指向 2.7.18，缺少 `pathlib` 等标准库
- ✅ 正确：`py -3 scripts/sync_plans_index.py`
- ❌ 错误：`python scripts/sync_plans_index.py`

#### Python 脚本执行
- 简单脚本（单行、无嵌套引号）：`py -3 -c '...'`
- 复杂脚本（多行 + 引号/中文，或超 3 行）：写 `scripts/_tmp_<用途>.py` → 执行；`/end` 时统一清理 `_tmp_*.py`
- **一次性原则**：临时脚本应一次性写对，同一脚本反复创建-运行超过 2 次 → 停止，换用 `replace_in_file` 或其他工具
- **禁止即删**：临时脚本执行后**不得立即删除**，保留至 `/end` 统一清理（便于排查问题和复用）

#### 会话存档
- 会话级恢复包统一放在：`docs/debug/session_archives/<YYYY-MM-DD>-<Topic>/`

#### 文件操作效率规范

> **原则**: 搜索→读取→编辑 三阶段，每阶段尽量一次完成，避免重复操作

##### 1. 搜索阶段

**工具优先级**
| 场景 | 首选 | 备选 |
|------|------|------|
| 文件/路径搜索 | `es.exe` (Everything) | `fd` / `rg --files` |
| 文本内容搜索 | `rg -n <pattern>` | `sg`（需语法细节时） |
| 结构/AST 搜索 | `sg` | LSP/ctags |
| 排除二进制/生成文件 | `rg -g !*.png -g !Binaries/**` | allow/deny 列表 |

**搜索效率规则**
1. **Merge when scanning**: For log/error scanning or "find any of these" tasks, use merged regex: `rg -n "(Error|Exception|Traceback)"`
2. **Keep separate when pinpointing**: For precise location of a specific symbol/string, single-keyword search is acceptable
3. **Avoid redundant searches**: Do not search the same keyword twice in unedited files; cache and reuse results
4. **Locate then dive**: First search to build "file:line" map, then read specific ranges as needed

##### 2. 读取阶段

**阈值定义**: 文件 > 1000 行视为"大文件"

**大文件读取流程**
1. 先用 `sg -n pattern <file>` 或 `rg -n` 获取目标行号
2. 按行号范围分块读取（单块 300-400 行）：`Get-Content <file> -First 400` / `-Tail 400`
3. **一次性原则**: 预估所需范围，尽量一次读取足够内容
4. **上限**: 同一文件分段读取不超过 3 次（超过说明策略有问题，应先定位再读取）

##### 3. 编辑阶段

**工具选择**
| 文件行数 | 推荐工具 | 禁止行为 |
|----------|----------|----------|
| ≤300行 | `edit_file` 全文替换 | - |
| >300行 | `replace_in_file` 精确 SEARCH/REPLACE | 禁止 `edit_file` 全文覆盖 |
| 含特殊缩进（Tab/深层嵌套） | 写临时 Python 脚本操作 | 禁止内联 PowerShell 多行 |

**强制流程**（>300行文件）
1. **编辑前**：读取目标区域，确认缩进风格（Tab 数量 / 空格数）
2. **编辑时**：使用 `replace_in_file` 的 SEARCH/REPLACE 块，保留原始缩进
3. **编辑后**：执行语法验证（Python: `py -3 -m py_compile <file>`）
4. **编辑后禁重读**: 信任工具成功，禁止重读验证（除非验证失败）
5. **失败处理**：语法错误 → 不叠加修复 → 回滚重来，累计 3 次后停止请求帮助

#### Python 文件缩进规范
- **本项目 Python 缩进**：使用 **4 空格**（遵循 PEP 8）
- **编辑前确认**：修改前检查目标行的空格层级
- **生成代码对齐**：新增代码的缩进必须与上下文空格数量完全一致
- ❌ 反例：原文件 4 空格缩进，生成代码变成 Tab 或 2 空格
- ✅ 正例：读取后确认 `indent=4`，生成代码保持 4 空格

---

## 3. ENCODING STRATEGY
- **Rule 1**: Read as UTF-8 by default; only run chardet detection on UnicodeDecodeError.
- **Rule 2**: Preserve original encoding when editing.
- **Rule 3**: New files = UTF-8 without BOM.

#### Encoding Detection (On Error Only)
```powershell
# Run ONLY when UnicodeDecodeError occurs
py -3 -c "import chardet; print(chardet.detect(open(r'<file>','rb').read())['encoding'])"
```
- **Fallback** (if chardet unavailable): Try BOM detection, then `gb18030` → `gbk` in sequence.
- **Forbidden**: Exhaustively trying multiple encodings and printing each failure (wastes tokens).

---

## 4. CODING STANDARD: RenderDoc C++ Style Guide

> **权威文档**: `docs/CONTRIBUTING/Developing-Change.md`
> 
> **格式化工具**: 项目根目录 `.clang-format`（Chromium 风格），提交前必须执行 `clang-format`。

### 4.1 核心原则
1. **clang-format 强制**: 所有 C++ 代码必须通过 `.clang-format` 格式化。
2. **显式优于隐式**: 优先使用显式类型声明，限制 `auto` 使用。
3. **一致性优先**: 遵循现有代码风格，即使与个人偏好不同。

### 4.2 缩进与格式
| 规则 | 要求 |
|------|------|
| 缩进 | **2 空格**（禁止 Tab） |
| 行宽 | 100 字符 |
| 指针/引用 | `int *ptr`（星号靠右） |
| 大括号 | Allman 风格（新行） |

```cpp
// 正确示例
void MyFunction()
{
  int *ptr = NULL;
  if(condition)
  {
    DoSomething();
  }
}
```

### 4.3 类型与容器
| 禁止使用 | 替代方案 | 说明 |
|----------|----------|------|
| `nullptr` | `NULL` | 项目强制要求 |
| `std::vector` | `rdcarray<T>` | 自定义容器 |
| `std::string` | `rdcstr` | 自定义字符串 |
| `std::pair` | `rdcpair<A,B>` | 自定义 pair |
| `auto` | 显式类型 | 仅在类型明显时使用 |

### 4.4 命名规范
| 元素 | 风格 | 示例 |
|------|------|------|
| 类/结构体 | PascalCase | `ReplayController` |
| 函数 | PascalCase | `GetTexture()` |
| 成员变量 | `m_` 前缀 + camelCase | `m_textureId` |
| 局部变量 | camelCase | `localVar` |
| 常量/枚举值 | PascalCase | `MaxCount` |

### 4.5 文件组织
- **驱动代码**: `renderdoc/driver/{api}/` (d3d11, d3d12, gl, vulkan)
- **核心代码**: `renderdoc/core/`
- **Qt UI**: `qrenderdoc/`
- **Python 模块**: `qrenderdoc/Code/Interface/`

### 4.6 跨平台注意事项
- 使用 `RDOC_WIN32`, `RDOC_LINUX`, `RDOC_APPLE` 等宏进行平台判断。
- 路径分隔符使用 `/`（内部统一处理）。
- 避免使用平台特定 API，优先使用 `renderdoc/os/` 抽象层。

---

## 5. CODEX AGENT ROLE

### 5.1 Task Format
- Receive: Background, Requirements, Files, Constraints.

### 5.2 Feedback Format
- Return: Modified Files, Key Changes, Verification Status.

### 5.2.1 Response Design
- **Source**: `docs/AI_Response_Design_Methodology.md`（问题分析模式 + 三秒法则 + 信息密度金字塔）
- **Goal**: CLI 可读、先结论后细节、表格做摘要
- **Rule**: 遵守该文档的结构与格式规范

### 5.3 Prohibitions
- NO Auto Compile.
- NO Deleting files without approval.
- 分析笔记统一置于 `docs/analysis/`，禁止在仓库根散落临时文件。

## 6. 本地工程路径（参考）
- 当前仓库：`d:\Code\git\renderdoc`（Windows）/ `/mnt/d/Code/git/renderdoc`（WSL）
- 构建输出：`build/`（禁止修改）
- 第三方库：`renderdoc/3rdparty/`（禁止修改）

---

## 7. RDC 文件格式分析

> **目标**：理解 `.rdc` 文件结构，为构建 MCP/Skill 提供解析入口。

### 7.1 核心类与文件

| 类/文件 | 路径 | 职责 |
|---------|------|------|
| `RDCFile` | `renderdoc/serialise/rdcfile.h/.cpp` | RDC 文件读写核心类 |
| `CaptureFile` | `renderdoc/replay/capture_file.cpp` | 高层封装，实现 `ICaptureFile` 接口 |
| `SectionType` | `renderdoc/api/replay/replay_enums.h` | 定义 RDC 文件的 Section 类型枚举 |
| `StreamReader/Writer` | `renderdoc/serialise/streamio.h` | 二进制流读写 |

### 7.2 RDC 文件结构

```
┌─────────────────────────────────────┐
│ File Header (magic, version)        │
├─────────────────────────────────────┤
│ Section 0: FrameCapture (主数据)     │
│   - Chunks (序列化的 API 调用)       │
│   - 资源数据 (纹理、缓冲区)          │
├─────────────────────────────────────┤
│ Section 1: ResolveDatabase          │
├─────────────────────────────────────┤
│ Section N: ExtendedThumbnail / etc  │
└─────────────────────────────────────┘
```

### 7.3 关键入口点

**打开 RDC 文件**：
```cpp
// renderdoc/serialise/rdcfile.cpp:236
void RDCFile::Open(const rdcstr &path)
```

**读取初始化数据**：
```cpp
// renderdoc/replay/replay_controller.cpp:2167
RDResult ReplayController::CreateDevice(RDCFile *rdc, const ReplayOptions &opts)
```

**各驱动的读取入口**：
- Vulkan: `renderdoc/driver/vulkan/vk_replay.cpp:199` → `VulkanReplay::ReadLogInitialisation`
- D3D12: `renderdoc/driver/d3d12/d3d12_replay.cpp:275` → `D3D12Replay::ReadLogInitialisation`
- D3D11: `renderdoc/driver/d3d11/d3d11_replay.cpp:1694` → `D3D11Replay::ReadLogInitialisation`
- OpenGL: `renderdoc/driver/gl/gl_replay.cpp:114` → `GLReplay::ReadLogInitialisation`

---

## 8. Python API 参考

> **目标**：使用 Python 脚本自动化分析 RDC 文件。

### 8.1 模块入口

| 模块 | 说明 |
|------|------|
| `renderdoc` | 核心模块，SWIG 生成 |
| `qrenderdoc` | Qt UI 扩展模块 |

**SWIG 接口定义**：
- `qrenderdoc/Code/pyrenderdoc/renderdoc.i` — 核心 API 绑定
- `qrenderdoc/Code/pyrenderdoc/qrenderdoc.i` — UI 扩展绑定

### 8.2 核心类

| 类 | 职责 |
|----|------|
| `renderdoc.CaptureFile` | 打开/保存 RDC 文件 |
| `renderdoc.ReplayController` | 回放控制，访问捕获数据 |
| `renderdoc.SDFile` | 结构化数据文件 |
| `renderdoc.ActionDescription` | 描述单个绘制/调度调用 |
| `renderdoc.TextureDescription` | 纹理元数据 |
| `renderdoc.BufferDescription` | 缓冲区元数据 |

### 8.3 常用操作示例

```python
import renderdoc as rd

# 打开 RDC 文件
cap = rd.OpenCaptureFile()
result = cap.OpenFile("capture.rdc", "", None)

# 获取回放控制器
controller = cap.OpenCapture(rd.ReplayOptions(), None)

# 遍历所有绘制调用
actions = controller.GetRootActions()
for action in actions:
    print(f"EID {action.eventId}: {action.GetName(controller.GetStructuredFile())}")

# 获取纹理列表
textures = controller.GetTextures()
for tex in textures:
    print(f"Texture: {tex.name} ({tex.width}x{tex.height})")

controller.Shutdown()
cap.Shutdown()
```

### 8.4 文档与示例

- **官方 Python API 文档**: https://renderdoc.org/docs/python_api/index.html
- **内置脚本示例**: `qrenderdoc/Windows/PythonShell.cpp` (嵌入式 Python Shell)

---

## 9. 源码分析路线图

> **目标**：按顺序阅读源码，快速理解 RDC 解析流程。

### 9.1 推荐阅读顺序

| 阶段 | 文件 | 重点 |
|------|------|------|
| **1. 入口** | `renderdoc/replay/capture_file.cpp` | `CaptureFile::OpenFile` 如何调用 `RDCFile` |
| **2. 文件格式** | `renderdoc/serialise/rdcfile.h/.cpp` | `Open()`, `Init()`, `SectionIndex()` |
| **3. Section 类型** | `renderdoc/api/replay/replay_enums.h` | 搜索 `SectionType` 枚举 |
| **4. 序列化** | `renderdoc/serialise/serialiser.h` | `Serialiser` 模板类 |
| **5. 回放控制** | `renderdoc/replay/replay_controller.cpp` | `CreateDevice`, `PostCreateInit` |
| **6. 驱动适配** | `renderdoc/driver/{api}/{api}_replay.cpp` | `ReadLogInitialisation` |

### 9.2 关键搜索模式

```bash
# 查找 RDC 文件打开逻辑
rg -n "RDCFile::Open" renderdoc/

# 查找各驱动的 Replay 入口
rg -n "ReadLogInitialisation" renderdoc/driver/

# 查找 Section 类型定义
rg -n "enum class SectionType" renderdoc/

# 查找 Python 绑定
rg -n "CaptureFile|ReplayController" qrenderdoc/Code/pyrenderdoc/
```

### 9.3 调试技巧

1. **断点位置**：`RDCFile::Init()` — 所有 RDC 解析从这里开始
2. **日志开关**：设置环境变量 `RENDERDOC_DEBUG_LOG=1` 启用详细日志
3. **Python 交互**：在 RenderDoc UI 中使用 Python Shell 实时探索 API

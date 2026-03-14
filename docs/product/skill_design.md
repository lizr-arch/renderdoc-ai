# AI Skill 设计案（安装/自检 + 增值分析）

## 角色与场景
- 用户：渲染程序员、游戏程序员、TA；希望用自然语言驱动自动化与高阶解读。
- 场景：环境快速就绪；基于报告/快照/MCP 数据生成结论、脚本、行动清单。

## 双职责
1) 安装/自检（一次性/异常时）
   - 安装/更新 MCP 扩展，检查 PySide2/6/线程回退。
   - 启动/验证 `renderdoc-mcp`，检测 `%TEMP%/renderdoc_mcp`。
   - 失败场景给出修复步骤（勾选扩展、重启 GUI、路径注入）。
2) 增值分析（核心）
   - 读取数据源：GUI/离线报告、JSON 快照、MCP 查询结果。
   - 生成高阶输出：瓶颈归因、管线/状态审阅、Shader 公式提取、资源异常检测、回归对比摘要、行动清单/脚本。

## 典型用例
- 性能热点：聚合 `get_action_timings` / 报告计时，输出 Top-N + 可能原因 + 验证步骤。
- Shader 解析：拉取反编译文本，提取 BRDF/光照路径/关键宏，标出风险与改动点。
- 管线审阅：检测深度/混合/采样/顶点布局异常，生成检查清单。
- 资源异常：找尺寸/格式/采样不匹配的 RT/纹理，提示潜在渲染瑕疵。
- 回归对比：对两份快照/报告，输出变化摘要（格式、绑定、计时、资源数）。
- 脚本生成：将自然语言意图翻译为 MCP/CLI 命令或复现场景的操作序列。

## 性能归因（调研结论 & 最小可行输出）
- 数据可用性：当前捕获 `get_action_timings` 返回 338 条，约 30% 为 0/负值（需过滤）。可用总时长约 1.8–2.2 ms，Top 事件 ~0.48 ms。
- 最小输出形态（Markdown 简报 + 命令清单）：
  - 标题：性能瓶颈初步（Top-N by GPU time，过滤 <=0）
  - 列表：`event_id | name | duration_ms`
  - 提示：计时可用 / zero/neg 数量；若占比高，建议缩小 marker_filter 或检查 GPU 计时支持。
  - 命令清单（可直接执行）：
    - `renderdoc-mcp call get_pipeline_state --event-id <eid>`
    - `renderdoc-mcp call find_draws_by_shader --shader-name <kw>`
    - `renderdoc-mcp call find_draws_by_texture --texture-name <kw>`
    - 需要资源内容时：`renderdoc-mcp call get_texture_info|get_texture_data|get_buffer_contents ...`
- 风险与降级：
  - GPU 计时不可用或 0/neg 占比高：在输出中显式标注；提示改用 marker_filter 或确认硬件/驱动计时支持。
  - 命名不清晰：可附加 `get_draw_calls --event-id-min/max` 以获取上下文名称。

## 数据契约
- 输入：报告 HTML/JSON 快照；MCP 响应（动作/计时/管线/资源/Shader）；用户描述。
- 输出：Markdown/HTML 片段、命令脚本、行动清单（含 event_id/resource_id 引用）。

## 与其他功能的关系
- 不生成整份报告；依赖 GUI/离线/MCP 数据。
- 安装/自检仅做环境准备，不掺杂分析逻辑。

## 落地步骤
- 定义可调用脚本/API 列表（MCP 调用模板、离线快照读取器）。
   - 示例：`flow_diagram.py`（待实现）生成 Mermaid/JSON 概览供 AI 二次讲解。
- 编写 Skill Prompt/动作集：安装自检集、分析集（用例驱动）。
- 文档化输入/输出示例，明确 AI 输出格式（摘要 + 证据 + 下一步）。

## 验收指标
- 安装自检：3 步内完成；失败给出可执行指引。
- 分析有效性：Top-N 瓶颈/风险命中率；用户采纳脚本/行动清单比例。

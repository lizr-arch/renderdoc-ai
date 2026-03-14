# MCP 实时接口设计案

## 角色与场景
- 脚本/自动化、AI 助手、局部数据补拉、性能/渲染问题定位。

## 目标
- 提供可靠的实时数据 API，不生成整份报告；强调按需、小颗粒、低延迟。
- 为 Skill/脚本提供标准调用与示例。

## 核心工具
- `renderdoc-mcp`（FastMCP 服务器）
- 扩展（renderdoc_mcp_bridge）：文件 IPC（线程或 Qt 定时），已适配 PySide2/6 缺失场景。

## 主要 API（样例）
- 捕获：`get_capture_status`, `list_captures`, `open_capture`
- 动作：`get_draw_calls`（过滤）、`get_frame_summary`, `get_draw_call_details`
- 计时：`get_action_timings`（支持 marker/exclude）
- 搜索：`find_draws_by_shader`, `find_draws_by_texture`, `find_draws_by_resource`
- 管线/Shader：`get_pipeline_state`, `get_shader_info`
- 资源：`get_buffer_contents`, `get_texture_info`, `get_texture_data`

## 定位与边界
- 不提供“一键报告”；用于按需查询、补全离线缺口、驱动 AI 分析。
- 可输出局部 JSON 供外部工具/AI 消费。

## 健康/安装
- 扩展安装脚本：`python tools/mcp/scripts/install_extension.py`
- 运行：RenderDoc GUI + 扩展启用 -> `renderdoc-mcp` -> `renderdoc-mcp call ...`
- 回退：无 Qt 时使用线程轮询。

## 示例工作流
- 性能热点：`get_action_timings --marker-filter ...` -> 生成 Top-N 列表。
- 反查资源：`find_draws_by_texture --texture-name UI` -> event_id 列表 -> `get_pipeline_state`。
- 纹理/缓冲抽取：`get_texture_data` / `get_buffer_contents` -> AI/脚本做进一步分析。

## 验收指标
- 延迟与可用性：常用调用在小捕获下 < 500ms；无扩展时明确报错指引。
- 稳定性：容忍缺 Qt/路径问题（有回退与错误提示）。

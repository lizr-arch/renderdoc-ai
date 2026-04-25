# MCP 实时接口设计案

> 2026-04-23 delta：本文件描述的是 MCP 设计目标，不等同于“当前全部方法都已运行验证”。
> 当前已验证运行面以 `get_capture_status` 和 `bridge_unavailable / recovery_hint` 诊断增强为主；更大方法集仍以 `docs/product/mcp_query_contract_v1.md` 作为契约目标。
> 当前状态总入口：`docs/product/delivery_surfaces_status.md`

## 角色与场景
- 脚本/自动化、AI 助手、局部数据补拉、性能/渲染问题定位。

## 目标
- 提供可靠的实时数据 API，不生成整份报告；强调按需、小颗粒、低延迟。
- 为 Skill/脚本提供标准调用与示例。

## 当前实现状态（2026-04-23）

- 当前最可信的运行面是：
  - `run_query.py --method get_capture_status`
  - `tools/mcp/snapshot_consumer.py`
  - `tools/mcp/tests/test_snapshot_consumer.py`
- 当前已经有代码/测试证据的点：
  - 统一 `mcp-query.v1` envelope
  - `bridge_unavailable`
  - `capture_not_loaded`
  - `timeout`
  - GUI 未启动、IPC 锁冲突、bridge 不可用时的 `recovery_hint`
- 当前不能诚实宣称已经 repo-local 验证完毕的，是更大方法集的 GUI handler/source：
  - `list_captures`
  - `open_capture`
  - `get_draw_calls`
  - `get_draw_call_details`
  - `find_draws_by_*`
  - `get_texture_info`
  - `get_buffer_contents`

使用建议：

- 把本文件当作设计案和产品目标
- 把 `mcp_query_contract_v1.md` 当作正式契约
- 把 `delivery_surfaces_status.md` 当作当前真实落地状态

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

# RDC Analysis MCP Server - 设计文档

## 1. 概述

### 1.1 目标

提供一个 MCP (Model Context Protocol) 服务器，让 AI（如 Claude）能够：
- 打开和分析 RenderDoc 截帧文件（.rdc）
- 查询 DrawCall、纹理、缓冲区等资源信息
- 导出纹理为图片文件
- **调用 rdc_analyzer 生成 HTML 分析报告**
- 对比多个截帧

### 1.2 设计决策

| 决策项 | 选择 | 理由 |
|--------|------|------|
| 语言 | Python | RenderDoc 提供 Python API |
| 框架 | FastMCP | 官方推荐，简化开发 |
| 传输方式 | stdio | 本地运行，数据不出本机 |
| 会话模式 | 多会话 | 支持同时打开多个 RDC 进行对比 |
| 分析引擎 | 整合 rdc_analyzer | 复用现有 HTML 报告生成能力 |
| RenderDoc 路径 | 硬编码修改版路径 | 确保使用跨 GPU 兼容版本 |

### 1.3 整合架构

**核心思想**：MCP 作为 rdc_analyzer 的上层封装，AI 通过 MCP 工具调用 Analyzer 的功能。

```
┌─────────────────────────────────────────────────────────────────┐
│                       用户与 AI 交互                            │
│   "分析一下这个 RDC，找出性能问题"                              │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    MCP Server (rdc_mcp.py)                      │
│   ┌───────────────────────────────────────────────────────────┐ │
│   │ MCP Tools (AI 可调用)                                     │ │
│   │                                                           │ │
│   │ ┌─────────────┐ ┌─────────────┐ ┌─────────────────────┐  │ │
│   │ │ 基础查询类  │ │ 分析类     │ │ 导出类              │  │ │
│   │ │             │ │            │ │                     │  │ │
│   │ │ open_capture│ │ analyze    │ │ export_texture      │  │ │
│   │ │ list_actions│ │ get_issues │ │ export_report       │  │ │
│   │ │ get_info    │ │ get_hotspot│ │                     │  │ │
│   │ └─────────────┘ └─────────────┘ └─────────────────────┘  │ │
│   └───────────────────────────────────────────────────────────┘ │
│                              │                                   │
│                              ▼ 内部调用                          │
│   ┌───────────────────────────────────────────────────────────┐ │
│   │             rdc_analyzer (现有代码库)                     │ │
│   │                                                           │ │
│   │ from rdc_analyzer.main import analyze, AnalysisOptions    │ │
│   │ from rdc_analyzer.core.hotspot_analyzer import ...        │ │
│   │ from rdc_analyzer.exporters.html_exporter import ...      │ │
│   └───────────────────────────────────────────────────────────┘ │
│                              │                                   │
│                              ▼                                   │
│   ┌───────────────────────────────────────────────────────────┐ │
│   │             RenderDoc Python Module                       │ │
│   │             (x64/Development/renderdoc.pyd)               │ │
│   │             (跨 GPU 兼容修改版)                           │ │
│   └───────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

---

## 2. 架构

### 2.1 组件图

```
┌──────────────────────────────────────────────────────────────────┐
│                        rdc_mcp.py (入口)                         │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │                     SessionManager                          ││
│  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐           ││
│  │  │  Session 1  │ │  Session 2  │ │  Session N  │           ││
│  │  │  (abc123)   │ │  (def456)   │ │  (...)      │           ││
│  │  │    ↓        │ │    ↓        │ │    ↓        │           ││
│  │  │ CaptureFile │ │ CaptureFile │ │ CaptureFile │           ││
│  │  │ Controller  │ │ Controller  │ │ Controller  │           ││
│  │  │ AnalysisCtx │ │ AnalysisCtx │ │ AnalysisCtx │ (缓存)    ││
│  │  └─────────────┘ └─────────────┘ └─────────────┘           ││
│  └─────────────────────────────────────────────────────────────┘│
│                                                                  │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │                    MCP Tools (3 类)                         ││
│  │                                                             ││
│  │  【基础查询】                                               ││
│  │  rdc_open_capture │ rdc_close_capture │ rdc_get_info       ││
│  │  rdc_list_actions │ rdc_get_action    │ rdc_list_textures  ││
│  │  rdc_list_buffers │ rdc_get_pipeline                       ││
│  │                                                             ││
│  │  【分析功能】(封装 rdc_analyzer)                            ││
│  │  rdc_analyze      │ rdc_get_issues    │ rdc_get_hotspots   ││
│  │  rdc_get_summary  │ rdc_compare                            ││
│  │                                                             ││
│  │  【导出功能】                                               ││
│  │  rdc_export_texture │ rdc_export_report                    ││
│  └─────────────────────────────────────────────────────────────┘│
│                                                                  │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │                  AnalyzerBridge (适配层)                    ││
│  │  - 封装 rdc_analyzer.main.analyze()                        ││
│  │  - 封装 rdc_analyzer.core.hotspot_analyzer                 ││
│  │  - 封装 rdc_analyzer.rules.RuleRunner                      ││
│  └─────────────────────────────────────────────────────────────┘│
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
                               │
              ┌────────────────┴────────────────┐
              ▼                                 ▼
┌─────────────────────────────┐   ┌─────────────────────────────┐
│     rdc_analyzer (现有库)   │   │  RenderDoc Python Module    │
│  - main.py (analyze 入口)   │   │  (x64/Development/          │
│  - core/ (分析核心)         │   │   renderdoc.pyd)            │
│  - rules/ (规则引擎)        │   │  (跨 GPU 兼容修改版)        │
│  - exporters/ (导出器)      │   │                             │
└─────────────────────────────┘   └─────────────────────────────┘
```

### 2.2 会话生命周期

```
         rdc_open_capture(path)
                │
                ▼
    ┌───────────────────────┐
    │   创建 Session        │
    │   - 生成 session_id   │
    │   - 打开 CaptureFile  │
    │   - 创建 Controller   │
    └───────────────────────┘
                │
                ▼
    ┌───────────────────────┐
    │   活跃状态            │ ◄──── 其他工具调用
    │   - 响应查询请求      │       (rdc_list_actions, etc.)
    │   - 保持资源          │
    └───────────────────────┘
                │
                ▼ rdc_close_capture(session_id)
    ┌───────────────────────┐
    │   清理                │
    │   - Controller.Shutdown │
    │   - CaptureFile.Shutdown│
    │   - 移除 Session      │
    └───────────────────────┘
```

---

## 3. 工具定义

### 3.1 工具清单

#### 基础查询类

| 工具 | 功能 | readOnly | destructive | idempotent |
|------|------|----------|-------------|------------|
| `rdc_open_capture` | 打开 RDC 文件 | ✅ | ❌ | ❌ |
| `rdc_close_capture` | 关闭会话 | ✅ | ❌ | ✅ |
| `rdc_get_info` | 获取截帧信息 | ✅ | ❌ | ✅ |
| `rdc_list_actions` | 列出绘制调用 | ✅ | ❌ | ✅ |
| `rdc_get_action` | 获取单个 Action | ✅ | ❌ | ✅ |
| `rdc_list_textures` | 列出纹理 | ✅ | ❌ | ✅ |
| `rdc_list_buffers` | 列出缓冲区 | ✅ | ❌ | ✅ |
| `rdc_get_pipeline` | 获取管线状态 | ✅ | ❌ | ✅ |

#### 分析功能类（封装 rdc_analyzer）

| 工具 | 功能 | readOnly | destructive | idempotent |
|------|------|----------|-------------|------------|
| `rdc_analyze` | 执行完整分析并生成报告 | ❌ | ❌ | ✅ |
| `rdc_get_issues` | 获取检测到的问题列表 | ✅ | ❌ | ✅ |
| `rdc_get_hotspots` | 获取性能热点 | ✅ | ❌ | ✅ |
| `rdc_get_summary` | 获取分析摘要 | ✅ | ❌ | ✅ |
| `rdc_compare` | 对比两个 RDC | ✅ | ❌ | ✅ |

#### 导出功能类

| 工具 | 功能 | readOnly | destructive | idempotent |
|------|------|----------|-------------|------------|
| `rdc_export_texture` | 导出纹理为图片 | ❌ | ❌ | ✅ |
| `rdc_export_report` | 导出 HTML/JSON 报告 | ❌ | ❌ | ✅ |

### 3.2 输入/输出 Schema

#### rdc_open_capture

**输入**：
```json
{
  "rdc_path": "D:\\backup\\capture.rdc"
}
```

**输出**：
```json
{
  "session_id": "abc123",
  "api": "Vulkan",
  "frame_number": 1234,
  "device": "NVIDIA GeForce RTX 2060 SUPER",
  "action_count": 5678,
  "texture_count": 123,
  "buffer_count": 456
}
```

#### rdc_list_actions

**输入**：
```json
{
  "session_id": "abc123",
  "offset": 0,
  "limit": 50,
  "filter": "Draw"  // 可选：过滤类型
}
```

**输出**：
```json
{
  "total": 5678,
  "count": 50,
  "offset": 0,
  "has_more": true,
  "actions": [
    {
      "eid": 1,
      "name": "vkCmdDrawIndexed",
      "flags": ["Drawcall", "Indexed"],
      "num_indices": 1000,
      "num_instances": 1
    }
  ]
}
```

#### rdc_get_action

**输入**：
```json
{
  "session_id": "abc123",
  "eid": 1234
}
```

**输出**：
```json
{
  "eid": 1234,
  "name": "vkCmdDrawIndexed",
  "flags": ["Drawcall", "Indexed"],
  "num_indices": 36,
  "num_instances": 1,
  "vertex_offset": 0,
  "index_offset": 0,
  "instance_offset": 0,
  "outputs": [
    {"resource_id": 123, "name": "RenderTarget0"}
  ],
  "depth_output": {"resource_id": 124, "name": "DepthBuffer"}
}
```

#### rdc_list_textures

**输入**：
```json
{
  "session_id": "abc123",
  "offset": 0,
  "limit": 50
}
```

**输出**：
```json
{
  "total": 123,
  "count": 50,
  "textures": [
    {
      "resource_id": 100,
      "name": "Albedo_Texture",
      "width": 1024,
      "height": 1024,
      "depth": 1,
      "mips": 10,
      "array_size": 1,
      "format": "R8G8B8A8_UNORM",
      "type": "Texture2D"
    }
  ]
}
```

#### rdc_export_texture

**输入**：
```json
{
  "session_id": "abc123",
  "resource_id": 100,
  "output_path": "D:\\output\\texture.png",
  "mip": 0,
  "slice": 0,
  "format": "png"  // png/jpg/exr
}
```

**输出**：
```json
{
  "success": true,
  "output_path": "D:\\output\\texture.png",
  "size_bytes": 4194304
}
```

### 3.3 分析功能类工具 Schema

#### rdc_analyze (核心工具)

**功能**：调用 rdc_analyzer 执行完整分析，生成 HTML 报告

**输入**：
```json
{
  "session_id": "abc123",
  "output_dir": "D:\\output\\analysis",
  "options": {
    "platform": "pc",
    "enable_performance_analysis": true,
    "enable_mali_analysis": false,
    "enable_tile_analysis": false,
    "sample_textures": true,
    "max_texture_size": 256
  }
}
```

**输出**：
```json
{
  "success": true,
  "summary": {
    "total_events": 10234,
    "draw_call_count": 5678,
    "total_vertices": 1234567,
    "total_triangles": 411522,
    "texture_count": 123,
    "buffer_count": 456,
    "error_count": 0,
    "warning_count": 15,
    "info_count": 42
  },
  "report_path": "D:\\output\\analysis\\report.html",
  "output_files": [
    "D:\\output\\analysis\\report.html",
    "D:\\output\\analysis\\data.json"
  ],
  "duration_seconds": 45.3
}
```

#### rdc_get_issues

**功能**：获取 rdc_analyzer 检测到的问题列表（警告、错误）

**输入**：
```json
{
  "session_id": "abc123",
  "severity": "warning",
  "category": "performance",
  "limit": 20
}
```

**输出**：
```json
{
  "total": 15,
  "issues": [
    {
      "id": "PERF001",
      "severity": "warning",
      "category": "performance",
      "title": "高三角形数量 DrawCall",
      "description": "DrawCall #1234 包含 50000+ 三角形，考虑使用 LOD",
      "event_id": 1234,
      "suggestion": "为远距离物体使用低多边形 LOD 模型"
    },
    {
      "id": "TEX001",
      "severity": "warning", 
      "category": "texture",
      "title": "大尺寸纹理",
      "description": "纹理 'Albedo_4K' 尺寸为 4096x4096，考虑压缩",
      "resource_id": 100,
      "suggestion": "使用 BC7 压缩格式减少显存占用"
    }
  ]
}
```

#### rdc_get_hotspots

**功能**：获取性能热点（最耗时的 DrawCall）

**输入**：
```json
{
  "session_id": "abc123",
  "top_n": 10,
  "metric": "triangles"
}
```

**输出**：
```json
{
  "metric": "triangles",
  "hotspots": [
    {
      "rank": 1,
      "event_id": 1234,
      "name": "vkCmdDrawIndexed",
      "value": 50000,
      "percentage": 12.5,
      "cumulative_percentage": 12.5
    },
    {
      "rank": 2,
      "event_id": 2345,
      "name": "vkCmdDrawIndexed",
      "value": 35000,
      "percentage": 8.7,
      "cumulative_percentage": 21.2
    }
  ]
}
```

#### rdc_export_report

**功能**：导出分析报告为 HTML 或 JSON

**输入**：
```json
{
  "session_id": "abc123",
  "output_path": "D:\\output\\report.html",
  "format": "html"
}
```

**输出**：
```json
{
  "success": true,
  "output_path": "D:\\output\\report.html",
  "size_bytes": 1048576
}
```

---

## 4. 错误处理

### 4.1 错误类型

| 错误类型 | HTTP 类比 | 处理方式 |
|----------|-----------|----------|
| 会话不存在 | 404 | 返回 "Session not found: {id}" |
| RDC 打开失败 | 400 | 返回具体错误信息（跨 GPU 问题等） |
| 资源不存在 | 404 | 返回 "Resource not found: {id}" |
| 参数错误 | 400 | Pydantic 验证错误 |
| 内部错误 | 500 | 捕获异常，返回安全信息 |

### 4.2 错误响应格式

```json
{
  "error": true,
  "error_type": "SessionNotFound",
  "message": "Session 'abc123' not found. Available sessions: ['def456']",
  "suggestion": "Use rdc_open_capture to create a new session."
}
```

---

## 5. 文件结构

### 5.1 开发目录结构

```
scripts/rdc_mcp/
├── rdc_mcp.py              # MCP 服务器入口 + FastMCP 注册
├── session_manager.py      # 会话管理
├── analyzer_bridge.py      # rdc_analyzer 适配层 (新增)
├── tools/
│   ├── __init__.py
│   ├── capture.py          # 打开/关闭/信息
│   ├── actions.py          # Action 相关
│   ├── resources.py        # 纹理/缓冲区
│   ├── pipeline.py         # Pipeline 状态
│   └── analysis.py         # 分析功能 (新增，调用 analyzer_bridge)
├── models/
│   ├── __init__.py
│   ├── inputs.py           # Pydantic 输入模型
│   └── outputs.py          # 输出数据结构
├── requirements.txt
├── install.bat             # 一键安装脚本
├── run_mcp.bat             # 启动脚本
├── README.md               # 用户指南
└── DESIGN.md               # 本文件
```

### 5.2 整合分发包结构

```
RDC-AI-Analyzer/
├── renderdoc/                    # 修改版 RenderDoc
│   ├── renderdoc.dll
│   ├── renderdoc.pyd             # Python 模块
│   └── qrenderdoc.exe            # (可选) GUI
│
├── rdc_analyzer/                 # 分析库 (完整目录)
│   ├── main.py
│   ├── core/
│   ├── rules/
│   ├── exporters/
│   └── ...
│
├── rdc_mcp/                      # MCP 服务器
│   ├── rdc_mcp.py
│   ├── session_manager.py
│   ├── analyzer_bridge.py
│   └── tools/
│
├── install.bat                   # 一键安装
├── run_mcp.bat                   # 启动 MCP
├── requirements.txt
└── README.md                     # 使用说明
```

---

## 6. 依赖

### 6.1 Python 包

```
# requirements.txt
mcp>=1.0.0
pydantic>=2.0.0
Pillow>=9.0.0
```

### 6.2 内置依赖（通过 sys.path 添加）

| 模块 | 路径 | 说明 |
|------|------|------|
| `renderdoc.pyd` | `renderdoc/` | RenderDoc Python 模块（修改版） |
| `rdc_analyzer` | `rdc_analyzer/` | HTML 报告生成库 |

---

## 7. 使用方式

### 7.1 安装

1. 下载 `RDC-AI-Analyzer.zip`
2. 解压到任意目录（如 `D:\Tools\RDC-AI-Analyzer`）
3. 运行 `install.bat`
4. 按提示配置 Claude Desktop

### 7.2 配置 Claude Desktop

编辑 `%APPDATA%\Claude\claude_desktop_config.json`：

```json
{
  "mcpServers": {
    "rdc_analyzer": {
      "command": "py",
      "args": ["-3", "D:\\Tools\\RDC-AI-Analyzer\\rdc_mcp\\rdc_mcp.py"]
    }
  }
}
```

### 7.3 重启 Claude Desktop

配置生效后，重启 Claude Desktop。

---

## 8. 示例对话

### 对话 1：打开并分析 RDC

**用户**：帮我分析一下 D:\backup\战斗特写1.rdc，找出性能问题

**AI 调用**：
1. `rdc_open_capture(rdc_path="D:\\backup\\战斗特写1.rdc")`
2. `rdc_analyze(session_id="abc123", output_dir="D:\\backup\\analysis")`
3. `rdc_get_issues(session_id="abc123", severity="warning")`

**AI 回复**：
> 分析完成！发现 15 个性能警告：
> 
> 1. **PERF001**: DrawCall #1234 包含 50000+ 三角形
>    - 建议：为远距离物体使用 LOD
> 
> 2. **TEX001**: 纹理 'Albedo_4K' 尺寸为 4096x4096
>    - 建议：使用 BC7 压缩
> 
> 完整报告已保存到：`D:\backup\analysis\report.html`

### 对话 2：查看性能热点

**用户**：这帧里最消耗性能的是什么？

**AI 调用**：`rdc_get_hotspots(session_id="abc123", top_n=5)`

**AI 回复**：
> 前 5 个性能热点（按三角形数量）：
> 
> | 排名 | DrawCall | 三角形 | 占比 |
> |------|----------|--------|------|
> | 1 | #1234 | 50,000 | 12.5% |
> | 2 | #2345 | 35,000 | 8.7% |
> | 3 | #3456 | 28,000 | 7.0% |
> | 4 | #4567 | 22,000 | 5.5% |
> | 5 | #5678 | 18,000 | 4.5% |
> 
> 前 5 个热点占总三角形的 38.2%

### 对话 3：导出特定纹理

**用户**：把那个 4K 纹理导出给我看看

**AI 调用**：`rdc_export_texture(session_id="abc123", resource_id=100, output_path="D:\\backup\\albedo_4k.png")`

**AI 回复**：
> 已导出纹理到 `D:\backup\albedo_4k.png` (4.0 MB)

---

## 9. 后续扩展

| 功能 | 优先级 | 说明 |
|------|--------|------|
| Shader 源码查看 | 中 | 提取 SPIR-V 并反编译 |
| Buffer 数据查看 | 中 | 读取顶点/索引数据 |
| 性能计数器 | 低 | 需要 GPU 支持 |
| 截帧对比 | 中 | 对比两个 session 的 Action 差异 |

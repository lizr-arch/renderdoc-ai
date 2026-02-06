# RDC Analysis MCP Server

让 AI（如 CodeMaker VS Code 插件）能够分析 RenderDoc 截帧文件 (.rdc)。

## 功能特性

- **打开 RDC 文件**：支持 Vulkan、D3D11、D3D12、OpenGL 截帧
- **查询绘制调用**：列出 DrawCall、获取详细信息
- **查询资源**：纹理、缓冲区列表
- **性能分析**：生成 HTML 报告，检测性能问题
- **优化建议**：根据分析结果给出针对性建议
- **跨 GPU 兼容**：使用修改版 RenderDoc，支持在不同 GPU 上回放

## 快速开始

### 1. 安装依赖

```bash
# 运行安装脚本（安装 Python 依赖）
install.bat
```

### 2. 配置 CodeMaker VS Code

在 VS Code 中，打开 **Settings** (Ctrl+,) → 搜索 `codemaker.mcp` → 添加 MCP 服务器配置：

**方式一：通过 settings.json**

编辑 VS Code 的 `settings.json`（Ctrl+Shift+P → "Preferences: Open Settings (JSON)"）：

```json
{
  "codemaker.mcp.servers": {
    "rdc_analyzer": {
      "command": "py",
      "args": ["-3", "D:\\path\\to\\RDC-AI-Analyzer\\scripts\\rdc_mcp\\rdc_mcp.py"]
    }
  }
}
```

> ⚠️ **注意**：将路径替换为你实际的安装目录。

**方式二：通过 CodeMaker 设置界面**

1. 打开 VS Code 命令面板 (Ctrl+Shift+P)
2. 搜索 "CodeMaker: Configure MCP Servers"
3. 添加新的 MCP 服务器：
   - 名称：`rdc_analyzer`
   - 命令：`py`
   - 参数：`-3`, `D:\path\to\rdc_mcp\rdc_mcp.py`

### 3. 重启 VS Code

配置生效后，重启 VS Code 或重新加载窗口 (Ctrl+Shift+P → "Developer: Reload Window")。

---

## 使用示例

在 CodeMaker 对话中直接请求分析：

### 打开并分析 RDC

```
用户：帮我分析一下 D:\backup\战斗特写1.rdc

AI：好的，让我打开这个截帧文件...
    
    截帧信息：
    - API: Vulkan
    - 设备: NVIDIA GeForce RTX 2060 SUPER
    - 绘制调用: 5678 个
    - 纹理: 123 个
    - 缓冲区: 456 个
```

### 查看性能热点

```
用户：这帧里最消耗性能的 DrawCall 是什么？

AI：让我分析一下绘制调用...
    
    前 5 个热点（按三角形数量）：
    1. #1234 - 50,000 三角形 (12.5%)
    2. #2345 - 35,000 三角形 (8.7%)
    ...
```

### 获取优化建议

```
用户：有什么优化建议？

AI：根据分析结果，有以下建议：
    
    🔴 高优先级：
    - Draw Call 数量过多（5678个），建议考虑合批优化
    
    🟡 中优先级：
    - 检测到 3 个未压缩纹理，建议使用 BC7 压缩
```

---

## 可用工具

### 基础查询

| 工具 | 说明 |
|------|------|
| `rdc_open_capture` | 打开 RDC 文件，返回会话 ID |
| `rdc_close_capture` | 关闭会话，释放资源 |
| `rdc_get_info` | 获取截帧基本信息 |
| `rdc_list_actions` | 列出绘制调用（支持分页、过滤） |
| `rdc_list_textures` | 列出纹理资源 |

### 分析功能

| 工具 | 说明 |
|------|------|
| `rdc_analyze` | 执行完整分析，生成 HTML 报告 |
| `rdc_get_issues` | 获取检测到的问题列表 |
| `rdc_get_hotspots` | 获取性能热点排名 |
| `rdc_get_suggestions` | 获取优化建议 |

---

## 目录结构

```
RDC-AI-Analyzer/
├── bin/                        # 魔改版 RenderDoc
│   ├── qrenderdoc.exe
│   ├── renderdoc.dll
│   ├── renderdoc.pyd           # Python 绑定
│   ├── Qt5*.dll                # Qt 运行时
│   ├── python36.dll
│   └── qtplugins/
├── scripts/
│   ├── rdc_mcp/                # MCP 服务器
│   │   ├── rdc_mcp.py          # 入口
│   │   ├── session_manager.py
│   │   └── models/
│   └── rdc_analyzer/           # 分析库
├── install.bat                 # 安装脚本
├── run_mcp.bat                 # 手动启动（调试用）
└── README.md
```

## 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `RENDERDOC_PATH` | renderdoc.pyd 所在目录 | 自动检测（../bin） |

## 故障排除

### 无法加载 renderdoc 模块

设置 `RENDERDOC_PATH` 环境变量指向包含 `renderdoc.pyd` 的目录：

```bash
set RENDERDOC_PATH=D:\Tools\RDC-AI-Analyzer\bin
```

### MCP 服务器无响应

1. 确保 Python 3.8+ 已安装（`py -3 --version`）
2. 运行 `install.bat` 安装依赖
3. 检查 VS Code settings.json 中的路径是否正确
4. 重新加载 VS Code 窗口

### 手动测试 MCP 服务器

```bash
cd D:\path\to\RDC-AI-Analyzer
run_mcp.bat
```

如果正常启动，会显示等待 stdio 输入的状态。

---

## 许可证

MIT License
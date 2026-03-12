# RDC Analyzer - 独立发布包

> 构建时间: 2026-02-05 15:48:30

## 快速开始

### Windows

```cmd
:: 分析 RDC 文件
run_analyzer.bat analyze D:\captures\game.rdc -o ./output

:: 提取资源 (纹理、Shader)
run_analyzer.bat extract-resources D:\captures\game.rdc --all

:: 查看帮助
run_analyzer.bat --help
```

## 系统要求

- **操作系统**: Windows 10/11 x64
- **Python**: Python 3.6（如果 bin 目录不含 python.exe）
- **GPU**: 支持 D3D11/D3D12/Vulkan/OpenGL 的显卡

## 目录结构

```
rdc_analyzer_standalone/
├── bin/                    # RenderDoc 核心组件
│   ├── renderdoc.dll       # 核心引擎
│   ├── renderdoc.pyd       # Python 绑定
│   ├── renderdoccmd.exe    # 命令行工具
│   └── ...
├── analyzer/               # Python 分析脚本
├── run_analyzer.bat        # 启动脚本
└── README.md               # 本文档
```

## 可用命令

| 命令 | 说明 |
|------|------|
| `analyze` | 分析 RDC 文件，生成 HTML/JSON 报告 |
| `extract-resources` | 提取纹理、Shader、RT 快照 |
| `compare` | 对比两个帧的性能差异 |
| `rules` | 列出可用的分析规则 |

## 常见问题

### Q: 提示找不到 Python 3.6

RenderDoc 的 Python 绑定需要 Python 3.6。请安装:
https://www.python.org/downloads/release/python-368/

### Q: 打开 RDC 文件失败

可能的原因：
1. RDC 文件版本不兼容（需要相同或兼容版本的 RenderDoc 捕获）
2. 跨 GPU 厂商回放（如在 NVIDIA 上回放 Mali 捕获）
3. 文件损坏

### Q: 如何在代码中使用

```python
import sys
sys.path.insert(0, "./bin")
sys.path.insert(0, "./analyzer")

# 设置 DLL 路径 (Python 3.8+)
import os
os.add_dll_directory("./bin")

# 使用分析器
from analyzer.pipeline import analyze_rdc
result = analyze_rdc("capture.rdc")
```

## 版权声明

本工具基于 RenderDoc 开发，RenderDoc 使用 MIT 许可证。
https://github.com/baldurk/renderdoc

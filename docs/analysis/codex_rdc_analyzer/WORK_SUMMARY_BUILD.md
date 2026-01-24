# RenderDoc 编译与 Python 3.6 环境配置

> **重要**：RenderDoc Python 模块 (`renderdoc.pyd`) 需要 Python 3.6 才能运行！

## 1. 编译环境要求

| 依赖 | 版本 | 用途 |
|------|------|------|
| Visual Studio | 2022 Community | 编译器 |
| v140 工具集 | VS 2015 C++ 工具 | Qt 组件编译依赖 |
| Python | 3.6.8 (64-bit) | renderdoc.pyd 运行时 |
| MSBuild | 17.x | 构建系统 |

## 2. 一键编译脚本

已创建批处理脚本：`scripts/_build_renderdoc.bat`

**使用方法**：
```cmd
cd d:\Code\git\renderdoc\scripts
call _build_renderdoc.bat
```

## 3. 编译输出清单

| 文件 | 路径 | 说明 |
|------|------|------|
| `renderdoc.dll` | `x64/Development/` | 核心库 (84 MB) |
| `renderdoccmd.exe` | `x64/Development/` | 命令行工具 |
| `qrenderdoc.exe` | `x64/Development/` | GUI 应用 |
| `renderdoc.pyd` | `x64/Development/pymodules/` | Python 核心模块 |
| `qrenderdoc.pyd` | `x64/Development/pymodules/` | Qt UI Python 扩展 |
| `python36.dll` | `x64/Development/` | Python 3.6 运行时 |

## 4. Python 3.6 安装

**安装路径**：`D:\Program Files\Python36`

**安装步骤**：
1. 下载：https://www.python.org/ftp/python/3.6.8/python-3.6.8-amd64.exe
2. 运行安装程序，选择 "Customize installation"
3. 安装路径设为 `D:\Program Files\Python36`
4. 勾选 "Add Python 3.6 to PATH"

## 5. 验证 Python API

**测试脚本**：`scripts/_test_pyd_import.py`

**运行测试**：
```cmd
"D:\Program Files\Python36\python.exe" d:\Code\git\renderdoc\scripts\_test_pyd_import.py
```

**或使用封装脚本**：
```cmd
call d:\Code\git\renderdoc\scripts\_test_py36.bat
```

**预期输出**：
```
==================================================
SUCCESS: renderdoc module imported!
==================================================
Version: 1.43

Available API items: 457
Sample items: ['APIEvent', 'APIProperties', ...] ...
```

## 6. Python 3.6 DLL 加载注意事项

由于 `os.add_dll_directory()` 在 Python 3.8+ 才可用，Python 3.6 需要通过修改 `PATH` 环境变量来加载依赖 DLL：

```python
import os
import sys

# 添加 pymodules 到 Python 路径
sys.path.insert(0, r'd:\Code\git\renderdoc\x64\Development\pymodules')

# 添加 DLL 目录到 PATH（Python 3.6 方式）
dll_path = r'd:\Code\git\renderdoc\x64\Development'
os.environ['PATH'] = dll_path + os.pathsep + os.environ.get('PATH', '')

# 现在可以导入
import renderdoc as rd
print("Version:", rd.GetVersionString())  # 输出: 1.43
```

## 7. 常见编译问题

| 问题 | 原因 | 解决方案 |
|------|------|----------|
| LNK1104: 无法打开 renderdoc.pyd | 文件被占用 | 关闭所有 Python/qrenderdoc 进程后重试 |
| C1041: 无法打开 vc140.pdb | 并行编译冲突 | 删除 `x64/Development/obj/*/vc140.pdb` 后重试 |
| 找不到 v140 工具集 | 未安装 VS 2015 工具 | VS Installer → 单个组件 → 搜索 v140 并安装 |
| DLL load failed | Python 版本不匹配 | 必须使用 Python 3.6.x，不支持 3.7+ |

## 8. 快速清理命令

```cmd
:: 终止可能占用文件的进程
taskkill /F /IM python.exe 2>nul
taskkill /F /IM qrenderdoc.exe 2>nul

:: 删除锁定的 PDB 文件
del /f "d:\Code\git\renderdoc\x64\Development\obj\qrenderdoc_module\vc140.pdb" 2>nul
```

## 9. 编译验证记录

**验证日期**：2026-01-24

**验证结果**：
```
Testing Python 3.6 at "D:\Program Files\Python36\python.exe"
Python 3.6.8

Testing renderdoc.pyd import...
==================================================
SUCCESS: renderdoc module imported!
==================================================
Version: 1.43

Available API items: 457
Sample items: ['APIEvent', 'APIProperties', 'APIUseData', ...] ...
```

## 10. 相关脚本

| 脚本 | 用途 |
|------|------|
| `scripts/_build_renderdoc.bat` | 一键编译 RenderDoc |
| `scripts/_test_py36.bat` | Python 3.6 验证封装 |
| `scripts/_test_pyd_import.py` | pyd 导入测试脚本 |

## 11. Python API 快速入门

```python
import os
import sys

# 环境设置
sys.path.insert(0, r'd:\Code\git\renderdoc\x64\Development\pymodules')
os.environ['PATH'] = r'd:\Code\git\renderdoc\x64\Development' + os.pathsep + os.environ.get('PATH', '')

import renderdoc as rd

# 打开 RDC 文件
cap = rd.OpenCaptureFile()
result = cap.OpenFile(r"path\to\capture.rdc", "", None)

if result == rd.ResultCode.Succeeded:
    # 获取回放控制器
    status, controller = cap.OpenCapture(rd.ReplayOptions(), None)
    
    if status == rd.ResultCode.Succeeded:
        # 获取所有 Action（DrawCall/Dispatch/...）
        actions = controller.GetRootActions()
        print("Total actions:", len(actions))
        
        # 遍历 Action
        for action in actions:
            print("EID {}: {}".format(action.eventId, action.customName))
        
        # 获取纹理列表
        textures = controller.GetTextures()
        print("Total textures:", len(textures))
        
        controller.Shutdown()
    
    cap.Shutdown()
```

---

**参考文档**：
- RenderDoc 官方 Python API：https://renderdoc.org/docs/python_api/index.html
- 本地离线文档：`docs/offline_reference/RENDERDOC_DOCS_INDEX.md`

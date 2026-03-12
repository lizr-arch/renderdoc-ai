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

**验证日期**：2025-01-24

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

## 12. Sphinx 文档系统

### 12.1 什么是 Sphinx？

**Sphinx** 是一个用 Python 编写的文档生成工具，最初是为 Python 官方文档开发的，现已成为技术文档领域的事实标准。

| 特性 | 说明 |
|------|------|
| **源格式** | reStructuredText (`.rst`) 或 Markdown |
| **输出格式** | HTML、PDF、ePub、CHM 等 |
| **核心能力** | 自动从 Python 代码生成 API 文档 |
| **扩展性** | 丰富的插件生态系统 |

### 12.2 为什么 RenderDoc 使用 Sphinx？

RenderDoc 使用 Sphinx 有以下关键原因：

1. **Python API 自动文档化**
   - `sphinx.ext.autodoc` 扩展可以自动从 `renderdoc.pyd` 模块提取类、函数、参数的文档字符串
   - 无需手动维护 API 文档，代码即文档

2. **交叉引用与链接**
   - `sphinx_paramlinks` 扩展提供参数级别的精确链接
   - 类型、函数、类之间可以自动建立超链接

3. **多格式输出**
   - 同一源文件可生成 HTML（在线浏览）、CHM（Windows 帮助）、PDF 等格式
   - RenderDoc 官方使用 CHM 作为内嵌帮助文件

4. **与代码同步**
   - 文档源文件与代码在同一仓库
   - 每次编译时自动生成最新 API 参考

### 12.3 我们做了什么？

我们成功在本地构建了 RenderDoc 的完整 Sphinx 文档：

| 步骤 | 操作 | 结果 |
|------|------|------|
| **1. 安装依赖** | `pip install sphinx sphinx_paramlinks sphinx_rtd_theme` | ✅ |
| **2. 加载 pyd** | Sphinx 自动导入 `renderdoc.pyd` 和 `qrenderdoc.pyd` | ✅ |
| **3. 生成文档** | `sphinx-build -b html . ../Documentation/html` | ✅ |
| **4. 验证输出** | 检查 `Documentation/html/index.html` | ✅ |

**构建输出**：
```
d:\Code\git\renderdoc\Documentation\html\
├── index.html              # 首页
├── python_api/             # Python API 参考
│   ├── renderdoc.html      # 核心模块文档
│   ├── qrenderdoc.html     # Qt UI 扩展文档
│   └── examples/           # 示例代码
├── how/                    # 操作指南
├── window/                 # 界面说明
└── ...
```

### 12.4 如何重新构建文档

**方法 1：使用封装脚本（推荐）**
```cmd
call d:\Code\git\renderdoc\scripts\_build_sphinx_docs.bat
```

**方法 2：手动执行**
```cmd
cd d:\Code\git\renderdoc\docs
"D:\Program Files\Python36\python.exe" -m sphinx -b html -d ..\Documentation\doctrees . ..\Documentation\html
```

### 12.5 查看本地文档

构建完成后，可以用浏览器打开：
```cmd
start d:\Code\git\renderdoc\Documentation\html\index.html
```

### 12.6 Sphinx 依赖包

| 包名 | 版本 | 用途 |
|------|------|------|
| `sphinx` | 5.3.0 | 核心文档生成器 |
| `sphinx_paramlinks` | 0.6.0 | 参数链接扩展 |
| `sphinx_rtd_theme` | 2.0.0 | Read the Docs 主题 |

### 12.7 conf.py 关键配置

RenderDoc 的 `docs/conf.py` 中有几个关键配置：

```python
# 扩展模块
extensions = ['sphinx.ext.autodoc', 'sphinx_paramlinks']

# 自动添加 pyd 路径
sys.path.insert(0, os.path.abspath(binpath + 'Development/pymodules'))
os.environ["PATH"] += os.pathsep + os.path.abspath(binpath + 'Development/')

# Python 3.8+ 的 DLL 加载兼容
if sys.platform == 'win32' and sys.version_info[1] >= 8:
    os.add_dll_directory(dev_path)
```

**注意**：由于我们使用 Python 3.6，`os.add_dll_directory()` 不可用，conf.py 中的 `PATH` 修改方式正是为此兼容。

### 12.8 相关脚本

| 脚本 | 用途 |
|------|------|
| `scripts/_install_sphinx.bat` | 为 Python 3.6 安装 Sphinx 及依赖 |
| `scripts/_build_sphinx_docs.bat` | 一键构建 HTML 文档 |
| `scripts/_check_py36.bat` | 验证 Python 3.6 环境 |
| `scripts/_check_sphinx.bat` | 验证 Sphinx 安装 |

---

**参考文档**：
- RenderDoc 官方 Python API：https://renderdoc.org/docs/python_api/index.html
- Sphinx 官方文档：https://www.sphinx-doc.org/
- 本地离线文档：`docs/offline_reference/RENDERDOC_DOCS_INDEX.md`

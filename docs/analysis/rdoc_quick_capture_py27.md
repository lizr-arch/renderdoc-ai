# RenderDoc 进程内截帧（Python 2.7 原生扩展版）

本方案用于 **Python 2.7 嵌入式环境**（无 ctypes）中直接调用 RenderDoc App API。

---

## 1. 为什么需要原生扩展

你的游戏内 Python 是 **2.7.18**，且 `_ctypes` 不存在：
```
>>> import ctypes
ImportError: No module named ctypes
```
因此无法使用 ctypes 方案，只能用 **原生 C 扩展 .pyd**。

---

## 1.5 必要前提：启用 .pyd 动态加载

如果游戏内执行：
```python
import imp
print(imp.get_suffixes())
```
只返回 `.py` / `.pyc`，说明 **PythonCore 禁用了动态模块加载**，`.pyd` 无法被 import。

**根因：**  
`Engine/Sources/External/PythonCore/Python-2.7.18/PC/pyconfig.h` 中  
`HAVE_DYNAMIC_LOADING` 被注释（默认禁用）。

**修复：**  
在 `pyconfig.h` 中启用：
```
#define HAVE_DYNAMIC_LOADING
```
然后 **重新构建 PythonCore/引擎**。

**验证：**  
`imp.get_suffixes()` 输出中包含 `.pyd`。

---

## 2. 产物与路径

- 源码：`util/rdoc_quick_capture_py27/rdoc_capture_py27.cpp`
- 构建脚本：`util/rdoc_quick_capture_py27/build_py27_capture.cmd`
- 输出：`util/rdoc_quick_capture_py27/out/rdoc_capture.pyd`
- 部署目标：`F:\Code\S1\Package\Script\Python\engine\Lib\rdoc_capture.pyd`

---

## 3. 构建步骤

在本机执行（命令仅记录，不自动执行）：

```cmd
util\rdoc_quick_capture_py27\build_py27_capture.cmd
```

构建依赖：
- `python27.dll`（2.7.18）：`F:\Code\S1\Engine\Binaries\Win64\capture_texture\python27.dll`
- `Python.h`（2.7.12 头文件可用）：`F:\Code\S1\doc\tools\Formation_Toos\venv\Include`

脚本会自动生成 `python27.lib`（从 dll 导出）。

---

## 4. 部署步骤

将 `rdoc_capture.pyd` 拷贝到：
```
F:\Code\S1\Package\Script\Python\engine\Lib
```
该目录已在 `sys.path` 中，可直接 `import rdoc_capture`。

---

## 5. 游戏内调用示例

```python
import rdoc_capture

rdoc_capture.load(r"F:\Code\S1\RenderDoc\renderdoc.dll")
print(rdoc_capture.is_available())

rdoc_capture.set_capture_path(r"F:\Code\S1\RenderDocCaptures\capture")
rdoc_capture.set_capture_title("UI_Target")
rdoc_capture.trigger_capture()
```

可选 helper（仓库内）：`util/rdoc_quick_capture_py27/rdoc_capture_helper.py`
```python
import rdoc_capture_helper as rdoc

ok = rdoc.init(
    dll_path=r"F:\Code\S1\RenderDoc\renderdoc.dll",
    capture_path=r"F:\Code\S1\RenderDocCaptures\capture",
    title="UI_Target"
)
print(ok)
rdoc.trigger()
```

---

## 6. 常见问题

**问题 1：`import rdoc_capture` 失败**  
- 确认 `.pyd` 已放到 `engine\Lib`  
- 确认文件名为 `rdoc_capture.pyd`  
- 确认 `imp.get_suffixes()` 包含 `.pyd`

**问题 2：`is_available()` 为 False**  
- `renderdoc.dll` 未加载  
- DLL 路径不可访问，或 `RENDERDOC_GetAPI` 导出不存在  

**问题 3：没有生成 `.rdc`**  
- `set_capture_path` 目录无写权限  
- 触发时机太晚，RenderDoc 未 hook 到 D3D11  

---

## 7. 关键 API 说明

- `load(dll_path=None)`：加载 RenderDoc 并获取 API  
- `is_available()`：是否成功获取 API  
- `set_capture_path(path)`：设置输出路径模板  
- `set_capture_title(title)`：设置捕获标题  
- `trigger_capture()`：触发截帧

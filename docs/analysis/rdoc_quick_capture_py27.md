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

---

## 6. 常见问题

**问题 1：`import rdoc_capture` 失败**  
- 确认 `.pyd` 已放到 `engine\Lib`  
- 确认文件名为 `rdoc_capture.pyd`

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


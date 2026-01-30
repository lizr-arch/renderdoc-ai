# RenderDoc 进程内 Python 截帧（DX11 版）

本说明用于教你在 **DX11 游戏进程内** 通过 Python 直接触发 RenderDoc 截帧，避免在 RenderDoc UI 中配置启动参数与路径。

---

## 1. 思路与原理（核心）

RenderDoc 提供 **App API**（`RENDERDOC_GetAPI`），可在**进程内**直接触发截帧：

1) 进程内加载 `renderdoc.dll`  
2) 调用 `RENDERDOC_GetAPI(version)` 获取函数表  
3) 调用 `TriggerCapture()` 触发截帧

我们用 Python 的 `ctypes` 调用 C 接口，实现“在目标界面直接截帧”的需求。

关键优势：
- 不需要改 C++ 游戏代码  
- 不需要手动在 RenderDoc UI 里配置启动  
- DX11 下 `TriggerCapture()` **不依赖** device/window 指针

---

## 2. 前置条件

- 游戏进程**已经加载** Python（例如 `PythonCore_x64h.dll` / `Python_x64h.dll`）  
- `renderdoc.dll` 在进程内可加载（路径可访问）  
- 推荐尽量**在 D3D11 设备创建前**加载 RenderDoc，避免 hook 不上

---

## 3. 代码位置

已创建脚本（外部游戏目录）：

```
F:\Code\S1\Package\rdoc_quick_capture\rdoc_inprocess_capture.py
```

---

## 4. 使用方法（最小流程）

在目标 UI 逻辑中调用：

```python
from rdoc_quick_capture.rdoc_inprocess_capture import RenderDocInProcess

rdoc = RenderDocInProcess(r"F:\Code\S1\RenderDoc\renderdoc.dll")
if rdoc.is_available() and in_target_ui:
    rdoc.set_capture_path(r"F:\Code\S1\RenderDocCaptures\capture")
    rdoc.set_capture_title("UI_Target")
    rdoc.trigger_capture()
```

说明：
- `set_capture_path` 设置输出目录/前缀  
- `set_capture_title` 标记捕获标题  
- `trigger_capture()` 会立即生成 `.rdc`

---

## 5. 你要怎么测试（验证步骤）

1) **确保可写目录**  
   建议先手动创建：`F:\Code\S1\RenderDocCaptures\`

2) **尽早加载 RenderDoc**  
   在游戏 Python 初始化阶段创建 `RenderDocInProcess(...)`，让 `renderdoc.dll` 尽量早加载。

3) **在目标 UI 触发**  
   当 UI 条件满足时调用：
   - `rdoc.set_capture_path(...)`
   - `rdoc.trigger_capture()`

4) **检查输出**  
   在 `F:\Code\S1\RenderDocCaptures\` 下确认生成 `.rdc`。

5) **打开验证**  
   用 RenderDoc 打开 `.rdc`，确认能看到该帧 drawcall。

---

## 6. 常见问题与排查

**问题 1：`renderdoc.dll` 找不到**  
- 把 `renderdoc.dll` 复制到游戏目录，或传绝对路径给 `RenderDocInProcess(...)`

**问题 2：`RENDERDOC_GetAPI` 获取失败**  
- DLL 不是 RenderDoc 版本（或版本太老）  
- 使用本地编译产物：`D:\Code\git\renderdoc\x64\Development\renderdoc.dll`

**问题 3：没有生成 `.rdc`**  
- 确认调用发生在目标 UI 时  
- 确认 `set_capture_path(...)` 指向可写目录  
- 确认 RenderDoc 在 D3D11 设备创建前已加载（否则可能无法 hook）

---

## 7. 关键接口参考

来自 `renderdoc/api/app/renderdoc_app.h`：  
- `RENDERDOC_GetAPI`  
- `TriggerCapture()`  
- `SetCaptureFilePathTemplate()`  
- `SetCaptureTitle()`


# RenderDoc 进程内 Python 截帧（DX11 版）

本说明用于教你在 **DX11 游戏进程内** 通过 Python 直接触发 RenderDoc 截帧，避免手动在 RenderDoc UI 里配置启动参数。

---

## 1. 思路与原理（核心）

RenderDoc 提供 **App API**（`RENDERDOC_GetAPI`），可在**进程内**直接触发截帧：  

1) 进程内加载 `renderdoc.dll`  
2) 调用 `RENDERDOC_GetAPI(version)` 获取函数表  
3) 调用 `TriggerCapture()` 触发截帧  

这里我们用 Python 的 `ctypes` 动态调用 C 接口，实现 **“在目标界面直接截帧”**。

关键优势：  
- 不需要改 C++ 游戏代码  
- 不需要手动在 RenderDoc UI 里配置启动  
- DX11 情况下，`TriggerCapture()` 不依赖 device/window 指针  

---

## 2. 你现在的环境验证结果

已确认：  
- 游戏进程内加载了 `PythonCore_x64h.dll` / `Python_x64h.dll`  
  → 说明 Python **确实在进程内运行**  
- RenderDoc 已成功编译（Development|x64）  

这意味着 **Python 进程内调用 RenderDoc API 是可行的**。

---

## 3. 代码位置（已放入）

已创建脚本：

```
F:\Code\S1\Package\rdoc_quick_capture\rdoc_inprocess_capture.py
```

你只要在游戏的 Python 更新逻辑里引入并调用即可。

---

## 4. 使用方法（最小流程）

在目标界面逻辑中调用：

```python
from rdoc_quick_capture.rdoc_inprocess_capture import RenderDocInProcess

rdoc = RenderDocInProcess(r"F:\Code\S1\RenderDoc\renderdoc.dll")
if rdoc.is_available() and in_target_ui:
    rdoc.set_capture_path(r"F:\Code\S1\RenderDocCaptures\capture")
    rdoc.set_capture_title("UI_Target")
    rdoc.trigger_capture()
```

说明：
- `set_capture_path` 会设置输出目录/前缀
- `trigger_capture()` 会立即生成 `.rdc`
- 你只需把它放在目标 UI 条件触发的地方

---

## 5. 常见失败原因与排查

**失败 1：`renderdoc.dll` 找不到**  
- 把 `renderdoc.dll` 复制到游戏目录，或传绝对路径给 `RenderDocInProcess(...)`

**失败 2：`RENDERDOC_GetAPI` 获取失败**  
- DLL 不是 RenderDoc 版本（或版本太老）
- 使用本地编译输出：`D:\Code\git\renderdoc\x64\Development\renderdoc.dll`

**失败 3：没有生成 `.rdc`**  
- 确认调用发生在目标 UI 时  
- 确认 `set_capture_path(...)` 指向可写目录  
- 可加日志打印 `is_available()` 状态

---

## 6. 你可以怎么扩展

- **更稳定**：在目标 UI 触发 `trigger_capture()` 而非依赖热键  
- **更可读**：用 `set_capture_title()` 标注捕获标题  
- **批量抓取**：在多个关键 UI 状态触发捕获

---

## 7. 关键接口参考

来自 `renderdoc/api/app/renderdoc_app.h`：  
- `RENDERDOC_GetAPI`  
- `TriggerCapture()`  
- `SetCaptureFilePathTemplate()`  
- `SetCaptureTitle()`  

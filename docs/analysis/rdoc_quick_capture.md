# RenderDoc 快速截帧集成（D3D12 / Windows）

目标：游戏正常启动后，在目标界面按 F12 或直接触发 API，即可生成 `.rdc`。

## 1. 前置条件
- 进程内可加载 `renderdoc.dll`（无反作弊/保护限制）。
- 目标 API 为 D3D12（示例为 D3D12）。

## 2. 集成步骤（最小）
1) 确保 `renderdoc.dll` 在进程内可加载  
   - 常见做法：将 `renderdoc.dll` 放在游戏可执行文件目录，或传入绝对路径给 `Init()`。
2) 在引擎初始化阶段创建并初始化 `RDocQuickCapture`
3) 设置捕获路径与热键
4) 在目标 UI/场景满足时触发捕获

示例（见 `util/rdoc_quick_capture/example_d3d12.cpp`）：
- `RDocQuickCapture::Init(NULL)`：尝试加载 `renderdoc.dll`
- `SetCaptureFilePathTemplate("captures/my_game")`：设置输出路径模板
- `SetHotkeyF12()`：设置热键
- `Trigger()`：在目标界面直接触发捕获

## 3. D3D12 说明
如果需要精确控制一帧的开始/结束，可用：
- `StartFrame(ID3D12Device*, HWND)`
- `EndFrame(ID3D12Device*, HWND)`

如果使用 `Trigger()`，无需传递 device/window，通常足够用于“目标 UI 点击即捕获”。

## 4. 失败排查
若 `Init()` 返回 false：
- `renderdoc.dll` 未加载到进程
- DLL 路径错误或无法访问
- 版本/导出符号异常（`RENDERDOC_GetAPI` 不存在）

## 5. 输出验证
- 捕获文件默认输出到你设置的路径模板目录中
- 通过 RenderDoc UI 打开 `.rdc` 验证捕获内容

## 6. 注意事项
- 不建议在正式发行包中启用
- 与引擎日志/热键系统冲突时，优先改为直接调用 `Trigger()`

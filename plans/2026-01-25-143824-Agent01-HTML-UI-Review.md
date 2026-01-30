# Scope / Assumptions
- In scope: 对 `g145_from_convert_report.html` 做“自动化截图 + 自动交互 + 自动核验”闭环；产出截图与验收记录。
- Out of scope: 修改 HTML 生成逻辑或 RenderDoc 代码；安装新依赖；更改第三方库。
- 假设：Windows 环境可正常启动 Edge；HTML 文件可被本机浏览器打开；允许创建分析产物到 `docs/analysis/`。

# Build/Test/Lint Quick Guide (只记录不执行)
- 打开 HTML：`Start-Process "D:\renderdoc\goog pixel-9\g145_from_convert_report.html"`
- 自动化审阅脚本（PowerShell）：`pwsh -File scripts/_tmp_html_ui_review.ps1 -Html "D:\renderdoc\goog pixel-9\g145_from_convert_report.html" -OutDir "docs/analysis/codex_rdc_analyzer/html_review"`
- 截图完整性检查：`py -3 -c "from pathlib import Path;p=Path('docs/analysis/codex_rdc_analyzer/html_review');print([f.name for f in p.glob('*.png')])"`

# Repo / File List (预期修改/新增)
- 新增（临时脚本）：`scripts/_tmp_html_ui_review.ps1`
- 新增（审阅产物）：`docs/analysis/codex_rdc_analyzer/html_review/`
- 修改（记录审阅结果）：`docs/analysis/codex_rdc_analyzer/WORK_SUMMARY_VERIFICATION.md`

# Approach (Pseudo-code)
```
launch Edge with html file
wait for window handle -> bring to foreground -> get window rect
capture baseline screenshot
send PageDown (x3), capture screenshots after each
mouse wheel zoom in/out on texture area, capture screenshots
click in Event Browser area, capture screenshot
compute hash/diff for screenshots to ensure UI changes
write review record to WORK_SUMMARY_VERIFICATION.md
```

# Automation Script (完整片段)
```powershell
param(
  [string]$Html,
  [string]$OutDir
)

Add-Type -AssemblyName System.Drawing
Add-Type -AssemblyName System.Windows.Forms
Add-Type @"
using System;
using System.Runtime.InteropServices;
public class Win32 {
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hWnd);
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr hWnd, out RECT rect);
  [DllImport("user32.dll")] public static extern void mouse_event(uint dwFlags, uint dx, uint dy, uint dwData, UIntPtr dwExtraInfo);
  [StructLayout(LayoutKind.Sequential)]
  public struct RECT { public int Left; public int Top; public int Right; public int Bottom; }
}
"@

$edge = Start-Process "msedge.exe" -ArgumentList $Html -PassThru
Start-Sleep -Seconds 2

$hWnd = $edge.MainWindowHandle
if ($hWnd -eq 0) { throw "Edge window not found" }
[Win32]::SetForegroundWindow($hWnd) | Out-Null

$rect = New-Object Win32+RECT
[Win32]::GetWindowRect($hWnd, [ref]$rect) | Out-Null

$width  = $rect.Right - $rect.Left
$height = $rect.Bottom - $rect.Top

if (-not (Test-Path $OutDir)) { New-Item -ItemType Directory -Path $OutDir | Out-Null }

function Save-Screenshot([string]$name) {
  $bmp = New-Object System.Drawing.Bitmap $width, $height
  $g = [System.Drawing.Graphics]::FromImage($bmp)
  $g.CopyFromScreen($rect.Left, $rect.Top, 0, 0, $bmp.Size)
  $path = Join-Path $OutDir $name
  $bmp.Save($path, [System.Drawing.Imaging.ImageFormat]::Png)
  $g.Dispose(); $bmp.Dispose()
}

function Send-Wheel([int]$delta) {
  # 0x0800 = WHEEL
  [Win32]::mouse_event(0x0800, 0, 0, $delta, [UIntPtr]::Zero)
}

function Send-Click([int]$x, [int]$y) {
  [System.Windows.Forms.Cursor]::Position = New-Object System.Drawing.Point($x, $y)
  # 0x0002 = LEFTDOWN, 0x0004 = LEFTUP
  [Win32]::mouse_event(0x0002, 0, 0, 0, [UIntPtr]::Zero)
  Start-Sleep -Milliseconds 50
  [Win32]::mouse_event(0x0004, 0, 0, 0, [UIntPtr]::Zero)
}

Save-Screenshot "01_baseline.png"

# Scroll down to sections
[System.Windows.Forms.SendKeys]::SendWait("{PGDN}")
Start-Sleep -Milliseconds 300
Save-Screenshot "02_pgdn.png"

[System.Windows.Forms.SendKeys]::SendWait("{PGDN}")
Start-Sleep -Milliseconds 300
Save-Screenshot "03_pgdn.png"

[System.Windows.Forms.SendKeys]::SendWait("{PGDN}")
Start-Sleep -Milliseconds 300
Save-Screenshot "04_pgdn.png"

# Zoom in/out on center (texture area)
$cx = [int]($rect.Left + $width * 0.65)
$cy = [int]($rect.Top + $height * 0.55)
Send-Click $cx $cy
Send-Wheel 120
Start-Sleep -Milliseconds 200
Save-Screenshot "05_zoom_in.png"
Send-Wheel -120
Start-Sleep -Milliseconds 200
Save-Screenshot "06_zoom_out.png"

# Click on left side (event list area)
$ex = [int]($rect.Left + $width * 0.25)
$ey = [int]($rect.Top + $height * 0.55)
Send-Click $ex $ey
Start-Sleep -Milliseconds 200
Save-Screenshot "07_event_click.png"
```

# Impact Analysis
- 风险：Edge 窗口句柄获取失败 → 需要重试或手动指定浏览器。
- 风险：坐标点击未命中目标 → 需要调节相对坐标（0.25/0.65/0.55）。
- 风险：截图受 DPI/缩放影响 → 建议统一 100% 缩放。
- 风险：当前会话不支持 GUI 截图（CopyFromScreen 句柄无效）。

# Action Items (2–5 分钟粒度)
- [x] 1. 新建 `scripts/_tmp_html_ui_review.ps1`（脚本见上）。
- [ ] 2. 运行脚本生成截图并验证 PNG 输出。（失败：CopyFromScreen 句柄无效）
- [ ] 3. 统计截图数量与文件大小（> 50KB）。（阻塞：无截图产物）
- [ ] 4. 对比截图差异（确认交互产生变化）。（阻塞：无截图产物）
- [ ] 5. 将审阅记录写入 `WORK_SUMMARY_VERIFICATION.md`。（需注明自动化失败原因）

# Verification / DoD
- 截图文件生成 ≥ 7 张，且均可打开。
- 截图存在明显差异（滚动/缩放前后不一致）。
- 验收记录已写入 `WORK_SUMMARY_VERIFICATION.md`。

# Next Steps
- 用户批准后进入 /do 执行自动化审阅。

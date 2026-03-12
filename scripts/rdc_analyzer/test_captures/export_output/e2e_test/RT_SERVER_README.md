# RT 预览服务使用说明

## 功能说明

RT 预览服务允许您在浏览器查看报告时，按需从 RDC 文件加载 Render Target **与纹理缩略图**。
这避免了预先导出大量图片，节省时间和磁盘空间。

## 使用方法

### Windows

1. **双击运行** `start_rt_server.bat`
2. 或使用 Python Headless（推荐）：
   ```
   py -3 rt_preview_server.py --rdc "path\to\your_capture.rdc" --port 8765
   ```
3. 如需加载真实 RDC 文件：
   ```
   start_rt_server.bat "path\to\your_capture.rdc"
   ```

### Linux/Mac

1. 运行脚本：
   ```bash
   ./start_rt_server.sh /path/to/your_capture.rdc
   ```

## 服务信息

- **端口**: 8765
- **API 端点**: `http://localhost:8765/api/rt/{eid}`
- **纹理端点**: `http://localhost:8765/api/texture/{id}`

## 在报告中使用

1. 启动 RT 预览服务器
2. 打开 `events.html` 或 `textures.html`
3. 在事件页点击「从 RDC 加载」或在纹理页点击「显示缩略图」
4. 系统会自动请求对应 EID 的 Render Target 或纹理缩略图

## 故障排除

### 服务器无法启动

- 确保已安装 RenderDoc（需要 qrenderdoc.exe）
- 确保端口 8765 未被占用

### 图片加载失败

- 检查浏览器控制台是否有 CORS 错误
- 确认服务器正在运行
- 某些事件可能没有可用的 Render Target

## 技术细节

服务器使用 RenderDoc 的 Python API 进行实时截图：
1. 设置帧事件 (`controller.SetFrameEvent`)
2. 导出当前 RT (`controller.SaveTexture`)
3. 返回 Base64 编码的 PNG 图片

#!/usr/bin/env python3
"""
RT Preview Server - 按需加载 Render Target 预览服务

提供轻量级 HTTP API，支持从 RDC 文件动态导出指定事件的 Render Target 图像。

架构:
    ┌─────────────────┐     fetch("/api/rt/{eid}")     ┌──────────────────────┐
    │   events.html   │  ────────────────────────────► │  RT Preview Server   │
    │   (浏览器)       │  ◄────────────────────────────  │  (localhost:8765)    │
    └─────────────────┘     { image: "data:..." }      └──────────────────────┘

API 端点:
    GET /api/rt/{eid}         获取指定事件的 RT 快照 (Base64 PNG)
    GET /api/rt/{eid}/all     获取所有绑定的 RT (多个 slot)
    GET /api/texture/{id}     获取指定纹理资源
    GET /api/status           服务状态检查
    GET /                     简单的状态页面

用法:
    # 方式1: 命令行启动 (需在 qrenderdoc 环境中)
    qrenderdoc.exe --script rt_preview_server.py -- --rdc capture.rdc --port 8765

    # 方式1.1: Headless 启动 (Python 直接运行，无 GUI)
    py -3 rt_preview_server.py --rdc capture.rdc --port 8765
    
    # 方式2: 作为模块导入
    from rt_preview_server import RTPreviewServer
    server = RTPreviewServer("capture.rdc", port=8765)
    server.start()

作者: RenderDoc RDC Analyzer Team
版本: 1.0.0
"""

import json
import base64
import io
import sys
import os
import re
import threading
import time
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from typing import Optional, Dict, Any, Tuple

# 尝试导入 RenderDoc
try:
    import renderdoc as rd
    HAS_RENDERDOC = True
except ImportError:
    HAS_RENDERDOC = False
    print("[WARN] renderdoc module not available, running in mock mode")

FORCE_MOCK = False


class RTExporter:
    """
    Render Target 导出器 - 封装 RenderDoc API 调用
    """
    
    def __init__(self, rdc_path: str):
        """
        初始化导出器
        
        Args:
            rdc_path: RDC 文件路径
        """
        self.rdc_path = rdc_path
        self.cap: Optional[Any] = None
        self.controller: Optional[Any] = None
        self.textures: Dict[int, Any] = {}  # resourceId -> TextureDescription
        self.current_eid: int = -1
        self._lock = threading.Lock()
        
        if not HAS_RENDERDOC or FORCE_MOCK:
            print("[RTExporter] Running in MOCK mode (no renderdoc)")
            return
        
        self._init_replay()
    
    def _init_replay(self):
        """初始化 Replay Controller"""
        if not HAS_RENDERDOC or FORCE_MOCK:
            return
        
        print(f"[RTExporter] Opening RDC: {self.rdc_path}")
        
        self.cap = rd.OpenCaptureFile()
        result = self.cap.OpenFile(self.rdc_path, '', None)
        
        if result != rd.ResultCode.Succeeded:
            raise RuntimeError(f"Failed to open RDC: {result}")
        
        print("[RTExporter] Initializing Replay (requires GPU)...")
        status, self.controller = self.cap.OpenCapture(rd.ReplayOptions(), None)
        
        if status != rd.ResultCode.Succeeded:
            self.cap.Shutdown()
            raise RuntimeError(f"Failed to create Replay: {status}")
        
        # 缓存纹理列表
        tex_list = self.controller.GetTextures()
        for tex in tex_list:
            self.textures[tex.resourceId] = tex
        
        print(f"[RTExporter] Ready. {len(self.textures)} textures cached.")
    
    def get_rt_snapshot(self, eid: int, max_size: int = 512) -> Tuple[Optional[str], str]:
        """
        获取指定事件的 Render Target 快照
        
        Args:
            eid: Event ID
            max_size: 缩略图最大尺寸
            
        Returns:
            (base64_image, error_message)
        """
        if not HAS_RENDERDOC:
            # Mock 模式返回占位符
            return self._generate_mock_image(eid), ""
        
        with self._lock:
            try:
                # 跳转到指定事件
                if self.current_eid != eid:
                    self.controller.SetFrameEvent(eid, True)
                    self.current_eid = eid
                
                # 获取当前 Pipeline State
                state = self.controller.GetPipelineState()
                
                # 获取输出合并器 (Output Merger) 的 RT 绑定
                # 不同 API 有不同的接口
                rt_ids = self._get_bound_rt_ids(state)
                
                if not rt_ids:
                    return None, "No Render Target bound at this event"
                
                # 导出第一个 RT (通常是主 Color Target)
                rt_id = rt_ids[0]
                return self._export_texture_base64(rt_id, max_size), ""
                
            except Exception as e:
                return None, f"Export failed: {str(e)}"
    
    def get_all_rt_snapshots(self, eid: int, max_size: int = 256) -> Tuple[list, str]:
        """
        获取指定事件的所有 RT 快照
        
        Args:
            eid: Event ID
            max_size: 缩略图最大尺寸
            
        Returns:
            ([{slot, image, name, format}], error_message)
        """
        if not HAS_RENDERDOC:
            return [{"slot": 0, "image": self._generate_mock_image(eid), "name": "MockRT"}], ""
        
        with self._lock:
            try:
                if self.current_eid != eid:
                    self.controller.SetFrameEvent(eid, True)
                    self.current_eid = eid
                
                state = self.controller.GetPipelineState()
                rt_ids = self._get_bound_rt_ids(state)
                
                results = []
                for i, rt_id in enumerate(rt_ids):
                    tex = self.textures.get(rt_id)
                    image = self._export_texture_base64(rt_id, max_size)
                    
                    results.append({
                        "slot": i,
                        "image": image,
                        "name": tex.name if tex else f"RT_{rt_id}",
                        "format": str(tex.format) if tex else "Unknown",
                        "width": tex.width if tex else 0,
                        "height": tex.height if tex else 0,
                        "resourceId": rt_id
                    })
                
                return results, ""
                
            except Exception as e:
                return [], f"Export failed: {str(e)}"
    
    def get_texture_snapshot(self, resource_id: int, max_size: int = 512) -> Tuple[Optional[str], str]:
        """
        获取指定纹理资源的快照
        
        Args:
            resource_id: 纹理资源 ID
            max_size: 最大尺寸
            
        Returns:
            (base64_image, error_message)
        """
        if not HAS_RENDERDOC:
            return self._generate_mock_image(resource_id), ""
        
        with self._lock:
            try:
                if resource_id not in self.textures:
                    return None, f"Texture {resource_id} not found"
                
                return self._export_texture_base64(resource_id, max_size), ""
                
            except Exception as e:
                return None, f"Export failed: {str(e)}"
    
    def _get_bound_rt_ids(self, state) -> list:
        """
        从 Pipeline State 获取绑定的 RT Resource IDs
        
        支持多种图形 API
        """
        rt_ids = []
        
        try:
            # Vulkan / D3D12 / D3D11 通用接口
            om = state.GetOutputMerger()
            
            # 尝试获取 Render Targets
            if hasattr(om, 'renderTargets'):
                for rt in om.renderTargets:
                    if hasattr(rt, 'resourceId') and rt.resourceId != 0:
                        rt_ids.append(rt.resourceId)
                    elif hasattr(rt, 'resource') and rt.resource != 0:
                        rt_ids.append(rt.resource)
            
            # 如果没有 renderTargets，尝试 colorTargets (Vulkan)
            if not rt_ids and hasattr(om, 'colorTargets'):
                for ct in om.colorTargets:
                    if hasattr(ct, 'resourceId') and ct.resourceId != 0:
                        rt_ids.append(ct.resourceId)
            
            # Depth/Stencil Target
            if hasattr(om, 'depthTarget'):
                dt = om.depthTarget
                if hasattr(dt, 'resourceId') and dt.resourceId != 0:
                    rt_ids.append(dt.resourceId)
                elif hasattr(dt, 'resource') and dt.resource != 0:
                    rt_ids.append(dt.resource)
                    
        except Exception as e:
            print(f"[RTExporter] Warning: Failed to get RT from state: {e}")
        
        return rt_ids
    
    def _export_texture_base64(self, resource_id: int, max_size: int) -> str:
        """
        导出纹理为 Base64 编码的 PNG
        
        Args:
            resource_id: 纹理资源 ID
            max_size: 最大尺寸（用于生成缩略图）
            
        Returns:
            data:image/png;base64,... 格式的字符串
        """
        import tempfile
        
        # 创建临时文件
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as f:
            temp_path = f.name
        
        try:
            # 配置保存参数
            save = rd.TextureSave()
            save.resourceId = rd.ResourceId(resource_id)
            save.destType = rd.FileType.PNG
            save.mip = 0
            save.slice.sliceIndex = 0
            
            # 如果纹理很大，使用降采样
            tex = self.textures.get(resource_id)
            if tex and (tex.width > max_size or tex.height > max_size):
                # 计算缩放比例
                scale = min(max_size / tex.width, max_size / tex.height)
                # RenderDoc 不直接支持缩放，我们导出原图后再处理
                # 这里先导出原图
            
            # 执行保存
            result = self.controller.SaveTexture(save, temp_path)
            
            if result != rd.ResultCode.Succeeded:
                raise RuntimeError(f"SaveTexture failed: {result}")
            
            # 读取文件并转换为 Base64
            with open(temp_path, 'rb') as f:
                png_data = f.read()
            
            # 如果需要缩放，使用 PIL
            if tex and (tex.width > max_size or tex.height > max_size):
                try:
                    from PIL import Image
                    img = Image.open(io.BytesIO(png_data))
                    img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
                    buffer = io.BytesIO()
                    img.save(buffer, format='PNG')
                    png_data = buffer.getvalue()
                except ImportError:
                    pass  # PIL 不可用，使用原图
            
            b64 = base64.b64encode(png_data).decode('ascii')
            return f"data:image/png;base64,{b64}"
            
        finally:
            # 清理临时文件
            if os.path.exists(temp_path):
                os.unlink(temp_path)
    
    def _generate_mock_image(self, seed: int) -> str:
        """
        生成 Mock 占位图像（用于无 RenderDoc 环境的测试）
        """
        # 简单的 1x1 彩色 PNG (根据 seed 变化颜色)
        colors = [
            b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82',  # Red
            b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xfc\x0f\x00\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82',  # Green
            b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xfc\xff\x00\x00\x02\x01\x00\x06\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82',  # Blue
        ]
        png = colors[seed % len(colors)]
        return f"data:image/png;base64,{base64.b64encode(png).decode()}"
    
    def shutdown(self):
        """清理资源"""
        if self.controller:
            self.controller.Shutdown()
            self.controller = None
        if self.cap:
            self.cap.Shutdown()
            self.cap = None
        print("[RTExporter] Shutdown complete.")


class RTPreviewHandler(BaseHTTPRequestHandler):
    """
    HTTP 请求处理器
    """
    
    # 类变量：共享的导出器实例
    exporter: Optional[RTExporter] = None
    
    def log_message(self, format, *args):
        """自定义日志格式"""
        print(f"[HTTP] {self.address_string()} - {format % args}")
    
    def send_json(self, data: dict, status: int = 200):
        """发送 JSON 响应"""
        content = json.dumps(data, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', len(content))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Cache-Control', 'no-cache')
        self.end_headers()
        self.wfile.write(content)
    
    def send_error_json(self, message: str, status: int = 400):
        """发送错误响应"""
        self.send_json({"error": message, "success": False}, status)
    
    def do_OPTIONS(self):
        """处理 CORS 预检请求"""
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
    
    def do_GET(self):
        """处理 GET 请求"""
        parsed = urlparse(self.path)
        path = parsed.path
        
        # 路由分发
        if path == '/' or path == '/status':
            self.handle_status()
        elif path.startswith('/api/rt/'):
            self.handle_rt_request(path)
        elif path.startswith('/api/texture/'):
            self.handle_texture_request(path)
        else:
            self.send_error_json("Not found", 404)
    
    def handle_status(self):
        """状态检查端点"""
        self.send_json({
            "success": True,
            "status": "running",
            "renderdoc_available": HAS_RENDERDOC,
            "rdc_loaded": self.exporter is not None and self.exporter.controller is not None,
            "texture_count": len(self.exporter.textures) if self.exporter else 0
        })
    
    def handle_rt_request(self, path: str):
        """
        处理 RT 快照请求
        
        支持:
            /api/rt/{eid}       获取第一个 RT
            /api/rt/{eid}/all   获取所有 RT
        """
        if self.exporter is None:
            self.send_error_json("Exporter not initialized", 500)
            return
        
        # 解析路径
        # /api/rt/123 或 /api/rt/123/all
        match = re.match(r'/api/rt/(\d+)(/all)?', path)
        if not match:
            self.send_error_json("Invalid path. Use /api/rt/{eid} or /api/rt/{eid}/all")
            return
        
        eid = int(match.group(1))
        get_all = match.group(2) == '/all'
        
        if get_all:
            # 获取所有 RT
            results, error = self.exporter.get_all_rt_snapshots(eid)
            if error:
                self.send_json({"success": False, "error": error, "results": []})
            else:
                self.send_json({"success": True, "eid": eid, "results": results})
        else:
            # 获取第一个 RT
            image, error = self.exporter.get_rt_snapshot(eid)
            if error:
                self.send_json({"success": False, "error": error, "image": None})
            else:
                self.send_json({"success": True, "eid": eid, "image": image})
    
    def handle_texture_request(self, path: str):
        """
        处理纹理快照请求
        
        /api/texture/{resource_id}
        """
        if self.exporter is None:
            self.send_error_json("Exporter not initialized", 500)
            return
        
        match = re.match(r'/api/texture/(\d+)', path)
        if not match:
            self.send_error_json("Invalid path. Use /api/texture/{resource_id}")
            return
        
        resource_id = int(match.group(1))
        image, error = self.exporter.get_texture_snapshot(resource_id)
        
        if error:
            self.send_json({"success": False, "error": error, "image": None})
        else:
            self.send_json({"success": True, "resourceId": resource_id, "image": image})


class RTPreviewServer:
    """
    RT 预览服务器
    """
    
    def __init__(self, rdc_path: str, port: int = 8765, host: str = "127.0.0.1"):
        """
        初始化服务器
        
        Args:
            rdc_path: RDC 文件路径
            port: 监听端口
            host: 监听地址
        """
        self.rdc_path = rdc_path
        self.port = port
        self.host = host
        self.server: Optional[HTTPServer] = None
        self.exporter: Optional[RTExporter] = None
        self._thread: Optional[threading.Thread] = None
    
    def start(self, blocking: bool = True):
        """
        启动服务器
        
        Args:
            blocking: 是否阻塞当前线程
        """
        print("=" * 60)
        print("RT Preview Server")
        print("=" * 60)
        print(f"RDC File: {self.rdc_path}")
        print(f"Server URL: http://{self.host}:{self.port}")
        print()
        
        # 初始化导出器
        self.exporter = RTExporter(self.rdc_path)
        RTPreviewHandler.exporter = self.exporter
        
        # 创建 HTTP 服务器
        self.server = HTTPServer((self.host, self.port), RTPreviewHandler)
        
        print(f"[Server] Listening on http://{self.host}:{self.port}")
        print()
        print("API Endpoints:")
        print(f"  GET /api/status           - Check server status")
        print(f"  GET /api/rt/{{eid}}         - Get RT snapshot for event")
        print(f"  GET /api/rt/{{eid}}/all     - Get all RT snapshots for event")
        print(f"  GET /api/texture/{{id}}     - Get texture by resource ID")
        print()
        print("Press Ctrl+C to stop the server.")
        print("=" * 60)
        
        if blocking:
            try:
                self.server.serve_forever()
            except KeyboardInterrupt:
                print("\n[Server] Shutting down...")
            finally:
                self.stop()
        else:
            self._thread = threading.Thread(target=self.server.serve_forever, daemon=True)
            self._thread.start()
    
    def stop(self):
        """停止服务器"""
        if self.server:
            self.server.shutdown()
            self.server = None
        if self.exporter:
            self.exporter.shutdown()
            self.exporter = None
        print("[Server] Stopped.")
    
    def is_running(self) -> bool:
        """检查服务器是否运行中"""
        return self.server is not None


def generate_start_script(rdc_path: str, output_dir: str, port: int = 8765) -> dict:
    """
    生成启动脚本
    
    Args:
        rdc_path: RDC 文件路径
        output_dir: 输出目录
        port: 服务器端口
        
    Returns:
        {"bat": bat_path, "sh": sh_path}
    """
    output_dir = Path(output_dir)
    rdc_path = Path(rdc_path).resolve()
    
    # Windows batch 脚本
    bat_content = f'''@echo off
echo Starting RT Preview Server...
echo.
echo RDC File: {rdc_path}
echo Server URL: http://127.0.0.1:{port}
echo.

REM 尝试找到 qrenderdoc.exe
set RENDERDOC_PATH=C:\\Program Files\\RenderDoc\\qrenderdoc.exe
if not exist "%RENDERDOC_PATH%" (
    set RENDERDOC_PATH=C:\\Program Files (x86)\\RenderDoc\\qrenderdoc.exe
)
if not exist "%RENDERDOC_PATH%" (
    echo [ERROR] RenderDoc not found. Please install RenderDoc or set RENDERDOC_PATH.
    pause
    exit /b 1
)

REM 启动服务
"%RENDERDOC_PATH%" --script "{Path(__file__).resolve()}" -- --rdc "{rdc_path}" --port {port}

pause
'''
    
    # Unix shell 脚本
    sh_content = f'''#!/bin/bash
echo "Starting RT Preview Server..."
echo ""
echo "RDC File: {rdc_path}"
echo "Server URL: http://127.0.0.1:{port}"
echo ""

# 尝试找到 qrenderdoc
RENDERDOC_PATH=$(which qrenderdoc 2>/dev/null)
if [ -z "$RENDERDOC_PATH" ]; then
    RENDERDOC_PATH="/usr/bin/qrenderdoc"
fi
if [ ! -x "$RENDERDOC_PATH" ]; then
    echo "[ERROR] RenderDoc not found. Please install RenderDoc."
    exit 1
fi

# 启动服务
"$RENDERDOC_PATH" --script "{Path(__file__).resolve()}" -- --rdc "{rdc_path}" --port {port}
'''
    
    # 写入文件
    bat_path = output_dir / "start_rt_server.bat"
    sh_path = output_dir / "start_rt_server.sh"
    
    bat_path.write_text(bat_content, encoding='utf-8')
    sh_path.write_text(sh_content, encoding='utf-8')
    
    # Unix 脚本添加执行权限
    try:
        os.chmod(sh_path, 0o755)
    except:
        pass
    
    return {"bat": str(bat_path), "sh": str(sh_path)}


# ============================================================
# CLI 入口
# ============================================================

def main():
    """命令行入口"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="RT Preview Server - On-demand Render Target snapshot service",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # 启动服务器
  qrenderdoc.exe --script rt_preview_server.py -- --rdc capture.rdc
  
  # 指定端口
  qrenderdoc.exe --script rt_preview_server.py -- --rdc capture.rdc --port 9000
  
  # 生成启动脚本
  python rt_preview_server.py --generate-script --rdc capture.rdc --output ./report/
        """
    )
    
    parser.add_argument("--rdc", required=True, help="Path to RDC capture file")
    parser.add_argument("--port", type=int, default=8765, help="Server port (default: 8765)")
    parser.add_argument("--host", default="127.0.0.1", help="Server host (default: 127.0.0.1)")
    parser.add_argument("--generate-script", action="store_true", help="Generate start scripts and exit")
    parser.add_argument("--output", help="Output directory for scripts (with --generate-script)")
    parser.add_argument("--mock", action="store_true", help="Run in mock mode (no renderdoc)")
    
    args = parser.parse_args()
    
    global FORCE_MOCK
    if args.mock:
        FORCE_MOCK = True

    if args.generate_script:
        # 仅生成启动脚本
        output_dir = args.output or Path(args.rdc).parent
        scripts = generate_start_script(args.rdc, output_dir, args.port)
        print(f"Generated: {scripts['bat']}")
        print(f"Generated: {scripts['sh']}")
        return 0
    
    # 启动服务器
    if not Path(args.rdc).exists():
        print(f"[ERROR] RDC file not found: {args.rdc}")
        return 1
    
    server = RTPreviewServer(args.rdc, args.port, args.host)
    server.start(blocking=True)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())

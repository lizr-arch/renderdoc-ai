#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
RT Preview Server (Standalone) - 独立运行的 RT 预览服务

必须在 RenderDoc 开发环境中运行：
    cd D:\\Code\\git\\renderdoc\\x64\\Development
    py -3.6 ..\\..\\scripts\\rdc_analyzer\\rt_server_standalone.py D:\\backup\\dayuanjing.rdc

功能：
    - HTTP 服务监听 localhost:8765
    - 按需导出指定 EID 的 Render Target 图像
    - 支持 CORS，可被 HTML 报告直接调用

版本：1.0.0
"""

import sys
import os
import json
import base64
import tempfile
import re
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse

# ============================================================
# RenderDoc 环境初始化
# ============================================================

def init_renderdoc_env():
    """初始化 RenderDoc 模块环境"""
    # 如果已经能导入，直接返回
    try:
        import renderdoc
        return True
    except ImportError:
        pass
    
    # 检查常见路径
    possible_paths = [
        # 当前目录（假设在 x64/Development 中运行）
        os.getcwd(),
        # 相对于脚本的路径
        os.path.join(os.path.dirname(__file__), "..", "..", "x64", "Development"),
        # 环境变量
        os.environ.get("RENDERDOC_PATH", ""),
    ]
    
    for path in possible_paths:
        if not path:
            continue
        path = os.path.abspath(path)
        pyd_file = os.path.join(path, "renderdoc.pyd")
        if os.path.exists(pyd_file):
            if path not in sys.path:
                sys.path.insert(0, path)
            try:
                import renderdoc
                print(f"[OK] Loaded renderdoc from: {path}")
                return True
            except ImportError as e:
                print(f"[WARN] Found renderdoc.pyd but import failed: {e}")
    
    return False


# ============================================================
# 全局状态
# ============================================================

class GlobalState:
    """全局共享状态"""
    rd = None           # renderdoc 模块
    cap = None          # CaptureFile
    controller = None   # ReplayController
    textures = {}       # resourceId -> TextureDescription
    current_eid = -1
    lock = threading.Lock()
    rdc_path = ""

g = GlobalState()


def init_replay(rdc_path):
    """初始化 Replay Controller"""
    import renderdoc as rd
    g.rd = rd
    g.rdc_path = rdc_path
    
    print(f"[INFO] Opening RDC: {rdc_path}")
    
    # 初始化 Replay API
    rd.InitialiseReplay(rd.GlobalEnvironment(), [])
    
    # 打开捕获文件
    g.cap = rd.OpenCaptureFile()
    result = g.cap.OpenFile(rdc_path, '', None)
    
    if result != rd.ResultCode.Succeeded:
        raise RuntimeError(f"Failed to open RDC: {result}")
    
    print("[INFO] Initializing Replay (requires GPU)...")
    status, g.controller = g.cap.OpenCapture(rd.ReplayOptions(), None)
    
    if status != rd.ResultCode.Succeeded:
        g.cap.Shutdown()
        raise RuntimeError(f"Failed to create Replay: {status}")
    
    # 缓存纹理列表
    tex_list = g.controller.GetTextures()
    for tex in tex_list:
        g.textures[tex.resourceId] = tex
    
    print(f"[OK] Replay ready. {len(g.textures)} textures cached.")


def get_rt_snapshot(eid, max_size=512):
    """
    获取指定事件的 Render Target 快照
    
    Returns: (base64_image, error_message)
    """
    with g.lock:
        try:
            rd = g.rd
            controller = g.controller
            
            # 跳转到指定事件
            if g.current_eid != eid:
                controller.SetFrameEvent(eid, True)
                g.current_eid = eid
            
            # 获取 Pipeline State
            state = controller.GetPipelineState()
            
            # 获取绑定的 RT
            rt_ids = get_bound_rt_ids(state)
            
            if not rt_ids:
                return None, "No Render Target bound at this event"
            
            # 导出第一个 RT
            rt_id = rt_ids[0]
            return export_texture_base64(rt_id, max_size), ""
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            return None, f"Export failed: {str(e)}"


def get_all_rt_snapshots(eid, max_size=256):
    """
    获取指定事件的所有 RT 快照
    
    Returns: ([{slot, image, name, format, ...}], error_message)
    """
    with g.lock:
        try:
            rd = g.rd
            controller = g.controller
            
            if g.current_eid != eid:
                controller.SetFrameEvent(eid, True)
                g.current_eid = eid
            
            state = controller.GetPipelineState()
            rt_ids = get_bound_rt_ids(state)
            
            results = []
            for i, rt_id in enumerate(rt_ids):
                tex = g.textures.get(rt_id)
                image = export_texture_base64(rt_id, max_size)
                
                results.append({
                    "slot": i,
                    "image": image,
                    "name": str(tex.name) if tex else f"RT_{rt_id}",
                    "format": str(tex.format.Name()) if tex else "Unknown",
                    "width": tex.width if tex else 0,
                    "height": tex.height if tex else 0,
                    "resourceId": int(rt_id)
                })
            
            return results, ""
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            return [], f"Export failed: {str(e)}"


def get_bound_rt_ids(state):
    """从 Pipeline State 获取绑定的 RT Resource IDs"""
    rt_ids = []
    rd = g.rd
    
    try:
        # 获取 Output Merger
        om = state.GetOutputMerger()
        
        # 尝试不同 API 的接口
        # D3D11/D3D12
        if hasattr(om, 'renderTargets'):
            for rt in om.renderTargets:
                res_id = None
                if hasattr(rt, 'resourceId'):
                    res_id = rt.resourceId
                elif hasattr(rt, 'resource'):
                    res_id = rt.resource
                
                if res_id and int(res_id) != 0:
                    rt_ids.append(res_id)
        
        # Vulkan - colorAttachments
        if not rt_ids and hasattr(om, 'colorAttachments'):
            for att in om.colorAttachments:
                if hasattr(att, 'imageResourceId') and int(att.imageResourceId) != 0:
                    rt_ids.append(att.imageResourceId)
        
        # OpenGL - drawFBO.colorAttachments
        if not rt_ids and hasattr(om, 'drawFBO'):
            fbo = om.drawFBO
            if hasattr(fbo, 'colorAttachments'):
                for att in fbo.colorAttachments:
                    if hasattr(att, 'resourceId') and int(att.resourceId) != 0:
                        rt_ids.append(att.resourceId)
        
        # Depth Target
        depth_id = None
        if hasattr(om, 'depthTarget'):
            dt = om.depthTarget
            if hasattr(dt, 'resourceId'):
                depth_id = dt.resourceId
            elif hasattr(dt, 'resource'):
                depth_id = dt.resource
        elif hasattr(om, 'depthAttachment'):
            da = om.depthAttachment
            if hasattr(da, 'imageResourceId'):
                depth_id = da.imageResourceId
        
        if depth_id and int(depth_id) != 0:
            rt_ids.append(depth_id)
            
    except Exception as e:
        print(f"[WARN] Failed to get RT from state: {e}")
    
    return rt_ids


def export_texture_base64(resource_id, max_size=512):
    """导出纹理为 Base64 PNG"""
    rd = g.rd
    controller = g.controller
    
    # 创建临时文件
    fd, temp_path = tempfile.mkstemp(suffix='.png')
    os.close(fd)
    
    try:
        # 配置保存参数
        save = rd.TextureSave()
        save.resourceId = resource_id
        save.destType = rd.FileType.PNG
        save.mip = 0
        save.slice.sliceIndex = 0
        
        # 执行保存
        result = controller.SaveTexture(save, temp_path)
        
        if result != rd.ResultCode.Succeeded:
            raise RuntimeError(f"SaveTexture failed: {result}")
        
        # 读取文件
        with open(temp_path, 'rb') as f:
            png_data = f.read()
        
        # 如果需要缩放
        tex = g.textures.get(resource_id)
        if tex and (tex.width > max_size or tex.height > max_size):
            try:
                from PIL import Image
                import io
                img = Image.open(io.BytesIO(png_data))
                img.thumbnail((max_size, max_size), Image.LANCZOS)
                buffer = io.BytesIO()
                img.save(buffer, format='PNG')
                png_data = buffer.getvalue()
            except ImportError:
                pass  # PIL 不可用，使用原图
        
        b64 = base64.b64encode(png_data).decode('ascii')
        return f"data:image/png;base64,{b64}"
        
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)


# ============================================================
# HTTP Server
# ============================================================

class RTHandler(BaseHTTPRequestHandler):
    """HTTP 请求处理器"""
    
    def log_message(self, format, *args):
        print(f"[HTTP] {self.address_string()} - {format % args}")
    
    def send_json(self, data, status=200):
        content = json.dumps(data, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', len(content))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Cache-Control', 'no-cache')
        self.end_headers()
        self.wfile.write(content)
    
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
    
    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        
        if path == '/' or path == '/status' or path == '/api/status':
            self.handle_status()
        elif path.startswith('/api/rt/'):
            self.handle_rt(path)
        elif path.startswith('/api/texture/'):
            self.handle_texture(path)
        else:
            self.send_json({"error": "Not found"}, 404)
    
    def handle_status(self):
        self.send_json({
            "success": True,
            "status": "running",
            "rdc_path": g.rdc_path,
            "texture_count": len(g.textures),
            "current_eid": g.current_eid
        })
    
    def handle_rt(self, path):
        # /api/rt/1234 or /api/rt/1234/all
        match = re.match(r'/api/rt/(\d+)(/all)?', path)
        if not match:
            self.send_json({"error": "Invalid path. Use /api/rt/{eid}"}, 400)
            return
        
        eid = int(match.group(1))
        get_all = match.group(2) == '/all'
        
        if get_all:
            results, error = get_all_rt_snapshots(eid)
            if error:
                self.send_json({"success": False, "error": error, "results": []})
            else:
                self.send_json({"success": True, "eid": eid, "results": results})
        else:
            image, error = get_rt_snapshot(eid)
            if error:
                self.send_json({"success": False, "error": error, "image": None})
            else:
                self.send_json({"success": True, "eid": eid, "image": image})
    
    def handle_texture(self, path):
        match = re.match(r'/api/texture/(\d+)', path)
        if not match:
            self.send_json({"error": "Invalid path"}, 400)
            return
        
        resource_id = int(match.group(1))
        
        with g.lock:
            try:
                if resource_id not in g.textures:
                    self.send_json({"success": False, "error": f"Texture {resource_id} not found"})
                    return
                
                image = export_texture_base64(resource_id)
                self.send_json({"success": True, "resourceId": resource_id, "image": image})
            except Exception as e:
                self.send_json({"success": False, "error": str(e)})


def run_server(host="127.0.0.1", port=8765):
    """启动 HTTP 服务器"""
    server = HTTPServer((host, port), RTHandler)
    print(f"\n[OK] RT Preview Server running at http://{host}:{port}")
    print("\nAPI Endpoints:")
    print(f"  GET /api/status          - Server status")
    print(f"  GET /api/rt/{{eid}}        - Get RT snapshot for event")
    print(f"  GET /api/rt/{{eid}}/all    - Get all RT snapshots")
    print(f"  GET /api/texture/{{id}}    - Get texture by resource ID")
    print("\nPress Ctrl+C to stop.\n")
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[INFO] Shutting down...")
    finally:
        server.shutdown()


# ============================================================
# Main
# ============================================================

def main():
    print("=" * 60)
    print("RT Preview Server (Standalone)")
    print("=" * 60)
    
    # 初始化 RenderDoc 环境
    if not init_renderdoc_env():
        print("[ERROR] Cannot load renderdoc module!")
        print("Please run this script from the RenderDoc Development directory:")
        print("  cd D:\\Code\\git\\renderdoc\\x64\\Development")
        print("  py -3.6 ..\\..\\scripts\\rdc_analyzer\\rt_server_standalone.py <rdc_file>")
        return 1
    
    # 解析参数
    import argparse
    parser = argparse.ArgumentParser(description="RT Preview Server")
    parser.add_argument("rdc_file", help="Path to RDC capture file")
    parser.add_argument("--port", type=int, default=8765, help="Server port (default: 8765)")
    parser.add_argument("--host", default="127.0.0.1", help="Server host")
    
    args = parser.parse_args()
    
    if not os.path.exists(args.rdc_file):
        print(f"[ERROR] RDC file not found: {args.rdc_file}")
        return 1
    
    # 初始化 Replay
    try:
        init_replay(args.rdc_file)
    except Exception as e:
        print(f"[ERROR] Failed to initialize replay: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    # 启动服务器
    try:
        run_server(args.host, args.port)
    finally:
        # 清理
        if g.controller:
            g.controller.Shutdown()
        if g.cap:
            g.cap.Shutdown()
        print("[OK] Cleanup complete.")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())

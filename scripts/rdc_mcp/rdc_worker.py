#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
RDC Worker - Python 3.6 兼容的 RenderDoc 操作脚本
通过 stdin/stdout 接收 JSON 命令，执行 RDC 操作并返回 JSON 结果

用法:
    py -3.6 rdc_worker.py < request.json > response.json
    
或者从命令行参数传入:
    py -3.6 rdc_worker.py '{"command": "open", "rdc_path": "..."}'
"""

from __future__ import print_function

import os
import sys
import json
import traceback

# 设置 renderdoc 加载路径
def _setup_renderdoc_path():
    """设置 renderdoc.pyd 的加载路径"""
    renderdoc_path = os.environ.get("RENDERDOC_PATH")
    
    if not renderdoc_path:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        possible_paths = [
            os.path.join(os.path.dirname(script_dir), "renderdoc"),
            os.path.join(os.path.dirname(os.path.dirname(script_dir)), "x64", "Development", "pymodules"),
        ]
        for path in possible_paths:
            if os.path.exists(os.path.join(path, "renderdoc.pyd")):
                renderdoc_path = path
                break
    
    if renderdoc_path and renderdoc_path not in sys.path:
        sys.path.insert(0, renderdoc_path)
        
        dll_dir = renderdoc_path
        if os.path.basename(renderdoc_path) == "pymodules":
            parent_dir = os.path.dirname(renderdoc_path)
            if os.path.exists(os.path.join(parent_dir, "renderdoc.dll")):
                dll_dir = parent_dir
        
        # Python 3.6 兼容方式
        os.environ['PATH'] = dll_dir + os.pathsep + os.environ.get('PATH', '')

_setup_renderdoc_path()

try:
    import renderdoc as rd
except ImportError as e:
    print(json.dumps({
        "success": False,
        "error": "Failed to load renderdoc: {}".format(str(e))
    }))
    sys.exit(1)


class RDCWorker(object):
    """RDC 操作工作器"""
    
    def __init__(self):
        self.capture = None
        self.controller = None
        self.rdc_path = None
    
    def open_capture(self, rdc_path):
        """打开 RDC 文件"""
        if not os.path.exists(rdc_path):
            return {"success": False, "error": "File not found: {}".format(rdc_path)}
        
        # 关闭之前的
        self.close_capture()
        
        self.capture = rd.OpenCaptureFile()
        result = self.capture.OpenFile(rdc_path, "", None)
        
        if result != rd.ResultCode.Succeeded:
            self.capture.Shutdown()
            self.capture = None
            return {"success": False, "error": "Failed to open RDC: {}".format(str(result))}
        
        # 创建 ReplayController
        status, controller = self.capture.OpenCapture(rd.ReplayOptions(), None)
        
        if status != rd.ResultCode.Succeeded or not controller:
            self.capture.Shutdown()
            self.capture = None
            return {"success": False, "error": "Failed to create ReplayController: {}".format(str(status))}
        
        self.controller = controller
        
        self.rdc_path = rdc_path
        
        # 获取基本信息
        info = self._get_capture_info()
        return {"success": True, "info": info}
    
    def close_capture(self):
        """关闭当前打开的 RDC"""
        if self.controller:
            self.controller.Shutdown()
            self.controller = None
        if self.capture:
            self.capture.Shutdown()
            self.capture = None
        self.rdc_path = None
        return {"success": True}
    
    def _get_capture_info(self):
        """获取捕获信息"""
        if not self.capture:
            return None
        
        info = {
            "rdc_path": self.rdc_path,
            "api": "Unknown",
            "machine": "",
            "driver": "",
        }
        
        # 使用 CaptureFile 的方法获取信息
        try:
            info["api"] = self.capture.DriverName()
            info["machine"] = self.capture.RecordedMachineIdent()
        except Exception:
            pass
        
        return info
    
    def get_actions(self, max_count=100):
        """获取绘制调用列表"""
        if not self.controller:
            return {"success": False, "error": "No capture open"}
        
        actions = []
        root_actions = self.controller.GetRootActions()
        
        def _collect_actions(action_list, depth=0):
            for action in action_list:
                if len(actions) >= max_count:
                    break
                
                actions.append({
                    "eventId": action.eventId,
                    "name": action.GetName(self.controller.GetStructuredFile()),
                    "flags": str(action.flags),
                    "numIndices": action.numIndices,
                    "numInstances": action.numInstances,
                    "depth": depth,
                })
                
                if action.children:
                    _collect_actions(action.children, depth + 1)
        
        _collect_actions(root_actions)
        return {"success": True, "actions": actions, "total": len(actions)}
    
    def get_textures(self, max_count=50):
        """获取纹理列表"""
        if not self.controller:
            return {"success": False, "error": "No capture open"}
        
        textures = []
        for tex in self.controller.GetTextures():
            if len(textures) >= max_count:
                break
            
            textures.append({
                "resourceId": str(tex.resourceId),
                "name": tex.name if hasattr(tex, 'name') else "",
                "width": tex.width,
                "height": tex.height,
                "depth": tex.depth,
                "format": str(tex.format.Name()) if hasattr(tex.format, 'Name') else str(tex.format),
                "mips": tex.mips,
                "arraysize": tex.arraysize,
            })
        
        return {"success": True, "textures": textures, "total": len(textures)}
    
    def get_buffers(self, max_count=50):
        """获取缓冲区列表"""
        if not self.controller:
            return {"success": False, "error": "No capture open"}
        
        buffers = []
        for buf in self.controller.GetBuffers():
            if len(buffers) >= max_count:
                break
            
            buffers.append({
                "resourceId": str(buf.resourceId),
                "length": buf.length,
            })
        
        return {"success": True, "buffers": buffers, "total": len(buffers)}
    
    def analyze(self, output_dir=None, platform="android"):
        """调用 rdc_analyzer 进行分析"""
        if not self.rdc_path:
            return {"success": False, "error": "No capture open"}
        
        # 尝试导入 rdc_analyzer
        script_dir = os.path.dirname(os.path.abspath(__file__))
        analyzer_path = os.path.join(os.path.dirname(script_dir), "rdc_analyzer")
        
        if analyzer_path not in sys.path:
            sys.path.insert(0, analyzer_path)
        
        try:
            from main import analyze, AnalysisOptions
        except ImportError:
            return {"success": False, "error": "rdc_analyzer not found at {}".format(analyzer_path)}
        
        # 准备输出目录
        if not output_dir:
            output_dir = os.path.join(os.path.dirname(self.rdc_path), "analysis_output")
        
        os.makedirs(output_dir, exist_ok=True)
        
        # 执行分析
        try:
            result = analyze(self.rdc_path, output_dir, platform=platform)
            
            # 转换为可序列化的格式
            summary = {
                "total_issues": result.total_issues if hasattr(result, 'total_issues') else 0,
                "critical_count": result.critical_count if hasattr(result, 'critical_count') else 0,
                "warning_count": result.warning_count if hasattr(result, 'warning_count') else 0,
                "info_count": result.info_count if hasattr(result, 'info_count') else 0,
                "output_dir": output_dir,
            }
            
            return {"success": True, "summary": summary}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def execute(self, request):
        """执行请求"""
        command = request.get("command", "")
        
        # 如果提供了 rdc_path 且当前未打开或打开的是不同文件，先打开
        rdc_path = request.get("rdc_path", "")
        if rdc_path and command not in ["open", "close", "ping"]:
            if self.rdc_path != rdc_path:
                open_result = self.open_capture(rdc_path)
                if not open_result.get("success"):
                    return open_result
        
        if command == "open":
            return self.open_capture(request.get("rdc_path", ""))
        elif command == "close":
            return self.close_capture()
        elif command == "get_actions":
            return self.get_actions(request.get("max_count", 100))
        elif command == "get_textures":
            return self.get_textures(request.get("max_count", 50))
        elif command == "get_buffers":
            return self.get_buffers(request.get("max_count", 50))
        elif command == "analyze":
            return self.analyze(
                request.get("output_dir"),
                request.get("platform", "android")
            )
        elif command == "ping":
            return {"success": True, "message": "pong", "python_version": sys.version}
        else:
            return {"success": False, "error": "Unknown command: {}".format(command)}


def main():
    """主入口"""
    worker = RDCWorker()
    
    # 从命令行参数或 stdin 读取请求
    if len(sys.argv) > 1:
        request_json = sys.argv[1]
    else:
        request_json = sys.stdin.read()
    
    try:
        request = json.loads(request_json)
    except (ValueError, TypeError) as e:
        print(json.dumps({"success": False, "error": "Invalid JSON: {}".format(str(e))}))
        sys.exit(1)
    
    try:
        result = worker.execute(request)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except Exception as e:
        print(json.dumps({
            "success": False, 
            "error": str(e),
            "traceback": traceback.format_exc()
        }))
        sys.exit(1)
    finally:
        worker.close_capture()


if __name__ == "__main__":
    main()

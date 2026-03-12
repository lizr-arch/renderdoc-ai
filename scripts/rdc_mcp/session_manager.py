"""
RDC MCP Server - Session Manager
管理多个 RDC 会话，每个会话对应一个打开的 RDC 文件
"""

import os
import sys
import uuid
from dataclasses import dataclass, field
from typing import Optional, Any, Dict, List

# 动态添加 renderdoc 模块路径
def _setup_renderdoc_path():
    """设置 renderdoc.pyd 的加载路径"""
    # 优先使用环境变量
    renderdoc_path = os.environ.get("RENDERDOC_PATH")
    
    if not renderdoc_path:
        # 默认路径：脚本目录的上级（分发包结构）
        script_dir = os.path.dirname(os.path.abspath(__file__))
        possible_paths = [
            # 分发包结构: RDC-AI-Analyzer/rdc_mcp/ -> RDC-AI-Analyzer/renderdoc/
            os.path.join(os.path.dirname(script_dir), "renderdoc"),
            # 开发环境: scripts/rdc_mcp/ -> x64/Development/pymodules/
            os.path.join(os.path.dirname(os.path.dirname(script_dir)), "x64", "Development", "pymodules"),
        ]
        for path in possible_paths:
            if os.path.exists(os.path.join(path, "renderdoc.pyd")):
                renderdoc_path = path
                break
    
    if renderdoc_path and renderdoc_path not in sys.path:
        sys.path.insert(0, renderdoc_path)
        
        # 设置 DLL 搜索路径
        # 如果是 pymodules 子目录，需要添加父目录（renderdoc.dll 所在位置）
        dll_dir = renderdoc_path
        if os.path.basename(renderdoc_path) == "pymodules":
            parent_dir = os.path.dirname(renderdoc_path)
            if os.path.exists(os.path.join(parent_dir, "renderdoc.dll")):
                dll_dir = parent_dir
        
        # Python 3.8+ 使用 add_dll_directory
        if hasattr(os, 'add_dll_directory'):
            os.add_dll_directory(dll_dir)
            if dll_dir != renderdoc_path:
                os.add_dll_directory(renderdoc_path)
        else:
            # Python 3.6/3.7 使用 PATH 环境变量
            os.environ['PATH'] = dll_dir + os.pathsep + os.environ.get('PATH', '')

_setup_renderdoc_path()

try:
    import renderdoc as rd
except ImportError as e:
    raise ImportError(
        f"无法加载 renderdoc 模块: {e}\n"
        "请设置环境变量 RENDERDOC_PATH 指向包含 renderdoc.pyd 的目录"
    )


@dataclass
class Session:
    """单个 RDC 会话"""
    session_id: str
    rdc_path: str
    capture: Any  # rd.CaptureFile
    controller: Any  # rd.ReplayController
    
    # 缓存的分析结果
    analysis_result: Optional[Any] = None
    
    # 元数据
    api_name: str = ""
    device_name: str = ""
    
    def shutdown(self):
        """关闭会话，释放资源"""
        if self.controller:
            self.controller.Shutdown()
            self.controller = None
        if self.capture:
            self.capture.Shutdown()
            self.capture = None


class SessionManager:
    """会话管理器"""
    
    def __init__(self):
        self._sessions: Dict[str, Session] = {}
    
    def create_session(self, rdc_path: str) -> Session:
        """
        打开 RDC 文件并创建会话
        
        Args:
            rdc_path: RDC 文件路径
            
        Returns:
            Session: 新创建的会话
            
        Raises:
            FileNotFoundError: 文件不存在
            RuntimeError: 打开失败
        """
        # 验证文件存在
        if not os.path.exists(rdc_path):
            raise FileNotFoundError(f"RDC 文件不存在: {rdc_path}")
        
        # 打开 CaptureFile
        cap = rd.OpenCaptureFile()
        result = cap.OpenFile(rdc_path, "", None)
        
        if result != rd.ResultCode.Succeeded:
            cap.Shutdown()
            raise RuntimeError(f"打开 RDC 文件失败: {result.str()}")
        
        # 创建 ReplayController
        status = cap.OpenCapture(rd.ReplayOptions(), None)
        
        if not status:
            cap.Shutdown()
            raise RuntimeError("创建 ReplayController 失败")
        
        controller = status
        
        # 生成会话 ID
        session_id = str(uuid.uuid4())[:8]
        
        # 获取 API 信息
        api_name = "Unknown"
        device_name = "Unknown"
        
        api_props = cap.APIProps
        if api_props:
            api_name = api_props.pipelineType.name if hasattr(api_props, 'pipelineType') else "Unknown"
        
        # 尝试从 structured file 获取设备信息
        sd_file = controller.GetStructuredFile()
        if sd_file and sd_file.chunks:
            for chunk in sd_file.chunks:
                if "driver" in chunk.name.lower():
                    device_name = chunk.name
                    break
        
        # 创建会话
        session = Session(
            session_id=session_id,
            rdc_path=rdc_path,
            capture=cap,
            controller=controller,
            api_name=api_name,
            device_name=device_name,
        )
        
        self._sessions[session_id] = session
        return session
    
    def get_session(self, session_id: str) -> Optional[Session]:
        """获取会话"""
        return self._sessions.get(session_id)
    
    def close_session(self, session_id: str) -> bool:
        """关闭并移除会话"""
        session = self._sessions.pop(session_id, None)
        if session:
            session.shutdown()
            return True
        return False
    
    def list_sessions(self) -> List[str]:
        """列出所有会话 ID"""
        return list(self._sessions.keys())
    
    def close_all(self):
        """关闭所有会话"""
        for session_id in list(self._sessions.keys()):
            self.close_session(session_id)


# 全局会话管理器实例
_manager: Optional[SessionManager] = None


def get_session_manager() -> SessionManager:
    """获取全局会话管理器"""
    global _manager
    if _manager is None:
        _manager = SessionManager()
    return _manager

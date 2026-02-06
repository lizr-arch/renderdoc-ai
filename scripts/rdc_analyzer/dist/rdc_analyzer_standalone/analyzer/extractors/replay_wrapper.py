"""
RenderDoc ReplayController 封装
================================

封装 RenderDoc Python API 的回放控制器功能

提供:
1. 安全的控制器生命周期管理
2. 统一的状态查询接口
3. 资源数据访问
4. 着色器反射信息
"""

import logging
from contextlib import contextmanager
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import Any, Callable, Dict, Generator, List, Optional, Tuple, Union

# 尝试导入 renderdoc 模块
try:
    import renderdoc as rd
    RENDERDOC_AVAILABLE = True
except ImportError:
    rd = None  # type: ignore
    RENDERDOC_AVAILABLE = False

from ..core.pipeline_state import (
    ResourceBinding,
    ShaderBindings,
    SamplerInfo,
    RenderTargetInfo,
    DepthStencilInfo,
    ViewportInfo,
    ScissorRect,
    BlendStateInfo,
    RasterizerStateInfo,
    ResourceType,
    ShaderStage,
    PrimitiveTopology,
    CullMode,
    FillMode,
)


logger = logging.getLogger(__name__)


# =============================================================================
# 异常类型
# =============================================================================

class ReplayError(Exception):
    """回放控制器错误基类"""
    pass


class RenderDocNotAvailableError(ReplayError):
    """RenderDoc 模块不可用"""
    def __init__(self):
        super().__init__(
            "RenderDoc Python module not available. "
            "Make sure to run this script with RenderDoc's Python environment."
        )


class CaptureLoadError(ReplayError):
    """加载截帧文件失败"""
    def __init__(self, path: str, reason: str):
        self.path = path
        self.reason = reason
        super().__init__(f"Failed to load capture '{path}': {reason}")


class ReplayInitError(ReplayError):
    """初始化回放失败"""
    pass


# =============================================================================
# 辅助函数
# =============================================================================

def ensure_renderdoc_available():
    """确保 RenderDoc 模块可用"""
    if not RENDERDOC_AVAILABLE:
        raise RenderDocNotAvailableError()


# =============================================================================
# 回放控制器封装
# =============================================================================

@dataclass
class CaptureInfo:
    """截帧信息"""
    file_path: str
    api: str = ""
    timestamp: str = ""
    driver: str = ""
    machine_ident: str = ""
    
    # 统计信息
    total_events: int = 0
    total_actions: int = 0  # Draw/Dispatch/Clear 等


class ReplayWrapper:
    """
    RenderDoc ReplayController 封装类
    
    提供安全的资源管理和统一的状态查询接口
    
    使用方式（上下文管理器）:
        with ReplayWrapper.open("capture.rdc") as replay:
            state = replay.get_pipeline_state(event_id)
            
    使用方式（手动管理）:
        replay = ReplayWrapper("capture.rdc")
        replay.open()
        try:
            state = replay.get_pipeline_state(event_id)
        finally:
            replay.close()
    """
    
    def __init__(self, rdc_path: Union[str, Path]):
        """
        初始化回放封装器
        
        Args:
            rdc_path: RDC 文件路径
        """
        ensure_renderdoc_available()
        
        self.rdc_path = Path(rdc_path)
        if not self.rdc_path.exists():
            raise FileNotFoundError(f"RDC file not found: {rdc_path}")
        
        # 内部状态
        self._cap: Optional[Any] = None  # rd.CaptureFile
        self._controller: Optional[Any] = None  # rd.ReplayController
        self._is_open: bool = False
        
        # 缓存
        self._api_type: Optional[str] = None
        self._resources_cache: Dict[int, Any] = {}
        self._textures_cache: Dict[int, Any] = {}
        self._buffers_cache: Dict[int, Any] = {}
    
    @classmethod
    @contextmanager
    def open(cls, rdc_path: Union[str, Path]) -> Generator['ReplayWrapper', None, None]:
        """
        上下文管理器方式打开 RDC 文件
        
        Args:
            rdc_path: RDC 文件路径
            
        Yields:
            ReplayWrapper 实例
        """
        wrapper = cls(rdc_path)
        wrapper._open()
        try:
            yield wrapper
        finally:
            wrapper.close()
    
    def _open(self):
        """打开并初始化回放"""
        if self._is_open:
            return
        
        logger.info(f"Opening capture: {self.rdc_path}")
        
        # 创建 CaptureFile
        self._cap = rd.OpenCaptureFile()
        
        # 打开文件
        result = self._cap.OpenFile(str(self.rdc_path), '', None)
        if result != rd.ResultCode.Succeeded:
            raise CaptureLoadError(str(self.rdc_path), f"OpenFile failed: {result}")
        
        # 检查 API 类型
        api = self._cap.LocalReplaySupport()
        if api == rd.ReplaySupport.Unsupported:
            raise CaptureLoadError(
                str(self.rdc_path), 
                "Capture API is not supported for local replay"
            )
        
        # 初始化回放
        status, controller = self._cap.OpenCapture(rd.ReplayOptions(), None)
        if status != rd.ResultCode.Succeeded:
            raise ReplayInitError(f"OpenCapture failed: {status}")
        
        self._controller = controller
        self._is_open = True
        
        # 获取 API 类型
        self._api_type = self._get_api_name()
        
        logger.info(f"Capture opened successfully. API: {self._api_type}")
    
    def close(self):
        """关闭回放并释放资源"""
        if not self._is_open:
            return
        
        logger.info("Closing capture...")
        
        if self._controller:
            self._controller.Shutdown()
            self._controller = None
        
        if self._cap:
            self._cap.Shutdown()
            self._cap = None
        
        self._is_open = False
        self._clear_cache()
    
    def _clear_cache(self):
        """清除缓存"""
        self._resources_cache.clear()
        self._textures_cache.clear()
        self._buffers_cache.clear()
    
    @property
    def controller(self) -> Any:
        """获取底层 ReplayController"""
        if not self._is_open or not self._controller:
            raise ReplayError("Replay not open")
        return self._controller
    
    @property
    def api_type(self) -> str:
        """获取图形 API 类型"""
        return self._api_type or "Unknown"
    
    @property
    def is_open(self) -> bool:
        """是否已打开"""
        return self._is_open
    
    # -------------------------------------------------------------------------
    # 基本信息
    # -------------------------------------------------------------------------
    
    def _get_api_name(self) -> str:
        """获取 API 名称"""
        api_props = self._controller.GetAPIProperties()
        
        # 根据 API 类型返回名称
        api_type = api_props.pipelineType
        
        if hasattr(rd.GraphicsAPI, 'D3D11') and api_type == rd.GraphicsAPI.D3D11:
            return "D3D11"
        elif hasattr(rd.GraphicsAPI, 'D3D12') and api_type == rd.GraphicsAPI.D3D12:
            return "D3D12"
        elif hasattr(rd.GraphicsAPI, 'OpenGL') and api_type == rd.GraphicsAPI.OpenGL:
            return "OpenGL"
        elif hasattr(rd.GraphicsAPI, 'Vulkan') and api_type == rd.GraphicsAPI.Vulkan:
            return "Vulkan"
        else:
            return "Unknown"
    
    def get_capture_info(self) -> CaptureInfo:
        """获取截帧信息"""
        info = CaptureInfo(file_path=str(self.rdc_path))
        info.api = self.api_type
        
        # 统计动作数量
        root_actions = self._controller.GetRootActions()
        
        def count_actions(actions) -> Tuple[int, int]:
            total = 0
            actionable = 0
            for action in actions:
                total += 1
                if hasattr(action, 'flags'):
                    flags = action.flags
                    if (hasattr(flags, 'Drawcall') or hasattr(flags, 'Dispatch') or 
                        hasattr(flags, 'Clear') or hasattr(flags, 'Copy')):
                        actionable += 1
                children = getattr(action, 'children', [])
                if children:
                    ct, ca = count_actions(children)
                    total += ct
                    actionable += ca
            return total, actionable
        
        info.total_events, info.total_actions = count_actions(root_actions)
        
        return info
    
    def get_root_actions(self) -> List[Any]:
        """获取根动作列表"""
        return self._controller.GetRootActions()
    
    # -------------------------------------------------------------------------
    # 事件导航
    # -------------------------------------------------------------------------
    
    def move_to_event(self, event_id: int):
        """
        移动到指定事件
        
        Args:
            event_id: 事件 ID
        """
        self._controller.SetFrameEvent(event_id, True)
    
    def get_current_event_id(self) -> int:
        """获取当前事件 ID"""
        return self._controller.GetCurrentEventID()
    
    # -------------------------------------------------------------------------
    # 管线状态查询
    # -------------------------------------------------------------------------
    
    def get_d3d11_state(self) -> Any:
        """获取 D3D11 管线状态"""
        state = self._controller.GetPipelineState()
        return state.GetD3D11()
    
    def get_d3d12_state(self) -> Any:
        """获取 D3D12 管线状态"""
        state = self._controller.GetPipelineState()
        return state.GetD3D12()
    
    def get_vulkan_state(self) -> Any:
        """获取 Vulkan 管线状态"""
        state = self._controller.GetPipelineState()
        return state.GetVulkan()
    
    def get_opengl_state(self) -> Any:
        """获取 OpenGL 管线状态"""
        state = self._controller.GetPipelineState()
        return state.GetOpenGL()
    
    def get_pipeline_state(self) -> Any:
        """获取当前 API 的管线状态"""
        api = self.api_type
        if api == "D3D11":
            return self.get_d3d11_state()
        elif api == "D3D12":
            return self.get_d3d12_state()
        elif api == "Vulkan":
            return self.get_vulkan_state()
        elif api == "OpenGL":
            return self.get_opengl_state()
        else:
            raise ReplayError(f"Unknown API type: {api}")
    
    # -------------------------------------------------------------------------
    # 资源查询
    # -------------------------------------------------------------------------
    
    def get_resources(self) -> List[Any]:
        """获取所有资源列表"""
        return self._controller.GetResources()
    
    def get_resource(self, resource_id: int) -> Optional[Any]:
        """
        获取资源描述
        
        Args:
            resource_id: 资源 ID
            
        Returns:
            ResourceDescription 或 None
        """
        if resource_id in self._resources_cache:
            return self._resources_cache[resource_id]
        
        # 遍历资源列表查找
        resources = self.get_resources()
        for res in resources:
            if res.resourceId == resource_id:
                self._resources_cache[resource_id] = res
                return res
        
        return None
    
    def get_texture_description(self, resource_id: int) -> Optional[Any]:
        """
        获取纹理描述
        
        Args:
            resource_id: 纹理资源 ID
            
        Returns:
            TextureDescription 或 None
        """
        if resource_id in self._textures_cache:
            return self._textures_cache[resource_id]
        
        textures = self._controller.GetTextures()
        for tex in textures:
            if tex.resourceId == resource_id:
                self._textures_cache[resource_id] = tex
                return tex
        
        return None
    
    def get_buffer_description(self, resource_id: int) -> Optional[Any]:
        """
        获取缓冲区描述
        
        Args:
            resource_id: 缓冲区资源 ID
            
        Returns:
            BufferDescription 或 None
        """
        if resource_id in self._buffers_cache:
            return self._buffers_cache[resource_id]
        
        buffers = self._controller.GetBuffers()
        for buf in buffers:
            if buf.resourceId == resource_id:
                self._buffers_cache[resource_id] = buf
                return buf
        
        return None
    
    def get_resource_name(self, resource_id: int) -> str:
        """
        获取资源名称
        
        Args:
            resource_id: 资源 ID
            
        Returns:
            资源名称或空字符串
        """
        res = self.get_resource(resource_id)
        if res:
            return res.name
        return ""
    
    # -------------------------------------------------------------------------
    # 着色器查询
    # -------------------------------------------------------------------------
    
    def get_shader_reflection(self, shader_id: int, 
                              entry_point: str = "") -> Optional[Any]:
        """
        获取着色器反射信息
        
        Args:
            shader_id: 着色器资源 ID
            entry_point: 入口点名称（可选）
            
        Returns:
            ShaderReflection 或 None
        """
        if shader_id == 0:
            return None
        
        try:
            # D3D11/D3D12
            refl = self._controller.GetShader(
                rd.ResourceId(shader_id), 
                rd.ShaderEntryPoint(entry_point, rd.ShaderStage.Vertex)
            )
            return refl
        except Exception as e:
            logger.debug(f"Failed to get shader reflection for {shader_id}: {e}")
            return None
    
    def get_shader_debug_info(self, shader_id: int) -> Optional[Any]:
        """
        获取着色器调试信息
        
        Args:
            shader_id: 着色器资源 ID
            
        Returns:
            ShaderDebugInfo 或 None
        """
        if shader_id == 0:
            return None
        
        try:
            return self._controller.GetDebugInfo(rd.ResourceId(shader_id))
        except Exception as e:
            logger.debug(f"Failed to get shader debug info for {shader_id}: {e}")
            return None
    
    # -------------------------------------------------------------------------
    # 数据读取
    # -------------------------------------------------------------------------
    
    def get_buffer_data(self, buffer_id: int, 
                        offset: int = 0, 
                        length: int = 0) -> bytes:
        """
        读取缓冲区数据
        
        Args:
            buffer_id: 缓冲区资源 ID
            offset: 起始偏移
            length: 读取长度（0 表示全部）
            
        Returns:
            字节数据
        """
        return self._controller.GetBufferData(
            rd.ResourceId(buffer_id), 
            offset, 
            length
        )
    
    def get_texture_data(self, texture_id: int,
                         subresource: int = 0) -> bytes:
        """
        读取纹理数据
        
        Args:
            texture_id: 纹理资源 ID
            subresource: 子资源索引
            
        Returns:
            字节数据
        """
        # 获取纹理描述以确定格式
        tex = self.get_texture_description(texture_id)
        if not tex:
            return b''
        
        return self._controller.GetTextureData(
            rd.ResourceId(texture_id),
            rd.Subresource(subresource, 0)
        )
    
    # -------------------------------------------------------------------------
    # GPU 计时
    # -------------------------------------------------------------------------
    
    def get_action_timing(self, event_id: int) -> float:
        """
        获取动作的 GPU 执行时间
        
        Args:
            event_id: 事件 ID
            
        Returns:
            执行时间（秒），不可用时返回 0
        """
        # 获取计时器结果
        # 注意：这需要在支持 GPU 计时的硬件上运行
        try:
            actions = self._controller.GetActionInfo(event_id)
            if actions and hasattr(actions, 'duration'):
                return actions.duration
        except Exception:
            pass
        return 0.0
    
    # -------------------------------------------------------------------------
    # 便捷方法
    # -------------------------------------------------------------------------
    
    def iter_actions(self, root_actions: Optional[List[Any]] = None
                     ) -> Generator[Any, None, None]:
        """
        迭代所有动作（深度优先）
        
        Yields:
            DrawcallDescription 对象
        """
        if root_actions is None:
            root_actions = self.get_root_actions()
        
        for action in root_actions:
            yield action
            children = getattr(action, 'children', [])
            if children:
                yield from self.iter_actions(children)
    
    def iter_draw_calls(self) -> Generator[Any, None, None]:
        """
        只迭代绘制调用
        
        Yields:
            具有 Drawcall flag 的 DrawcallDescription
        """
        for action in self.iter_actions():
            if hasattr(action, 'flags'):
                flags = action.flags
                if hasattr(flags, 'Drawcall') and flags.Drawcall:
                    yield action
    
    def iter_dispatches(self) -> Generator[Any, None, None]:
        """
        只迭代计算调度
        
        Yields:
            具有 Dispatch flag 的 DrawcallDescription
        """
        for action in self.iter_actions():
            if hasattr(action, 'flags'):
                flags = action.flags
                if hasattr(flags, 'Dispatch') and flags.Dispatch:
                    yield action


# =============================================================================
# Mock 类（用于测试）
# =============================================================================

class MockReplayWrapper:
    """
    模拟的 ReplayWrapper，用于测试和开发
    
    不需要实际的 RDC 文件，返回虚假数据
    """
    
    def __init__(self, api_type: str = "D3D11"):
        self._api_type = api_type
        self._is_open = False
        self._current_event = 0
    
    @classmethod
    @contextmanager
    def open(cls, rdc_path: Union[str, Path] = "", 
             api_type: str = "D3D11") -> Generator['MockReplayWrapper', None, None]:
        wrapper = cls(api_type)
        wrapper._is_open = True
        try:
            yield wrapper
        finally:
            wrapper._is_open = False
    
    @property
    def api_type(self) -> str:
        return self._api_type
    
    @property
    def is_open(self) -> bool:
        return self._is_open
    
    def close(self):
        self._is_open = False
    
    def move_to_event(self, event_id: int):
        self._current_event = event_id
    
    def get_current_event_id(self) -> int:
        return self._current_event
    
    def get_capture_info(self) -> CaptureInfo:
        return CaptureInfo(
            file_path="mock_capture.rdc",
            api=self._api_type,
            total_events=100,
            total_actions=50,
        )
    
    def get_root_actions(self) -> List[Any]:
        """返回模拟的动作列表"""
        return []
    
    def get_pipeline_state(self) -> Any:
        """返回 None，子类或测试可以覆盖"""
        return None
    
    def get_resources(self) -> List[Any]:
        return []
    
    def get_resource(self, resource_id: int) -> Optional[Any]:
        return None
    
    def get_resource_name(self, resource_id: int) -> str:
        return f"Resource_{resource_id}"
    
    def get_texture_description(self, resource_id: int) -> Optional[Any]:
        return None
    
    def get_buffer_description(self, resource_id: int) -> Optional[Any]:
        return None

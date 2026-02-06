"""
RenderDoc API 解析器
====================

使用 RenderDoc Python API 解析 RDC 文件。
需要在 RenderDoc 环境中运行，或已安装 renderdoc 模块。
"""

import os
from typing import Optional, List, Any, Dict
from .base import BaseParser
from ..core.context import ParsedData


class APIParser(BaseParser):
    """
    RenderDoc API 解析器
    
    使用 renderdoc Python 模块直接访问 RDC 数据。
    提供最完整的数据访问能力。
    """
    
    _rd_module: Optional[Any] = None
    _controller: Optional[Any] = None
    _cap: Optional[Any] = None
    
    def __init__(self, rdc_path: str):
        super().__init__(rdc_path)
        self._controller = None
        self._cap = None
    
    @classmethod
    def _try_import_rd(cls) -> Optional[Any]:
        """尝试导入 renderdoc 模块"""
        if cls._rd_module is not None:
            return cls._rd_module
        
        try:
            import renderdoc as rd
            cls._rd_module = rd
            return rd
        except ImportError:
            return None
    
    def is_available(self) -> bool:
        """检查 RenderDoc API 是否可用"""
        return self._try_import_rd() is not None
    
    def parse(self) -> ParsedData:
        """
        使用 RenderDoc API 解析 RDC 文件
        
        Returns:
            解析后的数据
        """
        rd = self._try_import_rd()
        if rd is None:
            raise RuntimeError("RenderDoc module not available")
        
        # 打开 Capture 文件
        self._cap = rd.OpenCaptureFile()
        status = self._cap.OpenFile(self.rdc_path, '', None)
        
        if status != rd.ResultCode.Succeeded:
            raise RuntimeError(f"Failed to open RDC file: {status}")
        
        # 获取 ReplayController
        status, self._controller = self._cap.OpenCapture(
            rd.ReplayOptions(), None
        )
        
        if status != rd.ResultCode.Succeeded:
            raise RuntimeError(f"Failed to open capture for replay: {status}")
        
        # 获取 Actions
        actions = self._controller.GetRootActions()
        
        # 构建元数据
        meta = self._build_meta(rd)
        
        return ParsedData(
            meta=meta,
            controller=self._controller,
            actions=self._flatten_actions(actions),
        )
    
    def _build_meta(self, rd) -> Dict[str, Any]:
        """构建元数据"""
        meta = {
            "source_file": os.path.basename(self.rdc_path),
            "parser": "api",
            "api_version": getattr(rd, 'GetVersionString', lambda: 'unknown')(),
        }
        
        # 尝试获取更多信息
        if self._controller:
            try:
                props = self._controller.GetAPIProperties()
                meta["graphics_api"] = str(props.pipelineType)
            except Exception:
                pass
        
        return meta
    
    def _flatten_actions(self, actions: List[Any]) -> List[Any]:
        """
        递归展平 Action 树
        
        RenderDoc 的 Actions 是树形结构 (Markers 包含子 Actions)
        """
        result = []
        
        for action in actions:
            result.append(action)
            if hasattr(action, 'children') and action.children:
                result.extend(self._flatten_actions(action.children))
        
        return result
    
    def close(self):
        """关闭 Capture 文件"""
        if self._controller:
            self._controller.Shutdown()
            self._controller = None
        if self._cap:
            self._cap.Close()
            self._cap = None
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False

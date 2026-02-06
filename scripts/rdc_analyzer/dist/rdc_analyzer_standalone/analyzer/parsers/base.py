"""
解析器基类
==========

定义解析器的统一接口。
"""

from abc import ABC, abstractmethod
from typing import Optional
from ..core.context import AnalysisContext, ParsedData


class BaseParser(ABC):
    """
    解析器基类
    
    职责: 读取 RDC 文件，提取原始数据到 ParsedData
    """
    
    def __init__(self, rdc_path: str):
        """
        初始化解析器
        
        Args:
            rdc_path: RDC 文件路径
        """
        self.rdc_path = rdc_path
    
    @abstractmethod
    def parse(self) -> ParsedData:
        """
        解析 RDC 文件
        
        Returns:
            解析后的数据
        """
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """
        检查解析器是否可用
        
        Returns:
            True 如果解析器可以使用
        """
        pass
    
    def create_context(self, platform: str = "pc") -> AnalysisContext:
        """
        创建分析上下文
        
        Args:
            platform: 目标平台
            
        Returns:
            包含解析数据的分析上下文
        """
        from ..config import get_thresholds
        
        parsed = self.parse()
        return AnalysisContext(
            parsed=parsed,
            platform=platform,
            thresholds=get_thresholds(platform),
        )

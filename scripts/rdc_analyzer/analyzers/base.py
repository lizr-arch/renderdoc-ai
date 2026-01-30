"""
分析器基类
==========

定义分析器的统一接口。
"""

from abc import ABC, abstractmethod
from typing import List
from ..core.context import AnalysisContext
from ..core.types import Issue


class BaseAnalyzer(ABC):
    """
    分析器基类
    
    职责: 分析 AnalysisContext 中的数据，填充分析结果
    
    设计原则:
    - 单一职责: 每个分析器只负责一个分析维度
    - 依赖注入: 通过 AnalysisContext 获取输入数据
    - 可组合: 多个分析器可以串行执行
    """
    
    # 分析器名称 (子类覆盖)
    name: str = "base"
    
    # 分析器描述
    description: str = "Base analyzer"
    
    # 依赖的其他分析器 (执行顺序)
    dependencies: List[str] = []
    
    def __init__(self, context: AnalysisContext):
        """
        初始化分析器
        
        Args:
            context: 分析上下文
        """
        self.context = context
    
    @abstractmethod
    def analyze(self) -> None:
        """
        执行分析
        
        分析结果应写入 self.context 的相应字段
        """
        pass
    
    def is_api_mode(self) -> bool:
        """检查是否为 API 模式"""
        return self.context.parsed.controller is not None
    
    def is_binary_mode(self) -> bool:
        """检查是否为二进制模式"""
        return self.context.parsed.controller is None
    
    def get_threshold(self, key: str, default=None):
        """获取阈值配置"""
        return self.context.get_threshold(key, default)


class AnalyzerPipeline:
    """
    分析器流水线
    
    按依赖顺序执行多个分析器
    """
    
    def __init__(self, context: AnalysisContext):
        self.context = context
        self._analyzers: List[BaseAnalyzer] = []
    
    def add(self, analyzer_class: type) -> "AnalyzerPipeline":
        """
        添加分析器
        
        Args:
            analyzer_class: 分析器类
            
        Returns:
            self (链式调用)
        """
        self._analyzers.append(analyzer_class(self.context))
        return self
    
    def run(self) -> AnalysisContext:
        """
        执行所有分析器
        
        Returns:
            分析完成的上下文
        """
        for analyzer in self._analyzers:
            analyzer.analyze()
        return self.context

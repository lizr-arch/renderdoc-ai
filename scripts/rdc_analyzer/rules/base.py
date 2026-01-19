"""
规则基类和注册器
================

定义规则的统一接口和装饰器注册机制。
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Type, Optional, Callable, Any
from ..core.context import AnalysisContext
from ..core.types import Issue
from ..core.enums import Severity, Category


class BaseRule(ABC):
    """
    规则基类
    
    每个规则负责检测一种特定的问题。
    规则通过装饰器自动注册到 RuleRegistry。
    """
    
    # 规则 ID (必须唯一, 如 "RD_DC_001")
    rule_id: str = "RD_BASE"
    
    # 规则名称
    name: str = "Base Rule"
    
    # 规则描述
    description: str = "Base rule description"
    
    # 严重程度
    severity: str = Severity.WARNING
    
    # 分类
    category: str = Category.PERFORMANCE
    
    # 支持的平台 (空列表表示所有平台)
    platforms: List[str] = []
    
    # 是否启用
    enabled: bool = True
    
    def __init__(self, context: AnalysisContext):
        """
        初始化规则
        
        Args:
            context: 分析上下文
        """
        self.context = context
    
    @abstractmethod
    def check(self) -> List[Issue]:
        """
        执行规则检查
        
        Returns:
            发现的问题列表
        """
        pass
    
    def is_applicable(self) -> bool:
        """
        检查规则是否适用于当前平台
        
        Returns:
            True 如果规则适用
        """
        if not self.enabled:
            return False
        
        if not self.platforms:
            return True
        
        return self.context.platform.lower() in [p.lower() for p in self.platforms]
    
    def get_threshold(self, key: str, default: Any = None) -> Any:
        """获取阈值配置"""
        return self.context.get_threshold(key, default)
    
    def create_issue(
        self,
        message: str,
        location_path: Optional[str] = None,
        severity: Optional[str] = None,
        category: Optional[str] = None,
    ) -> Issue:
        """
        创建问题对象
        
        Args:
            message: 问题描述
            location_path: 问题位置路径
            severity: 覆盖默认严重程度
            category: 覆盖默认分类
            
        Returns:
            Issue 对象
        """
        return Issue(
            severity=severity or self.severity,
            category=category or self.category,
            code=self.rule_id,
            message=message,
            location_path=location_path,
        )


class RuleRegistry:
    """
    规则注册表
    
    使用装饰器模式注册规则:
    
    @RuleRegistry.register
    class MyRule(BaseRule):
        rule_id = "RD_MY_001"
        ...
    """
    
    _rules: Dict[str, Type[BaseRule]] = {}
    
    @classmethod
    def register(cls, rule_class: Type[BaseRule]) -> Type[BaseRule]:
        """
        注册规则 (装饰器)
        
        Args:
            rule_class: 规则类
            
        Returns:
            规则类 (不变)
        """
        rule_id = rule_class.rule_id
        if rule_id in cls._rules:
            raise ValueError(f"Duplicate rule ID: {rule_id}")
        cls._rules[rule_id] = rule_class
        return rule_class
    
    @classmethod
    def get(cls, rule_id: str) -> Optional[Type[BaseRule]]:
        """
        获取规则类
        
        Args:
            rule_id: 规则 ID
            
        Returns:
            规则类, 或 None
        """
        return cls._rules.get(rule_id)
    
    @classmethod
    def all(cls) -> Dict[str, Type[BaseRule]]:
        """
        获取所有注册的规则
        
        Returns:
            规则 ID -> 规则类 的字典
        """
        return cls._rules.copy()
    
    @classmethod
    def list_ids(cls) -> List[str]:
        """
        列出所有规则 ID
        
        Returns:
            规则 ID 列表
        """
        return list(cls._rules.keys())
    
    @classmethod
    def clear(cls):
        """清空注册表 (用于测试)"""
        cls._rules.clear()
    
    @classmethod
    def count(cls) -> int:
        """返回注册的规则数量"""
        return len(cls._rules)

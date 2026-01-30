"""
规则运行器
==========

负责执行所有注册的规则并收集问题。
"""

from typing import List, Optional, Set
from ..core.context import AnalysisContext
from ..core.types import Issue
from .base import BaseRule, RuleRegistry


class RuleRunner:
    """
    规则运行器
    
    执行所有适用的规则，收集问题。
    """
    
    def __init__(self, context: AnalysisContext):
        """
        初始化运行器
        
        Args:
            context: 分析上下文
        """
        self.context = context
        self._disabled_rules: Set[str] = set()
        self._enabled_only: Optional[Set[str]] = None
    
    def disable_rule(self, rule_id: str) -> "RuleRunner":
        """
        禁用指定规则
        
        Args:
            rule_id: 规则 ID
            
        Returns:
            self (链式调用)
        """
        self._disabled_rules.add(rule_id)
        return self
    
    def enable_only(self, rule_ids: List[str]) -> "RuleRunner":
        """
        只启用指定规则
        
        Args:
            rule_ids: 规则 ID 列表
            
        Returns:
            self (链式调用)
        """
        self._enabled_only = set(rule_ids)
        return self
    
    def run(self) -> List[Issue]:
        """
        执行所有适用的规则
        
        Returns:
            所有发现的问题
        """
        issues = []
        
        for rule_id, rule_class in RuleRegistry.all().items():
            # 检查是否被禁用
            if rule_id in self._disabled_rules:
                continue
            
            # 检查是否在启用列表中
            if self._enabled_only and rule_id not in self._enabled_only:
                continue
            
            # 创建规则实例
            rule = rule_class(self.context)
            
            # 检查是否适用
            if not rule.is_applicable():
                continue
            
            # 执行检查
            try:
                rule_issues = rule.check()
                issues.extend(rule_issues)
            except Exception as e:
                # 记录规则执行错误但不中断
                issues.append(Issue(
                    severity="warning",
                    category="internal",
                    code="RD_INTERNAL",
                    message=f"Rule {rule_id} failed: {str(e)}",
                ))
        
        return issues
    
    def run_single(self, rule_id: str) -> List[Issue]:
        """
        执行单个规则
        
        Args:
            rule_id: 规则 ID
            
        Returns:
            发现的问题
        """
        rule_class = RuleRegistry.get(rule_id)
        if not rule_class:
            return []
        
        rule = rule_class(self.context)
        if not rule.is_applicable():
            return []
        
        return rule.check()

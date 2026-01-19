"""
规则模块
========

提供自动化检测规则的定义和注册。

使用方式:
    from rdc_analyzer.rules import RuleRegistry, RuleRunner
    
    # 注册所有规则
    register_all_rules()
    
    # 运行规则
    runner = RuleRunner(context)
    issues = runner.run()
"""

from .base import BaseRule, RuleRegistry
from .runner import RuleRunner


def register_all_rules():
    """
    注册所有内置规则
    
    导入规则模块会自动触发 @RuleRegistry.register 装饰器
    """
    # Draw Call 规则
    from . import draw_call
    
    # 纹理规则
    from . import texture
    
    # 渲染状态规则
    from . import state
    
    # 渲染 Pass 规则
    from . import render_pass
    
    # Buffer 规则
    from . import buffer
    
    # 移动端规则
    from . import mobile


__all__ = [
    "BaseRule",
    "RuleRegistry", 
    "RuleRunner",
    "register_all_rules",
]
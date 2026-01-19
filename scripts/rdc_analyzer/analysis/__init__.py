"""
分析模块
========

提供 Draw Call 级别的深度分析功能
"""

from .call_analyzer import (
    CallAnalyzer,
    CallAnalyzerConfig,
    BindingIssue,
    BindingState,
    IssueSeverity,
    IssueCategory,
    analyze_draw_calls,
    create_sample_draws_for_testing,
)

from .resource_tracker import (
    ResourceTracker,
    ResourceTrackerConfig,
    ResourceAccess,
    ResourceDependency,
    ResourceLifetime,
    DependencyType,
    track_resources,
)

__all__ = [
    # 调用分析器
    'CallAnalyzer',
    'CallAnalyzerConfig',
    'BindingIssue',
    'BindingState',
    'IssueSeverity',
    'IssueCategory',
    'analyze_draw_calls',
    'create_sample_draws_for_testing',
    # 资源追踪器
    'ResourceTracker',
    'ResourceTrackerConfig',
    'ResourceAccess',
    'ResourceDependency',
    'ResourceLifetime',
    'DependencyType',
    'track_resources',
]
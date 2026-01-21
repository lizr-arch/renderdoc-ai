"""
回归检测类型定义
================

定义回归检测规则和结果数据结构。

规则列表:
- REG001: Draw Call 数量增加
- REG002: 纹理分辨率增加
- REG003: Shader 变更检测
- REG004: 缓冲区大小增加
- REG005: 三角形数量增加
- REG006: Overdraw 风险检测
- REG007: 新增渲染 Pass
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Dict, Any


class RegressionSeverity(Enum):
    """回归严重程度
    
    细粒度分级用于 CI 退出码判断:
    - INFO/LOW: 仅提示，不影响 CI
    - MEDIUM: 中级警告，可配置是否阻断
    - HIGH: 高级警告，默认阻断
    - CRITICAL: 严重问题，必须阻断
    """
    INFO = "info"           # 信息提示（兼容旧版）
    LOW = "low"             # 低级别
    MEDIUM = "medium"       # 中级别
    HIGH = "high"           # 高级别
    WARNING = "warning"     # 警告（兼容旧版，等同于 MEDIUM）
    CRITICAL = "critical"   # 严重问题


class RegressionRuleId(Enum):
    """回归规则 ID"""
    REG001 = "REG001"  # Draw Call 数量增加
    REG002 = "REG002"  # 纹理分辨率增加
    REG003 = "REG003"  # Shader 变更
    REG004 = "REG004"  # 缓冲区大小增加
    REG005 = "REG005"  # 三角形数量增加
    REG006 = "REG006"  # Overdraw 风险
    REG007 = "REG007"  # 新增渲染 Pass


@dataclass
class RegressionRule:
    """
    回归检测规则定义
    
    Attributes:
        rule_id: 规则 ID
        name: 规则名称
        description: 规则描述
        severity: 默认严重程度
        threshold: 触发阈值 (百分比)
        enabled: 是否启用
    """
    rule_id: RegressionRuleId
    name: str
    description: str
    severity: RegressionSeverity = RegressionSeverity.WARNING
    threshold: float = 0.0
    enabled: bool = True
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "rule_id": self.rule_id.value,
            "name": self.name,
            "description": self.description,
            "severity": self.severity.value,
            "threshold": self.threshold,
            "enabled": self.enabled,
        }


@dataclass
class EvidenceAnchor:
    """
    证据锚点 - 用于关联回归问题到具体的渲染事件
    
    Attributes:
        event_id: RenderDoc Event ID
        marker_path: Debug Marker 路径 (如 "Shadow/MainLight/Cascade0")
        description: 事件描述
    """
    event_id: int
    marker_path: str = ""
    description: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "marker_path": self.marker_path,
            "description": self.description,
        }


@dataclass
class RegressionIssue:
    """
    检测到的回归问题
    
    Attributes:
        rule_id: 触发的规则 ID
        severity: 严重程度
        message: 问题描述
        details: 详细信息
        baseline_value: 基准值
        target_value: 目标值
        delta_percent: 变化百分比
        affected_resources: 受影响的资源 ID 列表
        evidence: 证据锚点列表 (用于跳转到问题位置)
    """
    rule_id: RegressionRuleId
    severity: RegressionSeverity
    message: str
    details: str = ""
    baseline_value: Optional[float] = None
    target_value: Optional[float] = None
    delta_percent: Optional[float] = None
    affected_resources: List[str] = field(default_factory=list)
    evidence: List[EvidenceAnchor] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "rule_id": self.rule_id.value,
            "severity": self.severity.value,
            "message": self.message,
            "details": self.details,
            "baseline_value": self.baseline_value,
            "target_value": self.target_value,
            "delta_percent": self.delta_percent,
            "affected_resources": self.affected_resources,
            "evidence": [e.to_dict() for e in self.evidence],
        }


@dataclass
class RegressionResult:
    """
    回归检测结果 (用于 CI 输出和 JUnit XML)
    
    与 RegressionIssue 类似，但增加了阈值等 CI 所需字段。
    
    Attributes:
        rule_id: 触发的规则 ID
        severity: 严重程度
        category: 类别 (如 DrawCalls, Triangles)
        metric_name: 指标名称
        baseline_value: 基准值
        target_value: 目标值
        delta_percent: 变化百分比
        threshold_percent: 阈值百分比
        message: 问题描述
        details: 详细信息
    """
    rule_id: RegressionRuleId
    severity: RegressionSeverity
    category: str
    metric_name: str
    baseline_value: float
    target_value: float
    delta_percent: float
    threshold_percent: float
    message: str
    details: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "rule_id": self.rule_id.value,
            "severity": self.severity.value,
            "category": self.category,
            "metric_name": self.metric_name,
            "baseline_value": self.baseline_value,
            "target_value": self.target_value,
            "delta_percent": self.delta_percent,
            "threshold_percent": self.threshold_percent,
            "message": self.message,
            "details": self.details,
        }


@dataclass
class RegressionReport:
    """
    回归检测报告
    
    Attributes:
        issues: 检测到的问题列表 (RegressionIssue)
        results: 回归结果列表 (RegressionResult, 用于 CI/JUnit)
        rules_checked: 已检查的规则数量
        rules_triggered: 触发的规则数量
    """
    issues: List[RegressionIssue] = field(default_factory=list)
    results: List[RegressionResult] = field(default_factory=list)
    rules_checked: int = 0
    rules_triggered: int = 0
    # 内部字段，用于显式覆盖计算属性（向后兼容）
    _has_warning_override: Optional[bool] = field(default=None, repr=False)
    _has_critical_override: Optional[bool] = field(default=None, repr=False)
    
    def __init__(
        self,
        issues: List[RegressionIssue] = None,
        results: List[RegressionResult] = None,
        rules_checked: int = 0,
        rules_triggered: int = 0,
        has_warning: bool = None,
        has_critical: bool = None,
    ):
        """初始化报告
        
        Args:
            issues: 问题列表
            results: 结果列表（用于 CI）
            rules_checked: 已检查规则数
            rules_triggered: 触发规则数
            has_warning: 显式设置是否有警告（覆盖自动计算）
            has_critical: 显式设置是否有严重问题（覆盖自动计算）
        """
        self.issues = issues if issues is not None else []
        self.results = results if results is not None else []
        self.rules_checked = rules_checked
        self.rules_triggered = rules_triggered
        self._has_warning_override = has_warning
        self._has_critical_override = has_critical
    
    @property
    def has_critical(self) -> bool:
        """是否有严重问题"""
        if self._has_critical_override is not None:
            return self._has_critical_override
        from_issues = any(i.severity == RegressionSeverity.CRITICAL for i in self.issues)
        from_results = any(r.severity == RegressionSeverity.CRITICAL for r in self.results)
        return from_issues or from_results
    
    @property
    def has_warning(self) -> bool:
        """是否有警告"""
        if self._has_warning_override is not None:
            return self._has_warning_override
        warning_severities = {
            RegressionSeverity.WARNING,
            RegressionSeverity.MEDIUM,
            RegressionSeverity.HIGH,
        }
        from_issues = any(i.severity in warning_severities for i in self.issues)
        from_results = any(r.severity in warning_severities for r in self.results)
        return from_issues or from_results
    
    @property
    def critical_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == RegressionSeverity.CRITICAL)
    
    @property
    def warning_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == RegressionSeverity.WARNING)
    
    @property
    def info_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == RegressionSeverity.INFO)
    
    @property
    def is_regression_detected(self) -> bool:
        """是否检测到回归 (警告或严重)"""
        return self.has_critical or self.has_warning
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "issues": [i.to_dict() for i in self.issues],
            "rules_checked": self.rules_checked,
            "rules_triggered": self.rules_triggered,
            "summary": {
                "critical_count": self.critical_count,
                "warning_count": self.warning_count,
                "info_count": self.info_count,
                "is_regression_detected": self.is_regression_detected,
            }
        }


# 预定义规则配置
DEFAULT_RULES: Dict[RegressionRuleId, RegressionRule] = {
    RegressionRuleId.REG001: RegressionRule(
        rule_id=RegressionRuleId.REG001,
        name="Draw Call 数量增加",
        description="检测 Draw Call 数量是否显著增加",
        severity=RegressionSeverity.WARNING,
        threshold=5.0,  # >5% 触发
    ),
    RegressionRuleId.REG002: RegressionRule(
        rule_id=RegressionRuleId.REG002,
        name="纹理分辨率增加",
        description="检测纹理分辨率是否大幅增加",
        severity=RegressionSeverity.WARNING,
        threshold=50.0,  # >50% 触发
    ),
    RegressionRuleId.REG003: RegressionRule(
        rule_id=RegressionRuleId.REG003,
        name="Shader 变更",
        description="检测 Shader 代码是否发生变化",
        severity=RegressionSeverity.INFO,
        threshold=0.0,  # 任何变化都报告
    ),
    RegressionRuleId.REG004: RegressionRule(
        rule_id=RegressionRuleId.REG004,
        name="缓冲区大小增加",
        description="检测缓冲区大小是否显著增加",
        severity=RegressionSeverity.WARNING,
        threshold=30.0,  # >30% 触发
    ),
    RegressionRuleId.REG005: RegressionRule(
        rule_id=RegressionRuleId.REG005,
        name="三角形数量增加",
        description="检测渲染的三角形数量是否增加",
        severity=RegressionSeverity.CRITICAL,
        threshold=10.0,  # >10% 触发为严重
    ),
    RegressionRuleId.REG006: RegressionRule(
        rule_id=RegressionRuleId.REG006,
        name="Overdraw 风险",
        description="检测是否存在潜在的 Overdraw 问题",
        severity=RegressionSeverity.WARNING,
        threshold=0.0,
    ),
    RegressionRuleId.REG007: RegressionRule(
        rule_id=RegressionRuleId.REG007,
        name="新增渲染 Pass",
        description="检测是否添加了新的渲染 Pass",
        severity=RegressionSeverity.INFO,
        threshold=0.0,
    ),
}

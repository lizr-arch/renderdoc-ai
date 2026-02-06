"""
审计报告数据结构
================

定义资产审计的结果和报告格式。
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from enum import Enum
from datetime import datetime


class AssetCategory(str, Enum):
    """资产分类"""
    TEXTURE = "texture"
    BUFFER = "buffer"
    SHADER = "shader"
    RENDER_TARGET = "render_target"
    SAMPLER = "sampler"
    PIPELINE = "pipeline"


class AuditSeverity(str, Enum):
    """审计问题严重程度"""
    CRITICAL = "critical"  # 必须修复
    WARNING = "warning"    # 应该修复
    INFO = "info"          # 建议优化
    PASS = "pass"          # 检查通过


@dataclass
class AuditIssue:
    """审计发现的问题
    
    Attributes:
        rule_id: 规则 ID (如 RD_TEX_001)
        category: 资产分类
        severity: 严重程度
        message: 问题描述
        resource_id: 相关资源 ID
        resource_name: 资源名称 (可选)
        details: 详细信息 (键值对)
        suggestion: 优化建议
    """
    rule_id: str
    category: AssetCategory
    severity: AuditSeverity
    message: str
    resource_id: Optional[str] = None
    resource_name: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)
    suggestion: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "rule_id": self.rule_id,
            "category": self.category.value,
            "severity": self.severity.value,
            "message": self.message,
            "resource_id": self.resource_id,
            "resource_name": self.resource_name,
            "details": self.details,
            "suggestion": self.suggestion,
        }


@dataclass
class AssetStats:
    """单类资产统计
    
    Attributes:
        count: 资产数量
        total_memory: 总内存 (bytes)
        avg_memory: 平均内存
        max_memory: 最大单项内存
        issue_count: 问题数量
    """
    count: int = 0
    total_memory: int = 0
    avg_memory: float = 0.0
    max_memory: int = 0
    issue_count: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "count": self.count,
            "total_memory": self.total_memory,
            "avg_memory": self.avg_memory,
            "max_memory": self.max_memory,
            "issue_count": self.issue_count,
        }


@dataclass
class TextureStats(AssetStats):
    """纹理统计"""
    compressed_count: int = 0
    uncompressed_count: int = 0
    missing_mipmap_count: int = 0
    oversized_count: int = 0  # > 2048
    npot_count: int = 0       # 非 2 次幂
    
    def to_dict(self) -> Dict[str, Any]:
        base = super().to_dict()
        base.update({
            "compressed_count": self.compressed_count,
            "uncompressed_count": self.uncompressed_count,
            "missing_mipmap_count": self.missing_mipmap_count,
            "oversized_count": self.oversized_count,
            "npot_count": self.npot_count,
        })
        return base


@dataclass
class BufferStats(AssetStats):
    """Buffer 统计"""
    vertex_buffer_count: int = 0
    index_buffer_count: int = 0
    constant_buffer_count: int = 0
    other_count: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        base = super().to_dict()
        base.update({
            "vertex_buffer_count": self.vertex_buffer_count,
            "index_buffer_count": self.index_buffer_count,
            "constant_buffer_count": self.constant_buffer_count,
            "other_count": self.other_count,
        })
        return base


@dataclass
class AuditSummary:
    """审计摘要
    
    Attributes:
        total_issues: 总问题数
        critical_count: 严重问题数
        warning_count: 警告数
        info_count: 提示数
        pass_count: 通过数
        total_memory: 总资源内存
        texture_stats: 纹理统计
        buffer_stats: Buffer 统计
    """
    total_issues: int = 0
    critical_count: int = 0
    warning_count: int = 0
    info_count: int = 0
    pass_count: int = 0
    total_memory: int = 0
    
    texture_stats: TextureStats = field(default_factory=TextureStats)
    buffer_stats: BufferStats = field(default_factory=BufferStats)
    
    @property
    def has_critical(self) -> bool:
        """是否有严重问题"""
        return self.critical_count > 0
    
    @property
    def has_warning(self) -> bool:
        """是否有警告"""
        return self.warning_count > 0
    
    @property
    def grade(self) -> str:
        """评级 (A/B/C/D/F)"""
        if self.critical_count > 0:
            return "F"
        elif self.warning_count > 5:
            return "D"
        elif self.warning_count > 0:
            return "C"
        elif self.info_count > 5:
            return "B"
        else:
            return "A"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_issues": self.total_issues,
            "critical_count": self.critical_count,
            "warning_count": self.warning_count,
            "info_count": self.info_count,
            "pass_count": self.pass_count,
            "total_memory": self.total_memory,
            "grade": self.grade,
            "texture_stats": self.texture_stats.to_dict(),
            "buffer_stats": self.buffer_stats.to_dict(),
        }


@dataclass
class AuditReport:
    """审计报告
    
    Attributes:
        file_path: 分析的文件路径
        platform: 目标平台
        preset: 使用的预设
        generated_at: 生成时间
        summary: 摘要统计
        issues: 发现的问题列表
        textures: 纹理资产列表
        buffers: Buffer 资产列表
    """
    file_path: str
    platform: str = "pc"
    preset: str = "default"
    generated_at: datetime = field(default_factory=datetime.now)
    
    summary: AuditSummary = field(default_factory=AuditSummary)
    issues: List[AuditIssue] = field(default_factory=list)
    
    # 资产清单
    textures: List[Dict[str, Any]] = field(default_factory=list)
    buffers: List[Dict[str, Any]] = field(default_factory=list)
    
    @property
    def has_critical(self) -> bool:
        """是否有严重问题"""
        return self.summary.has_critical
    
    @property
    def has_warning(self) -> bool:
        """是否有警告"""
        return self.summary.has_warning
    
    def add_issue(self, issue: AuditIssue) -> None:
        """添加问题"""
        self.issues.append(issue)
        
        # 更新计数
        self.summary.total_issues += 1
        if issue.severity == AuditSeverity.CRITICAL:
            self.summary.critical_count += 1
        elif issue.severity == AuditSeverity.WARNING:
            self.summary.warning_count += 1
        elif issue.severity == AuditSeverity.INFO:
            self.summary.info_count += 1
        elif issue.severity == AuditSeverity.PASS:
            self.summary.pass_count += 1
    
    def get_issues_by_category(self, category: AssetCategory) -> List[AuditIssue]:
        """按分类获取问题"""
        return [i for i in self.issues if i.category == category]
    
    def get_issues_by_severity(self, severity: AuditSeverity) -> List[AuditIssue]:
        """按严重程度获取问题"""
        return [i for i in self.issues if i.severity == severity]
    
    def format_summary(self) -> str:
        """格式化摘要文本"""
        lines = [
            "",
            "=" * 60,
            f"资产审计报告 - 评级: {self.summary.grade}",
            "=" * 60,
            "",
            f"文件: {self.file_path}",
            f"平台: {self.platform}",
            f"预设: {self.preset}",
            f"时间: {self.generated_at.strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "--- 问题统计 ---",
            f"  严重: {self.summary.critical_count}",
            f"  警告: {self.summary.warning_count}",
            f"  提示: {self.summary.info_count}",
            "",
            "--- 纹理统计 ---",
            f"  总数: {self.summary.texture_stats.count}",
            f"  内存: {self._format_bytes(self.summary.texture_stats.total_memory)}",
            f"  压缩: {self.summary.texture_stats.compressed_count}",
            f"  未压缩: {self.summary.texture_stats.uncompressed_count}",
            f"  缺 Mipmap: {self.summary.texture_stats.missing_mipmap_count}",
            "",
            "--- Buffer 统计 ---",
            f"  总数: {self.summary.buffer_stats.count}",
            f"  内存: {self._format_bytes(self.summary.buffer_stats.total_memory)}",
            "",
        ]
        
        # 打印问题
        if self.issues:
            lines.append("--- 问题详情 ---")
            
            critical = self.get_issues_by_severity(AuditSeverity.CRITICAL)
            if critical:
                lines.append("\n[!!!] 严重问题:")
                for issue in critical[:5]:
                    lines.append(f"  [{issue.rule_id}] {issue.message}")
                if len(critical) > 5:
                    lines.append(f"  ... 还有 {len(critical) - 5} 个")
            
            warnings = self.get_issues_by_severity(AuditSeverity.WARNING)
            if warnings:
                lines.append("\n[!] 警告:")
                for issue in warnings[:5]:
                    lines.append(f"  [{issue.rule_id}] {issue.message}")
                if len(warnings) > 5:
                    lines.append(f"  ... 还有 {len(warnings) - 5} 个")
        else:
            lines.append("[+] 未发现问题，资产健康！")
        
        lines.append("")
        return "\n".join(lines)
    
    def _format_bytes(self, size: int) -> str:
        """格式化字节数"""
        if size < 1024:
            return f"{size} B"
        elif size < 1024 * 1024:
            return f"{size / 1024:.1f} KB"
        elif size < 1024 * 1024 * 1024:
            return f"{size / (1024 * 1024):.1f} MB"
        else:
            return f"{size / (1024 * 1024 * 1024):.2f} GB"
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "file_path": self.file_path,
            "platform": self.platform,
            "preset": self.preset,
            "generated_at": self.generated_at.isoformat(),
            "summary": self.summary.to_dict(),
            "issues": [i.to_dict() for i in self.issues],
            "textures": self.textures,
            "buffers": self.buffers,
        }

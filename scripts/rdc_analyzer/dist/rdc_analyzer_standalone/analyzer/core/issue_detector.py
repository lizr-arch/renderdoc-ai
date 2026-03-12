"""
Issue Detector - 自动化问题检测引擎

职责：
- 定义问题严重性（Severity）和分类（Category）枚举
- 提供纹理、Shader、Buffer 等资源的问题检测规则
- 从 ReportDataContract 提取所有问题

设计原则：
- 规则可扩展：每类资源一个检测函数
- 结果可排序：按 severity.priority 降序排列
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Any, Optional, Callable


# =============================================================================
# 枚举定义
# =============================================================================

class Severity(Enum):
    """问题严重性级别"""
    CRITICAL = "critical"  # 必须修复，会导致崩溃或严重性能问题
    WARNING = "warning"    # 建议修复，可能影响性能
    INFO = "info"          # 信息提示，最佳实践建议

    @property
    def priority(self) -> int:
        """用于排序的优先级数值（越大越严重）"""
        priorities = {
            "critical": 3,
            "warning": 2,
            "info": 1,
        }
        return priorities[self.value]


class Category(Enum):
    """问题分类"""
    TEXTURE = "texture"
    SHADER = "shader"
    BUFFER = "buffer"
    PERFORMANCE = "performance"
    MEMORY = "memory"


# =============================================================================
# Issue 数据类
# =============================================================================

@dataclass
class Issue:
    """单个问题的描述"""
    severity: Severity
    category: Category
    title: str
    description: str
    resource_id: Optional[str] = None
    suggestion: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """转换为可序列化的字典"""
        return {
            "severity": self.severity.value,
            "category": self.category.value,
            "title": self.title,
            "description": self.description,
            "resource_id": self.resource_id,
            "suggestion": self.suggestion,
            "metadata": self.metadata,
        }


# =============================================================================
# 纹理问题检测规则
# =============================================================================

def _is_power_of_two(n: int) -> bool:
    """检查是否为 2 的幂次"""
    return n > 0 and (n & (n - 1)) == 0


def _is_compressed_format(fmt: str) -> bool:
    """检查是否为压缩格式"""
    compressed_prefixes = (
        "BC", "DXT", "ETC", "ASTC", "PVRTC",
        "ATI1", "ATI2", "3DC",
    )
    if not fmt:
        return True  # 未知格式不报警
    return any(fmt.upper().startswith(prefix) for prefix in compressed_prefixes)


def detect_texture_issues(textures: List[Dict[str, Any]]) -> List[Issue]:
    """
    检测纹理相关问题
    
    规则：
    1. 超大纹理（>4096 任一边）- WARNING
    2. 非 2 的幂次尺寸 - INFO
    3. 大尺寸未压缩纹理（≥1024 且非压缩格式）- WARNING
    """
    issues: List[Issue] = []
    
    for tex in textures:
        name = tex.get("name", "unknown")
        width = tex.get("width", 0)
        height = tex.get("height", 0)
        fmt = tex.get("format", "")
        
        # 规则 1: 超大纹理
        if width > 4096 or height > 4096:
            issues.append(Issue(
                severity=Severity.WARNING,
                category=Category.TEXTURE,
                title="Oversized Texture",
                description=f"Texture '{name}' is {width}x{height}, exceeding 4096 threshold",
                resource_id=name,
                suggestion="Consider reducing resolution or using streaming/mipmaps",
                metadata={"width": width, "height": height},
            ))
        
        # 规则 2: 非 2 的幂次（NPOT）
        if width > 0 and height > 0:
            if not _is_power_of_two(width) or not _is_power_of_two(height):
                issues.append(Issue(
                    severity=Severity.INFO,
                    category=Category.TEXTURE,
                    title="NPOT Texture",
                    description=f"Texture '{name}' ({width}x{height}) is not power-of-two, may cause GPU inefficiency",
                    resource_id=name,
                    suggestion="Use power-of-two dimensions (256, 512, 1024, 2048...)",
                    metadata={"width": width, "height": height},
                ))
        
        # 规则 3: 大尺寸未压缩
        if (width >= 1024 or height >= 1024) and not _is_compressed_format(fmt):
            issues.append(Issue(
                severity=Severity.WARNING,
                category=Category.TEXTURE,
                title="Uncompressed Large Texture",
                description=f"Texture '{name}' ({width}x{height}) uses uncompressed format '{fmt}'",
                resource_id=name,
                suggestion="Consider using BC7, BC5, or ASTC compression to reduce memory",
                metadata={"width": width, "height": height, "format": fmt},
            ))
    
    return issues


# =============================================================================
# IssueDetector 主类
# =============================================================================

class IssueDetector:
    """
    问题检测器主类
    
    用法：
        detector = IssueDetector()
        issues = detector.detect(contract)
    """
    
    def __init__(self):
        # 规则列表：(资源类型, 检测函数)
        self.rules: List[tuple] = [
            ("textures", detect_texture_issues),
            # 未来扩展：
            # ("shaders", detect_shader_issues),
            # ("buffers", detect_buffer_issues),
        ]
    
    def detect(self, contract) -> List[Issue]:
        """
        从 ReportDataContract 检测所有问题
        
        Args:
            contract: ReportDataContract 实例
            
        Returns:
            按严重性降序排列的问题列表
        """
        all_issues: List[Issue] = []
        
        for field_name, detector_func in self.rules:
            data = getattr(contract, field_name, [])
            if data:
                issues = detector_func(data)
                all_issues.extend(issues)
        
        # 按严重性降序排序
        all_issues.sort(key=lambda i: i.severity.priority, reverse=True)
        
        return all_issues


# =============================================================================
# 便捷函数
# =============================================================================

def detect_all_issues(contract) -> List[Issue]:
    """
    便捷函数：检测 contract 中的所有问题
    
    Args:
        contract: ReportDataContract 实例
        
    Returns:
        问题列表
    """
    detector = IssueDetector()
    return detector.detect(contract)

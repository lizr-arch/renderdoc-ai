"""
IssueDetector 单元测试
按 TDD 流程：先写失败测试 -> 实现 -> 验证通过
"""
import unittest
from scripts.rdc_analyzer.core.issue_detector import (
    Severity,
    Category,
    Issue,
    IssueDetector,
    detect_texture_issues,
    detect_all_issues,
)


class TestSeverityEnum(unittest.TestCase):
    """测试 Severity 枚举"""

    def test_severity_values(self):
        """测试严重性级别定义"""
        self.assertEqual(Severity.CRITICAL.value, "critical")
        self.assertEqual(Severity.WARNING.value, "warning")
        self.assertEqual(Severity.INFO.value, "info")

    def test_severity_ordering(self):
        """测试严重性可比较（用于排序）"""
        # critical > warning > info
        severities = [Severity.INFO, Severity.CRITICAL, Severity.WARNING]
        sorted_sev = sorted(severities, key=lambda s: s.priority, reverse=True)
        self.assertEqual(sorted_sev, [Severity.CRITICAL, Severity.WARNING, Severity.INFO])


class TestCategoryEnum(unittest.TestCase):
    """测试 Category 枚举"""

    def test_category_values(self):
        """测试问题分类定义"""
        self.assertEqual(Category.TEXTURE.value, "texture")
        self.assertEqual(Category.SHADER.value, "shader")
        self.assertEqual(Category.BUFFER.value, "buffer")
        self.assertEqual(Category.PERFORMANCE.value, "performance")
        self.assertEqual(Category.MEMORY.value, "memory")


class TestIssueDataclass(unittest.TestCase):
    """测试 Issue 数据类"""

    def test_issue_creation(self):
        """测试问题对象创建"""
        issue = Issue(
            severity=Severity.CRITICAL,
            category=Category.TEXTURE,
            title="Oversized Texture",
            description="Texture exceeds 4096x4096",
            resource_id="tex_001",
            suggestion="Consider using mipmaps or reducing resolution",
        )
        self.assertEqual(issue.severity, Severity.CRITICAL)
        self.assertEqual(issue.category, Category.TEXTURE)
        self.assertEqual(issue.title, "Oversized Texture")
        self.assertIn("4096", issue.description)

    def test_issue_to_dict(self):
        """测试转换为字典"""
        issue = Issue(
            severity=Severity.WARNING,
            category=Category.SHADER,
            title="Test Issue",
            description="Test description",
        )
        d = issue.to_dict()
        self.assertEqual(d["severity"], "warning")
        self.assertEqual(d["category"], "shader")
        self.assertEqual(d["title"], "Test Issue")


class TestTextureIssueDetection(unittest.TestCase):
    """测试纹理问题检测规则"""

    def test_oversized_texture_detection(self):
        """测试超大纹理检测（>4096）"""
        textures = [
            {"name": "normal_tex", "width": 1024, "height": 1024},
            {"name": "huge_tex", "width": 8192, "height": 8192},
        ]
        issues = detect_texture_issues(textures)
        
        # 应该检测到 1 个超大纹理问题
        oversized = [i for i in issues if "oversized" in i.title.lower() or "8192" in i.description]
        self.assertEqual(len(oversized), 1)
        self.assertEqual(oversized[0].severity, Severity.WARNING)
        self.assertIn("huge_tex", oversized[0].resource_id)

    def test_npot_texture_detection(self):
        """测试非 2 的幂次纹理检测"""
        textures = [
            {"name": "pot_tex", "width": 512, "height": 512},  # 2^9, OK
            {"name": "npot_tex", "width": 500, "height": 500},  # NOT power of 2
        ]
        issues = detect_texture_issues(textures)
        
        npot_issues = [i for i in issues if "npot" in i.title.lower() or "power" in i.description.lower()]
        self.assertEqual(len(npot_issues), 1)
        self.assertEqual(npot_issues[0].category, Category.TEXTURE)

    def test_uncompressed_large_texture(self):
        """测试大尺寸未压缩纹理检测"""
        textures = [
            {"name": "compressed_tex", "width": 2048, "height": 2048, "format": "BC7_UNORM"},
            {"name": "uncompressed_tex", "width": 2048, "height": 2048, "format": "R8G8B8A8_UNORM"},
        ]
        issues = detect_texture_issues(textures)
        
        # 未压缩的大纹理应该被标记
        uncompressed = [i for i in issues if "uncompressed" in i.title.lower() or "compress" in i.description.lower()]
        self.assertGreaterEqual(len(uncompressed), 1)

    def test_no_issues_for_good_textures(self):
        """测试正常纹理不产生问题"""
        textures = [
            {"name": "good_tex", "width": 512, "height": 512, "format": "BC7_UNORM"},
        ]
        issues = detect_texture_issues(textures)
        self.assertEqual(len(issues), 0)


class TestIssueDetector(unittest.TestCase):
    """测试 IssueDetector 主类"""

    def test_detector_initialization(self):
        """测试检测器初始化"""
        detector = IssueDetector()
        self.assertIsNotNone(detector)
        self.assertIsInstance(detector.rules, list)

    def test_detect_from_contract(self):
        """测试从 ReportDataContract 检测问题"""
        from scripts.rdc_analyzer.report_contract import ReportDataContract
        
        contract = ReportDataContract(
            textures=[
                {"name": "huge", "width": 16384, "height": 16384},
            ]
        )
        detector = IssueDetector()
        issues = detector.detect(contract)
        
        self.assertIsInstance(issues, list)
        self.assertGreater(len(issues), 0)

    def test_detect_all_issues_function(self):
        """测试便捷函数 detect_all_issues"""
        from scripts.rdc_analyzer.report_contract import ReportDataContract
        
        contract = ReportDataContract(
            textures=[
                {"name": "problem_tex", "width": 999, "height": 999},  # NPOT
            ]
        )
        issues = detect_all_issues(contract)
        
        self.assertIsInstance(issues, list)
        self.assertGreater(len(issues), 0)


class TestIssueSorting(unittest.TestCase):
    """测试问题排序功能"""

    def test_sort_by_severity(self):
        """测试按严重性排序"""
        issues = [
            Issue(Severity.INFO, Category.TEXTURE, "Info issue", ""),
            Issue(Severity.CRITICAL, Category.TEXTURE, "Critical issue", ""),
            Issue(Severity.WARNING, Category.TEXTURE, "Warning issue", ""),
        ]
        
        sorted_issues = sorted(issues, key=lambda i: i.severity.priority, reverse=True)
        
        self.assertEqual(sorted_issues[0].severity, Severity.CRITICAL)
        self.assertEqual(sorted_issues[1].severity, Severity.WARNING)
        self.assertEqual(sorted_issues[2].severity, Severity.INFO)


if __name__ == "__main__":
    unittest.main()

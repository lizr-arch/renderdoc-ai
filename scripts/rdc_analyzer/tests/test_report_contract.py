"""
Test Report Contract - 报告数据契约单元测试

测试 ReportDataContract 和 build_manifest() 的正确性。
"""

import unittest
import sys
from pathlib import Path

# 添加父目录到路径以支持导入
sys.path.insert(0, str(Path(__file__).parent.parent))

from report_contract import (
    ReportDataContract,
    build_manifest,
    validate_manifest,
)


class TestReportDataContract(unittest.TestCase):
    """测试 ReportDataContract 数据类"""
    
    def test_default_values(self):
        """测试默认值初始化"""
        report = ReportDataContract()
        self.assertEqual(report.textures, [])
        self.assertEqual(report.shaders, [])
        self.assertEqual(report.events, [])
        self.assertEqual(report.meta, {})
    
    def test_with_data(self):
        """测试带数据初始化"""
        report = ReportDataContract(
            meta={"capture_name": "test.rdc"},
            textures=[{"name": "tex1", "width": 1024}],
            shaders=[{"name": "shader1"}],
            events=[{"eid": 1}, {"eid": 2}],
        )
        self.assertEqual(len(report.textures), 1)
        self.assertEqual(len(report.shaders), 1)
        self.assertEqual(len(report.events), 2)
        self.assertEqual(report.meta["capture_name"], "test.rdc")
    
    def test_to_dict(self):
        """测试转换为字典"""
        report = ReportDataContract(
            textures=[{"name": "t1"}],
            shaders=[{"name": "s1"}],
        )
        d = report.to_dict()
        self.assertIn("textures", d)
        self.assertIn("shaders", d)
        self.assertEqual(len(d["textures"]), 1)
    
    def test_from_dict(self):
        """测试从字典创建"""
        data = {
            "meta": {"capture_name": "test.rdc"},
            "textures": [{"name": "t1"}],
            "events": [{"eid": 1}],
        }
        report = ReportDataContract.from_dict(data)
        self.assertEqual(report.meta["capture_name"], "test.rdc")
        self.assertEqual(len(report.textures), 1)
        self.assertEqual(len(report.events), 1)


class TestBuildManifest(unittest.TestCase):
    """测试 build_manifest() 函数"""
    
    def test_manifest_counts(self):
        """测试 Manifest 统计数量"""
        report = ReportDataContract(
            textures=[{"name": "t0"}],
            shaders=[{"name": "s0"}],
            events=[{"eid": 1}],
        )
        manifest = build_manifest(report)
        
        self.assertEqual(manifest["counts"]["textures"], 1)
        self.assertEqual(manifest["counts"]["shaders"], 1)
        self.assertEqual(manifest["counts"]["events"], 1)
        self.assertEqual(manifest["counts"]["buffers"], 0)
    
    def test_coverage_calculation_full(self):
        """测试完整数据的覆盖率计算"""
        report = ReportDataContract(
            textures=[{"name": "t1"}],
            shaders=[{"name": "s1"}],
            events=[{"eid": 1}],
            buffers=[{"name": "b1"}],
            issues=[{"id": "i1"}],
            pipeline_states=[{"state": "s1"}],
        )
        manifest = build_manifest(report)
        # 6/6 字段非空 = 100%
        self.assertEqual(manifest["coverage"], 1.0)
    
    def test_coverage_calculation_partial(self):
        """测试部分数据的覆盖率计算"""
        report = ReportDataContract(
            textures=[{"name": "t1"}],
            shaders=[{"name": "s1"}],
            # events, buffers, issues, pipeline_states 为空
        )
        manifest = build_manifest(report)
        # 2/6 字段非空 ≈ 33%
        self.assertAlmostEqual(manifest["coverage"], 2/6, places=2)
    
    def test_coverage_calculation_empty(self):
        """测试空数据的覆盖率"""
        report = ReportDataContract()
        manifest = build_manifest(report)
        self.assertEqual(manifest["coverage"], 0.0)
    
    def test_issue_stats(self):
        """测试问题统计"""
        report = ReportDataContract(
            issues=[
                {"id": "1", "severity": "critical"},
                {"id": "2", "severity": "critical"},
                {"id": "3", "severity": "warning"},
                {"id": "4", "severity": "info"},
            ]
        )
        manifest = build_manifest(report)
        
        self.assertEqual(manifest["issue_stats"]["critical"], 2)
        self.assertEqual(manifest["issue_stats"]["warning"], 1)
        self.assertEqual(manifest["issue_stats"]["info"], 1)
        self.assertEqual(manifest["issue_stats"]["pass"], 0)
    
    def test_manifest_version(self):
        """测试 Manifest 版本号"""
        report = ReportDataContract()
        manifest = build_manifest(report)
        self.assertEqual(manifest["version"], "2.0")
    
    def test_manifest_generated_at(self):
        """测试生成时间戳"""
        report = ReportDataContract()
        manifest = build_manifest(report)
        self.assertIn("generated_at", manifest)
        self.assertIsNotNone(manifest["generated_at"])
    
    def test_manifest_meta(self):
        """测试 Manifest 元数据"""
        report = ReportDataContract(
            meta={
                "capture_name": "game_frame.rdc",
                "api": "D3D11",
                "source": "A-route",
            }
        )
        manifest = build_manifest(report)
        
        self.assertEqual(manifest["meta"]["capture_name"], "game_frame.rdc")
        self.assertEqual(manifest["meta"]["api"], "D3D11")
        self.assertEqual(manifest["meta"]["source"], "A-route")


class TestValidateManifest(unittest.TestCase):
    """测试 validate_manifest() 函数"""
    
    def test_valid_coverage(self):
        """测试覆盖率通过"""
        manifest = {
            "coverage": 0.8,
            "counts": {"textures": 10, "shaders": 5},
        }
        is_valid, msg = validate_manifest(manifest, min_coverage=0.5)
        self.assertTrue(is_valid)
        self.assertIn("通过", msg)
    
    def test_invalid_coverage(self):
        """测试覆盖率不足"""
        manifest = {
            "coverage": 0.2,
            "counts": {"textures": 1, "shaders": 0, "events": 0},
        }
        is_valid, msg = validate_manifest(manifest, min_coverage=0.5)
        self.assertFalse(is_valid)
        self.assertIn("不足", msg)
        self.assertIn("shaders", msg)  # 空字段应列出
    
    def test_edge_case_exact_threshold(self):
        """测试边界情况：恰好达到阈值"""
        manifest = {
            "coverage": 0.5,
            "counts": {},
        }
        is_valid, msg = validate_manifest(manifest, min_coverage=0.5)
        self.assertTrue(is_valid)

    def test_validate_manifest_tool_exists(self):
        """验证 manifest 工具存在"""
        tool_path = Path(__file__).parent.parent / "tools" / "validate_manifest.py"
        self.assertTrue(tool_path.exists())


if __name__ == "__main__":
    unittest.main()

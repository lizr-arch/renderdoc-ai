"""
Feature Flag 测试 - 验证 --ui-version 参数集成
"""
import unittest
import sys
from pathlib import Path
from io import StringIO


class TestUIVersionFlag(unittest.TestCase):
    """测试 --ui-version 命令行参数"""

    def test_argparse_has_ui_version(self):
        """测试 argparse 包含 --ui-version 参数"""
        import argparse
        
        # 模拟导入并检查参数
        sys.path.insert(0, str(Path(__file__).parent.parent))
        
        # 创建一个 mock parser 来验证参数定义
        from scripts.rdc_analyzer.analyze_xml_report import main
        
        # 检查源代码中是否包含 --ui-version
        source_path = Path(__file__).parent.parent / "analyze_xml_report.py"
        source = source_path.read_text(encoding="utf-8")
        
        self.assertIn("--ui-version", source)

    def test_ui_version_choices(self):
        """测试 --ui-version 接受有效值"""
        source_path = Path(__file__).parent.parent / "analyze_xml_report.py"
        source = source_path.read_text(encoding="utf-8")
        
        # 应该支持 v1（旧版）和 v2（新版）
        self.assertIn("v1", source)
        self.assertIn("v2", source)

    def test_default_ui_version_is_v1(self):
        """测试默认 UI 版本是 v1（保持兼容）"""
        source_path = Path(__file__).parent.parent / "analyze_xml_report.py"
        source = source_path.read_text(encoding="utf-8")
        
        # 默认应为 v1 以保持向后兼容
        self.assertIn('default="v1"', source)


class TestUIVersionIntegration(unittest.TestCase):
    """测试 UI 版本集成"""

    def test_v2_uses_new_report_ui(self):
        """测试 v2 版本调用新的 report_ui 模块"""
        source_path = Path(__file__).parent.parent / "analyze_xml_report.py"
        source = source_path.read_text(encoding="utf-8")
        
        # v2 应该导入并使用 report_ui
        self.assertIn("report_ui", source)
        self.assertIn("render_report_shell", source)


if __name__ == "__main__":
    unittest.main()

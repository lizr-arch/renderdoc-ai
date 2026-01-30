"""
RegressionDetector 单元测试
===========================

TASK-011 测试用例
Created: 2026-01-20
"""

import pytest
import sys
from pathlib import Path

# 添加项目路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from diff.diff_engine import DiffEngine
from diff.diff_types import (
    DiffResult, DiffStatus, MetricDiff, SummaryDiff,
    TextureDiff, ShaderDiff, DrawCallDiff, ResourceDiff
)
from diff.regression_detector import RegressionDetector
from diff.regression_types import (
    RegressionRuleId, RegressionSeverity, RegressionReport, RegressionIssue
)


class TestRegressionDetector:
    """RegressionDetector 基本功能测试"""
    
    @pytest.fixture
    def detector(self):
        return RegressionDetector()
    
    @pytest.fixture
    def empty_diff(self):
        """空差异结果"""
        return DiffResult()
    
    @pytest.fixture
    def diff_with_draw_call_increase(self):
        """Draw Call 增加的差异结果"""
        diff = DiffResult()
        diff.summary = SummaryDiff(
            draw_calls=MetricDiff("draw_calls", 100, 120),  # +20%
            texture_count=MetricDiff("texture_count", 10, 10),
            shader_count=MetricDiff("shader_count", 5, 5),
            buffer_count=MetricDiff("buffer_count", 20, 20),
            triangles=MetricDiff("triangles", 10000, 10000),
        )
        return diff
    
    def test_detect_empty_diff(self, detector, empty_diff):
        """测试空差异检测"""
        report = detector.detect(empty_diff)
        
        assert isinstance(report, RegressionReport)
        assert report.rules_checked == 7  # 默认 7 条规则
        assert not report.is_regression_detected
    
    def test_detect_draw_call_increase(self, detector, diff_with_draw_call_increase):
        """测试 REG001: Draw Call 增加检测"""
        report = detector.detect(diff_with_draw_call_increase)
        
        # 应该触发 REG001 (阈值 5%, 实际 20%)
        reg001_issues = [i for i in report.issues if i.rule_id == RegressionRuleId.REG001]
        assert len(reg001_issues) == 1
        assert reg001_issues[0].delta_percent == 20.0
        assert report.is_regression_detected


class TestREG001DrawCallCount:
    """REG001: Draw Call 数量增加测试"""
    
    def test_below_threshold(self):
        """低于阈值不触发"""
        detector = RegressionDetector()
        diff = DiffResult()
        diff.summary = SummaryDiff(
            draw_calls=MetricDiff("draw_calls", 100, 103),  # +3% < 5%
            texture_count=MetricDiff("texture_count", 10, 10),
            shader_count=MetricDiff("shader_count", 5, 5),
            buffer_count=MetricDiff("buffer_count", 20, 20),
            triangles=MetricDiff("triangles", 10000, 10000),
        )
        
        report = detector.detect(diff)
        reg001 = [i for i in report.issues if i.rule_id == RegressionRuleId.REG001]
        assert len(reg001) == 0
    
    def test_above_threshold(self):
        """超过阈值触发"""
        detector = RegressionDetector()
        diff = DiffResult()
        diff.summary = SummaryDiff(
            draw_calls=MetricDiff("draw_calls", 100, 110),  # +10% > 5%
            texture_count=MetricDiff("texture_count", 10, 10),
            shader_count=MetricDiff("shader_count", 5, 5),
            buffer_count=MetricDiff("buffer_count", 20, 20),
            triangles=MetricDiff("triangles", 10000, 10000),
        )
        
        report = detector.detect(diff)
        reg001 = [i for i in report.issues if i.rule_id == RegressionRuleId.REG001]
        assert len(reg001) == 1
        assert reg001[0].severity == RegressionSeverity.WARNING
    
    def test_custom_threshold(self):
        """自定义阈值"""
        detector = RegressionDetector(
            custom_thresholds={RegressionRuleId.REG001: 15.0}  # 提高到 15%
        )
        diff = DiffResult()
        diff.summary = SummaryDiff(
            draw_calls=MetricDiff("draw_calls", 100, 110),  # +10% < 15%
            texture_count=MetricDiff("texture_count", 10, 10),
            shader_count=MetricDiff("shader_count", 5, 5),
            buffer_count=MetricDiff("buffer_count", 20, 20),
            triangles=MetricDiff("triangles", 10000, 10000),
        )
        
        report = detector.detect(diff)
        reg001 = [i for i in report.issues if i.rule_id == RegressionRuleId.REG001]
        assert len(reg001) == 0  # 不触发，因为阈值提高了


class TestREG002TextureResolution:
    """REG002: 纹理分辨率增加测试"""
    
    def test_texture_resolution_increase(self):
        """纹理分辨率增加检测"""
        detector = RegressionDetector()
        diff = DiffResult()
        diff.summary = SummaryDiff(
            draw_calls=MetricDiff("draw_calls", 100, 100),
            texture_count=MetricDiff("texture_count", 10, 10),
            shader_count=MetricDiff("shader_count", 5, 5),
            buffer_count=MetricDiff("buffer_count", 20, 20),
            triangles=MetricDiff("triangles", 10000, 10000),
        )
        
        # 添加分辨率增加的纹理 (changes 使用 Tuple 格式)
        diff.texture_diffs = [
            TextureDiff(
                resource_id="tex001",
                name="Albedo",
                status=DiffStatus.MODIFIED,
                changes={
                    "width": (1024, 2048),   # (baseline, target)
                    "height": (1024, 2048),
                }
            )
        ]
        
        report = detector.detect(diff)
        reg002 = [i for i in report.issues if i.rule_id == RegressionRuleId.REG002]
        assert len(reg002) == 1
        # 像素增加 4x = 300%
        assert reg002[0].delta_percent == 300.0


class TestREG003ShaderChanges:
    """REG003: Shader 变更测试"""
    
    def test_shader_modified(self):
        """Shader 修改检测"""
        detector = RegressionDetector()
        diff = DiffResult()
        diff.summary = SummaryDiff(
            draw_calls=MetricDiff("draw_calls", 100, 100),
            texture_count=MetricDiff("texture_count", 10, 10),
            shader_count=MetricDiff("shader_count", 5, 5),
            buffer_count=MetricDiff("buffer_count", 20, 20),
            triangles=MetricDiff("triangles", 10000, 10000),
        )
        
        diff.shader_diffs = [
            ShaderDiff("ps001", "MainPS", DiffStatus.MODIFIED, shader_type="PS"),
        ]
        
        report = detector.detect(diff)
        reg003 = [i for i in report.issues if i.rule_id == RegressionRuleId.REG003]
        assert len(reg003) == 1
        assert "代码发生变化" in reg003[0].message
    
    def test_shader_added(self):
        """Shader 新增检测"""
        detector = RegressionDetector()
        diff = DiffResult()
        diff.summary = SummaryDiff(
            draw_calls=MetricDiff("draw_calls", 100, 100),
            texture_count=MetricDiff("texture_count", 10, 10),
            shader_count=MetricDiff("shader_count", 5, 6),
            buffer_count=MetricDiff("buffer_count", 20, 20),
            triangles=MetricDiff("triangles", 10000, 10000),
        )
        
        diff.shader_diffs = [
            ShaderDiff("cs001", "ComputeCS", DiffStatus.ADDED, shader_type="CS"),
        ]
        
        report = detector.detect(diff)
        reg003 = [i for i in report.issues if i.rule_id == RegressionRuleId.REG003]
        assert len(reg003) == 1
        assert "新增" in reg003[0].message


class TestREG004BufferSize:
    """REG004: 缓冲区大小增加测试"""
    
    def test_buffer_size_increase(self):
        """缓冲区大小增加检测"""
        detector = RegressionDetector()
        diff = DiffResult()
        diff.summary = SummaryDiff(
            draw_calls=MetricDiff("draw_calls", 100, 100),
            texture_count=MetricDiff("texture_count", 10, 10),
            shader_count=MetricDiff("shader_count", 5, 5),
            buffer_count=MetricDiff("buffer_count", 20, 20),
            triangles=MetricDiff("triangles", 10000, 10000),
        )
        
        # changes 使用 Tuple 格式 (baseline, target)
        diff.buffer_diffs = [
            ResourceDiff(
                resource_id="buf001",
                name="VertexBuffer",
                status=DiffStatus.MODIFIED,
                changes={"size": (10000, 15000)}  # +50%
            )
        ]
        
        report = detector.detect(diff)
        reg004 = [i for i in report.issues if i.rule_id == RegressionRuleId.REG004]
        assert len(reg004) == 1
        assert reg004[0].delta_percent == 50.0


class TestREG005TriangleCount:
    """REG005: 三角形数量增加测试"""
    
    def test_triangle_count_increase(self):
        """三角形数量增加检测"""
        detector = RegressionDetector()
        diff = DiffResult()
        diff.summary = SummaryDiff(
            draw_calls=MetricDiff("draw_calls", 100, 100),
            texture_count=MetricDiff("texture_count", 10, 10),
            shader_count=MetricDiff("shader_count", 5, 5),
            buffer_count=MetricDiff("buffer_count", 20, 20),
            triangles=MetricDiff("triangles", 10000, 12000),  # +20%
        )
        
        report = detector.detect(diff)
        reg005 = [i for i in report.issues if i.rule_id == RegressionRuleId.REG005]
        assert len(reg005) == 1
        assert reg005[0].severity == RegressionSeverity.CRITICAL  # 三角形增加是严重问题


class TestREG006OverdrawRisk:
    """REG006: Overdraw 风险测试"""
    
    def test_overdraw_detection(self):
        """Overdraw 风险检测"""
        detector = RegressionDetector()
        diff = DiffResult()
        diff.summary = SummaryDiff(
            draw_calls=MetricDiff("draw_calls", 100, 102),
            texture_count=MetricDiff("texture_count", 10, 10),
            shader_count=MetricDiff("shader_count", 5, 5),
            buffer_count=MetricDiff("buffer_count", 20, 20),
            triangles=MetricDiff("triangles", 10000, 10000),
        )
        
        # 多个新增 Draw Call 使用相同顶点数
        # DrawCallDiff 使用 vertex_count 字段
        diff.draw_call_diffs = [
            DrawCallDiff(event_id=101, status=DiffStatus.ADDED, vertex_count=500),
            DrawCallDiff(event_id=102, status=DiffStatus.ADDED, vertex_count=500),
        ]
        
        report = detector.detect(diff)
        reg006 = [i for i in report.issues if i.rule_id == RegressionRuleId.REG006]
        assert len(reg006) == 1
        assert "Overdraw" in reg006[0].message


class TestREG007NewRenderPass:
    """REG007: 新增渲染 Pass 测试"""
    
    def test_new_draw_calls_detected(self):
        """新增 Draw Call 检测"""
        detector = RegressionDetector()
        diff = DiffResult()
        diff.summary = SummaryDiff(
            draw_calls=MetricDiff("draw_calls", 100, 105),
            texture_count=MetricDiff("texture_count", 10, 10),
            shader_count=MetricDiff("shader_count", 5, 5),
            buffer_count=MetricDiff("buffer_count", 20, 20),
            triangles=MetricDiff("triangles", 10000, 10000),
        )
        
        # DrawCallDiff 没有 name 参数，只使用 event_id 和 status
        diff.draw_call_diffs = [
            DrawCallDiff(event_id=101, status=DiffStatus.ADDED, draw_type="DrawIndexed"),
        ]
        
        report = detector.detect(diff)
        reg007 = [i for i in report.issues if i.rule_id == RegressionRuleId.REG007]
        assert len(reg007) == 1
        assert "新增" in reg007[0].message


class TestRuleConfiguration:
    """规则配置测试"""
    
    def test_disable_rule(self):
        """禁用规则"""
        detector = RegressionDetector()
        detector.enable_rule(RegressionRuleId.REG001, False)
        
        diff = DiffResult()
        diff.summary = SummaryDiff(
            draw_calls=MetricDiff("draw_calls", 100, 200),  # +100%
            texture_count=MetricDiff("texture_count", 10, 10),
            shader_count=MetricDiff("shader_count", 5, 5),
            buffer_count=MetricDiff("buffer_count", 20, 20),
            triangles=MetricDiff("triangles", 10000, 10000),
        )
        
        report = detector.detect(diff)
        reg001 = [i for i in report.issues if i.rule_id == RegressionRuleId.REG001]
        assert len(reg001) == 0  # 规则禁用，不触发
        assert report.rules_checked == 6  # 只检查 6 条
    
    def test_set_severity(self):
        """设置严重程度"""
        detector = RegressionDetector()
        detector.set_severity(RegressionRuleId.REG001, RegressionSeverity.CRITICAL)
        
        diff = DiffResult()
        diff.summary = SummaryDiff(
            draw_calls=MetricDiff("draw_calls", 100, 120),  # +20%
            texture_count=MetricDiff("texture_count", 10, 10),
            shader_count=MetricDiff("shader_count", 5, 5),
            buffer_count=MetricDiff("buffer_count", 20, 20),
            triangles=MetricDiff("triangles", 10000, 10000),
        )
        
        report = detector.detect(diff)
        reg001 = [i for i in report.issues if i.rule_id == RegressionRuleId.REG001]
        assert len(reg001) == 1
        assert reg001[0].severity == RegressionSeverity.CRITICAL


class TestRegressionReport:
    """RegressionReport 测试"""
    
    def test_report_statistics(self):
        """报告统计属性"""
        report = RegressionReport()
        report.issues = [
            RegressionIssue(RegressionRuleId.REG001, RegressionSeverity.WARNING, "test1"),
            RegressionIssue(RegressionRuleId.REG005, RegressionSeverity.CRITICAL, "test2"),
            RegressionIssue(RegressionRuleId.REG003, RegressionSeverity.INFO, "test3"),
        ]
        
        assert report.warning_count == 1
        assert report.critical_count == 1
        assert report.info_count == 1
        assert report.has_critical
        assert report.has_warning
        assert report.is_regression_detected
    
    def test_report_to_dict(self):
        """报告序列化"""
        report = RegressionReport()
        report.issues = [
            RegressionIssue(RegressionRuleId.REG001, RegressionSeverity.WARNING, "test"),
        ]
        report.rules_checked = 7
        report.rules_triggered = 1
        
        data = report.to_dict()
        
        assert "issues" in data
        assert "summary" in data
        assert data["rules_checked"] == 7
        assert data["summary"]["warning_count"] == 1


class TestIntegrationWithDiffEngine:
    """与 DiffEngine 集成测试"""
    
    def test_full_pipeline(self):
        """完整流程测试: DiffEngine -> RegressionDetector"""
        baseline = {
            "apiType": "Vulkan",
            "events": [
                {"eventId": 1, "name": "Draw", "indexCount": 1000},
            ],
            "textures": [
                {"resourceId": "tex001", "name": "Albedo", "width": 1024, "height": 1024, "format": "BC7"},
            ],
            "buffers": [],
            "shaders": [
                {"resourceId": "vs001", "type": "VS", "name": "MainVS", "hash": "abc"},
            ],
            "statistics": {
                "totalDrawCalls": 1,
                "totalTriangles": 500,
            }
        }
        
        target = {
            "apiType": "Vulkan",
            "events": [
                {"eventId": 1, "name": "Draw", "indexCount": 1000},
                {"eventId": 2, "name": "Draw", "indexCount": 2000},  # 新增
            ],
            "textures": [
                {"resourceId": "tex001", "name": "Albedo", "width": 2048, "height": 2048, "format": "BC7"},  # 分辨率增加
            ],
            "buffers": [],
            "shaders": [
                {"resourceId": "vs001", "type": "VS", "name": "MainVS", "hash": "xyz"},  # hash 变化
            ],
            "statistics": {
                "totalDrawCalls": 2,
                "totalTriangles": 1500,  # 三角形增加
            }
        }
        
        # Step 1: DiffEngine
        engine = DiffEngine()
        diff_result = engine.compare(baseline, target)
        
        # Step 2: RegressionDetector
        detector = RegressionDetector()
        report = detector.detect(diff_result)
        
        # 验证检测结果
        assert report.is_regression_detected
        
        # 应该触发多个规则
        triggered_rules = {i.rule_id for i in report.issues}
        
        # REG001: Draw Call +100%
        assert RegressionRuleId.REG001 in triggered_rules
        
        # REG002: 纹理分辨率增加 (1024^2 -> 2048^2 = +300%)
        assert RegressionRuleId.REG002 in triggered_rules
        
        # REG003: Shader hash 变化
        assert RegressionRuleId.REG003 in triggered_rules
        
        # REG005: 三角形 +200%
        assert RegressionRuleId.REG005 in triggered_rules


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
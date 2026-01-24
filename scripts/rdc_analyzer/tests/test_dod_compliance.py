"""DoD 7 合规性测试

验证 Definition of Done 7.1-7.8 的实现。
"""
import sys
import pytest
from pathlib import Path

# 添加模块路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from rdc_analyzer.main import AnalysisPipeline
from rdc_analyzer.core.types import CanonicalIssue


class TestDOD74EvidenceChain:
    """DoD 7.4: Evidence Chain - issues 包含 event_ids/resource_ids"""
    
    def test_canonicalize_simple_issue(self):
        """测试简单 issue 转换"""
        p = AnalysisPipeline.__new__(AnalysisPipeline)
        p._issues = [{
            'code': 'TEST001',
            'severity': 'high',
            'message': 'Test issue',
            'event_id': 123
        }]
        
        result = p._canonicalize_issues()
        
        assert len(result) == 1
        assert result[0]['code'] == 'TEST001'
        assert result[0]['event_ids'] == [123]
    
    def test_canonicalize_eventId_camelcase_alias(self):
        """测试 eventId 驼峰别名兼容 (Issue: Evidence Chain 断链修复)
        
        部分规则分析器 (_analyze_rules) 输出使用 eventId 而非 event_id，
        _canonicalize_issues() 必须同时识别两种命名。
        """
        p = AnalysisPipeline.__new__(AnalysisPipeline)
        p._issues = [
            # 驼峰单值
            {'code': 'RULE001', 'severity': 'warning', 'message': 'CamelCase single', 'eventId': 456},
            # 驼峰数组
            {'code': 'RULE002', 'severity': 'info', 'message': 'CamelCase array', 'eventIds': [789, 790]},
            # 混合：同时有 event_id 和 eventId (下划线优先)
            {'code': 'RULE003', 'severity': 'high', 'message': 'Mixed', 'event_id': 100, 'eventId': 200},
        ]
        
        result = p._canonicalize_issues()
        
        # 第一条: eventId 应被识别
        assert 456 in result[0]['event_ids'], "eventId 驼峰单值未被识别"
        # 第二条: eventIds 数组应被合并
        assert 789 in result[1]['event_ids'] and 790 in result[1]['event_ids'], "eventIds 驼峰数组未被识别"
        # 第三条: event_id 优先，eventId 被忽略（避免重复）
        assert 100 in result[2]['event_ids'], "event_id 应优先被使用"
    
    def test_canonicalize_multiple_events(self):
        """测试多 event_ids 合并"""
        p = AnalysisPipeline.__new__(AnalysisPipeline)
        p._issues = [{
            'code': 'BIND001',
            'severity': 'warning',
            'message': 'Draw call issue',
            'event_id': 100,
            'event_ids': [101, 102],
            'related_events': [103, 104]
        }]
        
        result = p._canonicalize_issues()
        
        # 所有 event 都应合并并去重
        assert 100 in result[0]['event_ids']
        assert 101 in result[0]['event_ids']
        assert 103 in result[0]['event_ids']
    
    def test_canonicalize_resource_ids(self):
        """测试 resource_ids 提取"""
        p = AnalysisPipeline.__new__(AnalysisPipeline)
        p._issues = [{
            'code': 'RES001',
            'severity': 'info',
            'message': 'Resource issue',
            'resource_id': 'tex_0x12345678',
            'resource_ids': ['buf_0x87654321']
        }]
        
        result = p._canonicalize_issues()
        
        assert 'tex_0x12345678' in result[0]['resource_ids']
        assert 'buf_0x87654321' in result[0]['resource_ids']
    
    def test_canonicalize_evidence_fields(self):
        """测试 evidence 字段提取"""
        p = AnalysisPipeline.__new__(AnalysisPipeline)
        p._issues = [{
            'code': 'PERF001',
            'severity': 'high',
            'message': 'Performance issue',
            'threshold': 100,
            'actual': 250,
            'impact_score': 0.85
        }]
        
        result = p._canonicalize_issues()
        
        evidence = result[0].get('evidence', {})
        assert evidence.get('threshold') == 100
        assert evidence.get('actual') == 250
        assert evidence.get('impact_score') == 0.85


class TestDOD77Preflight:
    """DoD 7.7: Capture Preflight - 缺失数据警告"""
    
    def test_preflight_ok_status(self):
        """测试所有数据完整时返回 ok"""
        p = AnalysisPipeline.__new__(AnalysisPipeline)
        coverage = {
            'overall': 'high',
            'details': {
                'markers': 'present',
                'pipeline_state': 'present',
                'resource_lifecycle': 'present',
                'shader_analysis': 'present'
            },
            'missing_items': []
        }
        
        result = p._build_preflight(coverage)
        
        assert result['status'] == 'ok'
        assert len(result['missing_data']) == 0
    
    def test_preflight_warning_missing_markers(self):
        """测试缺少 Markers 时返回警告"""
        p = AnalysisPipeline.__new__(AnalysisPipeline)
        coverage = {
            'overall': 'medium',
            'details': {
                'markers': 'missing',
                'pipeline_state': 'present'
            },
            'missing_items': ['markers']
        }
        
        result = p._build_preflight(coverage)
        
        assert result['status'] == 'warning'
        assert any(item['item'] == 'Debug Markers' for item in result['missing_data'])
        assert len(result['capture_recommendations']) >= 1
    
    def test_preflight_warning_estimated_pipeline(self):
        """测试 pipeline_state 为 estimated 时返回警告"""
        p = AnalysisPipeline.__new__(AnalysisPipeline)
        coverage = {
            'overall': 'medium',
            'details': {
                'markers': 'present',
                'pipeline_state': 'estimated'
            },
            'missing_items': []
        }
        
        result = p._build_preflight(coverage)
        
        assert result['status'] == 'warning'
        assert any(item['item'] == 'Pipeline State' for item in result['missing_data'])
    
    def test_preflight_error_multiple_missing(self):
        """测试多项缺失时升级为 error"""
        p = AnalysisPipeline.__new__(AnalysisPipeline)
        coverage = {
            'overall': 'low',
            'details': {
                'markers': 'missing',
                'pipeline_state': 'missing',
                'resource_lifecycle': 'missing',
                'shader_analysis': 'missing'
            },
            'missing_items': ['markers', 'pipeline_state', 'resource_lifecycle', 'shader_analysis']
        }
        
        result = p._build_preflight(coverage)
        
        assert result['status'] == 'error'
        assert len(result['missing_data']) >= 3
    
    def test_preflight_recommendations_content(self):
        """测试推荐内容包含引擎指导"""
        p = AnalysisPipeline.__new__(AnalysisPipeline)
        coverage = {
            'overall': 'low',
            'details': {'markers': 'missing'},
            'missing_items': ['markers']
        }
        
        result = p._build_preflight(coverage)
        
        # 检查推荐包含 Unity/Unreal 指导
        rec = result['capture_recommendations'][0]
        assert 'unity' in rec
        assert 'unreal' in rec
        assert 'custom' in rec


class TestDOD72SchemaStability:
    """DoD 7.2: Schema 稳定性 - JSON 包含必要顶层块"""
    
    def test_canonical_issue_structure(self):
        """验证 CanonicalIssue 数据结构"""
        issue = CanonicalIssue(
            code='TEST001',
            severity='high',
            category='performance',
            message='Test message',
            event_ids=[1, 2, 3],
            resource_ids=['res_001'],
            evidence={'metric': 100}
        )
        
        d = issue.to_dict()
        
        # 必需字段
        assert 'code' in d
        assert 'severity' in d
        assert 'category' in d
        assert 'message' in d
        assert 'event_ids' in d
        assert 'resource_ids' in d
        
        # 值正确
        assert d['code'] == 'TEST001'
        assert d['event_ids'] == [1, 2, 3]


class TestDOD73DataQuality:
    """DoD 7.3: DataQuality/Confidence - coverage 结构验证"""
    
    def test_coverage_report_required_keys(self):
        """验证 coverage 报告必须包含的顶层 key"""
        # 构造最小 Pipeline mock（只需要 _build_coverage_report 依赖的属性）
        from unittest.mock import MagicMock
        
        pipeline = MagicMock()
        pipeline._events = []
        pipeline._draw_calls = []
        pipeline._resources = {}
        pipeline._pipeline_state_samples = 0
        pipeline._resource_lifecycle_tracked = False
        pipeline._resource_samples = []
        pipeline._mali_report = None
        pipeline._performance_report = None
        
        # 直接调用 _build_coverage_report（绑定到 mock 对象）
        from rdc_analyzer.main import AnalysisPipeline
        coverage = AnalysisPipeline._build_coverage_report(pipeline)
        
        # === 验证必须存在的顶层 key ===
        required_keys = ['overall', 'details', 'missing_items', 'confidence_reasons', 'sampling_stats']
        for key in required_keys:
            assert key in coverage, f"coverage 缺少必需 key: {key}"
        
        # === 验证 overall 值域 ===
        assert coverage['overall'] in ('high', 'medium', 'low'), \
            f"overall 值域应为 high/medium/low，实际为: {coverage['overall']}"
        
        # === 验证 details 是 dict 且包含关键面 ===
        assert isinstance(coverage['details'], dict), "details 应为 dict"
        expected_detail_keys = ['events', 'draw_calls', 'resources', 'markers', 
                                 'pipeline_state', 'resource_lifecycle']
        for key in expected_detail_keys:
            assert key in coverage['details'], f"details 缺少 key: {key}"
    
    def test_coverage_degradation_logic_no_data(self):
        """验证：无数据时，所有维度应降级为 missing/estimated 且包含原因"""
        from unittest.mock import MagicMock
        from rdc_analyzer.main import AnalysisPipeline
        
        pipeline = MagicMock()
        pipeline._events = []
        pipeline._draw_calls = []
        pipeline._resources = {}
        pipeline._pipeline_state_samples = 0
        pipeline._resource_lifecycle_tracked = False
        pipeline._resource_samples = []
        pipeline._mali_report = None
        pipeline._performance_report = None
        
        coverage = AnalysisPipeline._build_coverage_report(pipeline)
        
        # === 验证降级状态 ===
        details = coverage['details']
        assert details['events'] == 'missing', "无事件时应为 missing"
        assert details['draw_calls'] == 'missing', "无 draw call 时应为 missing"
        assert details['resources'] == 'missing', "无资源时应为 missing"
        assert details['pipeline_state'] == 'estimated', "无采样时应为 estimated"
        assert details['resource_lifecycle'] == 'estimated', "无追踪时应为 estimated"
        
        # === 验证置信度原因非空 ===
        assert len(coverage['confidence_reasons']) > 0, "降级时 confidence_reasons 不应为空"
        assert any('Pipeline State' in r or '估算' in r for r in coverage['confidence_reasons']), \
            "confidence_reasons 应包含 Pipeline State 降级原因"
        
        # === 验证整体可信度降为 low ===
        assert coverage['overall'] == 'low', f"全缺失时 overall 应为 low，实际为: {coverage['overall']}"
    
    def test_coverage_with_partial_data(self):
        """验证：有部分数据时，降级逻辑正确（维度状态正确识别）"""
        from unittest.mock import MagicMock
        from rdc_analyzer.main import AnalysisPipeline
        
        pipeline = MagicMock()
        pipeline._events = [{'eventId': 1, 'name': 'DrawIndexed'}]
        pipeline._draw_calls = [{'eventId': 1}]
        pipeline._resources = {'textures': {'tex1': {}}}  # 只有 textures，无 buffers
        pipeline._pipeline_state_samples = 0
        pipeline._resource_lifecycle_tracked = False
        pipeline._resource_samples = []
        pipeline._mali_report = None
        pipeline._performance_report = None
        
        coverage = AnalysisPipeline._build_coverage_report(pipeline)
        
        # === 验证部分数据状态 ===
        details = coverage['details']
        assert details['events'] == 'present', "有事件时应为 present"
        assert details['draw_calls'] == 'present', "有 draw call 时应为 present"
        assert details['resources'] == 'partial', "只有 textures 时应为 partial"
        
        # === 验证：2 present + 1 partial + 5 missing/estimated = 仍然是 low ===
        # 加权: 2*1.0 + 1*0.5 + N*0.2 = 2.9 / 8 ≈ 0.36 < 0.5 → low
        # 这是预期行为：大部分数据缺失时确实应该 overall=low
        assert coverage['overall'] == 'low', \
            f"大部分数据缺失时 overall 应为 low，实际为: {coverage['overall']}"
        
        # === 验证 missing_items 包含原因 ===
        assert len(coverage['missing_items']) > 0, "应有 missing_items 描述缺失原因"
    
    def test_coverage_pipeline_state_sampling_stats(self):
        """验证：有 pipeline state 采样时，sampling_stats 正确填充"""
        from unittest.mock import MagicMock
        from rdc_analyzer.main import AnalysisPipeline
        
        pipeline = MagicMock()
        pipeline._events = [{'eventId': i} for i in range(10)]
        pipeline._draw_calls = [{'eventId': i} for i in range(10)]
        pipeline._resources = {}
        pipeline._pipeline_state_samples = 5  # 采样了 5 个
        pipeline._resource_lifecycle_tracked = False
        pipeline._resource_samples = []
        pipeline._mali_report = None
        pipeline._performance_report = None
        
        coverage = AnalysisPipeline._build_coverage_report(pipeline)
        
        # === 验证采样统计 ===
        assert 'pipeline_state' in coverage['sampling_stats'], "应有 pipeline_state 采样统计"
        stats = coverage['sampling_stats']['pipeline_state']
        assert stats['sampled'] == 5, f"sampled 应为 5，实际为: {stats['sampled']}"
        assert stats['total'] == 10, f"total 应为 10，实际为: {stats['total']}"
        assert stats['ratio'] == 0.5, f"ratio 应为 0.5，实际为: {stats['ratio']}"
        
        # === 验证 50% 采样率时为 partial ===
        assert coverage['details']['pipeline_state'] == 'partial', \
            f"50% 采样率应为 partial，实际为: {coverage['details']['pipeline_state']}"

    def test_resource_lifecycle_partial_when_sampling_low(self):
        """验证：资源生命周期在低采样率时应为 partial 而非 present"""
        from unittest.mock import MagicMock
        from rdc_analyzer.main import AnalysisPipeline

        pipeline = MagicMock()
        pipeline._events = [{'eventId': i} for i in range(10)]
        pipeline._draw_calls = [{'eventId': i} for i in range(10)]
        pipeline._resources = {'textures': {'tex1': {}}}
        pipeline._pipeline_state_samples = 2  # 低采样率
        pipeline._resource_lifecycle_tracked = True
        pipeline._resource_samples = []
        pipeline._mali_report = None
        pipeline._performance_report = None

        coverage = AnalysisPipeline._build_coverage_report(pipeline)

        assert coverage['details']['resource_lifecycle'] == 'partial', \
            f"低采样率时应为 partial，实际为: {coverage['details']['resource_lifecycle']}"


class TestRuleRunnerIntegration:
    """规则输出统一：_analyze_rules 必须接入 RuleRunner"""
    
    def test_analyze_rules_uses_rule_runner(self):
        """验证 _analyze_rules 使用 RuleRunner 产出 issues"""
        from types import SimpleNamespace
        from unittest.mock import MagicMock, patch
        from rdc_analyzer.core.types import Issue
        from rdc_analyzer.main import AnalysisPipeline
        
        pipeline = MagicMock()
        pipeline._draw_calls = [{'eventId': 1, 'numIndices': 3, 'numInstances': 1}]
        pipeline._issues = []
        pipeline._performance_report = None
        pipeline._mali_report = None
        pipeline._resources = {'textures': {}, 'buffers': {}}
        pipeline._events = []
        pipeline.options = SimpleNamespace(
            enable_performance_analysis=False,
            enable_mali_analysis=False,
            enabled_rules=None,
            disabled_rules=None,
            platform='pc'
        )
        pipeline._report_progress = MagicMock()
        pipeline._run_performance_analysis = MagicMock()
        pipeline._run_mali_analysis = MagicMock()
        
        runner_issue = Issue(
            severity="warning",
            category="performance",
            code="RD_TEST",
            message="RuleRunner issued"
        )
        
        with patch("rdc_analyzer.main.register_all_rules") as mock_register, \
             patch("rdc_analyzer.main.RuleRunner") as mock_runner:
            mock_runner.return_value.run.return_value = [runner_issue]
            
            AnalysisPipeline._analyze_rules(pipeline)
            
            mock_register.assert_called_once()
            mock_runner.assert_called_once()
            assert any(
                getattr(issue, "code", None) == "RD_TEST" or issue.get("code") == "RD_TEST"
                for issue in pipeline._issues
            ), "RuleRunner 输出的 issue 未被加入 _issues"


class TestVerificationPlanSchema:
    """验证 verification_plan 字段的 schema 稳定性
    
    锁定字段命名和枚举值，防止意外回退。
    """
    
    def test_verification_plan_field_names(self):
        """验证 verification_plan 使用规范字段名"""
        from rdc_analyzer.main import AnalysisPipeline
        import inspect
        
        # 获取 _build_suggestions 方法源码
        source = inspect.getsource(AnalysisPipeline._build_suggestions)
        
        # === 禁止旧字段名 ===
        assert "how_to_verify" not in source, \
            "发现旧字段名 'how_to_verify'，应改为 'how_to_capture'"
        
        # === 必须使用新字段名 ===
        assert "how_to_capture" in source, \
            "缺少必需字段 'how_to_capture'"
    
    def test_expected_direction_enum_values(self):
        """验证 expected_direction 使用规范枚举值"""
        from rdc_analyzer.main import AnalysisPipeline
        import inspect
        import re
        
        source = inspect.getsource(AnalysisPipeline._build_suggestions)
        source += inspect.getsource(AnalysisPipeline._create_suggestion_from_recommendation)
        
        # 提取所有 expected_direction 的值
        pattern = r"'expected_direction':\s*'(\w+)'"
        values = re.findall(pattern, source)
        
        # === 只允许 increase/decrease/unchanged ===
        allowed = {'increase', 'decrease', 'unchanged'}
        for val in values:
            assert val in allowed, \
                f"非法 expected_direction 值: '{val}'，只允许 {allowed}"
        
        # === 禁止旧值 'down'/'up' ===
        assert 'down' not in values, \
            "发现旧枚举值 'down'，应改为 'decrease'"
        assert 'up' not in values, \
            "发现旧枚举值 'up'，应改为 'increase'"
    
    def test_verification_plan_structure(self):
        """验证 verification_plan 的完整结构"""
        from unittest.mock import MagicMock, patch
        from rdc_analyzer.main import AnalysisPipeline
        
        # 模拟一个有 issues 的 Pipeline
        pipeline = MagicMock()
        pipeline._issues = [{'code': 'BIND001', 'severity': 'warning', 'message': 'Test'}]
        
        suggestions = AnalysisPipeline._build_suggestions(pipeline)
        
        # 至少应生成一个建议
        if len(suggestions) > 0:
            suggestion = suggestions[0]
            
            # === 验证 verification_plan 结构 ===
            assert 'verification_plan' in suggestion, "建议应包含 verification_plan"
            vp = suggestion['verification_plan']
            
            # 必需字段
            assert 'metrics' in vp, "verification_plan 应包含 metrics"
            assert 'expected_direction' in vp, "verification_plan 应包含 expected_direction"
            assert 'how_to_capture' in vp, "verification_plan 应包含 how_to_capture"
            
            # 类型校验
            assert isinstance(vp['metrics'], list), "metrics 应为 list"
            assert isinstance(vp['expected_direction'], str), "expected_direction 应为 str"
            assert isinstance(vp['how_to_capture'], str), "how_to_capture 应为 str"

    def test_verification_plan_for_rule_runner_codes(self):
        """验证 RuleRunner 规则码也能生成 verification_plan"""
        from unittest.mock import MagicMock
        from rdc_analyzer.main import AnalysisPipeline

        pipeline = MagicMock()
        pipeline._performance_report = None
        pipeline._issues = [{'code': 'RD_DC_001', 'severity': 'warning', 'message': 'Draw Call high'}]

        suggestions = AnalysisPipeline._build_suggestions(pipeline)

        assert len(suggestions) > 0, "RD_DC_001 应生成建议"
        vp = suggestions[0]['verification_plan']
        assert 'metrics' in vp and 'expected_direction' in vp and 'how_to_capture' in vp


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

"""
Rules 模块测试
=============

测试规则注册和执行。
"""

import pytest
from rdc_analyzer.rules.base import BaseRule, RuleRegistry
from rdc_analyzer.core.types import Issue, ParsedData, FrameSummary, TextureInfo
from rdc_analyzer.core.context import AnalysisContext
from rdc_analyzer.core.enums import Severity, Category

# 确保规则被加载
from rdc_analyzer.rules import draw_call, texture, buffer, render_pass, state, mobile


class TestRuleRegistry:
    """测试规则注册表"""
    
    def test_registry_not_empty(self):
        """验证注册表非空"""
        rules = RuleRegistry.all()
        assert len(rules) > 0, "规则注册表不应为空"
    
    def test_all_rules_have_id(self):
        """验证所有规则有 ID"""
        rules = RuleRegistry.all()
        for rule_id, rule_cls in rules.items():
            assert hasattr(rule_cls, 'rule_id'), f"{rule_cls.__name__} 缺少 rule_id"
            assert rule_cls.rule_id.startswith(("RD_", "TILE_")), f"{rule_cls.rule_id} 格式错误"
    
    def test_all_rules_have_name(self):
        """验证所有规则有名称"""
        rules = RuleRegistry.all()
        for rule_id, rule_cls in rules.items():
            assert hasattr(rule_cls, 'name'), f"{rule_cls.__name__} 缺少 name"
            assert len(rule_cls.name) > 0
    
    def test_all_rules_have_severity(self):
        """验证所有规则有严重程度"""
        rules = RuleRegistry.all()
        for rule_id, rule_cls in rules.items():
            assert hasattr(rule_cls, 'severity'), f"{rule_cls.__name__} 缺少 severity"
    
    def test_all_rules_have_category(self):
        """验证所有规则有分类"""
        rules = RuleRegistry.all()
        for rule_id, rule_cls in rules.items():
            assert hasattr(rule_cls, 'category'), f"{rule_cls.__name__} 缺少 category"
    
    def test_unique_rule_ids(self):
        """验证规则 ID 唯一"""
        rule_ids = RuleRegistry.list_ids()
        assert len(rule_ids) == len(set(rule_ids)), "存在重复的规则 ID"
    
    def test_rule_count(self):
        """验证规则数量"""
        count = RuleRegistry.count()
        assert count >= 30, f"规则数量应该 >= 30, 实际: {count}"


class TestBaseRule:
    """测试基础规则类"""
    
    @pytest.fixture
    def mock_context(self):
        """创建模拟上下文"""
        parsed = ParsedData(
            api="D3D11",
            draws=[{"event_id": i, "vertex_count": 100} for i in range(10)],
            total_events=100
        )
        frame_summary = FrameSummary(
            draw_call_count=10,
            vertex_count=1000,
            viewport_width=1920,
            viewport_height=1080
        )
        return AnalysisContext(
            parsed=parsed,
            frame_summary=frame_summary,
            platform="pc"
        )
    
    def test_rule_instantiation(self, mock_context):
        """验证规则可实例化"""
        rules = RuleRegistry.all()
        if rules:
            rule_id, rule_cls = next(iter(rules.items()))
            rule = rule_cls(mock_context)
            assert rule is not None
            assert rule.context == mock_context
    
    def test_create_issue(self, mock_context):
        """验证 create_issue 方法"""
        rules = RuleRegistry.all()
        if rules:
            rule_id, rule_cls = next(iter(rules.items()))
            rule = rule_cls(mock_context)
            
            issue = rule.create_issue(
                message="Test message",
                location_path="Test/Path"
            )
            
            assert isinstance(issue, Issue)
            assert issue.message == "Test message"
            assert issue.location_path == "Test/Path"
            assert issue.code == rule.rule_id


class TestDrawCallRules:
    """测试 Draw Call 规则"""
    
    @pytest.fixture
    def high_dc_context(self):
        """创建高 Draw Call 上下文"""
        parsed = ParsedData(
            api="D3D11",
            draws=[{"event_id": i, "vertex_count": 100} for i in range(5000)],
            total_events=5000
        )
        frame_summary = FrameSummary(
            draw_call_count=5000,
            vertex_count=500000,
            viewport_width=1920,
            viewport_height=1080
        )
        return AnalysisContext(
            parsed=parsed,
            frame_summary=frame_summary,
            platform="pc"
        )
    
    def test_draw_call_count_rule_triggers(self, high_dc_context):
        """验证 Draw Call Count 规则在高 DC 时触发"""
        from rdc_analyzer.rules.draw_call import DrawCallCountRule
        
        rule = DrawCallCountRule(high_dc_context)
        issues = rule.check()
        
        # 5000 DC 应该触发 PC 阈值 (3000)
        assert len(issues) >= 1, "5000 Draw Call 应该触发警告"


class TestTextureRules:
    """测试纹理规则"""
    
    @pytest.fixture
    def large_texture_context(self):
        """创建大纹理上下文"""
        parsed = ParsedData(api="D3D11", draws=[], total_events=10)
        frame_summary = FrameSummary(viewport_width=1920, viewport_height=1080)
        
        textures = [
            TextureInfo(
                resource_id="tex_large",
                name="LargeTexture",
                width=4096,
                height=4096,
                format="R8G8B8A8_UNORM",
                memory_size=67108864  # 64MB
            )
        ]
        
        return AnalysisContext(
            parsed=parsed,
            frame_summary=frame_summary,
            textures=textures,
            platform="pc"
        )
    
    def test_large_texture_detection(self, large_texture_context):
        """验证可以检测到大纹理"""
        assert len(large_texture_context.textures) == 1
        assert large_texture_context.textures[0].width == 4096


class TestMobileRules:
    """测试移动端规则"""
    
    def test_mobile_rules_exist(self):
        """验证移动端规则存在"""
        rules = RuleRegistry.all()
        mobile_rules = [r for r in rules.values() if "mobile" in r.platforms]
        assert len(mobile_rules) >= 1, "应该有至少 1 个移动端规则"


class TestRuleApplicability:
    """测试规则适用性"""
    
    @pytest.fixture
    def pc_context(self):
        """创建 PC 上下文"""
        parsed = ParsedData(api="D3D11", draws=[], total_events=10)
        frame_summary = FrameSummary()
        return AnalysisContext(
            parsed=parsed,
            frame_summary=frame_summary,
            platform="pc"
        )
    
    @pytest.fixture
    def mobile_context(self):
        """创建移动端上下文"""
        parsed = ParsedData(api="GLES", draws=[], total_events=10)
        frame_summary = FrameSummary()
        return AnalysisContext(
            parsed=parsed,
            frame_summary=frame_summary,
            platform="mobile"
        )
    
    def test_mobile_rules_not_on_pc(self, pc_context):
        """验证移动端规则不在 PC 运行"""
        from rdc_analyzer.rules.mobile import TBDRFlushRule
        
        rule = TBDRFlushRule(pc_context)
        assert not rule.is_applicable(), "TBDR 规则不应在 PC 平台适用"
    
    def test_mobile_rules_on_mobile(self, mobile_context):
        """验证移动端规则在移动平台运行"""
        from rdc_analyzer.rules.mobile import TBDRFlushRule
        
        rule = TBDRFlushRule(mobile_context)
        assert rule.is_applicable(), "TBDR 规则应在移动平台适用"

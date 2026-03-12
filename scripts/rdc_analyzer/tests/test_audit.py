#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
审计模块测试
============

测试 AuditEngine 和 AuditReport 的核心功能。
"""

import pytest
from datetime import datetime


class TestAuditSeverity:
    """测试审计严重程度枚举"""
    
    def test_severity_values(self):
        """测试严重程度枚举值"""
        from rdc_analyzer.audit.report import AuditSeverity
        
        # 验证枚举存在
        assert AuditSeverity.CRITICAL.value == "critical"
        assert AuditSeverity.WARNING.value == "warning"
        assert AuditSeverity.INFO.value == "info"
        assert AuditSeverity.PASS.value == "pass"


class TestAssetCategory:
    """测试资产分类枚举"""
    
    def test_category_values(self):
        """测试分类枚举值"""
        from rdc_analyzer.audit.report import AssetCategory
        
        assert AssetCategory.TEXTURE.value == "texture"
        assert AssetCategory.BUFFER.value == "buffer"
        assert AssetCategory.SHADER.value == "shader"


class TestAuditIssue:
    """测试审计问题数据类"""
    
    def test_issue_creation(self):
        """测试创建问题"""
        from rdc_analyzer.audit.report import (
            AuditIssue, AuditSeverity, AssetCategory
        )
        
        issue = AuditIssue(
            rule_id="AUD001",
            category=AssetCategory.TEXTURE,
            severity=AuditSeverity.WARNING,
            message="纹理过大",
            resource_id="tex_0001",
            suggestion="考虑降低分辨率"
        )
        
        assert issue.rule_id == "AUD001"
        assert issue.severity == AuditSeverity.WARNING
        assert issue.resource_id == "tex_0001"
    
    def test_issue_to_dict(self):
        """测试问题序列化"""
        from rdc_analyzer.audit.report import (
            AuditIssue, AuditSeverity, AssetCategory
        )
        
        issue = AuditIssue(
            rule_id="AUD002",
            category=AssetCategory.BUFFER,
            severity=AuditSeverity.CRITICAL,
            message="Buffer 内存过大"
        )
        
        d = issue.to_dict()
        assert d["rule_id"] == "AUD002"
        assert d["severity"] == "critical"  # 枚举值为小写
        assert d["category"] == "buffer"


class TestAuditPreset:
    """测试审计预设"""
    
    def test_default_preset(self):
        """测试默认预设"""
        from rdc_analyzer.audit.engine import PRESETS
        
        default = PRESETS["default"]
        assert default.max_texture_size == 2048
        assert default.max_texture_memory_mb == 16.0
        assert default.check_npot is False
    
    def test_mobile_preset(self):
        """测试移动端预设"""
        from rdc_analyzer.audit.engine import PRESETS
        
        mobile = PRESETS["mobile"]
        assert mobile.max_texture_size == 2048
        assert mobile.max_texture_memory_mb == 8.0
        assert mobile.check_npot is True
    
    def test_pc_preset(self):
        """测试 PC 预设"""
        from rdc_analyzer.audit.engine import PRESETS
        
        pc = PRESETS["pc"]
        assert pc.max_texture_size == 4096
        assert pc.max_texture_memory_mb == 32.0
    
    def test_strict_preset(self):
        """测试严格预设"""
        from rdc_analyzer.audit.engine import PRESETS
        
        strict = PRESETS["strict"]
        assert strict.max_texture_size == 1024
        assert strict.strict_mode is True


class TestAuditEngine:
    """测试审计引擎"""
    
    @pytest.fixture
    def sample_capture_data(self):
        """创建示例捕获数据"""
        return {
            "textures": [
                {
                    "resource_id": "tex_001",
                    "name": "diffuse_map",
                    "width": 2048,
                    "height": 2048,
                    "format": "BC1_UNORM",
                    "mip_levels": 1,
                    "memory_size": 2097152,  # 2MB
                },
                {
                    "resource_id": "tex_002",
                    "name": "normal_map",
                    "width": 4096,
                    "height": 4096,
                    "format": "R8G8B8A8_UNORM",
                    "mip_levels": 11,
                    "memory_size": 67108864,  # 64MB
                },
                {
                    "resource_id": "tex_003",
                    "name": "small_icon",
                    "width": 100,
                    "height": 100,
                    "format": "R8G8B8A8_UNORM",
                    "mip_levels": 1,
                    "memory_size": 40000,
                },
            ],
            "buffers": [
                {
                    "resource_id": "buf_001",
                    "name": "vertex_buffer",
                    "size": 1048576,  # 1MB
                    "usage": "vertex",
                },
            ],
            "draw_calls": [],
        }
    
    def test_engine_creation_default(self):
        """测试默认引擎创建 (PC 平台自动选择 pc 预设)"""
        from rdc_analyzer.audit.engine import AuditEngine
        
        engine = AuditEngine()
        assert engine.platform == "pc"
        # 注意：默认 platform="pc" 会选择 "pc" 预设，而非 "default"
        assert engine.preset.name == "pc"
    
    def test_engine_creation_mobile(self):
        """测试移动端引擎创建"""
        from rdc_analyzer.audit.engine import AuditEngine
        
        engine = AuditEngine(platform="mobile")
        assert engine.platform == "mobile"
        assert engine.preset.name == "mobile"
    
    def test_engine_with_preset_override(self):
        """测试预设覆盖"""
        from rdc_analyzer.audit.engine import AuditEngine
        
        engine = AuditEngine(platform="pc", preset="strict")
        assert engine.preset.name == "strict"
    
    def test_audit_basic(self, sample_capture_data):
        """测试基本审计"""
        from rdc_analyzer.audit.engine import AuditEngine
        
        engine = AuditEngine(platform="pc", preset="pc")
        report = engine.audit(sample_capture_data)
        
        assert report is not None
        assert len(report.textures) == 3
        assert len(report.buffers) == 1
    
    def test_audit_detect_oversized_texture(self, sample_capture_data):
        """测试检测超大纹理 (使用 strict 预设)"""
        from rdc_analyzer.audit.engine import AuditEngine
        from rdc_analyzer.audit.report import AuditSeverity
        
        engine = AuditEngine(preset="strict")  # 1024 上限
        report = engine.audit(sample_capture_data)
        
        # 应检测到 2048 和 4096 纹理超标 (rule_id: AUD_TEX_001)
        oversized_issues = [
            i for i in report.issues 
            if "AUD_TEX_001" in i.rule_id or "尺寸过大" in i.message
        ]
        assert len(oversized_issues) >= 2
    
    def test_audit_detect_no_mipmaps(self, sample_capture_data):
        """测试检测缺少 Mipmap"""
        from rdc_analyzer.audit.engine import AuditEngine
        
        engine = AuditEngine(preset="default")
        report = engine.audit(sample_capture_data)
        
        # tex_001 (2048x2048, mip=1) 应触发警告
        mipmap_issues = [
            i for i in report.issues 
            if "mipmap" in i.rule_id.lower() or "mip" in i.message.lower()
        ]
        assert len(mipmap_issues) >= 1
    
    def test_audit_detect_npot(self, sample_capture_data):
        """测试检测非 2 次幂纹理"""
        from rdc_analyzer.audit.engine import AuditEngine
        
        engine = AuditEngine(platform="mobile")  # mobile 启用 NPOT 检测
        report = engine.audit(sample_capture_data)
        
        # tex_003 (100x100) 应触发 NPOT 警告 (rule_id: AUD_TEX_005)
        npot_issues = [
            i for i in report.issues 
            if "AUD_TEX_005" in i.rule_id or "2 次幂" in i.message or "非 2 次幂" in i.message
        ]
        assert len(npot_issues) >= 1
    
    def test_audit_detect_high_memory(self, sample_capture_data):
        """测试检测高内存纹理"""
        from rdc_analyzer.audit.engine import AuditEngine
        
        engine = AuditEngine(preset="mobile")  # 8MB 上限
        report = engine.audit(sample_capture_data)
        
        # tex_002 (64MB) 应触发严重警告
        mem_issues = [
            i for i in report.issues 
            if "memory" in i.rule_id.lower() or "内存" in i.message
        ]
        assert len(mem_issues) >= 1


class TestAuditReport:
    """测试审计报告"""
    
    def test_report_creation(self):
        """测试创建报告"""
        from rdc_analyzer.audit.report import AuditReport
        
        report = AuditReport(
            file_path="test.json",
            platform="pc",
            preset="default"
        )
        
        assert report.file_path == "test.json"
        assert report.platform == "pc"
        assert len(report.issues) == 0
    
    def test_report_add_issue(self):
        """测试添加问题"""
        from rdc_analyzer.audit.report import (
            AuditReport, AuditIssue, AuditSeverity, AssetCategory
        )
        
        report = AuditReport(file_path="test.json", platform="pc", preset="default")
        
        issue = AuditIssue(
            rule_id="AUD001",
            category=AssetCategory.TEXTURE,
            severity=AuditSeverity.WARNING,
            message="测试问题"
        )
        report.add_issue(issue)
        
        assert len(report.issues) == 1
        assert report.summary.warning_count == 1
    
    def test_report_has_critical(self):
        """测试 has_critical 属性"""
        from rdc_analyzer.audit.report import (
            AuditReport, AuditIssue, AuditSeverity, AssetCategory
        )
        
        report = AuditReport(file_path="test.json", platform="pc", preset="default")
        assert report.has_critical is False
        
        report.add_issue(AuditIssue(
            rule_id="AUD001",
            category=AssetCategory.TEXTURE,
            severity=AuditSeverity.CRITICAL,
            message="严重问题"
        ))
        
        assert report.has_critical is True
    
    def test_report_grade(self):
        """测试评级计算"""
        from rdc_analyzer.audit.report import (
            AuditReport, AuditIssue, AuditSeverity, AssetCategory
        )
        
        # 无问题 -> A
        report_a = AuditReport(file_path="test.json", platform="pc", preset="default")
        assert report_a.summary.grade == "A"
        
        # 有警告 -> C 或更低
        report_c = AuditReport(file_path="test.json", platform="pc", preset="default")
        for _ in range(3):
            report_c.add_issue(AuditIssue(
                rule_id="AUD001",
                category=AssetCategory.TEXTURE,
                severity=AuditSeverity.WARNING,
                message="警告"
            ))
        assert report_c.summary.grade in ("B", "C", "D")
        
        # 有严重问题 -> F
        report_f = AuditReport(file_path="test.json", platform="pc", preset="default")
        report_f.add_issue(AuditIssue(
            rule_id="AUD001",
            category=AssetCategory.TEXTURE,
            severity=AuditSeverity.CRITICAL,
            message="严重问题"
        ))
        assert report_f.summary.grade == "F"
    
    def test_report_to_dict(self):
        """测试报告序列化"""
        from rdc_analyzer.audit.report import AuditReport
        
        report = AuditReport(
            file_path="test.json",
            platform="mobile",
            preset="mobile"
        )
        
        d = report.to_dict()
        assert d["file_path"] == "test.json"
        assert d["platform"] == "mobile"
        assert "summary" in d
        assert "issues" in d
    
    def test_format_summary(self):
        """测试摘要格式化"""
        from rdc_analyzer.audit.report import AuditReport
        
        report = AuditReport(
            file_path="test.json",
            platform="pc",
            preset="default"
        )
        
        summary_text = report.format_summary()
        assert "评级" in summary_text or "Grade" in summary_text or "A" in summary_text


class TestAuditIntegration:
    """集成测试"""
    
    def test_full_audit_flow(self):
        """测试完整审计流程"""
        from rdc_analyzer.audit import AuditEngine, AuditReport
        
        # 创建测试数据
        capture_data = {
            "textures": [
                {
                    "resource_id": "tex_001",
                    "name": "large_texture",
                    "width": 8192,
                    "height": 8192,
                    "format": "R8G8B8A8_UNORM",
                    "mip_levels": 1,
                    "memory_size": 268435456,  # 256MB
                }
            ],
            "buffers": [],
            "draw_calls": [],
        }
        
        # 使用严格预设
        engine = AuditEngine(preset="strict")
        report = engine.audit(capture_data, file_path="test_capture.json")
        
        # 验证
        assert report.has_critical  # 256MB 纹理应触发严重警告
        assert report.summary.grade == "F"
        assert len(report.issues) >= 1
    
    def test_audit_empty_capture(self):
        """测试空捕获数据"""
        from rdc_analyzer.audit import AuditEngine
        
        engine = AuditEngine()
        report = engine.audit({}, file_path="empty.json")
        
        assert report.summary.grade == "A"
        assert len(report.issues) == 0


class TestCLIAuditCommand:
    """测试 CLI audit 命令参数解析"""
    
    def test_audit_parser_exists(self):
        """测试 audit 子命令存在"""
        import argparse
        from rdc_analyzer.__main__ import main
        
        # 验证 audit 命令被注册
        # 通过尝试解析参数来验证
        import sys
        old_argv = sys.argv
        try:
            sys.argv = ["rdc_analyzer", "audit", "--help"]
            with pytest.raises(SystemExit) as exc_info:
                main()
            # --help 应该返回 0
            assert exc_info.value.code == 0
        except SystemExit:
            pass
        finally:
            sys.argv = old_argv

#!/usr/bin/env python3
"""
测试 M3.3 数据管道完整性

验证 PerformanceIssue → CanonicalIssue → JSON → HTML 的 evidence 字段传递
"""

import json
import pytest
import sys
from pathlib import Path

# 添加 rdc_analyzer 到 path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.types import (
    PerformanceIssue,
    EvidenceChain,
    ContextEvidence,
    Action
)
from report_bundle_generator import ReportBundleGenerator


class TestEvidenceChainDataPipeline:
    """测试证据链数据管道完整性"""
    
    def test_evidence_chain_to_dict(self):
        """EvidenceChain.to_dict() 生成正确的字典结构"""
        chain = EvidenceChain(
            issue_code="TEX-001",
            summary="测试证据链",
            evidences=[
                ContextEvidence(
                    type="metric",
                    label="纹理大小",
                    value=4096,
                    threshold=2048,
                    unit="px",
                    severity="warning"
                )
            ],
            actions=[
                Action(
                    type="jump",
                    label="查看纹理",
                    target_page="textures.html",
                    target_id="tex_123"
                )
            ],
            affected_resources=["tex_123", "tex_456"],
            affected_events=[100, 200],
            impact_score=75.0,
            verification_plan="检查纹理是否被正确压缩"
        )
        
        result = chain.to_dict()
        
        assert result["issue_code"] == "TEX-001"
        assert result["summary"] == "测试证据链"
        assert len(result["evidences"]) == 1
        assert result["evidences"][0]["label"] == "纹理大小"
        assert result["evidences"][0]["value"] == 4096
        assert result["evidences"][0]["threshold"] == 2048
        assert len(result["actions"]) == 1
        assert result["actions"][0]["type"] == "jump"
        assert result["actions"][0]["target_page"] == "textures.html"
        assert result["affected_resources"] == ["tex_123", "tex_456"]
        assert result["affected_events"] == [100, 200]
        assert result["impact_score"] == 75.0
    
    def test_performance_issue_to_canonical_preserves_evidence_chain(self):
        """PerformanceIssue.to_canonical() 正确保留 evidence_chain"""
        chain = EvidenceChain(
            issue_code="TEX-001",
            summary="超大纹理",
            evidences=[
                ContextEvidence(
                    type="metric", label="宽度", value=4096,
                    threshold=2048, unit="px", severity="warning"
                )
            ],
            actions=[
                Action(type="jump", label="查看", target_page="textures.html", target_id="tex_1")
            ],
            impact_score=80.0
        )
        
        issue = PerformanceIssue(
            rule_id="TEX-001",
            severity="warning",
            category="texture",
            title="超大纹理警告",
            message="纹理 tex_1 尺寸 4096x4096 超过推荐阈值",
            resource_id="tex_1",
            actual_value=4096,
            threshold_value=2048,
            impact_score=80.0,
            suggestion="考虑压缩或降低分辨率",
            evidence_chain=chain
        )
        
        canonical = issue.to_canonical()
        
        # 验证 evidence 包含 evidence_chain
        assert "evidence" in canonical.__dict__ or hasattr(canonical, '_asdict')
        evidence = getattr(canonical, 'evidence', {})
        
        assert "evidence_chain" in evidence
        assert evidence["evidence_chain"]["issue_code"] == "TEX-001"
        assert evidence["evidence_chain"]["summary"] == "超大纹理"
        assert len(evidence["evidence_chain"]["evidences"]) == 1
        assert len(evidence["evidence_chain"]["actions"]) == 1
    
    def test_report_bundle_generator_preserves_evidence_in_json(self, tmp_path):
        """ReportBundleGenerator 正确将 evidence 传递到 JSON"""
        generator = ReportBundleGenerator(tmp_path, "test_capture")
        
        # 模拟含有 evidence 字段的 issue 数据
        performance_data = {
            "issues": [
                {
                    "rule_id": "TEX-001",
                    "severity": "warning",
                    "category": "texture",
                    "title": "超大纹理",
                    "message": "纹理尺寸过大",
                    "suggestion": "压缩纹理",
                    "evidence": {
                        "actual": 4096,
                        "threshold": 2048,
                        "evidence_chain": {
                            "issue_code": "TEX-001",
                            "summary": "超大纹理",
                            "evidences": [
                                {"type": "metric", "label": "宽度", "value": 4096, "threshold": 2048, "unit": "px"}
                            ],
                            "actions": [
                                {"type": "jump", "label": "查看纹理", "target_page": "textures.html", "target_id": "tex_1"}
                            ],
                            "affected_resources": ["tex_1"],
                            "impact_score": 75.0
                        }
                    }
                }
            ],
            "recommendations": []
        }
        
        generator.set_performance_data(performance_data)
        
        # 生成 recommendations.html
        html = generator.generate_recommendations()
        
        # 从 HTML 中提取 JSON 数据
        import re
        match = re.search(r'<script id="recommendationsData"[^>]*>(.*?)</script>', html, re.DOTALL)
        assert match, "未找到 recommendationsData 脚本标签"
        
        json_text = match.group(1).strip()
        issues = json.loads(json_text)
        
        # 验证 evidence 字段被保留
        assert len(issues) == 1
        assert "evidence" in issues[0]
        assert "evidence_chain" in issues[0]["evidence"]
        assert issues[0]["evidence"]["evidence_chain"]["issue_code"] == "TEX-001"
        assert len(issues[0]["evidence"]["evidence_chain"]["evidences"]) == 1
        assert len(issues[0]["evidence"]["evidence_chain"]["actions"]) == 1


class TestEvidenceChainJSRendering:
    """测试前端 JS 渲染兼容性（数据格式验证）"""
    
    def test_evidence_chain_json_structure_matches_js_expectations(self):
        """验证 Python 生成的 JSON 结构符合 JS renderEvidenceChain 预期"""
        chain = EvidenceChain(
            issue_code="TEX-002",
            summary="测试摘要",
            evidences=[
                ContextEvidence(
                    type="metric",
                    label="测试标签",
                    value=100,
                    threshold=50,
                    unit="%",
                    severity="critical"
                )
            ],
            actions=[
                Action(
                    type="jump",
                    label="跳转按钮",
                    target_page="textures.html",
                    target_id="event_123"
                ),
                Action(
                    type="highlight",
                    label="高亮资源",
                    target_id="res_456"
                )
            ],
            affected_resources=["res_1", "res_2"],
            affected_events=[10, 20, 30],
            impact_score=85.5,
            verification_plan="验证步骤说明"
        )
        
        result = chain.to_dict()
        
        # JS renderEvidenceChain 预期的字段名
        # 检查 evidences 结构
        ev = result["evidences"][0]
        assert "label" in ev  # JS: ev.label
        assert "value" in ev  # JS: ev.value
        assert "threshold" in ev  # JS: ev.threshold
        assert "unit" in ev  # JS: ev.unit
        assert "severity" in ev  # JS: ev.severity
        
        # 检查 actions 结构
        action = result["actions"][0]
        assert "type" in action  # JS: action.type
        assert "label" in action  # JS: action.label
        assert "target_page" in action  # JS: action.target_page
        assert "target_id" in action  # JS: action.target_id
        
        # 检查其他字段
        assert "affected_resources" in result  # JS: chain.affected_resources
        assert "affected_events" in result  # JS: chain.affected_events
        assert "impact_score" in result  # JS: chain.impact_score
        assert "verification_plan" in result  # JS: chain.verification_plan


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

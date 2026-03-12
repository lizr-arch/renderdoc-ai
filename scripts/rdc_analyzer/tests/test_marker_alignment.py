"""
P5-03: Marker/Pass 对齐增强测试
==============================

测试 DiffEngine 的 marker 对齐策略。

Created: 2026-01-21
"""

import pytest
from ..diff.diff_engine import DiffEngine
from ..diff.diff_types import DiffStatus


class TestMarkerAlignment:
    """测试 Marker 对齐策略"""
    
    def test_align_strategy_constants(self):
        """验证对齐策略常量"""
        assert DiffEngine.ALIGN_BY_ORDER == "order"
        assert DiffEngine.ALIGN_BY_SIGNATURE == "signature"
        assert DiffEngine.ALIGN_BY_MARKER == "marker"
    
    def test_default_strategy_is_order(self):
        """默认策略是按顺序对齐"""
        engine = DiffEngine()
        assert engine.align_strategy == "order"
        assert engine.ignore_order is False
    
    def test_ignore_order_upgrades_to_signature(self):
        """ignore_order=True 自动升级到 signature 策略"""
        engine = DiffEngine(ignore_order=True)
        assert engine.align_strategy == "signature"
    
    def test_explicit_marker_strategy(self):
        """显式指定 marker 策略"""
        engine = DiffEngine(align_strategy="marker")
        assert engine.align_strategy == "marker"
    
    def test_marker_signature_matching(self):
        """测试 Marker + Shader 复合签名匹配"""
        baseline = {
            "events": [
                {
                    "eventId": 100,
                    "name": "DrawIndexed",
                    "marker_path": "Scene/Opaque/Character",
                    "indexCount": 1000,
                    "pipelineState": {
                        "shaders": {
                            "VS": {"resourceId": "vs_001"},
                            "PS": {"resourceId": "ps_001"},
                        }
                    }
                },
                {
                    "eventId": 101,
                    "name": "DrawIndexed",
                    "marker_path": "Scene/Opaque/Environment",
                    "indexCount": 2000,
                    "pipelineState": {
                        "shaders": {
                            "VS": {"resourceId": "vs_002"},
                            "PS": {"resourceId": "ps_002"},
                        }
                    }
                },
            ]
        }
        
        # Target 有 EventID 偏移，但 Marker 和 Shader 相同
        target = {
            "events": [
                {
                    "eventId": 200,  # 偏移了 100
                    "name": "DrawIndexed",
                    "marker_path": "Scene/Opaque/Character",
                    "indexCount": 1000,
                    "pipelineState": {
                        "shaders": {
                            "VS": {"resourceId": "vs_001"},
                            "PS": {"resourceId": "ps_001"},
                        }
                    }
                },
                {
                    "eventId": 201,
                    "name": "DrawIndexed",
                    "marker_path": "Scene/Opaque/Environment",
                    "indexCount": 2000,
                    "pipelineState": {
                        "shaders": {
                            "VS": {"resourceId": "vs_002"},
                            "PS": {"resourceId": "ps_002"},
                        }
                    }
                },
            ]
        }
        
        engine = DiffEngine(align_strategy="marker")
        result = engine.compare(baseline, target)
        
        # 应该没有差异（完美匹配）
        assert len(result.draw_call_diffs) == 0
    
    def test_marker_matching_with_shader_change(self):
        """Marker 相同但 Shader 变化的情况"""
        baseline = {
            "events": [
                {
                    "eventId": 100,
                    "name": "DrawIndexed",
                    "marker_path": "Scene/Opaque/Character",
                    "indexCount": 1000,
                    "pipelineState": {
                        "shaders": {
                            "VS": {"resourceId": "vs_001"},
                            "PS": {"resourceId": "ps_001"},
                        }
                    }
                },
            ]
        }
        
        target = {
            "events": [
                {
                    "eventId": 200,
                    "name": "DrawIndexed",
                    "marker_path": "Scene/Opaque/Character",
                    "indexCount": 1000,
                    "pipelineState": {
                        "shaders": {
                            "VS": {"resourceId": "vs_001"},
                            "PS": {"resourceId": "ps_002_new"},  # 变化
                        }
                    }
                },
            ]
        }
        
        engine = DiffEngine(align_strategy="marker")
        result = engine.compare(baseline, target)
        
        # 应该有 1 个 MODIFIED（通过 marker_only 匹配）
        assert len(result.draw_call_diffs) == 1
        diff = result.draw_call_diffs[0]
        assert diff.status == DiffStatus.MODIFIED
        assert diff.event_id == 200
        assert diff.matched_event_id == 100
        assert "shader_PS" in diff.changes
    
    def test_fallback_to_shader_matching(self):
        """无 Marker 时回退到 Shader 签名匹配"""
        baseline = {
            "events": [
                {
                    "eventId": 100,
                    "name": "DrawIndexed",
                    # 无 marker_path
                    "indexCount": 1000,
                    "pipelineState": {
                        "shaders": {
                            "VS": {"resourceId": "vs_001"},
                            "PS": {"resourceId": "ps_001"},
                        }
                    }
                },
            ]
        }
        
        target = {
            "events": [
                {
                    "eventId": 200,
                    "name": "DrawIndexed",
                    "indexCount": 1000,
                    "pipelineState": {
                        "shaders": {
                            "VS": {"resourceId": "vs_001"},
                            "PS": {"resourceId": "ps_001"},
                        }
                    }
                },
            ]
        }
        
        engine = DiffEngine(align_strategy="marker")
        result = engine.compare(baseline, target)
        
        # 通过 shader_fallback 匹配成功，无差异
        assert len(result.draw_call_diffs) == 0
    
    def test_added_draw_call_detection(self):
        """检测新增的 Draw Call"""
        baseline = {
            "events": [
                {
                    "eventId": 100,
                    "name": "DrawIndexed",
                    "marker_path": "Scene/Opaque",
                    "indexCount": 1000,
                    "pipelineState": {"shaders": {}}
                },
            ]
        }
        
        target = {
            "events": [
                {
                    "eventId": 100,
                    "name": "DrawIndexed",
                    "marker_path": "Scene/Opaque",
                    "indexCount": 1000,
                    "pipelineState": {"shaders": {}}
                },
                {
                    "eventId": 101,
                    "name": "DrawIndexed",
                    "marker_path": "Scene/Transparent",  # 新增
                    "indexCount": 500,
                    "pipelineState": {"shaders": {"VS": {"resourceId": "vs_new"}}}
                },
            ]
        }
        
        engine = DiffEngine(align_strategy="marker")
        result = engine.compare(baseline, target)
        
        added = [d for d in result.draw_call_diffs if d.status == DiffStatus.ADDED]
        assert len(added) == 1
        assert added[0].event_id == 101
        assert added[0].marker_path == "Scene/Transparent"
    
    def test_removed_draw_call_detection(self):
        """检测删除的 Draw Call"""
        baseline = {
            "events": [
                {
                    "eventId": 100,
                    "name": "DrawIndexed",
                    "marker_path": "Scene/Opaque",
                    "indexCount": 1000,
                    "pipelineState": {"shaders": {}}
                },
                {
                    "eventId": 101,
                    "name": "DrawIndexed",
                    "marker_path": "Scene/Legacy",
                    "indexCount": 500,
                    "pipelineState": {"shaders": {"VS": {"resourceId": "vs_old"}}}
                },
            ]
        }
        
        target = {
            "events": [
                {
                    "eventId": 100,
                    "name": "DrawIndexed",
                    "marker_path": "Scene/Opaque",
                    "indexCount": 1000,
                    "pipelineState": {"shaders": {}}
                },
            ]
        }
        
        engine = DiffEngine(align_strategy="marker")
        result = engine.compare(baseline, target)
        
        removed = [d for d in result.draw_call_diffs if d.status == DiffStatus.REMOVED]
        assert len(removed) == 1
        assert removed[0].event_id == 101
        assert removed[0].marker_path == "Scene/Legacy"
    
    def test_match_type_annotation(self):
        """验证 match_type 字段正确标注"""
        baseline = {
            "events": [
                {
                    "eventId": 100,
                    "name": "DrawIndexed",
                    "marker_path": "Pass/A",
                    "indexCount": 100,
                    "vertexCount": 50,  # 变化触发 MODIFIED
                    "pipelineState": {
                        "shaders": {
                            "VS": {"resourceId": "vs"},
                            "PS": {"resourceId": "ps"},
                        }
                    }
                },
            ]
        }
        
        target = {
            "events": [
                {
                    "eventId": 200,
                    "name": "DrawIndexed",
                    "marker_path": "Pass/A",
                    "indexCount": 100,
                    "vertexCount": 60,  # 变化
                    "pipelineState": {
                        "shaders": {
                            "VS": {"resourceId": "vs"},
                            "PS": {"resourceId": "ps"},
                        }
                    }
                },
            ]
        }
        
        engine = DiffEngine(align_strategy="marker")
        result = engine.compare(baseline, target)
        
        assert len(result.draw_call_diffs) == 1
        diff = result.draw_call_diffs[0]
        assert diff.match_type == "marker+shader"
        assert diff.marker_path == "Pass/A"
    
    def test_multiple_draws_same_marker(self):
        """同一 Marker 下有多个 Draw Call"""
        baseline = {
            "events": [
                {
                    "eventId": 100,
                    "name": "DrawIndexed",
                    "marker_path": "Scene/Batch",
                    "indexCount": 1000,
                    "pipelineState": {"shaders": {"VS": {"resourceId": "vs1"}}}
                },
                {
                    "eventId": 101,
                    "name": "DrawIndexed",
                    "marker_path": "Scene/Batch",  # 同一 Marker
                    "indexCount": 2000,
                    "pipelineState": {"shaders": {"VS": {"resourceId": "vs2"}}}
                },
                {
                    "eventId": 102,
                    "name": "DrawIndexed",
                    "marker_path": "Scene/Batch",
                    "indexCount": 3000,
                    "pipelineState": {"shaders": {"VS": {"resourceId": "vs3"}}}
                },
            ]
        }
        
        # EventID 偏移但保持顺序
        target = {
            "events": [
                {
                    "eventId": 200,
                    "name": "DrawIndexed",
                    "marker_path": "Scene/Batch",
                    "indexCount": 1000,
                    "pipelineState": {"shaders": {"VS": {"resourceId": "vs1"}}}
                },
                {
                    "eventId": 201,
                    "name": "DrawIndexed",
                    "marker_path": "Scene/Batch",
                    "indexCount": 2000,
                    "pipelineState": {"shaders": {"VS": {"resourceId": "vs2"}}}
                },
                {
                    "eventId": 202,
                    "name": "DrawIndexed",
                    "marker_path": "Scene/Batch",
                    "indexCount": 3000,
                    "pipelineState": {"shaders": {"VS": {"resourceId": "vs3"}}}
                },
            ]
        }
        
        engine = DiffEngine(align_strategy="marker")
        result = engine.compare(baseline, target)
        
        # 完美匹配，无差异
        assert len(result.draw_call_diffs) == 0


class TestOrderAlignment:
    """测试按顺序对齐策略"""
    
    def test_order_strategy_detects_all_changes(self):
        """按顺序对齐时，EventID 偏移会被检测为变化"""
        baseline = {
            "events": [
                {
                    "eventId": 100,
                    "name": "DrawIndexed",
                    "indexCount": 1000,
                    "pipelineState": {"shaders": {}}
                },
            ]
        }
        
        target = {
            "events": [
                {
                    "eventId": 200,  # 不同的 eventId
                    "name": "DrawIndexed",
                    "indexCount": 1000,
                    "pipelineState": {"shaders": {}}
                },
            ]
        }
        
        engine = DiffEngine(align_strategy="order")
        result = engine.compare(baseline, target)
        
        # 按顺序对齐时，内容相同不应报告差异
        # (因为 _diff_draw_call 不比较 eventId)
        assert len(result.draw_call_diffs) == 0


class TestSignatureAlignment:
    """测试签名对齐策略"""
    
    def test_signature_matching_ignores_event_id(self):
        """签名匹配忽略 EventID 差异"""
        baseline = {
            "events": [
                {
                    "eventId": 100,
                    "name": "DrawIndexed",
                    "indexCount": 1000,
                    "pipelineState": {
                        "shaders": {
                            "VS": {"resourceId": "vs_001"},
                            "PS": {"resourceId": "ps_001"},
                        }
                    }
                },
            ]
        }
        
        target = {
            "events": [
                {
                    "eventId": 999,  # 完全不同的 ID
                    "name": "DrawIndexed",
                    "indexCount": 1000,
                    "pipelineState": {
                        "shaders": {
                            "VS": {"resourceId": "vs_001"},
                            "PS": {"resourceId": "ps_001"},
                        }
                    }
                },
            ]
        }
        
        engine = DiffEngine(align_strategy="signature")
        result = engine.compare(baseline, target)
        
        # 签名相同，无差异
        assert len(result.draw_call_diffs) == 0

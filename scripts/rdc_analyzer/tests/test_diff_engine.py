"""
DiffEngine 单元测试
==================

TASK-010 测试用例
Created: 2026-01-20
"""

import pytest
import sys
from pathlib import Path

# 添加项目路径 (直接导入 diff 模块，避免触发顶层 rdc_analyzer.__init__.py)
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 直接从 diff 子模块导入，绕过 rdc_analyzer 的 __init__.py
from diff.diff_engine import DiffEngine
from diff.diff_types import (
    DiffResult, DiffStatus, MetricDiff, 
    TextureDiff, ShaderDiff, DrawCallDiff
)


class TestMetricDiff:
    """MetricDiff 数据结构测试"""
    
    def test_delta_calculation(self):
        """测试差值计算"""
        diff = MetricDiff("test", 100, 150)
        assert diff.delta == 50
        assert diff.is_increase
        assert not diff.is_decrease
    
    def test_delta_percent(self):
        """测试百分比计算"""
        diff = MetricDiff("test", 100, 120)
        assert diff.delta_percent == 20.0
        
        # 负增长
        diff2 = MetricDiff("test", 100, 80)
        assert diff2.delta_percent == -20.0
    
    def test_zero_baseline(self):
        """测试基准为零的情况"""
        diff = MetricDiff("test", 0, 100)
        assert diff.delta_percent == 100.0
        
        diff2 = MetricDiff("test", 0, 0)
        assert diff2.delta_percent == 0.0
    
    def test_status(self):
        """测试状态判断"""
        unchanged = MetricDiff("test", 100, 100)
        assert unchanged.status == DiffStatus.UNCHANGED
        
        modified = MetricDiff("test", 100, 150)
        assert modified.status == DiffStatus.MODIFIED


class TestDiffEngine:
    """DiffEngine 核心功能测试"""
    
    @pytest.fixture
    def engine(self):
        return DiffEngine()
    
    @pytest.fixture
    def baseline_data(self):
        """基准数据"""
        return {
            "apiType": "Vulkan",
            "events": [
                {"eventId": 1, "name": "vkCmdDrawIndexed", "indexCount": 1000, "vertexCount": 500},
                {"eventId": 2, "name": "vkCmdDrawIndexed", "indexCount": 2000, "vertexCount": 800},
            ],
            "textures": [
                {"resourceId": "tex001", "name": "Albedo", "width": 1024, "height": 1024, "format": "BC7"},
                {"resourceId": "tex002", "name": "Normal", "width": 512, "height": 512, "format": "BC5"},
            ],
            "buffers": [
                {"resourceId": "buf001", "name": "VB", "size": 10000},
            ],
            "shaders": [
                {"resourceId": "vs001", "type": "VS", "name": "MainVS", "hash": "abc123"},
                {"resourceId": "ps001", "type": "PS", "name": "MainPS", "hash": "def456"},
            ],
            "statistics": {
                "totalDrawCalls": 2,
                "totalTriangles": 1000,
            }
        }
    
    @pytest.fixture
    def target_data(self):
        """目标数据 (有变化)"""
        return {
            "apiType": "Vulkan",
            "events": [
                {"eventId": 1, "name": "vkCmdDrawIndexed", "indexCount": 1000, "vertexCount": 500},
                {"eventId": 2, "name": "vkCmdDrawIndexed", "indexCount": 3000, "vertexCount": 1200},  # 修改
                {"eventId": 3, "name": "vkCmdDrawIndexed", "indexCount": 500, "vertexCount": 200},   # 新增
            ],
            "textures": [
                {"resourceId": "tex001", "name": "Albedo", "width": 2048, "height": 2048, "format": "BC7"},  # 修改
                # tex002 删除
                {"resourceId": "tex003", "name": "Roughness", "width": 1024, "height": 1024, "format": "BC4"},  # 新增
            ],
            "buffers": [
                {"resourceId": "buf001", "name": "VB", "size": 15000},  # 修改
                {"resourceId": "buf002", "name": "IB", "size": 5000},   # 新增
            ],
            "shaders": [
                {"resourceId": "vs001", "type": "VS", "name": "MainVS", "hash": "abc123"},  # 不变
                {"resourceId": "ps001", "type": "PS", "name": "MainPS", "hash": "xyz789"},  # hash 变化
                {"resourceId": "cs001", "type": "CS", "name": "PostCS", "hash": "new001"},  # 新增
            ],
            "statistics": {
                "totalDrawCalls": 3,
                "totalTriangles": 1500,
            }
        }
    
    def test_compare_empty_data(self, engine):
        """测试空数据对比"""
        result = engine.compare({}, {})
        
        assert isinstance(result, DiffResult)
        assert not result.has_changes
    
    def test_compare_identical_data(self, engine, baseline_data):
        """测试相同数据对比"""
        result = engine.compare(baseline_data, baseline_data)
        
        # 摘要应该显示无变化
        assert result.summary.draw_calls.delta == 0
        assert result.summary.texture_count.delta == 0
        
        # 不应有纹理/Shader 差异
        assert len([t for t in result.texture_diffs if t.status != DiffStatus.UNCHANGED]) == 0
    
    def test_compare_summary(self, engine, baseline_data, target_data):
        """测试摘要对比"""
        result = engine.compare(baseline_data, target_data)
        
        # Draw Call: 2 -> 3
        assert result.summary.draw_calls.baseline == 2
        assert result.summary.draw_calls.target == 3
        assert result.summary.draw_calls.delta == 1
        
        # Texture: 2 -> 2
        assert result.summary.texture_count.baseline == 2
        assert result.summary.texture_count.target == 2
        
        # Shader: 2 -> 3
        assert result.summary.shader_count.baseline == 2
        assert result.summary.shader_count.target == 3
    
    def test_texture_diffs(self, engine, baseline_data, target_data):
        """测试纹理差异检测"""
        result = engine.compare(baseline_data, target_data)
        
        # 检查新增
        added = [t for t in result.texture_diffs if t.status == DiffStatus.ADDED]
        assert len(added) == 1
        assert added[0].resource_id == "tex003"
        
        # 检查删除
        removed = [t for t in result.texture_diffs if t.status == DiffStatus.REMOVED]
        assert len(removed) == 1
        assert removed[0].resource_id == "tex002"
        
        # 检查修改
        modified = [t for t in result.texture_diffs if t.status == DiffStatus.MODIFIED]
        assert len(modified) == 1
        assert modified[0].resource_id == "tex001"
        assert "width" in modified[0].changes
    
    def test_shader_diffs(self, engine, baseline_data, target_data):
        """测试 Shader 差异检测"""
        result = engine.compare(baseline_data, target_data)
        
        # 新增 CS
        added = [s for s in result.shader_diffs if s.status == DiffStatus.ADDED]
        assert len(added) == 1
        assert added[0].shader_type == "CS"
        
        # PS hash 变化
        modified = [s for s in result.shader_diffs if s.status == DiffStatus.MODIFIED]
        assert len(modified) == 1
        assert modified[0].resource_id == "ps001"
    
    def test_buffer_diffs(self, engine, baseline_data, target_data):
        """测试 Buffer 差异检测"""
        result = engine.compare(baseline_data, target_data)
        
        # 新增
        added = [b for b in result.buffer_diffs if b.status == DiffStatus.ADDED]
        assert len(added) == 1
        assert added[0].resource_id == "buf002"
        
        # 修改
        modified = [b for b in result.buffer_diffs if b.status == DiffStatus.MODIFIED]
        assert len(modified) == 1
        assert "size" in modified[0].changes
    
    def test_draw_call_diffs(self, engine, baseline_data, target_data):
        """测试 Draw Call 差异检测"""
        result = engine.compare(baseline_data, target_data)
        
        # 新增
        added = [d for d in result.draw_call_diffs if d.status == DiffStatus.ADDED]
        assert len(added) == 1
        assert added[0].event_id == 3
        
        # 修改
        modified = [d for d in result.draw_call_diffs if d.status == DiffStatus.MODIFIED]
        assert len(modified) == 1
        assert modified[0].event_id == 2
        assert "indexCount" in modified[0].changes
    
    def test_to_dict(self, engine, baseline_data, target_data):
        """测试 JSON 序列化"""
        result = engine.compare(baseline_data, target_data)
        
        data = result.to_dict()
        
        assert "baseline_file" in data
        assert "summary" in data
        assert "texture_diffs" in data
        assert "shader_diffs" in data
        assert "statistics" in data
    
    def test_to_json(self, engine, baseline_data, target_data):
        """测试 JSON 字符串输出"""
        result = engine.compare(baseline_data, target_data)
        
        json_str = result.to_json()
        
        assert isinstance(json_str, str)
        assert "baseline_file" in json_str
        assert "texture_diffs" in json_str


class TestDiffEngineIgnoreOrder:
    """测试 ignore_order 模式"""
    
    def test_ignore_order_matching(self):
        """测试按特征匹配"""
        baseline = {
            "events": [
                {"eventId": 1, "name": "Draw", "indexCount": 100, "pipelineState": {"shaders": {"VS": {"resourceId": "vs1"}}}},
                {"eventId": 2, "name": "Draw", "indexCount": 200, "pipelineState": {"shaders": {"VS": {"resourceId": "vs2"}}}},
            ],
            "textures": [],
            "buffers": [],
            "shaders": [],
        }
        
        # 顺序颠倒
        target = {
            "events": [
                {"eventId": 1, "name": "Draw", "indexCount": 200, "pipelineState": {"shaders": {"VS": {"resourceId": "vs2"}}}},
                {"eventId": 2, "name": "Draw", "indexCount": 100, "pipelineState": {"shaders": {"VS": {"resourceId": "vs1"}}}},
            ],
            "textures": [],
            "buffers": [],
            "shaders": [],
        }
        
        # ignore_order=True 应该匹配成功，不报新增/删除
        engine = DiffEngine(ignore_order=True)
        result = engine.compare(baseline, target)
        
        added = [d for d in result.draw_call_diffs if d.status == DiffStatus.ADDED]
        removed = [d for d in result.draw_call_diffs if d.status == DiffStatus.REMOVED]
        
        assert len(added) == 0
        assert len(removed) == 0


class TestDiffResultProperties:
    """测试 DiffResult 统计属性"""
    
    def test_statistics_properties(self):
        """测试统计属性计算"""
        result = DiffResult()
        
        # 使用顶层导入的类，而非再次导入
        result.texture_diffs = [
            TextureDiff("t1", "T1", DiffStatus.ADDED),
            TextureDiff("t2", "T2", DiffStatus.ADDED),
            TextureDiff("t3", "T3", DiffStatus.REMOVED),
            TextureDiff("t4", "T4", DiffStatus.MODIFIED),
        ]
        
        assert result.textures_added == 2
        assert result.textures_removed == 1
        assert result.textures_modified == 1
        
        result.shader_diffs = [
            ShaderDiff("s1", "S1", DiffStatus.ADDED),
        ]
        assert result.shaders_added == 1
        assert result.shaders_removed == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
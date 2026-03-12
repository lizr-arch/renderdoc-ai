"""
Unit tests for heatmap_builder.py (M4.1 - v2.0 重构版)

测试热力图构建器的核心功能（使用模式分析）：
    - 使用模式检测（FIRST_USE, CONTINUOUS, SPARSE, ISOLATED）
    - 连续条目合并
    - 连续性评分计算

设计理念变更说明（v1.0 → v2.0）:
    - 旧版: 检测"冗余绑定"（REDUNDANT）
    - 新版: 分析"使用模式"（连续使用=缓存友好，稀疏使用=可优化）
    - 驱动自动处理重复绑定，我们关注的是 Draw Call 排序优化
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from core.types import (
    ResourceUsageIndex,
    UsageRecord,
    UsagePattern,  # v2.0: 新的使用模式枚举
    BindingHeatmapEntry,
    BindingHeatmapData,
)
from core.heatmap_builder import (
    HeatmapBuilder,
    build_heatmap_collection,
    compute_binding_heatmap,
)


class TestHeatmapBuilder:
    """热力图构建器测试（v2.0 使用模式分析）"""
    
    def test_isolated_usage_detection(self):
        """测试孤立使用检测（仅使用一次）"""
        # 创建测试数据：资源仅使用一次
        index = ResourceUsageIndex()
        index.add_texture_usage(
            "tex_001",
            UsageRecord(event_id=10, binding_type="SRV", slot=0)
        )
        
        builder = HeatmapBuilder(index)
        heatmap = builder.build_for_resource("tex_001")
        
        assert heatmap is not None
        assert len(heatmap.entries) == 1
        # 仅使用一次应该标记为 ISOLATED
        assert heatmap.entries[0].status == UsagePattern.ISOLATED
    
    def test_first_use_detection(self):
        """测试首次使用检测（多次使用时的第一次）"""
        index = ResourceUsageIndex()
        # 多次使用：第一次应该是 FIRST_USE
        index.add_texture_usage("tex_001", UsageRecord(event_id=10, binding_type="SRV", slot=0))
        index.add_texture_usage("tex_001", UsageRecord(event_id=11, binding_type="SRV", slot=0))
        
        builder = HeatmapBuilder(index, event_ids=[10, 11])
        heatmap = builder.build_for_resource("tex_001")
        
        assert heatmap is not None
        assert len(heatmap.entries) == 2
        assert heatmap.entries[0].status == UsagePattern.FIRST_USE
    
    def test_continuous_usage_detection(self):
        """测试连续使用检测（相邻 Draw Call）"""
        index = ResourceUsageIndex()
        # 连续3个事件使用同一资源
        index.add_texture_usage("tex_001", UsageRecord(event_id=10, binding_type="SRV", slot=0))
        index.add_texture_usage("tex_001", UsageRecord(event_id=11, binding_type="SRV", slot=0))
        index.add_texture_usage("tex_001", UsageRecord(event_id=12, binding_type="SRV", slot=0))
        
        builder = HeatmapBuilder(index, event_ids=[10, 11, 12])
        heatmap = builder.build_for_resource("tex_001")
        
        assert heatmap is not None
        # 合并后：FIRST_USE@10, CONTINUOUS@11-12
        assert len(heatmap.entries) >= 1
        
        # 检查是否有连续使用标记
        has_continuous = any(e.status == UsagePattern.CONTINUOUS for e in heatmap.entries)
        assert has_continuous, "应检测到连续使用（缓存友好）"
    
    def test_sparse_usage_after_gap(self):
        """测试稀疏使用检测
        
        当 event_ids 列表提供时，连续性基于列表索引判断。
        资源在事件 10 使用，然后跳过 20, 30, 40，在事件 50 再次使用。
        """
        index = ResourceUsageIndex()
        index.add_texture_usage("tex_001", UsageRecord(event_id=10, binding_type="SRV", slot=0))
        index.add_texture_usage("tex_001", UsageRecord(event_id=50, binding_type="SRV", slot=0))
        
        # 提供完整的事件列表，包含中间的事件
        builder = HeatmapBuilder(index, event_ids=[10, 20, 30, 40, 50])
        heatmap = builder.build_for_resource("tex_001")
        
        assert heatmap is not None
        assert len(heatmap.entries) == 2
        assert heatmap.entries[0].status == UsagePattern.FIRST_USE
        # 索引 0 (事件10) 和 索引 4 (事件50) 差值 > 1，不连续，所以是 SPARSE
        assert heatmap.entries[1].status == UsagePattern.SPARSE
    
    def test_continuity_score_calculation(self):
        """测试连续性评分计算
        
        5个事件：1 first + 4 continuous = 100% 连续性
        """
        index = ResourceUsageIndex()
        for i in range(5):
            index.add_texture_usage(
                "tex_001",
                UsageRecord(event_id=10 + i, binding_type="SRV", slot=0)
            )
        
        builder = HeatmapBuilder(index, event_ids=list(range(10, 15)))
        heatmap = builder.build_for_resource("tex_001")
        
        assert heatmap is not None
        # 全部连续使用，连续性评分应该接近 100%
        assert heatmap.efficiency_score >= 90.0
    
    def test_low_continuity_score(self):
        """测试低连续性评分（稀疏使用）"""
        index = ResourceUsageIndex()
        # 在 100 个事件中，仅在 10, 50, 90 使用（间隔大）
        index.add_texture_usage("tex_001", UsageRecord(event_id=10, binding_type="SRV", slot=0))
        index.add_texture_usage("tex_001", UsageRecord(event_id=50, binding_type="SRV", slot=0))
        index.add_texture_usage("tex_001", UsageRecord(event_id=90, binding_type="SRV", slot=0))
        
        # 完整事件列表
        event_ids = list(range(10, 100))
        builder = HeatmapBuilder(index, event_ids=event_ids)
        heatmap = builder.build_for_resource("tex_001")
        
        assert heatmap is not None
        # 稀疏使用，连续性评分应该是 0%
        assert heatmap.efficiency_score == 0.0
    
    def test_build_all_resources(self):
        """测试构建所有资源的热力图"""
        index = ResourceUsageIndex()
        
        # 添加多种资源
        index.add_texture_usage("tex_001", UsageRecord(event_id=10, binding_type="SRV", slot=0))
        index.add_shader_usage("shader_001", UsageRecord(event_id=10, binding_type="VS", slot=0))
        index.add_buffer_usage("buf_001", UsageRecord(event_id=10, binding_type="VB", slot=0))
        
        builder = HeatmapBuilder(index)
        collection = builder.build_all()
        
        # HeatmapCollection 使用统一的 heatmaps 字典
        assert len(collection.heatmaps) == 3
        assert "tex_001" in collection.heatmaps
        assert "shader_001" in collection.heatmaps
        assert "buf_001" in collection.heatmaps
    
    def test_convenience_functions(self):
        """测试便捷函数"""
        # 测试 build_heatmap_collection
        index = ResourceUsageIndex()
        index.add_texture_usage("tex_001", UsageRecord(event_id=10, binding_type="SRV", slot=0))
        
        collection = build_heatmap_collection(index)
        assert len(collection.heatmaps) == 1
        
        # 测试 compute_binding_heatmap
        usages = [
            UsageRecord(event_id=10, binding_type="SRV", slot=0),
            UsageRecord(event_id=20, binding_type="SRV", slot=0),
        ]
        heatmap = compute_binding_heatmap("tex_002", usages)
        assert heatmap is not None
        assert heatmap.resource_id == "tex_002"
    
    def test_entry_merging(self):
        """测试连续条目合并"""
        index = ResourceUsageIndex()
        # 10个连续使用
        for i in range(10):
            index.add_texture_usage(
                "tex_001",
                UsageRecord(event_id=100 + i, binding_type="SRV", slot=0)
            )
        
        builder = HeatmapBuilder(index, event_ids=list(range(100, 110)))
        heatmap = builder.build_for_resource("tex_001")
        
        assert heatmap is not None
        # 合并后应该只有 2 个条目：FIRST_USE@100, CONTINUOUS@101-109
        assert len(heatmap.entries) == 2
        
        # 检查跨度
        continuous_entry = heatmap.entries[1]
        assert continuous_entry.event_start == 101
        assert continuous_entry.event_end == 109
        assert continuous_entry.status == UsagePattern.CONTINUOUS
    
    def test_different_slots_continuous(self):
        """测试不同槽位也被视为连续使用
        
        v2.0 设计变更：我们关注的是资源本身的使用时序，
        不再区分槽位。只要同一资源在相邻 Draw Call 中使用，
        就是连续使用。
        """
        index = ResourceUsageIndex()
        # 同一资源绑定到不同槽位 - 在 v2.0 中应该是连续使用
        index.add_texture_usage("tex_001", UsageRecord(event_id=10, binding_type="SRV", slot=0))
        index.add_texture_usage("tex_001", UsageRecord(event_id=11, binding_type="SRV", slot=1))
        index.add_texture_usage("tex_001", UsageRecord(event_id=12, binding_type="SRV", slot=2))
        
        builder = HeatmapBuilder(index, event_ids=[10, 11, 12])
        heatmap = builder.build_for_resource("tex_001")
        
        assert heatmap is not None
        # 连续 3 个事件使用同一资源，应该有连续使用标记
        continuous_count = sum(1 for e in heatmap.entries if e.status == UsagePattern.CONTINUOUS)
        assert continuous_count > 0, "不同槽位的相邻使用应该是连续使用"


class TestBindingHeatmapDataSerialization:
    """测试热力图数据序列化"""
    
    def test_to_dict(self):
        """测试 to_dict 方法"""
        entry = BindingHeatmapEntry(
            event_start=10,
            event_end=20,
            status=UsagePattern.CONTINUOUS,
            binding_type="SRV",
            slot=0,
        )
        
        data = BindingHeatmapData(
            resource_id="tex_001",
            entries=[entry],
            efficiency_score=100.0,
        )
        
        result = data.to_dict()
        
        assert result["resource_id"] == "tex_001"
        assert result["efficiency_score"] == 100.0
        assert len(result["entries"]) == 1
        # to_dict maps status to 'pattern' with uppercase value
        assert result["entries"][0]["pattern"] == "CONTINUOUS"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
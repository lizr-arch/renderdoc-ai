"""
Unit tests for heatmap_builder.py (M4.1)

测试热力图构建器的核心功能：
    - 绑定状态检测（FIRST_BIND, NORMAL, REDUNDANT）
    - 连续条目合并
    - 效率评分计算
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from core.types import (
    ResourceUsageIndex,
    UsageRecord,
    BindingStatus,
    BindingHeatmapEntry,
    BindingHeatmapData,
)
from core.heatmap_builder import (
    HeatmapBuilder,
    build_heatmap_collection,
    compute_binding_heatmap,
)


class TestHeatmapBuilder:
    """热力图构建器测试"""
    
    def test_first_bind_detection(self):
        """测试首次绑定检测"""
        # 创建测试数据
        index = ResourceUsageIndex()
        index.add_texture_usage(
            "tex_001",
            UsageRecord(event_id=10, binding_type="SRV", slot=0)
        )
        
        builder = HeatmapBuilder(index)
        heatmap = builder.build_for_resource("tex_001")
        
        assert heatmap is not None
        assert len(heatmap.entries) == 1
        assert heatmap.entries[0].status == BindingStatus.FIRST_BIND
    
    def test_redundant_binding_detection(self):
        """测试冗余绑定检测"""
        index = ResourceUsageIndex()
        # 连续3个事件绑定同一资源到同一槽位
        index.add_texture_usage("tex_001", UsageRecord(event_id=10, binding_type="SRV", slot=0))
        index.add_texture_usage("tex_001", UsageRecord(event_id=11, binding_type="SRV", slot=0))
        index.add_texture_usage("tex_001", UsageRecord(event_id=12, binding_type="SRV", slot=0))
        
        builder = HeatmapBuilder(index, event_ids=[10, 11, 12])
        heatmap = builder.build_for_resource("tex_001")
        
        assert heatmap is not None
        # 由于合并，应该只有1个条目（FIRST_BIND 后跟 REDUNDANT 会合并）
        # 实际上：第一个是 FIRST_BIND，后两个是 REDUNDANT
        # 合并后：FIRST_BIND@10, REDUNDANT@11-12
        assert len(heatmap.entries) >= 1
        
        # 检查是否有冗余标记
        has_redundant = any(e.status == BindingStatus.REDUNDANT for e in heatmap.entries)
        assert has_redundant, "应检测到冗余绑定"
    
    def test_normal_binding_after_gap(self):
        """测试间隔后的正常绑定
        
        当 event_ids 列表提供时，连续性基于列表索引判断。
        [10, 100] 中 100 紧跟 10（索引差 = 1），被视为连续。
        
        要测试 "非连续" 场景，需要在中间有其他事件（该资源未使用）。
        """
        index = ResourceUsageIndex()
        # 使用中间有间隙的事件序列
        # 资源在事件 10 使用，然后跳过 20, 30, 40，在事件 50 再次使用
        index.add_texture_usage("tex_001", UsageRecord(event_id=10, binding_type="SRV", slot=0))
        index.add_texture_usage("tex_001", UsageRecord(event_id=50, binding_type="SRV", slot=0))
        
        # 提供完整的事件列表，包含中间的事件
        builder = HeatmapBuilder(index, event_ids=[10, 20, 30, 40, 50])
        heatmap = builder.build_for_resource("tex_001")
        
        assert heatmap is not None
        assert len(heatmap.entries) == 2
        assert heatmap.entries[0].status == BindingStatus.FIRST_BIND
        # 索引 0 (事件10) 和 索引 4 (事件50) 差值 > 1，不连续，所以是 NORMAL
        assert heatmap.entries[1].status == BindingStatus.NORMAL
    
    def test_efficiency_score_calculation(self):
        """测试效率评分计算"""
        index = ResourceUsageIndex()
        # 5个事件：1 first + 4 redundant
        for i in range(5):
            index.add_texture_usage(
                "tex_001",
                UsageRecord(event_id=10 + i, binding_type="SRV", slot=0)
            )
        
        builder = HeatmapBuilder(index, event_ids=list(range(10, 15)))
        heatmap = builder.build_for_resource("tex_001")
        
        assert heatmap is not None
        # 效率应该很低（80% 是冗余）
        assert heatmap.efficiency_score < 50.0
    
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
        # 10个连续冗余绑定
        for i in range(10):
            index.add_texture_usage(
                "tex_001",
                UsageRecord(event_id=100 + i, binding_type="SRV", slot=0)
            )
        
        builder = HeatmapBuilder(index, event_ids=list(range(100, 110)))
        heatmap = builder.build_for_resource("tex_001")
        
        assert heatmap is not None
        # 合并后应该只有 2 个条目：FIRST_BIND@100, REDUNDANT@101-109
        assert len(heatmap.entries) == 2
        
        # 检查跨度
        redundant_entry = heatmap.entries[1]
        assert redundant_entry.event_start == 101
        assert redundant_entry.event_end == 109
    
    def test_different_slots_not_redundant(self):
        """测试不同槽位不被判定为冗余"""
        index = ResourceUsageIndex()
        # 同一资源绑定到不同槽位 - 不应该是冗余
        index.add_texture_usage("tex_001", UsageRecord(event_id=10, binding_type="SRV", slot=0))
        index.add_texture_usage("tex_001", UsageRecord(event_id=11, binding_type="SRV", slot=1))
        index.add_texture_usage("tex_001", UsageRecord(event_id=12, binding_type="SRV", slot=2))
        
        builder = HeatmapBuilder(index, event_ids=[10, 11, 12])
        heatmap = builder.build_for_resource("tex_001")
        
        assert heatmap is not None
        # 不同槽位，不应该有冗余
        redundant_count = sum(1 for e in heatmap.entries if e.status == BindingStatus.REDUNDANT)
        assert redundant_count == 0, "不同槽位的绑定不应该被判定为冗余"


class TestBindingHeatmapDataSerialization:
    """测试热力图数据序列化"""
    
    def test_to_dict(self):
        """测试 to_dict 方法"""
        entry = BindingHeatmapEntry(
            event_start=10,
            event_end=20,
            status=BindingStatus.REDUNDANT,
            binding_type="SRV",
            slot=0,
        )
        
        data = BindingHeatmapData(
            resource_id="tex_001",
            entries=[entry],
            efficiency_score=50.0,
        )
        
        result = data.to_dict()
        
        assert result["resource_id"] == "tex_001"
        assert result["efficiency_score"] == 50.0
        assert len(result["entries"]) == 1
        assert result["entries"][0]["status"] == BindingStatus.REDUNDANT


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

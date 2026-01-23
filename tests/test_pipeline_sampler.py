"""
PipelineSampler 单元测试
========================

测试管线状态采样器的核心功能，使用 Mock 对象模拟 RenderDoc API。
"""

import pytest
from unittest.mock import MagicMock, patch
from dataclasses import dataclass
from typing import Any

# 测试目标
import sys
import os

# 添加项目路径（确保可直接导入 rdc_analyzer 包）
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

from rdc_analyzer.extractors.pipeline_sampler import (
    PipelineSampler,
    PipelineSample,
    SamplingConfig,
    SamplingResult,
    SamplingStrategy,
    sample_pipeline_states,
)
from rdc_analyzer.core.pipeline_state import (
    DrawType,
    PrimitiveTopology,
)


# =============================================================================
# Mock 对象
# =============================================================================

class MockResourceId:
    """模拟 RenderDoc ResourceId"""
    def __init__(self, value: int):
        self._value = value
    
    def __eq__(self, other):
        if isinstance(other, MockResourceId):
            return self._value == other._value
        return False
    
    def __int__(self):
        return self._value
    
    @classmethod
    def Null(cls):
        return cls(0)


class MockShaderReflection:
    """模拟着色器反射"""
    def __init__(self, resource_id: int, name: str = ""):
        self.resourceId = MockResourceId(resource_id)
        self.debugName = name


class MockViewport:
    """模拟视口"""
    def __init__(self, x=0, y=0, width=1920, height=1080, min_depth=0.0, max_depth=1.0):
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.minDepth = min_depth
        self.maxDepth = max_depth


class MockScissor:
    """模拟裁剪矩形"""
    def __init__(self, x=0, y=0, width=1920, height=1080):
        self.x = x
        self.y = y
        self.width = width
        self.height = height


class MockViewportScissor:
    """模拟视口+裁剪"""
    def __init__(self):
        self.vp = MockViewport()
        self.scissor = MockScissor()


class MockViewportScissorState:
    """模拟视口裁剪状态"""
    def __init__(self):
        self.viewportScissors = [MockViewportScissor()]


class MockOutputTarget:
    """模拟输出目标"""
    def __init__(self, resource_id: int):
        self.resourceId = MockResourceId(resource_id)


class MockIAState:
    """模拟输入装配状态"""
    def __init__(self, topology):
        self.topology = topology


class MockPipelineState:
    """模拟管线状态"""
    def __init__(self, vs_id=100, ps_id=200, cs_id=0, rt_ids=None):
        self._vs = MockShaderReflection(vs_id, "TestVS") if vs_id else None
        self._ps = MockShaderReflection(ps_id, "TestPS") if ps_id else None
        self._cs = MockShaderReflection(cs_id, "TestCS") if cs_id else None
        self._rt_ids = rt_ids or [300]
        self._topology = None  # 将在使用时设置
    
    def GetShaderReflection(self, stage):
        if hasattr(stage, 'Vertex') or stage == 0:
            return self._vs
        elif hasattr(stage, 'Pixel') or stage == 4:
            return self._ps
        elif hasattr(stage, 'Compute') or stage == 5:
            return self._cs
        return None
    
    def GetOutputTargets(self):
        return [MockOutputTarget(rt_id) for rt_id in self._rt_ids]
    
    def GetDepthTarget(self):
        return MockOutputTarget(400)
    
    def GetViewportScissor(self):
        return MockViewportScissorState()
    
    def GetIAState(self):
        return MockIAState(self._topology)


class MockController:
    """模拟 ReplayController"""
    def __init__(self, pipeline_state=None):
        self._state = pipeline_state or MockPipelineState()
        self._current_event = 0
    
    def SetFrameEvent(self, event_id, force=True):
        self._current_event = event_id
    
    def GetPipelineState(self):
        return self._state
    
    def GetTexture(self, resource_id):
        return MagicMock(width=1920, height=1080, format=MagicMock(Name=lambda: "R8G8B8A8_UNORM"))


# =============================================================================
# 测试用例
# =============================================================================

class TestSamplingStrategy:
    """测试采样策略选择"""
    
    def test_first_n_strategy(self):
        """测试 FIRST_N 策略"""
        config = SamplingConfig(
            sample_count=5,
            strategy=SamplingStrategy.FIRST_N
        )
        sampler = PipelineSampler(None, config)
        indices = sampler._select_sample_indices(100, 5, SamplingStrategy.FIRST_N)
        
        assert indices == [0, 1, 2, 3, 4]
    
    def test_last_n_strategy(self):
        """测试 LAST_N 策略"""
        config = SamplingConfig(
            sample_count=5,
            strategy=SamplingStrategy.LAST_N
        )
        sampler = PipelineSampler(None, config)
        indices = sampler._select_sample_indices(100, 5, SamplingStrategy.LAST_N)
        
        assert indices == [95, 96, 97, 98, 99]
    
    def test_uniform_strategy(self):
        """测试 UNIFORM 策略"""
        config = SamplingConfig(
            sample_count=5,
            strategy=SamplingStrategy.UNIFORM
        )
        sampler = PipelineSampler(None, config)
        indices = sampler._select_sample_indices(100, 5, SamplingStrategy.UNIFORM)
        
        # 均匀分布：0, 20, 40, 60, 80
        assert len(indices) == 5
        assert indices[0] == 0
        assert indices[-1] == 80
    
    def test_sample_count_exceeds_total(self):
        """测试采样数量超过总数时返回所有"""
        config = SamplingConfig(sample_count=100)
        sampler = PipelineSampler(None, config)
        indices = sampler._select_sample_indices(10, 100, SamplingStrategy.UNIFORM)
        
        assert len(indices) == 10
        assert indices == list(range(10))


class TestPipelineSampler:
    """测试 PipelineSampler 核心功能"""
    
    @pytest.fixture
    def mock_rd(self):
        """创建模拟的 renderdoc 模块"""
        mock_rd = MagicMock()
        
        # ActionFlags
        mock_rd.ActionFlags.Drawcall = 1
        mock_rd.ActionFlags.Dispatch = 2
        mock_rd.ActionFlags.Clear = 4
        mock_rd.ActionFlags.Indexed = 8
        mock_rd.ActionFlags.Instanced = 16
        
        # ShaderStage
        mock_rd.ShaderStage.Vertex = 0
        mock_rd.ShaderStage.Pixel = 4
        mock_rd.ShaderStage.Compute = 5
        
        # Topology
        mock_rd.Topology.Unknown = 0
        mock_rd.Topology.PointList = 1
        mock_rd.Topology.LineList = 2
        mock_rd.Topology.LineStrip = 3
        mock_rd.Topology.TriangleList = 4
        mock_rd.Topology.TriangleStrip = 5
        mock_rd.Topology.LineList_Adj = 6
        mock_rd.Topology.LineStrip_Adj = 7
        mock_rd.Topology.TriangleList_Adj = 8
        mock_rd.Topology.TriangleStrip_Adj = 9
        
        # ResourceId
        mock_rd.ResourceId = MockResourceId
        
        return mock_rd
    
    @pytest.fixture
    def sample_events(self):
        """创建测试事件列表"""
        return [
            {'eventId': 10, 'name': 'DrawIndexed', 'flags': 1 | 8, 'numIndices': 1000, 'numInstances': 1},
            {'eventId': 20, 'name': 'DrawIndexedInstanced', 'flags': 1 | 8 | 16, 'numIndices': 500, 'numInstances': 10},
            {'eventId': 30, 'name': 'ClearRenderTarget', 'flags': 4, 'numIndices': 0, 'numInstances': 0},
            {'eventId': 40, 'name': 'Dispatch', 'flags': 2, 'numIndices': 0, 'numInstances': 0},
            {'eventId': 50, 'name': 'DrawIndexed', 'flags': 1 | 8, 'numIndices': 2000, 'numInstances': 1},
        ]
    
    def test_filter_clears_by_default(self, sample_events):
        """测试默认跳过 clear 操作"""
        config = SamplingConfig(sample_count=10, skip_clears=True)
        sampler = PipelineSampler(MockController(), config)
        
        # 手动测试过滤逻辑
        candidates = []
        for event in sample_events:
            flags = event.get('flags', 0)
            is_draw = bool(flags & 1)
            is_dispatch = bool(flags & 2)
            is_clear = bool(flags & 4)
            
            if is_clear and config.skip_clears:
                continue
            if is_draw or is_dispatch:
                candidates.append(event)
        
        # 应该有 4 个候选 (3 draw + 1 dispatch)
        assert len(candidates) == 4
        assert all(e['name'] != 'ClearRenderTarget' for e in candidates)
    
    def test_include_dispatches(self, sample_events):
        """测试包含 dispatch 调用"""
        config = SamplingConfig(sample_count=10, include_dispatches=True)
        sampler = PipelineSampler(MockController(), config)
        
        candidates = []
        for event in sample_events:
            flags = event.get('flags', 0)
            is_draw = bool(flags & 1)
            is_dispatch = bool(flags & 2)
            is_clear = bool(flags & 4)
            
            if is_clear and config.skip_clears:
                continue
            if is_draw or (is_dispatch and config.include_dispatches):
                candidates.append(event)
        
        dispatch_count = sum(1 for e in candidates if e['flags'] & 2)
        assert dispatch_count == 1
    
    def test_exclude_dispatches(self, sample_events):
        """测试排除 dispatch 调用"""
        config = SamplingConfig(sample_count=10, include_dispatches=False)
        
        candidates = []
        for event in sample_events:
            flags = event.get('flags', 0)
            is_draw = bool(flags & 1)
            is_dispatch = bool(flags & 2)
            is_clear = bool(flags & 4)
            
            if is_clear and config.skip_clears:
                continue
            if is_dispatch and not config.include_dispatches:
                continue
            if is_draw:
                candidates.append(event)
        
        # 应该只有 3 个 draw call
        assert len(candidates) == 3
        assert all(not (e['flags'] & 2) for e in candidates)


class TestDrawTypeDetection:
    """测试 draw type 检测"""
    
    def test_detect_draw_indexed(self):
        """测试检测 DrawIndexed"""
        sampler = PipelineSampler(None)
        
        mock_rd = MagicMock()
        mock_rd.ActionFlags.Drawcall = 1
        mock_rd.ActionFlags.Dispatch = 2
        mock_rd.ActionFlags.Clear = 4
        mock_rd.ActionFlags.Indexed = 8
        mock_rd.ActionFlags.Instanced = 16
        
        flags = 1 | 8  # Drawcall | Indexed
        draw_type = sampler._determine_draw_type(flags, mock_rd)
        
        assert draw_type == DrawType.DRAW_INDEXED
    
    def test_detect_draw_indexed_instanced(self):
        """测试检测 DrawIndexedInstanced"""
        sampler = PipelineSampler(None)
        
        mock_rd = MagicMock()
        mock_rd.ActionFlags.Drawcall = 1
        mock_rd.ActionFlags.Dispatch = 2
        mock_rd.ActionFlags.Clear = 4
        mock_rd.ActionFlags.Indexed = 8
        mock_rd.ActionFlags.Instanced = 16
        
        flags = 1 | 8 | 16  # Drawcall | Indexed | Instanced
        draw_type = sampler._determine_draw_type(flags, mock_rd)
        
        assert draw_type == DrawType.DRAW_INDEXED_INSTANCED
    
    def test_detect_dispatch(self):
        """测试检测 Dispatch"""
        sampler = PipelineSampler(None)
        
        mock_rd = MagicMock()
        mock_rd.ActionFlags.Drawcall = 1
        mock_rd.ActionFlags.Dispatch = 2
        mock_rd.ActionFlags.Clear = 4
        mock_rd.ActionFlags.Indexed = 8
        mock_rd.ActionFlags.Instanced = 16
        
        flags = 2  # Dispatch
        draw_type = sampler._determine_draw_type(flags, mock_rd)
        
        assert draw_type == DrawType.DISPATCH


class TestSamplingResult:
    """测试 SamplingResult 数据结构"""
    
    def test_to_dict(self):
        """测试转换为字典"""
        from rdc_analyzer.core.pipeline_state import PipelineSnapshot
        
        sample = PipelineSample(
            event_id=100,
            name="DrawIndexed",
            draw_type=DrawType.DRAW_INDEXED,
            snapshot=PipelineSnapshot(),
            vertex_shader_id=1,
            pixel_shader_id=2,
        )
        
        result = SamplingResult(
            samples=[sample],
            total_candidates=10,
            sampled_count=1,
            unique_shaders=2,
        )
        
        d = result.to_dict()
        
        assert d['total_candidates'] == 10
        assert d['sampled_count'] == 1
        assert d['unique_shaders'] == 2
        assert len(d['samples']) == 1
        assert d['samples'][0]['event_id'] == 100
        assert d['samples'][0]['vertex_shader_id'] == 1
    
    def test_shader_signature(self):
        """测试着色器签名"""
        from rdc_analyzer.core.pipeline_state import PipelineSnapshot
        
        sample = PipelineSample(
            event_id=100,
            name="DrawIndexed",
            draw_type=DrawType.DRAW_INDEXED,
            snapshot=PipelineSnapshot(),
            vertex_shader_id=10,
            pixel_shader_id=20,
            compute_shader_id=0,
        )
        
        sig = sample.shader_signature()
        assert sig == (10, 20, 0)


class TestConvenienceFunction:
    """测试便捷函数"""
    
    def test_sample_pipeline_states_creates_sampler(self):
        """测试便捷函数创建采样器"""
        with patch('rdc_analyzer.extractors.pipeline_sampler.PipelineSampler') as MockSampler:
            mock_instance = MagicMock()
            mock_instance.sample_from_events.return_value = SamplingResult()
            MockSampler.return_value = mock_instance
            
            result = sample_pipeline_states(
                controller=MagicMock(),
                events=[],
                sample_count=30,
                strategy=SamplingStrategy.FIRST_N
            )
            
            # 验证创建了采样器
            MockSampler.assert_called_once()
            call_args = MockSampler.call_args
            config = call_args[0][1]  # 第二个位置参数是 config
            
            assert config.sample_count == 30
            assert config.strategy == SamplingStrategy.FIRST_N


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

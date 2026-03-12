"""
HotspotAnalyzer 单元测试
========================

测试复杂度评分模型和热点分析逻辑。
"""

import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import unittest
from dataclasses import dataclass
from typing import List

from rdc_analyzer.core.hotspot_analyzer import (
    HotspotAnalyzer,
    HotspotLevel,
    DrawComplexityScore,
    HotspotReport,
    analyze_hotspots,
)


@dataclass
class MockDrawCall:
    """模拟 DrawCallInfo"""
    event_id: int
    name: str = "DrawIndexed"
    vertex_count: int = 0
    index_count: int = 0
    instance_count: int = 1
    rt_ids: List[str] = None
    vs_id: str = ""
    ps_id: str = ""
    pass_index: int = 0
    blend_enabled: bool = False
    depth_test: bool = True
    fill_mode: str = "solid"
    
    def __post_init__(self):
        if self.rt_ids is None:
            self.rt_ids = ["rt0"]


class TestDrawComplexityScore(unittest.TestCase):
    """测试 DrawComplexityScore 计算"""
    
    def test_basic_calculation(self):
        """测试基础分数计算"""
        score = DrawComplexityScore(
            event_id=1,
            primitive_count=1000,
            instance_count=1,
            rt_count=1,
            shader_weight=1.0,
            state_weight=1.0,
        )
        result = score.calculate()
        
        self.assertEqual(score.base_score, 1000)
        self.assertEqual(score.weighted_score, 1000)
        self.assertEqual(result, 1000)
    
    def test_instanced_draw(self):
        """测试实例化绘制"""
        score = DrawComplexityScore(
            event_id=2,
            primitive_count=100,
            instance_count=50,
        )
        score.calculate()
        
        self.assertEqual(score.base_score, 5000)  # 100 * 50
    
    def test_mrt_multiplier(self):
        """测试 MRT 乘数"""
        score = DrawComplexityScore(
            event_id=3,
            primitive_count=1000,
            instance_count=1,
            rt_count=4,
        )
        score.calculate()
        
        self.assertEqual(score.weighted_score, 4000)  # 1000 * 4
    
    def test_shader_weight(self):
        """测试 Shader 权重"""
        score = DrawComplexityScore(
            event_id=4,
            primitive_count=1000,
            shader_weight=2.0,
        )
        score.calculate()
        
        self.assertEqual(score.weighted_score, 2000)
    
    def test_vertex_fallback(self):
        """测试从顶点数推断三角形数"""
        score = DrawComplexityScore(
            event_id=5,
            primitive_count=0,  # 无三角形数
            vertex_count=300,   # 100 triangles
        )
        score.calculate()
        
        self.assertEqual(score.base_score, 100)


class TestHotspotAnalyzer(unittest.TestCase):
    """测试 HotspotAnalyzer"""
    
    def test_add_draw_dataclass(self):
        """测试添加 dataclass 格式的 draw"""
        analyzer = HotspotAnalyzer()
        draw = MockDrawCall(
            event_id=1,
            index_count=3000,  # 1000 triangles
            instance_count=10,
        )
        
        score = analyzer.add_draw(draw)
        
        self.assertEqual(score.event_id, 1)
        self.assertEqual(score.primitive_count, 1000)
        self.assertEqual(score.instance_count, 10)
        self.assertEqual(score.base_score, 10000)
    
    def test_add_draw_dict(self):
        """测试添加 dict 格式的 draw"""
        analyzer = HotspotAnalyzer()
        draw = {
            "eid": 2,
            "name": "DrawIndexed",
            "numIndices": 6000,
            "numInstances": 5,
            "outputs": ["rt0", "rt1"],
        }
        
        score = analyzer.add_draw(draw)
        
        self.assertEqual(score.event_id, 2)
        self.assertEqual(score.primitive_count, 2000)
        self.assertEqual(score.rt_count, 2)
    
    def test_shader_weight_estimation(self):
        """测试 Shader 权重估算"""
        shader_db = {
            "vs_complex": {"instruction_count": 500},
        }
        analyzer = HotspotAnalyzer(shader_db=shader_db)
        
        draw = MockDrawCall(event_id=1, index_count=300, vs_id="vs_complex")
        score = analyzer.add_draw(draw)
        
        # 500 / 200 + 0.5 = 3.0
        self.assertEqual(score.shader_weight, 3.0)
    
    def test_shader_name_heuristic(self):
        """测试 Shader 名称启发式"""
        analyzer = HotspotAnalyzer()
        
        # PBR 着色器
        draw = MockDrawCall(event_id=1, index_count=300, ps_id="ps_pbr_main")
        score = analyzer.add_draw(draw)
        self.assertEqual(score.shader_weight, 1.5)  # SHADER_WEIGHTS["pbr"]
    
    def test_state_weight(self):
        """测试状态权重计算"""
        analyzer = HotspotAnalyzer()
        
        # 启用混合 + 无深度测试
        draw = MockDrawCall(
            event_id=1,
            index_count=300,
            blend_enabled=True,
            depth_test=False,
        )
        score = analyzer.add_draw(draw)
        
        # 1.0 + 0.1 (blend) + 0.05 (no depth) = 1.15
        self.assertAlmostEqual(score.state_weight, 1.15, places=2)
    
    def test_analyze_empty(self):
        """测试空分析"""
        analyzer = HotspotAnalyzer()
        report = analyzer.analyze()
        
        self.assertEqual(report.total_draws, 0)
        self.assertEqual(len(report.hotspots), 0)
    
    def test_analyze_hotspot_levels(self):
        """测试热点级别分配"""
        analyzer = HotspotAnalyzer()
        
        # 添加 20 个 draw，复杂度递增
        for i in range(20):
            draw = MockDrawCall(
                event_id=i,
                index_count=(i + 1) * 300,  # 100 ~ 2000 triangles
            )
            analyzer.add_draw(draw)
        
        report = analyzer.analyze()
        
        # 验证排序 (最高分在前)
        self.assertEqual(report.hotspots[0].event_id, 19)
        
        # 验证级别分配
        levels = [h.hotspot_level for h in report.hotspots]
        self.assertIn(HotspotLevel.CRITICAL, levels)
        self.assertIn(HotspotLevel.HIGH, levels)
    
    def test_analyze_pass_aggregation(self):
        """测试 Pass 级别聚合"""
        analyzer = HotspotAnalyzer()
        
        # Pass 0: 3 draws
        for i in range(3):
            analyzer.add_draw(MockDrawCall(event_id=i, index_count=3000, pass_index=0))
        
        # Pass 1: 2 heavy draws
        for i in range(3, 5):
            analyzer.add_draw(MockDrawCall(event_id=i, index_count=30000, pass_index=1))
        
        report = analyzer.analyze()
        
        self.assertEqual(len(report.pass_hotspots), 2)
        # Pass 1 应该排在前面 (更重)
        self.assertEqual(report.pass_hotspots[0].pass_index, 1)
    
    def test_generate_suggestions(self):
        """测试优化建议生成"""
        analyzer = HotspotAnalyzer()
        
        # 添加一个高多边形 draw
        draw = MockDrawCall(
            event_id=1,
            index_count=600000,  # 200k triangles
            instance_count=200,
            rt_ids=["rt0", "rt1", "rt2", "rt3", "rt4", "rt5"],
        )
        analyzer.add_draw(draw)
        
        report = analyzer.analyze()
        
        self.assertTrue(len(report.suggestions) > 0)
        sugg = report.suggestions[0]
        
        # 验证建议内容
        self.assertIn("高多边形数", str(sugg["reasons"]))
        self.assertIn("大量实例", str(sugg["reasons"]))
        self.assertIn("MRT", str(sugg["reasons"]))
    
    def test_score_distribution(self):
        """测试分数分布统计"""
        analyzer = HotspotAnalyzer()
        
        for i in range(100):
            analyzer.add_draw(MockDrawCall(event_id=i, index_count=(i + 1) * 30))
        
        dist = analyzer.get_score_distribution(bins=5)
        
        self.assertEqual(len(dist), 5)
        total_count = sum(d[2] for d in dist)
        self.assertEqual(total_count, 100)


class TestAnalyzeHotspotsFunction(unittest.TestCase):
    """测试便捷函数"""
    
    def test_analyze_hotspots(self):
        """测试 analyze_hotspots 函数"""
        draws = [
            {"eid": 1, "numIndices": 3000},
            {"eid": 2, "numIndices": 30000},
            {"eid": 3, "numIndices": 300},
        ]
        
        report = analyze_hotspots(draws, top_n=2)
        
        self.assertEqual(report.total_draws, 3)
        self.assertEqual(len(report.hotspots), 2)
        # 最高分应该是 eid=2
        self.assertEqual(report.hotspots[0].event_id, 2)


if __name__ == "__main__":
    # 运行测试
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromModule(sys.modules[__name__])
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # 输出摘要
    print("\n" + "=" * 60)
    if result.wasSuccessful():
        print(f"[OK] All {result.testsRun} tests passed!")
    else:
        print(f"[FAIL] {len(result.failures)} failures, {len(result.errors)} errors")
    
    sys.exit(0 if result.wasSuccessful() else 1)

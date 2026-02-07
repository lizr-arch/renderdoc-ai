#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
M4.3 端到端测试：验证 Shader 多维度分析数据流

测试内容：
1. 后端 generate_shaders() 是否正确生成 maliAnalysis + dynamicMetrics
2. JSON 数据结构是否符合前端期望
3. 评分算法是否正确计算健康评分和加权成本
"""

import json
import sys
import tempfile
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))


def test_data_structure_generation():
    """测试：后端生成的数据结构是否正确"""
    from report_bundle_generator import ReportBundleGenerator
    
    # 创建临时输出目录
    with tempfile.TemporaryDirectory() as tmpdir:
        gen = ReportBundleGenerator(tmpdir, "TestCapture")
        
        # 模拟 Shader 数据
        mock_shaders = [
            {
                "id": "shader_001",
                "name": "MainPS",
                "type": "fragment",
                "hlsl": "float4 main() { return float4(1,0,0,1); }"
            },
            {
                "id": "shader_002",
                "name": "ShadowVS",
                "type": "vertex",
                "hlsl": "void main() {}"
            }
        ]
        
        # 模拟 Mali 分析数据
        mock_mali_data = {
            "shader_001": {
                "cycles": {"total": 15.5, "arithmetic": 8.0, "load_store": 4.0, "texture": 12.0, "varying": 2.0},
                "bound": "T",
                "work_registers": 28,
                "uniform_registers": 16,
                "stack_spilling": False,
                "has_late_zs": False,
                "fma_util": 45,
                "cvt_util": 30,
                "sfu_util": 25
            }
        }
        
        # 模拟 Shader 使用映射
        mock_usage_map = {
            "shader_001": [
                {"event_id": 100, "draw_name": "PostProcess_Bloom", "slot": 0},
                {"event_id": 105, "draw_name": "PostProcess_Bloom", "slot": 0},
                {"event_id": 200, "draw_name": "DrawMesh_Character", "slot": 0},
            ],
            "shader_002": [
                {"event_id": 50, "draw_name": "ShadowPass", "slot": 0},
            ]
        }
        
        gen.set_shaders(mock_shaders, mali_data=mock_mali_data, usage_map=mock_usage_map)
        
        # 生成 shaders.html
        html_content = gen.generate_shaders()
        
        # 提取 shaderData JSON (模板使用 const shaderData = {{SHADER_DATA_JSON}};)
        import re
        match = re.search(r'const shaderData = (\[.*?\]);', html_content, re.DOTALL)
        
        assert match, "未找到 shaderData JSON"
        
        shader_data = json.loads(match.group(1))
        
        print(f"✓ 成功生成 {len(shader_data)} 个 Shader 数据")
        
        # 验证第一个 Shader (有 Mali 数据)
        shader1 = shader_data[0]
        
        # 检查 maliAnalysis 字段
        assert "maliAnalysis" in shader1, "缺少 maliAnalysis 字段"
        mali = shader1["maliAnalysis"]
        
        assert mali["cycles"] == 15.5, f"cycles 错误: {mali['cycles']}"
        assert mali["boundUnit"] == "T", f"boundUnit 错误: {mali['boundUnit']}"
        assert mali["workRegisters"] == 28, f"workRegisters 错误: {mali['workRegisters']}"
        assert mali["uniformRegisters"] == 16, f"uniformRegisters 错误"
        assert mali["stackSpilling"] == False, "stackSpilling 错误"
        assert mali["hasLateZS"] == False, "hasLateZS 错误"
        
        print("✓ maliAnalysis 字段结构正确")
        
        # 检查 cycleDetails
        assert "cycleDetails" in mali, "缺少 cycleDetails"
        cd = mali["cycleDetails"]
        assert cd["arithmetic"] == 8.0, f"arithmetic 错误: {cd['arithmetic']}"
        assert cd["texture"] == 12.0, f"texture 错误: {cd['texture']}"
        
        print("✓ cycleDetails 字段正确")
        
        # 检查 dynamicMetrics 字段
        assert "dynamicMetrics" in shader1, "缺少 dynamicMetrics 字段"
        dm = shader1["dynamicMetrics"]
        
        assert dm["drawCount"] == 3, f"drawCount 错误: {dm['drawCount']} (期望 3)"
        assert dm["pixelCoverage"] == 1.0, f"pixelCoverage 错误: {dm['pixelCoverage']} (期望 1.0，因为有 bloom)"
        assert dm["viewportWidth"] == 1920, "viewportWidth 错误"
        assert dm["viewportHeight"] == 1080, "viewportHeight 错误"
        
        print("✓ dynamicMetrics 字段正确")
        
        # 检查 usedBy 字段
        assert "usedBy" in shader1, "缺少 usedBy 字段"
        assert len(shader1["usedBy"]) == 3, f"usedBy 长度错误: {len(shader1['usedBy'])}"
        
        print("✓ usedBy 字段正确")
        
        # 验证第二个 Shader (无 Mali 数据)
        shader2 = shader_data[1]
        
        assert "maliAnalysis" not in shader2 or shader2.get("maliAnalysis") is None, \
            "shader_002 不应有 maliAnalysis"
        assert "dynamicMetrics" in shader2, "shader_002 应有 dynamicMetrics"
        assert shader2["dynamicMetrics"]["drawCount"] == 1, "shader_002 drawCount 错误"
        # ShadowPass -> coverage = 0.5
        assert shader2["dynamicMetrics"]["pixelCoverage"] == 0.5, \
            f"shader_002 pixelCoverage 错误: {shader2['dynamicMetrics']['pixelCoverage']}"
        
        print("✓ 无 Mali 数据的 Shader 处理正确")
        
        return True


def test_health_score_algorithm():
    """测试：评分算法计算是否正确"""
    # 直接从 shader_perf_analyzer 模块导入（已添加项目路径到 sys.path）
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "shader_perf_analyzer",
        str(Path(__file__).parent.parent / "analyzers" / "shader_perf_analyzer.py")
    )
    spa = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(spa)
    
    calculate_cycles_score = spa.calculate_cycles_score
    calculate_register_score = spa.calculate_register_score
    calculate_weighted_cost = spa.calculate_weighted_cost
    calculate_health_score = spa.calculate_health_score
    HealthLevel = spa.HealthLevel
    
    # 测试 cycles 评分
    assert calculate_cycles_score(5) == 100, "5 cycles 应为 100 分"
    assert calculate_cycles_score(8) == 100, "8 cycles 应为 100 分"
    assert 80 <= calculate_cycles_score(14) <= 82, f"14 cycles 应约为 80 分: {calculate_cycles_score(14)}"
    assert 58 <= calculate_cycles_score(20) <= 62, f"20 cycles 应约为 60 分: {calculate_cycles_score(20)}"
    assert calculate_cycles_score(40) < 20, f"40 cycles 应 < 20 分: {calculate_cycles_score(40)}"
    
    print("✓ cycles 评分算法正确")
    
    # 测试寄存器评分
    assert calculate_register_score(16, False) == 100, "16 regs 应为 100 分"
    assert 83 <= calculate_register_score(32, False) <= 87, f"32 regs 应约为 85 分: {calculate_register_score(32, False)}"
    assert calculate_register_score(48, False) < 60, f"48 regs 应 < 60 分: {calculate_register_score(48, False)}"
    assert calculate_register_score(32, True) == 20, "stack_spilling 应为 20 分"
    
    print("✓ 寄存器评分算法正确")
    
    # 测试加权成本
    cost = calculate_weighted_cost(
        cycles=10.0,
        viewport_pixels=1920 * 1080,
        coverage=0.5,
        draw_count=5,
        register_penalty=1.0
    )
    expected = (10.0 * 1920 * 1080 * 0.5 * 5 * 1.0) / 1_000_000
    assert abs(cost - expected) < 0.01, f"加权成本计算错误: {cost} != {expected}"
    
    print("✓ 加权成本算法正确")
    
    # 测试健康评分
    score, level = calculate_health_score(80, 85, 0, 0)
    assert 60 <= score <= 90, f"健康评分异常: {score}"
    assert level == HealthLevel.INFO, f"健康等级异常: {level}"
    
    score2, level2 = calculate_health_score(50, 50, 1, 0)
    assert level2 == HealthLevel.CRITICAL, f"有 critical 规则时应为 CRITICAL: {level2}"
    
    print("✓ 健康评分综合算法正确")
    
    return True


def test_coverage_heuristic():
    """测试：覆盖率启发式估算"""
    # 检查后端实现的 Pass 名称识别
    test_cases = [
        ("PostProcess_Bloom", 1.0),
        ("PostProcess_Blur", 1.0),
        ("FullscreenBlit", 1.0),
        ("ShadowPass", 0.5),
        ("UI_HUD", 0.2),
        ("DrawMesh_Character", 0.5),  # 默认
    ]
    
    from report_bundle_generator import ReportBundleGenerator
    import tempfile
    
    with tempfile.TemporaryDirectory() as tmpdir:
        gen = ReportBundleGenerator(tmpdir, "Test")
        
        for pass_name, expected_coverage in test_cases:
            # 模拟带有特定 Pass 名称的使用记录
            mock_shaders = [{"id": "s1", "name": "TestShader", "type": "fragment"}]
            mock_usage = {
                "s1": [{"event_id": 1, "draw_name": pass_name, "slot": 0}]
            }
            
            gen.set_shaders(mock_shaders, mali_data={}, usage_map=mock_usage)
            html = gen.generate_shaders()
            
            # 提取 JSON
            import re
            match = re.search(r'const shaderData = (\[.*?\]);', html, re.DOTALL)
            if not match:
                raise AssertionError(f"未找到 shaderData JSON for pass '{pass_name}'")
            data = json.loads(match.group(1))
            
            actual = data[0]["dynamicMetrics"]["pixelCoverage"]
            assert abs(actual - expected_coverage) < 0.01, \
                f"Pass '{pass_name}' 覆盖率错误: {actual} (期望 {expected_coverage})"
        
        print("✓ 覆盖率启发式估算正确")
    
    return True


def main():
    """运行所有测试"""
    print("\n" + "=" * 60)
    print("M4.3 端到端测试: Shader 多维度分析数据流")
    print("=" * 60 + "\n")
    
    tests = [
        ("数据结构生成", test_data_structure_generation),
        ("评分算法", test_health_score_algorithm),
        ("覆盖率启发式", test_coverage_heuristic),
    ]
    
    passed = 0
    failed = 0
    
    for name, test_func in tests:
        print(f"\n--- 测试: {name} ---")
        try:
            if test_func():
                passed += 1
                print(f"✅ {name} 通过")
        except AssertionError as e:
            failed += 1
            print(f"❌ {name} 失败: {e}")
        except Exception as e:
            failed += 1
            print(f"❌ {name} 异常: {type(e).__name__}: {e}")
    
    print("\n" + "=" * 60)
    print(f"测试结果: {passed} 通过, {failed} 失败")
    print("=" * 60)
    
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    exit(main())

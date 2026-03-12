#!/usr/bin/env python3
"""
E2E 测试用 Bundle 报告生成器

生成包含 Evidence Chain 和深链接功能的测试报告，
用于验证 M3 里程碑的跨页面跳转和高亮功能。
"""

import sys
from pathlib import Path

# 添加父目录到 PATH
sys.path.insert(0, str(Path(__file__).parent.parent))

from report_bundle_generator import ReportBundleGenerator


def create_test_data():
    """创建包含 Evidence Chain 的完整测试数据"""
    
    # 纹理数据（用于 textures.html）
    textures = [
        {
            "id": "tex_001",
            "name": "diffuse_hero",
            "width": 4096,
            "height": 4096,
            "format": "BC7_UNORM",
            "mips": 1,
            "vram_bytes": 4096 * 4096,
            "thumbnail": None
        },
        {
            "id": "tex_002", 
            "name": "normal_ground",
            "width": 2048,
            "height": 2048,
            "format": "BC5_UNORM",
            "mips": 8,
            "vram_bytes": 2048 * 2048,
            "thumbnail": None
        },
        {
            "id": "tex_003",
            "name": "ui_button",
            "width": 512,
            "height": 512,
            "format": "R8G8B8A8_UNORM",
            "mips": 1,
            "vram_bytes": 512 * 512 * 4,
            "thumbnail": None
        }
    ]
    
    # 事件数据（用于 events.html）
    events = [
        {
            "eid": 100,
            "name": "DrawIndexed",
            "draw_calls": 1,
            "duration_us": 150.5,
            "vertex_count": 30000,
            "instance_count": 1
        },
        {
            "eid": 200,
            "name": "DrawIndexedInstanced",
            "draw_calls": 1,
            "duration_us": 320.8,
            "vertex_count": 15000,
            "instance_count": 50
        },
        {
            "eid": 300,
            "name": "Dispatch",
            "draw_calls": 1,
            "duration_us": 85.2,
            "thread_groups": [16, 16, 1]
        }
    ]
    
    # Shader 数据（用于 shaders.html）
    shaders = [
        {
            "id": "shader_001",
            "name": "VS_Main",
            "type": "Vertex",
            "instructions": 45,
            "registers": 8,
            "source_preview": "// Vertex shader for main pass"
        },
        {
            "id": "shader_002",
            "name": "PS_Main",
            "type": "Pixel",
            "instructions": 120,
            "registers": 24,
            "source_preview": "// Pixel shader with PBR lighting"
        },
        {
            "id": "shader_003",
            "name": "CS_Blur",
            "type": "Compute",
            "instructions": 80,
            "registers": 16,
            "source_preview": "// Gaussian blur compute shader"
        }
    ]
    
    # 性能问题数据（用于 recommendations.html）- 包含 Evidence Chain
    performance_data = {
        "issues": [
            {
                "id": "issue_001",
                "severity": "high",
                "category": "Texture",
                "title": "超大纹理未使用 Mipmap",
                "description": "发现 4096x4096 纹理仅有 1 级 mip，可能导致远距离采样时带宽浪费",
                "impact": "GPU 带宽浪费约 30%",
                "suggestion": "为该纹理生成完整 mipmap 链",
                "evidence": {
                    "evidence_chain": {
                        "summary": "4096x4096 纹理仅有 1 级 mip",
                        "evidences": [
                            {
                                "label": "纹理尺寸",
                                "value": "4096",
                                "unit": "px",
                                "threshold": "2048",
                                "severity": "critical"
                            },
                            {
                                "label": "Mip 级数",
                                "value": "1",
                                "unit": "",
                                "threshold": "8+",
                                "severity": "warning"
                            }
                        ],
                        "actions": [
                            {
                                "type": "jump",
                                "label": "跳转到纹理",
                                "target_page": "textures",
                                "target_id": "tex_001"
                            }
                        ],
                        "affected_resources": ["tex_001"]
                    }
                }
            },
            {
                "id": "issue_002",
                "severity": "medium",
                "category": "DrawCall",
                "title": "高顶点数绘制调用",
                "description": "EID 100 绘制了 30000 个顶点，考虑使用 LOD 或剔除优化",
                "impact": "顶点处理开销较高",
                "suggestion": "实现基于距离的 LOD 系统",
                "evidence": {
                    "evidence_chain": {
                        "summary": "EID 100 绘制了 30000 个顶点",
                        "evidences": [
                            {
                                "label": "顶点数",
                                "value": "30000",
                                "unit": "",
                                "threshold": "20000",
                                "severity": "warning"
                            }
                        ],
                        "actions": [
                            {
                                "type": "jump",
                                "label": "跳转到事件",
                                "target_page": "events",
                                "target_id": "100"
                            }
                        ],
                        "affected_resources": ["100"]
                    }
                }
            },
            {
                "id": "issue_003",
                "severity": "low",
                "category": "Shader",
                "title": "Shader 指令数较高",
                "description": "PS_Main 使用了 120 条指令，可能影响像素填充率",
                "impact": "像素着色器可能成为瓶颈",
                "suggestion": "考虑简化光照计算或使用预计算 LUT",
                "evidence": {
                    "evidence_chain": {
                        "summary": "PS_Main 使用了 120 条指令",
                        "evidences": [
                            {
                                "label": "指令数",
                                "value": "120",
                                "unit": "",
                                "threshold": "100",
                                "severity": "info"
                            }
                        ],
                        "actions": [
                            {
                                "type": "jump",
                                "label": "跳转到 Shader",
                                "target_page": "shaders",
                                "target_id": "shader_002"
                            }
                        ],
                        "affected_resources": ["shader_002"]
                    }
                }
            }
        ],
        "summary": {
            "total_issues": 3,
            "high_severity": 1,
            "medium_severity": 1,
            "low_severity": 1
        }
    }
    
    # 汇总数据（用于 index.html）
    summary = {
        "capture_name": "E2E_Test_Capture",
        "api": "D3D11",
        "total_events": len(events),
        "total_textures": len(textures),
        "total_shaders": len(shaders),
        "total_vram_mb": sum(t["vram_bytes"] for t in textures) / (1024 * 1024),
        "performance_score": 72,
        "issues_count": len(performance_data["issues"])
    }
    
    return {
        "summary": summary,
        "textures": textures,
        "events": events,
        "shaders": shaders,
        "performance": performance_data
    }


def main():
    """生成 E2E 测试 Bundle 报告"""
    
    # 输出目录
    output_dir = Path(__file__).parent.parent / "test_captures" / "export_output" / "e2e_test"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print("=" * 70)
    print("E2E Test Bundle Generator")
    print("=" * 70)
    
    # 创建测试数据
    print("\n[1/2] Creating test data with Evidence Chain...")
    test_data = create_test_data()
    
    print(f"  - Textures: {len(test_data['textures'])}")
    print(f"  - Events: {len(test_data['events'])}")
    print(f"  - Shaders: {len(test_data['shaders'])}")
    print(f"  - Performance Issues: {len(test_data['performance']['issues'])}")
    
    # 生成报告
    print("\n[2/2] Generating Bundle Report...")
    generator = ReportBundleGenerator(output_dir, "E2E_Test_Capture")
    
    # 使用正确的 setter 方法设置数据
    generator.set_textures(test_data["textures"])
    generator.set_events(test_data["events"])
    generator.set_shaders(test_data["shaders"])
    generator.set_performance_data(test_data["performance"])
    
    # 使用 generate_all() 生成并保存所有页面
    generator.generate_all()
    
    # 输出验证信息
    print("\n" + "=" * 70)
    print("✅ E2E Test Bundle Generated Successfully!")
    print("=" * 70)
    print(f"\nOutput: {output_dir}")
    print("\n📋 E2E Verification Checklist:")
    print("-" * 40)
    print("1. Open recommendations.html in browser")
    print("2. Find issue '超大纹理未使用 Mipmap'")
    print("3. Click '跳转到纹理' button")
    print("4. Verify: Should navigate to textures.html?id=tex_001&highlight=true")
    print("5. Verify: tex_001 should have pulse highlight animation")
    print("-" * 40)
    print("6. Go back to recommendations.html")
    print("7. Find issue '高顶点数绘制调用'")
    print("8. Click '跳转到事件' button")
    print("9. Verify: Should navigate to events.html?eid=100&highlight=true")
    print("10. Verify: EID 100 row should have pulse highlight")
    print("-" * 40)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())

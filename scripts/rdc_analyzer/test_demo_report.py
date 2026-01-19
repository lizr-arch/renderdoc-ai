#!/usr/bin/env python3
"""生成演示报告 - 包含模拟的去重和热度分析数据"""

import json
import sys
from pathlib import Path

# 确保可以导入本地模块
sys.path.insert(0, str(Path(__file__).parent))

from generate_offline_report import generate_offline_html

def main():
    # 读取纹理数据
    textures_file = Path(__file__).parent / "test_captures/test_game_textures/textures.json"
    
    if not textures_file.exists():
        print(f"[ERROR] 找不到纹理文件: {textures_file}")
        return 1
    
    with open(textures_file, 'r', encoding='utf-8') as f:
        textures = json.load(f)
    
    print(f"[OK] 加载了 {len(textures)} 个纹理")
    
    # 模拟去重分析结果
    duplicate_analysis = {
        "duplicate_groups": [
            {
                "hash": "abc123def456",
                "count": 3,
                "wasted_bytes": 4194304,
                "textures": [
                    {"resource_id": 101, "name": "DiffuseTexture_001", "width": 2048, "height": 2048, "format": "BC7_UNORM"},
                    {"resource_id": 201, "name": "DiffuseTexture_Copy", "width": 2048, "height": 2048, "format": "BC7_UNORM"},
                    {"resource_id": 301, "name": "DiffuseTexture_Backup", "width": 2048, "height": 2048, "format": "BC7_UNORM"}
                ]
            },
            {
                "hash": "xyz789abc012",
                "count": 2,
                "wasted_bytes": 1048576,
                "textures": [
                    {"resource_id": 102, "name": "NormalMap_Brick", "width": 1024, "height": 1024, "format": "BC5_UNORM"},
                    {"resource_id": 202, "name": "NormalMap_Brick_v2", "width": 1024, "height": 1024, "format": "BC5_UNORM"}
                ]
            }
        ],
        "total_wasted_bytes": 5242880,
        "total_duplicate_count": 3,
        "metadata_only": False
    }
    
    # 模拟热度分析结果
    usage_analysis = {
        "total_events": 1247,
        "used_textures": 3,
        "unused_textures": 2,
        "hot_list": [
            {"resource_id": 101, "name": "DiffuseTexture_001", "use_count": 89, "estimated_size": 4194304},
            {"resource_id": 103, "name": "AlbedoMap_Metal", "use_count": 67, "estimated_size": 1048576},
            {"resource_id": 102, "name": "NormalMap_Brick", "use_count": 45, "estimated_size": 1048576}
        ],
        "cold_list": [
            {"resource_id": 104, "name": "UI_Placeholder", "use_count": 0, "estimated_size": 262144, "format": "R8G8B8A8_UNORM"},
            {"resource_id": 105, "name": "DebugTexture_Grid", "use_count": 0, "estimated_size": 524288, "format": "R8G8B8A8_UNORM"}
        ]
    }
    
    # 生成报告
    output_path = Path(__file__).parent / "demo_full_report.html"
    
    generate_offline_html(
        textures,
        "test_game.rdc",
        str(output_path),
        duplicate_analysis=duplicate_analysis,
        usage_analysis=usage_analysis
    )
    
    print(f"[OK] 报告已生成: {output_path}")
    print(f"[OK] 文件大小: {output_path.stat().st_size / 1024:.1f} KB")
    return 0


if __name__ == "__main__":
    sys.exit(main())

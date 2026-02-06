#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Generate a realistic 145-texture analysis report with:
- Duplicate detection results
- Usage heatmap (hot/cold textures)
- Optimization recommendations

This simulates a real RDC analysis to demonstrate M3 features.
"""

import json
import random
import hashlib
import base64
import os
import sys

# Add parent path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.optimization_advisor import OptimizationAdvisor, generate_optimization_report as gen_opt_report


def generate_placeholder_thumbnail(width, height, color_seed):
    """Generate a minimal PNG placeholder (colored square)"""
    # Return a simple base64 placeholder - in real use this would be actual texture data
    random.seed(color_seed)
    r, g, b = random.randint(50,200), random.randint(50,200), random.randint(50,200)
    
    # Minimal SVG with solid color (placeholder for real texture thumbnails)
    svg_content = '<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64"><rect fill="rgb({},{},{})" width="64" height="64"/></svg>'.format(r, g, b)
    encoded = base64.b64encode(svg_content.encode()).decode()
    return "data:image/svg+xml;base64," + encoded


def generate_realistic_textures(count=145):
    """Generate realistic texture metadata simulating a game capture"""
    
    textures = []
    
    # Texture categories found in typical game captures
    categories = [
        # Diffuse/Albedo textures (common, often large)
        {"prefix": "T_", "suffix": "_D", "format": "BC7_UNORM", "sizes": [(2048, 2048), (1024, 1024), (512, 512)], "weight": 25},
        {"prefix": "T_", "suffix": "_Albedo", "format": "BC7_UNORM_SRGB", "sizes": [(2048, 2048), (1024, 1024)], "weight": 15},
        
        # Normal maps
        {"prefix": "T_", "suffix": "_N", "format": "BC5_UNORM", "sizes": [(2048, 2048), (1024, 1024), (512, 512)], "weight": 20},
        
        # Roughness/Metallic/AO (often packed)
        {"prefix": "T_", "suffix": "_ORM", "format": "BC7_UNORM", "sizes": [(1024, 1024), (512, 512)], "weight": 10},
        {"prefix": "T_", "suffix": "_Mask", "format": "BC4_UNORM", "sizes": [(512, 512), (256, 256)], "weight": 8},
        
        # UI textures
        {"prefix": "UI_", "suffix": "", "format": "R8G8B8A8_UNORM", "sizes": [(256, 256), (128, 128), (64, 64)], "weight": 12},
        
        # Shadow maps
        {"prefix": "ShadowMap_", "suffix": "", "format": "D32_FLOAT", "sizes": [(4096, 4096), (2048, 2048)], "weight": 3},
        
        # HDR environment
        {"prefix": "HDR_", "suffix": "_Cubemap", "format": "R16G16B16A16_FLOAT", "sizes": [(512, 512), (256, 256)], "weight": 2},
        
        # Render targets
        {"prefix": "RT_", "suffix": "_Color", "format": "R11G11B10_FLOAT", "sizes": [(1920, 1080), (1280, 720)], "weight": 3},
        {"prefix": "RT_", "suffix": "_Depth", "format": "D24_UNORM_S8_UINT", "sizes": [(1920, 1080)], "weight": 2},
    ]
    
    # Asset names for variety
    asset_names = [
        "Brick", "Concrete", "Metal", "Wood", "Stone", "Glass", "Fabric", "Leather",
        "Character", "Weapon", "Vehicle", "Environment", "Foliage", "Rock", "Ground",
        "Wall", "Floor", "Ceiling", "Door", "Window", "Prop", "Decal", "FX",
        "Hero", "Enemy", "NPC", "Player", "Boss", "Chest", "Barrel", "Crate",
        "Sky", "Cloud", "Water", "Fire", "Smoke", "Debris", "Blood", "Dirt"
    ]
    
    texture_id = 1000
    
    # Generate textures based on weighted categories
    for cat in categories:
        num_textures = int(count * cat["weight"] / 100)
        for i in range(num_textures):
            name = f"{cat['prefix']}{random.choice(asset_names)}_{i:02d}{cat['suffix']}"
            size = random.choice(cat["sizes"])
            
            textures.append({
                "id": texture_id,
                "resourceId": texture_id,
                "name": name,
                "format": cat["format"],
                "width": size[0],
                "height": size[1],
                "depth": 1,
                "mips": calculate_mip_levels(size[0], size[1]),
                "arrayLayers": 6 if "Cubemap" in name else 1,
                "thumbnail": generate_placeholder_thumbnail(size[0], size[1], texture_id)
            })
            texture_id += 1
    
    # Fill remaining with random textures
    while len(textures) < count:
        cat = random.choice(categories)
        size = random.choice(cat["sizes"])
        name = f"{cat['prefix']}{random.choice(asset_names)}_{len(textures):02d}{cat['suffix']}"
        
        textures.append({
            "id": texture_id,
            "resourceId": texture_id,
            "name": name,
            "format": cat["format"],
            "width": size[0],
            "height": size[1],
            "depth": 1,
            "mips": calculate_mip_levels(size[0], size[1]),
            "arrayLayers": 1,
            "thumbnail": generate_placeholder_thumbnail(size[0], size[1], texture_id)
        })
        texture_id += 1
    
    return textures[:count]


def calculate_mip_levels(width, height):
    """Calculate number of mip levels for a texture"""
    import math
    return max(1, int(math.log2(max(width, height))) + 1)


def generate_duplicate_groups(textures):
    """Simulate duplicate detection results"""
    
    duplicates = {
        "groups": [],
        "total_wasted_bytes": 0,
        "total_duplicates": 0
    }
    
    # Create 5-8 duplicate groups
    num_groups = random.randint(5, 8)
    used_ids = set()
    
    for group_idx in range(num_groups):
        # Pick 2-4 textures to be "duplicates"
        available = [t for t in textures if t["id"] not in used_ids and t["width"] >= 512]
        if len(available) < 2:
            break
            
        group_size = random.randint(2, min(4, len(available)))
        members = random.sample(available, group_size)
        
        # Calculate wasted VRAM
        base_tex = members[0]
        bytes_per_tex = estimate_vram(base_tex)
        wasted = bytes_per_tex * (len(members) - 1)
        
        duplicates["groups"].append({
            "hash": hashlib.md5(f"group_{group_idx}".encode()).hexdigest()[:16],
            "textures": [{"id": m["id"], "name": m["name"], "format": m["format"], 
                         "width": m["width"], "height": m["height"]} for m in members],
            "wasted_bytes": wasted
        })
        
        duplicates["total_wasted_bytes"] += wasted
        duplicates["total_duplicates"] += len(members) - 1
        
        for m in members:
            used_ids.add(m["id"])
    
    return duplicates


def generate_usage_analysis(textures):
    """Simulate texture usage analysis (hot/cold detection)"""
    
    usage = {
        "textures": {},
        "dead_textures": [],
        "hot_textures": [],
        "cold_textures": []
    }
    
    for tex in textures:
        tex_id = tex["id"]
        
        # Simulate usage patterns
        # - RT and Shadow maps: always hot (used every frame)
        # - UI: medium usage
        # - Character/Weapon: high usage
        # - Some assets: never used (dead)
        
        if tex["name"].startswith("RT_") or tex["name"].startswith("ShadowMap_"):
            use_count = random.randint(50, 200)
            usage["hot_textures"].append(tex_id)
        elif tex["name"].startswith("UI_"):
            use_count = random.randint(5, 30)
        elif any(kw in tex["name"] for kw in ["Character", "Player", "Weapon", "Hero"]):
            use_count = random.randint(20, 100)
            usage["hot_textures"].append(tex_id)
        else:
            # 15% chance of being dead texture
            if random.random() < 0.15:
                use_count = 0
                usage["dead_textures"].append(tex_id)
            else:
                use_count = random.randint(1, 20)
                if use_count <= 3:
                    usage["cold_textures"].append(tex_id)
        
        usage["textures"][str(tex_id)] = {
            "use_count": use_count,
            "first_use_eid": random.randint(10, 100) if use_count > 0 else None,
            "last_use_eid": random.randint(500, 1000) if use_count > 0 else None
        }
    
    return usage


def estimate_vram(tex):
    """Estimate VRAM usage for a texture"""
    bpp_map = {
        "BC1_UNORM": 0.5, "BC1_UNORM_SRGB": 0.5,
        "BC3_UNORM": 1.0, "BC3_UNORM_SRGB": 1.0,
        "BC4_UNORM": 0.5, "BC5_UNORM": 1.0,
        "BC7_UNORM": 1.0, "BC7_UNORM_SRGB": 1.0,
        "R8G8B8A8_UNORM": 4.0, "R8G8B8A8_SRGB": 4.0,
        "R16G16B16A16_FLOAT": 8.0,
        "R11G11B10_FLOAT": 4.0,
        "D32_FLOAT": 4.0, "D24_UNORM_S8_UINT": 4.0,
    }
    
    bpp = bpp_map.get(tex["format"], 4.0)
    pixels = tex["width"] * tex["height"] * tex.get("depth", 1) * tex.get("arrayLayers", 1)
    
    # Account for mipmaps (roughly 1.33x for full chain)
    if tex.get("mips", 1) > 1:
        pixels = int(pixels * 1.33)
    
    return int(pixels * bpp)


def generate_optimization_report(textures, duplicates, usage, rdc_name="Game_capture.rdc"):
    """Use OptimizationAdvisor to generate recommendations"""
    
    # Convert duplicate groups to the format expected by OptimizationAdvisor
    duplicate_analysis = {
        "duplicate_groups": [],
        "total_wasted_bytes": duplicates["total_wasted_bytes"]
    }
    
    for group in duplicates["groups"]:
        duplicate_analysis["duplicate_groups"].append({
            "hash": group["hash"],
            "textures": [
                {"resource_id": t["id"], "name": t["name"]} 
                for t in group["textures"]
            ],
            "wasted_bytes": group["wasted_bytes"]
        })
    
    # Convert usage analysis to expected format
    cold_list = []
    for tex_id in usage["dead_textures"]:
        tex = next((t for t in textures if t["id"] == tex_id), None)
        if tex:
            cold_list.append({
                "resource_id": tex_id,
                "name": tex["name"],
                "estimated_size": estimate_vram(tex)
            })
    
    usage_analysis = {
        "cold_list": cold_list,
        "hot_list": usage.get("hot_textures", []),
        "usage_map": usage.get("textures", {})
    }
    
    # Create advisor and run analysis
    advisor = OptimizationAdvisor(
        textures=textures,
        rdc_name=rdc_name,
        duplicate_analysis=duplicate_analysis,
        usage_analysis=usage_analysis
    )
    
    report = advisor.analyze()
    
    # Calculate summary stats
    total_savings = report.get_total_savings()
    issues = []
    
    for item in report.items:
        issues.append({
            "severity": item.priority.name,
            "title": item.title,
            "description": item.description,
            "savings_bytes": item.estimated_savings_bytes,
            "category": item.category.value,
            "affected_count": len(item.affected_resources)
        })
    
    return {
        "markdown": report.to_markdown(),
        "issues": issues,
        "summary": {
            "total_issues": len(issues),
            "total_savings_bytes": total_savings
        }
    }


def main():
    print("=" * 60)
    print("  Generating 145-Texture Analysis Report (M3 Demo)")
    print("=" * 60)
    
    # Generate realistic texture data
    print("\n[1/5] Generating realistic texture metadata...")
    textures = generate_realistic_textures(145)
    print(f"      Generated {len(textures)} textures")
    
    # Calculate total VRAM
    total_vram = sum(estimate_vram(t) for t in textures)
    print(f"      Total VRAM: {total_vram / (1024*1024):.1f} MB")
    
    # Generate duplicate analysis
    print("\n[2/5] Simulating duplicate detection...")
    duplicates = generate_duplicate_groups(textures)
    print(f"      Found {len(duplicates['groups'])} duplicate groups")
    print(f"      Total duplicates: {duplicates['total_duplicates']}")
    print(f"      Wasted VRAM: {duplicates['total_wasted_bytes'] / (1024*1024):.2f} MB")
    
    # Generate usage analysis
    print("\n[3/5] Simulating usage analysis...")
    usage = generate_usage_analysis(textures)
    print(f"      Dead textures: {len(usage['dead_textures'])}")
    print(f"      Cold textures: {len(usage['cold_textures'])}")
    print(f"      Hot textures: {len(usage['hot_textures'])}")
    
    # Generate optimization report
    print("\n[4/5] Generating optimization recommendations...")
    opt_report = generate_optimization_report(textures, duplicates, usage)
    
    # Count issues by severity
    critical = len([i for i in opt_report["issues"] if i["severity"] == "CRITICAL"])
    high = len([i for i in opt_report["issues"] if i["severity"] == "HIGH"])
    medium = len([i for i in opt_report["issues"] if i["severity"] == "MEDIUM"])
    low = len([i for i in opt_report["issues"] if i["severity"] == "LOW"])
    print(f"      Issues: {critical} Critical, {high} High, {medium} Medium, {low} Low")
    print(f"      Potential VRAM savings: {opt_report['summary']['total_savings_bytes'] / (1024*1024):.2f} MB")
    
    # Generate HTML report
    print("\n[5/5] Generating HTML report...")
    
    from generate_offline_report import generate_offline_html
    
    # Save report
    output_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    output_path = os.path.join(output_dir, "full_145_texture_report.html")
    
    # Convert duplicates to expected format for generate_offline_html
    duplicate_analysis_for_html = {
        "duplicate_groups": [],
        "total_wasted_bytes": duplicates["total_wasted_bytes"],
        "total_duplicate_count": duplicates["total_duplicates"]
    }
    for group in duplicates["groups"]:
        duplicate_analysis_for_html["duplicate_groups"].append({
            "hash": group["hash"],
            "textures": [
                {"resource_id": t["id"], "name": t["name"]} 
                for t in group["textures"]
            ],
            "count": len(group["textures"]),
            "wasted_bytes": group["wasted_bytes"]
        })
    
    # Convert usage to expected format
    usage_analysis_for_html = {
        "cold_list": [],
        "hot_list": [],
        "total_textures": len(textures),
        "used_count": len(textures) - len(usage["dead_textures"]),
        "unused_count": len(usage["dead_textures"])
    }
    for tex_id in usage["dead_textures"]:
        tex = next((t for t in textures if t["id"] == tex_id), None)
        if tex:
            usage_analysis_for_html["cold_list"].append({
                "resource_id": tex_id,
                "name": tex["name"],
                "estimated_size": estimate_vram(tex)
            })
    for tex_id in usage["hot_textures"]:
        tex = next((t for t in textures if t["id"] == tex_id), None)
        if tex:
            usage_analysis_for_html["hot_list"].append({
                "resource_id": tex_id,
                "name": tex["name"],
                "use_count": usage["textures"].get(str(tex_id), {}).get("use_count", 0)
            })
    
    # Call generate_offline_html (it writes file directly)
    generate_offline_html(
        textures=textures,
        rdc_name="Game_x64h_Capture_2026.01.18_15.30.45.rdc",
        output_path=output_path,
        duplicate_analysis=duplicate_analysis_for_html,
        usage_analysis=usage_analysis_for_html
    )
    
    print(f"\n{'=' * 60}")
    print(f"  Report saved to: {output_path}")
    print(f"{'=' * 60}")
    
    # Also save the Markdown optimization report
    md_path = os.path.join(output_dir, "optimization_recommendations.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(opt_report["markdown"])
    
    print(f"  Optimization report saved to: {md_path}")
    
    return output_path


if __name__ == "__main__":
    main()

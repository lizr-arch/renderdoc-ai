#!/usr/bin/env python3
"""
从 RDC 导出的 XML 中提取 vkCreateDevice chunk，分析 VRS 扩展
"""
import re
import sys

def extract_create_device_chunk(xml_path: str):
    """提取 vkCreateDevice chunk 的完整内容"""
    with open(xml_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 找到 vkCreateDevice chunk
    pattern = r'<chunk[^>]*name="vkCreateDevice"[^>]*>.*?</chunk>'
    match = re.search(pattern, content, re.DOTALL)
    
    if match:
        chunk = match.group(0)
        print(f"[OK] 找到 vkCreateDevice chunk ({len(chunk)} bytes)")
        print("-" * 80)
        
        # 美化输出（每行一个标签）
        lines = chunk.split('><')
        for i, line in enumerate(lines):
            if i > 0:
                line = '<' + line
            if i < len(lines) - 1:
                line = line + '>'
            # 缩进
            indent_level = line.count('<') - line.count('</') - line.count('/>')
            print(line[:500])  # 截断太长的行
        return chunk
    else:
        print("[ERROR] 未找到 vkCreateDevice chunk")
        return None


def search_vrs_keywords(xml_path: str):
    """搜索所有 VRS 相关关键字"""
    keywords = [
        'pipelineFragmentShadingRate',
        'primitiveFragmentShadingRate', 
        'attachmentFragmentShadingRate',
        'VK_KHR_fragment_shading_rate',
        'FragmentShadingRate',
        'VRS',
        'shadingRate'
    ]
    
    print("\n[INFO] 搜索 VRS 相关关键字...")
    with open(xml_path, 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            for kw in keywords:
                if kw.lower() in line.lower():
                    print(f"  Line {line_num}: {line.strip()[:150]}")
                    break


if __name__ == "__main__":
    xml_path = r"D:\backup\scene209_test.xml"
    
    # 先搜索 VRS 关键字
    search_vrs_keywords(xml_path)
    
    print("\n" + "=" * 80)
    print("[INFO] 提取 vkCreateDevice chunk...")
    print("=" * 80)
    
    extract_create_device_chunk(xml_path)

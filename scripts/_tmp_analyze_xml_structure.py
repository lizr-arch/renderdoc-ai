#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""分析 RDC XML 中的资源绑定调用结构"""

import xml.etree.ElementTree as ET

def analyze_chunk_structure(xml_path):
    """分析特定调用的参数结构"""
    tree = ET.parse(xml_path)
    root = tree.getroot()
    chunks = root.find("chunks")
    
    if chunks is None:
        print("No chunks found")
        return
    
    targets = [
        "PSSetShaderResources",
        "PSSetConstantBuffers", 
        "PSSetSamplers",
        "VSSetShaderResources",
        "VSSetConstantBuffers",
        "OMSetRenderTargets",
        "IASetVertexBuffers",
        "IASetIndexBuffer",
        "CreateRasterizerState",
    ]
    
    found = {}
    for chunk in chunks.findall("chunk"):
        chunk_name = chunk.get("name", "")
        for target in targets:
            if target in chunk_name and target not in found:
                found[target] = chunk
                print(f"\n{'='*60}")
                print(f"FOUND: {chunk_name}")
                print(f"{'='*60}")
                print_element(chunk, depth=0, max_depth=3)
                break
                
    print(f"\n\nSummary: Found {len(found)}/{len(targets)} target chunks")
    for t in targets:
        status = "Found" if t in found else "NOT FOUND"
        print(f"  {t}: {status}")

def print_element(elem, depth=0, max_depth=3):
    """递归打印元素结构"""
    if depth > max_depth:
        return
        
    indent = "  " * depth
    attrs = " ".join([f'{k}="{v}"' for k, v in elem.attrib.items()])
    text = (elem.text or "").strip()[:50]
    
    print(f"{indent}<{elem.tag} {attrs}>{text}")
    
    for child in list(elem)[:10]:  # 限制子元素数量
        print_element(child, depth + 1, max_depth)

if __name__ == "__main__":
    import sys
    xml_path = sys.argv[1] if len(sys.argv) > 1 else "scripts/rdc_analyzer/output/e2e_test_pc/capture.xml"
    analyze_chunk_structure(xml_path)

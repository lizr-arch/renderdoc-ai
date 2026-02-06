#!/usr/bin/env python3
"""
分析 RDC 所需的 Vulkan 扩展 vs 软件渲染器支持的扩展
"""

import os
import sys
from datetime import datetime

LOG_FILE = r"D:\backup\extension_analysis_log.txt"

def log(msg):
    timestamp = datetime.now().strftime("%H:%M:%S")
    line = f"[{timestamp}] {msg}"
    print(line)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def main():
    log("=" * 60)
    log("RDC Vulkan 扩展需求分析")
    log("=" * 60)
    log("")
    
    try:
        import renderdoc as rd
        log("[OK] renderdoc 模块导入成功")
    except ImportError as e:
        log(f"[ERROR] 无法导入 renderdoc: {e}")
        return
    
    rdc_path = r"D:\backup\人物入水.rdc"
    log(f"RDC 文件: {rdc_path}")
    log("")
    
    # 打开 RDC 并获取其 Structured Data
    cap = rd.OpenCaptureFile()
    result = cap.OpenFile(rdc_path, '', None)
    
    if hasattr(result, 'code'):
        if result.code != rd.ResultCode.Succeeded:
            log(f"[ERROR] 无法打开: {result.message}")
            return
    
    log("[OK] RDC 打开成功")
    
    # 获取结构化数据
    log("")
    log("正在读取结构化数据...")
    sdf = cap.OpenStructuredFile()
    if sdf is None:
        log("[ERROR] 无法获取结构化数据")
        cap.Shutdown()
        return
    
    log(f"[OK] Chunks 数量: {len(sdf.chunks)}")
    
    # 搜索 vkCreateInstance 和 vkCreateDevice 来找到启用的扩展
    log("")
    log("搜索启用的扩展...")
    
    instance_extensions = []
    device_extensions = []
    
    for i, chunk in enumerate(sdf.chunks):
        chunk_name = chunk.name
        
        # vkCreateInstance 包含实例扩展
        if "vkCreateInstance" in chunk_name:
            log(f"  找到 vkCreateInstance (Chunk {i})")
            # 遍历 chunk 数据找扩展
            try:
                data = chunk.data
                log(f"    数据类型: {type(data)}")
                # 尝试找 ppEnabledExtensionNames
                if hasattr(data, 'children'):
                    for child in data.children:
                        log(f"      {child.name}: {child.type}")
            except Exception as e:
                log(f"    [WARN] 无法解析: {e}")
        
        # vkCreateDevice 包含设备扩展
        if "vkCreateDevice" in chunk_name:
            log(f"  找到 vkCreateDevice (Chunk {i})")
            try:
                data = chunk.data
                if hasattr(data, 'children'):
                    for child in data.children:
                        log(f"      {child.name}")
            except Exception as e:
                log(f"    [WARN] 无法解析: {e}")
        
        # 限制搜索范围
        if i > 100:
            break
    
    # 从已导出的 XML 中搜索扩展
    log("")
    log("从 XML 文件搜索扩展...")
    
    xml_path = r"D:\backup\人物入水_export\frame.xml"
    if os.path.exists(xml_path):
        log(f"  使用: {xml_path}")
        
        # 简单的文本搜索
        import re
        
        try:
            with open(xml_path, 'r', encoding='utf-8', errors='ignore') as f:
                # 只读取前 1MB
                content = f.read(1024 * 1024)
            
            # 搜索 VK_ 开头的扩展名
            extensions = set(re.findall(r'VK_[A-Z]+_[a-z_]+', content))
            
            log(f"  找到 {len(extensions)} 个扩展引用:")
            for ext in sorted(extensions):
                log(f"    - {ext}")
                
        except Exception as e:
            log(f"  [ERROR] 无法读取 XML: {e}")
    else:
        log(f"  [WARN] XML 不存在: {xml_path}")
    
    cap.Shutdown()
    log("")
    log("分析完成")


if __name__ == "__main__":
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        f.write(f"扩展分析 - {datetime.now().isoformat()}\n\n")
    
    try:
        main()
    except Exception as e:
        log(f"[FATAL] {e}")
        import traceback
        log(traceback.format_exc())

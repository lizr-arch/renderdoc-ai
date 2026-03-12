#!/usr/bin/env python3
"""
RenderDoc XML RenderPass 分析器

功能：
1. 解析 RenderDoc 导出的 XML 文件
2. 提取所有 RenderPass 及其绑定的 Render Target
3. 生成 RenderPass 摘要报告

用法：
    py -3 analyze_renderpass.py <xml_path>

版本: 1.0.0
"""

import re
import sys
from pathlib import Path
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


@dataclass
class ImageInfo:
    """Image 信息"""
    resource_id: int
    width: int = 0
    height: int = 0
    depth: int = 1
    format: str = ""
    usage: str = ""
    name: str = ""


@dataclass
class ImageViewInfo:
    """ImageView 信息"""
    view_id: int
    image_id: int
    format: str = ""
    aspect: str = ""


@dataclass
class FramebufferInfo:
    """Framebuffer 信息"""
    fb_id: int
    renderpass_id: int
    width: int
    height: int
    attachments: List[int] = field(default_factory=list)  # ImageView IDs


@dataclass
class RenderPassInstance:
    """RenderPass 实例（一次 BeginRenderPass 调用）"""
    chunk_index: int
    renderpass_id: int
    framebuffer_id: int
    render_area: Tuple[int, int]  # width, height
    draw_count: int = 0
    timestamp: int = 0


class RenderPassAnalyzer:
    """RenderPass 分析器"""
    
    def __init__(self, xml_path: str):
        self.xml_path = Path(xml_path)
        self.data: bytes = b""
        
        # 资源表
        self.images: Dict[int, ImageInfo] = {}
        self.image_views: Dict[int, ImageViewInfo] = {}
        self.framebuffers: Dict[int, FramebufferInfo] = {}
        self.renderpass_instances: List[RenderPassInstance] = []
        
    def load(self):
        """加载 XML 文件"""
        print(f"加载文件: {self.xml_path}")
        print(f"文件大小: {self.xml_path.stat().st_size / 1024 / 1024:.1f} MB")
        self.data = self.xml_path.read_bytes()
        print(f"已加载到内存")
        
    def parse_images(self):
        """解析 vkCreateImage"""
        pattern = rb'vkCreateImage"[^>]*>.*?<ResourceId name="image"[^>]*>(\d+)</ResourceId>.*?</chunk>'
        # 简化：直接提取关键字段
        img_pattern = rb'<chunk[^>]*name="vkCreateImage"[^>]*>.*?<ResourceId name="Image"[^>]*>(\d+)</ResourceId>'
        
        for match in re.finditer(rb'<chunk[^>]*name="vkCreateImage"[^>]*length="(\d+)".*?</chunk>', self.data, re.DOTALL):
            chunk_data = match.group(0)
            
            # 提取 Image ID
            id_match = re.search(rb'<ResourceId name="Image"[^>]*>(\d+)</ResourceId>', chunk_data)
            if not id_match:
                continue
            img_id = int(id_match.group(1))
            
            # 提取尺寸
            width = height = depth = 0
            extent_match = re.search(rb'<struct name="extent".*?<uint name="width"[^>]*>(\d+)</uint>.*?<uint name="height"[^>]*>(\d+)</uint>.*?<uint name="depth"[^>]*>(\d+)</uint>', chunk_data, re.DOTALL)
            if extent_match:
                width = int(extent_match.group(1))
                height = int(extent_match.group(2))
                depth = int(extent_match.group(3))
            
            # 提取格式
            fmt = ""
            fmt_match = re.search(rb'<enum name="format"[^>]*string="([^"]+)"', chunk_data)
            if fmt_match:
                fmt = fmt_match.group(1).decode()
            
            # 提取 usage
            usage = ""
            usage_match = re.search(rb'<enum name="usage"[^>]*string="([^"]+)"', chunk_data)
            if usage_match:
                usage = usage_match.group(1).decode()
            
            self.images[img_id] = ImageInfo(
                resource_id=img_id,
                width=width,
                height=height,
                depth=depth,
                format=fmt,
                usage=usage
            )
        
        print(f"  解析到 {len(self.images)} 个 Image")
        
    def parse_image_views(self):
        """解析 vkCreateImageView"""
        for match in re.finditer(rb'<chunk[^>]*name="vkCreateImageView"[^>]*>.*?</chunk>', self.data, re.DOTALL):
            chunk_data = match.group(0)
            
            # 提取 View ID
            view_match = re.search(rb'<ResourceId name="View"[^>]*>(\d+)</ResourceId>', chunk_data)
            if not view_match:
                continue
            view_id = int(view_match.group(1))
            
            # 提取 Image ID
            img_match = re.search(rb'<ResourceId name="image"[^>]*>(\d+)</ResourceId>', chunk_data)
            img_id = int(img_match.group(1)) if img_match else 0
            
            # 提取格式
            fmt = ""
            fmt_match = re.search(rb'<enum name="format"[^>]*string="([^"]+)"', chunk_data)
            if fmt_match:
                fmt = fmt_match.group(1).decode()
            
            # 提取 aspect
            aspect = ""
            aspect_match = re.search(rb'<enum name="aspectMask"[^>]*string="([^"]+)"', chunk_data)
            if aspect_match:
                aspect = aspect_match.group(1).decode()
            
            self.image_views[view_id] = ImageViewInfo(
                view_id=view_id,
                image_id=img_id,
                format=fmt,
                aspect=aspect
            )
        
        print(f"  解析到 {len(self.image_views)} 个 ImageView")
        
    def parse_framebuffers(self):
        """解析 vkCreateFramebuffer"""
        for match in re.finditer(rb'<chunk[^>]*name="vkCreateFramebuffer"[^>]*>.*?</chunk>', self.data, re.DOTALL):
            chunk_data = match.group(0)
            
            # 提取 Framebuffer ID
            fb_match = re.search(rb'<ResourceId name="Framebuffer"[^>]*>(\d+)</ResourceId>', chunk_data)
            if not fb_match:
                continue
            fb_id = int(fb_match.group(1))
            
            # 提取 RenderPass ID
            rp_match = re.search(rb'<ResourceId name="renderPass"[^>]*>(\d+)</ResourceId>', chunk_data)
            rp_id = int(rp_match.group(1)) if rp_match else 0
            
            # 提取尺寸
            w_match = re.search(rb'<uint name="width"[^>]*>(\d+)</uint>', chunk_data)
            h_match = re.search(rb'<uint name="height"[^>]*>(\d+)</uint>', chunk_data)
            width = int(w_match.group(1)) if w_match else 0
            height = int(h_match.group(1)) if h_match else 0
            
            # 提取 Attachments (ImageView IDs)
            attachments = []
            attach_match = re.search(rb'<array name="pAttachments"[^>]*>(.*?)</array>', chunk_data, re.DOTALL)
            if attach_match:
                for iv_match in re.finditer(rb'<ResourceId[^>]*>(\d+)</ResourceId>', attach_match.group(1)):
                    attachments.append(int(iv_match.group(1)))
            
            self.framebuffers[fb_id] = FramebufferInfo(
                fb_id=fb_id,
                renderpass_id=rp_id,
                width=width,
                height=height,
                attachments=attachments
            )
        
        print(f"  解析到 {len(self.framebuffers)} 个 Framebuffer")
        
    def parse_renderpass_instances(self):
        """解析 vkCmdBeginRenderPass 调用"""
        # 先找所有 BeginRenderPass 位置
        begins = list(re.finditer(rb'<chunk[^>]*chunkIndex="(\d+)"[^>]*name="vkCmdBeginRenderPass"[^>]*timestamp="(\d+)"[^>]*>.*?</chunk>', self.data, re.DOTALL))
        
        for match in begins:
            chunk_data = match.group(0)
            chunk_index = int(match.group(1))
            timestamp = int(match.group(2))
            
            # 提取 RenderPass ID
            rp_match = re.search(rb'<ResourceId name="renderPass"[^>]*>(\d+)</ResourceId>', chunk_data)
            rp_id = int(rp_match.group(1)) if rp_match else 0
            
            # 提取 Framebuffer ID
            fb_match = re.search(rb'<ResourceId name="framebuffer"[^>]*>(\d+)</ResourceId>', chunk_data)
            fb_id = int(fb_match.group(1)) if fb_match else 0
            
            # 提取 renderArea
            w_match = re.search(rb'<uint name="width"[^>]*>(\d+)</uint>', chunk_data)
            h_match = re.search(rb'<uint name="height"[^>]*>(\d+)</uint>', chunk_data)
            width = int(w_match.group(1)) if w_match else 0
            height = int(h_match.group(1)) if h_match else 0
            
            self.renderpass_instances.append(RenderPassInstance(
                chunk_index=chunk_index,
                renderpass_id=rp_id,
                framebuffer_id=fb_id,
                render_area=(width, height),
                timestamp=timestamp
            ))
        
        print(f"  解析到 {len(self.renderpass_instances)} 个 RenderPass 实例")
        
    def count_draws_per_renderpass(self):
        """统计每个 RenderPass 内的 Draw 数量"""
        # 找所有 Draw 和 EndRenderPass 的位置
        events = []
        
        for match in re.finditer(rb'<chunk[^>]*chunkIndex="(\d+)"[^>]*name="(vkCmdDraw\w*|vkCmdEndRenderPass)"', self.data):
            chunk_index = int(match.group(1))
            name = match.group(2).decode()
            events.append((chunk_index, name))
        
        events.sort(key=lambda x: x[0])
        
        # 分配 draw 到对应的 renderpass
        rp_idx = 0
        for chunk_index, name in events:
            if rp_idx >= len(self.renderpass_instances):
                break
            
            rp = self.renderpass_instances[rp_idx]
            
            if chunk_index < rp.chunk_index:
                continue
            
            if name == "vkCmdEndRenderPass":
                rp_idx += 1
            elif name.startswith("vkCmdDraw"):
                rp.draw_count += 1
        
    def analyze(self):
        """执行完整分析"""
        print("\n" + "=" * 60)
        print("RenderPass 分析")
        print("=" * 60)
        
        print("\n[1/5] 解析 Images...")
        self.parse_images()
        
        print("[2/5] 解析 ImageViews...")
        self.parse_image_views()
        
        print("[3/5] 解析 Framebuffers...")
        self.parse_framebuffers()
        
        print("[4/5] 解析 RenderPass 实例...")
        self.parse_renderpass_instances()
        
        print("[5/5] 统计 Draw 调用...")
        self.count_draws_per_renderpass()
        
    def generate_report(self) -> str:
        """生成报告"""
        lines = []
        lines.append("=" * 70)
        lines.append("RenderPass 分析报告")
        lines.append("=" * 70)
        lines.append(f"文件: {self.xml_path.name}")
        lines.append(f"总 Images: {len(self.images)}")
        lines.append(f"总 ImageViews: {len(self.image_views)}")
        lines.append(f"总 Framebuffers: {len(self.framebuffers)}")
        lines.append(f"总 RenderPass 实例: {len(self.renderpass_instances)}")
        lines.append("")
        
        # 按尺寸分组
        size_groups: Dict[Tuple[int, int], List[RenderPassInstance]] = defaultdict(list)
        for rp in self.renderpass_instances:
            size_groups[rp.render_area].append(rp)
        
        lines.append("-" * 70)
        lines.append("按 RenderArea 尺寸分组")
        lines.append("-" * 70)
        
        for size, rps in sorted(size_groups.items(), key=lambda x: x[0][0] * x[0][1], reverse=True):
            total_draws = sum(rp.draw_count for rp in rps)
            lines.append(f"\n[{size[0]}x{size[1]}] - {len(rps)} passes, {total_draws} draws")
            
            for i, rp in enumerate(rps[:5]):  # 只显示前 5 个
                fb = self.framebuffers.get(rp.framebuffer_id)
                rt_info = []
                
                if fb:
                    for view_id in fb.attachments[:3]:  # 只显示前 3 个附件
                        iv = self.image_views.get(view_id)
                        if iv:
                            img = self.images.get(iv.image_id)
                            if img:
                                rt_info.append(f"Image#{iv.image_id} ({img.format})")
                            else:
                                rt_info.append(f"View#{view_id}")
                
                rt_str = ", ".join(rt_info) if rt_info else "N/A"
                lines.append(f"  [{i+1}] ChunkIdx={rp.chunk_index}, Draws={rp.draw_count}, RT=[{rt_str}]")
            
            if len(rps) > 5:
                lines.append(f"  ... 还有 {len(rps) - 5} 个 passes")
        
        # 可能的 Render Target 分析
        lines.append("")
        lines.append("-" * 70)
        lines.append("疑似主要 Render Target (屏幕分辨率或大尺寸)")
        lines.append("-" * 70)
        
        main_rts = []
        for img_id, img in self.images.items():
            # 检查是否被用作 RT (通过 usage 或 format)
            is_rt = any([
                "COLOR_ATTACHMENT" in img.usage,
                "DEPTH" in img.usage,
                "DEPTH" in img.format,
                img.width >= 1024 and img.height >= 512,  # 较大纹理
            ])
            if is_rt:
                main_rts.append(img)
        
        main_rts.sort(key=lambda x: x.width * x.height, reverse=True)
        
        for img in main_rts[:15]:
            usage_short = img.usage.replace("VK_IMAGE_USAGE_", "").replace("_BIT", "")[:40]
            lines.append(f"  Image#{img.resource_id}: {img.width}x{img.height} {img.format}")
            if usage_short:
                lines.append(f"    Usage: {usage_short}")
        
        return "\n".join(lines)


def main():
    if len(sys.argv) < 2:
        print("用法: py -3 analyze_renderpass.py <xml_path>")
        print("示例: py -3 analyze_renderpass.py D:\\backup\\人物入水.xml")
        sys.exit(1)
    
    xml_path = sys.argv[1]
    
    analyzer = RenderPassAnalyzer(xml_path)
    analyzer.load()
    analyzer.analyze()
    
    report = analyzer.generate_report()
    print("\n" + report)
    
    # 保存报告
    report_path = Path(xml_path).with_suffix(".renderpass_report.txt")
    report_path.write_text(report, encoding="utf-8")
    print(f"\n报告已保存到: {report_path}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
纹理去重检测器

检测 RDC 捕获中内容相同但 ID 不同的重复纹理，量化 VRAM 浪费。

算法：
1. 阶段一：按元数据 (width, height, format, mips) 分组，找出候选重复
2. 阶段二：对候选组计算内容哈希 (MD5)，确认真正重复

Author: RenderDoc Analyzer Project
Version: 1.0.0
"""

import hashlib
from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass, field


@dataclass
class DuplicateGroup:
    """重复纹理组"""
    fingerprint: str  # 内容哈希的前16字符
    count: int  # 重复数量
    wasted_bytes: int  # 浪费的字节数 = (count - 1) × size
    textures: List[Dict[str, Any]] = field(default_factory=list)  # 组内所有纹理


@dataclass 
class DuplicateAnalysisResult:
    """去重分析结果"""
    duplicate_groups: List[DuplicateGroup] = field(default_factory=list)
    total_wasted_bytes: int = 0
    total_duplicate_count: int = 0  # 多余的纹理数量
    total_textures_scanned: int = 0
    skipped_textures: int = 0  # 跳过的纹理（太大或无法读取）
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典（用于 JSON 序列化）"""
        return {
            "duplicate_groups": [
                {
                    "fingerprint": g.fingerprint,
                    "count": g.count,
                    "wasted_bytes": g.wasted_bytes,
                    "textures": g.textures
                }
                for g in self.duplicate_groups
            ],
            "total_wasted_bytes": self.total_wasted_bytes,
            "total_duplicate_count": self.total_duplicate_count,
            "total_textures_scanned": self.total_textures_scanned,
            "skipped_textures": self.skipped_textures
        }


class DuplicateDetector:
    """
    纹理去重检测器
    
    使用两阶段算法：
    1. 元数据预过滤：相同 (width, height, format, mips) 的纹理才可能重复
    2. 内容哈希确认：计算像素数据的 MD5 哈希，找出真正重复
    """
    
    # 默认最大处理纹理大小 (16MB 未压缩)
    DEFAULT_MAX_SIZE = 16 * 1024 * 1024
    
    def __init__(self, controller=None, progress_callback: Optional[Callable[[int, int, str], None]] = None):
        """
        初始化检测器
        
        Args:
            controller: RenderDoc ReplayController 实例
            progress_callback: 进度回调 (current, total, message)
        """
        self._controller = controller
        self._progress_callback = progress_callback
        self._rd = None  # renderdoc 模块引用
    
    def set_controller(self, controller):
        """设置 ReplayController"""
        self._controller = controller
    
    def _report_progress(self, current: int, total: int, message: str):
        """报告进度"""
        if self._progress_callback:
            self._progress_callback(current, total, message)
    
    def _estimate_texture_size(self, tex: Dict[str, Any]) -> int:
        """
        估算纹理大小（字节）
        
        Args:
            tex: 纹理信息字典
            
        Returns:
            估算的字节数
        """
        width = tex.get("width", 0)
        height = tex.get("height", 0)
        depth = tex.get("depth", 1)
        mips = tex.get("mip_levels", 1)
        array_layers = tex.get("array_layers", 1)
        
        # 从格式名推断 BPP
        format_name = tex.get("format_name", "").upper()
        
        # BPP 映射 (bits per pixel)
        if "BC1" in format_name or "DXT1" in format_name:
            bpp = 4
        elif "BC2" in format_name or "BC3" in format_name or "DXT" in format_name:
            bpp = 8
        elif "BC4" in format_name:
            bpp = 4
        elif "BC5" in format_name:
            bpp = 8
        elif "BC6" in format_name or "BC7" in format_name:
            bpp = 8
        elif "ASTC_4x4" in format_name:
            bpp = 8
        elif "ASTC_5x5" in format_name:
            bpp = 5.12
        elif "ASTC_6x6" in format_name:
            bpp = 3.56
        elif "ASTC_8x8" in format_name:
            bpp = 2
        elif "R8G8B8A8" in format_name or "B8G8R8A8" in format_name or "RGBA8" in format_name:
            bpp = 32
        elif "R8G8B8" in format_name or "RGB8" in format_name:
            bpp = 24
        elif "R16G16B16A16" in format_name:
            bpp = 64
        elif "R32G32B32A32" in format_name:
            bpp = 128
        elif "R8" in format_name:
            bpp = 8
        elif "R16" in format_name or "D16" in format_name:
            bpp = 16
        elif "R32" in format_name or "D32" in format_name or "D24" in format_name:
            bpp = 32
        else:
            bpp = 32  # 默认假设 32bpp
        
        # 计算 Mipmap 链总大小
        total_size = 0
        mip_width, mip_height, mip_depth = width, height, depth
        
        for _ in range(mips):
            mip_size = int(mip_width * mip_height * mip_depth * bpp / 8)
            total_size += max(mip_size, 1)
            mip_width = max(mip_width // 2, 1)
            mip_height = max(mip_height // 2, 1)
            mip_depth = max(mip_depth // 2, 1)
        
        return total_size * array_layers
    
    def _get_metadata_key(self, tex: Dict[str, Any]) -> tuple:
        """
        生成纹理元数据键（用于第一阶段分组）
        
        Args:
            tex: 纹理信息字典
            
        Returns:
            (width, height, depth, format_name, mip_levels, array_layers) 元组
        """
        return (
            tex.get("width", 0),
            tex.get("height", 0),
            tex.get("depth", 1),
            tex.get("format_name", ""),
            tex.get("mip_levels", 1),
            tex.get("array_layers", 1)
        )
    
    def _compute_content_hash(self, resource_id: int, use_sampling: bool = False) -> Optional[str]:
        """
        计算纹理内容的 MD5 哈希
        
        Args:
            resource_id: 纹理资源 ID
            use_sampling: 是否使用采样模式（只取部分数据）
            
        Returns:
            MD5 哈希字符串，失败返回 None
        """
        if self._controller is None:
            return None
        
        try:
            # 延迟导入 renderdoc 模块
            if self._rd is None:
                import renderdoc as rd
                self._rd = rd
            
            # 获取 Mip 0 的数据
            sub = self._rd.Subresource(0, 0, 0)
            data = self._controller.GetTextureData(
                self._rd.ResourceId.FromInteger(resource_id),
                sub
            )
            
            if data is None or len(data) == 0:
                return None
            
            # 计算哈希
            if use_sampling and len(data) > 65536:
                # 采样模式：取开头、中间、结尾各一部分
                sample_size = 16384
                sample = data[:sample_size]
                mid = len(data) // 2
                sample += data[mid:mid + sample_size]
                sample += data[-sample_size:]
                return hashlib.md5(sample).hexdigest()
            else:
                return hashlib.md5(bytes(data)).hexdigest()
                
        except Exception as e:
            print(f"  [WARN] Failed to compute hash for resource {resource_id}: {e}")
            return None
    
    def detect(
        self, 
        textures: List[Dict[str, Any]], 
        max_size: int = DEFAULT_MAX_SIZE,
        use_sampling: bool = False
    ) -> DuplicateAnalysisResult:
        """
        检测重复纹理
        
        Args:
            textures: 纹理信息列表
            max_size: 最大处理纹理大小（字节），超过则跳过
            use_sampling: 对大纹理使用采样哈希
            
        Returns:
            DuplicateAnalysisResult 分析结果
        """
        result = DuplicateAnalysisResult()
        result.total_textures_scanned = len(textures)
        
        if not textures:
            return result
        
        self._report_progress(0, len(textures), "开始元数据分组...")
        
        # =====================================================================
        # 阶段 1: 按元数据分组
        # =====================================================================
        metadata_groups: Dict[tuple, List[Dict[str, Any]]] = {}
        
        for tex in textures:
            key = self._get_metadata_key(tex)
            if key not in metadata_groups:
                metadata_groups[key] = []
            
            # 添加估算大小
            tex["_estimated_size"] = self._estimate_texture_size(tex)
            metadata_groups[key].append(tex)
        
        # 筛选出可能重复的组（元数据相同且有多个纹理）
        candidate_groups = {
            k: v for k, v in metadata_groups.items() 
            if len(v) >= 2
        }
        
        if not candidate_groups:
            self._report_progress(len(textures), len(textures), "未发现候选重复组")
            return result
        
        self._report_progress(0, len(candidate_groups), f"发现 {len(candidate_groups)} 个候选组，开始计算内容哈希...")
        
        # =====================================================================
        # 阶段 2: 对候选组计算内容哈希
        # =====================================================================
        processed = 0
        
        for group_idx, (meta_key, group) in enumerate(candidate_groups.items()):
            self._report_progress(group_idx, len(candidate_groups), f"分析候选组 {group_idx + 1}/{len(candidate_groups)}")
            
            # 按内容哈希再分组
            hash_map: Dict[str, List[Dict[str, Any]]] = {}
            
            for tex in group:
                res_id = tex.get("resource_id", 0)
                estimated_size = tex.get("_estimated_size", 0)
                
                # 检查大小限制
                if estimated_size > max_size and not use_sampling:
                    result.skipped_textures += 1
                    continue
                
                # 计算内容哈希
                content_hash = self._compute_content_hash(
                    res_id, 
                    use_sampling=(use_sampling and estimated_size > max_size // 4)
                )
                
                if content_hash is None:
                    result.skipped_textures += 1
                    continue
                
                if content_hash not in hash_map:
                    hash_map[content_hash] = []
                hash_map[content_hash].append(tex)
            
            # 找出真正重复的（哈希相同且有多个）
            for content_hash, duplicates in hash_map.items():
                if len(duplicates) >= 2:
                    # 计算浪费的字节数
                    sizes = [d.get("_estimated_size", 0) for d in duplicates]
                    wasted = sum(sizes[1:])  # 除第一个外都是浪费的
                    
                    # 构建纹理信息列表
                    tex_list = []
                    for d in duplicates:
                        tex_list.append({
                            "resource_id": d.get("resource_id", 0),
                            "name": d.get("custom_name", "") or d.get("name", f"Texture_{d.get('resource_id', 0)}"),
                            "size": d.get("_estimated_size", 0),
                            "width": d.get("width", 0),
                            "height": d.get("height", 0),
                            "format": d.get("format_name", "")
                        })
                    
                    dup_group = DuplicateGroup(
                        fingerprint=content_hash[:16],
                        count=len(duplicates),
                        wasted_bytes=wasted,
                        textures=tex_list
                    )
                    result.duplicate_groups.append(dup_group)
                    result.total_wasted_bytes += wasted
                    result.total_duplicate_count += len(duplicates) - 1  # 多余的数量
        
        # 按浪费字节数排序（从大到小）
        result.duplicate_groups.sort(key=lambda g: g.wasted_bytes, reverse=True)
        
        self._report_progress(
            len(candidate_groups), 
            len(candidate_groups), 
            f"完成！发现 {len(result.duplicate_groups)} 组重复"
        )
        
        return result


def detect_duplicates_from_texture_list(
    textures: List[Dict[str, Any]],
    controller=None,
    max_size: int = DuplicateDetector.DEFAULT_MAX_SIZE,
    progress_callback: Optional[Callable[[int, int, str], None]] = None
) -> Dict[str, Any]:
    """
    便捷函数：从纹理列表检测重复
    
    Args:
        textures: 纹理信息列表（需包含 resource_id, width, height, format_name 等字段）
        controller: RenderDoc ReplayController（可选，用于计算内容哈希）
        max_size: 最大处理纹理大小
        progress_callback: 进度回调
        
    Returns:
        分析结果字典
    """
    detector = DuplicateDetector(controller, progress_callback)
    
    if controller is None:
        # 无 controller 时只能做元数据比对
        print("  [INFO] No controller provided, using metadata-only comparison")
        return _metadata_only_detect(textures)
    
    result = detector.detect(textures, max_size)
    return result.to_dict()


def _metadata_only_detect(textures: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    仅基于元数据的重复检测（无需 ReplayController）
    
    这是一个降级方案，只能找出元数据完全相同的纹理，
    无法确认内容是否真的相同。
    
    Returns:
        带有 "metadata_only": True 标记的结果
    """
    metadata_groups: Dict[tuple, List[Dict[str, Any]]] = {}
    
    for tex in textures:
        key = (
            tex.get("width", 0),
            tex.get("height", 0),
            tex.get("depth", 1),
            tex.get("format_name", ""),
            tex.get("mip_levels", 1),
            tex.get("array_layers", 1)
        )
        if key not in metadata_groups:
            metadata_groups[key] = []
        metadata_groups[key].append(tex)
    
    duplicate_groups = []
    total_wasted = 0
    total_dup_count = 0
    
    for key, group in metadata_groups.items():
        if len(group) >= 2:
            # 估算大小
            width, height, depth, _, mips, layers = key
            estimated_size = width * height * depth * 4 * layers  # 粗略估计
            wasted = estimated_size * (len(group) - 1)
            
            tex_list = []
            for tex in group:
                tex_list.append({
                    "resource_id": tex.get("resource_id", 0),
                    "name": tex.get("custom_name", "") or tex.get("name", ""),
                    "size": estimated_size,
                    "width": width,
                    "height": height,
                    "format": tex.get("format_name", "")
                })
            
            duplicate_groups.append({
                "fingerprint": f"meta_{hash(key) & 0xFFFFFFFF:08x}",
                "count": len(group),
                "wasted_bytes": wasted,
                "textures": tex_list
            })
            total_wasted += wasted
            total_dup_count += len(group) - 1
    
    # 按浪费排序
    duplicate_groups.sort(key=lambda g: g["wasted_bytes"], reverse=True)
    
    return {
        "duplicate_groups": duplicate_groups,
        "total_wasted_bytes": total_wasted,
        "total_duplicate_count": total_dup_count,
        "total_textures_scanned": len(textures),
        "skipped_textures": 0,
        "metadata_only": True  # 标记这是仅元数据检测
    }

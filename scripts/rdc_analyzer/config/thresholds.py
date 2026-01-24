"""
检测阈值配置
============

定义各规则的检测阈值，与 RULES_RENDERDOC.md 保持同步。
"""

from typing import Dict, Any


_ALIAS_KEYS = {
    # Draw Call
    "draw_call_count": "max_draw_calls",
    "min_vertices_per_draw": "small_draw_vertex_threshold",
    "instancing_threshold": "instancing_suggestion_threshold",
    # Texture
    "max_texture_memory_mb": "large_texture_threshold_mb",
    "mipmap_required_size": "mipmap_required_min_size",
    # Buffer
    "max_buffer_size_mb": "large_buffer_threshold_mb",
    "max_buffer_updates": "dynamic_buffer_update_threshold",
    # Render Target
    "max_rt_switches": "max_rt_changes",
    # State
    "max_blend_changes": "max_blend_state_changes",
}

_ALIAS_DEFAULTS = {
    # Draw Call
    "max_vertices_per_draw": 100000,
    # Texture
    "max_texture_size": 2048,
    "compression_required_size": 512,
    "texture_array_threshold": 8,
    # Buffer
    "max_vertex_stride": 64,
    # State
    "max_depth_changes": 200,
    "max_rasterizer_changes": 200,
    "max_blend_draws": 200,
    # Render Pass
    "depth_prepass_threshold": 500,
    "max_shadowmap_size": 4096,
    # Mobile-only rules
    "mobile_max_overdraw": 3.0,
    "mobile_texture_size": 1024,
    "mobile_max_alpha_test": 50,
}


def _apply_threshold_aliases(thresholds: Dict[str, Any]) -> Dict[str, Any]:
    """补齐规则别名阈值，避免规则读取不到配置值。"""
    for alias, target in _ALIAS_KEYS.items():
        if alias not in thresholds and target in thresholds:
            thresholds[alias] = thresholds[target]

    for key, value in _ALIAS_DEFAULTS.items():
        thresholds.setdefault(key, value)

    return thresholds


# PC 平台默认阈值
DEFAULT_THRESHOLDS: Dict[str, Any] = {
    # ==================== Draw Call 规则 ====================
    # RD_DC_001: Draw Call 数量过多
    "max_draw_calls": 3000,
    
    # RD_DC_002: 小批次 Draw Call
    "small_draw_vertex_threshold": 100,
    "small_draw_max_ratio": 0.1,  # 10%
    
    # RD_DC_003: 空 Draw Call
    "empty_draw_enabled": True,
    
    # RD_DC_004: 实例化建议阈值
    "instancing_suggestion_threshold": 50,  # 相似 Draw 数量
    
    # ==================== 纹理规则 ====================
    # RD_TEX_001: 超大纹理
    "large_texture_threshold_mb": 16.0,
    
    # RD_TEX_002: 纹理尺寸超出屏幕
    "texture_oversized_factor": 2.0,  # 超过屏幕分辨率 N 倍
    
    # RD_TEX_003: NPOT 纹理警告
    "npot_warning_enabled": True,
    
    # RD_TEX_004: 未压缩纹理
    "uncompressed_texture_threshold_kb": 256,
    
    # RD_TEX_005: Mipmap 缺失
    "mipmap_required_min_size": 256,  # 大于此尺寸需要 Mipmap
    
    # RD_TEX_006: 未使用纹理
    "unused_texture_detection": True,
    
    # RD_TEX_007: 小纹理过多
    "small_texture_size": 32,
    "small_texture_max_count": 100,
    
    # ==================== Buffer 规则 ====================
    # RD_BUF_001: 超大 Buffer
    "large_buffer_threshold_mb": 64.0,
    
    # RD_BUF_002: Dynamic Buffer 频繁更新
    "dynamic_buffer_update_threshold": 10,  # 每帧更新次数
    
    # ==================== Render Target 规则 ====================
    # RD_RT_001: 过多 RT 切换
    "max_rt_changes": 50,
    
    # RD_RT_002: 过大 RT
    "large_rt_factor": 2.0,  # 超过屏幕分辨率 N 倍
    
    # RD_RT_003: 未使用 RT
    "unused_rt_detection": True,
    
    # RD_RT_004: RT Clear 冗余
    "redundant_clear_detection": True,
    
    # ==================== 状态切换规则 ====================
    # RD_STATE_001: 冗余状态设置
    "max_redundant_state_ratio": 0.1,  # 10%
    
    # RD_STATE_002: Shader 切换过多
    "max_shader_changes": 500,
    
    # RD_STATE_003: Blend 状态切换过多
    "max_blend_state_changes": 100,
    
    # ==================== Pass 规则 ====================
    # RD_PASS_001: Pass 数量过多
    "max_pass_count": 30,
    
    # RD_PASS_002: Pass 内 Draw 过少
    "min_draws_per_pass": 5,
    
    # ==================== 全屏效果规则 ====================
    # RD_FS_001: 全屏 Pass 过多
    "max_fullscreen_passes": 10,
    
    # RD_FS_002: 全屏 Pass 分辨率过高
    "fullscreen_resolution_limit": 0,  # 0 = 使用屏幕分辨率
    
    # ==================== 透明度规则 ====================
    # RD_ALPHA_001: 透明物体过多
    "max_transparent_ratio": 0.3,  # 30%
    
    # ==================== 深度规则 ====================
    # RD_DEPTH_001: Overdraw 检测阈值
    "overdraw_threshold": 3.0,  # 平均 3 层以上
    
    # ==================== Compute 规则 ====================
    # RD_CS_001: Dispatch 维度过小
    "min_dispatch_size": 64,
    
    # ==================== 内存规则 ====================
    # RD_MEM_001: 帧内存总量
    "max_frame_memory_mb": 1024.0,  # 1GB
    
    # RD_MEM_002: 纹理内存占比
    "max_texture_memory_ratio": 0.8,  # 80%
}


# 移动端阈值 (更严格)
MOBILE_THRESHOLDS: Dict[str, Any] = {
    **DEFAULT_THRESHOLDS,
    
    # Draw Call 更严格
    "max_draw_calls": 500,
    "small_draw_vertex_threshold": 50,
    
    # 纹理更严格
    "large_texture_threshold_mb": 4.0,
    "texture_oversized_factor": 1.5,
    "mipmap_required_min_size": 128,
    
    # Buffer 更严格
    "large_buffer_threshold_mb": 16.0,
    
    # RT 更严格
    "max_rt_changes": 20,
    "large_rt_factor": 1.5,
    
    # 状态更严格
    "max_shader_changes": 200,
    
    # Pass 更严格
    "max_pass_count": 15,
    "max_fullscreen_passes": 5,
    
    # 内存更严格
    "max_frame_memory_mb": 512.0,
}


# 低端设备阈值
LOW_END_THRESHOLDS: Dict[str, Any] = {
    **MOBILE_THRESHOLDS,
    
    "max_draw_calls": 300,
    "large_texture_threshold_mb": 2.0,
    "max_rt_changes": 10,
    "max_pass_count": 10,
    "max_frame_memory_mb": 256.0,
}

DEFAULT_THRESHOLDS = _apply_threshold_aliases(DEFAULT_THRESHOLDS)
MOBILE_THRESHOLDS = _apply_threshold_aliases(MOBILE_THRESHOLDS)
LOW_END_THRESHOLDS = _apply_threshold_aliases(LOW_END_THRESHOLDS)


def get_thresholds(platform: str = "pc") -> Dict[str, Any]:
    """
    获取指定平台的阈值配置
    
    Args:
        platform: 平台名称 ("pc", "mobile", "low_end")
        
    Returns:
        阈值字典
    """
    platform = platform.lower()
    
    if platform in ("mobile", "android", "ios"):
        return MOBILE_THRESHOLDS.copy()
    elif platform in ("low_end", "lowend", "low"):
        return LOW_END_THRESHOLDS.copy()
    else:
        return DEFAULT_THRESHOLDS.copy()

#!/usr/bin/env python3
"""
纹理使用热度分析器

遍历 Draw Call，统计每个纹理被引用的次数，找出:
- 高频使用的热点纹理
- 从未使用的"死纹理"

Author: RenderDoc Texture Analyzer
Version: 1.0.0
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Any
from collections import defaultdict

# 延迟导入 renderdoc 模块
try:
    import renderdoc as rd
    HAS_RENDERDOC = True
except ImportError:
    HAS_RENDERDOC = False


@dataclass
class TextureUsageInfo:
    """单个纹理的使用信息"""
    resource_id: int
    name: str = ""
    width: int = 0
    height: int = 0
    format: str = ""
    
    # 使用统计
    use_count: int = 0                    # 被绘制调用使用的次数
    used_in_events: List[int] = field(default_factory=list)  # 使用该纹理的事件 ID 列表
    
    # 使用类型
    as_shader_resource: int = 0           # 作为着色器资源 (SRV) 次数
    as_render_target: int = 0             # 作为渲染目标 (RTV) 次数
    as_depth_target: int = 0              # 作为深度模板目标 (DSV) 次数
    as_uav: int = 0                       # 作为无序访问视图 (UAV) 次数
    
    def to_dict(self) -> dict:
        return {
            "resource_id": self.resource_id,
            "name": self.name,
            "width": self.width,
            "height": self.height,
            "format": self.format,
            "use_count": self.use_count,
            "used_in_events": self.used_in_events[:20],  # 只保留前20个事件
            "as_shader_resource": self.as_shader_resource,
            "as_render_target": self.as_render_target,
            "as_depth_target": self.as_depth_target,
            "as_uav": self.as_uav,
        }


@dataclass
class TextureUsageAnalysis:
    """纹理使用分析结果"""
    total_textures: int = 0               # 纹理总数
    used_textures: int = 0                # 被使用的纹理数
    unused_textures: int = 0              # 未使用的纹理数
    total_draw_calls: int = 0             # 绘制调用总数
    
    # 分类列表
    unused_list: List[TextureUsageInfo] = field(default_factory=list)   # 未使用的纹理
    hot_list: List[TextureUsageInfo] = field(default_factory=list)      # 高频使用的纹理 (Top 10)
    cold_list: List[TextureUsageInfo] = field(default_factory=list)     # 低频使用的纹理 (使用1-3次)
    
    # 所有纹理的使用信息
    all_usage: Dict[int, TextureUsageInfo] = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        return {
            "total_textures": self.total_textures,
            "used_textures": self.used_textures,
            "unused_textures": self.unused_textures,
            "total_draw_calls": self.total_draw_calls,
            "unused_list": [t.to_dict() for t in self.unused_list],
            "hot_list": [t.to_dict() for t in self.hot_list],
            "cold_list": [t.to_dict() for t in self.cold_list],
        }


class TextureUsageAnalyzer:
    """纹理使用热度分析器"""
    
    def __init__(self, controller: 'rd.ReplayController', verbose: bool = True):
        """
        Args:
            controller: RenderDoc ReplayController
            verbose: 是否输出详细日志
        """
        if not HAS_RENDERDOC:
            raise RuntimeError("renderdoc module not available")
        
        self._controller = controller
        self._verbose = verbose
        self._texture_info: Dict[int, TextureUsageInfo] = {}
        
    def log(self, msg: str):
        if self._verbose:
            print(f"[TextureUsageAnalyzer] {msg}")
    
    def analyze(self) -> TextureUsageAnalysis:
        """
        执行纹理使用分析
        
        Returns:
            TextureUsageAnalysis 分析结果
        """
        # 1. 收集所有纹理
        self._collect_textures()
        
        # 2. 遍历所有绘制调用，统计纹理使用
        self._analyze_draw_calls()
        
        # 3. 生成分析报告
        return self._generate_report()
    
    def _collect_textures(self):
        """收集所有纹理信息"""
        textures = self._controller.GetTextures()
        self.log(f"Collecting {len(textures)} textures...")
        
        # 获取资源名称映射
        name_map = {}
        try:
            resources = self._controller.GetResources()
            for r in resources:
                name_map[int(r.resourceId)] = r.name
        except:
            pass
        
        for tex in textures:
            if tex.resourceId == rd.ResourceId.Null():
                continue
            
            res_id = int(tex.resourceId)
            self._texture_info[res_id] = TextureUsageInfo(
                resource_id=res_id,
                name=name_map.get(res_id, ""),
                width=tex.width,
                height=tex.height,
                format=tex.format.Name(),
            )
        
        self.log(f"  Found {len(self._texture_info)} valid textures")
    
    def _analyze_draw_calls(self):
        """遍历所有绘制调用，分析纹理使用"""
        actions = self._controller.GetRootActions()
        
        draw_count = 0
        event_count = 0
        
        def process_action(action):
            nonlocal draw_count, event_count
            event_count += 1
            
            # 只分析有实际绘制操作的事件
            flags = action.flags
            is_draw = bool(flags & (rd.ActionFlags.Drawcall | rd.ActionFlags.Dispatch))
            
            if is_draw:
                draw_count += 1
                self._analyze_event(action.eventId)
            
            # 递归处理子事件
            for child in action.children:
                process_action(child)
        
        self.log("Analyzing draw calls...")
        for action in actions:
            process_action(action)
        
        self.log(f"  Processed {event_count} events, {draw_count} draw calls")
    
    def _analyze_event(self, event_id: int):
        """分析单个事件中使用的纹理"""
        try:
            # 切换到该事件
            self._controller.SetFrameEvent(event_id, False)
            
            # 获取管线状态
            pipe = self._controller.GetPipelineState()
            if not pipe.IsCaptureLoaded():
                return
            
            # 收集所有使用的纹理资源
            used_textures: Set[int] = set()
            
            # 1. 检查着色器只读资源 (SRV)
            for stage in [rd.ShaderStage.Vertex, rd.ShaderStage.Pixel, 
                         rd.ShaderStage.Geometry, rd.ShaderStage.Hull, 
                         rd.ShaderStage.Domain, rd.ShaderStage.Compute]:
                try:
                    resources = pipe.GetReadOnlyResources(stage, True)
                    for used_desc in resources:
                        res_id = int(used_desc.descriptor.resource)
                        if res_id in self._texture_info:
                            used_textures.add(res_id)
                            self._texture_info[res_id].as_shader_resource += 1
                except:
                    pass
            
            # 2. 检查渲染目标 (RTV)
            try:
                render_targets = pipe.GetOutputTargets()
                for desc in render_targets:
                    res_id = int(desc.resource)
                    if res_id in self._texture_info:
                        used_textures.add(res_id)
                        self._texture_info[res_id].as_render_target += 1
            except:
                pass
            
            # 3. 检查深度目标 (DSV)
            try:
                depth = pipe.GetDepthTarget()
                res_id = int(depth.resource)
                if res_id in self._texture_info:
                    used_textures.add(res_id)
                    self._texture_info[res_id].as_depth_target += 1
            except:
                pass
            
            # 4. 检查 UAV 资源
            for stage in [rd.ShaderStage.Pixel, rd.ShaderStage.Compute]:
                try:
                    uavs = pipe.GetReadWriteResources(stage, True)
                    for used_desc in uavs:
                        res_id = int(used_desc.descriptor.resource)
                        if res_id in self._texture_info:
                            used_textures.add(res_id)
                            self._texture_info[res_id].as_uav += 1
                except:
                    pass
            
            # 更新使用计数
            for res_id in used_textures:
                info = self._texture_info[res_id]
                info.use_count += 1
                if len(info.used_in_events) < 100:  # 限制记录数量
                    info.used_in_events.append(event_id)
            
        except Exception as e:
            # 静默忽略错误，继续分析
            pass
    
    def _generate_report(self) -> TextureUsageAnalysis:
        """生成分析报告"""
        result = TextureUsageAnalysis()
        result.total_textures = len(self._texture_info)
        result.all_usage = self._texture_info
        
        # 分类
        unused = []
        used = []
        
        for res_id, info in self._texture_info.items():
            if info.use_count == 0:
                unused.append(info)
            else:
                used.append(info)
        
        result.used_textures = len(used)
        result.unused_textures = len(unused)
        result.unused_list = unused
        
        # 排序：按使用次数降序
        used.sort(key=lambda x: x.use_count, reverse=True)
        
        # 热点纹理 (Top 10)
        result.hot_list = used[:10]
        
        # 低频纹理 (使用 1-3 次)
        result.cold_list = [t for t in used if 1 <= t.use_count <= 3]
        
        # 统计绘制调用数（取最大事件ID作为近似值）
        max_event = 0
        for info in used:
            if info.used_in_events:
                max_event = max(max_event, max(info.used_in_events))
        result.total_draw_calls = max_event
        
        self.log(f"Analysis complete:")
        self.log(f"  Total textures: {result.total_textures}")
        self.log(f"  Used: {result.used_textures}, Unused: {result.unused_textures}")
        if result.hot_list:
            self.log(f"  Most used: {result.hot_list[0].name or result.hot_list[0].resource_id} ({result.hot_list[0].use_count} times)")
        
        return result


def analyze_texture_usage(controller: 'rd.ReplayController', verbose: bool = True) -> Optional[dict]:
    """
    便捷函数：分析纹理使用情况
    
    Args:
        controller: RenderDoc ReplayController
        verbose: 是否输出日志
        
    Returns:
        分析结果字典，失败返回 None
    """
    if not HAS_RENDERDOC:
        print("[ERROR] renderdoc module not available")
        return None
    
    try:
        analyzer = TextureUsageAnalyzer(controller, verbose)
        result = analyzer.analyze()
        return result.to_dict()
    except Exception as e:
        print(f"[ERROR] Texture usage analysis failed: {e}")
        import traceback
        traceback.print_exc()
        return None

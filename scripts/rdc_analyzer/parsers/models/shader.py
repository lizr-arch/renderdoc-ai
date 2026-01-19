"""
Shader 数据模型
===============

包含 SPIR-V Shader 信息的数据类。

从 rdc_parser.py 提取。
"""

import struct
from dataclasses import dataclass, field
from typing import List, Optional, TYPE_CHECKING

from ..constants import (
    SPIRV_MAGIC, SPIRV_OP_NAME, SPIRV_OP_ENTRY_POINT,
    SPIRV_EXEC_VERTEX, SPIRV_EXEC_TESSELLATION_CONTROL,
    SPIRV_EXEC_TESSELLATION_EVALUATION, SPIRV_EXEC_GEOMETRY,
    SPIRV_EXEC_FRAGMENT, SPIRV_EXEC_GLCOMPUTE, SPIRV_EXEC_KERNEL,
    SPIRV_EXEC_TASK_NV, SPIRV_EXEC_MESH_NV,
    SPIRV_EXEC_RAY_GENERATION_KHR, SPIRV_EXEC_INTERSECTION_KHR,
    SPIRV_EXEC_ANY_HIT_KHR, SPIRV_EXEC_CLOSEST_HIT_KHR,
    SPIRV_EXEC_MISS_KHR, SPIRV_EXEC_CALLABLE_KHR,
    SPIRV_EXEC_MODEL_NAMES,
)


@dataclass
class ShaderResource:
    """Shader 使用的资源信息
    
    从 SPIR-V 的 OpName 和类型信息中提取的资源描述。
    资源类型通过名称模式推断：
    - Texture: 名称包含 Texture, Image, Map 等
    - Sampler: 名称包含 Sampler
    - Buffer: 名称包含 Buffer, UBO, SSBO 等
    - Uniform: 名称包含 Uniform, Params, Constants 等
    """
    spirv_id: int           # SPIR-V 中的 ID
    name: str               # OpName 定义的名称
    category: str           # 'Texture', 'Sampler', 'Buffer', 'Uniform', 'Other'
    
    @staticmethod
    def classify_name(name: str) -> str:
        """根据名称模式推断资源类型
        
        分类优先级（从高到低）:
        1. 后缀匹配 - 以 'Sampler' 结尾 → Sampler
        2. 排除模式 - 内部类型名等 → Other
        3. 关键词匹配 - Texture/Buffer/Uniform
        """
        if not name:
            return 'Other'
        
        name_lower = name.lower()
        
        # [优先级 1] 后缀精确匹配 - Sampler 后缀
        # 处理如 "Material_Texture2D_0Sampler", "SceneColorSampler" 等
        if name.endswith('Sampler') or name.endswith('_Sampler'):
            return 'Sampler'
        
        # [优先级 2] 排除的模式 - SPIR-V 内部类型名
        exclude_patterns = ['type.', 'in.var.', 'out.var.', '$globals', 'main_']
        if any(p in name_lower for p in exclude_patterns):
            return 'Other'
        
        # [优先级 3a] Texture/Image 模式
        texture_keywords = ['texture', 'image', 'map', 'atlas', 'cubemap', 'render', 
                           'shadow', 'depth', 'stencil', 'color', 'normal', 'specular',
                           'albedo', 'roughness', 'metallic', 'ao', 'emissive',
                           'scene', 'screen', 'gbuffer', 'hdr', 'ldr', 'lut']
        if any(kw in name_lower for kw in texture_keywords):
            return 'Texture'
        
        # [优先级 3b] Buffer 模式
        buffer_keywords = ['buffer', 'ubo', 'ssbo', 'storage', 'instance', 
                          'vertex', 'index', 'indirect', 'data']
        if any(kw in name_lower for kw in buffer_keywords):
            return 'Buffer'
        
        # [优先级 3c] Uniform/Constant 模式
        uniform_keywords = ['uniform', 'constant', 'param', 'setting', 'config',
                           'view', 'primitive', 'material', 'light', 'fog', 
                           'time', 'frame', 'camera', 'transform']
        if any(kw in name_lower for kw in uniform_keywords):
            return 'Uniform'
        
        return 'Other'


@dataclass
class SPIRVEntryPoint:
    """SPIR-V 入口点信息"""
    execution_model: int
    entry_id: int
    name: str
    
    @property
    def stage_name(self) -> str:
        """获取可读的 shader 阶段名称"""
        return SPIRV_EXEC_MODEL_NAMES.get(self.execution_model, f"Unknown({self.execution_model})")
    
    @property
    def short_stage(self) -> str:
        """获取简短的阶段标识 (VS, PS, CS 等)"""
        stage_map = {
            SPIRV_EXEC_VERTEX: "VS",
            SPIRV_EXEC_TESSELLATION_CONTROL: "TCS",
            SPIRV_EXEC_TESSELLATION_EVALUATION: "TES",
            SPIRV_EXEC_GEOMETRY: "GS",
            SPIRV_EXEC_FRAGMENT: "PS",  # 习惯称为 Pixel Shader
            SPIRV_EXEC_GLCOMPUTE: "CS",
            SPIRV_EXEC_KERNEL: "KN",
            SPIRV_EXEC_TASK_NV: "TS",
            SPIRV_EXEC_MESH_NV: "MS",
            SPIRV_EXEC_RAY_GENERATION_KHR: "RG",
            SPIRV_EXEC_INTERSECTION_KHR: "IS",
            SPIRV_EXEC_ANY_HIT_KHR: "AH",
            SPIRV_EXEC_CLOSEST_HIT_KHR: "CH",
            SPIRV_EXEC_MISS_KHR: "MI",
            SPIRV_EXEC_CALLABLE_KHR: "CA",
        }
        return stage_map.get(self.execution_model, "??")


@dataclass
class ShaderInfo:
    """提取的 Shader 信息"""
    resource_id: int
    spirv_data: bytes
    code_size: int
    chunk_offset: int  # 在 FrameCapture 中的偏移
    
    # 可选：解析后的元数据
    _entry_points: Optional[List[SPIRVEntryPoint]] = field(default=None, repr=False)
    _debug_names: Optional[dict] = field(default=None, repr=False)
    
    @property
    def is_valid_spirv(self) -> bool:
        """检查是否是有效的 SPIR-V"""
        if len(self.spirv_data) < 4:
            return False
        magic = struct.unpack('<I', self.spirv_data[:4])[0]
        return magic == SPIRV_MAGIC
    
    @property
    def spirv_version(self) -> str:
        """获取 SPIR-V 版本"""
        if len(self.spirv_data) < 8:
            return "Unknown"
        version = struct.unpack('<I', self.spirv_data[4:8])[0]
        major = (version >> 16) & 0xFF
        minor = (version >> 8) & 0xFF
        return f"{major}.{minor}"
    
    @property
    def entry_points(self) -> List[SPIRVEntryPoint]:
        """获取所有入口点（惰性解析）"""
        if self._entry_points is None:
            self._parse_spirv_metadata()
        return self._entry_points or []
    
    @property
    def primary_entry_point(self) -> Optional[SPIRVEntryPoint]:
        """获取主入口点（通常只有一个）"""
        eps = self.entry_points
        return eps[0] if eps else None
    
    @property
    def entry_name(self) -> str:
        """获取入口点名称（如 main, vs_main 等）"""
        ep = self.primary_entry_point
        return ep.name if ep else "unknown"
    
    @property
    def stage(self) -> str:
        """获取 shader 阶段简称 (VS, PS, CS 等)"""
        ep = self.primary_entry_point
        return ep.short_stage if ep else "??"
    
    @property
    def display_name(self) -> str:
        """获取用于显示的名称，如 "VS:main" 或 "PS:fragment_main" """
        ep = self.primary_entry_point
        if ep:
            return f"{ep.short_stage}:{ep.name}"
        return f"Shader_{self.resource_id:x}"
    
    @property
    def debug_names(self) -> dict:
        """获取所有调试名称（惰性解析）"""
        if self._debug_names is None:
            self._parse_spirv_metadata()
        return self._debug_names or {}
    
    @property
    def friendly_label(self) -> str:
        """
        从 OpName 变量名中选择最有意义的名称作为友好标签。
        
        优先级（按重要性排序）：
        1. UE 渲染管线关键字（如 ReflectionCapture, EyeAdaptation, Shadow 等）
        2. 资源采样器名称（如 SceneColorSampler, InputTexture 等）
        3. Buffer 名称（如 LightDataBuffer 等）
        4. 排除无意义的名称（如 type.*, $Globals, in.var.*, out.var.* 等）
        """
        names = self.debug_names
        if not names:
            return ""
        
        # 重要关键字（UE 渲染管线组件）
        important_keywords = [
            # 光照与阴影
            'Shadow', 'Light', 'Reflection', 'Refraction', 'GI', 'Ambient',
            # 后处理
            'PostProcess', 'Bloom', 'DOF', 'DepthOfField', 'MotionBlur',
            'EyeAdaptation', 'Exposure', 'ToneMap', 'ColorGrad',
            'FXAA', 'TAA', 'SSAO', 'SSR', 'Fog',
            # 渲染阶段
            'BasePass', 'Deferred', 'Forward', 'Translucent', 'Distortion',
            'Velocity', 'PrePass', 'CustomDepth', 'Decal',
            # 资源类型
            'Texture', 'Sampler', 'Buffer', 'Grid', 'Capture',
            # 特效
            'Particle', 'Atmosphere', 'Sky', 'Cloud', 'Water', 'Terrain',
        ]
        
        # 需要排除的无意义前缀
        exclude_prefixes = [
            'type.', '$', 'in.var.', 'out.var.', 'main_', '_',
        ]
        
        # 需要排除的无意义名称
        exclude_names = {
            'Globals', 'View', 'Primitive', 'DrawRectangleParameters',
        }
        
        best_name = ""
        best_score = -1
        
        for target_id, name in names.items():
            # 跳过无意义名称
            if not name or len(name) < 3:
                continue
            if any(name.startswith(prefix) for prefix in exclude_prefixes):
                continue
            if name in exclude_names:
                continue
            
            # 计算重要性分数
            score = 0
            name_lower = name.lower()
            
            for keyword in important_keywords:
                if keyword.lower() in name_lower:
                    score += 10
            
            # 长度适中的名称优先（太短可能无意义，太长可能是路径）
            if 8 <= len(name) <= 40:
                score += 2
            elif 5 <= len(name) < 8:
                score += 1
            
            # 包含大写字母（驼峰命名）更可能是有意义的名称
            if any(c.isupper() for c in name[1:]):
                score += 1
            
            if score > best_score:
                best_score = score
                best_name = name
        
        return best_name
    
    @property
    def all_resources(self) -> List[ShaderResource]:
        """
        获取该 Shader 使用的所有资源列表。
        
        从 OpName 中提取的资源会按名称模式分类为:
        - Texture: 纹理资源
        - Sampler: 采样器
        - Buffer: 缓冲区 (UBO, SSBO 等)
        - Uniform: 统一变量/常量
        - Other: 其他（类型定义、临时变量等）
        
        注意：只返回有意义的资源名称，排除 type.*, in.var.*, out.var.* 等。
        """
        names = self.debug_names
        if not names:
            return []
        
        resources = []
        for spirv_id, name in names.items():
            if not name or len(name) < 3:
                continue
            
            category = ShaderResource.classify_name(name)
            
            # 只返回有意义的资源（排除 Other）
            if category != 'Other':
                resources.append(ShaderResource(
                    spirv_id=spirv_id,
                    name=name,
                    category=category
                ))
        
        # 按类别和名称排序
        category_order = {'Texture': 0, 'Sampler': 1, 'Buffer': 2, 'Uniform': 3}
        resources.sort(key=lambda r: (category_order.get(r.category, 99), r.name))
        
        return resources
    
    @property
    def resource_summary(self) -> dict:
        """
        获取资源使用摘要统计。
        
        返回各类型资源的数量和名称列表，用于快速了解 Shader 的资源需求。
        """
        resources = self.all_resources
        summary = {
            'total': len(resources),
            'by_category': {},
            'texture_count': 0,
            'sampler_count': 0,
            'buffer_count': 0,
            'uniform_count': 0,
        }
        
        for res in resources:
            cat = res.category
            if cat not in summary['by_category']:
                summary['by_category'][cat] = []
            summary['by_category'][cat].append(res.name)
            
            # 计数
            count_key = f"{cat.lower()}_count"
            if count_key in summary:
                summary[count_key] += 1
        
        return summary
    
    def _parse_spirv_metadata(self):
        """解析 SPIR-V 中的元数据（OpName, OpEntryPoint 等）"""
        self._entry_points = []
        self._debug_names = {}
        
        if not self.is_valid_spirv or len(self.spirv_data) < 20:
            return
        
        data = self.spirv_data
        offset = 20  # 跳过 SPIR-V header (5 words)
        
        while offset < len(data) - 4:
            word = struct.unpack_from('<I', data, offset)[0]
            word_count = word >> 16
            opcode = word & 0xFFFF
            
            if word_count == 0:
                break
            
            inst_size = word_count * 4
            if offset + inst_size > len(data):
                break
            
            # OpEntryPoint: 入口点定义
            # 格式: OpEntryPoint <execution_model> <entry_id> "<name>" [interface_ids...]
            if opcode == SPIRV_OP_ENTRY_POINT and word_count >= 4:
                exec_model = struct.unpack_from('<I', data, offset + 4)[0]
                entry_id = struct.unpack_from('<I', data, offset + 8)[0]
                # 名称从 word 3 开始，以 null 终止
                name_start = offset + 12
                name_bytes = data[name_start:offset + inst_size]
                null_idx = name_bytes.find(b'\x00')
                if null_idx >= 0:
                    name = name_bytes[:null_idx].decode('utf-8', errors='replace')
                else:
                    name = name_bytes.decode('utf-8', errors='replace')
                
                self._entry_points.append(SPIRVEntryPoint(
                    execution_model=exec_model,
                    entry_id=entry_id,
                    name=name
                ))
            
            # OpName: 给 ID 命名（用于调试）
            # 格式: OpName <id> "<name>"
            elif opcode == SPIRV_OP_NAME and word_count >= 3:
                target_id = struct.unpack_from('<I', data, offset + 4)[0]
                name_start = offset + 8
                name_bytes = data[name_start:offset + inst_size]
                null_idx = name_bytes.find(b'\x00')
                if null_idx >= 0:
                    name = name_bytes[:null_idx].decode('utf-8', errors='replace')
                else:
                    name = name_bytes.decode('utf-8', errors='replace')
                
                self._debug_names[target_id] = name
            
            offset += inst_size

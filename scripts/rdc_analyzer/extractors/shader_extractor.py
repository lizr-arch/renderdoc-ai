"""
Shader 提取器
=============

封装 RenderDoc 的 Shader 反射 API，提取 Shader 源码、签名和资源绑定信息。

核心 API:
- PipeState.GetShaderReflection(stage) -> ShaderReflection
- PipeState.GetShader(stage) -> ResourceId
- ReplayController.DisassembleShader(pipeline, reflection, target) -> str
- ReplayController.GetDisassemblyTargets(withPipeline) -> List[str]
"""

from dataclasses import dataclass
from typing import List, Dict, Optional, Any, Callable
import hashlib

from ..core.types import (
    ShaderInfo, 
    ShaderSignature, 
    ShaderConstantBlock, 
    ShaderConstant,
    ShaderResource
)


# Shader 阶段枚举映射 (RenderDoc ShaderStage)
SHADER_STAGE_NAMES = {
    0: "Vertex",
    1: "Hull",           # D3D: Hull, GL: TessControl
    2: "Domain",         # D3D: Domain, GL: TessEval  
    3: "Geometry",
    4: "Pixel",          # D3D: Pixel, GL: Fragment
    5: "Compute",
    6: "Task",           # Mesh shader pipeline (D3D12/VK)
    7: "Mesh",           # Mesh shader pipeline (D3D12/VK)
}

SHADER_TYPE_ABBREV = {
    "Vertex": "VS",
    "Hull": "HS",
    "Domain": "DS",
    "Geometry": "GS",
    "Pixel": "PS",
    "Fragment": "PS",  # OpenGL 别名
    "Compute": "CS",
    "Task": "AS",      # Amplification Shader
    "Mesh": "MS",
}

# ShaderEncoding 枚举映射
SHADER_ENCODING_NAMES = {
    0: "Unknown",
    1: "DXBC",
    2: "GLSL",
    3: "SPIRV",
    4: "SPIRVAsm", 
    5: "HLSL",
    6: "DXIL",
    7: "OpenGLAsm",  # GL assembly (ARB_program)
}


@dataclass
class ShaderExtractorResult:
    """Shader 提取结果"""
    shaders: List[ShaderInfo]
    unique_shader_count: int
    # 按阶段分组的 shader 资源 ID
    by_stage: Dict[str, List[str]]  # {"VS": ["0x1234", ...], ...}
    # 提取过程中的警告
    warnings: List[str]


class ShaderExtractor:
    """
    Shader 源码和元数据提取器
    
    使用方法:
    ```python
    extractor = ShaderExtractor(controller)
    
    # 提取当前事件点的所有绑定 Shader
    result = extractor.extract_bound_shaders(pipe_state)
    
    # 提取特定 Shader 的详细信息
    shader_info = extractor.extract_shader_details(pipe_state, ShaderStage.Pixel)
    ```
    """
    
    def __init__(self, controller, rd_module=None):
        """
        初始化 Shader 提取器
        
        Args:
            controller: RenderDoc ReplayController 实例
            rd_module: renderdoc 模块 (可选，用于类型访问)
        """
        self.controller = controller
        self.rd = rd_module
        
        # 缓存已提取的 Shader (避免重复反汇编)
        self._shader_cache: Dict[str, ShaderInfo] = {}
        
        # 可用的反汇编目标
        self._disasm_targets: Optional[List[str]] = None
        
    def get_disassembly_targets(self, with_pipeline: bool = True) -> List[str]:
        """获取可用的反汇编目标列表"""
        if self._disasm_targets is None:
            try:
                self._disasm_targets = list(
                    self.controller.GetDisassemblyTargets(with_pipeline)
                )
            except Exception:
                self._disasm_targets = []
        return self._disasm_targets
    
    def extract_bound_shaders(self, pipe_state) -> ShaderExtractorResult:
        """
        提取当前管线状态中所有绑定的 Shader
        
        Args:
            pipe_state: PipeState 对象 (来自 controller.GetPipelineState())
            
        Returns:
            ShaderExtractorResult 包含所有提取的 Shader 信息
        """
        shaders = []
        by_stage: Dict[str, List[str]] = {}
        warnings = []
        seen_ids = set()
        
        # 遍历所有可能的 Shader 阶段
        for stage_value, stage_name in SHADER_STAGE_NAMES.items():
            try:
                # 尝试获取 ShaderStage 枚举值
                if self.rd is not None:
                    stage_enum = getattr(self.rd.ShaderStage, stage_name, None)
                    if stage_enum is None:
                        continue
                else:
                    stage_enum = stage_value
                
                # 获取 Shader 反射信息
                reflection = pipe_state.GetShaderReflection(stage_enum)
                if reflection is None:
                    continue
                    
                # 获取 Shader 资源 ID
                shader_id = pipe_state.GetShader(stage_enum)
                if shader_id is None or (hasattr(shader_id, 'id') and shader_id.id() == 0):
                    continue
                    
                # 转换为字符串 ID
                str_id = str(shader_id)
                
                # 记录按阶段分组
                abbrev = SHADER_TYPE_ABBREV.get(stage_name, stage_name)
                if abbrev not in by_stage:
                    by_stage[abbrev] = []
                by_stage[abbrev].append(str_id)
                
                # 避免重复提取同一 Shader
                if str_id in seen_ids:
                    continue
                seen_ids.add(str_id)
                
                # 提取详细信息
                shader_info = self._extract_from_reflection(
                    reflection, 
                    stage_name,
                    pipe_state
                )
                shaders.append(shader_info)
                
            except Exception as e:
                warnings.append(f"Failed to extract {stage_name} shader: {e}")
                
        return ShaderExtractorResult(
            shaders=shaders,
            unique_shader_count=len(shaders),
            by_stage=by_stage,
            warnings=warnings
        )
    
    def extract_shader_at_stage(
        self, 
        pipe_state, 
        stage_name: str
    ) -> Optional[ShaderInfo]:
        """
        提取指定阶段的 Shader 详细信息
        
        Args:
            pipe_state: PipeState 对象
            stage_name: 阶段名称 ("Vertex", "Pixel", etc.)
            
        Returns:
            ShaderInfo 或 None
        """
        try:
            # 获取 ShaderStage 枚举
            if self.rd is not None:
                stage_enum = getattr(self.rd.ShaderStage, stage_name, None)
                if stage_enum is None:
                    return None
            else:
                # 反向查找枚举值
                stage_enum = None
                for v, n in SHADER_STAGE_NAMES.items():
                    if n == stage_name:
                        stage_enum = v
                        break
                if stage_enum is None:
                    return None
            
            reflection = pipe_state.GetShaderReflection(stage_enum)
            if reflection is None:
                return None
                
            return self._extract_from_reflection(reflection, stage_name, pipe_state)
            
        except Exception:
            return None
    
    def _extract_from_reflection(
        self, 
        reflection, 
        stage_name: str,
        pipe_state=None
    ) -> ShaderInfo:
        """
        从 ShaderReflection 对象提取 ShaderInfo
        
        Args:
            reflection: RenderDoc ShaderReflection 对象
            stage_name: Shader 阶段名称
            pipe_state: PipeState (用于反汇编)
        """
        # 基本信息
        resource_id = str(reflection.resourceId) if hasattr(reflection, 'resourceId') else ""
        
        # 检查缓存
        if resource_id in self._shader_cache:
            return self._shader_cache[resource_id]
        
        abbrev = SHADER_TYPE_ABBREV.get(stage_name, stage_name)
        
        info = ShaderInfo(
            resource_id=resource_id,
            type=abbrev,
            name=getattr(reflection, 'entryPoint', '') or f"{abbrev}_{resource_id[-8:]}",
            stage=stage_name,
            entry_point=getattr(reflection, 'entryPoint', ''),
        )
        
        # 编码格式
        if hasattr(reflection, 'encoding'):
            enc_val = int(reflection.encoding) if hasattr(reflection.encoding, '__int__') else reflection.encoding
            info.encoding = SHADER_ENCODING_NAMES.get(enc_val, str(enc_val))
        
        # 调试信息
        if hasattr(reflection, 'debugInfo') and reflection.debugInfo:
            debug_info = reflection.debugInfo
            if hasattr(debug_info, 'files') and debug_info.files:
                info.debug_file = str(debug_info.files[0].filename) if debug_info.files else ""
            info.has_debug_info = True
        
        # 工作组大小 (Compute Shader)
        if hasattr(reflection, 'dispatchThreadsDimension'):
            dims = reflection.dispatchThreadsDimension
            info.workgroup_size = [int(dims[0]), int(dims[1]), int(dims[2])]
        
        # 输入签名
        if hasattr(reflection, 'inputSignature'):
            info.input_signature = self._extract_signatures(reflection.inputSignature)
        
        # 输出签名
        if hasattr(reflection, 'outputSignature'):
            info.output_signature = self._extract_signatures(reflection.outputSignature)
        
        # 常量块
        if hasattr(reflection, 'constantBlocks'):
            info.constant_blocks = self._extract_constant_blocks(reflection.constantBlocks)
        
        # 只读资源 (SRV)
        if hasattr(reflection, 'readOnlyResources'):
            info.read_only_resources = self._extract_resources(reflection.readOnlyResources, True)
        
        # 读写资源 (UAV)
        if hasattr(reflection, 'readWriteResources'):
            info.read_write_resources = self._extract_resources(reflection.readWriteResources, False)
        
        # 采样器
        if hasattr(reflection, 'samplers'):
            info.samplers = [str(s.name) for s in reflection.samplers if hasattr(s, 'name')]
        
        # 原始字节和 Hash
        if hasattr(reflection, 'rawBytes') and reflection.rawBytes:
            raw = bytes(reflection.rawBytes)
            info.raw_bytes = raw
            info.hash = hashlib.sha256(raw).hexdigest()[:16]
        
        # 获取反汇编 (ASM)
        info.source_asm = self._get_disassembly(reflection, pipe_state)
        
        # 缓存结果
        self._shader_cache[resource_id] = info
        
        return info
    
    def _extract_signatures(self, sig_list) -> List[ShaderSignature]:
        """提取输入/输出签名列表"""
        signatures = []
        for sig in sig_list:
            signatures.append(ShaderSignature(
                semantic_name=str(getattr(sig, 'semanticName', '')),
                semantic_index=int(getattr(sig, 'semanticIndex', 0)),
                var_name=str(getattr(sig, 'varName', '')),
                register=int(getattr(sig, 'regIndex', 0)),
                system_value=str(getattr(sig, 'systemValue', '')),
                component_type=str(getattr(sig, 'varType', '')),
                component_count=int(getattr(sig, 'compCount', 4)),
                used_mask=int(getattr(sig, 'regChannelMask', 0xF)),
            ))
        return signatures
    
    def _extract_constant_blocks(self, cb_list) -> List[ShaderConstantBlock]:
        """提取常量块列表"""
        blocks = []
        for i, cb in enumerate(cb_list):
            block = ShaderConstantBlock(
                name=str(getattr(cb, 'name', f'CB{i}')),
                slot=i,  # 通常按顺序
                byte_size=int(getattr(cb, 'byteSize', 0)),
            )
            
            # 提取变量
            if hasattr(cb, 'variables'):
                for var in cb.variables:
                    block.variables.append(ShaderConstant(
                        name=str(getattr(var, 'name', '')),
                        type_name=str(getattr(var.type, 'name', '')) if hasattr(var, 'type') else '',
                        byte_offset=int(getattr(var, 'byteOffset', 0)),
                        byte_size=int(getattr(var.type, 'baseByteSize', 0)) if hasattr(var, 'type') else 0,
                        rows=int(getattr(var.type, 'rows', 1)) if hasattr(var, 'type') else 1,
                        columns=int(getattr(var.type, 'columns', 1)) if hasattr(var, 'type') else 1,
                        array_size=int(getattr(var.type, 'arrayByteStride', 0)) if hasattr(var, 'type') else 0,
                    ))
            
            blocks.append(block)
        return blocks
    
    def _extract_resources(self, res_list, is_read_only: bool) -> List[ShaderResource]:
        """提取资源绑定列表"""
        resources = []
        for i, res in enumerate(res_list):
            resources.append(ShaderResource(
                name=str(getattr(res, 'name', f'Resource{i}')),
                slot=i,
                resource_type=str(getattr(res, 'textureType', 'Unknown')) if hasattr(res, 'textureType') else 'Buffer',
                is_read_only=is_read_only,
            ))
        return resources
    
    def _get_disassembly(self, reflection, pipe_state) -> str:
        """
        获取 Shader 反汇编代码
        
        Args:
            reflection: ShaderReflection 对象
            pipe_state: PipeState 对象 (用于获取 pipeline ID)
            
        Returns:
            反汇编字符串，失败返回空字符串
        """
        if self.controller is None:
            return ""
            
        try:
            # 获取 pipeline ResourceId
            pipeline_id = None
            if pipe_state is not None:
                # 尝试获取 Graphics 或 Compute pipeline
                pipeline_id = pipe_state.GetGraphicsPipelineObject()
                if pipeline_id is None or (hasattr(pipeline_id, 'id') and pipeline_id.id() == 0):
                    pipeline_id = pipe_state.GetComputePipelineObject()
            
            # 使用默认反汇编目标 (第一个，通常是原生格式)
            target = ""
            targets = self.get_disassembly_targets()
            if targets:
                target = targets[0]  # 默认目标
            
            # 调用反汇编 API
            disasm = self.controller.DisassembleShader(
                pipeline_id if pipeline_id else self.rd.ResourceId() if self.rd else None,
                reflection,
                target
            )
            return str(disasm) if disasm else ""
            
        except Exception as e:
            return f"// Disassembly failed: {e}"
    
    def clear_cache(self):
        """清除 Shader 缓存"""
        self._shader_cache.clear()
        self._disasm_targets = None


def create_shader_extractor(controller, rd_module=None) -> ShaderExtractor:
    """
    工厂函数：创建 ShaderExtractor 实例
    
    Args:
        controller: RenderDoc ReplayController
        rd_module: renderdoc 模块 (可选)
        
    Returns:
        配置好的 ShaderExtractor 实例
    """
    return ShaderExtractor(controller, rd_module)

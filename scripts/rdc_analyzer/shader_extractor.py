#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Shader Extractor - 从 ZIP+XML 导出中提取 Shader 源码

从 RenderDoc 的 zip.xml 导出格式中提取 SPIR-V shader，
并使用 spirv-cross 转换为 GLSL 以便显示。

工作流程:
1. 解析 XML 中的 vkCreateShaderModule chunks
2. 从 ZIP 中提取 SPIR-V 二进制数据
3. 使用 spirv-cross 反编译为 GLSL
4. 返回可显示的 shader 源码

使用方法:
    from shader_extractor import ShaderExtractor
    
    extractor = ShaderExtractor(xml_path, zip_path)
    shaders = extractor.extract_shaders(max_count=20)
    # shaders = [{'id': 123, 'stage': 'fragment', 'source': '...', 'glsl': '...'}, ...]
"""

import base64
import io
import logging
import re
import struct
import subprocess
import tempfile
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# SPIR-V Magic number
SPIRV_MAGIC = 0x07230203


@dataclass
class ShaderModuleInfo:
    """Shader 模块信息"""
    resource_id: int
    code_size: int
    buffer_index: int
    stage: str = "unknown"  # vertex, fragment, compute, etc.
    entry_point: str = "main"


@dataclass
class ExtractedShader:
    """提取的 Shader"""
    resource_id: int
    stage: str
    code_size: int
    spirv_data: bytes = field(repr=False)
    glsl_source: str = ""
    spirv_disasm: str = ""
    error: str = ""
    
    @property
    def has_glsl(self) -> bool:
        return bool(self.glsl_source)
    
    @property
    def display_source(self) -> str:
        """返回用于显示的源码（优先 GLSL，降级到 SPIR-V 反汇编）"""
        return self.glsl_source or self.spirv_disasm or f"// Binary SPIR-V ({self.code_size} bytes)"


class ShaderExtractor:
    """
    从 ZIP+XML 导出中提取 Shader
    """
    
    def __init__(self, xml_path: Path, zip_path: Optional[Path] = None):
        """
        初始化提取器
        
        Args:
            xml_path: XML 文件路径
            zip_path: ZIP 文件路径（如果未指定，自动推断）
        """
        self.xml_path = Path(xml_path)
        
        # 推断 ZIP 路径
        if zip_path:
            self.zip_path = Path(zip_path)
        else:
            self.zip_path = self._find_zip_path()
        
        self.shader_modules: Dict[int, ShaderModuleInfo] = {}
        self._parsed = False
        
        # 检测 spirv-cross
        self.spirv_cross_path = self._find_spirv_cross()
    
    def _find_zip_path(self) -> Path:
        """推断 ZIP 文件路径"""
        candidates = [
            self.xml_path.parent / self.xml_path.name.replace('.xml', ''),
            self.xml_path.with_suffix('.zip'),
            self.xml_path.with_suffix(''),
        ]
        for candidate in candidates:
            if candidate.exists():
                return candidate
        return candidates[0]
    
    def _find_spirv_cross(self) -> Optional[str]:
        """查找 spirv-cross 可执行文件"""
        import shutil
        import glob
        
        # 检查 PATH
        path = shutil.which("spirv-cross")
        if path:
            return path
        
        # 搜索 VulkanSDK 和 RenderDoc 内置
        search_paths = [
            r"C:\Program Files\RenderDoc\plugins\spirv\spirv-cross.exe",
            r"D:\Program Files\RenderDoc\plugins\spirv\spirv-cross.exe",
            r"C:\VulkanSDK\*\Bin\spirv-cross.exe",
            r"D:\VulkanSDK\*\Bin\spirv-cross.exe",
            r"D:\Code\tools\spirv-cross\build\Release\spirv-cross.exe",
            "/usr/bin/spirv-cross",
            "/usr/local/bin/spirv-cross",
        ]
        
        for pattern in search_paths:
            matches = glob.glob(pattern)
            if matches:
                return sorted(matches)[-1]  # 最新版本
        
        return None
    
    def is_available(self) -> Tuple[bool, str]:
        """检查提取器是否可用"""
        if not self.xml_path.exists():
            return False, f"XML file not found: {self.xml_path}"
        if not self.zip_path.exists():
            return False, f"ZIP file not found: {self.zip_path}"
        return True, "Ready"
    
    def parse(self) -> bool:
        """解析 XML 文件"""
        if self._parsed:
            return True
        
        available, reason = self.is_available()
        if not available:
            logger.warning(f"ShaderExtractor not available: {reason}")
            return False
        
        logger.info(f"Parsing XML for shaders: {self.xml_path}")
        
        try:
            with open(self.xml_path, 'rb') as f:
                data = f.read()
            
            # 解析 vkCreateShaderModule chunks
            self._parse_shader_modules(data)
            
            # 尝试关联 pipeline 以推断 shader stage
            self._parse_pipelines(data)
            
            self._parsed = True
            logger.info(f"Parsed {len(self.shader_modules)} shader modules")
            return True
            
        except Exception as e:
            logger.error(f"Failed to parse XML: {e}")
            return False
    
    def _parse_shader_modules(self, data: bytes):
        """解析 vkCreateShaderModule chunks"""
        pattern = rb'<chunk[^>]+name="vkCreateShaderModule"[^>]*>(.*?)</chunk>'
        
        for match in re.finditer(pattern, data, re.DOTALL):
            chunk = match.group(1)
            
            # 提取 ShaderModule ResourceId
            id_match = re.search(rb'<ResourceId[^>]+name="ShaderModule"[^>]*>(\d+)</ResourceId>', chunk)
            if not id_match:
                continue
            resource_id = int(id_match.group(1))
            
            # 提取 codeSize
            size_match = re.search(rb'<uint[^>]+name="codeSize"[^>]*>(\d+)</uint>', chunk)
            code_size = int(size_match.group(1)) if size_match else 0
            
            # 提取 buffer index (pCode)
            buffer_match = re.search(rb'<buffer[^>]+name="pCode"[^>]*>(\d+)</buffer>', chunk)
            buffer_index = int(buffer_match.group(1)) if buffer_match else -1
            
            if buffer_index >= 0 and code_size > 0:
                self.shader_modules[resource_id] = ShaderModuleInfo(
                    resource_id=resource_id,
                    code_size=code_size,
                    buffer_index=buffer_index,
                )
    
    def _parse_pipelines(self, data: bytes):
        """解析 pipeline 创建以推断 shader stage"""
        # Graphics pipelines
        pattern = rb'<chunk[^>]+name="vkCreateGraphicsPipelines"[^>]*>(.*?)</chunk>'
        
        for match in re.finditer(pattern, data, re.DOTALL):
            chunk = match.group(1)
            
            # 查找 shader stages
            stages = [
                (rb'VK_SHADER_STAGE_VERTEX_BIT', 'vertex'),
                (rb'VK_SHADER_STAGE_FRAGMENT_BIT', 'fragment'),
                (rb'VK_SHADER_STAGE_GEOMETRY_BIT', 'geometry'),
                (rb'VK_SHADER_STAGE_TESSELLATION_CONTROL_BIT', 'tesscontrol'),
                (rb'VK_SHADER_STAGE_TESSELLATION_EVALUATION_BIT', 'tesseval'),
            ]
            
            # 简单的关联：找到 stage 后查找其对应的 module
            for stage_pattern, stage_name in stages:
                # 查找包含该 stage 的 PipelineShaderStageCreateInfo
                stage_start = chunk.find(stage_pattern)
                if stage_start == -1:
                    continue
                
                # 在该 stage 附近查找 module ResourceId
                # 搜索范围：stage_start 前后 2000 字节
                search_start = max(0, stage_start - 500)
                search_end = min(len(chunk), stage_start + 500)
                search_region = chunk[search_start:search_end]
                
                module_match = re.search(rb'<ResourceId[^>]+name="module"[^>]*>(\d+)</ResourceId>', search_region)
                if module_match:
                    module_id = int(module_match.group(1))
                    if module_id in self.shader_modules:
                        self.shader_modules[module_id].stage = stage_name
        
        # Compute pipelines
        pattern = rb'<chunk[^>]+name="vkCreateComputePipelines"[^>]*>(.*?)</chunk>'
        
        for match in re.finditer(pattern, data, re.DOTALL):
            chunk = match.group(1)
            
            # 查找 compute shader module
            module_match = re.search(rb'<ResourceId[^>]+name="module"[^>]*>(\d+)</ResourceId>', chunk)
            if module_match:
                module_id = int(module_match.group(1))
                if module_id in self.shader_modules:
                    self.shader_modules[module_id].stage = 'compute'
    
    def extract_spirv(self, shader_info: ShaderModuleInfo) -> Optional[bytes]:
        """从 ZIP 中提取 SPIR-V 数据"""
        buffer_name = f"{shader_info.buffer_index:06d}"
        
        try:
            with zipfile.ZipFile(self.zip_path, 'r') as zf:
                data = zf.read(buffer_name)
                
                # 验证 SPIR-V magic
                if len(data) >= 4:
                    magic = struct.unpack('<I', data[:4])[0]
                    if magic == SPIRV_MAGIC:
                        return data
                    else:
                        logger.warning(f"Buffer {buffer_name} is not valid SPIR-V (magic: {hex(magic)})")
                
                return data  # 返回原始数据，可能需要进一步处理
                
        except Exception as e:
            logger.error(f"Failed to read buffer {buffer_name}: {e}")
            return None
    
    def spirv_to_glsl(self, spirv_data: bytes, stage: str) -> Tuple[str, str]:
        """
        使用 spirv-cross 将 SPIR-V 转换为 GLSL
        
        Returns:
            (glsl_source, error_message)
        """
        if not self.spirv_cross_path:
            return "", "spirv-cross not found"
        
        # 写入临时文件
        with tempfile.NamedTemporaryFile(suffix='.spv', delete=False) as f:
            f.write(spirv_data)
            spv_path = f.name
        
        try:
            # 运行 spirv-cross
            cmd = [
                self.spirv_cross_path,
                spv_path,
                "--version", "310",  # GLSL ES 3.10
                "--es",
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                return result.stdout, ""
            else:
                return "", result.stderr
                
        except subprocess.TimeoutExpired:
            return "", "spirv-cross timed out"
        except Exception as e:
            return "", str(e)
        finally:
            try:
                Path(spv_path).unlink()
            except:
                pass
    
    def spirv_disassemble(self, spirv_data: bytes) -> str:
        """生成 SPIR-V 的简单反汇编表示"""
        lines = [
            "; SPIR-V Binary",
            f"; Size: {len(spirv_data)} bytes",
            "",
        ]
        
        if len(spirv_data) < 20:
            lines.append("; Too small for valid SPIR-V")
            return "\n".join(lines)
        
        # 解析 header
        magic, version, generator, bound, schema = struct.unpack('<5I', spirv_data[:20])
        
        lines.append(f"; Magic: {hex(magic)}")
        lines.append(f"; Version: {(version >> 16) & 0xFF}.{(version >> 8) & 0xFF}")
        lines.append(f"; Generator: {hex(generator)}")
        lines.append(f"; Bound: {bound}")
        lines.append("")
        
        # 简单的指令计数
        offset = 20
        instruction_count = 0
        opcodes = {}
        
        while offset < len(spirv_data) - 4:
            word = struct.unpack_from('<I', spirv_data, offset)[0]
            word_count = word >> 16
            opcode = word & 0xFFFF
            
            if word_count == 0:
                break
            
            instruction_count += 1
            opcodes[opcode] = opcodes.get(opcode, 0) + 1
            
            offset += word_count * 4
        
        lines.append(f"; Total Instructions: {instruction_count}")
        lines.append(f"; Unique Opcodes: {len(opcodes)}")
        
        return "\n".join(lines)
    
    def extract_shaders(
        self,
        max_count: int = 20,
        convert_to_glsl: bool = True
    ) -> List[ExtractedShader]:
        """
        提取 shader 并转换为 GLSL
        
        Args:
            max_count: 最多提取多少个 shader
            convert_to_glsl: 是否转换为 GLSL
        
        Returns:
            [ExtractedShader, ...]
        """
        available, reason = self.is_available()
        if not available:
            logger.warning(f"Cannot extract shaders: {reason}")
            return []
        
        if not self._parsed:
            if not self.parse():
                return []
        
        # 按 stage 排序（vertex, fragment 优先）
        stage_priority = {'vertex': 0, 'fragment': 1, 'compute': 2}
        sorted_modules = sorted(
            self.shader_modules.values(),
            key=lambda m: (stage_priority.get(m.stage, 99), m.resource_id)
        )
        
        results = []
        for module in sorted_modules[:max_count]:
            # 提取 SPIR-V
            spirv_data = self.extract_spirv(module)
            if not spirv_data:
                continue
            
            shader = ExtractedShader(
                resource_id=module.resource_id,
                stage=module.stage,
                code_size=len(spirv_data),
                spirv_data=spirv_data,
            )
            
            # 生成 SPIR-V 反汇编
            shader.spirv_disasm = self.spirv_disassemble(spirv_data)
            
            # 转换为 GLSL
            if convert_to_glsl and self.spirv_cross_path:
                glsl, error = self.spirv_to_glsl(spirv_data, module.stage)
                if glsl:
                    shader.glsl_source = glsl
                else:
                    shader.error = error
            elif not self.spirv_cross_path:
                shader.error = "spirv-cross not available"
            
            results.append(shader)
            
            status = "✓ GLSL" if shader.has_glsl else "○ SPIR-V only"
            logger.debug(f"  {status} ID={module.resource_id} stage={module.stage} size={len(spirv_data)}")
        
        glsl_count = sum(1 for s in results if s.has_glsl)
        logger.info(f"Extracted {len(results)} shaders ({glsl_count} with GLSL)")
        
        return results


def extract_shaders_for_report(
    xml_path: Path,
    max_count: int = 20
) -> Dict[int, dict]:
    """
    便捷函数: 为报告生成提取 shader
    
    Args:
        xml_path: XML 文件路径
        max_count: 最多提取多少个
    
    Returns:
        {resource_id: {'stage': '...', 'source': '...', 'glsl': '...'}, ...}
    """
    extractor = ShaderExtractor(xml_path)
    
    available, reason = extractor.is_available()
    if not available:
        logger.info(f"Shader extraction disabled: {reason}")
        return {}
    
    shaders = extractor.extract_shaders(max_count=max_count)
    
    return {
        s.resource_id: {
            'stage': s.stage,
            'source': s.display_source,
            'glsl': s.glsl_source,
            'spirv_size': s.code_size,
            'has_glsl': s.has_glsl,
            'error': s.error,
        }
        for s in shaders
    }


if __name__ == '__main__':
    import sys
    
    logging.basicConfig(level=logging.DEBUG)
    
    if len(sys.argv) < 2:
        print("Usage: py -3 shader_extractor.py <xml_file> [--test]")
        sys.exit(1)
    
    xml_path = Path(sys.argv[1])
    
    extractor = ShaderExtractor(xml_path)
    available, reason = extractor.is_available()
    print(f"Available: {available} - {reason}")
    print(f"spirv-cross: {extractor.spirv_cross_path or 'not found'}")
    
    if available and '--test' in sys.argv:
        shaders = extractor.extract_shaders(max_count=5)
        for s in shaders:
            status = "✓" if s.has_glsl else "○"
            print(f"  {status} ID={s.resource_id} stage={s.stage} size={s.code_size}")
            if s.has_glsl:
                preview = s.glsl_source[:200].replace('\n', '\\n')
                print(f"      GLSL preview: {preview}...")
            if s.error:
                print(f"      Error: {s.error}")

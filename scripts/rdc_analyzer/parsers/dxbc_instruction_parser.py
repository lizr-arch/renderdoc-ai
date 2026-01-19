#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DXBC 指令解析器
===============

解析 DXBC 反汇编指令，分类统计各类操作，用于生成更精确的 GLSL Stub。

Mali GPU 执行单元映射:
- FMA (Fused Multiply-Add): 标量/矢量乘加运算
- CVT (Convert): 类型转换、数据移动
- SFU (Special Function Unit): sin/cos/rsqrt/log/exp 等超越函数
- LS (Load/Store): 内存读写
- Varying: 插值器操作
- Texture: 纹理采样

参考:
- https://docs.microsoft.com/en-us/windows/win32/direct3dhlsl/dx-graphics-hlsl-sm5-asm
- Mali Valhall 架构白皮书
"""

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from enum import Enum, auto


class InstructionCategory(Enum):
    """指令类别（映射到 Mali 执行单元）"""
    FMA = "fma"           # 算术运算 (FMA 单元)
    CVT = "cvt"           # 转换/移动 (CVT 单元)
    SFU = "sfu"           # 特殊函数 (SFU 单元)
    TEXTURE = "texture"   # 纹理采样
    LOAD_STORE = "ls"     # 内存加载/存储
    VARYING = "varying"   # 插值器
    CONTROL = "control"   # 控制流
    COMPARE = "compare"   # 比较操作
    BITWISE = "bitwise"   # 位运算
    DECLARATION = "decl"  # 声明（不计入执行）
    UNKNOWN = "unknown"


# DXBC 指令到 Mali 单元的映射表
INSTRUCTION_MAP: Dict[str, InstructionCategory] = {
    # ========== FMA 类 (算术运算) ==========
    # 基础算术
    "add": InstructionCategory.FMA,
    "iadd": InstructionCategory.FMA,
    "mul": InstructionCategory.FMA,
    "imul": InstructionCategory.FMA,
    "umul": InstructionCategory.FMA,
    "mad": InstructionCategory.FMA,      # multiply-add
    "imad": InstructionCategory.FMA,
    "umad": InstructionCategory.FMA,
    "div": InstructionCategory.FMA,
    "idiv": InstructionCategory.FMA,
    "udiv": InstructionCategory.FMA,
    
    # 点积
    "dp2": InstructionCategory.FMA,
    "dp3": InstructionCategory.FMA,
    "dp4": InstructionCategory.FMA,
    
    # min/max/abs
    "min": InstructionCategory.FMA,
    "imin": InstructionCategory.FMA,
    "umin": InstructionCategory.FMA,
    "max": InstructionCategory.FMA,
    "imax": InstructionCategory.FMA,
    "umax": InstructionCategory.FMA,
    
    # 线性插值
    "lrp": InstructionCategory.FMA,  # lerp
    
    # 取反/绝对值（通常通过修饰符实现，但也可能是独立指令）
    "neg": InstructionCategory.FMA,
    
    # ========== CVT 类 (类型转换/数据移动) ==========
    "mov": InstructionCategory.CVT,
    "movc": InstructionCategory.CVT,     # conditional move
    "swapc": InstructionCategory.CVT,
    
    # 类型转换
    "ftoi": InstructionCategory.CVT,     # float to int
    "ftou": InstructionCategory.CVT,     # float to uint
    "itof": InstructionCategory.CVT,     # int to float
    "utof": InstructionCategory.CVT,     # uint to float
    "f16tof32": InstructionCategory.CVT,
    "f32tof16": InstructionCategory.CVT,
    "dtof": InstructionCategory.CVT,     # double to float
    "ftod": InstructionCategory.CVT,     # float to double
    
    # 打包/解包
    "bfi": InstructionCategory.CVT,      # bit field insert
    "bfrev": InstructionCategory.CVT,    # bit field reverse
    "countbits": InstructionCategory.CVT,
    "firstbit_hi": InstructionCategory.CVT,
    "firstbit_lo": InstructionCategory.CVT,
    "firstbit_shi": InstructionCategory.CVT,
    
    # ========== SFU 类 (超越函数) ==========
    "sqrt": InstructionCategory.SFU,
    "rsq": InstructionCategory.SFU,      # 1/sqrt(x)
    "rcp": InstructionCategory.SFU,      # 1/x
    "log": InstructionCategory.SFU,
    "exp": InstructionCategory.SFU,
    "sincos": InstructionCategory.SFU,   # 同时计算 sin 和 cos
    
    # 导数（用于 mipmap 选择，在 Mali 上走 SFU）
    "deriv_rtx": InstructionCategory.SFU,
    "deriv_rtx_coarse": InstructionCategory.SFU,
    "deriv_rtx_fine": InstructionCategory.SFU,
    "deriv_rty": InstructionCategory.SFU,
    "deriv_rty_coarse": InstructionCategory.SFU,
    "deriv_rty_fine": InstructionCategory.SFU,
    
    # ========== 纹理采样 ==========
    "sample": InstructionCategory.TEXTURE,
    "sample_b": InstructionCategory.TEXTURE,    # with bias
    "sample_c": InstructionCategory.TEXTURE,    # comparison (shadow)
    "sample_c_lz": InstructionCategory.TEXTURE,
    "sample_d": InstructionCategory.TEXTURE,    # with derivatives
    "sample_l": InstructionCategory.TEXTURE,    # with LOD
    "sample_indexable": InstructionCategory.TEXTURE,
    "gather4": InstructionCategory.TEXTURE,
    "gather4_c": InstructionCategory.TEXTURE,
    "gather4_po": InstructionCategory.TEXTURE,
    "gather4_po_c": InstructionCategory.TEXTURE,
    "resinfo": InstructionCategory.TEXTURE,     # get texture info
    "sample_info": InstructionCategory.TEXTURE,
    
    # ========== Load/Store ==========
    "ld": InstructionCategory.LOAD_STORE,
    "ld_indexable": InstructionCategory.LOAD_STORE,
    "ld_structured": InstructionCategory.LOAD_STORE,
    "ld_raw": InstructionCategory.LOAD_STORE,
    "ld_uav_typed": InstructionCategory.LOAD_STORE,
    "store": InstructionCategory.LOAD_STORE,
    "store_structured": InstructionCategory.LOAD_STORE,
    "store_raw": InstructionCategory.LOAD_STORE,
    "store_uav_typed": InstructionCategory.LOAD_STORE,
    
    # 原子操作
    "atomic_iadd": InstructionCategory.LOAD_STORE,
    "atomic_and": InstructionCategory.LOAD_STORE,
    "atomic_or": InstructionCategory.LOAD_STORE,
    "atomic_xor": InstructionCategory.LOAD_STORE,
    "atomic_imin": InstructionCategory.LOAD_STORE,
    "atomic_imax": InstructionCategory.LOAD_STORE,
    "atomic_umin": InstructionCategory.LOAD_STORE,
    "atomic_umax": InstructionCategory.LOAD_STORE,
    "atomic_cmp_store": InstructionCategory.LOAD_STORE,
    
    # ========== 比较操作 ==========
    "lt": InstructionCategory.COMPARE,
    "ult": InstructionCategory.COMPARE,
    "ge": InstructionCategory.COMPARE,
    "uge": InstructionCategory.COMPARE,
    "eq": InstructionCategory.COMPARE,
    "ieq": InstructionCategory.COMPARE,
    "ne": InstructionCategory.COMPARE,
    "ine": InstructionCategory.COMPARE,
    
    # ========== 位运算 ==========
    "and": InstructionCategory.BITWISE,
    "or": InstructionCategory.BITWISE,
    "xor": InstructionCategory.BITWISE,
    "not": InstructionCategory.BITWISE,
    "ishl": InstructionCategory.BITWISE,
    "ishr": InstructionCategory.BITWISE,
    "ushr": InstructionCategory.BITWISE,
    
    # ========== 控制流 ==========
    "if_z": InstructionCategory.CONTROL,
    "if_nz": InstructionCategory.CONTROL,
    "else": InstructionCategory.CONTROL,
    "endif": InstructionCategory.CONTROL,
    "loop": InstructionCategory.CONTROL,
    "endloop": InstructionCategory.CONTROL,
    "break": InstructionCategory.CONTROL,
    "breakc_z": InstructionCategory.CONTROL,
    "breakc_nz": InstructionCategory.CONTROL,
    "continue": InstructionCategory.CONTROL,
    "continuec_z": InstructionCategory.CONTROL,
    "continuec_nz": InstructionCategory.CONTROL,
    "switch": InstructionCategory.CONTROL,
    "case": InstructionCategory.CONTROL,
    "default": InstructionCategory.CONTROL,
    "endswitch": InstructionCategory.CONTROL,
    "ret": InstructionCategory.CONTROL,
    "retc_z": InstructionCategory.CONTROL,
    "retc_nz": InstructionCategory.CONTROL,
    "call": InstructionCategory.CONTROL,
    "callc_z": InstructionCategory.CONTROL,
    "callc_nz": InstructionCategory.CONTROL,
    "discard_z": InstructionCategory.CONTROL,
    "discard_nz": InstructionCategory.CONTROL,
    
    # ========== 声明 (不计入执行周期) ==========
    "dcl_temps": InstructionCategory.DECLARATION,
    "dcl_input": InstructionCategory.DECLARATION,
    "dcl_input_ps": InstructionCategory.DECLARATION,
    "dcl_input_ps_sgv": InstructionCategory.DECLARATION,
    "dcl_input_ps_siv": InstructionCategory.DECLARATION,
    "dcl_output": InstructionCategory.DECLARATION,
    "dcl_output_sgv": InstructionCategory.DECLARATION,
    "dcl_output_siv": InstructionCategory.DECLARATION,
    "dcl_resource": InstructionCategory.DECLARATION,
    "dcl_resource_texture2d": InstructionCategory.DECLARATION,
    "dcl_resource_texturecube": InstructionCategory.DECLARATION,
    "dcl_sampler": InstructionCategory.DECLARATION,
    "dcl_constantbuffer": InstructionCategory.DECLARATION,
    "dcl_globalFlags": InstructionCategory.DECLARATION,
    "dcl_immediateConstantBuffer": InstructionCategory.DECLARATION,
    "dcl_indexableTemp": InstructionCategory.DECLARATION,
    "dcl_uav_typed": InstructionCategory.DECLARATION,
    "dcl_uav_structured": InstructionCategory.DECLARATION,
    "dcl_uav_raw": InstructionCategory.DECLARATION,
    "dcl_tgsm_structured": InstructionCategory.DECLARATION,
    "dcl_tgsm_raw": InstructionCategory.DECLARATION,
    "dcl_thread_group": InstructionCategory.DECLARATION,
    "dcl_tessellator_domain": InstructionCategory.DECLARATION,
    "dcl_tessellator_output_primitive": InstructionCategory.DECLARATION,
    "dcl_tessellator_partitioning": InstructionCategory.DECLARATION,
    "dcl_hs_max_tessfactor": InstructionCategory.DECLARATION,
    "dcl_hs_fork_phase_instance_count": InstructionCategory.DECLARATION,
    "dcl_function_body": InstructionCategory.DECLARATION,
    "dcl_function_table": InstructionCategory.DECLARATION,
    "dcl_interface": InstructionCategory.DECLARATION,
}


@dataclass
class DXBCInstruction:
    """单条 DXBC 指令"""
    opcode: str
    category: InstructionCategory
    operands: List[str]
    raw_line: str
    line_number: int
    
    # 操作数分析
    dest_register: Optional[str] = None
    src_registers: List[str] = field(default_factory=list)
    swizzle: Optional[str] = None
    saturate: bool = False


@dataclass
class DXBCAnalysisResult:
    """DXBC 分析结果"""
    # 基本信息
    shader_model: str = ""
    shader_type: str = ""  # "vs", "ps", "cs", etc.
    
    # 寄存器使用
    temp_registers: int = 0
    input_count: int = 0
    output_count: int = 0
    cbuffer_count: int = 0
    texture_count: int = 0
    sampler_count: int = 0
    uav_count: int = 0
    
    # 指令统计
    total_instructions: int = 0
    category_counts: Dict[str, int] = field(default_factory=dict)
    opcode_counts: Dict[str, int] = field(default_factory=dict)
    
    # 详细指令列表
    instructions: List[DXBCInstruction] = field(default_factory=list)
    
    # 控制流分析
    has_branching: bool = False
    has_loops: bool = False
    loop_depth: int = 0
    branch_depth: int = 0
    
    # 特殊标记
    has_derivatives: bool = False
    has_discard: bool = False
    uses_gather: bool = False
    
    def get_mali_cycle_estimate(self) -> Dict[str, float]:
        """
        估算 Mali GPU 各单元的周期数
        
        注意：这是一个粗略估计，实际周期取决于：
        - 具体 GPU 型号的管线配置
        - 数据依赖和管线停顿
        - 工作组大小和占用率
        """
        cycles = {
            "arith_fma": 0.0,
            "arith_cvt": 0.0,
            "arith_sfu": 0.0,
            "load_store": 0.0,
            "texture": 0.0,
            "varying": 0.0,
        }
        
        # 基础周期估算（单指令周期）
        cycles["arith_fma"] = self.category_counts.get("fma", 0)
        cycles["arith_cvt"] = self.category_counts.get("cvt", 0)
        cycles["arith_sfu"] = self.category_counts.get("sfu", 0) * 2  # SFU 通常 2 周期
        cycles["load_store"] = self.category_counts.get("ls", 0) * 4  # LS 较慢
        cycles["texture"] = self.category_counts.get("texture", 0) * 8  # 纹理采样最慢
        
        # 比较和位运算走 FMA
        cycles["arith_fma"] += self.category_counts.get("compare", 0)
        cycles["arith_fma"] += self.category_counts.get("bitwise", 0)
        
        return cycles
    
    def get_bottleneck(self) -> Tuple[str, float]:
        """获取瓶颈单元和周期数"""
        cycles = self.get_mali_cycle_estimate()
        if not cycles:
            return "unknown", 0.0
        
        bottleneck = max(cycles.items(), key=lambda x: x[1])
        return bottleneck


class DXBCInstructionParser:
    """DXBC 反汇编指令解析器"""
    
    # 操作码正则（匹配指令开头）
    OPCODE_PATTERN = re.compile(r'^([a-z_]+(?:_[a-z]+)*)')
    
    # 寄存器正则
    REGISTER_PATTERN = re.compile(r'([rvocstiu]\d+|cb\d+\[\d+\]|icb\[\d+\])')
    
    # 输入声明正则
    INPUT_DECL_PATTERN = re.compile(r'dcl_input(?:_ps)?(?:_sgv|_siv)?\s+v(\d+)')
    
    # 输出声明正则
    OUTPUT_DECL_PATTERN = re.compile(r'dcl_output(?:_sgv|_siv)?\s+o(\d+)')
    
    # 资源声明正则
    RESOURCE_DECL_PATTERN = re.compile(r'dcl_resource_\w+\s+t(\d+)')
    SAMPLER_DECL_PATTERN = re.compile(r'dcl_sampler\s+s(\d+)')
    CBUFFER_DECL_PATTERN = re.compile(r'dcl_constantbuffer\s+cb(\d+)')
    
    # Shader Model 正则
    SHADER_MODEL_PATTERN = re.compile(r'^(vs|ps|cs|gs|hs|ds)_(\d+)_(\d+)')
    
    def __init__(self):
        self.result = DXBCAnalysisResult()
    
    def parse(self, dxbc_source: str) -> DXBCAnalysisResult:
        """
        解析 DXBC 反汇编源码
        
        Args:
            dxbc_source: DXBC 反汇编文本
            
        Returns:
            DXBCAnalysisResult: 解析结果
        """
        self.result = DXBCAnalysisResult()
        
        lines = dxbc_source.strip().split('\n')
        
        current_loop_depth = 0
        current_branch_depth = 0
        
        for line_num, raw_line in enumerate(lines, 1):
            line = raw_line.strip()
            
            # 跳过空行和注释
            if not line or line.startswith(';') or line.startswith('//'):
                continue
            
            # 检查 Shader Model
            sm_match = self.SHADER_MODEL_PATTERN.match(line)
            if sm_match:
                self.result.shader_type = sm_match.group(1)
                self.result.shader_model = line
                continue
            
            # 解析声明
            if line.startswith('dcl_'):
                self._parse_declaration(line)
                continue
            
            # 解析指令
            instruction = self._parse_instruction(line, line_num)
            if instruction:
                self.result.instructions.append(instruction)
                
                # 更新统计
                self.result.total_instructions += 1
                cat_name = instruction.category.value
                self.result.category_counts[cat_name] = \
                    self.result.category_counts.get(cat_name, 0) + 1
                self.result.opcode_counts[instruction.opcode] = \
                    self.result.opcode_counts.get(instruction.opcode, 0) + 1
                
                # 控制流分析
                if instruction.category == InstructionCategory.CONTROL:
                    if instruction.opcode == "loop":
                        current_loop_depth += 1
                        self.result.has_loops = True
                        self.result.loop_depth = max(
                            self.result.loop_depth, current_loop_depth
                        )
                    elif instruction.opcode == "endloop":
                        current_loop_depth = max(0, current_loop_depth - 1)
                    elif instruction.opcode in ("if_z", "if_nz"):
                        current_branch_depth += 1
                        self.result.has_branching = True
                        self.result.branch_depth = max(
                            self.result.branch_depth, current_branch_depth
                        )
                    elif instruction.opcode == "endif":
                        current_branch_depth = max(0, current_branch_depth - 1)
                    elif instruction.opcode in ("discard_z", "discard_nz"):
                        self.result.has_discard = True
                
                # 特殊指令标记
                if instruction.opcode.startswith("deriv_"):
                    self.result.has_derivatives = True
                if instruction.opcode.startswith("gather"):
                    self.result.uses_gather = True
        
        return self.result
    
    def _parse_declaration(self, line: str):
        """解析声明语句"""
        # dcl_temps
        if line.startswith('dcl_temps'):
            match = re.search(r'dcl_temps\s+(\d+)', line)
            if match:
                self.result.temp_registers = int(match.group(1))
        
        # dcl_input
        elif line.startswith('dcl_input'):
            self.result.input_count += 1
        
        # dcl_output
        elif line.startswith('dcl_output'):
            self.result.output_count += 1
        
        # dcl_resource
        elif 'dcl_resource' in line:
            self.result.texture_count += 1
        
        # dcl_sampler
        elif line.startswith('dcl_sampler'):
            self.result.sampler_count += 1
        
        # dcl_constantbuffer
        elif line.startswith('dcl_constantbuffer'):
            self.result.cbuffer_count += 1
        
        # dcl_uav
        elif line.startswith('dcl_uav'):
            self.result.uav_count += 1
    
    def _parse_instruction(
        self, line: str, line_num: int
    ) -> Optional[DXBCInstruction]:
        """解析单条指令"""
        # 提取操作码
        match = self.OPCODE_PATTERN.match(line)
        if not match:
            return None
        
        opcode = match.group(1).lower()
        
        # 处理带修饰符的操作码 (如 add_sat)
        base_opcode = opcode.replace('_sat', '').replace('_nz', '').replace('_z', '')
        
        # 查找类别
        category = INSTRUCTION_MAP.get(base_opcode, InstructionCategory.UNKNOWN)
        
        # 如果是声明，跳过
        if category == InstructionCategory.DECLARATION:
            return None
        
        # 提取操作数
        operands_str = line[match.end():].strip()
        operands = [op.strip() for op in operands_str.split(',') if op.strip()]
        
        # 解析寄存器
        dest_register = None
        src_registers = []
        
        if operands:
            # 第一个操作数通常是目标
            dest_match = self.REGISTER_PATTERN.search(operands[0])
            if dest_match:
                dest_register = dest_match.group(1)
            
            # 后续是源操作数
            for op in operands[1:]:
                reg_match = self.REGISTER_PATTERN.search(op)
                if reg_match:
                    src_registers.append(reg_match.group(1))
        
        return DXBCInstruction(
            opcode=opcode,
            category=category,
            operands=operands,
            raw_line=line,
            line_number=line_num,
            dest_register=dest_register,
            src_registers=src_registers,
            saturate='_sat' in opcode
        )


def analyze_dxbc(source: str) -> DXBCAnalysisResult:
    """
    便捷函数：分析 DXBC 反汇编
    
    Args:
        source: DXBC 反汇编文本
        
    Returns:
        DXBCAnalysisResult: 分析结果
    """
    parser = DXBCInstructionParser()
    return parser.parse(source)


def print_analysis_summary(result: DXBCAnalysisResult):
    """打印分析摘要"""
    print(f"\n=== DXBC Analysis Summary ===")
    print(f"Shader Model: {result.shader_model}")
    print(f"Total Instructions: {result.total_instructions}")
    print(f"Temp Registers: {result.temp_registers}")
    print(f"Inputs: {result.input_count}, Outputs: {result.output_count}")
    print(f"Textures: {result.texture_count}, Samplers: {result.sampler_count}")
    print(f"Constant Buffers: {result.cbuffer_count}")
    
    print(f"\n--- Category Breakdown ---")
    for cat, count in sorted(result.category_counts.items(), key=lambda x: -x[1]):
        print(f"  {cat}: {count}")
    
    print(f"\n--- Mali Cycle Estimate ---")
    cycles = result.get_mali_cycle_estimate()
    for unit, cyc in sorted(cycles.items(), key=lambda x: -x[1]):
        if cyc > 0:
            print(f"  {unit}: {cyc:.1f}")
    
    bottleneck, bottleneck_cycles = result.get_bottleneck()
    print(f"\nBottleneck: {bottleneck} ({bottleneck_cycles:.1f} cycles)")
    
    if result.has_loops:
        print(f"Has Loops: Yes (max depth: {result.loop_depth})")
    if result.has_branching:
        print(f"Has Branching: Yes (max depth: {result.branch_depth})")
    if result.has_discard:
        print(f"Uses Discard: Yes")


# 测试代码
if __name__ == "__main__":
    # 示例 DXBC 反汇编
    test_dxbc = """
ps_5_0
dcl_globalFlags refactoringAllowed
dcl_constantbuffer cb0[4], immediateIndexed
dcl_sampler s0, mode_default
dcl_resource_texture2d (float,float,float,float) t0
dcl_input_ps linear v0.xy
dcl_output o0.xyzw
dcl_temps 4
sample r0.xyzw, v0.xyxx, t0.xyzw, s0
mul r1.xyz, r0.xyzx, cb0[0].xyzx
add r1.xyz, r1.xyzx, cb0[1].xyzx
dp3 r2.x, r1.xyzx, r1.xyzx
rsq r2.x, r2.x
mul r1.xyz, r1.xyzx, r2.xxxx
mad r0.xyz, r0.xyzx, cb0[2].xyzx, r1.xyzx
mov o0.xyz, r0.xyzx
mov o0.w, r0.w
ret
"""
    
    result = analyze_dxbc(test_dxbc)
    print_analysis_summary(result)

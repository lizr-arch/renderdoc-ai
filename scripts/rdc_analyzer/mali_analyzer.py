#!/usr/bin/env python3
"""
Mali Offline Compiler 集成模块

调用 Mali Offline Compiler (malioc) 分析 SPIR-V shader，提取性能指标。

Author: RenderDoc Mali Analyzer Project
Version: 1.0.0
"""

import subprocess
import tempfile
import json
import os
import re
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

REPO_ROOT = Path(__file__).resolve().parents[2]
REPO_MALIOC = REPO_ROOT / "tools" / "malioc" / "2026.0" / "mali_offline_compiler" / "malioc.exe"
DEFAULT_MALIOC_CANDIDATES = [
    str(REPO_MALIOC),
    r"C:\Program Files\Arm\Arm Performance Studio 2026.0\mali_offline_compiler\malioc.exe",
    r"D:\Program Files\Arm\Arm Performance Studio 2025.3\mali_offline_compiler\malioc.exe",
]


def resolve_malioc_path() -> str:
    env_path = os.environ.get("MALIOC_PATH")
    if env_path and Path(env_path).exists():
        return env_path

    for candidate in DEFAULT_MALIOC_CANDIDATES:
        if Path(candidate).exists():
            return candidate

    return DEFAULT_MALIOC_CANDIDATES[0]


@dataclass
class MaliPerformanceMetrics:
    """Mali GPU 性能指标"""
    # 基本信息
    shader_type: str = ""  # vertex, fragment, compute
    gpu_name: str = ""
    driver_version: str = ""
    
    # 工作寄存器
    work_registers: int = 0
    uniform_registers: int = 0
    
    # 指令周期
    total_cycles: float = 0.0
    shortest_path: float = 0.0
    longest_path: float = 0.0
    
    # 算术单元
    fma_cycles: float = 0.0
    cvt_cycles: float = 0.0
    sfu_cycles: float = 0.0
    
    # 加载/存储
    load_store_cycles: float = 0.0
    texture_cycles: float = 0.0
    
    # 变化单元 (仅 Vertex)
    varying_cycles: float = 0.0
    
    # 栈溢出
    has_stack_spilling: bool = False
    spill_count: int = 0
    
    # 原始输出
    raw_output: str = ""
    
    # 解析状态
    parse_success: bool = False
    error_message: str = ""


@dataclass
class ShaderAnalysisResult:
    """Shader 分析结果"""
    shader_index: int
    shader_size: int
    spirv_version: str
    metrics: MaliPerformanceMetrics
    
    @property
    def is_valid(self) -> bool:
        return self.metrics.parse_success
    
    @property
    def performance_score(self) -> float:
        """计算性能评分 (越低越好)"""
        if not self.metrics.parse_success:
            return float('inf')
        
        # 基于总周期和寄存器使用量的简单评分
        cycle_score = self.metrics.longest_path
        register_penalty = max(0, self.metrics.work_registers - 32) * 0.5
        spill_penalty = self.metrics.spill_count * 10
        
        return cycle_score + register_penalty + spill_penalty


class MaliOfflineCompiler:
    """Mali Offline Compiler 包装器"""
    
    def __init__(self, malioc_path: str = None):
        self.malioc_path = malioc_path or resolve_malioc_path()
        self._validate_malioc()
    
    def _validate_malioc(self):
        """验证 malioc 是否可用"""
        if not os.path.exists(self.malioc_path):
            raise FileNotFoundError(f"Mali Offline Compiler not found: {self.malioc_path}")
        
        # 测试运行
        try:
            result = subprocess.run(
                [self.malioc_path, "--version"],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode != 0:
                raise RuntimeError(f"malioc --version failed: {result.stderr}")
            self.version = result.stdout.strip()
        except subprocess.TimeoutExpired:
            raise RuntimeError("malioc --version timed out")
    
    def analyze_spirv(self, spirv_data: bytes, gpu_core: str = "Mali-G715") -> MaliPerformanceMetrics:
        """分析单个 SPIR-V shader
        
        Args:
            spirv_data: SPIR-V 二进制数据
            gpu_core: 目标 GPU 核心名称
            
        Returns:
            MaliPerformanceMetrics: 性能指标
        """
        metrics = MaliPerformanceMetrics()
        
        # 创建临时文件保存 SPIR-V
        with tempfile.NamedTemporaryFile(suffix='.spv', delete=False) as f:
            f.write(spirv_data)
            spv_path = f.name
        
        try:
            # 调用 malioc
            result = subprocess.run(
                [
                    self.malioc_path,
                    "--spirv", spv_path,
                    "--core", gpu_core,
                    "--format", "json"
                ],
                capture_output=True,
                text=True,
                timeout=60
            )
            
            metrics.raw_output = result.stdout + result.stderr
            
            if result.returncode != 0:
                # 尝试文本格式输出
                result_text = subprocess.run(
                    [
                        self.malioc_path,
                        "--spirv", spv_path,
                        "--core", gpu_core
                    ],
                    capture_output=True,
                    text=True,
                    timeout=60
                )
                metrics.raw_output = result_text.stdout + result_text.stderr
                metrics = self._parse_text_output(result_text.stdout, metrics)
            else:
                # 解析 JSON 输出
                metrics = self._parse_json_output(result.stdout, metrics)
            
        except subprocess.TimeoutExpired:
            metrics.error_message = "Analysis timed out"
            metrics.parse_success = False
        except Exception as e:
            metrics.error_message = str(e)
            metrics.parse_success = False
        finally:
            # 清理临时文件
            try:
                os.unlink(spv_path)
            except:
                pass
        
        return metrics
    
    def _parse_json_output(self, output: str, metrics: MaliPerformanceMetrics) -> MaliPerformanceMetrics:
        """解析 JSON 格式输出
        
        malioc v8.7+ JSON 格式结构:
        {
            "shaders": [{
                "shader": {"api": "Vulkan", "type": "Fragment"},
                "hardware": {"core": "Mali-G715", ...},
                "variants": [{
                    "name": "Main",
                    "performance": {
                        "pipelines": ["arith_total", "arith_fma", "arith_cvt", "arith_sfu", "load_store", "texture"],
                        "total_cycles": {"cycle_count": [...], ...},
                        "shortest_path_cycles": {"cycle_count": [...], ...},
                        "longest_path_cycles": {"cycle_count": [...], ...}
                    },
                    "properties": [{"name": "work_registers_used", "value": N}, ...]
                }]
            }]
        }
        """
        try:
            data = json.loads(output)
            
            # 提取 shader 信息
            if "shaders" in data and len(data["shaders"]) > 0:
                shader_data = data["shaders"][0]
                
                # Shader 类型和 GPU
                shader_info = shader_data.get("shader", {})
                metrics.shader_type = shader_info.get("type", "")
                
                hw_info = shader_data.get("hardware", {})
                metrics.gpu_name = hw_info.get("core", "")
                
                # 获取变体 (通常是 "Main")
                variants = shader_data.get("variants", [])
                if variants:
                    variant = variants[0]
                    perf = variant.get("performance", {})
                    
                    # Pipeline 名称索引 (用于解析 cycle_count 数组)
                    pipelines = perf.get("pipelines", [])
                    pipeline_idx = {name: i for i, name in enumerate(pipelines)}
                    
                    # 解析 cycle counts
                    def get_cycles(cycle_data, pipeline_name):
                        """从 cycle_count 数组获取指定 pipeline 的周期数"""
                        if not cycle_data:
                            return 0.0
                        counts = cycle_data.get("cycle_count", [])
                        idx = pipeline_idx.get(pipeline_name, -1)
                        if 0 <= idx < len(counts):
                            return float(counts[idx])
                        return 0.0
                    
                    def safe_max(counts):
                        """安全获取列表最大值，过滤 None"""
                        if not counts:
                            return 0.0
                        valid = [c for c in counts if c is not None]
                        return max(valid) if valid else 0.0
                    
                    # Total cycles (取 load_store 作为代表，或取最大值)
                    total_data = perf.get("total_cycles", {})
                    total_counts = total_data.get("cycle_count", [])
                    metrics.total_cycles = safe_max(total_counts)
                    
                    # Shortest path
                    shortest_data = perf.get("shortest_path_cycles", {})
                    shortest_counts = shortest_data.get("cycle_count", [])
                    metrics.shortest_path = safe_max(shortest_counts)
                    
                    # Longest path
                    longest_data = perf.get("longest_path_cycles", {})
                    longest_counts = longest_data.get("cycle_count", [])
                    metrics.longest_path = safe_max(longest_counts)
                    
                    # 各单元周期 (从 longest_path_cycles 获取)
                    metrics.fma_cycles = get_cycles(longest_data, "arith_fma")
                    metrics.cvt_cycles = get_cycles(longest_data, "arith_cvt")
                    metrics.sfu_cycles = get_cycles(longest_data, "arith_sfu")
                    metrics.load_store_cycles = get_cycles(longest_data, "load_store")
                    metrics.texture_cycles = get_cycles(longest_data, "texture")
                    metrics.varying_cycles = get_cycles(longest_data, "varying")
                    
                    # 从 properties 获取寄存器信息
                    props = variant.get("properties", [])
                    for prop in props:
                        prop_name = prop.get("name", "")
                        prop_value = prop.get("value", 0)
                        
                        if prop_name == "work_registers_used":
                            metrics.work_registers = int(prop_value) if prop_value else 0
                        elif prop_name == "uniform_registers_used":
                            metrics.uniform_registers = int(prop_value) if prop_value else 0
                        elif prop_name == "stack_spill_bytes":
                            if prop_value and int(prop_value) > 0:
                                metrics.has_stack_spilling = True
                                metrics.spill_count = int(prop_value)
                
            metrics.parse_success = True
            
        except json.JSONDecodeError as e:
            metrics.error_message = f"JSON parse error: {e}"
            metrics.parse_success = False
            # 尝试文本解析
            metrics = self._parse_text_output(output, metrics)
        except Exception as e:
            metrics.error_message = f"JSON parse error: {e}"
            metrics.parse_success = False
        
        return metrics
    
    def _parse_text_output(self, output: str, metrics: MaliPerformanceMetrics) -> MaliPerformanceMetrics:
        """解析文本格式输出"""
        try:
            lines = output.split('\n')
            
            for line in lines:
                line = line.strip()
                
                # Shader 类型
                if "Shader type:" in line:
                    metrics.shader_type = line.split(":")[-1].strip()
                
                # GPU
                elif "Hardware:" in line or "Core:" in line:
                    metrics.gpu_name = line.split(":")[-1].strip()
                
                # 工作寄存器
                elif "Work registers:" in line:
                    match = re.search(r'(\d+)', line)
                    if match:
                        metrics.work_registers = int(match.group(1))
                
                # Uniform 寄存器
                elif "Uniform registers:" in line:
                    match = re.search(r'(\d+)', line)
                    if match:
                        metrics.uniform_registers = int(match.group(1))
                
                # 周期
                elif "Total instruction cycles:" in line or "Total cycles:" in line:
                    match = re.search(r'([\d.]+)', line)
                    if match:
                        metrics.total_cycles = float(match.group(1))
                
                elif "Shortest path cycles:" in line:
                    match = re.search(r'([\d.]+)', line)
                    if match:
                        metrics.shortest_path = float(match.group(1))
                
                elif "Longest path cycles:" in line:
                    match = re.search(r'([\d.]+)', line)
                    if match:
                        metrics.longest_path = float(match.group(1))
                
                # FMA
                elif "FMA:" in line or "Arithmetic:" in line:
                    match = re.search(r'([\d.]+)', line)
                    if match:
                        metrics.fma_cycles = float(match.group(1))
                
                # CVT
                elif "CVT:" in line:
                    match = re.search(r'([\d.]+)', line)
                    if match:
                        metrics.cvt_cycles = float(match.group(1))
                
                # SFU
                elif "SFU:" in line:
                    match = re.search(r'([\d.]+)', line)
                    if match:
                        metrics.sfu_cycles = float(match.group(1))
                
                # Load/Store
                elif "Load/Store:" in line or "LS:" in line:
                    match = re.search(r'([\d.]+)', line)
                    if match:
                        metrics.load_store_cycles = float(match.group(1))
                
                # Texture
                elif "Texture:" in line or "T:" in line:
                    match = re.search(r'([\d.]+)', line)
                    if match:
                        metrics.texture_cycles = float(match.group(1))
                
                # Varying
                elif "Varying:" in line or "V:" in line:
                    match = re.search(r'([\d.]+)', line)
                    if match:
                        metrics.varying_cycles = float(match.group(1))
                
                # Stack spilling
                elif "stack spilling" in line.lower():
                    metrics.has_stack_spilling = True
                    match = re.search(r'(\d+)', line)
                    if match:
                        metrics.spill_count = int(match.group(1))
            
            # 如果提取到了任何有效数据，认为解析成功
            metrics.parse_success = (
                metrics.shader_type != "" or 
                metrics.total_cycles > 0 or 
                metrics.work_registers > 0
            )
            
        except Exception as e:
            metrics.error_message = f"Text parse error: {e}"
            metrics.parse_success = False
        
        return metrics
    
    def analyze_shaders_batch(
        self, 
        shaders: List[bytes], 
        gpu_core: str = "Mali-G715",
        max_workers: int = 4,
        progress_callback=None
    ) -> List[ShaderAnalysisResult]:
        """批量分析 shader
        
        Args:
            shaders: SPIR-V 数据列表
            gpu_core: 目标 GPU 核心
            max_workers: 并行工作线程数
            progress_callback: 进度回调函数 (current, total)
            
        Returns:
            分析结果列表
        """
        results = []
        total = len(shaders)
        
        def analyze_one(args):
            idx, spirv_data = args
            metrics = self.analyze_spirv(spirv_data, gpu_core)
            
            # 计算 SPIR-V 版本
            spirv_version = "Unknown"
            if len(spirv_data) >= 8:
                import struct
                version = struct.unpack('<I', spirv_data[4:8])[0]
                major = (version >> 16) & 0xFF
                minor = (version >> 8) & 0xFF
                spirv_version = f"{major}.{minor}"
            
            return ShaderAnalysisResult(
                shader_index=idx,
                shader_size=len(spirv_data),
                spirv_version=spirv_version,
                metrics=metrics
            )
        
        # 使用线程池并行处理
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(analyze_one, (i, s)): i 
                for i, s in enumerate(shaders)
            }
            
            completed = 0
            for future in as_completed(futures):
                result = future.result()
                results.append(result)
                completed += 1
                
                if progress_callback:
                    progress_callback(completed, total)
        
        # 按索引排序
        results.sort(key=lambda x: x.shader_index)
        
        return results


def get_available_gpu_cores(malioc_path: str = None) -> List[str]:
    """获取可用的 GPU 核心列表"""
    malioc = malioc_path or resolve_malioc_path()
    
    try:
        result = subprocess.run(
            [malioc, "--list"],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        cores = []
        for line in result.stdout.split('\n'):
            line = line.strip()
            if not line:
                continue
            if "architecture" in line or line.startswith("="):
                continue
            if "(" in line:
                name = line.split("(")[0].strip()
                if name:
                    cores.append(name)
        
        return cores
    except:
        # 返回常见核心列表
        return [
            "Mali-G78", "Mali-G77", "Mali-G76", "Mali-G72", "Mali-G71",
            "Mali-G715", "Mali-G615", "Mali-G510", "Mali-G310",
            "Mali-G720", "Mali-G620", "Mali-G520", "Mali-G320",
        ]


# ============================================================================
# CLI
# ============================================================================

if __name__ == '__main__':
    import sys
    
    print("Mali Offline Compiler Integration")
    print("=" * 60)
    
    try:
        malioc = MaliOfflineCompiler()
        print(f"Path: {malioc.malioc_path}")
        print(f"Version: {malioc.version}")
        
        cores = get_available_gpu_cores(malioc.malioc_path)
        print(f"\nAvailable GPU cores: {len(cores)}")
        for core in cores[:10]:
            print(f"  - {core}")
        if len(cores) > 10:
            print(f"  ... and {len(cores) - 10} more")
        
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

"""
Buffer 相关规则
===============

检测 Buffer 资源相关的性能问题。
"""

from typing import List
from .base import BaseRule, RuleRegistry
from ..core.types import Issue
from ..core.enums import Severity, Category


@RuleRegistry.register
class BufferSizeRule(BaseRule):
    """检测 Buffer 大小"""
    
    rule_id = "RD_BUF_001"
    name = "Large Buffer"
    description = "检测单个 Buffer 内存占用过大"
    severity = Severity.WARNING
    category = Category.BUFFER
    
    def check(self) -> List[Issue]:
        issues = []
        # 64MB 阈值
        threshold = self.get_threshold("max_buffer_size_mb", 64) * 1024 * 1024
        
        for buf in self.context.buffers:
            if buf.size > threshold:
                size_mb = buf.size / (1024 * 1024)
                issues.append(self.create_issue(
                    f"Buffer 过大: {buf.name or buf.resource_id} ({size_mb:.1f} MB)",
                    location_path=f"Buffer/{buf.resource_id}",
                ))
        
        return issues


@RuleRegistry.register
class DynamicBufferRule(BaseRule):
    """检测动态 Buffer 使用"""
    
    rule_id = "RD_BUF_002"
    name = "Dynamic Buffer Update"
    description = "检测频繁更新的动态 Buffer"
    severity = Severity.INFO
    category = Category.BUFFER
    
    def check(self) -> List[Issue]:
        issues = []
        
        # 统计 Buffer 更新次数
        update_counts = {}
        for update in self.context.parsed.buffer_updates:
            buf_id = update.get("buffer_id")
            update_counts[buf_id] = update_counts.get(buf_id, 0) + 1
        
        # 检测频繁更新
        threshold = self.get_threshold("max_buffer_updates", 10)
        frequent_updates = [
            (buf_id, count) 
            for buf_id, count in update_counts.items() 
            if count > threshold
        ]
        
        if frequent_updates:
            issues.append(self.create_issue(
                f"{len(frequent_updates)} 个 Buffer 更新频繁 (>{threshold}次)，考虑使用 Ring Buffer",
                location_path="Buffers",
            ))
        
        return issues


@RuleRegistry.register
class ConstantBufferRule(BaseRule):
    """检测 Constant Buffer 效率"""
    
    rule_id = "RD_BUF_003"
    name = "Constant Buffer Packing"
    description = "检测 Constant Buffer 是否高效打包"
    severity = Severity.INFO
    category = Category.BUFFER
    
    def check(self) -> List[Issue]:
        issues = []
        
        # 检测小 CB 数量
        small_cb_count = 0
        cb_sizes = []
        
        for buf in self.context.buffers:
            if buf.is_constant_buffer:
                cb_sizes.append(buf.size)
                if buf.size < 64:  # 小于64字节
                    small_cb_count += 1
        
        if small_cb_count > 20:
            issues.append(self.create_issue(
                f"{small_cb_count} 个小 Constant Buffer (<64B)，建议合并减少绑定开销",
                location_path="Constant Buffers",
            ))
        
        return issues


@RuleRegistry.register
class IndexBufferFormatRule(BaseRule):
    """检测 Index Buffer 格式"""
    
    rule_id = "RD_BUF_004"
    name = "Index Buffer Format"
    description = "检测 Index Buffer 是否使用最优格式"
    severity = Severity.INFO
    category = Category.BUFFER
    
    def check(self) -> List[Issue]:
        issues = []
        
        # 检测使用 32-bit index 但顶点数 < 65535 的情况
        wasteful_count = 0
        for draw in self.context.parsed.draws:
            if draw.get("index_format") == "R32_UINT":
                vertex_count = draw.get("vertex_count", 0)
                if vertex_count > 0 and vertex_count < 65535:
                    wasteful_count += 1
        
        if wasteful_count > 10:
            issues.append(self.create_issue(
                f"{wasteful_count} 个 Draw 使用 32-bit Index 但顶点数 <65535，浪费内存",
                location_path="Index Buffers",
            ))
        
        return issues


@RuleRegistry.register
class VertexBufferLayoutRule(BaseRule):
    """检测顶点布局效率"""
    
    rule_id = "RD_BUF_005"
    name = "Vertex Buffer Layout"
    description = "检测顶点属性是否过度使用"
    severity = Severity.INFO
    category = Category.BUFFER
    
    def check(self) -> List[Issue]:
        issues = []
        
        # 检测顶点 stride 过大
        large_stride_count = 0
        threshold = self.get_threshold("max_vertex_stride", 64)
        
        for draw in self.context.parsed.draws:
            stride = draw.get("vertex_stride", 0)
            if stride > threshold:
                large_stride_count += 1
        
        if large_stride_count > 0:
            issues.append(self.create_issue(
                f"{large_stride_count} 个 Draw 顶点 stride > {threshold} 字节，考虑拆分 stream",
                location_path="Vertex Buffers",
            ))
        
        return issues


@RuleRegistry.register
class UnusedBufferRule(BaseRule):
    """检测未使用的 Buffer"""
    
    rule_id = "RD_BUF_006"
    name = "Unused Buffer"
    description = "检测创建但未使用的 Buffer"
    severity = Severity.INFO
    category = Category.BUFFER
    
    def check(self) -> List[Issue]:
        issues = []
        
        # 统计使用过的 Buffer
        used_buffers = set()
        for draw in self.context.parsed.draws:
            for buf_id in draw.get("bound_buffers", []):
                used_buffers.add(buf_id)
        
        # 检测未使用的
        unused = []
        for buf in self.context.buffers:
            if buf.resource_id not in used_buffers:
                unused.append(buf)
        
        if len(unused) > 10:
            total_size = sum(buf.size for buf in unused)
            size_mb = total_size / (1024 * 1024)
            issues.append(self.create_issue(
                f"{len(unused)} 个 Buffer 未使用，占用 {size_mb:.1f} MB",
                location_path="Buffers",
            ))
        
        return issues

"""
Render Target Tracker - 分析 RT 操作序列和冗余检测

用于识别：
1. 冗余 Clear 操作（Clear 后没有 Draw）
2. 未使用的 RT（绑定后从未 Draw）
3. RT 切换热点（频繁绑定/解绑）
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Any
from enum import Enum


class RTOpType(Enum):
    """RT 操作类型"""
    CLEAR = "clear"           # ClearRenderTargetView / vkCmdClearColorImage
    CLEAR_DEPTH = "clear_depth"  # ClearDepthStencilView / vkCmdClearDepthStencilImage
    BIND = "bind"             # OMSetRenderTargets / vkCmdBeginRenderPass
    UNBIND = "unbind"         # RT 解绑（被其他 RT 替换或解绑）
    DRAW = "draw"             # Draw call 使用 RT
    RESOLVE = "resolve"       # ResolveSubresource / vkCmdResolveImage


@dataclass
class RTOperation:
    """单次 RT 操作记录"""
    eid: int                           # Event ID
    op_type: RTOpType                  # 操作类型
    resource_id: str                   # RT 资源 ID
    slot: int = 0                      # RT slot (Color0-7, Depth=-1)
    clear_color: Optional[tuple] = None  # Clear 颜色 (R,G,B,A)
    api_name: str = ""                 # 原始 API 名称
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "eid": self.eid,
            "opType": self.op_type.value,
            "resourceId": self.resource_id,
            "slot": self.slot,
            "clearColor": self.clear_color,
            "apiName": self.api_name,
        }


@dataclass
class RTLifecycle:
    """单个 RT 的生命周期分析"""
    resource_id: str
    first_clear_eid: Optional[int] = None
    first_bind_eid: Optional[int] = None
    first_draw_eid: Optional[int] = None
    last_draw_eid: Optional[int] = None
    
    total_clears: int = 0
    total_binds: int = 0
    total_draws: int = 0
    
    # 冗余标记
    cleared_but_unused: bool = False     # Clear 后没有任何 Draw
    bound_but_unused: bool = False       # 绑定后没有 Draw
    redundant_clear_count: int = 0       # 连续 Clear 次数（冗余）
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "resourceId": self.resource_id,
            "firstClearEid": self.first_clear_eid,
            "firstBindEid": self.first_bind_eid,
            "firstDrawEid": self.first_draw_eid,
            "lastDrawEid": self.last_draw_eid,
            "totalClears": self.total_clears,
            "totalBinds": self.total_binds,
            "totalDraws": self.total_draws,
            "clearedButUnused": self.cleared_but_unused,
            "boundButUnused": self.bound_but_unused,
            "redundantClearCount": self.redundant_clear_count,
        }


@dataclass
class RTIssue:
    """RT 相关问题"""
    issue_type: str           # "redundant_clear" | "unused_rt" | "excessive_switches"
    severity: str             # "warning" | "info"
    resource_id: str
    event_ids: List[int]
    message: str
    suggestion: str
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "issueType": self.issue_type,
            "severity": self.severity,
            "resourceId": self.resource_id,
            "eventIds": self.event_ids,
            "message": self.message,
            "suggestion": self.suggestion,
        }


class RTTracker:
    """Render Target 追踪器"""
    
    # API 名称映射
    CLEAR_COLOR_APIS = {
        "ID3D11DeviceContext::ClearRenderTargetView",
        "ID3D12GraphicsCommandList::ClearRenderTargetView",
        "vkCmdClearColorImage",
        "glClear",
        "glClearNamedFramebufferfv",
    }
    
    CLEAR_DEPTH_APIS = {
        "ID3D11DeviceContext::ClearDepthStencilView",
        "ID3D12GraphicsCommandList::ClearDepthStencilView",
        "vkCmdClearDepthStencilImage",
    }
    
    BIND_RT_APIS = {
        "ID3D11DeviceContext::OMSetRenderTargets",
        "ID3D12GraphicsCommandList::OMSetRenderTargets",
        "vkCmdBeginRenderPass",
        "vkCmdBeginRenderPass2",
        "vkCmdBeginRendering",
        "glBindFramebuffer",
    }
    
    def __init__(self):
        self.operations: List[RTOperation] = []
        self.lifecycles: Dict[str, RTLifecycle] = {}  # resource_id -> lifecycle
        self.current_bound_rts: Dict[int, str] = {}   # slot -> resource_id
        self.current_depth_rt: Optional[str] = None
        self._pending_clears: Dict[str, int] = {}     # resource_id -> clear_eid (未被 Draw 的 Clear)
        
    def reset(self):
        """重置追踪器状态"""
        self.operations.clear()
        self.lifecycles.clear()
        self.current_bound_rts.clear()
        self.current_depth_rt = None
        self._pending_clears.clear()
        
    def record_clear(self, eid: int, resource_id: str, is_depth: bool = False,
                     clear_color: Optional[tuple] = None, api_name: str = ""):
        """记录 Clear 操作"""
        if not resource_id or resource_id == "0":
            return
            
        op_type = RTOpType.CLEAR_DEPTH if is_depth else RTOpType.CLEAR
        op = RTOperation(
            eid=eid,
            op_type=op_type,
            resource_id=resource_id,
            slot=-1 if is_depth else 0,
            clear_color=clear_color,
            api_name=api_name,
        )
        self.operations.append(op)
        
        # 更新生命周期
        lc = self._get_or_create_lifecycle(resource_id)
        lc.total_clears += 1
        if lc.first_clear_eid is None:
            lc.first_clear_eid = eid
            
        # 检测连续 Clear（冗余）
        if resource_id in self._pending_clears:
            lc.redundant_clear_count += 1
        self._pending_clears[resource_id] = eid
        
    def record_bind(self, eid: int, color_rts: List[str], depth_rt: Optional[str] = None,
                    api_name: str = ""):
        """记录 RT 绑定操作
        
        Args:
            eid: Event ID
            color_rts: Color RT 资源 ID 列表 [slot0, slot1, ...]
            depth_rt: Depth RT 资源 ID
            api_name: API 名称
        """
        # 先处理解绑（旧的 RT 被替换）
        old_bound = set(self.current_bound_rts.values())
        new_bound = set(rt for rt in color_rts if rt and rt != "0")
        
        # 记录解绑操作
        for old_rt in old_bound - new_bound:
            self.operations.append(RTOperation(
                eid=eid,
                op_type=RTOpType.UNBIND,
                resource_id=old_rt,
                api_name=api_name,
            ))
            
        # 记录新绑定
        self.current_bound_rts.clear()
        for slot, rt_id in enumerate(color_rts):
            if rt_id and rt_id != "0":
                self.operations.append(RTOperation(
                    eid=eid,
                    op_type=RTOpType.BIND,
                    resource_id=rt_id,
                    slot=slot,
                    api_name=api_name,
                ))
                self.current_bound_rts[slot] = rt_id
                
                lc = self._get_or_create_lifecycle(rt_id)
                lc.total_binds += 1
                if lc.first_bind_eid is None:
                    lc.first_bind_eid = eid
                    
        # 处理 Depth RT
        if depth_rt and depth_rt != "0":
            if self.current_depth_rt and self.current_depth_rt != depth_rt:
                self.operations.append(RTOperation(
                    eid=eid,
                    op_type=RTOpType.UNBIND,
                    resource_id=self.current_depth_rt,
                    slot=-1,
                    api_name=api_name,
                ))
            self.current_depth_rt = depth_rt
            self.operations.append(RTOperation(
                eid=eid,
                op_type=RTOpType.BIND,
                resource_id=depth_rt,
                slot=-1,
                api_name=api_name,
            ))
            
    def record_draw(self, eid: int, api_name: str = ""):
        """记录 Draw 调用（使用当前绑定的 RT）"""
        # 所有当前绑定的 RT 都被使用
        for slot, rt_id in self.current_bound_rts.items():
            self.operations.append(RTOperation(
                eid=eid,
                op_type=RTOpType.DRAW,
                resource_id=rt_id,
                slot=slot,
                api_name=api_name,
            ))
            
            lc = self._get_or_create_lifecycle(rt_id)
            lc.total_draws += 1
            if lc.first_draw_eid is None:
                lc.first_draw_eid = eid
            lc.last_draw_eid = eid
            
            # 清除 pending clear
            if rt_id in self._pending_clears:
                del self._pending_clears[rt_id]
                
        # Depth RT 也被使用
        if self.current_depth_rt:
            lc = self._get_or_create_lifecycle(self.current_depth_rt)
            lc.total_draws += 1
            if lc.first_draw_eid is None:
                lc.first_draw_eid = eid
            lc.last_draw_eid = eid
            
            if self.current_depth_rt in self._pending_clears:
                del self._pending_clears[self.current_depth_rt]
                
    def finalize(self) -> List[RTIssue]:
        """完成分析，生成问题报告"""
        issues: List[RTIssue] = []
        
        # 检查所有未使用的 Clear
        for resource_id, clear_eid in self._pending_clears.items():
            lc = self.lifecycles.get(resource_id)
            if lc:
                lc.cleared_but_unused = True
                issues.append(RTIssue(
                    issue_type="redundant_clear",
                    severity="warning",
                    resource_id=resource_id,
                    event_ids=[clear_eid],
                    message=f"RT {resource_id} 在 EID {clear_eid} 被 Clear 后没有被使用",
                    suggestion="考虑移除该 Clear 操作，或检查是否遗漏了后续的 Draw 调用",
                ))
                
        # 检查绑定但未使用的 RT
        for resource_id, lc in self.lifecycles.items():
            if lc.total_binds > 0 and lc.total_draws == 0:
                lc.bound_but_unused = True
                issues.append(RTIssue(
                    issue_type="unused_rt",
                    severity="info",
                    resource_id=resource_id,
                    event_ids=[lc.first_bind_eid] if lc.first_bind_eid else [],
                    message=f"RT {resource_id} 被绑定 {lc.total_binds} 次但从未用于 Draw",
                    suggestion="检查是否是临时 RT 或调试用途",
                ))
                
            # 检查冗余 Clear
            if lc.redundant_clear_count > 0:
                issues.append(RTIssue(
                    issue_type="redundant_clear",
                    severity="info",
                    resource_id=resource_id,
                    event_ids=[],
                    message=f"RT {resource_id} 有 {lc.redundant_clear_count} 次连续 Clear（无 Draw 间隔）",
                    suggestion="合并连续的 Clear 操作可减少 GPU 开销",
                ))
                
        return issues
        
    def _get_or_create_lifecycle(self, resource_id: str) -> RTLifecycle:
        """获取或创建 RT 生命周期记录"""
        if resource_id not in self.lifecycles:
            self.lifecycles[resource_id] = RTLifecycle(resource_id=resource_id)
        return self.lifecycles[resource_id]
        
    def get_operations(self) -> List[Dict[str, Any]]:
        """获取所有操作记录（用于序列化）"""
        return [op.to_dict() for op in self.operations]
        
    def get_lifecycles(self) -> List[Dict[str, Any]]:
        """获取所有生命周期记录"""
        return [lc.to_dict() for lc in self.lifecycles.values()]
        
    def get_timeline_data(self) -> Dict[str, Any]:
        """获取时间线可视化数据"""
        # 按 resource_id 分组
        timeline: Dict[str, List[Dict]] = {}
        for op in self.operations:
            if op.resource_id not in timeline:
                timeline[op.resource_id] = []
            timeline[op.resource_id].append({
                "eid": op.eid,
                "type": op.op_type.value,
                "slot": op.slot,
            })
            
        return {
            "timeline": timeline,
            "summary": {
                "totalRTs": len(self.lifecycles),
                "totalOps": len(self.operations),
                "rtWithIssues": sum(1 for lc in self.lifecycles.values() 
                                   if lc.cleared_but_unused or lc.bound_but_unused),
            }
        }


# 便捷函数：从事件列表构建 RT 追踪数据
def analyze_rt_operations(events: List[Dict[str, Any]]) -> Dict[str, Any]:
    """分析事件列表中的 RT 操作
    
    Args:
        events: 事件列表，每个事件包含 eid, name, pipelineState 等
        
    Returns:
        RT 分析结果，包含 operations, lifecycles, issues, timeline
    """
    tracker = RTTracker()
    
    for event in events:
        eid = event.get("eid", 0)
        name = event.get("name", "")
        event_type = event.get("type", "")
        
        # 识别 Clear 操作
        if any(api in name for api in tracker.CLEAR_COLOR_APIS):
            # 尝试从参数提取 RT 资源 ID
            rt_id = _extract_rt_from_clear(event)
            if rt_id:
                tracker.record_clear(eid, rt_id, is_depth=False, api_name=name)
                
        elif any(api in name for api in tracker.CLEAR_DEPTH_APIS):
            rt_id = _extract_rt_from_clear(event)
            if rt_id:
                tracker.record_clear(eid, rt_id, is_depth=True, api_name=name)
                
        # 识别 Bind 操作
        elif any(api in name for api in tracker.BIND_RT_APIS):
            color_rts, depth_rt = _extract_rt_from_bind(event)
            if color_rts or depth_rt:
                tracker.record_bind(eid, color_rts, depth_rt, api_name=name)
                
        # 识别 Draw 操作
        elif event_type == "draw" or "Draw" in name or "Dispatch" in name:
            # 从 pipelineState 获取当前绑定的 RT
            ps = event.get("pipelineState", {})
            bindings = ps.get("bindings", {})
            
            # 提取 RT 列表
            render_targets = bindings.get("renderTargets", [])
            depth_target = bindings.get("depthTarget", {})
            
            if render_targets or depth_target:
                color_rts = [rt.get("resourceId", "") for rt in render_targets]
                depth_rt = depth_target.get("resourceId") if depth_target else None
                
                # 更新当前绑定状态
                if color_rts or depth_rt:
                    tracker.current_bound_rts = {i: rt for i, rt in enumerate(color_rts) if rt}
                    tracker.current_depth_rt = depth_rt
                    
            tracker.record_draw(eid, api_name=name)
            
    # 完成分析
    issues = tracker.finalize()
    
    return {
        "operations": tracker.get_operations(),
        "lifecycles": tracker.get_lifecycles(),
        "issues": [issue.to_dict() for issue in issues],
        "timeline": tracker.get_timeline_data(),
    }


def _extract_rt_from_clear(event: Dict[str, Any]) -> Optional[str]:
    """从 Clear 事件提取 RT 资源 ID"""
    # 尝试从 apiCall.params 提取
    api_call = event.get("apiCall", {})
    params = api_call.get("params", [])
    
    for param in params:
        name = param.get("name", "")
        if "RenderTargetView" in name or "pView" in name or "image" in name.lower():
            return str(param.get("value", ""))
            
    return None


def _extract_rt_from_bind(event: Dict[str, Any]) -> tuple:
    """从 Bind 事件提取 RT 列表"""
    api_call = event.get("apiCall", {})
    params = api_call.get("params", [])
    
    color_rts = []
    depth_rt = None
    
    for param in params:
        name = param.get("name", "")
        value = param.get("value", "")
        
        if "ppRenderTargetViews" in name:
            # D3D11 格式: [131, 0, 0, 0, ...]
            if isinstance(value, list):
                color_rts = [str(v) for v in value if v and v != 0]
            elif isinstance(value, str) and value.startswith("["):
                # 解析字符串格式
                import re
                matches = re.findall(r'\d+', value)
                color_rts = [m for m in matches if m != "0"]
                
        elif "pDepthStencilView" in name:
            depth_rt = str(value) if value and value != "0" else None
            
        elif "framebuffer" in name.lower():
            # Vulkan 格式
            if isinstance(value, dict):
                # 从 framebuffer 结构提取 attachments
                attachments = value.get("attachments", [])
                color_rts = [str(a.get("resourceId", "")) for a in attachments[:-1] if a]
                if attachments:
                    depth_rt = str(attachments[-1].get("resourceId", ""))
            else:
                color_rts = [str(value)]
                
    return color_rts, depth_rt

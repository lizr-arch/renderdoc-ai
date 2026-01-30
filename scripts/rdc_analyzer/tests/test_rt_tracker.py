"""
RT Tracker 单元测试
"""

import unittest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.rt_tracker import RTTracker, RTOpType, RTIssue, analyze_rt_operations


class TestRTTracker(unittest.TestCase):
    """RTTracker 核心功能测试"""
    
    def setUp(self):
        self.tracker = RTTracker()
        
    def test_record_clear_basic(self):
        """测试基本 Clear 记录"""
        self.tracker.record_clear(10, "RT001", is_depth=False, api_name="ClearRenderTargetView")
        
        self.assertEqual(len(self.tracker.operations), 1)
        self.assertEqual(self.tracker.operations[0].eid, 10)
        self.assertEqual(self.tracker.operations[0].op_type, RTOpType.CLEAR)
        self.assertEqual(self.tracker.operations[0].resource_id, "RT001")
        
        # 检查生命周期
        lc = self.tracker.lifecycles.get("RT001")
        self.assertIsNotNone(lc)
        self.assertEqual(lc.total_clears, 1)
        self.assertEqual(lc.first_clear_eid, 10)
        
    def test_clear_depth(self):
        """测试 Depth Clear 记录"""
        self.tracker.record_clear(20, "DSV001", is_depth=True, api_name="ClearDepthStencilView")
        
        self.assertEqual(self.tracker.operations[0].op_type, RTOpType.CLEAR_DEPTH)
        self.assertEqual(self.tracker.operations[0].slot, -1)
        
    def test_record_bind(self):
        """测试 RT 绑定"""
        self.tracker.record_bind(100, ["RT001", "RT002"], depth_rt="DSV001", api_name="OMSetRenderTargets")
        
        # 应该有 3 个 BIND 操作
        bind_ops = [op for op in self.tracker.operations if op.op_type == RTOpType.BIND]
        self.assertEqual(len(bind_ops), 3)
        
        # 检查槽位
        self.assertEqual(bind_ops[0].slot, 0)  # RT001 in slot 0
        self.assertEqual(bind_ops[1].slot, 1)  # RT002 in slot 1
        self.assertEqual(bind_ops[2].slot, -1)  # DSV001 is depth
        
        # 检查当前绑定状态
        self.assertEqual(self.tracker.current_bound_rts[0], "RT001")
        self.assertEqual(self.tracker.current_bound_rts[1], "RT002")
        self.assertEqual(self.tracker.current_depth_rt, "DSV001")
        
    def test_record_unbind_on_rebind(self):
        """测试重新绑定时自动解绑旧 RT"""
        self.tracker.record_bind(100, ["RT001"], api_name="OMSetRenderTargets")
        self.tracker.record_bind(200, ["RT002"], api_name="OMSetRenderTargets")
        
        unbind_ops = [op for op in self.tracker.operations if op.op_type == RTOpType.UNBIND]
        self.assertEqual(len(unbind_ops), 1)
        self.assertEqual(unbind_ops[0].resource_id, "RT001")
        
    def test_record_draw(self):
        """测试 Draw 调用记录"""
        self.tracker.record_bind(100, ["RT001"])
        self.tracker.record_draw(150, api_name="DrawIndexed")
        
        draw_ops = [op for op in self.tracker.operations if op.op_type == RTOpType.DRAW]
        self.assertEqual(len(draw_ops), 1)
        self.assertEqual(draw_ops[0].resource_id, "RT001")
        
        # 检查生命周期
        lc = self.tracker.lifecycles["RT001"]
        self.assertEqual(lc.total_draws, 1)
        self.assertEqual(lc.first_draw_eid, 150)
        self.assertEqual(lc.last_draw_eid, 150)
        
    def test_redundant_clear_detection(self):
        """测试冗余 Clear 检测"""
        # 两次 Clear 之间没有 Draw
        self.tracker.record_clear(10, "RT001")
        self.tracker.record_clear(20, "RT001")  # 冗余
        
        lc = self.tracker.lifecycles["RT001"]
        self.assertEqual(lc.redundant_clear_count, 1)
        
    def test_finalize_cleared_but_unused(self):
        """测试 finalize: Clear 后未使用"""
        self.tracker.record_clear(10, "RT001")
        # 没有后续 Draw
        
        issues = self.tracker.finalize()
        
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].issue_type, "redundant_clear")
        self.assertEqual(issues[0].resource_id, "RT001")
        self.assertIn("EID 10", issues[0].message)
        
    def test_finalize_bound_but_unused(self):
        """测试 finalize: 绑定但未使用"""
        self.tracker.record_bind(100, ["RT001"])
        # 没有 Draw
        
        issues = self.tracker.finalize()
        
        unused_issues = [i for i in issues if i.issue_type == "unused_rt"]
        self.assertEqual(len(unused_issues), 1)
        self.assertEqual(unused_issues[0].resource_id, "RT001")
        
    def test_clear_then_draw_no_issue(self):
        """测试正常流程：Clear -> Draw 不应产生问题"""
        self.tracker.record_bind(100, ["RT001"])
        self.tracker.record_clear(110, "RT001")
        self.tracker.record_draw(150)
        
        issues = self.tracker.finalize()
        
        # 不应该有 redundant_clear 问题
        redundant_issues = [i for i in issues if i.issue_type == "redundant_clear"]
        self.assertEqual(len(redundant_issues), 0)
        
    def test_ignore_invalid_resource_id(self):
        """测试忽略无效资源 ID"""
        self.tracker.record_clear(10, "")
        self.tracker.record_clear(20, "0")
        
        self.assertEqual(len(self.tracker.operations), 0)
        self.assertEqual(len(self.tracker.lifecycles), 0)
        
    def test_get_timeline_data(self):
        """测试时间线数据生成"""
        self.tracker.record_bind(100, ["RT001"])
        self.tracker.record_draw(150)
        self.tracker.record_bind(200, ["RT002"])
        
        data = self.tracker.get_timeline_data()
        
        self.assertIn("timeline", data)
        self.assertIn("summary", data)
        self.assertIn("RT001", data["timeline"])
        self.assertEqual(data["summary"]["totalRTs"], 2)
        
    def test_excessive_switches_detection(self):
        """测试过多 RT 切换检测"""
        # 模拟频繁切换：15 次绑定，每次只有 2 个 Draw（< 5 阈值）
        for i in range(15):
            self.tracker.record_bind(i * 10, ["RT001"])
            self.tracker.record_draw(i * 10 + 1)
            self.tracker.record_draw(i * 10 + 2)
            
        issues = self.tracker.finalize()
        
        switch_issues = [i for i in issues if i.issue_type == "excessive_switches"]
        self.assertEqual(len(switch_issues), 1)
        self.assertEqual(switch_issues[0].resource_id, "RT001")
        self.assertIn("频繁切换", switch_issues[0].message)
        
    def test_no_excessive_switches_if_enough_draws(self):
        """测试：如果每次绑定有足够 Draw，则不报告过多切换"""
        # 12 次绑定，每次 10 个 Draw（> 5 阈值）
        for i in range(12):
            self.tracker.record_bind(i * 100, ["RT001"])
            for j in range(10):
                self.tracker.record_draw(i * 100 + j + 1)
                
        issues = self.tracker.finalize()
        
        switch_issues = [i for i in issues if i.issue_type == "excessive_switches"]
        self.assertEqual(len(switch_issues), 0)


class TestAnalyzeRTOperations(unittest.TestCase):
    """analyze_rt_operations 便捷函数测试"""
    
    def test_analyze_draw_events(self):
        """测试分析 Draw 事件"""
        events = [
            {
                "eid": 100,
                "name": "DrawIndexed",
                "type": "draw",
                "pipelineState": {
                    "bindings": {
                        "renderTargets": [
                            {"resourceId": "RT001", "slot": 0}
                        ],
                        "depthTarget": {"resourceId": "DSV001"}
                    }
                }
            }
        ]
        
        result = analyze_rt_operations(events)
        
        self.assertIn("operations", result)
        self.assertIn("lifecycles", result)
        self.assertIn("issues", result)
        self.assertIn("timeline", result)
        
    def test_empty_events(self):
        """测试空事件列表"""
        result = analyze_rt_operations([])
        
        self.assertEqual(len(result["operations"]), 0)
        self.assertEqual(len(result["lifecycles"]), 0)
        self.assertEqual(len(result["issues"]), 0)


class TestRTOperationSerialization(unittest.TestCase):
    """序列化测试"""
    
    def test_operation_to_dict(self):
        """测试操作序列化"""
        from core.rt_tracker import RTOperation
        
        op = RTOperation(
            eid=100,
            op_type=RTOpType.CLEAR,
            resource_id="RT001",
            slot=0,
            clear_color=(1.0, 0.0, 0.0, 1.0),
            api_name="ClearRTV"
        )
        
        d = op.to_dict()
        
        self.assertEqual(d["eid"], 100)
        self.assertEqual(d["opType"], "clear")
        self.assertEqual(d["resourceId"], "RT001")
        self.assertEqual(d["clearColor"], (1.0, 0.0, 0.0, 1.0))
        
    def test_lifecycle_to_dict(self):
        """测试生命周期序列化"""
        from core.rt_tracker import RTLifecycle
        
        lc = RTLifecycle(
            resource_id="RT001",
            first_clear_eid=10,
            total_clears=2,
            cleared_but_unused=True,
        )
        
        d = lc.to_dict()
        
        self.assertEqual(d["resourceId"], "RT001")
        self.assertEqual(d["firstClearEid"], 10)
        self.assertEqual(d["clearedButUnused"], True)
        
    def test_issue_to_dict(self):
        """测试问题序列化"""
        issue = RTIssue(
            issue_type="redundant_clear",
            severity="warning",
            resource_id="RT001",
            event_ids=[10, 20],
            message="Test message",
            suggestion="Test suggestion"
        )
        
        d = issue.to_dict()
        
        self.assertEqual(d["issueType"], "redundant_clear")
        self.assertEqual(d["eventIds"], [10, 20])


if __name__ == "__main__":
    unittest.main(verbosity=2)

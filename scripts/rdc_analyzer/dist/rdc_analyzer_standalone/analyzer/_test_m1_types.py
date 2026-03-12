"""
M1.1 数据结构验证脚本

验证 UsageRecord、ResourceUsageIndex、EvidenceChain 等数据类正常工作。
"""
import sys
sys.path.insert(0, '.')

from core.types import (
    UsageRecord,
    ResourceUsageIndex,
    EvidenceChain,
    Action,
    ContextEvidence
)


def test_usage_record():
    """测试 UsageRecord 数据类"""
    record = UsageRecord(
        event_id=100,
        binding_type="SRV",
        slot=0,
        purpose_hint="Albedo",
        pass_name="GBuffer Pass",
        draw_name="DrawIndexed"
    )
    
    d = record.to_dict()
    assert d['event_id'] == 100
    assert d['binding_type'] == "SRV"
    assert d['slot'] == 0
    assert d['purpose_hint'] == "Albedo"
    print("✅ UsageRecord:", d)
    return True


def test_resource_usage_index():
    """测试 ResourceUsageIndex 数据类"""
    idx = ResourceUsageIndex()
    
    # 添加纹理使用记录
    idx.add_texture_usage("tex_0x1234", UsageRecord(event_id=100, binding_type="SRV", slot=0))
    idx.add_texture_usage("tex_0x1234", UsageRecord(event_id=150, binding_type="SRV", slot=0))
    idx.add_texture_usage("tex_0x5678", UsageRecord(event_id=200, binding_type="UAV", slot=1))
    
    # 添加 Shader 使用记录
    idx.add_shader_usage("vs_main", UsageRecord(event_id=100, binding_type="VS"))
    idx.add_shader_usage("ps_main", UsageRecord(event_id=100, binding_type="PS"))
    
    # 添加 RT 使用记录
    idx.add_rt_usage("rt_gbuffer", UsageRecord(event_id=100, binding_type="RTV", slot=0))
    
    # 验证查询
    tex_usages = idx.get_texture_usages("tex_0x1234")
    assert len(tex_usages) == 2
    assert tex_usages[0].event_id == 100
    
    # 验证统计
    stats = idx.get_statistics()
    assert stats['indexed_textures'] == 2
    assert stats['indexed_shaders'] == 2
    assert stats['total_texture_usages'] == 3
    print("✅ ResourceUsageIndex stats:", stats)
    
    # 验证 to_dict
    d = idx.to_dict()
    assert 'texture_usages' in d
    assert len(d['texture_usages']['tex_0x1234']) == 2
    print("✅ ResourceUsageIndex to_dict: OK")
    return True


def test_evidence_chain():
    """测试 EvidenceChain 数据类"""
    ec = EvidenceChain(
        issue_code="PERF004",
        summary="纹理 tex_0x1234 尺寸过大 (4096x4096 > 2048px 阈值)",
        impact_score=75.0,
        verification_plan="降低纹理分辨率后重新捕获，检查显存占用"
    )
    
    # 链式添加证据
    ec.add_evidence(
        label="纹理尺寸",
        value=4096,
        threshold=2048,
        unit="px",
        severity="warning",
        resource_id="tex_0x1234"
    ).add_evidence(
        label="显存占用",
        value=64.0,
        threshold=32.0,
        unit="MB",
        severity="critical"
    )
    
    # 链式添加操作
    ec.add_action(
        action_type="jump_to_texture",
        label="查看纹理详情",
        target_page="textures.html",
        target_id="tex_0x1234",
        highlight=True
    ).add_action(
        action_type="jump_to_event",
        label="跳转到首次使用",
        target_page="events.html",
        target_id="100"
    )
    
    # 设置受影响资源
    ec.affected_resources = ["tex_0x1234"]
    ec.affected_events = [100, 150, 200]
    
    # 验证 to_dict
    d = ec.to_dict()
    assert d['issue_code'] == "PERF004"
    assert len(d['evidences']) == 2
    assert len(d['actions']) == 2
    assert d['impact_score'] == 75.0
    print("✅ EvidenceChain:", d)
    return True


def test_action_url():
    """测试 Action URL 生成"""
    action = Action(
        type="jump_to_texture",
        label="View Texture",
        target_page="textures.html",
        target_id="tex_0x1234",
        params={"highlight": True, "scroll": "center"}
    )
    
    url = action.to_url()
    assert "textures.html" in url
    assert "id=tex_0x1234" in url
    assert "highlight=True" in url
    print("✅ Action URL:", url)
    return True


def main():
    """运行所有测试"""
    print("=" * 60)
    print("M1.1 数据结构验证")
    print("=" * 60)
    
    tests = [
        test_usage_record,
        test_resource_usage_index,
        test_evidence_chain,
        test_action_url,
    ]
    
    passed = 0
    for test in tests:
        try:
            if test():
                passed += 1
        except Exception as e:
            print(f"❌ {test.__name__} 失败: {e}")
    
    print("=" * 60)
    print(f"结果: {passed}/{len(tests)} 测试通过")
    print("=" * 60)
    
    return passed == len(tests)


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

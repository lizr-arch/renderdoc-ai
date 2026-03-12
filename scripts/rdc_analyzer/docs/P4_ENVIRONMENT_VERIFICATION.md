# P4-01: D3D11 Replay 环境验证报告

## 验证日期
2026-01-20

## 环境信息
- **OS**: Windows 10/11
- **Python (系统)**: 3.11.9
- **RenderDoc 构建路径**: `D:\Code\git\renderdoc\x64\Development\`

## 验证结果

### 1. renderdoccmd.exe ✅ 可用
```bash
# 缩略图导出
renderdoccmd.exe thumb <file.rdc> -o thumb.jpg  # ✓ 成功

# RDC → XML 转换
renderdoccmd.exe convert -f <file.rdc> -o output.xml -c xml  # ✓ 成功

# 支持的导出格式
- rdc (原生格式)
- chrome.json (Chrome Profiler JSON)
- xml (纯 XML)
- zip.xml (XML + ZIP)
```

### 2. 测试 RDC 文件 ✅ 有效
- **路径**: `D:\Code\git\renderdoc\Resource\Game_x64h_2026.01.07_05.35.50_frame3996.rdc`
- **大小**: 7,466,738 bytes (7.4 MB)
- **API**: D3D11
- **Chunks**: 388 个 API 调用记录

### 3. XML 导出结构
```xml
<rdc>
  <header>...</header>
  <section>...</section>
  <extended_thumbnail>...</extended_thumbnail>
  <chunks>
    <!-- 388 chunks, 包含: -->
    - ID3D11Device::CreateDeferredContext (20)
    - ID3D11Resource::SetDebugName (18)
    - ID3D11Device::CreateBuffer (17)
    - ID3D11DeviceContext::PSSetShaderResources (12)
    - ID3D11DeviceContext::OMSetRenderTargets (12)
    - ID3D11Device::CreateTexture2D (9)
    - ID3D11DeviceContext::*SetShader (多种)
    ...
  </chunks>
</rdc>
```

### 4. Python 绑定 ⚠️ 需特殊环境

**问题**:
- 系统 Python 3.11 无法直接加载 `renderdoc.pyd`
- RenderDoc 内置 Python 3.6 (`python36.dll`)
- 需要从 qrenderdoc.exe 内部执行脚本

**解决方案**:
```bash
# 方案 A: 使用 qrenderdoc 执行脚本
qrenderdoc.exe --python scripts/my_script.py

# 方案 B: 使用 renderdoccmd 转换后用标准 Python 解析
renderdoccmd.exe convert -f input.rdc -o output.xml -c xml
py -3 scripts/parse_xml.py output.xml

# 方案 C (推荐): 混合模式
# - 使用 renderdoccmd 导出 XML/JSON
# - 用标准 Python 处理和分析
```

## 推荐架构

```
┌─────────────────┐     ┌───────────────────┐     ┌──────────────────┐
│  input.rdc      │ ──► │  renderdoccmd.exe │ ──► │  output.xml      │
│  (二进制)        │     │  convert -c xml   │     │  (结构化数据)     │
└─────────────────┘     └───────────────────┘     └──────────────────┘
                                                          │
                                                          ▼
                                                  ┌──────────────────┐
                                                  │  py -3           │
                                                  │  rdc_analyzer    │
                                                  │  (标准 Python)    │
                                                  └──────────────────┘
```

## 下一步 (P4-02)

1. 创建 `RdcXmlParser` 类，解析 XML 导出
2. 提取 Draw Call、Pipeline State、Resources
3. 转换为 `CaptureData` 统一格式
4. 集成到现有的 compare/analyze 流程

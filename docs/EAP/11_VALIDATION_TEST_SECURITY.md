# 11_VALIDATION_TEST_SECURITY — 验证、性能与安全验收

用途：给 Codex 和开发者一套统一验收清单，避免只“能编译”但不能进项目。

---

## 1. 分层验收

| 层 | 验收目标 |
|---|---|
| Bridge | RenderDoc 不存在时 no-op；存在且 API 1.7.0 时能写 annotation |
| Core Types | key/value 校验、预算、scope 栈正确 |
| Engine Hooks | pass/draw/resource 能采集到真实语义 |
| Sidecar | JSON 正确、原子写入、可 redaction |
| Rules | 有 evidence 的确定性诊断 |
| CLI | 可 summary/query/rules/export-context |
| UI/MCP | 只读、安全、可审计 |

---

## 2. 单测清单

### 2.1 Bridge

- [ ] no RenderDoc loaded -> no crash；
- [ ] API symbol missing -> no crash；
- [ ] API version < 1.7 -> rich annotations disabled；
- [ ] empty key -> invalid argument；
- [ ] null device/command/object -> invalid argument；
- [ ] string value copied safely；
- [ ] return code mapping correct；
- [ ] Init thread-safe。

### 2.2 Key Validation

- [ ] valid keys accepted；
- [ ] missing `eap.` rejected；
- [ ] uppercase rejected；
- [ ] spaces rejected；
- [ ] `..` rejected；
- [ ] trailing dot rejected；
- [ ] overly long key rejected。

### 2.3 EAP Runtime

- [ ] BeginFrame resets budget；
- [ ] ScopedPass push/pop；
- [ ] nested pass behavior defined；
- [ ] thread_local pass stack if multi-threaded；
- [ ] OnlyWhenCapturing respected；
- [ ] budget exceeded recorded。

### 2.4 Sidecar

- [ ] minimal sidecar serializes；
- [ ] empty fields skipped；
- [ ] hash formatting stable；
- [ ] atomic write success；
- [ ] atomic write failure does not corrupt old file；
- [ ] redaction policies work；
- [ ] command/resource limit works；
- [ ] parse/roundtrip if parser exists。

### 2.5 Rules

- [ ] missing context rule；
- [ ] annotation budget rule；
- [ ] low mip rule；
- [ ] suspicious format rule；
- [ ] empty pass rule；
- [ ] shader missing hash rule；
- [ ] rule result evidence mandatory。

### 2.6 CLI

- [ ] summary valid sidecar；
- [ ] rules output JSON；
- [ ] query by pass/material/resource；
- [ ] export context redacted；
- [ ] exit code 0/1/2/3 correct。

---

## 3. 集成测试场景

### 3.1 Simple Triangle / Test Scene

目标：验证基础链路。

期望：

- 1 frame；
- 1 pass；
- 1 draw；
- 1 render target；
- sidecar 可写；
- summary 输出正确。

### 3.2 Material Scene

目标：验证 material/shader/mesh。

场景：

- 至少 3 个材质；
- 至少 2 个 shader permutation；
- 至少 2 个 mesh LOD。

期望：

- draw commands 能关联 material；
- shader hash 非 0；
- mesh lod 正确。

### 3.3 Texture Streaming Scene

目标：验证 resource + streaming + rule。

人为制造：

- resident mip > wanted mip；
- 或模拟 low mip。

期望：

- `rule:texture.streaming_low_mip` 命中。

### 3.4 RenderGraph Scene

目标：验证 pass 和 dependencies。

场景：

- DepthPrepass；
- BasePass；
- Lighting；
- PostProcess；
- UI。

期望：

- pass category 正确；
- event range 正确；
- empty pass rule 不误报。

### 3.5 No RenderDoc Scene

目标：验证无工具环境。

期望：

- 游戏正常运行；
- annotation no-op；
- sidecar 可按配置关闭或写 last frame；
- 无每帧日志刷屏。

---

## 4. 性能验收

### 4.1 默认状态

默认 shipping/prod：

- 编译禁用或 runtime 关闭；
- CPU overhead 接近 0；
- 不分配额外内存；
- 不写文件。

### 4.2 Development 非 capture

默认：

- `OnlyWhenCapturing = 1`；
- 不写 draw 级 annotation；
- 可以写极少量 frame diagnostics；
- 不超过 0.1 ms/frame 目标。

### 4.3 Capture 中

可接受更高 overhead，但要有预算：

| 项 | 目标 |
|---|---:|
| annotation 写入 | 不超过 50k command annotations/frame |
| sidecar command records | 默认不超过 200k |
| sidecar resource records | 默认不超过 100k |
| sidecar 文件大小 | 普通帧 < 50MB，大帧可更高 |
| 写文件时机 | frame/capture end，不在 draw 中写磁盘 |

### 4.4 热路径约束

- draw path 不做复杂字符串格式化；
- 尽可能使用已有 debug name；
- hash 到 hex string 可以 sidecar flush 时再做；
- mutex 区域要短；
- 允许首版简单 mutex，但要记录风险。

---

## 5. 安全验收

### 5.1 数据分类

EAP 可能包含：

- asset path；
- shader source path；
- debug symbol path；
- project name；
- branch/commit；
- GPU/driver；
- material/shader/pipeline hash；
- map/camera；
- user local path。

### 5.2 默认安全要求

- [ ] 默认不上传；
- [ ] 默认不联网；
- [ ] sidecar redaction 可配置；
- [ ] external/vendor policy 不含 asset path/user path/shader debug path；
- [ ] MCP 只读；
- [ ] MCP 限制读取路径；
- [ ] 所有写操作后置并需要确认；
- [ ] 日志不刷敏感路径，或按 policy redacted。

### 5.3 Redaction 测试

输入路径：

```text
C:/Users/Alice/Company/Project/Content/Characters/Hero/T_HeroFace_D.uasset
/Game/Characters/Hero/T_HeroFace_D
/home/alice/project/shaders/BasePass.usf
```

期望：

| Policy | 输出 |
|---|---|
| LocalFull | 可保留虚拟路径，用户路径按公司规则处理 |
| ProjectInternal | `/Game/...` 保留，用户路径移除 |
| CrossProject | basename + hash |
| ExternalVendor | hash only |

---

## 6. 手动 RenderDoc 验收

步骤：

1. 启动 RenderDoc。
2. 启动引擎/游戏 development build。
3. 确认 EAP 开关：

```text
r.EAP.EnableAnnotations=1
r.EAP.EnableSidecar=1
r.EAP.OnlyWhenCapturing=1
```

4. 抓一帧。
5. 打开 event browser。
6. 选中 BasePass 中一个 draw。
7. 检查 annotations：

```text
eap.pass.name
eap.cmd.kind
eap.material.id/name/path
eap.shader.ps.hash
eap.pso.hash
eap.mesh.id/lod
```

8. 打开 texture/resource。
9. 检查 object annotations：

```text
eap.resource.kind
eap.resource.format
eap.resource.width/height
eap.asset.path
eap.streaming.resident_mip/wanted_mip
```

10. 检查 sidecar 同目录生成。
11. 运行：

```bash
eap-analyze summary capture.rmeta.json
eap-analyze rules capture.rmeta.json --output capture.rules.json
```

---

## 7. 回归测试建议

建立 golden scenes：

| Scene | 目的 |
|---|---|
| Triangle | 基础 draw |
| Materials | material/shader/permutation |
| Streaming | texture mip rules |
| RenderGraph | pass/category/event range |
| Compute | dispatch/shader cs |
| UI | UI pass |
| XR/Multiview | view/eye 字段 |
| Mobile/Android | remote/device path，后置 |

每次改 EAP：

- 编译；
- 单测；
- 至少跑 Triangle + Materials；
- 生成 sidecar；
- CLI summary/rules；
- 比较 sidecar schema 没破坏。

---

## 8. 上线灰度

推荐：

1. 渲染工具组内部启用；
2. 一个项目 development build 启用；
3. QA 一键上报前先收集 1–2 周；
4. 再接 CI；
5. 最后接 MCP/AI。

不要一开始全公司默认打开 draw 级 annotation。


# 计划：Agent01 / Android Wireless Capture over LAN

时间：2026-04-22 18:35:01 | 负责人：Agent01

## Scope / Assumptions

- 目标：在 **不要求长期 USB 连线** 的前提下，让 PC 版 RenderDoc 能通过同网网络连接 Android 设备，远程触发截帧，并把最新 capture 同步回 PC。
- 本计划聚焦两个用户确认过的里程碑：
  - `Milestone 1`：PC 与手机上的 RenderDoc 能建立无线连接，并完成最小双向控制/状态消息闭环。
  - `Milestone 2`：PC 向手机发出截帧信号；手机执行截帧、把结果保存在本地；PC 可以拉取最新 capture。
- 本计划优先复用 RenderDoc 现有 `adb`、`RemoteServer`、`TargetControl`、`LiveCapture`、`CopyCapture` 架构；只在官方无线 `adb` 路径不可用或体验不足时，才进入自研 fallback。
- 本计划不承诺在 **完全绕过 Android 调试/系统权限链路** 的前提下，支持对任意第三方游戏做无线抓帧。若设备/系统不允许无线调试或不允许必要调试配置，本计划会进入 fallback，但 fallback 仍需遵守 Android 平台权限边界。
- 本计划只做架构与执行拆分，不执行代码实现，不执行构建命令。

## 主线归属 / Redundancy Check

- 主线归属：`底座`
- 主负责人：当前执行 Codex（后续 /do 可再拆分给具体开发负责人）
- 依赖事实层：
  - RenderDoc 通用远程回放/控制协议
  - Android `adb` 设备协议与现有注入/启动逻辑
  - qrenderdoc 的 Remote Host / Live Capture UI
- 不重复开发声明：
  - 不新建第二套 capture 协议来替代现有 `RemoteServer + TargetControl`。
  - 不新建第二套“PC 拉取 capture”的文件传输系统，优先复用 `CopyCapture` / `CopyCaptureFromRemote`。
  - 不新建第二套 Android 远程主机管理系统，优先复用 `RemoteHost` / `PersistantConfig` / `RemoteManager`。
- 重叠检查结果：
  - `Milestone 1` 与现有 `RemoteServer` / `TargetControl` / `RemoteManager` 高度重叠，**应复用**。
  - `Milestone 2` 与现有 `TriggerCapture` / `NewCapture` / `CopyCapture` / `CaptureCopied` 高度重叠，**应复用**。
  - 仅“无线配对/发现 UI”与“adb pair/connect 自动化”是本次新增范围。

## 用户结果定义

### Milestone 1

- 用户在 PC 上点击 `Pair Android over Wi-Fi` 或等价入口。
- PC 能完成无线配对/连接，或允许用户手动输入 `IP:port`。
- qrenderdoc 中出现可用的 Android 远程主机条目。
- PC 能建立远端 RenderDoc server / target control 会话。
- 用户可在 UI 中看到最小状态信息：在线、版本匹配、busy、目标名、API/可抓取状态。

### Milestone 2

- 用户在 PC 上点击 `Trigger Capture`。
- 手机上的目标进程执行截帧。
- PC 收到进度与成功/失败结果。
- capture 先保存在手机本地。
- 用户在 PC 上点击 `Get Latest Capture` 或等价入口，把最新 capture 同步到本地。

## Evidence Base

- Android 协议控制器与现有 `adb` 路径：
  - `renderdoc/android/android.cpp:647-667`
  - `renderdoc/android/android.cpp:948-1311`
  - `renderdoc/android/android.cpp:1340-1677`
- `adb` 工具查找与命令执行：
  - `renderdoc/android/android_tools.cpp:175-368`
  - `renderdoc/android/android.h:37-40`
- 通用远程服务器握手与连接：
  - `renderdoc/core/remote_server.cpp:1281-1400`
- 通用 target control 协议与 capture/copy：
  - `renderdoc/core/target_control.cpp:662-712`
  - `renderdoc/core/target_control.cpp:724-949`
  - `renderdoc/core/target_control.cpp:964-1002`
- 目标进程监听 target control：
  - `renderdoc/core/core.cpp:657-680`
- 远程 target 枚举：
  - `renderdoc/replay/entry_points.cpp:438-467`
- qrenderdoc Remote Host / 配置 / 连接：
  - `qrenderdoc/Code/Interface/RemoteHost.cpp:118-198`
  - `qrenderdoc/Code/Interface/PersistantConfig.cpp:353-432`
  - `qrenderdoc/Code/ReplayManager.cpp:164-211`
  - `qrenderdoc/Code/ReplayManager.cpp:324-337`
- qrenderdoc 远程主机 UI 与 Live Capture：
  - `qrenderdoc/Windows/Dialogs/RemoteManager.cpp:196-322`
  - `qrenderdoc/Windows/Dialogs/RemoteManager.cpp:369-701`
  - `qrenderdoc/Windows/Dialogs/RemoteManager.ui:16-130`
  - `qrenderdoc/Windows/Dialogs/LiveCapture.cpp:1261-1415`
- Android 端 RenderDoc app / loader 入口：
  - `renderdoccmd/android/AndroidManifest.xml:1-19`
  - `renderdoccmd/android/Loader.java:8-54`
  - `renderdoccmd/renderdoccmd_android.cpp:403-470`
- 编码与改动风格：
  - `docs/CONTRIBUTING/Developing-Change.md`

## 自我追问验证（4 轮）

### 第 1 轮：表面分析

问题：RenderDoc 现有架构看起来支持“同网无线连接 + 远程抓帧”吗？

- 证据 1：`renderdoccmd remoteserver` 支持监听指定 host，默认监听所有网卡接口，说明远程服务天然支持局域网访问。
  - 证据：`renderdoccmd/renderdoccmd.cpp:457-518`
- 证据 2：目标进程的 `TargetControl` 监听在 `0.0.0.0` 的一组端口上，不是只绑定回环地址。
  - 证据：`renderdoc/core/core.cpp:657-680`
- 证据 3：qrenderdoc 本来就支持手动添加远程 `hostname/IP` 主机。
  - 证据：`qrenderdoc/Windows/Dialogs/RemoteManager.cpp:369-383`

阶段结论：

- “PC <-> 手机同网连接 + 远程指令 + 文件同步”从 RenderDoc 底座看是 **支持的**。
- 当前缺的不是底层远程协议，而是 **Android 无线接入入口与 UI 自动化**。

### 第 2 轮：机制验证

问题：Android 现有抓帧机制具体依赖什么？

- 证据 1：设备枚举走 `adb devices`。
  - 证据：`renderdoc/android/android.cpp:651-664`
- 证据 2：启动 Android remote server 时，会安装/检查 APK、做 `adb forward`、推送 `renderdoc.conf`、拉起 `Loader -e renderdoccmd remoteserver`。
  - 证据：`renderdoc/android/android.cpp:1123-1258`
- 证据 3：执行抓帧时，会设置 GPU debug layers、设置 `RENDERDOC_CAPOPTS`、启动目标 app、必要时做 JDWP 注入与端口转发。
  - 证据：`renderdoc/android/android.cpp:1422-1602`
- 证据 4：PC 侧已经支持 `TriggerCapture`、`NewCapture`、`CaptureProgress`、`CopyCapture`、`CaptureCopied` 全闭环。
  - 证据：`renderdoc/core/target_control.cpp:662-712`
  - 证据：`qrenderdoc/Windows/Dialogs/LiveCapture.cpp:1303-1407`

阶段结论：

- Android 抓帧不是“手机端开个 socket 就完事”，而是依赖 `adb` 这条调试控制链完成设备准备、端口桥接和进程注入。
- 但一旦无线 `adb` 可用，**绝大部分抓帧/回传逻辑都可以零协议改动直接复用**。

### 第 3 轮：限制定位

问题：限制到底属于哪一层？

结论：这是 **实现/配置限制**，不是理论限制。

- 不是理论限制：
  - RenderDoc 远程服务和 target control 都已经支持 TCP 网络访问。
  - 证据：`renderdoccmd/renderdoccmd.cpp:457-518`、`renderdoc/core/core.cpp:657-680`
- 是实现限制：
  - 现有 Android 协议控制器只会自动枚举 `adb devices`，没有“PC 内建无线配对”UI 和命令封装。
  - 证据：`renderdoc/android/android.cpp:647-667`
  - 证据：`qrenderdoc/Windows/Dialogs/RemoteManager.cpp:369-701`
- 是配置限制：
  - Android 无线抓帧是否成功，仍取决于设备是否支持并开启无线调试、设备厂商限制、应用可调试性、layer/JDWP 链路可用性。
  - 证据：`renderdoc/android/android.cpp:1422-1602`

至少 1 个绕过方案：

- 绕过方案 A：在 qrenderdoc 内集成 `adb pair` / `adb connect` / `adb disconnect` / 手动 `IP:port` 管理，让无线 `adb` 先跑通，再复用整个现有 Android 抓帧链路。
- 绕过方案 B：若官方无线 `adb` 不可用，则开发 RenderDoc 自有 LAN pairing / discovery / remote host bootstrap，让 PC 能先连接到手机 RenderDoc app；但该路径默认只解决 `Milestone 1` 的连接/状态面，`Milestone 2` 是否能抓第三方 App 仍受 Android 调试权限限制。

### 第 4 轮：方案评估

#### 方案矩阵

| 方案 | 说明 | 成本 | 风险 | 适配里程碑 | 结论 |
| --- | --- | --- | --- | --- | --- |
| `方案 A` | 在 qrenderdoc 内集成官方无线 `adb` 配对/连接，继续使用 `adb` 协议控制器 | 中 | 低 | `M1 + M2` | 首选 |
| `方案 B` | 自研 LAN pairing / discovery / host bootstrap，但 capture/copy 仍复用现有 `RemoteServer + TargetControl` | 中到高 | 中 | `M1` 必达，`M2` 视设备而定 | 官方路径失败时立即启动 |
| `方案 C` | 完全绕过 `adb`，自研 Android 第三方游戏无线注入与抓帧 | 极高 | 极高 | 超出本轮可控范围 | 明确不选 |

建议：

- `/do` 首选执行 `方案 A`，因为它最能复用现有 RenderDoc 架构。
- 如果 `方案 A` 在目标设备群上不可用，**立即**启动 `方案 B`，但范围限定为：
  - 自研连接/发现/状态面；
  - 继续复用现有 capture/copy 协议；
  - 不在本轮承诺攻破 Android 平台权限边界。

## Build / Test / Lint Quick Guide

> `/plan` 阶段仅记录，不执行。

### 只读核查命令

- 协议/入口定位：
  - `rg -n "StartRemoteServer\\(|ExecuteAndInject\\(|adbForwardPorts\\(|TriggerCapture\\(|CopyCapture\\(" renderdoc qrenderdoc`
- UI 接线定位：
  - `rg -n "RemoteManager|LiveCapture|ConnectToRemoteServer|AddRemoteHost" qrenderdoc`
- Android loader / manifest：
  - `rg -n "renderdoccmd|Loader|INTERNET|MANAGE_EXTERNAL_STORAGE" renderdoccmd/android renderdoccmd`

### 构建命令（需用户授权后 /do 执行）

- Windows 主工程：
  - `msbuild renderdoc.sln /p:Configuration=Development /p:Platform=x64`
- 仅 GUI 本地验证：
  - `msbuild qrenderdoc/qrenderdoc_local.vcxproj /p:Configuration=Development /p:Platform=x64 /p:SolutionDir=D:\\Code\\git\\renderdoc\\`
- Android APK（如修改到 `renderdoccmd/android`）：
  - `cmake -S . -B build-android-arm64 -DBUILD_ANDROID=On -DANDROID_ABI=arm64-v8a`
  - `cmake --build build-android-arm64 -j8`

### 运行时验证命令（需用户授权后 /do 执行）

- 官方无线 `adb` 路径：
  - `adb pair <phone-ip>:<pair-port> <pair-code>`
  - `adb connect <phone-ip>:<debug-port>`
  - `adb devices -l`
- RenderDoc 运行态：
  - `renderdoccmd.exe --version`
  - `adb shell dumpsys package org.renderdoc.renderdoccmd.arm64 | findstr versionName`

### 预期输出

- `adb devices -l` 中能看到 `host:port` 形式的无线设备。
- qrenderdoc 的 Remote Hosts 列表中出现可连接 Android 设备。
- Live Capture 窗口能收到 `RegisterAPI` / `CaptureProgress` / `NewCapture` / `CaptureCopied`。

## File List（精确到当前热点范围）

### Android 协议与工具层

- `renderdoc/android/android_tools.cpp:175-368`
- `renderdoc/android/android.h:37-40`
- `renderdoc/android/android.cpp:647-667`
- `renderdoc/android/android.cpp:948-1311`
- `renderdoc/android/android.cpp:1340-1677`

### 通用远程协议层

- `renderdoc/core/remote_server.cpp:1281-1400`
- `renderdoc/core/target_control.cpp:662-712`
- `renderdoc/core/target_control.cpp:724-949`
- `renderdoc/core/target_control.cpp:964-1002`
- `renderdoc/core/core.cpp:657-680`
- `renderdoc/replay/entry_points.cpp:438-467`

### qrenderdoc 配置 / 连接 / UI 层

- `qrenderdoc/Code/Interface/RemoteHost.cpp:118-198`
- `qrenderdoc/Code/Interface/PersistantConfig.cpp:353-432`
- `qrenderdoc/Code/ReplayManager.cpp:164-211`
- `qrenderdoc/Code/ReplayManager.cpp:324-337`
- `qrenderdoc/Windows/Dialogs/RemoteManager.cpp:196-322`
- `qrenderdoc/Windows/Dialogs/RemoteManager.cpp:369-701`
- `qrenderdoc/Windows/Dialogs/RemoteManager.ui:16-130`
- `qrenderdoc/Windows/Dialogs/LiveCapture.cpp:1261-1415`

### Android RenderDoc app / loader 层

- `renderdoccmd/android/AndroidManifest.xml:1-19`
- `renderdoccmd/android/Loader.java:8-54`
- `renderdoccmd/renderdoccmd_android.cpp:403-470`

### 计划中允许新增的文件

- `qrenderdoc/Windows/Dialogs/AndroidWirelessSetupDialog.h`
- `qrenderdoc/Windows/Dialogs/AndroidWirelessSetupDialog.cpp`
- `qrenderdoc/Windows/Dialogs/AndroidWirelessSetupDialog.ui`
- 如 `android_tools.cpp` 改动超过可维护范围，可拆：
  - `renderdoc/android/android_wireless.h`
  - `renderdoc/android/android_wireless.cpp`

## Decisions

- 决定 1：官方无线 `adb` 是默认主路径；不先发明 `adbwifi://` 新协议名。
- 决定 2：现有协议名继续使用 `adb`，因为无线 `adb` 设备在 `adb devices` 中本质上仍是同一设备协议。
- 决定 3：`Milestone 1` 中“互相发送信息”解释为 **控制/状态消息闭环**，不要求第一版支持任意自定义文本消息。
- 决定 4：`Milestone 2` 中“获取最新截帧”优先复用 `NewCapture + CopyCapture`，不新写文件传输协议。
- 决定 5：若官方无线 `adb` 失败，则立即进入自研 fallback，但 fallback 先保证 `M1`，再评估 `M2` 对第三方 App 的可达性。

## Subagent 执行拓扑

### 目标

- 用尽可能多的 subagent 并行推进，但仍保持 **单一事实层**、**单一 capture 数据面**、**清晰文件边界**。
- 以 `Lead + 2 Explorers + 6 Workers + 1 Verifier` 的拓扑推进。
- 所有 subagent 都围绕同一计划执行，**只有 Lead 负责更新本计划文件**，避免计划文档冲突。

### Agent 列表

| Agent | 类型 | 推荐模型 | 责任 | 写入边界 |
| --- | --- | --- | --- | --- |
| `Lead` | 主代理 | 当前主模型 | 编排、集成、合流、计划维护 | 本计划文件 + 集成修补 |
| `Explorer-A` | `explorer` | `gpt-5.4-mini` | Android 无线 `adb` 与 `android.cpp` 路径精读 | 只读 |
| `Explorer-B` | `explorer` | `gpt-5.4-mini` | qrenderdoc RemoteHost / RemoteManager / LiveCapture 路径精读 | 只读 |
| `Worker-1` | `worker` | `gpt-5.3-codex` | Android 无线 `adb` helper、枚举与友好名 | `renderdoc/android/*` 指定文件 |
| `Worker-2` | `worker` | `gpt-5.3-codex` | `AndroidWirelessSetupDialog` 与 `RemoteManager` UI 接线 | `qrenderdoc/Windows/Dialogs/*` 指定文件 |
| `Worker-3` | `worker` | `gpt-5.3-codex` | `PersistantConfig` / `RemoteHost` 无线设备持久化与刷新 | `qrenderdoc/Code/Interface/*` 指定文件 |
| `Worker-4` | `worker` | `gpt-5.3-codex` | `LiveCapture` 最新 capture 拉取闭环 | `qrenderdoc/Windows/Dialogs/LiveCapture.*` |
| `Worker-5` | `worker` | `gpt-5.3-codex` | `ReplayManager` / 连接后体验与错误分层 | `qrenderdoc/Code/ReplayManager.cpp` |
| `Worker-6` | `worker` | `gpt-5.3-codex` | fallback 预研：手机 RenderDoc app 局域网最小入口 | `renderdoccmd/android/*`, `renderdoccmd/renderdoccmd_android.cpp` |
| `Verifier-1` | `worker` | `gpt-5.4-mini` | 构建/验证/回归清单执行与结果归档 | 默认只读；必要时仅写验证脚本/日志 |

### 为什么这样拆

- `Explorer-A/B` 先把已有代码热点钉住，避免多个 worker 重复探索。
- `Worker-1/2/3` 可并行完成 `Milestone 1` 的三大块：
  - Android 工具与协议侧
  - qrenderdoc UI 侧
  - 配置/持久化侧
- `Worker-4/5` 在 `Milestone 1` 基础上推进 `Milestone 2`，但写入边界彼此分离。
- `Worker-6` 从一开始并行做 fallback 预研，不阻塞主线，但能满足“如果官方路径不可用，立即转自研”的要求。
- `Verifier-1` 独立于实现 worker，避免“自己改、自己验、自己说没问题”。

## Branch / Worktree 布局

### 建议命名

| Agent | 分支名 | worktree 目录 |
| --- | --- | --- |
| `Lead` | `agent01/wireless-android-integration` | `D:\\Code\\git\\renderdoc-agent01-integration` |
| `Worker-1` | `agent01/wireless-android-tools` | `D:\\Code\\git\\renderdoc-agent01-w1` |
| `Worker-2` | `agent01/wireless-android-ui` | `D:\\Code\\git\\renderdoc-agent01-w2` |
| `Worker-3` | `agent01/wireless-android-config` | `D:\\Code\\git\\renderdoc-agent01-w3` |
| `Worker-4` | `agent01/wireless-livecapture` | `D:\\Code\\git\\renderdoc-agent01-w4` |
| `Worker-5` | `agent01/wireless-replay-flow` | `D:\\Code\\git\\renderdoc-agent01-w5` |
| `Worker-6` | `agent01/wireless-fallback-spike` | `D:\\Code\\git\\renderdoc-agent01-w6` |
| `Verifier-1` | `agent01/wireless-verifier` | `D:\\Code\\git\\renderdoc-agent01-v1` |

### 工作区规则

- 每个 worker 只在自己的 worktree 工作。
- 每个 worker 只能写自己负责的文件集合。
- 任何 worker 都 **不得** 回滚其它 worker 的改动。
- 任何共享文件冲突一律由 `Lead` 在集成 worktree 中解决。

## 并行开发流程

### Phase 0：先读代码，不写代码

- `Lead` 创建所有 worktree / branch。
- 同时启动：
  - `Explorer-A`
  - `Explorer-B`
  - `Worker-6`（fallback 预研）
- 这一步的目标不是改代码，而是把：
  - 主线可复用点
  - 官方无线 `adb` 关键失败点
  - fallback 最小闭环边界
  写成简短结论返回给 `Lead`。

### Phase 1：Milestone 1 主线并行

- 当 `Explorer-A/B` 返回后，`Lead` 同时启动：
  - `Worker-1`
  - `Worker-2`
  - `Worker-3`
- 预期并行关系：
  - `Worker-1` 负责 Android 工具侧与协议枚举。
  - `Worker-2` 负责无线向导与 `RemoteManager` 入口。
  - `Worker-3` 负责 host 持久化、刷新、友好名/显示行为。
- `Lead` 不等待全部完成后再行动；谁先完成谁先合流，但只做 **文件边界不重叠** 的提交。

### Phase 2：Milestone 1 集成与冒烟

- `Lead` 把 `Worker-1/2/3` 的提交按顺序 cherry-pick 到集成 worktree：
  1. `Worker-1`
  2. `Worker-3`
  3. `Worker-2`
- 合流后由 `Verifier-1` 执行：
  - 编译
  - `adb pair/connect`
  - Remote Host 刷新
  - target 枚举
- 若主线通过，进入 Phase 3。
- 若主线失败且原因指向“设备/ROM 不支持官方无线链路”，则立即并行提升 `Worker-6` 为正式 fallback 线。

### Phase 3：Milestone 2 并行

- `Lead` 在 `Milestone 1` 可用后，同时启动：
  - `Worker-4`
  - `Worker-5`
- 分工：
  - `Worker-4`：`LiveCapture` 中“最新 capture”状态和拉取动作。
  - `Worker-5`：`ReplayManager` / 连接后体验 / 错误文案与流程收束。

### Phase 4：Milestone 2 集成与回归

- `Lead` 合入 `Worker-4/5`。
- `Verifier-1` 执行：
  - 连通回归
  - 截帧进度回归
  - `NewCapture`
  - `CopyCapture`
  - 本地文件到达验证

### Phase 5：Fallback 决策

- 若官方主线能跑通：
  - `Worker-6` 只保留预研笔记，不进入主分支。
- 若官方主线在目标设备群不可用：
  - `Lead` 让 `Worker-6` 升级为正式实现线。
  - fallback 只承接：
    - `Milestone 1` 连接/状态面
    - `Milestone 2-limited` 在可捕获目标场景下的截帧/拉取
  - 不承诺突破 Android 平台权限边界。

## Subagent 协作协议

### 汇报格式

每个 subagent 结束时必须用固定格式回复：

- `Done`: 完成了什么
- `Files`: 改了哪些文件
- `Verification`: 跑了什么命令，结果如何
- `Risks`: 发现了什么风险
- `Next`: 建议 Lead 下一步怎么接

### 协作规则

- `Explorer` 只输出事实与证据，不提大而化之的重构建议。
- `Worker` 只能改自己拥有的文件；如果发现需要改别人文件，必须把建议交给 `Lead`。
- `Verifier-1` 默认不改业务代码；若确实需要修复小问题，必须先由 `Lead` 重新分派归属。
- `Lead` 是唯一可以：
  - 更新本计划文件
  - 调整边界
  - 解决跨 worker 冲突
  - 决定是否启用 fallback

### 失败升级规则

- 任一 worker 在同一问题上最多尝试 3 次。
- 第 3 次失败后，必须返回：
  - 已尝试方法
  - 精确错误
  - 推测根因
  - 推荐交接对象
- `Lead` 再决定：
  - 自己整合修复
  - 转交其它 worker
  - 启动 fallback

## 可直接使用的 Subagent Prompt

### Explorer-A Prompt

```text
你是 Explorer-A，负责只读分析 Android 无线 adb 接入路径。

任务目标：
1. 精读 renderdoc/android/android.cpp、android_tools.cpp、android.h。
2. 只回答这几个问题：
   - 现有 adb 设备枚举、StartRemoteServer、ExecuteAndInject 中，哪些逻辑天然支持无线 deviceID=host:port？
   - 哪些地方会因为无线 adb 引入额外问题？
   - Worker-1 需要改哪些精确函数，最小改法是什么？
3. 不写代码，不改文件。

证据要求：
- 每个结论必须附文件:行号。
- 明确区分“已支持 / 需修改 / 风险点”。

输出格式：
- Done
- Evidence
- Risks
- Recommended edit points

注意：
- 你不是一个人，代码库里会有其他 worker 并行工作。
- 不要建议大范围重构，只给最小实现路径。
```

### Explorer-B Prompt

```text
你是 Explorer-B，负责只读分析 qrenderdoc 的无线接入 UI 与 capture 流程热点。

任务目标：
1. 精读：
   - qrenderdoc/Windows/Dialogs/RemoteManager.cpp
   - qrenderdoc/Windows/Dialogs/RemoteManager.ui
   - qrenderdoc/Code/Interface/RemoteHost.cpp
   - qrenderdoc/Code/Interface/PersistantConfig.cpp
   - qrenderdoc/Windows/Dialogs/LiveCapture.cpp
2. 回答：
   - 无线 Android 配对应当挂在哪个 UI 入口最自然？
   - RemoteHost/PersistantConfig 里哪些点会影响无线 host 的显示/刷新？
   - LiveCapture 里“获取最新 capture”最小接线点是什么？
3. 不写代码，不改文件。

输出格式：
- Done
- Evidence
- UI recommendation
- Integration recommendation
- Risks

注意：
- 你不是一个人，其他 worker 会改这些周边模块。
- 不要提出跨 5 个文件的大重构，只给最小接线方案。
```

### Worker-1 Prompt

```text
你是 Worker-1，负责 Android 无线 adb 工具与协议枚举。

你拥有的文件：
- renderdoc/android/android_tools.cpp
- renderdoc/android/android.h
- renderdoc/android/android.cpp

你的目标：
1. 为 adb 新增 pair/connect/disconnect helper。
2. 让现有 Android 设备枚举和友好名路径对无线 deviceID=host:port 正常工作。
3. 不改变 USB adb 原行为。

严格边界：
- 不修改 qrenderdoc UI 文件。
- 不修改 LiveCapture。
- 不引入新协议名。

实现要求：
- 只做最小改动。
- 遵守 RenderDoc C++ 风格：显式类型、NULL、2 空格缩进、最小 STL。
- 修改完成后列出 changed files。

验证要求：
- 至少做代码级静态核查。
- 如果你能安全运行只读命令，可补充 rg/编译前检查。

输出格式：
- Done
- Files
- Verification
- Risks
- Notes for Lead

重要：
- 你不是一个人在代码库里工作。
- 不要回滚别人可能正在做的改动。
```

### Worker-2 Prompt

```text
你是 Worker-2，负责 qrenderdoc 无线 Android 配对/连接 UI。

你拥有的文件：
- qrenderdoc/Windows/Dialogs/AndroidWirelessSetupDialog.h
- qrenderdoc/Windows/Dialogs/AndroidWirelessSetupDialog.cpp
- qrenderdoc/Windows/Dialogs/AndroidWirelessSetupDialog.ui
- qrenderdoc/Windows/Dialogs/RemoteManager.cpp
- qrenderdoc/Windows/Dialogs/RemoteManager.ui

你的目标：
1. 新增无线 Android 配对/连接 dialog。
2. 在 RemoteManager 中新增入口，调用无线 pair/connect 流程。
3. 配对成功后刷新远程主机列表并尽量选中新出现的 adb://host:port。

严格边界：
- 不改 renderdoc/android/*。
- 不改 PersistantConfig / RemoteHost。
- 不改 LiveCapture。

实现要求：
- UI 保持与现有 qrenderdoc 风格一致。
- 优先小而明确，不要把 RemoteManager 改成第二套设备管理器。

输出格式：
- Done
- Files
- Verification
- Risks
- UI notes

重要：
- 你不是一个人在代码库里工作。
- 不要回滚其他 worker 的编辑。
```

### Worker-3 Prompt

```text
你是 Worker-3，负责无线 Android host 的持久化、刷新和展示一致性。

你拥有的文件：
- qrenderdoc/Code/Interface/RemoteHost.cpp
- qrenderdoc/Code/Interface/PersistantConfig.cpp

你的目标：
1. 确保无线 adb host 能被 PersistantConfig 正常枚举、刷新、复用旧状态。
2. 确保 RemoteHost 在无线 host 场景下的状态更新、连接、Launch 行为合理。
3. 不改变非 Android 远程主机的现有行为。

严格边界：
- 不改 RemoteManager UI。
- 不改 renderdoc/android/*。
- 不改 LiveCapture。

输出格式：
- Done
- Files
- Verification
- Risks
- Integration notes

重要：
- 你不是一个人在代码库里工作。
- 只修改你拥有的文件。
```

### Worker-4 Prompt

```text
你是 Worker-4，负责 LiveCapture 中“获取最新 capture”闭环。

你拥有的文件：
- qrenderdoc/Windows/Dialogs/LiveCapture.h
- qrenderdoc/Windows/Dialogs/LiveCapture.cpp

你的目标：
1. 基于现有 NewCapture / CopyCapture 机制，新增 latest capture 状态。
2. 在 UI 中提供“Get Latest Capture”或等价动作。
3. 不新建第二套文件传输协议，不扫描远端目录作为主实现。

严格边界：
- 不改 RemoteManager。
- 不改 renderdoc/android/*。
- 不改 ReplayManager。

实现要求：
- 优先复用现有消息循环。
- 失败路径要清晰：没有 capture、copy 失败、连接断开。

输出格式：
- Done
- Files
- Verification
- Risks
- UX notes

重要：
- 你不是一个人在代码库里工作。
- 不要碰别人负责的文件。
```

### Worker-5 Prompt

```text
你是 Worker-5，负责连接后体验与错误分层。

你拥有的文件：
- qrenderdoc/Code/ReplayManager.cpp

你的目标：
1. 收束无线 remote host 连接后的体验与错误文案。
2. 确保连接、断开、CopyCaptureFromRemote/ToRemote 路径在无线场景下提示清晰。
3. 不改变底层协议。

严格边界：
- 不改 LiveCapture。
- 不改 RemoteManager UI。
- 不改 renderdoc/android/*。

输出格式：
- Done
- Files
- Verification
- Risks
- Notes for integration

重要：
- 你不是一个人在代码库里工作。
- 只做最小范围收束，不做大重构。
```

### Worker-6 Prompt

```text
你是 Worker-6，负责 fallback 预研：当官方无线 adb 不可用时，手机 RenderDoc app 最小 LAN 连接方案。

你拥有的文件：
- renderdoccmd/android/AndroidManifest.xml
- renderdoccmd/android/Loader.java
- renderdoccmd/renderdoccmd_android.cpp

你的目标：
1. 只做最小预研，不默认合入主线。
2. 评估并实现最小入口，让手机侧更容易直接启动 RenderDoc remoteserver 并展示网络可连接状态。
3. 不承诺突破 Android 平台权限边界。

严格边界：
- 不改 qrenderdoc。
- 不改 renderdoc/android/* 主线 adb 协议。
- 不新写第二套 capture/copy 协议。

输出格式：
- Done
- Files
- Verification
- Risks
- Fallback viability

重要：
- 你不是一个人在代码库里工作。
- 这是 sidecar 预研，除非 Lead 明确要求，否则不要扩张范围。
```

### Verifier-1 Prompt

```text
你是 Verifier-1，负责独立验证无线 Android capture 方案。

你的职责：
1. 不负责业务实现，优先做独立验证。
2. 在 Lead 合入各 worker 改动后，执行：
   - 编译验证
   - adb pair/connect 验证
   - Remote Host 出现与连接验证
   - target 枚举验证
   - TriggerCapture / NewCapture / CopyCapture / CaptureCopied 验证
3. 只在 Lead 明确要求时创建小型验证脚本。

输出格式：
- Done
- Verification
- Failures
- Evidence
- Recommendation

重要：
- 你不是一个人在代码库里工作。
- 默认不改业务代码。
```

## 推荐 Spawn 顺序

1. `Explorer-A`
2. `Explorer-B`
3. `Worker-6`
4. `Worker-1`
5. `Worker-2`
6. `Worker-3`
7. `Verifier-1`（先待命，Milestone 1 合流后执行）
8. `Worker-4`
9. `Worker-5`

## Lead 的集成职责

- 在 subagent 返回后，Lead 先审：
  - 写入边界是否被遵守
  - 是否复用了现有协议
  - 是否偷建第二套系统
- 合流顺序建议：
  1. `Worker-1`
  2. `Worker-3`
  3. `Worker-2`
  4. `Verifier-1` 跑 `M1`
  5. `Worker-4`
  6. `Worker-5`
  7. `Verifier-1` 跑 `M2`
  8. 最后根据结果决定是否引入 `Worker-6`

## Milestones

### Milestone 1：无线连接与最小消息闭环

#### 目标

- PC 内完成 Android 无线配对/连接或手动录入。
- qrenderdoc 将无线 Android 设备视为可管理 `RemoteHost`。
- PC 能看到远端状态并建立 target control / remote server 会话。

#### 任务清单（2-5 分钟粒度）

- [x] 在 `renderdoc/android/android_tools.cpp` 中新增 `adb pair/connect/disconnect` helper，统一复用现有 `getToolPath()` 与 `execCommand()`。
- [x] 在 `renderdoc/android/android.h` 中声明新的无线 `adb` helper，保持 Android 工具层 API 明确。
- [x] 扩展 `renderdoc/android/android.cpp::EnumerateDevices()`，确认无线 `host:port` 设备与 USB 设备都能被识别并保留。
- [x] 在 `AndroidController::GetFriendlyName()` 路径上兼容无线 `deviceID`，避免 UI 只显示裸 `IP:port`。
- [x] 在 `qrenderdoc` 提供无线配对对话框（当前以内联 `AndroidWirelessSetupDialog` 落在 `RemoteManager.cpp`），支持：
  - 输入 pairing `IP:port`
  - 输入 pairing code
  - 输入 debug `IP:port`
  - 手动录入已连接无线设备
- [x] 在 `RemoteManager.ui` 中新增入口按钮或菜单项，触发无线 Android 配对/连接向导。
- [x] 在 `RemoteManager.cpp` 中接线：
  - 调用 `adb pair`
  - 调用 `adb connect`
  - 刷新 `PersistantConfig::UpdateEnumeratedProtocolDevices()`
  - 自动选中新出现的 `adb://host:port` 远程主机
- [x] 在 `RemoteHost.cpp` / `PersistantConfig.cpp` 中确认无线主机能被持久化、刷新、重连。
- [x] 在 `RemoteManager.cpp` 中补充状态显示：`Online / Offline / Busy / Version mismatch / Wireless`。
- [x] 使用现有 `RENDERDOC_CheckRemoteServerConnection()` 与 `RENDERDOC_EnumerateRemoteTargets()` 验证连接，而不是新造探活协议。
- [ ] 若官方无线 `adb` 连接失败，触发 fallback 决策记录，并切入 `M1-Fallback` 分支。

#### M1 Pseudo-code

```cpp
// renderdoc/android/android.h
namespace Android
{
Process::ProcessResult adbPairCommand(const rdcstr &hostPort, const rdcstr &pairCode);
Process::ProcessResult adbConnectCommand(const rdcstr &hostPort);
Process::ProcessResult adbDisconnectCommand(const rdcstr &hostPort);
}
```

```cpp
// renderdoc/android/android_tools.cpp
Process::ProcessResult adbPairCommand(const rdcstr &hostPort, const rdcstr &pairCode)
{
  return adbExecCommand("", "pair " + hostPort + " " + pairCode, ".", false);
}

Process::ProcessResult adbConnectCommand(const rdcstr &hostPort)
{
  return adbExecCommand("", "connect " + hostPort, ".", false);
}

Process::ProcessResult adbDisconnectCommand(const rdcstr &hostPort)
{
  return adbExecCommand("", "disconnect " + hostPort, ".", false);
}
```

```cpp
// qrenderdoc/Windows/Dialogs/RemoteManager.cpp
void RemoteManager::on_pairAndroidWireless_clicked()
{
  AndroidWirelessSetupDialog dlg(this);
  if(dlg.exec() != QDialog::Accepted)
    return;

  ResultDetails pairResult = Android::PairAndConnectWireless(
      dlg.PairingAddress(), dlg.PairCode(), dlg.DebugAddress());

  if(!pairResult.OK())
  {
    RDDialog::critical(this, tr("Wireless Pair Failed"), pairResult.Message());
    return;
  }

  m_Ctx.Config().UpdateEnumeratedProtocolDevices();
  RefreshHostListAndSelect(QString::fromUtf8(("adb://" + dlg.DebugAddress()).c_str()));
}
```

```cpp
// 连接验证继续复用现有路径
ResultDetails result = host.Connect(&server);
uint32_t ident = RENDERDOC_EnumerateRemoteTargets(host.Hostname(), 0);
ITargetControl *conn =
    RENDERDOC_CreateTargetControl(host.Hostname(), ident, GetSystemUsername(), true);
```

#### M1-Fallback（官方无线 adb 不可用时立即启动）

- [ ] 新增手机端“RenderDoc Wireless”最小入口页，展示 `IP`、版本、端口、连接状态。
- [ ] 允许手机端直接启动 `renderdoccmd remoteserver` 监听局域网。
- [ ] PC 端新增“Manual LAN RenderDoc Host”路径，直接添加 `host:port`。
- [ ] 用现有 `RENDERDOC_CheckRemoteServerConnection()` 验证手机 RenderDoc app 可连接。
- [ ] 用现有 `TargetControl` 或最小状态 RPC 显示版本/在线/忙碌状态。
- [ ] 记录 fallback 适用边界：本路径优先保证 `M1`，不在本 milestone 中承诺对任意第三方游戏做无线注入抓帧。

### Milestone 2：远程截帧、通知结果、同步最新 capture

#### 目标

- 用户在 PC 上远程触发截帧。
- 手机端目标进程成功执行截帧。
- PC 收到进度与结果。
- 用户可以在 PC 上一键获取最新 capture。

#### 任务清单（2-5 分钟粒度）

- [x] 复核 `LiveCapture.cpp` 当前 `TriggerCapture / CopyCapture` 路径，确认无线 `adb` 下无需额外协议改动。
- [x] 在 `AndroidController::StartRemoteServer()` 路径上验证无线设备 `deviceID=host:port` 时现有逻辑仍成立（基于源码复核）。
- [x] 在 `AndroidRemoteServer::ExecuteAndInject()` 路径上验证无线 `adb` 时（基于源码复核）：
  - `adb shell`
  - `adb forward`
  - `JDWP`
  - `setprop`
  仍使用同一 `deviceID` 即可工作。
- [x] 在 `RemoteManager` 或 `LiveCapture` UI 中新增“Get Latest Capture”动作。
- [x] 维护一个“最新 capture ID / path”状态缓存，优先基于现有 `NewCaptureData` 更新，而不是重新扫描手机文件系统。
- [x] 在收到 `TargetControlMessageType::NewCapture` 时，更新“latest capture”状态。
- [x] 在点击“Get Latest Capture”时，复用现有 `saveCapture()/CopyCapture(latestCaptureId, localPath)` 路径。
- [x] 在 `CaptureCopied` 回调中更新 UI，提供“Open Capture”或“Reveal in Folder”。
- [ ] 对失败路径补充细分文案：
  - 无活动 target
  - 远端 capture 失败
  - `CopyCapture` 失败
  - 网络断开
  - 版本不匹配
- [ ] 若无线 `adb` 无法支撑 `ExecuteAndInject()`，将问题归因到具体步骤（pair/connect/forward/JDWP/layer/app debuggable），并决定是否进入 fallback 的 `M2-limited`。

#### M2 Pseudo-code

```cpp
// qrenderdoc/Windows/Dialogs/LiveCapture.h
uint32_t m_LatestCaptureId = ~0U;
QString m_LatestCaptureTitle;
QString m_LatestCaptureSuggestedName;
```

```cpp
// qrenderdoc/Windows/Dialogs/LiveCapture.cpp
if(msg.type == TargetControlMessageType::NewCapture)
{
  NewCaptureData cap = msg.newCapture;
  m_LatestCaptureId = cap.captureId;
  m_LatestCaptureTitle = cap.title;
  m_LatestCaptureSuggestedName = SuggestCaptureFilename(cap);
  captureAdded(conn->GetTarget(), cap);
}
```

```cpp
void LiveCapture::on_getLatestCapture_clicked()
{
  if(m_LatestCaptureId == ~0U)
  {
    RDDialog::information(this, tr("No Capture"),
                          tr("No capture has been produced on the remote device yet."));
    return;
  }

  QString localPath = BuildLocalLatestCapturePath(m_LatestCaptureSuggestedName);
  m_CopyCaptureID = m_LatestCaptureId;
  m_CopyCaptureLocalPath = localPath;
  m_CopyCapture.release();
}
```

```cpp
if(msg.type == TargetControlMessageType::CaptureCopied)
{
  uint32_t capID = msg.newCapture.captureId;
  QString path = msg.newCapture.path;

  if(capID == m_LatestCaptureId)
    MarkLatestCaptureAsLocal(path);

  captureCopied(capID, path);
}
```

#### M2-limited（fallback 限定版）

- [ ] 如果 fallback 只保证手机 RenderDoc app 本身在线，但对第三方游戏缺少调试权限，则将 `Milestone 2` 限定为：
  - 对已具备可捕获 target 的场景执行远程截帧与回传；
  - 不虚报“所有游戏都可无线抓帧”。
- [ ] 在 UI 中明确失败归因，提示用户切换到官方无线 `adb` 路径或具备相应调试权限的设备。

## Impact Analysis

### 受影响模块

- Android 设备工具层：
  - 新增无线 `adb` 命令封装，但不改变现有 USB `adb` 逻辑。
- Android 协议控制器：
  - 继续使用协议名 `adb`，只增强设备接入路径。
- qrenderdoc 远程主机 UI：
  - 新增无线配对/连接入口、状态展示、最新 capture 拉取动作。
- Live Capture：
  - 增加“latest capture”概念，但仍复用原有消息循环和复制逻辑。

### 不应受影响模块

- `RemoteServer` 协议格式
- `TargetControl` 基础消息格式（除非 M1 演示确实需要新增一条最小状态消息）
- 各图形 API replay 驱动
- RDC 文件格式

### 兼容性影响

- USB `adb` 路径必须保持原样可用。
- 已有手工添加 IP 主机的非 Android 远程主机流程不能回归。
- 无线设备在 `adb devices` 中消失后，`PersistantConfig::UpdateEnumeratedProtocolDevices()` 需要优雅下线，不留下死 host。

## Risks / Blockers

- 风险 1：无线 `adb` 在不同 Android 厂商 ROM 上行为差异较大，`pair/connect` 成功不代表 `forward/JDWP/layer` 一定成功。
- 风险 2：`RemoteManager` 现有 UI 只有通用 host 输入框，若直接硬塞多字段无线配对流程，容易把旧 UI 弄乱；更适合独立 dialog。
- 风险 3：如果把官方无线 `adb` 与自研 LAN pairing 同时推进，容易形成两套接入语义和两套状态机，必须以单一路径为主。
- 风险 4：fallback 路径如果越界去承诺“无需 Android 调试权限也能抓任意第三方 App”，会在 `/do` 阶段失控。
- 风险 5：`Latest Capture` 若通过远端目录扫描实现，会和现有 `NewCapture` / `CopyCapture` 机制重复，增加一致性风险。

## Verification / Acceptance

### Milestone 1 DoD

- [ ] qrenderdoc 内可发起一次无线 Android pairing/connect 流程，或允许手动录入无线 `IP:port`。
- [ ] 无线设备能出现在 Remote Hosts 列表中，协议仍显示为 `adb`。
- [ ] 能通过现有远程连接流程把该设备连接为当前 remote host。
- [ ] 能枚举到至少一个 remote target ident。
- [ ] UI 能显示最小状态：`Online / Busy / Version mismatch / API status`。

### Milestone 2 DoD

- [ ] PC 端点击截帧后，Live Capture 能收到 `CaptureProgress` 或等价进度变化。
- [ ] 截帧成功后，PC 端能收到 `NewCapture`。
- [ ] 用户能点击“Get Latest Capture”把最新 capture 复制到 PC 本地。
- [ ] 复制完成后，PC 端能收到 `CaptureCopied`。
- [ ] 失败路径能区分：无线连接失败、target 启动失败、capture 失败、复制失败。

### 总体验收

- [x] 未引入第二套 Android 抓帧协议。
- [x] 未引入第二套 capture 文件传输协议。
- [ ] USB `adb` 原路径无回归。
- [x] 计划中的 fallback 仍然复用现有 `RemoteServer/TargetControl` 数据面。

## Next Steps

1. `/do` 先实现 `Milestone 1 / 方案 A`：qrenderdoc 内建无线 `adb pair/connect`。
2. 用最小真机链路验证：能看到无线设备、能连上 remote host、能枚举 target。
3. `/do` 再推进 `Milestone 2`：把“latest capture”拉取动作接到现有 `NewCapture + CopyCapture`。
4. 若 `Milestone 1 / 方案 A` 在目标设备上失败，则立即按本计划进入 `M1-Fallback`，但保持事实边界不变。

## 备注

- 本计划基于本地源码检索形成；仓库中未发现可直接调用的 Context MCP 工具，因此本轮证据来源标注为「基于本地检索（MCP unavailable）」。
- 本轮未生成 `.codex/tasks/*.xml`；如后续需要给并行执行者分发任务，可在 /do 前补充 XML 任务文档。

## /do Execution Log (Agent01, 2026-04-22)

- 18:35-18:50：进入 `/do`，先复核工作区与工程接线边界。
  - `git status --short` 显示仓库存在用户既有 `plans/*` 改动；本任务不回滚这些非本任务文件。
  - 新计划文件：`plans/2026-04-22-183501-Agent01-Wireless-Android-Capture.md`。
- 18:50-18:58：确认 qrenderdoc 新增对话框若落地，需要同步：
  - `qrenderdoc/qrenderdoc.pro`
  - `qrenderdoc/qrenderdoc_local.vcxproj`
  - `qrenderdoc/qrenderdoc_local.vcxproj.filters`
  - `qrenderdoc/CMakeLists.txt`（如构建系统需要显式列出）
- 18:58-19:05：按计划启动第一批并行 subagent（受线程上限限制，本轮先起 6 个）：
  - `Explorer-A`：Android 无线 adb 路径只读分析
  - `Explorer-B`：qrenderdoc UI/config/live-capture 只读分析
  - `Worker-1`：`renderdoc/android/*`
  - `Worker-2`：`RemoteManager + AndroidWirelessSetupDialog`
  - `Worker-3`：`PersistantConfig + RemoteHost`
  - `Worker-4`：`LiveCapture latest capture`
- 19:05-后续：Lead 本地跟踪工程文件、集成点与验证顺序，等待第一批 agent 返回后完成合流；本轮已完成静态验证并收口剩余回包，未启动构建命令。

### Worker-1 Status (2026-04-22 18:54)

- Done:
  - Added `adbPairCommand()`, `adbConnectCommand()`, and `adbDisconnectCommand()` in the Android tool layer.
  - Updated Android device enumeration to parse adb device state via whitespace, so `host:port` wireless IDs are preserved alongside USB IDs.
  - Wrapped wireless display names so enumerated `adb://host:port` hosts can show `Manufacturer Model (host:port)` when properties are available, with `host:port` fallback if they are not.
- Files:
  - `renderdoc/android/android.h`
  - `renderdoc/android/android_tools.cpp`
  - `renderdoc/android/android.cpp`
- Verification:
  - `git diff --check -- renderdoc/android/android.h renderdoc/android/android_tools.cpp renderdoc/android/android.cpp`
  - `clang-format --dry-run --Werror renderdoc/android/android.h renderdoc/android/android_tools.cpp renderdoc/android/android.cpp`
  - `rg -n "adbPairCommand|adbConnectCommand|adbDisconnectCommand|GetDeviceDisplayName|IsWirelessADBDeviceID|EnumerateDevices\\(" renderdoc/android/android.h renderdoc/android/android_tools.cpp renderdoc/android/android.cpp`
- Risks:
  - Wireless detection currently keys off a numeric suffix after the last `:`. This covers the intended `host:port` adb serials, but if future adb serial formats differ, the display-name wrapper may need widening.
  - No build was run in this worker turn, so compile/link validation still depends on lead-side integration or authorized build verification.
- Notes for Lead:
  - No new protocol name was introduced; protocol remains `adb`.
  - USB display behavior is unchanged unless a caller explicitly hits the new whitespace-tolerant enumeration path, which still preserves the same USB IDs.
  - If UI wiring wants a one-shot workflow, it can now call the new helpers directly without adding another adb command runner.

### Explorer-B Findings

- 无线入口应放在 `RemoteManager`，不要额外创建第二套 host manager。
- 配对成功后不能只调 `UpdateEnumeratedProtocolDevices()`，还必须同步刷新 `RemoteManager` 树并尝试重选新 host。
- “Get Latest Capture” 最小接线点应落在 `LiveCapture`，直接复用 `NewCapture + CopyCapture` 闭环，不扫描远端目录。

### Worker-2 Status

- Done:
  - 在 `RemoteManager.ui` 新增 `Pair Android over Wi-Fi...` 入口。
  - 在 `RemoteManager.cpp` 中新增无线配对对话框、host tree 同步辅助函数，以及 `on_pairAndroid_clicked()` 入口。
  - 配对成功后执行枚举刷新、host tree 同步，并优先选中新出现的 `adb://host:port` host。
- Lead Integration:
  - 原始实现里包含本地 `QProcess` adb runner。
  - Lead 已在合流时收口为统一调用 `renderdoc/android/*` 新增的 `Android::adbPairCommand()` / `Android::adbConnectCommand()`，避免形成两套 adb 入口。
- Risks:
  - 对话框当前以内联类形式保留在 `RemoteManager.cpp`；优点是避免额外工程文件接线，代价是该 cpp 体积变大。
  - 尚未做编译级验证。

### Worker-3 Status

- Done:
  - `PersistantConfig.cpp` 为无线 Android host 增加 merge/保留逻辑，避免自动管理 host 在离线后直接丢失。
  - `RemoteHost.cpp` 为无线 host 增加 refresh/retry 逻辑，在 Launch 前确认无线 adb 设备仍存在，并在 shutdown 后清理旧的 versionMismatch/versionError 状态。
- Verification:
  - Worker 报告格式化与 whitespace check 干净。
- Risks:
  - 尚未做编译级验证。

### Worker-4 Status

- Done:
  - 在 `LiveCapture` 中增加 latest-capture 状态、`Get Latest Capture` 按钮和状态文本。
  - 在 `NewCapture` / `CaptureCopied` / 断线路径上维护 latest-capture UI 状态。
  - 复用现有 `saveCapture()` / `CopyCapture` / `CaptureCopied` 闭环，没有新建文件传输协议。
- Verification:
  - `git diff --check -- qrenderdoc/Windows/Dialogs/LiveCapture.h qrenderdoc/Windows/Dialogs/LiveCapture.cpp qrenderdoc/Windows/Dialogs/LiveCapture.ui`
  - `py -3 -c "import xml.etree.ElementTree as ET; ET.parse(...LiveCapture.ui)"`（worker 回包为 `XML OK`）
- Risks:
  - target-control 协议只有成功态 `CaptureCopied`，没有单独 “copy failed” 消息，因此 UI 只能做最佳努力提示。
  - 尚未做编译级验证。

### Worker-5 Status

- Done:
  - `ReplayManager.cpp` 为无线 Android host 增加更贴近场景的连接失败文案。
  - 复制进度文案从通用 `Transferring...` 细化为上传/下载文案，并为无线 Android 单独提示。
- Scope:
  - 改动仅落在 `qrenderdoc/Code/ReplayManager.cpp`，不改协议、不改公开接口。
- Risks:
  - 无线 host 识别基于现有 `adb://host:port` / `_adb-tls` 命名形态，若未来 adb serial 形态变化，将自动回退到通用文案。
  - 尚未做编译级验证。

### Lead Integration Status

- Done:
  - 合并 `Worker-1/2/3/4/5` 改动到同一实现面。
  - 将 `RemoteManager.cpp` 的 adb 调用统一收口到 Android 工具层 helper，保留已有 UI 与 host tree 刷新逻辑。
  - 复核 `LiveCapture` latest-capture 实现，确认仍沿用现有 `saveCapture()` / `CopyCapture` 语义。
- Verification:
  - `clang-format -i qrenderdoc/Windows/Dialogs/RemoteManager.cpp qrenderdoc/Windows/Dialogs/RemoteManager.h qrenderdoc/Windows/Dialogs/LiveCapture.cpp qrenderdoc/Windows/Dialogs/LiveCapture.h qrenderdoc/Code/ReplayManager.cpp renderdoc/android/android.cpp renderdoc/android/android.h renderdoc/android/android_tools.cpp qrenderdoc/Code/Interface/PersistantConfig.cpp qrenderdoc/Code/Interface/RemoteHost.cpp`
  - `clang-format --dry-run --Werror renderdoc/android/android.h renderdoc/android/android.cpp renderdoc/android/android_tools.cpp qrenderdoc/Code/Interface/PersistantConfig.cpp qrenderdoc/Code/Interface/RemoteHost.cpp qrenderdoc/Code/ReplayManager.cpp qrenderdoc/Windows/Dialogs/RemoteManager.h qrenderdoc/Windows/Dialogs/RemoteManager.cpp qrenderdoc/Windows/Dialogs/LiveCapture.h qrenderdoc/Windows/Dialogs/LiveCapture.cpp`
  - `git diff --check -- renderdoc/android/android.h renderdoc/android/android.cpp renderdoc/android/android_tools.cpp qrenderdoc/Code/Interface/PersistantConfig.cpp qrenderdoc/Code/Interface/RemoteHost.cpp qrenderdoc/Code/ReplayManager.cpp qrenderdoc/Windows/Dialogs/RemoteManager.h qrenderdoc/Windows/Dialogs/RemoteManager.cpp qrenderdoc/Windows/Dialogs/RemoteManager.ui qrenderdoc/Windows/Dialogs/LiveCapture.h qrenderdoc/Windows/Dialogs/LiveCapture.cpp qrenderdoc/Windows/Dialogs/LiveCapture.ui`
  - `py -3 -c "import xml.etree.ElementTree as ET; ET.parse(r'qrenderdoc/Windows/Dialogs/RemoteManager.ui'); ET.parse(r'qrenderdoc/Windows/Dialogs/LiveCapture.ui'); print('XML OK')"`
- Result:
  - `git diff --check` 仅剩 `.ui` 文件的 Git 换行提示，无新的 whitespace 错误。
  - XML 解析通过。
- Risks:
  - 本轮没有用户授权运行 `msbuild`，因此所有改动都还缺少编译级验证与真机链路验证。
  - `RemoteManager` 尚未给 wireless host 增加显式 “Wireless” 状态标签，当前更多通过 `adb://host:port` host 形态与连接文案体现。
  - `Explorer-A` 未在本轮返回明确结论，因此 Android 协议侧的第二视角审阅仍不完整。

### Lead Build / Verification Update (2026-04-22 19:35-19:52)

- Done:
  - 复核本地 SSOT/计划入口，确认：
    - `AGENTS.md` 存在。
    - `plans/2026-04-22-183501-Agent01-Wireless-Android-Capture.md` 存在。
    - `docs/llm/ssot_index.md`、`docs/docs_index.md`、`sessions/UNKNOWN/SessionContext.md` 在当前仓库中不存在，本轮记录为「基于本地检索（MCP unavailable）」继续执行。
  - 定位 `ENABLE_UNIT_TESTS` 编译阻塞根因：
    - `qrenderdoc` 因为直接 include `renderdoc/common/*` 与 `renderdoc/android/*` 内部头，把 `QRDUtils.h` 的本地 `ENABLE_UNIT_TESTS` 宏与 `renderdoc/common/globalconfig.h` 的同名宏带进同一 TU，在 `/WX` 下转成错误。
  - 采用最小边界修复而不是修改全局宏：
    - `qrenderdoc/Windows/Dialogs/RemoteManager.cpp` 改为在 `qrenderdoc` 内部直接运行本地 `adb pair/connect`，不再 include `android/android.h`。
    - `qrenderdoc/Code/Interface/RemoteHost.cpp` 去掉 `common/result.h` 依赖，Launch 失败时回退为公共 `ResultCode`。
    - `qrenderdoc/Code/ReplayManager.cpp` 去掉 `common/result.h` / `common/formatting.h` 依赖，保留无线 host 识别和传输阶段文案。
    - `qrenderdoc/qrenderdoc.pro` 与 `qrenderdoc/qrenderdoc_local.vcxproj` 撤回对 `renderdoc/` 根 include path 的临时扩展。
- Verification:
  - `clang-format -i qrenderdoc/Windows/Dialogs/RemoteManager.cpp qrenderdoc/Code/Interface/RemoteHost.cpp qrenderdoc/Code/ReplayManager.cpp`
  - `git diff --check -- qrenderdoc/Windows/Dialogs/RemoteManager.cpp qrenderdoc/Code/Interface/RemoteHost.cpp qrenderdoc/Code/ReplayManager.cpp qrenderdoc/qrenderdoc.pro qrenderdoc/qrenderdoc_local.vcxproj`
  - `& 'E:\Program Files\Microsoft Visual Studio\2022\Community\MSBuild\Current\Bin\MSBuild.exe' qrenderdoc/qrenderdoc_local.vcxproj /p:Configuration=Development /p:Platform=x64 /p:SolutionDir=D:\Code\git\renderdoc\`
  - `Get-Item D:\Code\git\renderdoc\x64\Development\qrenderdoc.exe | Select-Object FullName, Length, LastWriteTime`
  - `py -3 -c "import xml.etree.ElementTree as ET; ET.parse(r'qrenderdoc/Windows/Dialogs/RemoteManager.ui'); ET.parse(r'qrenderdoc/Windows/Dialogs/LiveCapture.ui'); print('XML OK')"`
  - `& 'D:\Code\git\renderdoc\x64\Development\qrenderdoc.exe' --version`
- Result:
  - `git diff --check` 仅剩工程文件的 LF/CRLF 提示，无新的 whitespace 错误。
  - `qrenderdoc_local.vcxproj` 编译通过：`0 warnings / 0 errors / 00:00:35.68`。
  - 成功产出 `D:\Code\git\renderdoc\x64\Development\qrenderdoc.exe`。
  - `RemoteManager.ui` / `LiveCapture.ui` XML 解析通过。
  - `qrenderdoc.exe --version` 以退出码 `0` 完成，作为最小非交互 smoke test 通过。
- Risks:
  - 仍缺少真机链路验证，尚未实际确认：
    - 无线 pairing/connect
    - remote target 枚举
    - 真正的截帧与 latest-capture 拉取
  - 为保持 `qrenderdoc` 与 `renderdoc` 内部头边界干净，`ReplayManager` 的无线连接失败提示当前回退到更通用的 `ResultDetails` 文案；如果后续需要更细分的人类可读提示，建议在 qrenderdoc UI 层做映射，不要重新 include `common/result.h`。

### Lead Milestone-2 UX Update (2026-04-22 20:00-20:13)

- Done:
  - `LiveCapture` 增加轻量请求状态，区分：
    - 等待 target 上报新 capture
    - latest-capture 正在复制
    - 连接关闭导致 capture 请求未完成
    - 连接关闭导致 latest-capture 复制未完成
  - `LiveCapture` 的 latest-capture 区域补充了更细的文案/tooltip：
    - 没有 capture
    - 本地文件丢失
    - 需要切 replay context
    - remote server version mismatch
    - remote server busy
    - copy 无法启动
  - `LiveCapture` 的截帧按钮补充了可用性解释：
    - 尚未建立 live target connection
    - 还没上报 API
    - API unsupported
    - API not presenting
  - `RemoteManager` 主列表状态追加 `Wireless` 标签，并在选择无线 Android host 时把详情区切成更准确的无线说明：
    - `Android Endpoint:`
    - `Run Command: Launched automatically over adb...`
    - `Start via ADB`
- Files:
  - `qrenderdoc/Windows/Dialogs/LiveCapture.cpp`
  - `qrenderdoc/Windows/Dialogs/LiveCapture.h`
  - `qrenderdoc/Windows/Dialogs/RemoteManager.cpp`
- Verification:
  - `clang-format -i qrenderdoc/Windows/Dialogs/LiveCapture.cpp qrenderdoc/Windows/Dialogs/LiveCapture.h qrenderdoc/Windows/Dialogs/RemoteManager.cpp`
  - `git diff --check -- qrenderdoc/Windows/Dialogs/LiveCapture.cpp qrenderdoc/Windows/Dialogs/LiveCapture.h qrenderdoc/Windows/Dialogs/RemoteManager.cpp`
  - `& 'E:\Program Files\Microsoft Visual Studio\2022\Community\MSBuild\Current\Bin\MSBuild.exe' qrenderdoc/qrenderdoc_local.vcxproj /p:Configuration=Development /p:Platform=x64 /p:SolutionDir=D:\Code\git\renderdoc\`
  - `& 'D:\Code\git\renderdoc\x64\Development\qrenderdoc.exe' --version`
- Result:
  - `qrenderdoc_local.vcxproj` 再次编译通过：`0 warnings / 0 errors / 00:00:07.65`。
  - `qrenderdoc.exe --version` 以退出码 `0` 完成，最小 smoke test 通过。
- Risks:
  - `TargetControl` 现有协议没有显式 `CaptureFailed` 消息，因此“远端 capture 失败”目前仍只能通过：
    - API 不可捕获提示
    - latest-capture 未更新
    - 连接关闭时的 best-effort 文案
    这三类信号组合归因；如果后续测试发现这还不够，需要评估是否扩协议。
  - 当前无线状态展示已经有 `Wireless` 标签和 endpoint/ADB 说明，但仍是最小增强版，没有单独的 “Waiting for enumeration” 持久状态位。

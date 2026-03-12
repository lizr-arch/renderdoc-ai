# 计划：AgentD / M0-C Android Launch 失败分类统一

时间：2026-03-11 17:06:59 | 负责人：AgentD

## Scope / Assumptions

- 目标：完成 `M0-C`，把 Android launch 失败从“零散报错”收束成“错误分类 + 用户原因 + 修复建议 + 详细诊断入口”。
- 本计划只处理 Android launch 失败统一化，不重做 Android preflight 诊断，不重做 analyzer 导出。
- 负责人是新的执行 Codex；Lead 只负责设计和验收，不参与代码实现。

## Already Done

以下内容已完成，本计划禁止重做：

- [x] `CaptureDialog` 已实现 Android preflight 结构化诊断（`blockers / warnings / suggestions`）。
- [x] `CaptureDialog` 已替代旧的 Android 单条警告弹窗。
- [x] Analyzer 导出已写出 `capture_context.json`。
- [x] `qrenderdoc_local.vcxproj` 已通过一次完整构建验证。

## Evidence Base

- 总体边界：`docs/product/development_charter.md`
- Android 总计划：`plans/2026-03-10-211515-AgentA-Android-Capture-Access.md`
- 当前 Android preflight 实现：`qrenderdoc/Windows/Dialogs/CaptureDialog.cpp`
- 当前 launch 失败入口：`qrenderdoc/Windows/MainWindow.cpp`
- Android 结果码定义：`renderdoc/api/replay/replay_enums.h`
- Android 结果码文案：`renderdoc/api/replay/renderdoc_tostr.inl`
- Android 底层产生错误码的位置：`renderdoc/android/android.cpp`

## File List

- `qrenderdoc/Windows/MainWindow.h`
- `qrenderdoc/Windows/MainWindow.cpp`
- 如确有必要，可极小修改：`qrenderdoc/Windows/Dialogs/CaptureDialog.h`
- 如确有必要，可极小修改：`qrenderdoc/Windows/Dialogs/CaptureDialog.cpp`
- 当前计划文件本身

## Do Not Touch

- `qrenderdoc/Code/Analyzer/AnalyzerExporter.*`
- `qrenderdoc/Windows/AnalyzerReportViewer.*`
- `tools/mcp/*`
- `scripts/rdc_analyzer/*`
- `docs/product/snapshot_schema_v1.md`

## Task Checklist

- [x] 整理当前 Android launch 相关失败码：`JDWPFailure`、`AndroidLayerConfFailed`、`AndroidAPKInstallFailed`、`InjectionFailed`。
- [x] 建立稳定映射：`ResultCode -> 用户原因 -> 修复建议 -> 是否建议查看详细诊断`。
- [x] 统一 `MainWindow` 中 Android launch 失败处理，避免同类错误走不同文案。
- [x] 区分 `InjectionFailed` 中的超时与通用注入失败。
- [x] 为 Android 失败增加“查看详细诊断”或等价入口。
- [x] 更新计划文件，写明执行结果与验证命令。

## Error Mapping Target

| ResultCode | 用户可读原因 | 修复建议重点 |
| --- | --- | --- |
| `JDWPFailure` | 调试连接未建立 | 关闭 Android Studio；检查 debuggable；检查设备允许调试；检查 intent 参数 |
| `AndroidLayerConfFailed` | Android GPU debug layer 配置失败 | 检查 RenderDoc remote app / layer 安装与设备支持 |
| `AndroidAPKInstallFailed` | 安装 RenderDoc Android APK 或相关组件失败 | 检查 `adb`、USB 安装权限、设备连接、存储权限 |
| `InjectionFailed` | 注入或等待应用启动失败 | 区分超时、进程启动失败、通用注入失败；提示提高 timeout 或检查启动参数 |

## Pseudo-code

```cpp
struct AndroidLaunchDiagnosis
{
  ResultCode code;
  QString title;
  QString message;
  QStringList actions;
  bool offerDetails = false;
};

AndroidLaunchDiagnosis MainWindow::BuildAndroidLaunchDiagnosis(const ExecuteResult &ret)
{
  switch(ret.result.code)
  {
    case ResultCode::JDWPFailure: ...
    case ResultCode::AndroidLayerConfFailed: ...
    case ResultCode::AndroidAPKInstallFailed: ...
    case ResultCode::InjectionFailed: ...
    default: ...
  }
}
```

## Decisions

- 决定 1：M0-C 只收束 Android launch 失败路径，不扩展到其它平台或其它失败体系。
- 决定 2：优先复用现有 `ResultCode` 与 RenderDoc 原始错误信息，不重造错误码。
- 决定 3：详细诊断入口是对现有 preflight 的补充，不是第二套 Android 配置向导。

## Risks / Blockers

- `MainWindow.cpp` 中 Android 失败处理已存在局部特判，改动时要避免和已有 generic error path 冲突。
- 详细诊断入口如果依赖 `CaptureDialog` 状态，需注意最小接口设计，避免引入新的 UI 耦合。
- 错误码映射若写得太“智能”，容易掩盖原始 `ret.result.Message()`，必须保留原始错误文本。
- 构建授权已获得并执行验证；此前 `qrenderdoc` 因基线缺失文件失败（`AnalyzerReport*/PerformanceReport*` 与 `PerfReportLight.qss`），已在用户同步基线后解除。

## Verification / Acceptance

- [x] `qrenderdoc` 构建通过。
- [x] `JDWPFailure` 有专门文案，不再仅显示通用 launch 失败。
- [x] `AndroidLayerConfFailed` 有专门文案与动作建议。
- [x] `AndroidAPKInstallFailed` 有专门文案与动作建议。
- [x] `InjectionFailed` 至少区分“超时”与“其它注入失败”。
- [x] Android launch 失败路径保留原始错误文本，便于进一步排查。

## Next Steps

1. 在真实 Android 设备上最小回归：分别触发 4 类错误码，确认文案和入口行为。

## /do Execution Log (AgentD, 2026-03-11)

- 读取并确认边界文档：`D:\Code\git\renderdoc\AGENTS.md`、`D:\Code\git\renderdoc\docs\product\development_charter.md`、`D:\Code\git\renderdoc\docs\debug\session_archives\2026-03-11-RenderDoc-AI-Program-Control\HANDOFF.md`、`D:\Code\git\renderdoc\plans\2026-03-11-170659-AgentD-M0C-Android-Launch-Diagnose.md`。
- 为遵守“只在当前 worktree 开发”，将计划文件同步到：`D:\Code\git\renderdoc-agentd\plans\2026-03-11-170659-AgentD-M0C-Android-Launch-Diagnose.md`，后续只回写该文件。
- 修改文件：
  - `qrenderdoc/Windows/MainWindow.h`：新增 `showAndroidLaunchFailure(...)` 声明。
  - `qrenderdoc/Windows/MainWindow.cpp`：
    - 新增 Android 错误码识别与 `InjectionFailed` 超时判定辅助函数。
    - `OnCaptureTrigger` 改为统一调用 `showAndroidLaunchFailure(...)`，移除单独 `JDWPFailure` 老特判。
    - `showLaunchError` 接入同一 Android 诊断映射，并通过 `GUIInvoke::call` 保持 UI 线程弹窗。
    - 新增“Open Launch Application for detailed Android diagnosis?” 入口按钮，点击后打开 Launch Application 面板。
- 执行命令与结果：
  - `clang-format -i qrenderdoc/Windows/MainWindow.h qrenderdoc/Windows/MainWindow.cpp` -> 成功。
  - `clang-format -i qrenderdoc/Windows/MainWindow.cpp`（线程安全修补后二次格式化） -> 成功。
  - `git diff --check -- qrenderdoc/Windows/MainWindow.h qrenderdoc/Windows/MainWindow.cpp plans/2026-03-11-170659-AgentD-M0C-Android-Launch-Diagnose.md` -> 无输出（通过）。
  - `git status --short` -> `M qrenderdoc/Windows/MainWindow.cpp`、`M qrenderdoc/Windows/MainWindow.h`、`?? plans/2026-03-11-170659-AgentD-M0C-Android-Launch-Diagnose.md`。
- 本轮明确未执行：
  - Android preflight 重跑（按要求禁止重做）。
  - analyzer 导出（按要求禁止重做）。
- 用户授权变更：
  - 用户于本轮明确授权“同意构建，以后均可以自动构建”，后续会话内构建类命令可自动执行。
- 构建尝试与结果（授权后）：
  - `msbuild renderdoc.sln /p:Configuration=Development /p:Platform=x64 /m` -> 失败（环境 `msbuild` 不在 PATH）。
  - `E:\...\MSBuild.exe renderdoc.sln /p:Configuration=Development /p:Platform=x64 /m /nologo /verbosity:minimal` -> 失败。
    - 失败摘要：`qrenderdoc` 构建链路存在基线缺失文件/资源（`AnalyzerReportWidgets.h`、`PerformanceReportViewer.h/.ui`、`PerfReportLight.qss` 等）。
    - 日志同时暴露一处 M0-C 新增代码编译错误：`Windows\\MainWindow.cpp(85): error C2661`。
  - 已修复 `C2661`：`IsInjectionTimeout` 改为 `ToQStr(result.Message()).contains(...)`。
  - `E:\...\MSBuild.exe qrenderdoc\\qrenderdoc_local.vcxproj /p:Configuration=Development /p:Platform=x64 /p:SolutionDir=D:\\Code\\git\\renderdoc-agentd\\ /m /nologo /verbosity:minimal` -> 失败（同样为基线缺失文件）。
    - 日志检索：未再出现 `MainWindow.cpp(85)`/`C2661`，仅剩基线缺失文件错误。
    - 日志文件：`test_output/m0c_qrenderdoc_build.log`。
  - `E:\...\MSBuild.exe renderdoc.sln /p:Configuration=Development /p:Platform=x64 /m /nologo /verbosity:minimal`（修复 `C2661` 后二次全量验证） -> 失败（同样为基线缺失文件）。
    - 全量日志检索：未出现 `MainWindow.cpp(85)`/`C2661`，只剩 `AnalyzerReport*/PerformanceReport*` 缺失与 `PerfReportLight.qss` 缺失。
    - 日志文件：`test_output/m0c_full_build_after_fix.log`。
  - 用户同步基线缺失文件后，`E:\...\MSBuild.exe renderdoc.sln /p:Configuration=Development /p:Platform=x64 /m /nologo /verbosity:minimal`（三次全量验证） -> 成功（退出码 0）。
    - 关键产物：`qrenderdoc_local.vcxproj -> ...\\qrenderdoc.exe`、`...\\qrenderdoc.pdb`。
    - 日志检索：无 `error C*`、无 `MSB6006`、无 `C2661`、无报告线缺失文件错误。
    - 日志文件：`test_output/m0c_full_build_after_sync.log`。
  - 设备回归前置检查：
    - `where.exe adb` -> 成功（`C:\\Users\\lizhirui01\\AppData\\Local\\Android\\Sdk\\platform-tools\\adb.exe`）。
    - `adb devices -l` -> 无在线设备。
    - 结论：设备侧 4 错误码回归需要用户接入 Android 设备并做最小手工触发。
  - 截图问题（`AndroidAPKFolderNotFound`）定位与修复：
    - 源码定位：`renderdoc/android/android.cpp` 在 `InstallRenderDocServer` 中优先查找 `<libDir>/plugins/android/` 下的 `org.renderdoc.renderdoccmd.*.apk`。
    - 本地检查：worktree 原先无任何 `.apk`，导致弹窗“RenderDoc APK not found...”。
    - 修复动作：从已安装 RenderDoc 复制 `org.renderdoc.renderdoccmd.arm32.apk`、`org.renderdoc.renderdoccmd.arm64.apk` 到 `D:\\Code\\git\\renderdoc-agentd\\x64\\Development\\plugins\\android\\`。
    - 影响说明：仅补齐运行时 Android server APK 资源，不改代码逻辑，不影响 M0-C 实现边界。
  - 基线同步（用户要求“先从基线更新代码”）：
    - 环境现状：当前 shell 无 `git` 可执行（`git`/`git.exe`/`where git` 均不可用）。
    - 降级方案：按文件级从主仓库 `D:\\Code\\git\\renderdoc` 同步到当前 worktree `D:\\Code\\git\\renderdoc-agentd`，并保留 M0-C 的 `MainWindow.*` 本线改动。
    - 已同步文件：`AnalyzerReportWidgets.*`、`PerformanceReportViewer.*`、`PerformanceReportModels.*`、`PerformanceReportWidgets.*`、`Resources/PerfReportLight.qss`。
    - 校验：上述文件 SHA256 与主仓库一致（`SYNCED`）。
  - 用户复测反馈：
    - 用户运行路径：`D:\\Code\\git\\renderdoc\\x64\\Development\\qrenderdoc.exe`（主仓库可执行）。
    - 说明：此前 APK 补齐发生在 worktree `D:\\Code\\git\\renderdoc-agentd\\x64\\Development\\plugins\\android\\`，若运行主仓库可执行，仍会看到旧报错。
  - 版本不兼容（`Unsupported version`）根因与修复：
    - 现象：设备端 APK `versionName` 为 `e7f0b0ea67a5f931d5f718ff4d4cf6474b30c7c0`，桌面端 `renderdoccmd --version` 为 `NO_GIT_COMMIT_HASH_DEFINED_AT_BUILD_TIME`。
    - 根因：构建时 `renderdoc_version` 未读到 git commit，导致 host 版本签名与 APK 不一致。
    - 修复动作：使用显式提交号重建：
      - `E:\\...\\MSBuild.exe renderdoc.sln /p:Configuration=Development /p:Platform=x64 /p:CommitId=e7f0b0ea67a5f931d5f718ff4d4cf6474b30c7c0 /m /nologo /verbosity:minimal`
      - 中途遇到 `LNK1168`（`renderdoc.dll` 被 `qrenderdoc.exe` 占用），关闭 `qrenderdoc.exe` 后重建通过（退出码 0）。
    - 修复后校验：
      - `renderdoccmd --version` -> `built from e7f0b0ea67a5f931d5f718ff4d4cf6474b30c7c0`。
      - `adb shell dumpsys package org.renderdoc.renderdoccmd.arm64|arm32 | findstr versionName` -> 均为 `e7f0...`。

## /do Execution Log (AgentD, 2026-03-12 - Android 143 APK Alignment)

- 本轮目标：按用户锁定方案在当前 worktree 生成与 PC `v1.43` 对齐的 Android APK（`versionCode=143`，`versionName=e7f0...`），并覆盖到 `x64/Development/plugins/android/`。
- 现状确认：
  - `x64/Development/plugins/android/org.renderdoc.renderdoccmd.arm32.apk` 与 `arm64.apk` 初始均为 `versionCode='142'`（`aapt dump badging`）。
  - 这与 host `v1.43` 不一致，是 `Unsupported version` 循环的直接触发条件。
- 构建执行（用户已授权自动构建）：
  - 采用 Windows CMake + Ninja 路线，显式传入 `-DBUILD_VERSION_HASH=e7f0b0ea67a5f931d5f718ff4d4cf6474b30c7c0`。
  - arm32：`cmake -S . -B build-android-arm32 ... -DANDROID_ABI=armeabi-v7a ...` + `cmake --build build-android-arm32 -j8`。
  - arm64：`cmake -S . -B build-android-arm64 ... -DANDROID_ABI=arm64-v8a ...` + `cmake --build build-android-arm64 -j8`。
- 构建阻塞与处理（均为构建环境层，不涉及产品接口）：
  - 阻塞 1：`include-bin` 生成阶段调用默认 `c++`，环境缺失该命令。
    - 处理：使用 `-DHOST_NATIVE_CPP_COMPILER=...` 指定主机编译器。
  - 阻塞 2：`HOST_NATIVE_CPP_COMPILER` 带空格路径在 Ninja 命令中转义异常。
    - 处理：新增临时构建辅助脚本 `build-android-tools/host-clangpp.cmd`（仅构建流程使用，不改业务逻辑）。
  - 阻塞 3：Windows 下 `include-bin` 无扩展名不可被 `cmd` 直接执行。
    - 处理：仅在各自 build 目录修补生成的 `build.ninja`，将 `include-bin` 调用名改为 `include-bin.exe`（不改仓库源码）。
  - 说明：以上为构建层 workaround，目的是完成用户锁定的“同版本产物”交付，不影响 M0-C 功能代码。
- 构建结果：
  - `build-android-arm32/bin/org.renderdoc.renderdoccmd.arm32.apk` 生成成功。
  - `build-android-arm64/bin/org.renderdoc.renderdoccmd.arm64.apk` 生成成功。
  - 两者 `aapt dump badging` 均为：
    - `versionCode='143'`
    - `versionName='e7f0b0ea67a5f931d5f718ff4d4cf6474b30c7c0'`
- 运行目录覆盖：
  - 已复制到 `D:\\Code\\git\\renderdoc-agentd\\x64\\Development\\plugins\\android\\`。
  - 覆盖后再次 `aapt` 校验，arm32/arm64 仍为 `143 + e7f0...`。
- Host 版本复核：
  - `D:\\Code\\git\\renderdoc-agentd\\x64\\Development\\renderdoccmd.exe --version`
  - 输出：`renderdoccmd x64 v1.43 built from e7f0b0ea67a5f931d5f718ff4d4cf6474b30c7c0`。
- 设备清理（为 GUI 复测准备）：
  - `adb devices -l`：设备在线 `d6ce4623 / V1829A`。
  - `adb uninstall org.renderdoc.renderdoccmd.arm32` -> `Success`。
  - `adb uninstall org.renderdoc.renderdoccmd.arm64` -> `Success`。
  - `adb kill-server` + `adb start-server` 后设备仍在线。
  - `adb shell pm list packages | findstr renderdoc` 无输出（说明旧 RenderDoc 包已清理）。
- 用户实机回归结果（2026-03-12）：
  - `adb shell dumpsys package org.renderdoc.renderdoccmd.arm64 | findstr /R "versionCode versionName"`：
    - `versionCode=143`
    - `versionName=e7f0b0ea67a5f931d5f718ff4d4cf6474b30c7c0`
  - `adb shell dumpsys package org.renderdoc.renderdoccmd.arm32 | findstr /R "versionCode versionName"`：
    - `versionCode=143`
    - `versionName=e7f0b0ea67a5f931d5f718ff4d4cf6474b30c7c0`
  - GUI 结果：`Launch` 成功，`Capture` 成功，`Unsupported version` 循环问题已解除。
- 本轮未执行：
  - Android preflight（按要求不重做）。
  - analyzer 导出（按要求不重做）。

## /do Execution Log (AgentD, 2026-03-12 - Windows Android Build Workaround Script)

- 目标：将本次 Windows Android `include-bin` workaround 固化为可重复执行脚本，避免后续手工 patch/手工拷贝。
- 新增文件：
  - `scripts/build_android_aligned.ps1`
    - 功能：
      - 自动发现/设置 `JAVA_HOME`、`ANDROID_SDK*`、`ANDROID_NDK*`（支持参数覆盖）。
      - 自动生成 `build-android-tools/host-clangpp.cmd`，用于稳定指定 `HOST_NATIVE_CPP_COMPILER`。
      - 对 `build-android-arm32/build.ninja` 与 `build-android-arm64/build.ninja` 自动执行 `include-bin` -> `include-bin.exe` patch。
      - 支持一键执行 arm32+arm64 configure/build（`cmake + ninja`）。
      - 产物 `aapt dump badging` 校验（确保 `versionName` 与传入 commit 一致）。
      - 自动覆盖到 `x64/Development/plugins/android/` 并二次校验。
      - 可选 `-ResetDevicePackages` 执行 adb 卸载与重连。
- 说明（边界与影响）：
  - 该脚本只影响构建流程，不修改 RenderDoc 业务代码/协议/API。
  - `build.ninja` patch 仅发生在 build 输出目录，不是源码提交内容。
- 脚本验证：
  - 在当前 worktree 执行：
    - `.\scripts\build_android_aligned.ps1 -CommitHash e7f0b0ea67a5f931d5f718ff4d4cf6474b30c7c0 -SkipBuild`
  - 结果：通过（exit code 0），完成：
    - arm32/arm64 `build.ninja` patch；
    - build 产物 APK 校验；
    - `x64/Development/plugins/android/` 覆盖与校验；
    - 版本保持 `versionCode=143`、`versionName=e7f0...`。

## /do Execution Log (AgentD, 2026-03-12 - M0 Test Progress)

- T1（non-debuggable 路径）：
  - 用户截图显示 `Debuggable: No`、`Status: Blocked`、`Package is not debuggable...`，判定符合预期。
- T2（Injection timeout 路径）：
  - 通过将 `Settings > Android > Max Connection Timeout` 调低并触发等待，用户命中超时弹窗：
    - `Reason: Timed out while waiting for the app process to start.`
    - `Raw error: RenderDoc injection failed: Timeout was reached waiting for app to start.`
  - 该结果符合 `InjectionFailed(timeout)` 预期分支，判定通过。
- T3 准备阶段（2026-03-12）：
  - 用户当前截图为 `Invalid executable: com.netease.matchone/#DefaultActivity`。
  - 该错误属于“本地可执行路径解析失败/启动模式不正确”，不是 `AndroidAPKInstallFailed` 目标错误码。
  - 需要先切回 Android host 选择与包列表选择流程，再继续 T3 安装失败验证。
  - 用户设备约束：旧版本手机无“通过 USB 安装应用”开关；无法通过关闭该开关稳定制造安装失败。
  - 替代验证策略：通过临时替换无效 APK（保留同名）触发安装失败路径，验证 `AndroidAPKInstallFailed` 文案与分支。
  - 按用户要求由 Agent 代执行步骤 1-3：
    - 已备份：
      - `x64/Development/plugins/android/org.renderdoc.renderdoccmd.arm32.apk.bak`
      - `x64/Development/plugins/android/org.renderdoc.renderdoccmd.arm64.apk.bak`
    - 已将 `x64/Development/plugins/android/org.renderdoc.renderdoccmd.arm64.apk` 覆写为无效测试内容（22 bytes）。
    - `adb uninstall org.renderdoc.renderdoccmd.arm32|arm64` 返回 `DELETE_FAILED_INTERNAL_ERROR`，但后续 `pm list packages | findstr renderdoc` 无输出，判定当前设备上无 RenderDoc server 包驻留。
  - 用户执行第 4 步时出现 `No executable selected`，表明 Launch 面板中未正确选择 Android package/activity（仍在本地 executable 启动语义），尚未进入 APK 安装路径验证。
  - 与用户确认后，终止“强制破坏 APK 触发安装失败”的手工路径（设备交互成本高且不稳定）。
  - 已恢复现场：
    - `x64/Development/plugins/android/org.renderdoc.renderdoccmd.arm32.apk` 恢复为 `versionCode=143`, `versionName=e7f0...`。
    - `x64/Development/plugins/android/org.renderdoc.renderdoccmd.arm64.apk` 恢复为 `versionCode=143`, `versionName=e7f0...`。
  - 恢复后用户回归（Launch + Capture）结果：成功。

## /do Execution Log (AgentD, 2026-03-12 - Baseline Merge Closeout)

- 目标：
  - 按用户指令完成“提交代码并合并到基线”，并交付给其它负责人复检。
- 已完成操作（在基线 worktree `D:\\Code\\git\\renderdoc-release-main-bootstrap`）：
  - `fetch renderdoc-ai codex/agentd/m0c-android-launch`
  - `cherry-pick d8b61bd48` -> 基线新提交 `c7d1f9762`
  - `cherry-pick 605ae5547` -> 基线新提交 `4b8002d75`
  - `push renderdoc-ai HEAD:codex/integration/renderdoc-ai-20260311-linear-v2`
- 推送结果：
  - 远端更新成功：`2420da9cc..4b8002d75`。
- 合流内容（最小范围）：
  - `qrenderdoc/Windows/MainWindow.cpp`
  - `qrenderdoc/Windows/MainWindow.h`
  - `scripts/build_android_aligned.ps1`
  - `plans/2026-03-11-170659-AgentD-M0C-Android-Launch-Diagnose.md`（随提交同步）
- 校验状态：
  - Git 级校验通过：基线分支本地 `ahead 2` 后成功推送，提交链完整。
  - 产物级校验受限：基线目录当前无现成 `x64/Development/renderdoccmd.exe` 与 `x64/Development/plugins/android/*.apk`，无法直接执行二进制版本命令；需由后续负责人在基线工作区构建后复检。
- 约束遵循：
  - 未重做 preflight。
  - 未重做 analyzer 导出。
  - 未扩展 M0-C 之外产品范围。

## /do Execution Log (AgentD, 2026-03-12 - Baseline Branch Correction)

- 背景：
  - 用户指出本任务基线应为 `codex/integration/renderdoc-ai-20260311`，不是 `codex/integration/renderdoc-ai-20260311-linear-v2`。
- 纠正动作（在 `D:\\Code\\git\\renderdoc-integration` worktree）：
  - `fetch renderdoc-ai codex/agentd/m0c-android-launch`
  - `cherry-pick d8b61bd48` -> `56308e4c2`
  - `cherry-pick 605ae5547` -> `5a9654def`
  - `push renderdoc-ai HEAD:codex/integration/renderdoc-ai-20260311`
- 结果：
  - 真实基线分支已包含本任务两条代码提交。
  - 远端分支推送成功，等待其它负责人继续复检。

## /do Execution Log (AgentD, 2026-03-12 - D Branch Cleanup & Final Alignment Gate)

- 用户验收要求（本轮）：
  - 清理 D 工作区污染（至少 tracked clean）。
  - 处理 D 分支剩余 2 个 `docs(plan)` 提交。
  - 给出最终对齐验收口径结果。
- 实施动作：
  - 在 `D:\\Code\\git\\renderdoc-agentd` 执行 `git restore`，仅回滚非 D 边界的 tracked 变更：
    - `qrenderdoc/Resources/PerfReportLight.qss`
    - `qrenderdoc/Windows/AnalyzerReportWidgets.*`
    - `qrenderdoc/Windows/PerformanceReportModels.*`
    - `qrenderdoc/Windows/PerformanceReportViewer.*`
    - `qrenderdoc/Windows/PerformanceReportWidgets.*`
  - 清理后 `status --porcelain` 仅剩 `test_output/` 下 3 个 untracked 日志，tracked 项为 0。
  - 选择“合入基线”方案处理 2 个 docs 提交，在 `D:\\Code\\git\\renderdoc-integration` 执行：
    - `cherry-pick f6437df48` -> `10cf1f220`
    - `cherry-pick 400c0afce` -> `8d70ddd4f`
    - `push renderdoc-ai HEAD:codex/integration/renderdoc-ai-20260311`（成功）
- 最终口径检查：
  - 功能口径（M0-C 代码提交已入基线）：通过（`56308e4c2`, `5a9654def`）
  - 分支口径（`agentd_is_ancestor`）：当前为 `False`（cherry-pick 合流模型，非 merge 祖先链）
  - 工作区口径（D 分支 tracked clean）：通过

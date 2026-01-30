# RenderDoc 建议命令（Windows / 通用）

> 说明：本仓库 `Agents.md` 要求“构建类命令需用户授权”。这里仅记录常用命令，不自动执行。

## 搜索 / 导航
- 文本搜索：`rg -n "pattern" renderdoc/`
- 语法搜索（若安装 sg）：`sg -g "*.cpp" 'class_spec(name == "ReplayController")'`

## 格式化（C++）
- 使用 `clang-format`（RenderDoc 文档建议 clang-format 15.0，见 `docs/CONTRIBUTING.md`）。
- 常用：`clang-format -i <file1> <file2> ...`

## 构建（需用户授权）
- Windows (Visual Studio / MSBuild)：`msbuild renderdoc.sln /p:Configuration=Development /p:Platform=x64`
- Linux/Mac (CMake)：
  - `cmake -DCMAKE_BUILD_TYPE=Debug -Bbuild -H.`
  - `make -C build`
- Android：
  - `cmake -DBUILD_ANDROID=On -DANDROID_ABI=armeabi-v7a -Bbuild-android -H.`
  - `make -C build-android`

## 测试
- 目前官方文档说明测试主要是 ad-hoc（见 `docs/CONTRIBUTING/Testing.md`）。

## Python（本机环境注意事项，来自 Agents.md）
- 强制用 `py -3`（避免系统 python 指向 2.7）：例如 `py -3 scripts/sync_plans_index.py`

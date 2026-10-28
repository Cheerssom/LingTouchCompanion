# 灵触·随行 · LingTouch Companion

将视觉信息转换为触觉阵列反馈的辅助感知项目。当前实验使用手机摄像头、电脑端深度推理和 ESP32-S3，输出为 15 个六点模组，共 90 个触点。

当前交接与文件状态见 [CLAUDE.md](CLAUDE.md)。失败渲染已删除，阵列目录只保留源场景和工具；PCB 草稿仍未获装配或电气验证。

## 项目入口

| 目录 | 用途 |
|---|---|
| [experiments/chi2027/visionss/](experiments/chi2027/visionss/README.md) | 当前实验：米制深度、俯视栅格、BLE 传输与日志 |
| [experiments/chi2027/single_point/](experiments/chi2027/single_point/README.md) | 共用实验通路的单点告警对照条件 |
| [hardware/firmware/](hardware/firmware/README.md) | ESP32-S3 固件、引脚与通信协议 |
| [archive/app/frontend/](archive/app/frontend/README.md) | uni-app 手机应用 |
| [agent/backend/](agent/backend/README.md) | 地图、命令解析与视觉帧转发服务 |
| [archive/vision/](archive/vision/README.md) | 旧图像平面视觉管线，保留作回退 |
| [hardware/models/3mf/](hardware/models/3mf/README.md) | 前件、后件与两件式手柄的模型、完整生成代码及必要输入 |
| [PCB 修订稿](hardware/pcb/PCB_REDESIGN_2026-10-08/README.txt) | 五页原理图及实际板、98×98 mm 测试板的未布线布局草稿 |
| [阵列源文件与工具](hardware/models/BrailleModule_Video/ArrayPreview/README.md) | 离线编排与 JSON 渲染工具；当前场景外观未获认可 |
| [视频选定底图](image_prompt_comparison_2026-10-10/10_centered_original_scene.png) | 经过生成式编辑与实拍触点合成；来源见同目录 source.json，不能当原始实拍 |

## 运行实验

在仓库根目录、配置好依赖的 Python 环境中运行：

```powershell
python experiments/chi2027/visionss/phone_server.py
```

本机已验证环境为 `D:\anaconda\envs\LING\python.exe`。模型准备、手机连接与操作见 [实验说明](experiments/chi2027/visionss/README.md)。

## 浏览器工具

| 文件 | 用途 |
|---|---|
| [depth_preview.html](experiments/chi2027/depth_preview.html) | 图片深度预览；先运行 `python experiments/chi2027/visionss/depth_server.py` |
| [ble_mobile_controller.html](hardware/tools/ble_mobile_controller.html) | 手机 BLE 点阵控制，使用 ROT180 映射 |
| [ble_testbench.html](hardware/tools/ble_testbench.html) | 点阵与帧数据调试，保留旧 PROD 映射 |

BLE 页面需要浏览器提供 Web Bluetooth；两种映射不同，须与实际装配方向对应。

离线标定和距离验证见 [experiments/chi2027/TOPDOWN_VALIDATION.md](experiments/chi2027/TOPDOWN_VALIDATION.md)，工具为 `experiments/chi2027/validate_distance.py`、`check_balloon_depth.py` 和照片复制脚本 `prep_new_pics.py`。

## 端侧工程（2026-10-28 合入）

端侧目标形态是 CS30 深度相机（加 IMU）戴在头上、直插手机或平板，由手机或平板完成计算，再通过蓝牙把点阵发给手柄。新栅格为 9 列 × 6 行，每格 40 cm，覆盖左右 ±1.8 m、前方 1.0–3.4 m。已有论文实验通路保留在 `experiments/chi2027/`。

| 目录 | 归属与内容 |
|---|---|
| [core/](core/README.md) | 大家共用：C++17 类型、接口、参数、点阵编码与外壳门面 |
| [perception/](perception/README.md) | 视觉同学：CS30 取流、拆帧、几何与 0/1/2 栅格；协议材料和实验位 |
| [agent/](agent/README.md) | 对话 agent 同学：语音与 agent 接口、导航和命令解析后端 |
| [apps/](apps/README.md) | 交互同学：安卓 Kotlin、鸿蒙 ArkTS 外壳 |
| [hardware/](hardware/README.md) | Hsinlung：固件、模型、PCB、头戴方案与 BLE 工具 |
| [experiments/chi2027/](experiments/chi2027/README.md) | Hsinlung：已有论文实验通路 |
| [docs/](docs/) | [方案](docs/plans/)、[10/28 交接](docs/plans/HANDOFF_2026-10-28.md)、[报告](docs/REPORT_2026-10-28.md)、[真机验收](docs/device_tests.md) |
| [archive/](archive/) | 保留旧 uni-app 前端、旧 vision、比赛版 LingTouch.zip 和 10/09 云端交接 |

| 要做的事 | 入口 |
|---|---|
| 编译与测试共用核心 | `cmake -S core -B build/core` → `cmake --build build/core` → `ctest --test-dir build/core --output-on-failure`（CMake ≥ 3.16、C++17） |
| 安卓 App | Android Studio 打开 `apps/android/`，需要 SDK 35、NDK、CMake 3.22.1 |
| 鸿蒙 App | DevEco Studio 打开 `apps/harmony/`，系统 ≥ HarmonyOS 5.1.0 / API 18 |
| 深度帧检查 | `build/core/perception_tests/lt_frame_tool grid 帧文件 perception/cs30/calibration_0.bin`；平面检查把 `grid` 换成 `plane`（Windows 使用对应 `.exe`） |
| 导航与命令服务 | 在 `agent/backend/` 运行 `npm ci`、`npm start` |
| 模型与手柄资料 | 在 `hardware/models/` 下按模型 README 执行；新板手柄见 [拧扣榫交接](hardware/models/3mf/Handle_TwistKey_2026-10-27/HANDOFF.md) |

端侧内容目前是工程骨架。云端主机测试、两端构建和真机测试的边界见 [10/28 报告](docs/REPORT_2026-10-28.md)；状态 2 的触点表示、相机参数及手柄方向仍按验收清单确认。

## 本机文件与目录迁移

`pics/`、`Depth-Anything-V2/`、权重、`experiment_runs/`、`.pcba-workflow/`、密钥、依赖、论文材料和本地归档留在本机。实验脚本优先用 `LINGTOUCH_ROOT`，否则向上查找 `.git` 定位仓库根。

建模运行时在 `hardware/models/3mf/.runtime/structural-runtime/Scripts/python.exe`；建模命令在 `hardware/models/` 下执行。`hardware/models/.pcba-workflow` 联接到根目录的原资料。迁移脚本 [migrate_local_2026-10-28.ps1](docs/migrate_local_2026-10-28.ps1) 负责移动旧路径下的本机文件，支持 `-DryRun`，不覆盖同名文件。

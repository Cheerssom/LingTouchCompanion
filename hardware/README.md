# hardware — 硬件（Hsinlung）

| 目录 | 内容 |
|---|---|
| [firmware/](firmware/README.md) | ESP32-S3 触觉固件（当前 V2.8）、引脚与 BLE 协议 |
| [models/](models/3mf/README.md) | 3D 模型：`3mf/`（前件、后件、手柄、新板手柄、榫卯测试）、`BrailleModule/`、`BrailleModule_Video/`，三个目录同级、内容原样 |
| [pcb/](pcb/PCB_REDESIGN_2026-10-08/README.txt) | PCB 修订稿（10/08 五页原理图与两份未布线布局） |
| [headset/](headset/glass.md) | 头戴部分方案（`glass.md`） |
| [tools/](tools/) | 浏览器 BLE 调试页：`ble_mobile_controller.html`（ROT180 映射）、`ble_testbench.html`（旧 PROD 映射） |

**建模命令在 `hardware/models/` 下执行。** 各模型 README 里写的“从仓库根运行”（例如 `./3mf/.runtime/structural-runtime/Scripts/python.exe -B 3mf/regenerate.py --require-baseline`）指的就是这个目录：三个模型目录互相用 `../../3mf/…`、`parents[1]` 引用，所以保持同级、内容一个字节没改。本机的 `3mf/.runtime/` 等被忽略的文件要用 `docs/migrate_local_2026-10-28.ps1` 挪过来；`Handle_NewPCB_2026-10-20` 的脚本读 `.pcba-workflow/`，迁移脚本会在本目录下建指向仓库根 `.pcba-workflow` 的目录联接。

模型里的 C:/ 绝对路径和少数断链是移动前就有的，作为历史记录原样保留。

# perception/cs30 — CS30 协议材料

10/25 在 Hsinlung 电脑上做的 CS30（USB 2207:0016）免 SDK 取流结论，先读 [REPORT.md](REPORT.md)。

| 文件 | 内容 |
|---|---|
| `REPORT.md` | 结论：USB 上传的就是 640×480 uint16 毫米深度；启动序列、帧格式、帧率、停流与恢复 |
| `startup_sequence.json` | SDK 实际发出的 41 条控制请求（含切换接口与挂等时传输）；C++ 表由 `perception/native/tools/gen_startup_sequence.py` 从它生成 |
| `independent_proof.py` | PC 端独立实现（PyUSB + libusb，Windows），可当协议参考；运行时会在旁边写 `independent_runs/` |
| `calibration_0.bin`、`calibration_1.bin` | 两份 763 字节标定 blob（640×480 与 320×240，无 schema 解码见 `perception/native/include/lingtouch/perception/cs30_calibration.h`） |
| `reference_000/020/040.bin`、`reference_frames.json` | 3 张真实深度帧（基本是近场数据）及元数据 |
| `validation.json` | 10/25 的比对结果 |
| `compare_frames.py` | 比较两帧原始深度（真机验收第 1、2 条） |
| `android_evidence_README.md`、`libusb_android_README.txt` | UVCCamera 与上游 libusb 安卓方案的说明快照 |

厂家 SDK 的二进制、反汇编、strings 不进仓库（`.gitignore` 已挡住 `capture_runs/`、`independent_runs/`、`packages/`、`android_evidence/` 和 `.dll`）。

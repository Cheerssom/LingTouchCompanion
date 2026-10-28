# core — 端侧核心（大家共用）

C++17、CMake，不依赖任何平台接口。安卓（Kotlin，经 JNI）和鸿蒙（ArkTS，经 Node-API）都只调 `lingtouch/engine.h`。以后加 iOS 只多一层 Swift 外壳。

| 位置 | 内容 |
|---|---|
| `include/lingtouch/types.h` | 深度帧（时间戳、内参版本）、9×6 栅格（0/1/2 与每格诊断）、地面估计 |
| `include/lingtouch/modules.h` | 按《视觉方案 v1.0》第 9 节命名的模块接口：SensorAdapter、Registration、GroundPose、GeometryGrid、RGBInstance、SpatialLMService、EvidenceFusion、OutputAdapter / TactileEncoder |
| `include/lingtouch/inference.h` | 推理后端（鸿蒙 MindSpore Lite、安卓 ONNX Runtime）与大模型（llama.cpp）接口，本次只有接口 |
| `include/lingtouch/tactile.h` | 点阵编码：本次只有旧板（V2.8 固件，FFE0/FFE1/FFE3，15 字节） |
| `include/lingtouch/config.h`、`config/lingtouch_defaults.conf` | 全部参数。`.conf` 是唯一来源，编译时嵌入，两个平台用同一份 |
| `include/lingtouch/engine.h` | 给外壳的门面：启动序列、按批收包、后台算栅格、编码 |

感知部分（CS30 协议、拆帧、几何、0/1/2）在 [`perception/native`](../perception/native/README.md)，语音和 agent 接口在 [`agent/native`](../agent/native/README.md)，都由本目录的 `CMakeLists.txt` 一起编进 `lingtouch_engine`。

## 主机上编译和测试

```bash
cmake -S core -B build/core -G Ninja
```

```bash
cmake --build build/core
```

```bash
ctest --test-dir build/core --output-on-failure
```

需要 CMake ≥ 3.16 和支持 C++17 的编译器。`legacy_vectors_up_to_date`、`startup_sequence_up_to_date` 两项要 Python 3（前者还要 numpy，缺 numpy 时跳过）。

## 几条约定

- **状态 2 的触点表示没有默认值。** `encode_legacy_frame` 和 `Engine::encode_legacy` 都必须显式传 `UnknownCellPolicy`；配置 `tactile.unknown_cell_policy` 留空，注明“待 Hsinlung 定”，App 发帧前让使用者手选。
- **左右镜像和 ROT180 是显式参数**（`tactile.mirror_left_right`、`tactile.module_rot180`），默认沿用现有行为（都为 true），真机手摸确认。
- **两个平台对同一帧输出要完全一致。** 编译时关掉 FMA 合并、不用 fast-math（`lingtouch_target_defaults`）；判决只用加减乘除和 sqrt，随机数用自带的 SplitMix64，不用平台相关的 std 分布。
- 编码器与 `experiments/chi2027/visionss/frame_converter.py` 逐字节对比：向量由 `tools/gen_legacy_vectors.py` 生成，见 `tests/data/legacy_vectors.txt`。
- 新板（9+1 个模组）等固件定了再加一个 `TactileEncoder` 实现，别的模块不动。

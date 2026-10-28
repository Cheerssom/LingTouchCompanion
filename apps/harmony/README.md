# apps/harmony — 鸿蒙外壳（交互同学，平板优先）

ArkTS，Stage 模型。外壳只放只能用平台接口的东西：USB 授权与传输、蓝牙、长时任务、界面；启动表、拆帧、栅格、点阵编码都在 C++ 核心里（经 Node-API 调 `libentry.so`，源码 `entry/src/main/cpp/napi_init.cpp`）。

```
pages/Index.ets
 ├─ usb/Cs30Usb.ets  主路径：usbManager 执行启动表 → usbSubmitTransfer 挂 10 个等时传输
 │                    → 每个传输回调调一次 core.pushIsoTransfer（按批，32 个微帧）
 │                    备选：getFileDescriptor → core.openFd → native libusb（与安卓同一流程）
 ├─ device/HandleLink.ets  BLE FFE0：写 FFE1（15 字节），FFE3 通知 0x01 刷新完成 / 0x04 按键（取自 9/29 比赛版）
 └─ common/KeepAlive.ets  长时任务：bluetoothInteraction + location
```

## 编译（本地，DevEco Studio）

打开 `apps/harmony/`，配置签名后运行。`compatibleSdkVersion` / `targetSdkVersion` 都是 `5.1.0(18)`：`usbSubmitTransfer`、`UsbDataTransferParams`、等时传输类型在 OpenHarmony 文档里都是 API 18 起。DevEco 装的 SDK 更新时可以只调高 `targetSdkVersion`。`modelVersion` 沿用 9/29 比赛版工程的 `6.0.0`，与 DevEco 版本不符时按 IDE 提示改。

native 部分由 `entry/src/main/cpp/CMakeLists.txt` 把仓库里的 `core/` 整体编进 `libentry.so`。备选路径要编 libusb 的 Linux 后端；在鸿蒙 NDK 下编不过时，把该文件里的 `LINGTOUCH_HARMONY_LIBUSB` 改成 `OFF`，主路径不受影响。

**云端没有编译**：没有鸿蒙 SDK / DevEco。云端做过的检查：
- `napi_init.cpp` 用 Node-API 头文件（与鸿蒙 NAPI 接口相同）做了语法检查（开、关 libusb 两种），并编成 Node 插件跑了 `tools/napi_host_test.js`：启动表 44 步、标定分片拼接、参考帧切成等时包后拼出 1 帧、栅格 JSON、状态 2 策略必须显式、15 字节帧，全部通过。这不等于在鸿蒙上跑过。
- ArkTS 没有经过编译器检查（云端没有 ArkTS 编译器）。

## 界面

- 两个连接按钮分别走主路径和备选路径；真机清单要求两条都测。
- 9×6 栅格按行显示（· 空、■ 障碍、? 未知），每行有读屏文字（accessibilityText）。
- 没连设备显示“未连接”，拿不到的值不显示；帧率只在开流后用实测帧数算。
- 状态 2 的触点表示（平 / 凸）待 Hsinlung 定：配置里没设定时不预选，必须手选才能发帧。
- “持续发送”“后台运行”两个开关配合真机清单第 4 条（息屏/后台 10 分钟）。
- “平面检查”在界面线程上同步计算（建 4 张查表），平板上可能卡一两秒。

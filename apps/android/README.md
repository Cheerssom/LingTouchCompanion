# apps/android — 安卓外壳（交互同学）

Kotlin，不依赖 AndroidX。外壳只放只能用平台接口的东西：USB 授权与打开、蓝牙、前台服务、界面；取流协议、拆帧、栅格、点阵编码都在 C++ 核心里（经 JNI 调 `core/include/lingtouch/engine.h`）。

```
MainActivity ── USB 授权（先要 CAMERA 权限）→ UsbManager.openDevice → fd
StreamService（前台服务 connectedDevice + PARTIAL_WAKE_LOCK）
   ├─ NativeCore.nativeOpenCamera(fd) → libusb_wrap_sys_device → 启动序列 → 10 个等时传输 → 核心拆帧、算栅格
   └─ HandleLink：BLE FFE0，写 FFE1（15 字节），FFE3 通知 0x01 刷新完成 / 0x04 按键
```

## 编译（本地）

用 Android Studio 打开 `apps/android/`，或在该目录运行：

```bash
./gradlew assembleDebug
```

需要 Android SDK 35、NDK、CMake 3.22.1（SDK Manager 里装）。版本：AGP 8.7.3、Kotlin 2.0.21、Gradle 8.11.1、minSdk 29、只编 arm64-v8a。native 部分由 `app/src/main/cpp/CMakeLists.txt` 把仓库里的 `core/` 整体编进来，另出一个独立的 `libusb-1.0.so`（LGPL，不静态链接）。

**云端没有编出 APK**：Gradle 的 `google()` 仓库（dl.google.com）在云端会话里不可达，Android SDK/NDK 也装不了。云端做过的检查：
- native：用主机编译器（JNI 头取自 JDK）完整编译、链接 `liblingtouch_jni.so` 和 `libusb-1.0.so`；
- Kotlin：在一个临时 JVM 工程里，以 Robolectric `android-all:14`（API 34 框架类）为编译依赖编译全部 `.kt`，无错误、无警告。没有经过 AGP、资源合并和 Manifest 检查。

## 界面

- 连接相机 → 显示开流状态；9×6 栅格按行显示（· 空、■ 障碍、? 未知），每行的读屏文字是“第 N 行（X 到 Y 米）：空，障碍，未知…”。
- 没连设备显示“未连接”；没有的值不显示（帧率只在开流后用实测帧数计算）。
- 状态 2 的触点表示（平 / 凸）待 Hsinlung 定：配置里没设定时不预选，必须手选才能发帧。
- “持续发送”供真机后台测试：每次手柄刷新完成（或 1.5 s 超时）后发最新一帧。
- “平面检查”：对着平整的墙或斜看地面，比较光轴 Z / 径向、去不去畸变四种假设的平面残差。

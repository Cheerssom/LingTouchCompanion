# 真机验收清单（2026-10-28 骨架）

合并后在本地照着测。每条记下：机型与系统版本、日期、结果（通过/不通过/没测）、数字、截图或日志位置。
“通过”只指真的跑过并看到结果；没跑的写“没测”。

## 0. 准备

1. 合并分支后先运行本机迁移脚本（只移动、不删除，先演练）：
   ```powershell
   powershell -ExecutionPolicy Bypass -File docs\migrate_local_2026-10-28.ps1 -DryRun
   ```
   ```powershell
   powershell -ExecutionPolicy Bypass -File docs\migrate_local_2026-10-28.ps1
   ```
2. 电脑上跑一遍核心测试（需要 CMake 和 C++17 编译器）：
   ```bash
   cmake -S core -B build/core && cmake --build build/core && ctest --test-dir build/core --output-on-failure
   ```
3. 编出两个 App：安卓用 Android Studio 打开 `apps/android/`；鸿蒙用 DevEco Studio 打开 `apps/harmony/`（签名自己配）。云端两个都没编过，第一次编译的报错请记下来。
4. 供电：CS30 手册写 5V、平均 0.6A、约 3W，描述符里的 500mA 不作数。手机/平板带不动（开流失败、反复断开）就接带电源的 Hub 或分线器，记下用的是哪种。

## 1. 安卓：开流收帧，与厂家 SDK 对比，记录帧率

1. 安卓 App：「连接相机」→ 允许 CAMERA 和 USB 授权 → 状态变成“已开流”（Commit 本身约 2.4 秒）。
2. 看「拼帧」在涨、「丢弃不完整」「包错误」「UVC 错误位」接近 0；记下「处理帧率」（实测，最近 2 秒）。REPORT 里 PC 上默认积分时间约 14.05 帧/秒。
3. 标定：设备摘要里的内参应为 `cs30:HV0130315L0294:640x480:fnv1a64-f5bb174e726f0ff8:inferred`（与 `perception/cs30/calibration_0.bin` 同一份 blob）。不同就说明分片拼接或序列号对不上，记下完整摘要。
4. 与 SDK 对比：**手机上不能跑厂家 SDK，做不到 10/25 那种“同一次曝光、哈希一致”。** 改用“先后两次曝光”的比对：
   - 相机固定在三脚架上、场景不动；手机上「保存当前帧」，把 `Android/data/com.lingtouch.companion/files/latest_frame.bin` 拷到电脑；
   - 不动相机，接到电脑上用厂家 SDK（或 `perception/cs30/independent_proof.py`）存一帧；
   - 运行 `python perception/cs30/compare_frames.py latest_frame.bin 电脑那帧.raw`。REPORT 的参考：差值中位数约 3 mm、P95 约 12 mm。明显更大、或有效像素的位置整体错开，就是拆帧或协议有问题。
5. 内核驱动：若开流报 `claim 接口 … 失败`，说明系统的 uvcvideo 占着接口、自动 detach 没成功，记下报错。

## 2. 鸿蒙平板：同上，另记 usbSubmitTransfer 路径的帧率和丢包；两条路径都测

系统需 ≥ HarmonyOS 5.1.0（API 18）。

1. **主路径**「连接相机（usbSubmitTransfer）」：同第 1 条的 1–4 步。另记：
   - 「回调」「回调错误」「丢弃不完整」「包错误」，以及帧率能否到 PC 上的约 14 帧/秒；
   - 没有拼出帧时先确认：回调里的 `buffer` 是否真的装着数据、`isoPacketDescs` 是否有 32 项（文档没写清，代码按“数据在 buffer 里、第 i 个包从各包申请长度之和处开始”处理）；
   - `UsbTransferFlags` 文档只有 SHORT_NOT_OK / FREE_BUFFER / FREE_TRANSFER / ADD_ZERO_PACKET 四个值，代码用的是 SHORT_NOT_OK。若短包被当成错误（回调错误很多），记下来；
   - 接口 1 的 alt 1：代码先在描述符列表里找 `id=1, alternateSetting=1` 的项，找不到就复制 id=1 的项改 alternateSetting。切换失败时记下 `setInterface` 的返回值。
2. **备选路径**「连接相机（备选：fd + libusb）」：`usbManager.getFileDescriptor` 拿 fd，交给 native 的 `libusb_wrap_sys_device`，和安卓同一条流程。这条没人测过：鸿蒙给应用的 fd 是否支持 usbfs 的等时 URB 不知道。记下成功/失败和界面上的 libusb 日志。若 libusb 在鸿蒙 NDK 下编不过，把 `apps/harmony/entry/src/main/cpp/CMakeLists.txt` 里的 `LINGTOUCH_HARMONY_LIBUSB` 改成 `OFF`，并记下编译错误。
3. 两条都不够用时：OpenHarmony 的 USB DDK C 接口文档里，`OH_Usb_SendPipeRequest` 只写了中断和批量传输，没找到等时传输的函数，所以“改走 USB DDK”大概率不行；动手前先查当时的 DDK 文档有没有更新。

## 3. 两边喂同一帧，核心输出的 9×6 完全一致

1. 找一帧有地面的真实数据：任一台设备上对着有地面的场景「保存当前帧」，拷到电脑；先在电脑上跑
   ```bash
   build/core/perception_tests/lt_frame_tool grid latest_frame.bin perception/cs30/calibration_0.bin
   ```
   记下最后一行的“摘要”。
2. 把这帧改名为 `frame.bin`，分别放进两台设备的应用目录（安卓：`adb push frame.bin /sdcard/Android/data/com.lingtouch.companion/files/`；鸿蒙：`hdc file send` 到应用沙箱的 files 目录），两台都先连一次相机（让核心读到同一台相机的标定），再点「核对帧文件」。
3. 三处（电脑、安卓、鸿蒙）的摘要应完全相同。摘要覆盖 54 格、每格诊断、各阶段像素数、地面法线和高度的二进制位。不同的话把三处显示的栅格和摘要都记下来。

## 4. 息屏 / 后台至少 10 分钟，持续取流、计算、发蓝牙不停

1. 连上相机和手柄，选好状态 2 的表示方式，打开「持续发送」；鸿蒙另打开「后台运行（长时任务）」。
2. 记下「拼帧」「已发帧」「手柄确认刷新」三个数，然后息屏（或切到别的应用）≥ 10 分钟。
3. 亮屏回来再记三个数：都应持续增长；用差值除以时间得到后台期间的帧率和发帧率。手柄在息屏期间应一直在刷新（手摸确认）。
4. 安卓用的是 connectedDevice 类型前台服务 + PARTIAL_WAKE_LOCK；鸿蒙是 bluetoothInteraction + location 长时任务（“计算任务”只开放给 2in1，平板用不了）。被系统停掉时记下停在第几分钟、哪个数先不涨。

## 5. 发一帧到手柄（旧板 V2.8 固件），手摸确认位置和方向

1. 「扫描并连接手柄」→ 状态“已连接”。
2. 在相机前方放一个箱子（例如右前方约 2 m），界面上对应格应为 ■；选平或凸后「发送一帧」。
3. 手摸：凸起的点应落在与界面一致的左右、远近位置。最远的 4 行（旧板 10×9 的前 4 行）应全平。
4. 方向有三个开关，都在 `core/config/lingtouch_defaults.conf`：
   - `tactile.module_rot180`（模组 180° 反装，与 frame_converter.py 一致，默认 true）；
   - `tactile.mirror_left_right`（穿戴左右镜像，沿用 experiment_server.py 和 9/29 比赛版的做法，默认 true）；
   - `depth.image_mirrored`（CS30 深度图本身是否左右镜像，未确认，默认 false）。先看界面：物体放在左边，界面左列应亮；不对就是 `depth.image_mirrored`。界面对了、手摸反了，就是 `tactile.mirror_left_right`。
5. 状态 2：分别选平和凸各发一次，确认没有数据（全是 ?）时整片平或整片凸。最终用哪种，定了之后写进 `tactile.unknown_cell_policy`。

## 6. RGB 流和标定能否走同一套协议拿到

启动序列里 SET_CUR 0xa100 的 25 字节里，类型字段 `02` 表示深度。RGB 的类型值不知道：像 10/25 那样在电脑上抓厂家 SDK 打开 RGB 时的 USB 包，看 0xa100 的内容、Probe/Commit 的帧大小和后续是否换了端点。标定 blob 里看起来已经有 RGB 内参和 RGB←深度的外参（字段 15–17，推断），抓到 RGB 后可以拿来做配准。

## 7. 深度是光轴 Z 还是径向距离、要不要去畸变（平面检查）

1. **判 Z / 径向**：相机正对一面平整的墙，距离 1–2 m，墙填满画面中央，点「平面检查」。四种假设按残差排序，最小的那组的“含义”就是答案（合成测试里：对的 < 1 mm，错的 > 5 mm）。正对墙时，光轴 Z 深度在整面墙上是常数，去不去畸变墙都一样平，所以这一步只看含义。
2. **判去不去畸变**：斜着拍一个大平面（例如相机俯仰约 45° 看地面，地面填满画面中央），再点一次。同一含义下“去畸变”和“不去”的残差差别大，小的那个是答案。
3. 把结论写进 `depth.meaning`、`depth.undistort`，并把两次的四行结果抄进报告。也可以「保存当前帧」后在电脑上跑 `lt_frame_tool plane 帧文件 perception/cs30/calibration_0.bin`。

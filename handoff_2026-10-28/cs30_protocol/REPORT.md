# CS30 接 Android：可行性结论

**结论：不用厂商 SDK，Android 上能直接拿到深度图。** CS30 板上的 ASIC 已经把深度算好了，USB 上传的就是 640×480、uint16 小端、单位毫米的深度帧，主机端不需要相位解算、解包裹、温度或逐像素标定。PC 上已经用通用 libusb（PyUSB）独立实现过一遍：开流、收帧、停流、同进程再开流都正常，全程没加载任何厂商 DLL。同一次曝光下，它和 SDK 输出的深度图逐像素一致（45 帧，SHA-256 相同）。

**Android 路线**：UsbManager 申请权限并打开设备 → `getFileDescriptor()` → JNI 里 `libusb_wrap_sys_device` → libusb 异步**等时传输（isochronous）**。Java 层的 `bulkTransfer` / `controlTransfer` / `UsbRequest` 收不了等时端点，必须走 native。不需要 root，也不需要厂商的 Android SDK。

还没在具体手机上测过。对手机的要求：USB 2.0 High Speed 主机；用户授予 USB 权限，加 CAMERA 权限（新版 Android 对 USB 视频类设备会查）；5V 供电要够，手册写 5V、平均 0.6A、3W，手机带不动就接带电源的 Hub。描述符里写的 500mA 不作数。

## 设备实际情况（USB 2207:0016）

- 它是标准 UVC 类设备（class 0x0e）。Windows 上绑的是 libusbK 驱动，但驱动绑定和接口类是两回事，之前"单个 libusbK 节点 = 非 UVC"的判断不对。
- **接口 0**：VideoControl，端点 0x81，中断 IN，16 字节
- **接口 1**：VideoStreaming。alt 0 没有端点，alt 1 带端点 0x82
- **0x82**：等时 IN，wMaxPacketSize 0x1400，即每次 1024 字节 × 每微帧 3 次 = **每微帧 3072 字节**。PyUSB 打印的 5120 是它解析错了。
- 没有 bulk 端点。

## 启动序列

照抄 SDK 抓到的 41 个类控制请求，setup 和 OUT 数据都逐字节一致。完整序列见 `startup_sequence.json`，原始 trace 是 `capture_runs/20261025_152210/usb_events.jsonl`。

1. claim 接口 0，设为 alt 0。
2. 读设备信息，用 GET_CUR（bmRequestType 0xa1，bRequest 0x81，wIndex 0x0600）：
   - wValue 0xcb00 / 0xc700 / 0xc800 分别读子型号、固件、序列号。
   - 0xc100 / 0xc200 各分 14 片读两份标定 blob（各 763 字节的 protobuf）。
   - 分片格式：总长 LE16、累计结束偏移 LE16、本片长度 u8，后面跟数据。
   - 取深度用不到标定，但 SDK 会读，照着读。标定以后做去畸变、点云、RGB 对齐时会用到。
3. SET_CUR（0x21 / 0x01），wValue 0xa200，wIndex 0x0600，5 字节全 0。
4. SET_CUR，wValue 0xa100，25 字节，表示只开深度流：
   `00 00 00 00 00 80 02 e0 01 02 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00`
   其中 `80 02` 是 640，`e0 01` 是 480，`02` 是类型。
5. 在接口 1 上做 UVC Probe：
   - GET_MAX，setup 为 `a1 83 00 01 01 00 1a 00`
   - SET_CUR，setup 为 `21 01 00 01 01 00 1a 00`，数据为
     `01 00 01 01 15 16 05 00 00 00 00 00 00 00 00 00 00 00 00 76 c5 00 00 04 00 00`
   - GET_CUR，setup 为 `a1 81 00 01 01 00 1a 00`，返回
     `01 00 01 01 80 f0 fa 02 00 00 00 00 00 00 00 00 00 00 00 60 09 00 00 04 00 00`
6. SET_CUR，wValue 0xb000，4 字节全 0。
7. UVC Commit，setup 为 `21 01 00 02 01 00 1a 00`，数据就是 Probe 返回的那 26 字节（帧大小字段 `00 60 09 00` = 614400）。
   **Commit 正常要约 2.36 秒才完成。** 最早那次失败就是超时只给了 2 秒。现在控制请求的超时设 15 秒；不要在前面加 sleep，等每个请求完成再发下一个。
8. 接口 1 切到 alt 1，**立刻**挂 10 个等时传输：每个 32 微帧 × 3072 = 98304 字节，端点 0x82，超时 5000 ms。这 32 个是微帧缓冲，不是 32 张图。
9. 传输挂上之后再发控制请求，顺序不能反：
   - SET_CUR 0xa600，再 SET_CUR 0xa700，各 1 字节 0
   - 处理大约 270 ms 的事件
   - SET_CUR 0xa300 = `37 01`，这是 SDK 默认的积分时间
10. 停流：取消并排空所有传输 → 接口 1 设 alt 0 → 接口 0 设 alt 0 → release。重开就把整个序列再走一遍。

## 帧格式

- 每个非空等时包的开头是 2 字节 UVC 头，按 bHeaderLength 去掉。
- 按 FID 翻转和 EOF 标志把包拼成帧。
- 一帧 = 200 个 3070 字节的包 + 最后 400 字节 = 614400 = 640×480×2。最后一包含头共 402 字节。
- 空微帧和开流头几张空图丢掉。
- payload 直接按行优先、uint16 小端、毫米解，不用解压，也不用重排像素。
- 0、1 这类接近 0 的值是无效标记，比对时按 >10 mm 才算有效。
- 不能当 YUYV 彩色图渲染。

分开两次曝光的对比（独立程序和 SDK 只能先后占用相机）：有效像素的差值中位数 3 mm、P95 12 mm，和 SDK 自己相邻两帧之间的抖动是一个量级。这一项只用来验证空间排列和距离尺度，格式是否一致以上面同曝光的 45 帧为准。

## 帧率和带宽

- 默认积分时间下实测约 14.05 fps，折合 8.63 MB/s（69 Mbit/s）。
- 端点上限约 24.5 MB/s，USB2 High Speed 足够。30 fps 没测。
- 接收队列总共约 0.94 MiB，不需要申请一整帧大小的连续 URB。

## Android 参考实现

- **saki4510t/UVCCamera**：在非 root 的 Android 上用 fd 打开 UVC 设备，libuvc 里用 `libusb_fill_iso_transfer` 提交等时传输，Android 的 libusb 后端通过 `IOCTL_USBFS_SUBMITURB` 发 ISO 类型的 URB。这是真正的等时接收，可以证明这条路走得通。不过它是老项目，fd 接口是打补丁加的。
- **新写建议直接用上游 libusb 的 Android 方案**（libusb 仓库的 `android/README`）：关掉设备发现，`getFileDescriptor()` 之后调 `libusb_wrap_sys_device`，后面就是普通的 libusb 调用。
- 现成的通用 UVC App 不能直接拿来用：要加上面那些 CS30 专有的扩展控制，并且按 uint16 深度处理数据。
- 如果手机内核已经用视频驱动绑定了这个设备，用 detach kernel driver 或 force claim 把它拿过来，这一步不需要 root。

## 安全和恢复

- 没刷固件，没写配置、标定、序列号或 IP。所有 OUT 请求都和 SDK 正常启动时发的一致。
- 测完后 SDK 能正常重开，相机不需要拔插。
- 出错时先 release 再重开；还不行再调 `libusb_reset_device`。

## 证据和脚本

都在任务的目录里：

- `independent_proof.py`：PC 端独立实现，可以直接当协议参考
- `startup_sequence.json`：完整启动序列
- `capture_runs/`、`independent_runs/`：SDK 抓包和独立程序收到的所有帧
- `validation.json`、`proof_comparison.json`：比对结果
- `calibration_0.bin`、`calibration_1.bin`：两份标定数据
- `android_evidence/`：UVCCamera、libusb、AOSP 权限检查的源码快照
- SDK 的反汇编文件
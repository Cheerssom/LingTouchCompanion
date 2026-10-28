/**
 * CS30 取流（鸿蒙）。启动表、拆帧、栅格都在 C++ 核心里，这里只做只能用平台接口的部分。
 *
 * 主路径：usbManager 执行启动表（控制请求逐条等完成、不加 sleep，超时 15 s），接口 1 切到 alt 1 后
 *   立刻用 usbSubmitTransfer 挂 10 个等时传输（API 18 起），每个传输回调把整批微帧一次交给核心。
 * 备选路径：usbManager.getFileDescriptor 拿 fd → core.openFd → native libusb_wrap_sys_device，
 *   与安卓走同一条 native 流程。两条都要真机测（docs/device_tests.md）。
 * 停流：取消所有传输 → 接口 1 设 alt 0 → 接口 0 设 alt 0 → release → closePipe。
 */
import { usbManager, BusinessError } from '@kit.BasicServicesKit';
import core, { StartupStep } from 'libentry.so';

const CS30_VENDOR_ID = 0x2207;
const CS30_PRODUCT_ID = 0x0016;

function sleep(ms: number): Promise<void> {
  return new Promise<void>((resolve) => {
    setTimeout(resolve, ms);
  });
}

export class Cs30Usb {
  status: string = '未连接';
  path: string = '';  // 'submit' | 'fd' | ''
  callbacks: number = 0;
  callbackErrors: number = 0;
  private device: usbManager.USBDevice | undefined = undefined;
  private pipe: usbManager.USBDevicePipe | undefined = undefined;
  private transfers: usbManager.UsbDataTransferParams[] = [];
  private claimed: number[] = [];
  private running: boolean = false;

  findDevice(): usbManager.USBDevice | undefined {
    for (const d of usbManager.getDevices()) {
      if (d.vendorId === CS30_VENDOR_ID && d.productId === CS30_PRODUCT_ID) {
        return d;
      }
    }
    return undefined;
  }

  private findInterface(dev: usbManager.USBDevice, id: number, alt: number): usbManager.USBInterface | undefined {
    let base: usbManager.USBInterface | undefined = undefined;
    for (const config of dev.configs) {
      for (const iface of config.interfaces) {
        if (iface.id === id && iface.alternateSetting === alt) {
          return iface;
        }
        if (iface.id === id && base === undefined) {
          base = iface;
        }
      }
    }
    if (base === undefined) {
      return undefined;
    }
    // 描述符列表里没有单独的 alt 项时，按同一接口改 alternateSetting（真机核对）
    const copy: usbManager.USBInterface = {
      id: base.id,
      protocol: base.protocol,
      clazz: base.clazz,
      subClass: base.subClass,
      alternateSetting: alt,
      name: base.name,
      endpoints: base.endpoints
    };
    return copy;
  }

  private async connect(): Promise<string> {
    const dev = this.findDevice();
    if (dev === undefined) {
      return '没找到 CS30（2207:0016）';
    }
    if (!usbManager.hasRight(dev.name)) {
      const granted = await usbManager.requestRight(dev.name);
      if (!granted) {
        return '没有得到 USB 权限';
      }
    }
    const pipe = usbManager.connectDevice(dev);
    if (pipe === undefined) {
      return 'connectDevice 失败';
    }
    this.device = dev;
    this.pipe = pipe;
    return '';
  }

  private claim(dev: usbManager.USBDevice, pipe: usbManager.USBDevicePipe, id: number): string {
    if (this.claimed.includes(id)) {
      return '';
    }
    const iface = this.findInterface(dev, id, 0);
    if (iface === undefined) {
      return `设备上没有接口 ${id}`;
    }
    // force = true：内核驱动已绑定时强制拿回来（REPORT：detach / force claim）
    const r = usbManager.claimInterface(pipe, iface, true);
    if (r !== 0) {
      return `claim 接口 ${id} 失败：${r}`;
    }
    this.claimed.push(id);
    return '';
  }

  /** 主路径：usbSubmitTransfer。返回空串表示已开流。 */
  async startSubmitTransfer(): Promise<string> {
    await this.stop();
    let err = await this.connect();
    if (err) {
      return this.fail(err);
    }
    const dev = this.device as usbManager.USBDevice;
    const pipe = this.pipe as usbManager.USBDevicePipe;
    core.resetStream();
    err = this.claim(dev, pipe, 0);
    if (err) {
      return this.fail(err);
    }
    const timeout = core.protocolInfo().controlTimeoutMs;
    const count = core.startupStepCount();
    this.status = '启动中（Commit 约需 2–3 秒）';
    for (let i = 0; i < count; i++) {
      const step = core.startupStep(i);
      if (step.kind === 'control') {
        const data = step.isIn ? new Uint8Array(step.length) : new Uint8Array(step.data);
        const req: usbManager.USBDeviceRequestParams = {
          bmRequestType: step.requestType,
          bRequest: step.request,
          wValue: step.value,
          wIndex: step.index,
          wLength: step.length,
          data: data
        };
        let n = -1;
        try {
          n = await usbManager.usbControlTransfer(pipe, req, timeout);
        } catch (e) {
          return this.fail(`第 ${i} 步控制请求异常：${JSON.stringify(e)}`);
        }
        if (n < 0) {
          return this.fail(`第 ${i} 步控制请求失败：${n}`);
        }
        if (step.isIn) {
          const r = core.onStartupResponse(i, data.buffer.slice(0, n));
          if (r) {
            return this.fail(r);
          }
        }
      } else if (step.kind === 'alt') {
        err = this.claim(dev, pipe, step.interfaceNumber);
        if (err) {
          return this.fail(err);
        }
        const iface = this.findInterface(dev, step.interfaceNumber, step.altSetting);
        if (iface === undefined) {
          return this.fail(`找不到接口 ${step.interfaceNumber} 的 alt ${step.altSetting}`);
        }
        const r = usbManager.setInterface(pipe, iface);
        if (r !== 0) {
          return this.fail(`第 ${i} 步切换接口 ${step.interfaceNumber} 到 alt ${step.altSetting} 失败：${r}`);
        }
      } else {
        err = this.queueIso(pipe, step);  // 切到 alt 1 之后立刻挂传输，之后的控制请求在传输挂上之后再发
        if (err) {
          return this.fail(err);
        }
      }
      if (step.settleMs > 0) {
        await sleep(step.settleMs);  // 0xa700 之后约 270 ms，期间传输回调照常处理
      }
    }
    this.path = 'submit';
    const cal = core.finishStartup();
    this.status = cal ? `已开流（usbSubmitTransfer），但内参不可用：${cal}` : '已开流（usbSubmitTransfer）';
    return '';
  }

  private queueIso(pipe: usbManager.USBDevicePipe, step: StartupStep): string {
    this.running = true;
    this.transfers = [];
    const endpoint = core.protocolInfo().isoEndpoint;
    for (let k = 0; k < step.isoTransfers; k++) {
      const params: usbManager.UsbDataTransferParams = {
        devPipe: pipe,
        flags: usbManager.UsbTransferFlags.USB_TRANSFER_SHORT_NOT_OK,
        endpoint: endpoint,
        type: usbManager.UsbEndpointTransferType.TRANSFER_TYPE_ISOCHRONOUS,
        timeout: step.isoTimeoutMs,
        length: step.isoTransferBytes,
        callback: (err: BusinessError, data: usbManager.SubmitTransferCallback) => {
        },
        userData: new Uint8Array(0),
        buffer: new Uint8Array(step.isoTransferBytes),
        isoPacketCount: step.isoPackets
      };
      params.callback = (err: BusinessError, data: usbManager.SubmitTransferCallback) => {
        this.onTransfer(params, err, data);
      };
      try {
        usbManager.usbSubmitTransfer(params);
      } catch (e) {
        return `usbSubmitTransfer 失败：${JSON.stringify(e)}`;
      }
      this.transfers.push(params);
    }
    return '';
  }

  private onTransfer(params: usbManager.UsbDataTransferParams, err: BusinessError,
    data: usbManager.SubmitTransferCallback): void {
    this.callbacks++;
    if (err && err.code) {
      this.callbackErrors++;
    } else if (data.status === usbManager.UsbTransferStatus.TRANSFER_COMPLETED) {
      // 按批：一次把这个传输的全部微帧交给核心
      const n = data.isoPacketDescs.length;
      const descs = new Int32Array(n * 3);
      for (let k = 0; k < n; k++) {
        const d = data.isoPacketDescs[k];
        descs[3 * k] = d.length;
        descs[3 * k + 1] = d.actualLength;
        descs[3 * k + 2] = d.status;
      }
      core.pushIsoTransfer(params.buffer.buffer, descs);
    } else if (data.status !== usbManager.UsbTransferStatus.TRANSFER_CANCELED) {
      this.callbackErrors++;
    }
    if (this.running) {
      try {
        usbManager.usbSubmitTransfer(params);
      } catch (e) {
        this.callbackErrors++;
      }
    }
  }

  /** 备选路径：getFileDescriptor + native libusb。返回空串表示已开流。 */
  async startViaFd(): Promise<string> {
    await this.stop();
    if (!core.protocolInfo().libusbAvailable) {
      return this.fail('这次编译没有包含 libusb（entry/src/main/cpp/CMakeLists.txt 里 LINGTOUCH_HARMONY_LIBUSB=OFF）');
    }
    const err = await this.connect();
    if (err) {
      return this.fail(err);
    }
    const fd = usbManager.getFileDescriptor(this.pipe as usbManager.USBDevicePipe);
    // 文档：失败时返回 -1 或 88080486 / 88080488 这类错误码
    if (fd < 0 || fd >= 88000000) {
      return this.fail(`getFileDescriptor 返回 ${fd}`);
    }
    this.status = '启动中（备选路径，Commit 约需 2–3 秒）';
    const r = core.openFd(fd);
    if (r) {
      return this.fail(`libusb 路径失败：${r}\n${core.libusbLog()}`);
    }
    this.path = 'fd';
    this.status = `已开流（getFileDescriptor + libusb）\n${core.libusbLog()}`;
    return '';
  }

  async stop(): Promise<void> {
    this.running = false;
    for (const p of this.transfers) {
      try {
        usbManager.usbCancelTransfer(p);
      } catch (e) {
        // 已完成或已取消的传输会报 14400011，忽略
      }
    }
    if (this.transfers.length > 0) {
      await sleep(300);  // 等回调排空
    }
    this.transfers = [];
    core.closeFd();
    const dev = this.device;
    const pipe = this.pipe;
    if (dev !== undefined && pipe !== undefined) {
      for (const id of [1, 0]) {
        if (!this.claimed.includes(id)) {
          continue;
        }
        const alt0 = this.findInterface(dev, id, 0);
        if (alt0 !== undefined) {
          usbManager.setInterface(pipe, alt0);
          usbManager.releaseInterface(pipe, alt0);
        }
      }
      usbManager.closePipe(pipe);
    }
    this.claimed = [];
    this.device = undefined;
    this.pipe = undefined;
    this.path = '';
    this.status = '未连接';
  }

  private fail(message: string): string {
    this.stop();
    this.status = `失败：${message}`;
    return message;
  }
}

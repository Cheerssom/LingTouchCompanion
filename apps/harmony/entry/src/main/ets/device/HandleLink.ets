/**
 * 触觉手柄（旧板，V2.8 固件）BLE 链路，取自 9/29 比赛版 hw/phone/entry/src/main/ets/device/HandleLink.ets。
 *
 * 服务 FFE0：写特征 FFE1 下发 15 字节点阵帧；通知特征 FFE3 回传 [类型, 数据]：
 *   0x01 刷新完成   0x04 按键扫描请求
 * 手柄每次刷新约 220ms，刷新中收到新帧会中止当前刷新。因此一次只下发一帧，
 * 收到刷新完成（或超时）后再下发最新的待发帧，中间产生的帧只保留最后一帧。
 * 与比赛版的差别：回调改成一个对象传入；不再跳过与上一帧相同的帧（后台持续发送测试要看到每次刷新）。
 */
import { ble, constant } from '@kit.ConnectivityKit';
import { BusinessError } from '@kit.BasicServicesKit';

const SERVICE_UUID = '0000FFE0-0000-1000-8000-00805F9B34FB';
const FRAME_UUID = '0000FFE1-0000-1000-8000-00805F9B34FB';
const STATUS_UUID = '0000FFE3-0000-1000-8000-00805F9B34FB';

const EVT_REFRESH_DONE = 0x01;
const EVT_SCAN_REQUEST = 0x04;

const SCAN_MS = 8000;
const REFRESH_TIMEOUT_MS = 1500;
const RECONNECT_MS = 3000;

export type HandleState = 'disconnected' | 'scanning' | 'connecting' | 'connected';

export class HandleCallbacks {
  onState: (state: HandleState) => void = (state: HandleState) => {
  };
  onFrameDone: (shown: boolean) => void = (shown: boolean) => {
  };
  onButton: () => void = () => {
  };
}

interface FoundHandle {
  deviceId: string;
  rssi: number;
}

function sameUuid(a: string, b: string): boolean {
  return a.toUpperCase() === b.toUpperCase();
}

export class HandleLink {
  state: HandleState = 'disconnected';
  framesShown: number = 0;
  private callbacks: HandleCallbacks;
  private client?: ble.GattClientDevice;
  private deviceId: string = '';
  private wantConnected: boolean = false;
  private reconnectTimer: number = -1;
  private inflight?: Uint8Array;
  private inflightTimer: number = -1;
  private pending?: Uint8Array;

  constructor(callbacks: HandleCallbacks) {
    this.callbacks = callbacks;
  }

  private setState(state: HandleState): void {
    if (this.state !== state) {
      this.state = state;
      this.callbacks.onState(state);
    }
  }

  /** 扫描广播 FFE0 的手柄，连接信号最强的一个。 */
  scanAndConnect(): void {
    const found: FoundHandle[] = [];
    const onFind = (results: Array<ble.ScanResult>) => {
      for (const r of results) {
        if (!found.some((f: FoundHandle) => f.deviceId === r.deviceId)) {
          found.push({ deviceId: r.deviceId, rssi: r.rssi });
        }
      }
    };
    try {
      ble.on('BLEDeviceFind', onFind);
      const filter: ble.ScanFilter = { serviceUuid: SERVICE_UUID };
      const options: ble.ScanOptions = { interval: 0, dutyMode: ble.ScanDuty.SCAN_MODE_LOW_LATENCY };
      ble.startBLEScan([filter], options);
      this.setState('scanning');
    } catch (e) {
      ble.off('BLEDeviceFind', onFind);
      return;
    }
    setTimeout(() => {
      try {
        ble.stopBLEScan();
      } catch (e) {
      }
      ble.off('BLEDeviceFind', onFind);
      found.sort((a: FoundHandle, b: FoundHandle) => b.rssi - a.rssi);
      if (found.length > 0) {
        this.connect(found[0].deviceId);
      } else {
        this.setState('disconnected');
      }
    }, SCAN_MS);
  }

  connect(deviceId: string): void {
    this.disconnect();
    this.deviceId = deviceId;
    this.wantConnected = true;
    this.openClient();
  }

  disconnect(): void {
    this.wantConnected = false;
    if (this.reconnectTimer >= 0) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = -1;
    }
    this.closeClient();
    this.setState('disconnected');
  }

  /** 请求显示一帧；返回空串表示已发出或排队，否则是原因。 */
  show(frame: Uint8Array): string {
    if (this.state !== 'connected') {
      return '手柄未连接';
    }
    if (this.inflight === undefined) {
      this.write(frame);
    } else {
      this.pending = frame;
    }
    return '';
  }

  private openClient(): void {
    try {
      const client = ble.createGattClientDevice(this.deviceId);
      this.client = client;
      client.on('BLEConnectionStateChange', (s: ble.BLEConnectionChangeState) => this.onConnState(client, s));
      client.on('BLECharacteristicChange', (c: ble.BLECharacteristic) => this.onNotify(c));
      this.setState('connecting');
      client.connect();
    } catch (e) {
      this.scheduleReconnect();
    }
  }

  private closeClient(): void {
    const client = this.client;
    this.client = undefined;
    this.resetFlow();
    if (client === undefined) {
      return;
    }
    try {
      client.off('BLEConnectionStateChange');
      client.off('BLECharacteristicChange');
      client.disconnect();
    } catch (e) {
    }
    try {
      client.close();
    } catch (e) {
    }
  }

  private resetFlow(): void {
    if (this.inflightTimer >= 0) {
      clearTimeout(this.inflightTimer);
      this.inflightTimer = -1;
    }
    this.inflight = undefined;
    this.pending = undefined;
  }

  private onConnState(client: ble.GattClientDevice, s: ble.BLEConnectionChangeState): void {
    if (client !== this.client) {
      return;
    }
    if (s.state === constant.ProfileConnectionState.STATE_CONNECTED) {
      this.setupServices(client);
    } else if (s.state === constant.ProfileConnectionState.STATE_DISCONNECTED) {
      this.closeClient();
      this.setState('disconnected');
      this.scheduleReconnect();
    }
  }

  private async setupServices(client: ble.GattClientDevice): Promise<void> {
    try {
      const services: Array<ble.GattService> = await client.getServices();
      const svc = services.find((s: ble.GattService) => sameUuid(s.serviceUuid, SERVICE_UUID));
      const status = svc?.characteristics.find((c: ble.BLECharacteristic) => sameUuid(c.characteristicUuid, STATUS_UUID));
      if (svc === undefined || status === undefined) {
        throw new Error('handle service not found');
      }
      await client.setCharacteristicChangeNotification(status, true);
      if (client === this.client) {
        this.setState('connected');
      }
    } catch (e) {
      if (client === this.client) {
        this.closeClient();
        this.setState('disconnected');
        this.scheduleReconnect();
      }
    }
  }

  private scheduleReconnect(): void {
    if (!this.wantConnected || this.reconnectTimer >= 0) {
      return;
    }
    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = -1;
      if (this.wantConnected && this.client === undefined) {
        this.openClient();
      }
    }, RECONNECT_MS);
  }

  private write(frame: Uint8Array): void {
    const client = this.client;
    if (client === undefined) {
      return;
    }
    this.inflight = frame;
    const value = new Uint8Array(frame).buffer;
    const ch: ble.BLECharacteristic = {
      serviceUuid: SERVICE_UUID,
      characteristicUuid: FRAME_UUID,
      characteristicValue: value,
      descriptors: [],
    };
    client.writeCharacteristicValue(ch, ble.GattWriteType.WRITE).catch((_e: BusinessError) => {
      this.finishInflight(false);
    });
    this.inflightTimer = setTimeout(() => {
      this.inflightTimer = -1;
      this.finishInflight(false);
    }, REFRESH_TIMEOUT_MS);
  }

  private finishInflight(shown: boolean): void {
    if (this.inflightTimer >= 0) {
      clearTimeout(this.inflightTimer);
      this.inflightTimer = -1;
    }
    const done = this.inflight;
    this.inflight = undefined;
    if (done === undefined) {
      return;
    }
    if (shown) {
      this.framesShown++;
    }
    this.callbacks.onFrameDone(shown);
    const next = this.pending;
    this.pending = undefined;
    if (next !== undefined) {
      this.show(next);
    }
  }

  private onNotify(c: ble.BLECharacteristic): void {
    if (!sameUuid(c.characteristicUuid, STATUS_UUID)) {
      return;
    }
    const data = new Uint8Array(c.characteristicValue);
    if (data.length < 1) {
      return;
    }
    if (data[0] === EVT_REFRESH_DONE) {
      this.finishInflight(true);
    } else if (data[0] === EVT_SCAN_REQUEST) {
      this.callbacks.onButton();
    }
  }
}

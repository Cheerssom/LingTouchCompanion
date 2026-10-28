# V2 布线规则包（2026-10-18 改正版）

针对 PCB2（原理图改动后 191 个网络）。布线器的规则全部从 DSN 读，所以要先在嘉立创设好再导出 DSN。

## 层

6 层，叠层 JLC06161H-3313，1.6 mm：

| 层 | 内容 |
|---|---|
| Top / Bottom | 器件和信号 |
| Inner1 | **GND 整板平面**（内电层，网络 GND） |
| Inner2 / Inner3 | 信号 |
| Inner4 | **VCC 整板平面**（内电层，网络 VCC，只放这一个网络，不分割） |

现在 PCB2 导出的 DSN 只有 Top/Bottom 两层：先在图层管理器里改成 6 层，Inner1、Inner4 设为内电层并指定 GND、VCC，导出的 DSN 里这两层才会是 `type power`。

为什么 Inner4 只放 VCC：VCC（3.53 V 线圈电源，18 个线圈 3.1 A、24 个 4.1 A）从 L1/C74–C76 出来，要送到 10 个模组的 40 个 VCC 脚、10 个 ULN 的 COM 脚和 10 颗 22 µF，横跨约 70 mm，只有它需要整层。按 0.5 oz 内层估算，L1 到阵列中部约 2.3 方，电阻约 2.6 mΩ，4.1 A 压降约 11 mV。其他电源都不需要平面：VBUS/VIN_SYS 只在 ESP 端 20 mm 内（J1→U58→U49/U50/U51/SW2），VCCS 最大 1 A，0.5 mm 走线足够。

## 规则（`V2_DesignRules.json`，设计 → 设计规则 → 导入配置）

| 线宽规则 | 线宽 | 网络 |
|---|---:|---|
| V2_SIGNAL（默认） | 0.18 mm | 其余 181 个网络，含线圈网络（≤0.2 A） |
| V2_POWER | 0.5 mm | VBUS、VIN_SYS、VCCS、ESP_5V_RAW、V5S、MAIN_SW、SMA_SW、ESP_SW |
| V2_PLANE_FANOUT | 0.4 mm | GND、VCC：只从焊盘拉到过孔，进平面 |

过孔：信号 0.5/0.25 mm（默认），电源 0.65/0.35 mm（上面 10 个网络）。间距、板边距照 PCB1_5。内电层：SMD 经过孔直连，THT 用花焊盘（手焊插座不吃热）。

只要给 10 个网络建两个网络类（`net-class-members.txt`），其余用默认，不用一个个点。

## 布线后手工补的

- VBUS、VIN_SYS（3 A）：0.5 mm 只是布通用，布完在 ESP 端用铺铜加宽。
- MAIN_SW、SMA_SW、ESP_SW 是开关节点：芯片 SW 脚到电感尽量短而宽，手画。
- VCC 进平面：C74–C76/L1 输出端至少 8 个电源过孔；每个 ULN COM 脚 2 个。GND 同理，U49 地焊盘下打一排。

## 布线器设置

布线层只勾 Top / Inner2 / Inner3 / Bottom（Inner1、Inner4 是平面）；不勾"自动设置规则"；"忽略铺铜连通性"不勾；开"自动过孔"；最小线宽 0.1 mm；边界框禁布边距 0.3 mm。

## 导出后核对

`python verify_dsn.py 新DSN路径`：检查 6 层、Inner1/Inner4 是平面、每个网络的线宽和过孔。

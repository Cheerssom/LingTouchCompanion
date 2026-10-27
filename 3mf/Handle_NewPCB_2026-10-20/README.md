# PCB1_2 盲杖手柄外壳（2026-10-27 版：三块壳 + 三根榫）

打印件共六件：托盘、前盖、后盖、前榫、后榫、中间榫。没有别的零件，也不需要外购件。尚未实打。

- **托盘**：从杖口到尾巴一整条。底面贴床，底边是原来的圆角。
- **前盖**：杖口、模组区，加上 45° 坡。打印时模组面朝下贴床。
- **后盖**：握把加尾段。顶面是一整个平面，打印时朝下贴床。
- **前榫、后榫**：沙漏截面，横穿托盘与盖的分缝。拔出这两根，两块盖就能一起从托盘上拿下来，用于充电和烧程序。后榫在充电宝后面，同时挡住充电宝，尾口敞开。
- **中间榫**：横穿两块盖之间的缝，把它们并成一整块，平时不拆。它位于板子上方 Z 5–14 mm，截面是两道 45° 的 V 形折条。打印时竖着放，截面贴床。
- 三根榫都是松插：槽全长比榫每边大 0.2 mm，不靠摩擦，不会卡死。

## 外形

- 总长 272.89 mm。
- 握把截面 38.27 × 32.05 mm，模组区 39.27 × 37.00 mm，尾段 44.00 × 32.05 mm。
- 杖口孔是 Ø25 的正圆，插深 28 mm，托盘和前盖各一半，上下对称。
- 杖口段顶面比模组面低 3 mm，不加高。
- 坡在 X 56.57–61.52，落差 4.95 mm，正好 45°；缝就在坡底，离 ESP 前端约 11 mm。
- 模组区开三条长窗，中间两道 2.10 mm 隔条；U48 单独开窗；SW1 是圆孔。模组固定顶面与壳面齐平。
- 天线贴位在杖口上方：一面平，用来贴 FPC；另两面 45°，向下通到杖孔。
- PCB 两个安装孔：托盘柱顶出一根 Ø1.0 销，穿过板上 Ø1.2 孔，伸出板面 1.8 mm；盖子柱底开 Ø1.3、深 1.8 mm 的孔接住销头，柱底离板面 0.2 mm 压住板。销同时把托盘和盖子对齐。

## 拓竹真切的支撑

设置：H2C、PLA Basic、0.4 mm、0.20mm Standard，只打开支撑，其余为系统默认。没有屏蔽体，没有涂抹。

整盘 96.09 g，其中支撑 2.25 g，全部落在 Hsinlung 认可的两处：

| 位置 | 支撑 |
|---|---:|
| 托盘底边贴床那圈 | 1.14 g |
| 前盖杖口段顶面下（含杖口到模组面的过渡） | 1.11 g |
| 其他任何地方（后盖、三根榫、坡、缝、各个槽） | 0 g |

同样设置切原手柄，结果是整盘 113.58 g，支撑 28.67 g。详见 [REPORT](REPORT_2026-10-27.md) 和[支撑路径图](renders/13_bambu_support.png)。

## 文件

- [打印 3MF](Handle_Print_H2C.3mf)：拓竹原生工程，含 G-code。
- [装配 3MF](Handle_Assembly.3mf)：含 PCB、模组、ESP、充电宝等参考件。
- 图：
  - [外观](renders/01_exterior.png)、[侧面](renders/02_side.png)、[顶面窗口](renders/03_top_windows.png)、[杖口正视](renders/05_cane_mouth.png)
  - [坡与缝](renders/06_slope_seam.png)、[打印姿态](renders/11_print_poses.png)、[盖内腔](renders/14_cover_interior.png)、[尾口](renders/15_tail_open.png)
  - [三根榫截面](renders/section_tenons.png)、[中线纵剖](renders/section_long.png)、[杖口横剖](renders/section_cane.png)、[PCB 安装孔](renders/section_pcb_holes.png)

在仓库根目录依次运行：

```powershell
3mf/.runtime/structural-runtime/Scripts/python.exe -B 3mf/Handle_NewPCB_2026-10-20/build.py
3mf/.runtime/structural-runtime/Scripts/python.exe -B 3mf/Handle_NewPCB_2026-10-20/slice.py
3mf/.runtime/structural-runtime/Scripts/python.exe -B 3mf/Handle_NewPCB_2026-10-20/verify.py
3mf/.runtime/structural-runtime/Scripts/python.exe -B 3mf/Handle_NewPCB_2026-10-20/render.py
```

各脚本的作用：

- **build**：生成六件和装配 3MF。
- **slice**：调拓竹真切，按件、按位置统计支撑，分成"认可"和"不认可"两类。核对通过后，用拓竹原生输出替换打印 3MF。
- **verify**：检查以下各项：
  - 碰撞；
  - PCB 两条长边和两个安装孔的定位；
  - 三根榫各自卡住哪两件；
  - 两块盖连同中间榫能否一起从托盘上抬起；
  - 充电宝只被后榫挡住；
  - 左右对称、杖孔正圆、顶面窗口与隔条；
  - 每件在打印姿态下有没有比 30° 平的朝下面，以及逐层有没有凭空起头或悬出过多。认可的三处之外必须为零；
  - 3MF 回读。
- **render**：出图。

models/ 下的 verification.json、slice_verification.json、fit_verification.json 是对应的结果。

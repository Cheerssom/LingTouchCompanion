Historical description only. Superseded model files, renders and case-specific tools were removed on 2026-10-28; the text remains as evidence for Shell_Lessons. Current work: ../../Handle_TwistKey_2026-10-27/HANDOFF.md.

【2026-10-11 更正】本文件夹的 PCB 摆位在宽度方向偏了 2.75 mm（用了借来的排母占位模型对齐），据此得出的“PCB 偏向 −Z”、电容让位、定位榫位置等结论不再成立。核实结果见 ../VERIFIED_FACTS.md；当前设计见 ../Coaxial_v1/。

手柄重建模型 · 2026-10-11

两版均保留原杖口、电池前舱、宽上盖、触觉开孔和尾部握持止挡。
只收窄下部握持段：

Grip_34mm：主版，下部目标宽度34 mm。
Grip_32mm：瘦握版，下部通常32 mm；为C78/C79电容留空间，
负Z侧两处平缓加宽1 mm，局部总宽33 mm。
上方壳体保持46 mm宽，不把PCB空间跟着整体缩小。

两个文件夹各含：
  Handle_Assembly.3mf：上下壳两件，按真实装配坐标保存，毫米。
  Handle_Print.3mf：两件并排的导入排版，仍可分开选择。
  housing.stl / cover.stl：可分别导入、单件排版，单位按毫米读取。
  housing.npz / cover.npz：精确装配网格，供后续建模工具读取。
  verification.json：尺寸与本次数字检查范围。

上盖沿厚度方向装入。原来的长滑槽已去掉，改为前后两个短榫定位，
平面边沿承受按压；侧向螺钉独立防止上盖抬起。
短榫每个侧面预留0.25 mm，螺孔按M2×5 mm样机假设建模。
拆盖时先取出侧向螺钉，再向上提起。

Assembly_34mm.png / Assembly_32mm.png：完整壳体外观。
Exploded_Joint.png / Joint_Closeup.png：拆盖与短榫结构。
Section_Comparison.png：原壳、34 mm、32 mm的实际握持截面对照。
Handle_Redesign.blend：含两版独立上下壳；默认显示34 mm版。

已核对两件闭合与拆盖路径、新握持段约2 mm以上的壁厚、裸电芯
参考包络、偏置PCB参考带，以及保留STEP中的下侧电容空间。
这不是完整实物装配或真人舒适度测试；ESP本体、保护板、包覆材料、
真实模块接口和全部固定件仍应以实物装配为准。

打印导入排版约270×116 mm，不能假定适合所有打印平台。
可分别用STL排版；支撑、材料与最终方向由所用打印条件决定。
原始Handle_Print.3mf和inputs/Handle_Original.3mf没有改动。

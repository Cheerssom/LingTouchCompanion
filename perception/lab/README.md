# perception/lab — 视觉同学的 Python 实验位

视觉同学的 Windows 原型 `windows_obstacle_grid/`（CS30 采集、点云、地面拟合、0/1/2、SpatialLM 桥接）和 `spatiallm_demo/`（SpatialLM 官方复现、照片试验、椅子补检）**不在本仓库**，在视觉同学自己的机器上，这里不去找、也不复制。方案见 [docs/plans/视觉方案_v1.0_视觉同学.md](../../docs/plans/视觉方案_v1.0_视觉同学.md)。

以后要放进仓库的 Python 实验代码放在这个目录。端侧实际运行的 C++ 实现在 [perception/native](../native/README.md)；参数在 `core/config/lingtouch_defaults.conf`，改门槛请改那里，两个 App 会一起生效。

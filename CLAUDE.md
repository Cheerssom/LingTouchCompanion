# 环境说明

只放仍然有效的本机环境信息。布局、每个文件夹归谁、各入口见 [README.md](README.md)。旧的 10/09 审阅交接已归档到 [archive/CLAUDE_2026-10-09.md](archive/CLAUDE_2026-10-09.md)。

- 视觉实验（`experiments/chi2027/`）用 `D:/anaconda/envs/LING/python.exe`。旧的小写 `lingtouch` 环境 NumPy/LAPACK 是坏的，不要用。
- 建模（`hardware/models/`）用 `hardware/models/3mf/.runtime/structural-runtime/Scripts/python.exe`，命令在 `hardware/models/` 下执行（那里相当于原来的仓库根）。换机器时按 `hardware/models/3mf/requirements.txt` 等固定版本安装。运行时不提交。
- 只在本机、不进 Git：仓库根的 `pics/`、`Depth-Anything-V2/`（含权重）、`experiment_runs/`、`.pcba-workflow/`（`hardware/models/.pcba-workflow` 是指向它的目录联接）、密钥（`.env`）、依赖、论文材料、本地归档。实验脚本按环境变量 `LINGTOUCH_ROOT`，没设就向上找 `.git` 来定位仓库根。
- 端侧核心：`cmake -S core -B build/core && cmake --build build/core && ctest --test-dir build/core`（需要 CMake ≥ 3.16、C++17 编译器）。
- 厂家 SDK 的二进制、反汇编、strings 不进仓库。
- 不要改全局协作约定或本地 AGENTS 备忘，除非被要求。

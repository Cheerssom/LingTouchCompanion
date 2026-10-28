# experiments/chi2027 — 论文实验通路（Hsinlung）

手机拍摄 → 米制深度（Depth-Anything-V2）→ 俯视栅格或单点告警 → BLE。与端侧骨架（`core/`、`apps/`）是两条独立的路，互不调用。

| 位置 | 内容 |
|---|---|
| [visionss/](visionss/README.md) | 实验服务（空间栅格条件），入口 `python experiments/chi2027/visionss/phone_server.py` |
| [single_point/](single_point/README.md) | 单点告警对照条件，入口 `python experiments/chi2027/single_point/alert_server.py` |
| [TOPDOWN_VALIDATION.md](TOPDOWN_VALIDATION.md) | 离线标定与距离验证记录（历史证据） |
| `validate_distance.py`、`check_balloon_depth.py`、`prep_new_pics.py` | 离线验证工具，读仓库根的 `pics/` |
| `depth_preview.html` | 图片深度预览，配合 `visionss/depth_server.py` |

命令在仓库根目录执行。`Depth-Anything-V2/`、`pics/`、`experiment_runs/` 留在本机仓库根，不进 Git；脚本经 `visionss/repo_paths.py` 定位仓库根（先看环境变量 `LINGTOUCH_ROOT`，否则向上找 `.git`）。本机环境 `D:\anaconda\envs\LING\python.exe`。

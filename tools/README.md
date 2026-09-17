# tools/ 工具清单

> 2026-09-17 整理。分四类：**验收/量测**、**采集/标定**、**运行**、**诊断**（`_` 前缀 = 排查用，可随时删）。
> 一次性迁移脚本（`_fix_*`、`_upgrade_*`）用完即删，历史在 git 里。

## 验收 / 量测（改完代码必跑）

| 文件 | 用途 | 怎么跑 |
|---|---|---|
| `tm_verify.py` | **读牌验收**（位对位）：① 用户标注的 27 张满手图 ② 实时帧对游戏真值 | `PYTHONPATH=src python3 tools/tm_verify.py 4` |
| `status_now.py` | 一眼看全局：设备/5 个服务/真值/读牌命中率/git | `PYTHONPATH=src python3 tools/status_now.py` |
| `acc_truth.py` | 操作准确率（身份级）：我们决定的牌 vs 游戏真值里真打出的牌 | `PYTHONPATH=src python3 tools/acc_truth.py` |
| `acc_report.py` | 操作准确率（点选口径）：决定 vs 桌面读回 | `PYTHONPATH=src python3 tools/acc_report.py` |
| `read_acc.py` | 读牌逐张准确率采样（真值+帧同步） | `PYTHONPATH=src python3 tools/read_acc.py 15` |
| `truth_log.py` | 真值采样器（周期落盘 `data/truth/*.jsonl`） | `PYTHONPATH=src python3 tools/truth_log.py` |

## 采集 / 标定（模板库）

| 文件 | 用途 |
|---|---|
| `tm_collect_live.py` | **用游戏真值当老师**，在实时帧上自动采"点数级"模板 → `data/templates_rank/` |
| `tm_build.py` | 用**用户标注的参考图**采"花色+点数"模板 → `data/templates_sr/`（追加，不清空） |
| `tm_montage.py` | 把一手牌的竖条放大+编号，拼成对照图（请人报花色时用，省力） |
| `tm_label_ref.py` | 参考图 + 标注 → 采模板 + 当场自校验 |
| `tm_selftest.py` | 旧版自检（已被 `tm_verify.py` 取代，保留作对照） |

⚠️ **两个模板目录互不覆盖**，`percept.load_templates_sr()` 合并读取：
- `data/templates_sr/` 花色+点数（参考图，24 类）
- `data/templates_rank/` 点数级（实时真值，`0_<点数>_<样本>_<x>.npy`）

⚠️ **采集与读取必须同一口径**：都用 `percept.card_top_y()` 逐牌按自身顶边裁（游戏会把某些牌抬高显示）。

## 运行

| 文件 | 用途 |
|---|---|
| `run_via_platform.py` | 跑托管窗口：`python3 tools/run_via_platform.py 150 guandan`（已在牌局不重开页） |
| `guandan_prep.py` | 进桌准备（重开页 + 开始游戏 + 带 CDP 调试口） |
| `live_view.py` | 网页直播 `:8140`（MJPEG + 操作日志 + 记牌事件） |
| `board_api.py` | 后台数据服务 `:8130`（`/games/<id>/history|pool|timeline|export.csv`） |
| `show_select_now.py` | 整屏 + 手牌放大截图（发给用户人眼核对时用） |

## 诊断（`_` 前缀，排查用，可随时删）

`_diag_live` 读牌链路 / `_diag_dist` 匹配距离 / `_diag_lift` 抬起量 / `_diag_tap`·`_diag_tapxy` 点击与选中 /
`_diag_cols` 逐列剖面 / `_diag_joker` 大小王 / `_diag_sense` 适配器 sense 链路 / `_diag_order`（读牌顺序）

## 关键常量（实测得来，改前先量）

| 常量 | 值 | 出处 |
|---|---|---|
| 手牌带 | y≈815–936（满手） | `percept.hand_band_measured()` |
| 牌距 | **24px** | `percept.card_slots()` |
| 牌面可见宽 | ~24px（末张全露 ~62px） | 同上 |
| 选中抬起 | 上移 **36px**；`lifted_px` 未选 197 → 选中 2756 | `tools/_diag_lift.py` |
| 模板匹配阈值 | `max_dist=0.6`（真牌位 0.000 / 杂位 0.95） | `tools/_diag_dist.py` |

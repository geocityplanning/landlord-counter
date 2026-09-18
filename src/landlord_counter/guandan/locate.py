"""掼蛋**专有定位**(2026-09-18): 离线标定 + 在线校验 ⇒ 给出"点哪里、有没有把握" ✓

为什么独立成一个模块(用户 2026-09-18 指令)
----------------------------------------
"每一个项目独立的定位逻辑、点牌逻辑、出牌逻辑" —— 掼蛋有它自己的几何(720x1280 竖屏、
手牌带 815..936、牌距 24、末张 88、按钮三段), 不该和斗地主/麻将共用一套通用自适应 ✗
通用自适应的代价: 每次都在赌, 换个局/换个承载就漂 ⇒ 点错牌 ✗(本项目实测踩过多轮)

本模块的对外契约
--------------
  locate(img, n_expected) -> (slots, check)     # 牌位; check.ok=False ⇒ **不许动手** ✓
  play_button(img) -> (x, y) | None             # 出牌按钮(实测像素, 每帧取) ✓
  card_tap(idx, n, img) -> (x, y) | None        # 第 idx 张的点击点 ✓
  hand_tap_y() -> int                           # 点击手牌用的纵坐标(带中点) ✓

纪律: 校验不过 ⇒ 返回 None / check.ok=False ⇒ 上层**拒绝动作并报警** ✓(绝不悄悄漂移 ✗)
"""
from __future__ import annotations


from . import geometry as G

_GEOM: G.GuandanGeom | None = None


def geom() -> G.GuandanGeom:
    """标定几何(进程内缓存; 标定文件改了要重启进程或用 reload()) ✓"""
    global _GEOM
    if _GEOM is None:
        _GEOM = G.load()
    return _GEOM


def reload() -> G.GuandanGeom:
    global _GEOM
    _GEOM = G.load()
    return _GEOM


def hand_tap_y() -> int:
    """点击手牌的纵坐标 = 标定手牌带的**中点**(实测: 用别处常量会打空 ✗)"""
    return geom().hand_y()


def locate(img, n_expected: int | None = None) -> tuple[list[int], G.CheckResult]:
    """定位牌位: 在线校验 + 右端锚点向左铺 ✓

    右端锚点的理由(实测): 末张完整可见 ⇒ 它的左缘必然可测 ⇒ 可靠 ✓
      而左端锚点会偏(最左那张挨着「你」框, 边缘弱) ⇒ 实测整排偏一张 ✗
    """
    g = geom()
    chk = G.verify_online(img, g, expect_cards=n_expected)
    if not chk.ok:
        return [], chk
    x_hi = chk.measured.get("white_x", [0, 0])[1]
    right_left = int(x_hi - g.last_card_w)
    if n_expected is None:
        x_lo = chk.measured.get("white_x", [0, 0])[0]
        n_expected = int(round((right_left - x_lo) / g.pitch)) + 1
    # ★ 优先用**离线按张数标定的实测表**(用户 2026-09-18: 每种情况量准 ✓)
    slots = g.slots_for(int(n_expected), right_left)
    slots = [s for s in slots if 0 <= s < img.shape[1]]
    chk.measured["source"] = "table" if (g.slots_by_n or {}).get(str(int(n_expected))) else "formula" 
    if len(slots) != int(n_expected):
        chk.ok = False
        chk.reasons.append(f"牌位生成异常: 得到 {len(slots)} 个, 预期 {n_expected}")
    return slots, chk


def card_tap(idx: int, n: int, img) -> tuple[int, int] | None:
    """第 idx 张的点击点(当帧实测) ✓ —— 校验不过返回 None(上层不许动手 ✓)"""
    g = geom()
    slots, chk = locate(img, n)
    if not chk.ok or not (0 <= idx < len(slots)):
        return None
    return int(slots[idx]), g.hand_y()


def play_button(img) -> tuple[int, int] | None:
    """出牌按钮(底部三段里**最亮**那段 = 金色) —— 每帧实测 ✓

    为什么实测: 按钮位置/外观会随局面变(可用/禁用/高亮) ⇒ 用标定常量会按空 ✗
      (标定值只作参考与在线校验的对照 ✓)
    """
    g = geom()
    y_a, y_b = g.btn_y0, g.btn_y1
    band = img[y_a:y_b]
    if band.size == 0:
        return None
    gg = band[:, :, 1].astype(int)
    ng = ~((gg > band[:, :, 2].astype(int) + 12) & (gg > band[:, :, 0].astype(int) + 12))
    col = ng.mean(axis=0)
    runs, s = [], None
    for x, v in enumerate(col):
        if v > 0.6 and s is None:
            s = x
        elif v <= 0.6 and s is not None:
            if x - s > 25:
                runs.append((s, x))
            s = None
    if s is not None and len(col) - s > 25:
        runs.append((s, len(col)))
    if len(runs) < 3:
        return None
    lo, hi = max(runs, key=lambda ab: band[:, ab[0]:ab[1]].mean())
    cx = int((lo + hi) // 2)
    if abs(cx - g.btn_play_x) > 60:          # 偏离标定太多 ⇒ 界面变了 ⇒ 不信 ✓
        return None
    return cx, int((y_a + y_b) // 2)

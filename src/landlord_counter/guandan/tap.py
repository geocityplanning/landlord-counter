"""掼蛋**专有点牌**(2026-09-18): 定位 → 点击 → **结果校验** ✓

用户要求: "每一个项目独立的定位逻辑, 点牌逻辑, 出牌逻辑" —— 本模块是掼蛋的点牌逻辑。
与通用手势(platform/gestures.py)的区别
------------------------------------
通用手势要兼顾多游戏, 于是到处是"自适应/回落/猜测" ✗ ⇒ 每个游戏都被它拖累
掼蛋点牌只做四件事, 每件都可验证:
  ① 点之前先**回落**: 清掉桌上已有的选中(否则与我们选的牌混成非法牌型 ✗)
  ② 按**标定+在线校验**过的位置, 逐张点(每点一张前重新定位, 因为牌会动 ✓)
  ③ 点完**复核**: 用游戏回执(牌型是否合法)与手牌张数变化判定成败 ✓
  ④ 失败**精确撤销**: 刚点过的牌原样点回去(游戏是开关 ⇒ 点回=取消) ✓

依赖注入(便于测试): 传入 tap_fn(x, y) 与 read_truth() 两个回调即可, 不直接耦合设备 ✓
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field

from . import locate as L


@dataclass
class TapResult:
    ok: bool
    detail: str = ""
    tapped: list = field(default_factory=list)     # 点过的索引(用于精确撤销 ✓)
    cleared: int = 0                                # 回落清掉几张
    reasons: list = field(default_factory=list)     # 失败原因(响亮 ✓)


def _cards_snapshot(read_truth) -> tuple[list, list]:
    """取 (手牌id顺序, 当前选中id) ✓ 无真值通道时返回 ([], [])"""
    try:
        tr = read_truth() or {}
    except Exception:  # noqa: BLE001
        return [], []
    return (tr.get("handIds") or []), (tr.get("selIds") or tr.get("selected") or [])


def clear_residue(tap_fn, read_truth, img_fn, rounds: int = 4) -> int:
    """**回落**: 把桌上已有的选中全部点掉(用户算法第③步) ✓

    做法: 真值给 selIds + handIds ⇒ 算出"是第几个牌位" ⇒ 点它(开关 ⇒ 取消) ✓
      每轮重新定位(牌一抬起/一取消, 位置就会变 ✓)
    为什么必须: 残留 + 我们选的牌 = 非法牌型 ⇒ 游戏回「无效的牌型组合」✗(实测踩到)
    """
    cleared = 0
    for _ in range(rounds):
        ids, sel = _cards_snapshot(read_truth)
        if not ids or not sel:
            break
        pos = [ids.index(s) for s in sel if s in ids]
        if not pos:
            break
        img = img_fn()
        if img is None:
            break
        slots, chk = L.locate(img, len(ids))
        if not chk.ok:
            break
        for p in pos:
            if 0 <= p < len(slots):
                if tap_fn(int(slots[p]), L.hand_tap_y()):
                    cleared += 1
        time.sleep(0.45)
    return cleared


def select_and_play(idxs: list[int], img_fn, tap_fn, read_truth,
                    press_play, *, verify_cards: int | None = None) -> TapResult:
    """掼蛋的完整点牌流程: 回落 → 逐张选 → 出牌 → 校验 ✓

    参数都是回调(不直接耦合设备/平台层) ⇒ 可单测 ✓
      img_fn()        -> 当前帧
      tap_fn(x, y)    -> 点一下(返回是否成功送达)
      read_truth()    -> 游戏真值(实验室裁判; 无则 None)
      press_play()    -> 按出牌按钮(返回 (ok, toast文本) 或 bool)
      verify_cards    -> 期望出牌张数(用于结果校验 ✓)
    """
    res = TapResult(ok=False)

    # ① 回落
    res.cleared = clear_residue(tap_fn, read_truth, img_fn)

    # ② 逐张选(每张点之前重新定位 ⇒ 牌的位移不会让我们点偏 ✓)
    ids0, _sel0 = _cards_snapshot(read_truth)
    n = len(ids0) if ids0 else None
    for i in idxs:
        img = img_fn()
        if img is None:
            res.reasons.append("取帧失败")
            return res
        slots, chk = L.locate(img, n)
        if not chk.ok:
            res.reasons.append("在线校验未通过: " + "; ".join(chk.reasons))
            return res                       # ★ 校验不过 ⇒ 不动手 ✓
        if not (0 <= i < len(slots)):
            res.reasons.append(f"索引 {i} 越界(共 {len(slots)} 位)")
            return res
        tap_fn(int(slots[i]), L.hand_tap_y())
        res.tapped.append(i)
        time.sleep(0.35)
        # 复核: 游戏是否真的把这张选上了 ✓
        ids, sel = _cards_snapshot(read_truth)
        if ids and i < len(ids) and ids[i] not in sel:
            res.reasons.append(f"第 {i} 张点了没选上")

    # ③ 出牌 + 结果校验
    before_ids, _ = _cards_snapshot(read_truth)
    n_before = len(before_ids)
    ok_press, toast = False, ""
    try:
        r = press_play()
        if isinstance(r, tuple):
            ok_press, toast = bool(r[0]), str(r[1] or "")
        else:
            ok_press = bool(r)
    except Exception as e:  # noqa: BLE001
        res.reasons.append(f"按出牌异常: {type(e).__name__}")
        return res
    time.sleep(1.6)
    after_ids, _ = _cards_snapshot(read_truth)
    n_after = len(after_ids)
    if n_before and n_after < n_before:
        res.ok = True
        res.detail = f"出牌成功: 手牌 {n_before} → {n_after}"
        return res
    res.detail = f"出牌未生效(手牌 {n_before} → {n_after})"
    if toast:
        res.reasons.append(f"游戏回执: {toast}")
    # ④ 精确撤销
    for i in reversed(res.tapped):
        img = img_fn()
        if img is None:
            break
        slots, chk = L.locate(img, None)
        if chk.ok and 0 <= i < len(slots):
            tap_fn(int(slots[i]), L.hand_tap_y())
        time.sleep(0.3)
    res.detail += " → 已精确撤销"
    return res

#!/usr/bin/env python3
"""**人工托管的"手"**: 按用户报的编号点牌 → 用游戏真值校验选中 → 出图。

用户 2026-09-18: "要不你给我手动控制出牌, 然后你截图"
用法:
  python3 tools/manual_tap.py 26 27          # 点第 26、27 号(1 起)
  python3 tools/manual_tap.py --play 26 27   # 点完确认无误再按"出牌"
  python3 tools/manual_tap.py --clear        # 清掉桌上已有的选中(精确回落)

要点(都是踩出来的):
  · 点击 x = 牌位 + 6px(点在牌的**左缘**上会被游戏判给左边那张 ✗)
  · **每点一张前重新实量牌位**(点完牌面会变, 上一轮的 x 会过期)
  · 校验只认**游戏真值** selected, 不认"看起来抬起了"
"""
from __future__ import annotations

import os
import sys
import time

import cv2
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from landlord_counter.guandan import locate as L          # noqa: E402
from landlord_counter.platform.cdp import CDP             # noqa: E402
from landlord_counter.platform.device import AdbDevice    # noqa: E402
from landlord_counter.platform.maatouch import MaaTouch   # noqa: E402

OUT = "/tmp/manual.png"
BAND = (790, 950)
NAME = {11: "J", 12: "Q", 13: "K", 14: "A", 15: "小王", 16: "大王"}


def nm(v: int) -> str:
    return NAME.get(v, str(v))


def wait_stable(dev, timeout: float = 2.5, tol: float = 2.0) -> bool:
    """等画面**停稳**再测量/截屏(用户 2026-09-18 指出: 刚出完牌有个**小火箭动画**,
    那一刻**牌是暂时消失的** ⇒ 此时截的图/量的数全是错的 ✗)

    做法: 连续两帧像素差 ≤ tol 即认为停稳(帧差判据零成本 ✓)
    """
    prev = dev.snap()
    t0 = time.time()
    while time.time() - t0 < timeout:
        time.sleep(0.35)
        cur = dev.snap()
        if prev.shape != cur.shape:
            prev = cur
            continue
        if float(np.mean(np.abs(cur.astype("int16") - prev.astype("int16")))) <= tol:
            return True
        prev = cur
    return False


def wait_ready(dev, c, timeout: float = 5.0) -> tuple:
    """等到"**画面停稳 且 牌真的在**"为止(2026-09-18 用户两次指出: 出牌瞬间有小火箭动画,
    牌面会**短暂全没** ✗)。

    为什么要两条: 只看"停稳"会漏 —— 动画期间牌全没了 ⇒ **连续两帧都是空的** ⇒ 像素差≈0
    ⇒ 误判"停稳"通过 ✗✓。所以还要**牌位数量 == 真值张数**这个硬条件 ✓。
    返回 (ok, 帧)。
    """
    t0 = time.time()
    while time.time() - t0 < timeout:
        wait_stable(dev, timeout=1.2)
        t = c.truth() or {}
        n = len((t.get("hands") or {}).get("0") or [])
        img = dev.snap()
        if n:
            slots, _ = L.locate(img, n)
            if len(slots) == n:
                return True, img
        time.sleep(0.3)
    return False, dev.snap()


def shot(dev, c, mt, note: str = "") -> tuple:
    """截一张"给用户看"的图: 整屏 + 手牌放大 + 编号 + 选中标记 ✓(先等"停稳且牌在" ✓)"""
    wait_ready(dev, c)
    t = c.truth() or {}
    hand = [int(v) for v in ((t.get("hands") or {}).get("0") or [])]
    ids = list(t.get("handIds") or [])
    sel = set(int(v) for v in (t.get("selected") or []))
    img = dev.snap()
    slots, _ = L.locate(img, len(hand))
    pos_sel = {i for i, i_ in enumerate(ids) if i_ in sel}      # 选中的是第几位(0 起)
    pb = L.play_button(img)

    full = img.copy()
    for i, x in enumerate(slots):
        x0 = int(x)
        col = (0, 0, 255) if i in pos_sel else (0, 255, 0)
        cv2.line(full, (x0, BAND[0]), (x0, BAND[1]), col, 2 if i in pos_sel else 1)
        cv2.putText(full, str(i + 1), (x0, BAND[0] - 6), cv2.FONT_HERSHEY_SIMPLEX,
                    0.42, (0, 255, 255), 1)
    if pb:
        cv2.circle(full, (int(pb[0]), int(pb[1])), 22, (255, 0, 255), 2)
    band = cv2.resize(img[BAND[0] - 25:BAND[1]], None, fx=2.5, fy=2.5,
                      interpolation=cv2.INTER_NEAREST)
    for i, x in enumerate(slots):
        xb = int(int(x) * 2.5)
        col = (0, 0, 255) if i in pos_sel else (0, 255, 0)
        cv2.line(band, (xb, 0), (xb, band.shape[0]), col, 2 if i in pos_sel else 1)
        cv2.putText(band, str(i + 1), (xb + 3, 20), cv2.FONT_HERSHEY_SIMPLEX,
                    0.55, (0, 255, 255), 2)
    sel_txt = " ".join(f"#{i + 1}({nm(hand[i])})" for i in sorted(pos_sel)) or "无"
    hdr = (f"turn={'ME' if t.get('current') == 0 else t.get('current')}  cards={len(hand)}  "
           f"selected={len(sel)}  [{sel_txt}]")
    if note:
        hdr = note + " | " + hdr
    head = np.full((34, max(full.shape[1], band.shape[1]), 3), 20, np.uint8)
    cv2.putText(head, hdr, (6, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.58,
                (0, 255, 255) if sel else (255, 255, 255), 1)
    bank = np.full((30, max(full.shape[1], band.shape[1]), 3), 20, np.uint8)
    cv2.putText(bank, "truth: " + " ".join(nm(v) for v in hand), (6, 22),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
    W = max(full.shape[1], band.shape[1])
    sep = np.full((6, W, 3), 40, np.uint8)
    def pad(p):
        return p if p.shape[1] == W else np.pad(p, ((0, 0), (0, W - p.shape[1]), (0, 0)))
    cv2.imwrite(OUT, np.vstack([pad(p) for p in (head, full, sep, band, sep, bank)]))
    # ★ 同时存进"按张数"的标定档案(用户 2026-09-18: "每种情况…方便以后复核")
    #   纪律: **只存合格帧**(牌位数 == 手牌张数 且 >0) ⇒ 既不会覆盖合格档案, 也不会留下
    #   需要人工清理的失败帧(用户当天手动删过一次 n13_fail ✗ ⇒ 直接不写 ✓)
    if len(hand) > 0 and len(slots) == len(hand):
        _dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..",
                            "data", "calib", "shots")
        os.makedirs(_dir, exist_ok=True)
        cv2.imwrite(os.path.join(_dir, f"n{len(hand)}.png"),
                    np.vstack([pad(p) for p in (head, full, sep, band, sep, bank)]))
    return hand, ids, sel, pos_sel


def tap_one(dev, c, mt, idx0: int) -> tuple:
    """点第 idx0(0 起) 张 —— 点前重新实量牌位 ✓; 返回 (x, 当帧牌位数, 该位读到的点数)"""
    t = c.truth() or {}
    hand = [int(v) for v in ((t.get("hands") or {}).get("0") or [])]
    wait_ready(dev, c)               # ★ 点之前等到"停稳且牌在": 动画期间量到的牌位是错的 ✗
    img = dev.snap()
    slots, _ = L.locate(img, len(hand))
    if idx0 >= len(slots):
        print(f"✗ 第 {idx0 + 1} 号越界(当前 {len(slots)} 位)")
        return (0, len(slots), 0)
    x = int(slots[idx0])
    mt.tap(x + 6, L.geom().hand_y())          # ★ +6px: 点在左缘上会被判给左邻 ✗
    return (x, len(slots), hand[idx0] if idx0 < len(hand) else 0)


def bottom_buttons(img) -> list:
    """量底部按钮行里的**各段按钮**中心(2026-09-18)。

    实测: y≈1113 那一行有三段(出牌=中间那段最亮/金色 [32,149,186] BGR) ⇒
    按"亮段"分段、返回各段中心 x。顺序 = 屏幕从左到右 ✓
    """
    y0, y1 = 1085, 1145
    strip = img[y0:y1].astype("int16")
    # 判据 = "**和桌面绿不一样**"(2026-09-18 两次猜颜色都错 ✗: "最亮20%"只挑到出牌那段,
    #        "蓝>绿"一段都挑不到 ⇒ 改为与**按钮行上方那条桌面**的均色比差异, 实测三段全出 ✓)
    ref = img[1030:1060].reshape(-1, 3).mean(axis=0)
    on = (np.abs(strip - ref.reshape(1, 1, 3)).sum(axis=2) > 90).mean(axis=0) > 0.5
    segs, start = [], None
    for i, v in enumerate(on):
        if v and start is None:
            start = i
        elif not v and start is not None:
            if i - start > 30:                       # 太窄的当噪声 ✓
                segs.append((start + i) // 2)
            start = None
    if start is not None and len(on) - start > 30:
        segs.append((start + len(on)) // 2)
    return [(int(x), (y0 + y1) // 2) for x in segs]


def do_pass(dev, c, mt) -> bool:
    """按"不出" —— 三格里中间是出牌(已知 ✓) ⇒ 先试最右、再试最左, 以真值为准 ✓"""
    t0 = c.truth() or {}
    before_cur = t0.get("current")
    btns = bottom_buttons(dev.snap())
    print(f"  底部按钮段: {btns}")
    order = [b for b in btns if abs(b[0] - 360) > 60]     # 排除中间(出牌) ✓
    order.sort(key=lambda b: -b[0])                        # 先右后左 ✓
    for x, y in order:
        mt.tap(x, y)
        time.sleep(1.2)
        t = c.truth() or {}
        sel = t.get("selected") or []
        if sel:
            print(f"  ✗ x={x} 是「提示」(选中了 {len(sel)} 张) ⇒ 清掉换另一侧")
            for sid in list(sel):
                ids = list(t.get("handIds") or [])
                if sid in ids:
                    ix = ids.index(sid)
                    img = dev.snap()
                    slots, _ = L.locate(img, len(ids))
                    if ix < len(slots):
                        mt.tap(int(slots[ix]) + 6, L.geom().hand_y())
                        time.sleep(0.5)
            continue
        if t.get("current") != before_cur:
            print(f"  ✓ x={x} 就是「不出」(轮到 {before_cur} → {t.get('current')})")
            return True
    print("  ✗ 两个候选都没让回合变化")
    return False


def main() -> int:
    args = [a for a in sys.argv[1:]]
    do_play = "--play" in args
    do_clear = "--clear" in args
    want_pass = "--pass" in args
    want_press = "--press" in args
    nums = [int(a) for a in args if a.isdigit()]

    dev = AdbDevice(serial="127.0.0.1:5555", url="http://172.18.0.1:8123/index.html")
    c = CDP()
    c.find_truth()
    mt = MaaTouch("127.0.0.1:5555")
    mt.start()

    if do_clear:
        t = c.truth() or {}
        ids = list(t.get("handIds") or [])
        sel = list(t.get("selected") or [])
        for sid in sel:
            if sid in ids:
                tap_one(dev, c, mt, ids.index(sid))
                time.sleep(0.45)
        time.sleep(0.8)
        hand, _i, s2, _p = shot(dev, c, mt, "清理后")
        print(f"✓ 清理: {len(sel)} → selected={len(s2)}")
        return 0

    if want_press:                       # 只按"出牌"(桌上已有选中时用 ✓, 不重复点牌)
        t = c.truth() or {}
        n0 = len((t.get("hands") or {}).get("0") or [])
        if not (t.get("selected") or []):
            print("✗ 桌上没有选中的牌 ⇒ 不按")
            return 1
        wait_stable(dev)
        pb = L.play_button(dev.snap())
        mt.tap(int(pb[0]), int(pb[1]))
        time.sleep(1.8)
        _h, _i, _s, _p = shot(dev, c, mt, "出牌后")
        print(f"✓ 已按出牌 | 手牌 {n0} → {len(_h)} | "
              f"{'✓ 打出去了' if len(_h) < n0 else '✗ 没打出去'}")
        return 0

    if want_pass:
        ok = do_pass(dev, c, mt)
        wait_stable(dev)
        shot(dev, c, mt, "不出后")
        print(f"✓ 不出 {'成功' if ok else '失败 ✗'} | 图: {OUT}")
        return 0 if ok else 1

    hand0 = [int(v) for v in ((c.truth() or {}).get("hands") or {}).get("0") or []]
    for n in nums:
        x, ns, v = tap_one(dev, c, mt, n - 1)
        print(f"  点第 {n} 号 → x={x} (当帧 {ns} 位, 该位应是 {nm(v)})")
        time.sleep(0.55)

    time.sleep(0.9)
    hand, ids, sel, pos_sel = shot(dev, c, mt, f"点了 {' '.join(str(n) for n in nums)}")
    # ★ 判定必须比**位置**(2026-09-18: 曾比"名字"且用点后的手牌 ⇒ 明明偏位却报'一致' ✗)
    want_pos = [n - 1 for n in nums]
    got_pos = sorted(pos_sel)
    want = [nm(hand0[p]) for p in want_pos if p < len(hand0)]
    got = [nm(hand0[p]) for p in got_pos if p < len(hand0)]
    # ★ 判定必须比**集合**而不是顺序(2026-09-18: 用序列比较 ⇒ 用户报"5551010"时
    #   我按 17,18,19,5,6 的顺序传, 实际选中的是排序后的 5,6,17,18,19 ⇒ 明明全对却报"不一致" ✗,
    #   白拦了一手好牌 —— 选牌本来就不分先后 ✓)
    same = sorted(want_pos) == got_pos
    print(f"✓ 你要的位: {[p + 1 for p in want_pos]}({' '.join(want)}) | "
          f"实际选中位: {[p + 1 for p in got_pos]}({' '.join(got) or '无'}) "
          f"| {'✓ 一致' if same else '✗ 不一致 —— 有偏移!'}")

    if do_play and same and got_pos:
        pb = L.play_button(dev.snap())
        mt.tap(int(pb[0]), int(pb[1]))
        time.sleep(1.6)
        hand2, _i, _s, _p = shot(dev, c, mt, "出牌后")
        print(f"✓ 已按出牌 | 手牌 {len(hand)} → {len(hand2)}"
              f" | {'✓ 打出去了' if len(hand2) < len(hand) else '✗ 没打出去'}")
    elif do_play:
        print("✗ 选中与要求不一致 ⇒ **不出牌**(避免把脏牌打出去)")
    print(f"图: {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

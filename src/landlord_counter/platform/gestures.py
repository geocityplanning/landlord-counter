"""通用手势执行层: 点选验证 / 扫点 / 提示选牌 / 回执轮询 / 两轮重试。

与游戏无关——游戏只需提供 GestureLayout(牌位公式/按钮坐标/判据函数)。
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Callable

from .actloop import ActReport, Evidence
from . import mode                      # ★ 真值/产品 模式开关(用户 2026-09-18 拍板解耦 ✓)

import numpy as np


@dataclass
class GestureLayout:
    """一款游戏的布局与判据(由适配器提供)。

    按钮坐标可以是固定点, 也可以用 ``btn_resolver(frame)`` 动态解析(如按颜色找按钮)。
    """

    card_tap_x: Callable[[int, int], int]      # (索引, 手牌张数) -> 设备x(公式, 兜底)
    hand_y: int                                # 手牌带点击 y
    lift_px: Callable[[np.ndarray], int]       # 抬起像素量(用于选牌验证)
    my_turn: Callable[[np.ndarray], bool]      # 是否我方回合(含按钮可用)
    white_count: Callable[[np.ndarray], int]   # 手牌白卡像素(用于回执)
    card_positions: Callable[[Any, int], list[int]] | None = None  # 实测牌位(优先, 与张数解耦)
    btn_hint: tuple[int, int] | None = None
    btn_play: tuple[int, int] | None = None
    btn_pass: tuple[int, int] | None = None
    btn_resolver: Callable[[np.ndarray], dict] | None = None   # → {'hint','play','pass'} 坐标
    lift_diff: Callable[[np.ndarray, np.ndarray], float] | None = None  # 帧差抬起量(可选, 更稳)
    lift_eps: float = 300.0     # "新抬起一张"的最小增量(像素口径≈300, 张数口径≈0.5)
    lift_one: float = 2559.0    # 单张抬起量(2026-09-17 实测: 未选 197 → 选中 2756, 差 2559 ✓)
    lift_min: float = 500.0     # 判定"有选中"的最小抬起量


class Executor:
    """通用出牌执行器。所有动作自带验证与重试, 绝不"静默失败"。"""


    def __init__(self, device, layout: GestureLayout, log: Callable[[str], None] = print) -> None:
        self.dev = device
        self.L = layout
        self.log = log
        self._dx = 0          # 点选自纠正偏移(全局)
        self.last_report = None      # 最近一次动作的 ActReport(执行器规范: 识别→动作→校验)
        self.cdp = None              # 可选: CDP 输入后端(调试/标定用)
        self.mt = None               # 可选: MaaTouch 拟人化输入(真实 MotionEvent: 压力/接触/时长)
        self._liveness_fails = 0     # 连续"点了没反应"次数(活性探针)
        self._lift_min = None        # 本次运行见过的最小抬起量(≈"空"基线, 自适应)

    # ---------- 基础 ----------
    def _snap(self):
        return self.dev.snap()

    def _lift(self, img) -> int:
        return self.L.lift_px(img) if img is not None else 0

    def _press(self, pt, wait: float = 1.6) -> bool:
        """按**按钮**: 优先 CDP 派发(实测 adb tap 在'出牌'上完全无反应), 失败回落 adb tap。

        CDP 只是"把这次点击送进去"的另一个通道; 是否生效仍由调用方的**校验**判定
        (执行器规范第 4 步: 点完必须看可观测信号)。
        """
        if pt is None:
            return False
        if self.mt is not None:                 # ① 拟人化输入优先(产品路径)
            try:
                self.mt.tap(pt[0], pt[1])
                time.sleep(wait)
                return True
            except Exception as e:  # noqa: BLE001
                self.log(f"  [input] MaaTouch 失败({type(e).__name__}) → 回落 CDP/adb")
        if self.cdp is not None:
            try:
                self.cdp.click_screen(pt[0], pt[1], settle=wait)
                return True
            except Exception as e:  # noqa: BLE001
                self.log(f"  [input] CDP 点击失败({type(e).__name__}) → 回落 adb tap")
        self.dev.tap(pt[0], pt[1], wait=wait)
        return True

    def btn(self, name: str, frame=None):
        """取按钮坐标: 优先 btn_resolver(动态), 否则固定点。返回 None 表示当前不可用。"""
        if self.L.btn_resolver is not None:
            img = frame if frame is not None else self._snap()
            if img is None:
                return None
            return self.L.btn_resolver(img).get(name)
        return getattr(self.L, f"btn_{name}", None)

    def _card_y(self) -> int:
        """点击手牌用的 y: 取**实测量到的手牌带**中点 ✓

        实测(2026-09-17): 原来用 layout 的 hand_y, 它已过期 ⇒ 点击**打在牌外** ⇒
        游戏收不到、`selected` 纹丝不动(视觉上却因动画略变, 把我骗了一整晚 ✗)
        改用实测带中点(y≈875)后: `tap(628, 875)` → 游戏真值 selected **立刻 +1** ✓✓
        """
        try:
            from ..guandan import percept as _P

            img = self._snap()
            if img is not None:
                y0, y1 = _P.hand_band_measured(img)
                if 60 <= y1 - y0 <= 220:
                    return int((y0 + y1) // 2)
        except Exception:  # noqa: BLE001
            pass
        return int(getattr(self.L, "hand_y", 875))

    def _play_btn(self):
        """出牌按钮的坐标: **从当前帧实测**(2026-09-17) —— layout 常量会过期 ✗

        教训: 与"点击手牌用过期 y"完全同一个坑 ✓ —— 按坐标来自 layout ⇒ 按下去没反应 ✗
        实测(720x1280 掼蛋): 底部 y≈1078..1148 有三段按钮(提示/出牌/不出),
          **出牌**那段最亮(金色, BGR≈[32,149,186], 另两段≈[18,72,115])
          ⇒ 取"最亮的那段"的中心, 实测 (360,1112) 与游戏 DOM 真值 (359,1111) 完全吻合 ✓✓
        """
        img = self._snap()
        if img is None:
            return None
        y_a, y_b = 1078, 1148
        band = img[y_a:y_b]
        if band.size == 0:
            return None
        g = band[:, :, 1].astype(int)
        not_green = ~((g > band[:, :, 2].astype(int) + 12) & (g > band[:, :, 0].astype(int) + 12))
        col = not_green.mean(axis=0)
        runs: list = []
        s = None
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
        lo, hi = max(runs, key=lambda ab: band[:, ab[0]:ab[1]].mean())   # 最亮 = 出牌 ✓
        return (int((lo + hi) // 2), int((y_a + y_b) // 2))

    def _wait_stable(self, timeout: float = 1.8, tol: float = 2.0) -> bool:
        """等画面**停稳**再量 —— 连续两帧像素差 ≤ tol 就算停稳 ✓

        实测(2026-09-17 用户线索): 出牌后的那一帧处于**动画中** ⇒ 此时牌位/抬起量全是错的 ✗
          (实测出牌后牌位检测从 28 个崩到 1 个 ✗)
        ⇒ 凡是"动作之后要测量", 先等停稳 ✓ (帧差判据, 零成本, 最多等 timeout)
        """
        import numpy as _np

        prev = self._snap()
        if prev is None:
            return False
        t0 = time.time()
        while time.time() - t0 < timeout:
            time.sleep(0.12)
            cur = self._snap()
            if cur is None:
                return False
            if cur.shape == prev.shape:
                if float(_np.abs(cur.astype("int16") - prev.astype("int16")).mean()) <= tol:
                    return True
            prev = cur
        return False

    def _tap_card_at(self, x: int, wait: float = 0.45) -> None:
        """点手牌某位置: 优先 CDP(可信事件), 否则 adb tap。

        实测教训(2026-09-15): adb 的 touch 能让牌视觉上抬起, 但**游戏内部不认这手牌**
        (点"出牌"毫无反应); 改用 CDP 派发的鼠标事件后, "选牌→出牌"一次成功 ✓。
        """
        # ★ 点击 = 牌位 + 6px(2026-09-18 实测): 点在牌的**左缘**上, 游戏会判给**左边那张**
        #   (实测: 点 x=326(第13位左缘) → 游戏选中显示位置[12] ✗; 点 x=14(左缘−2) → [0] ✓)
        x = int(x) + 6
        if self.mt is not None:                 # ① 拟人化输入优先
            try:
                self.mt.tap(x, self._card_y())
                return
            except Exception as e:  # noqa: BLE001
                self.log(f"  [input] MaaTouch 点牌失败({type(e).__name__}) → 回落")
        if self.cdp is not None:
            try:
                self.cdp.click_screen(x, self._card_y(), settle=wait)
                return
            except Exception as e:  # noqa: BLE001
                self.log(f"  [input] CDP 点牌失败({type(e).__name__}) → 回落 adb")
        self.dev.tap(x, self._card_y(), wait=wait)

    def tap_card(self, idx: int, n: int) -> bool:
        """点选第 idx 张并验证抬起; 失败则左右扫点(小牌量牌位漂移)。

        验证方式: 有 lift_diff(帧差) 用它(更稳); 否则用绝对抬起量增量。
        """
        # 身份驱动点选(2026-09-15): 点完看"实际抬起的列", 与目标位比对。
        #   实测现场: 想点 310 → 实际抬起 360(系统性偏 ~50px, 布局左缘测得偏左)
        #   ⇒ 把偏差累加进 self._dx(全局自纠正), 点偏了就取消重来。
        for _rnd in range(2):
            x_want = self._pos(idx, n)
            if not (0 < x_want < 720):
                return False
            before_img = self._snap()
            self._tap_card_at(x_want, wait=0.45)
            after_img = self._snap()
            if after_img is None:
                continue
            cols = []
            try:
                from ..guandan import percept as _P

                cols = [c for c, _w in _P.lifted_columns(before_img, after_img)]
            except Exception:  # noqa: BLE001
                pass
            # 可靠信号: 抬起增量(真的选中了牌)。抬起位只作**软校验/日志**:
            #   实测抬起带易混进桌面牌堆 → 幻影会诱导"取消重试"反而毁掉正确点选,
            #   故不据它取消。位置本身已由"卡边界实测"保证(与公式/张数无关)。
            est = round((self._lift(after_img) - (self._lift(before_img))) / self.L.lift_one)
            if est > 0:
                if cols:
                    near = min(cols, key=lambda c: abs(c - x_want))
                    if abs(near - x_want) > 20:
                        self.log(f"  [gesture] ⚠ 抬起位(想{x_want} 实测{near}) 不符, 但已选中{est}张 → 接受")
                return True
            if cols:                          # 没抬起但画面变了 → 记录后微调重试
                self.log(f"  [gesture] ⚠ 未选中但画面有变化 {cols} → 微调重试")
            self._dx += 6
        return False

    def _pos(self, idx: int, n: int) -> int:
        """第 idx 张的可点 x: 优先"实测牌位", 失败回落公式, 再叠加自纠正偏移 dx。"""
        base = None
        f = self.L.card_positions
        if f is not None:
            try:
                img = self._snap()
                xs = f(img, n) if img is not None else None
                if xs and 0 <= idx < len(xs):
                    base = int(xs[idx])
            except Exception:  # noqa: BLE001
                pass
        if base is None:
            base = self.L.card_tap_x(idx, n)
        return int(base + getattr(self, "_dx", 0))

    def select(self, idxs: list[int], n: int, ranks: list | None = None) -> bool:
        """按**组**点选: 同点数的牌只点一次(游戏会"帮点"补齐整组)。

        现场结论(2026-09-15 实测):
          · 帮点逻辑: 点一张 → 同点数整组一起选中(抬起量 +2559 ≈ 2 张, 单张≈1260);
          · 反效果: 再点同组的第二张 = **整组取消** ⇒ "一张一张点"会自己抵消, 永远选不上;
          · "抬起条在哪一列"的绝对读数不可靠(上方混着桌面牌堆, 实测点 x=208 读出 122)。
        做法: 目标牌按点数分组 → 每组只点一次 → 用**抬起量**确认这次点击是选中还是取消
              (没增长就补点一次) → 每组至少贡献一张即算成功。
        这是通用做法: 任何"点一张选一组"的手牌区(App/小程序同理)都适用。
        """
        base = self._lift(self._snap())

        def cnt(img=None) -> int:
            if img is None:
                img = self._snap()
            if img is None:
                return -1
            return max(0, round((self._lift(img) - base) / self.L.lift_one))

        # 目标位按点数分组(ranks 缺省则各自成组)
        picks = list(zip(idxs, ranks if (ranks and len(ranks) == len(idxs)) else [None] * len(idxs)))
        groups: list = []
        for i, r in picks:
            for gp in groups:
                if r is not None and gp[0] == r:
                    gp[1].append(i)
                    break
            else:
                groups.append([r, [i]])
        prev = 0
        reacted = 0
        for gi, (r, gidx) in enumerate(groups):
            x = self._pos(gidx[0], n)
            if not (0 < x < 720):
                continue
            b = self._snap()
            self._tap_card_at(x, wait=0.6)
            a = self._snap()
            c = cnt(a)
            # ---- 活性探针(执行器规范第 2/4 步): 首次点击必须带来可观测反应 ----
            if gi == 0 and c <= 0 and not self._frame_changed(b, a):
                self._liveness_fails += 1
                self.last_report = ActReport(
                    kind="select", skipped=True, not_our_turn=True,
                    reason=f"首次点击无任何反应(非我回合或通道失灵), 连续{self._liveness_fails}次",
                    evidence=Evidence(src="frame_diff",
                                      before={"lift": self._lift(b) if b is not None else None},
                                      after={"lift": self._lift(a) if a is not None else None},
                                      changed=False))
                return False
            self._liveness_fails = 0
            changed = self._frame_changed(b, a)
            if c <= prev and not changed:      # 没选中也没画面变化 → 补点一次
                self.log(f"  [gesture] ↻ 组选: x={x}(点数{r}) 未增({prev}→{c}) → 补点")
                self._tap_card_at(x, wait=0.6)
                a2 = self._snap()
                c2 = cnt(a2)
                changed = changed or self._frame_changed(a, a2)
                c = max(c, c2)
            if changed or c > prev:
                reacted += 1
            prev = max(prev, c)
        # 成功判据: 每组都点到了(有明显反应) —— 是否"打出去"由出牌回执(wait_receipt)终判
        ok = reacted >= 1 and (reacted >= len(groups) or prev >= len(groups))
        self.last_report = ActReport(kind="select", ok=ok, retries=0,
                                     reason=f"{len(groups)}组 → 有反应{reacted}组, 选中≈{prev}张",
                                     evidence=Evidence(src="measured",
                                                       before={"lift_base": base},
                                                       after={"lift_now": self._lift(self._snap())},
                                                       changed=prev > 0))
        self.log(f"  [gesture] {'✓ 组选完成' if ok else '✗ 组选不中'}: {len(groups)}组 有反应{reacted}组 选中≈{prev}张 (n={n})")
        return ok

    def _frame_changed(self, a, b, thr: float = 20.0) -> bool:
        """两帧是否有可见差异(活性探针用)。"""
        try:
            if a is None or b is None:
                return False
            return float(np.abs(b.astype(int) - a.astype(int)).mean()) > thr / 255.0
        except Exception:  # noqa: BLE001
            return False

    def _selected_xs(self) -> list:
        """当前已抬起(选中)的牌位 x(绝对测量)。"""
        try:
            from ..guandan import percept as _P

            img = self._snap()
            return _P.selected_columns(img) if img is not None else []
        except Exception:  # noqa: BLE001
            return []

    def clear(self, idxs: list[int], n: int) -> None:
        for i in idxs:
            self._tap_card_at(self._pos(i, n), wait=0.15)

    def selected_count(self, img, base: float | None = None) -> int:
        """已选张数: 用**相对基线**的抬起增量(承载存在基线偏移, 绝对值会多算)。"""
        lift = self._lift(img) - (base or 0.0)
        return round(lift / self.L.lift_one) if lift > self.L.lift_min else 0

    def pass_turn(self, frame=None) -> bool:
        p = self.btn("pass", frame)
        if not p:
            self.log("  [gesture] ✗ 找不到'不出'按钮")
            return False
        self._press(p, wait=1.6)
        return True

    # ---------- 出牌 ----------
    def wait_receipt(self, before: int, polls: int = 8, poll_s: float = 0.4) -> bool:
        """回执: 回合交出 或 手牌白卡明显下降。"""
        for _ in range(polls):
            time.sleep(poll_s)
            img = self._snap()
            if img is None:
                continue
            if not self.L.my_turn(img) or self.L.white_count(img) < before - 1500:
                return True
        return False

    def play_by_hint(self, want: int | None = None, follow: bool = False) -> str:
        """提示选牌执行: 提示 → 张数校验 → 出牌 → 回执(带补点一次)。

        返回 'ok' | 'none'(无可出) | 'mismatch'(张数不符, 已清选) | 'fail'
        """
        img0 = self._snap()
        before = self.L.white_count(img0)
        baseline = self._lift(img0)          # 抬起量基线(不同承载/版式下有偏移)
        ph = self.btn("hint")
        if not ph:
            return "fail"
        self._press(ph, wait=1.6)
        iv = self._snap()
        delta = self._lift(iv) - baseline    # 只用增量估算选中张数
        est = round(delta / self.L.lift_one) if delta > self.L.lift_min else 0
        if est == 0:
            return "none"
        if want and not follow and abs(est - want) > max(1, want // 2):
            self.pass_turn()                              # 清掉提示选中的牌
            return "mismatch"
        pp = self._play_btn() or self.btn("play")
        if not pp:
            return "fail"
        self._press(pp, wait=1.6)
        if self.wait_receipt(before):
            return "ok"
        self.log("  [gesture] ↻ 出牌未生效 → 补点一次")
        self._press(pp, wait=1.6)
        if self.wait_receipt(before, polls=6):
            return "ok"
        return "fail"

    # ---------- 伺服式直选(用户 2026-09-17 设计的算法) ----------
    def _flat_top(self) -> float:
        """"牌放平"时的顶边基线(动态实测, 不写死 ✗)。"""
        return float(getattr(self, "_top_flat", 0.0))

    def _raised_state(self, img, xs: list, idxs: list | None = None) -> list:
        """逐张判断: "已抬起(True) / 平放(False) / 看不出(None)" ✓

        用**滑动匹配**(读牌+量抬起同一机制 ✓): 只依赖牌自己的图案 → 不受邻牌遮挡 ✓
        (顶边/底边法都会被邻牌污染 ✗: 实测 真值5 → 顶边法12 / 底边法0)
        """
        from ..guandan import percept as _P

        if img is None:
            return [None] * len(xs)
        try:
            _cards, _info = _P.tm_read_hand(img)
        except Exception as e:  # noqa: BLE001
            # 不静默(教训: 一次 NameError 被吞掉, 整条直选链路全废还看不出来 ✗)
            self.log(f"  [servo] ✗ 读抬起失败: {type(e).__name__}: {e}")
            return [None] * len(xs)
        by_x = {int(x_): l_ for _s, _r, x_, l_ in _cards}
        # 兜底(2026-09-17): 坐标对不上时(不同来源的牌位/带漂移), 按**顺序对齐** ——
        #   两侧都是"从左到右", 第 i 个目标天然对应第 i 张读到的牌 ✓ (实测 27 = 27 ✓)
        rd = sorted((int(x_), l_) for _s, _r, x_, l_ in _cards)
        tg = sorted((int(x), i) for i, x in enumerate(xs))
        by_order = {}
        if len(rd) == len(tg):
            for (xr, l_), (xt, _i) in zip(rd, tg):
                by_order[xt] = l_
        # 最强兜底(2026-09-17): **按手牌索引对齐** —— 伺服本来就是按索引决策的,
        #   读取的牌也是从左到右 ⇒ 第 idx 张目标 = 读取里第 idx 张 ✓ (不依赖任何坐标来源 ✓)
        by_idx = {}
        if idxs is not None and len(_cards) > max(idxs, default=-1):
            for i, x in enumerate(xs):
                if i < len(idxs) and 0 <= idxs[i] < len(_cards):
                    by_idx[int(x)] = _cards[idxs[i]][3]
        out = []
        for x in xs:
            got = by_idx.get(int(x))
            if got is None:
                got = by_x.get(int(x))
            if got is None:
                for xx, ll in by_x.items():
                    if abs(xx - int(x)) <= 10:   # 点击坐标=牌位+6px, 容差要放宽 ✓
                        got = ll
                        break
            if got is None:
                got = by_order.get(int(x))
            out.append(None if got is None else bool(got >= 18))
        return out

    def _wait_ready(self, n: int, timeout: float = 5.0) -> bool:
        """等到"**画面停稳 且 牌位数量 == n**"为止(2026-09-18 用户两次指出的坑)。

        只看"停稳"会被出牌动画骗 ✗ —— 动画期间牌面**会短暂全没** ⇒ 连续两帧都是空的
        ⇒ 像素差≈0 ⇒ 误判"停稳"通过 ✓(人工模式实测: 档案里混进一张空帧 ✗)
        """
        from ..guandan import locate as L

        t0 = time.time()
        while time.time() - t0 < timeout:
            self._wait_stable(1.2)
            img = self._snap()
            if img is not None and n > 0 and len(L.locate(img, n)[0]) == n:
                return True
            time.sleep(0.3)
        return False

    def _select_cards(self, idxs: list, n: int, rounds: int = 3) -> bool:
        """**选牌到"游戏真值 = 目标"为止** —— 把人工托管那套搬进自动路径(2026-09-18 用户拍板)。

        人工模式(同一套定位/点击, 但每步过真值)27 张全出完、**零失误** ✓;
        旧自动路径用 `tm_read_hand` 的 x + "读抬起"核对 ✗ ⇒ 读数一错就点偏、越修越乱(1/3 成功) ✗
        ⇒ 差别只在**校验方式** ✓

        · 坐标: 一律来自 `locate.locate()`(按张数的标定表 ✓), 不用读牌结果 ✗
        · 有真值: 逐位核对 `selIds` ⇒ 缺的补点、多的点掉, 一致才返回 ✓
        · 无真值(产品路径): 逐张点一次, 成败交给"出牌回执 + 手牌张数下降" ✓
        """
        from ..guandan import locate as L

        cdp = getattr(self, "cdp", None)
        want = sorted(int(i) for i in idxs)
        # ★ 2026-09-21: 牌位偏格的**自校正**(用户铁律: 禁 layout 常量, 当帧实测+校验)
        #   实测: 手牌 21 张时 `slots_from_right` 用固定 pitch=24 从右端左铺 ⇒ 整体偏左一格
        #        ⇒ 点目标 i 结果选中 i-1(真值日志: 目标=[20] 选中=[19])⇒ 连续 3 轮越修越左 ✗
        #   做法: 判据全部来自**真值**(不猜 ✓) —— 只在"点的全是目标的左邻"时把整排右移一格 ✓
        #   按张数分别记(不同张数偏的量不同) ✓
        _shifts = getattr(self, "_slot_shift_by_n", None)
        if _shifts is None:
            _shifts = self._slot_shift_by_n = {}
        shift = int(_shifts.get(int(n), 0))
        for r in range(rounds):
            if not self._wait_ready(n):
                self.log(f"  [sel] ✗ 画面未就绪(牌位数≠{n}) ⇒ 本轮不点")
                return False
            slots, _chk = L.locate(self._snap(), n)
            ids, sel = [], set()
            if cdp is not None and mode.TRUTH:       # ★ 只有**真值模式**才用游戏真值核对 ✓
                try:
                    t = cdp.truth() or {}
                    ids = list(t.get("handIds") or [])
                    sel = set(int(v) for v in (t.get("selIds") or t.get("selected") or []))
                except Exception:  # noqa: BLE001
                    ids = []
            if not ids:                      # 产品路径: 没有真值 ⇒ 只按目标逐张点一次 ✓
                for i in want:
                    if 0 <= i < len(slots):
                        self._tap_card_at(slots[i], wait=0.35)
                self._wait_stable(1.2)
                return True
            got = sorted(i for i, x in enumerate(ids) if x in sel)
            miss = [i for i in want if i not in got]
            extra = [i for i in got if i not in want]
            self.log(f"  [sel] 第{r + 1}轮 真值选中={[i + 1 for i in got]} "
                     f"目标={[i + 1 for i in want]} 缺={[i + 1 for i in miss]} "
                     f"多={[i + 1 for i in extra]}")
            if not miss and not extra:
                self.log(f"  [sel] ✓ 真值核对一致({len(want)} 张)")
                return True
            # ★ 整体偏格的自校正判据: 缺的全是目标、多的全是"目标的左邻" ⇒ 整排右移一格 ✓
            _wset = set(want)
            if (shift == 0 and got and miss and not extra
                    and all((g + 1) in _wset for g in got)):
                _shifts[int(n)] = 1
                shift = 1
                self.log("  [sel] ⚙ 实测到牌位整体偏左一格 ⇒ 本轮起点击位置右移一格(自校正) ✓")
            for i in extra + miss:           # 多的点掉、缺的补点(游戏是开关 ✓)
                cur, _c = L.locate(self._snap(), n)
                j = i + shift                # 自校正后的实际点击位 ✓
                if 0 <= j < len(cur):
                    self._tap_card_at(cur[j], wait=0.4)
            self._wait_stable(1.0)
        return False

    def _servo_select(self, idxs: list, rounds: int = 3) -> bool:
        """伺服选牌(用户 2026-09-17 设计的算法): **求差 → 多的回落 / 少的补抬 → 复核** ✓

        量出的"抬起集合"包含三类: ① 我们要的 ② 上一轮我们点过、这轮不要的 ③ 游戏自己抬的提示牌
        ⇒ ②要回落(点掉) ✓; ③**只能点一次**就放过 —— 点它反而会把它选上 ✗(会来回振荡)
        判据全部来自**同一份读取结果**(看和点同源 ✓); 坐标每次点击前重新量 ✓
        """
        from ..guandan import percept as _P

        want = set(int(i) for i in idxs)
        tried_extra: set = set()          # 点过的"多余抬起"位 —— 只点一次, 防振荡 ✓
        for r in range(rounds):
            img = self._snap()
            try:
                cards, _info = _P.tm_read_hand(img)
            except Exception as e:  # noqa: BLE001
                self.log(f"  [servo] ✗ 读抬起失败: {type(e).__name__}: {e}")
                return
            raised = {i for i, c in enumerate(cards) if c[3] >= 18}
            miss = sorted(want - raised)                  # 少的 → 补抬 ✓
            extra = sorted(raised - want - tried_extra)   # 多的 → 回落(每个只试一次) ✓
            self.log(f"  [servo] 第{r + 1}轮 需补={len(miss)} 需落={len(extra)}")
            if not miss and not extra:
                self.log(f"  [servo] ✓ 就位({len(want)}张) → 可以出牌")
                return True
            for i in extra:                               # ★ 多了回落 ✓
                if i < len(cards):
                    fresh, _f = _P.tm_read_hand(self._snap())
                    _i = i if i < len(fresh) else None
                    if _i is not None:
                        self._tap_card_at(fresh[_i][2], wait=0.45)
                        self.log(f"  [servo] 回落 第{i}张 x={fresh[_i][2]}")
                    tried_extra.add(i)
            for i in miss:                                # ★ 少了补抬 ✓
                fresh, _f = _P.tm_read_hand(self._snap())
                if i < len(fresh):
                    self._tap_card_at(fresh[i][2], wait=0.5)
                    self.log(f"  [servo] 补点 第{i}张 x={fresh[i][2]}(当帧实量)")
        self._last_picked = list(getattr(self, '_last_picked', []))
        return False        # 没在 rounds 内就位 ✓

    def _clear_selection_via_truth(self) -> int:
        """把牌桌上**已有的选中**全部点掉 —— 用户算法第③步"多了回落"的精确版 ✓

        为什么必须做(2026-09-17 实测): 残留选中会和我们选的牌**混成非法牌型**
          ⇒ 游戏回『无效的牌型组合』✗(实测 selected=[94,90] + 我们点的 ♦5 = 3 张 ⇒ 被拒 ✓)
        怎么精确做: 真值给 selIds + handIds ⇒ 算出"是第几个牌位" ⇒ 点它(开关 ⇒ 取消) ✓
          每次点击前**重新取帧**、重新算位次(牌一抬起, 位置就会变 ✓)
        没有真值通道时返回 0(不改动, 交给下游的回执归因 ✓)
        """
        cdp = getattr(self, "cdp", None)
        if cdp is None:
            return 0
        import landlord_counter.guandan.percept as _P

        cleared = 0
        for _round in range(4):
            try:
                tr = cdp.truth() or {}
            except Exception:  # noqa: BLE001
                break
            ids = tr.get("handIds") or []
            sel = tr.get("selIds") or tr.get("selected") or []
            if not ids or not sel:
                break
            pos = [ids.index(s) for s in sel if s in ids]
            if not pos:
                break
            img = self._snap()
            if img is None:
                break
            y0, y1 = _P.hand_band_measured(img)
            cards, _i = _P.tm_read_hand(img)
            for p in pos:
                if 0 <= p < len(cards):
                    self._tap_card_at(cards[p][2], wait=0.45)
                    cleared += 1
            self._wait_stable(0.9)
        if cleared:
            self.log(f"  [gesture] 回落: 点掉桌上已有的选中 {cleared} 次 ✓")
        return cleared

    def direct_play(self, idxs: list[int], n: int, rounds: int = 2,
                    ranks: list | None = None) -> bool:
        """直选执行: 点选 → 校验张数 → 出牌 → 回执; 失败清选后再来一轮。"""
        # ★ 选牌与核对已统一到 _select_cards(坐标走 locate 标定表 / 核对走真值 ✓)
        _ = ranks                      # 保留签名兼容(调用方仍在传 ✓)
        # ★★ 先"回落"桌上**已有的选中**(用户算法第③步) —— 否则残留会和我们选的牌
        #   混成非法牌型, 游戏回『无效的牌型组合』✗(2026-09-17 实测踩到)
        self._clear_selection_via_truth()

        first = self._snap()
        before = self.L.white_count(first)
        base_lift = self._lift(first)
        self._lift_min = base_lift if self._lift_min is None else min(self._lift_min, base_lift)
        # ---- 清残留选中(实测: 残留会让"我们选的+残留"变成非法牌型 → 出牌被拒) ----
        # "空"基线估计: 取"见过的最小值"与 250 的更小者(实测空手牌抬起≈196; 脏值会带偏自适应)
        # ★ 删除"盲点清残留"(2026-09-17 实测有害 ✗): 游戏"点一张选一整组" → 盲点会把整手牌全选上 ✗
        #   实测: 从 16837 一路振荡(16837↔5801↔16300) → 越清越乱, 且把牌桌搞脏 ✗
        #   残留只可能来自"我们自己的选错"; 正确做法是**绝不盲点** —— 宁可本轮放弃 ✓
        # "空"基线: **动态实测**(2026-09-17 修正 ✗→✓)
        #   旧写法 min(self._lift_min, 250) 把基线硬压到 250 ✗ —— 但本界面里"游戏自己抬起的
        #   提示牌(如打A 时高亮的 A)"就有 ~3000 抬起 ✗ → 被误判成"我们选了牌" ✗ → 直选全部拒绝 ✓
        #   正解: 用本会话**观察到的最小抬起**当基线, 不设上限 ✓
        empty = self._lift_min if self._lift_min is not None else base_lift
        # ★ 不再"开局就放弃"(2026-09-17 用户算法): 有残留/有游戏自带高亮都**没关系** ✓
        #   伺服循环(_servo_select)会逐张核对我们想要的牌位是否已抬起, 缺的补点 ✓
        #   最终由"出牌回执"判成败 —— 不在这里做任何臆测 ✗
        _ = (self._lift_min, empty)          # 保留基线供后续诊断, 不做阻断
        for r in range(rounds):
            if r:
                self.log("  [gesture] ↻ 直选重试(重新取帧)")
                time.sleep(1.0)
            # ★★ 选牌 = "**选到真值一致为止**"(2026-09-18 用户拍板, 人工托管那套搬进来 ✓)
            #   坐标一律来自 locate(按张数的标定表 ✓), 不用读牌结果 ✗;
            #   有真值就逐位核对 selIds ✓ ⇒ 缺的补点、多的点掉, 一致才往下走 ✓
            #   旧做法(用 tm_read_hand 的 x + "读抬起"核对)会被读错带偏 ⇒ 实测只有 1/3 成功 ✗
            if not self._select_cards(idxs, n):
                self.log("  [gesture] ✗ 选牌未与真值一致 ⇒ 本轮不按出牌(不猜、不硬按)")
                self.clear(idxs, n)
                continue
            # ★ 点完与按出牌之间要**留够时间**(2026-09-17 实测): 最小路径等 0.9s ⇒ 100% ✓
            self._wait_stable()
            time.sleep(0.5)
            pp = self._play_btn() or self.btn("play")     # ★ 立刻按 ✓
            if not pp:
                self.clear(idxs, n)
                continue
            self._press(pp, wait=1.6)
            if self.wait_receipt(before):
                return True
            # ★★ 失败回滚: 优先"真值精确回落"(2026-09-18), 没真值就用老办法 ✓
            self.log("  [gesture] ↻ 出牌未生效 → 精确回落")
            if not self._clear_selection_via_truth():
                self.clear(idxs, n)
            time.sleep(0.3)
            continue
        return False

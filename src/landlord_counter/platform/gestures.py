"""通用手势执行层: 点选验证 / 扫点 / 提示选牌 / 回执轮询 / 两轮重试。

与游戏无关——游戏只需提供 GestureLayout(牌位公式/按钮坐标/判据函数)。
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Callable

from .actloop import ActReport, Evidence

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
    lift_one: float = 1260.0    # 单张抬起量(Bromite 实测 3 张=3779 → ≈1260/张; 原 1460 偏大)
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

    def _tap_card_at(self, x: int, wait: float = 0.45) -> None:
        """点手牌某位置: 优先 CDP(可信事件), 否则 adb tap。

        实测教训(2026-09-15): adb 的 touch 能让牌视觉上抬起, 但**游戏内部不认这手牌**
        (点"出牌"毫无反应); 改用 CDP 派发的鼠标事件后, "选牌→出牌"一次成功 ✓。
        """
        if self.mt is not None:                 # ① 拟人化输入优先
            try:
                self.mt.tap(x, self.L.hand_y)
                return
            except Exception as e:  # noqa: BLE001
                self.log(f"  [input] MaaTouch 点牌失败({type(e).__name__}) → 回落")
        if self.cdp is not None:
            try:
                self.cdp.click_screen(x, self.L.hand_y, settle=wait)
                return
            except Exception as e:  # noqa: BLE001
                self.log(f"  [input] CDP 点牌失败({type(e).__name__}) → 回落 adb")
        self.dev.tap(x, self.L.hand_y, wait=wait)

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
        pp = self.btn("play")
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

    def direct_play(self, idxs: list[int], n: int, rounds: int = 2,
                    ranks: list | None = None) -> bool:
        """直选执行: 点选 → 校验张数 → 出牌 → 回执; 失败清选后再来一轮。"""
        first = self._snap()
        before = self.L.white_count(first)
        base_lift = self._lift(first)
        self._lift_min = base_lift if self._lift_min is None else min(self._lift_min, base_lift)
        want_x = [self._pos(i, n) for i in idxs]
        pre_select = first
        # ---- 清残留选中(实测: 残留会让"我们选的+残留"变成非法牌型 → 出牌被拒) ----
        # "空"基线估计: 取"见过的最小值"与 250 的更小者(实测空手牌抬起≈196; 脏值会带偏自适应)
        empty = min(self._lift_min if self._lift_min is not None else 250, 250)
        if base_lift > empty + 400:
            for k in range(min(n, 30)):
                cur = self._lift(self._snap())
                if cur <= empty + 400:
                    break
                self._tap_card_at(self._pos(k, n), wait=0.45)
            self.log(f"  [gesture] 清残留选中: {base_lift} → {self._lift(self._snap())} (空基线≈{empty})")
        for r in range(rounds):
            if r:
                self.log("  [gesture] ↻ 直选重试(重新取帧)")
                time.sleep(1.0)
            if not self.select(idxs, n, ranks=ranks):
                self.clear(idxs, n)
                continue
            time.sleep(0.5)
            cur = self._snap()
            est = self.selected_count(cur, base_lift)
            # 身份校验(2026-09-15): 抬起的牌位必须与"想点的牌位"吻合, 否则就是点到了邻牌
            try:
                from ..guandan import percept as _P

                got = [c for c, _w in _P.lifted_columns(pre_select, cur)]
                if got:
                    miss = [x for x in want_x
                            if not any(abs(x - g) <= 16 for g in got)]
                    if miss:
                        self.log(f"  [gesture] ✗ 身份校验失败: 想点{want_x} 实际抬起{got}")
                        self.clear(idxs, n)
                        continue
            except Exception:  # noqa: BLE001
                pass
            if est == 0 or abs(est - len(idxs)) > max(1, len(idxs) // 2):
                self.log(f"  [gesture] ✗ 选牌校验失败(选中≈{est} vs 目标{len(idxs)})")
                self.clear(idxs, n)
                continue
            pp = self.btn("play")
            if not pp:
                self.clear(idxs, n)
                continue
            self._press(pp, wait=1.6)
            if self.wait_receipt(before):
                return True
            self.log("  [gesture] ↻ 出牌未生效 → 补点一次")
            self._press(pp, wait=1.6)
            if self.wait_receipt(before, polls=6):
                return True
            self.clear(idxs, n)
        return False

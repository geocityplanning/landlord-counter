"""掼蛋(开源 Web 版)适配器: 把既有 percept/ai 接进平台通用接口。

过渡期说明: 复用 ../guandan 下已标定的几何常量与工具, 后续逐步下沉到 platform。
"""
from __future__ import annotations

import json
import os
import re
import time

from ..types import Action, ExecResult, GameAdapter, Observation, SettleInfo

# 复用已标定常量(见 docs/M4_掼蛋几何参考.md)
from ...guandan import ai as AI
from ...guandan import percept as P
from ...guandan import rules as R
from ...guandan.agent import BTN_HINT, BTN_PASS, BTN_PLAY, JIPAI, WHITE_MIN, gold_button

# 读牌帧留证目录(读牌与"块宽真值"分歧时存帧, 供离线判定谁对)
READ_DUMP_DIR = os.getenv("GUANDAN_READ_DUMP_DIR", "/tmp/guandan_read_dumps")
DUMP_MAX = int(os.getenv("GUANDAN_READ_DUMP_MAX", "20"))     # 单次运行最多存几帧
DUMP_GAP = float(os.getenv("GUANDAN_READ_DUMP_GAP", "15"))   # 两帧最小间隔(秒)


class GuandanAdapter(GameAdapter):
    name = "guandan"
    package = None
    start_url = "http://172.18.0.1:8123/index.html"

    def __init__(self, ours: bool | None = None) -> None:
        self.ours = (os.getenv("GUANDAN_OURS", "0") == "1") if ours is None else ours
        self._last_seat = {"who": None, "blocks": {}}
        self._ex = None
        # RL 决策臂(2026-09-15): 开源预训练权重在我方合法候选里选牌 → 必须走点选直出
        self.rl = os.getenv("GUANDAN_DECIDE", "").strip().lower() == "rl"
        self._rl = None
        self._rl_hist: list = []
        self._rl_played = [0.0, 0.0, 0.0, 0.0]
        self._read_fail_n = 0        # 连续读牌失败次数(空读治理: 不空转)
        self._dump_n = 0             # 帧留证计数
        self._dump_t = 0.0
        self._tap_cal = None         # 点选自标定结果: {"n0","x0","raw","pairs"}

    def attach(self, device, vision=None) -> None:
        super().attach(device, vision)
        self._build_executor()

    def _build_executor(self) -> None:
        from ..a11y import A11y
        from ..gestures import Executor, GestureLayout

        self.a11y = A11y(getattr(self.device, "serial", "127.0.0.1:5555"))

        def _btn(name: str, fallback):
            """无障碍树按文字取按钮中心(精确), 取不到用固定坐标。"""
            pat = {"hint": "提示", "play": "出牌", "pass": "不出"}[name]
            try:
                n = self.a11y.button(pat)
                if n:
                    return n.center
            except Exception:  # noqa: BLE001
                pass
            return fallback

        layout = GestureLayout(
            card_tap_x=P.card_tap_x,
            card_positions=self._cal_positions,
            hand_y=875,
            btn_hint=BTN_HINT,
            btn_play=BTN_PLAY,
            btn_pass=BTN_PASS,
            lift_px=P.lifted_px,
            my_turn=P.my_turn,
            white_count=P.white_count,
        )
        self._ex = Executor(self.device, layout, log=print)

    # ---------- 感知 ----------
    def start_button(self, frame):
        # 优先无障碍文字按钮(再来一局/开始游戏), 失败回落金块检测
        try:
            for pat in ("再来一局", "开始游戏", "继续游戏"):
                n = self.a11y.button(pat)
                if n:
                    return n.center
        except Exception:  # noqa: BLE001
            pass
        return gold_button(frame)

    def progress_signal(self, frame):
        return P.white_count(frame)

    def _track_seat(self, frame) -> None:
        cur = P.blocks_by_seat(frame)
        changed = None
        for nm, box in cur.items():
            pb = self._last_seat["blocks"].get(nm)
            if pb is None or abs(box[0] - pb[0]) + abs(box[1] - pb[1]) > 10:
                changed = nm
        if changed:
            self._last_seat["who"] = changed
        elif not cur and self._last_seat["blocks"]:
            self._last_seat["who"] = None
        self._last_seat["blocks"] = cur

    def _calibrate_taps(self, frame) -> None:
        """点选自标定: 逐位试一次, 用"实际抬起位"建**真值牌位图**。

        为什么需要(实测 2026-09-15):
          ① 布局左缘与我们假设的略有差 → 最左那张点不中(点 x=94 无任何变化);
          ② 游戏会**自动配对**: 点一张会连带选中同点数的另一张(点 238 时 307 也抬起);
          ③ 页面重开后布局可能变 → 每轮重新标一次最稳。
        产出: x0(真值左缘) + 每位"点了会抬起哪些列"(raw) + 配对关系(pairs)。
        代价: 一次 ~n 次点选(满手 27 张约 30s), 且只点选不出牌, 不影响牌局。
        """
        if self.device is None:
            return
        n = P.hand_card_count_est(frame)
        if n < 20:
            return
        est = P.card_positions(frame, n)
        raw: dict = {}
        for i, x in enumerate(est):
            b = self.device.snap()
            self.device.tap(x, 875, wait=0.55)
            aa = self.device.snap()
            raw[i] = [c for c, _w in P.lifted_columns(b, aa)]
            self.device.tap(x, 875, wait=0.35)      # 复位(再点一次取消选中)
        xs0 = sorted(c - 24 * i for i, cols in raw.items() for c in cols)
        if not xs0:
            print("  [标定] 无任何抬起 → 放弃(触控/页面可能异常)", flush=True)
            return
        x0 = float(xs0[len(xs0) // 2])
        pairs = {i: sorted({(c - x0) / 24 for c in cols
                            if abs(c - (x0 + 24 * i)) > 16})
                 for i, cols in raw.items()}
        self._tap_cal = {"n0": n, "x0": x0, "raw": raw, "pairs": pairs}
        hit = sum(1 for i, cols in raw.items() if cols)
        print(f"  [标定] 真值左缘 x0={x0:.0f} | 命中 {hit}/{n} 位 | 配对关系 {sum(1 for v in pairs.values() if v)} 处",
              flush=True)

    def _cal_positions(self, frame, n: int) -> list:
        """执行层取位: 有标定 → 用真值图(按张数平移); 否则用实测左缘公式。"""
        cal = self._tap_cal
        if cal:
            x0 = cal["x0"] + (cal["n0"] - n) * 12     # 整排居中: 张数少 1 → 左缘右移 12px
            return [int(x0 + 24 * i + 12) for i in range(n)]
        return P.card_positions(frame, n)

    def _dump_read_evidence(self, frame, tag: str, info: dict) -> None:
        """帧留证: 读牌与块宽真值分歧时, 存一帧 PNG + 两种读数 JSON。

        目的: 现场只看到"读 6 张 vs 块宽推 13 张"这类分歧, 无法判定谁对;
        存下帧后可用 tools/analyze_read_dumps.py 离线复读(同一帧跑多种读法), 一次定案。
        """
        now = time.time()
        if frame is None or self._dump_n >= DUMP_MAX or now - self._dump_t < DUMP_GAP:
            return
        self._dump_n += 1
        self._dump_t = now
        try:
            import cv2

            os.makedirs(READ_DUMP_DIR, exist_ok=True)
            ts = time.strftime("%Y%m%d_%H%M%S")
            base = os.path.join(READ_DUMP_DIR, f"{ts}_{tag}")
            cv2.imwrite(base + ".png", frame)
            with open(base + ".json", "w", encoding="utf-8") as f:
                json.dump({"tag": tag, "ts": ts, **info}, f, ensure_ascii=False, indent=1)
            print(f"  [留证] {base}.png | {info}", flush=True)
        except Exception as e:  # noqa: BLE001
            print(f"  [留证] 失败: {e}", flush=True)

    def _band_looks_like_hand(self, frame) -> bool:
        """手牌带是否**真的**是手牌: 有足够宽的块且块内白密度够高。

        用途: "我方回合"判据会被动画帧/桌面残影骗到, 于是去读牌 → 读不到 → 点提示 →
        提示也没反应 → 每轮空转打一条"提示空且无手牌"(实测一晚几十条)。加这道闸门后
        不像手牌就直接当"非我回合"跳过, 不产生假动作。
        实测(2026-09-15): 只靠"密度"挡不住开始界面(块46-673/密度0.67/块宽推23张, 看着像 23 张牌)
        → 主循环会一直对着开始界面空转"提示空且无手牌"。改为两道硬判据:
          ① 画面没有"金钮"(开始游戏/再来一局/结算) = 不是决策时刻;
          ② 手牌带结构自洽(块宽反推张数 ≈ 卡边界计数, 见 P.hand_is_real)。
        """
        try:
            if gold_button(frame) is not None:
                return False
            ok, info = P.hand_is_real(frame)
            if not ok:
                self._last_band_info = info
                return False
            return True
        except Exception:  # noqa: BLE001
            return True

    def sense(self, frame) -> Observation:
        self._track_seat(frame)
        if not P.my_turn(frame):          # 手牌白卡 + 按钮可用(防残局误判)
            return Observation(frame=frame, my_turn=False)
        if not self._band_looks_like_hand(frame):
            return Observation(frame=frame, my_turn=False)   # 假"我回合" → 跳过, 不空转
        # 期望张数: 优先"块宽实测真值"(不依赖 VLM/像素分段, 实测比 hand_columns 准)
        n_vis = P.hand_card_count_est(frame) or P.hand_columns(frame)
        if self.rl and self._tap_cal is None and n_vis >= 25:
            self._calibrate_taps(frame)          # 满手时标定一次(本轮只做一次)
        # 优先"实测几何分段读"(整排直读会只读左半排, 实测 27 张只读出 12 张); 失败再回落整排。
        # 整轮重试 2 次: VLM 偶发空返回(服务端排队), 实测同一帧 3 次里 1 次失手 → 重试可兜住。
        hand = None
        for _try in range(2):
            hand = P.read_hand_strips_measured(self.vision, frame, n_vis) if n_vis else None
            if hand:
                break
        if not hand:
            hand = P.read_hand_ordered(self.vision, frame, expected=n_vis)
        if not hand:
            self._read_fail_evidence = {"n_est": n_vis, "n_read": None,
                                        "block": list(P.hand_block(frame) or (None, None))}
            self._dump_read_evidence(frame, "read_empty", self._read_fail_evidence)
            self._read_fail_n += 1
            if self._read_fail_n >= 3:      # 连续读不到 → 本帧不当"我回合", 交给看门狗/健康检查
                return Observation(frame=frame, my_turn=False)
            return Observation(frame=frame, my_turn=True, hand=None, extra={"read_fail": True})
        self._read_fail_n = 0
        table = P.read_table_last(self.vision, frame)
        cards = table or []
        # 一致性闸门: 牌位已与张数解耦(实测牌位), 故张数相差 1 张无害 → 只挡 >2 的离谱读数
        if hand and n_vis and abs(n_vis - len(hand)) > 1:
            hand2 = P.read_hand_ordered(self.vision, frame, expected=n_vis)
            if hand2:
                hand = hand2
            if abs(n_vis - len(hand)) > 2:      # 重读后仍离谱 → 不敢用, 走提示驱动
                self._dump_read_evidence(frame, "mismatch", {
                    "n_est": n_vis, "n_read": len(hand),
                    "block": list(P.hand_block(frame) or (None, None)),
                    "cards": [str(c) for c in hand]})
                return Observation(frame=frame, my_turn=True, hand=None, extra={"read_fail": True})
        return Observation(frame=frame, my_turn=True, hand=hand, table=cards,
                           extra={"n_vis": n_vis})

    # ---------- 决策 ----------
    def decide(self, obs: Observation) -> Action:
        if obs.extra.get("read_fail") or not obs.hand:
            return Action("play", combo=None, meta={"hint": True, "why": "读牌失败→提示驱动"})
        cards = obs.table or []
        if cards:
            gl = R.identify(cards, JIPAI)
            if getattr(gl, "is_invalid", False):
                return Action("play", combo=None, meta={"hint": True, "why": "待压牌非法→提示驱动"})
        if not self.ours:
            return Action("play", combo=None, meta={"hint": True, "why": "MVP提示驱动"})
        st = AI.GameState()
        st.jipai = JIPAI
        st.shi_dui_you = self._last_seat.get("who") == "top"
        last = R.identify(cards, JIPAI) if cards else None
        if self.rl:
            return self._decide_rl(obs, last, cards)
        choice = AI.choose_play(obs.hand, last, st)
        if choice is None or getattr(choice, "is_invalid", False):
            return Action("pass", meta={"why": "引擎判不出"})
        return Action("play", combo=choice, meta={"why": "自研决策"})

    def _decide_rl(self, obs: Observation, last, cards: list) -> Action:
        """RL 臂: 预训练权重在"我方全部合法出牌"里选 → 标记 direct(执行层点选直出)。"""
        who = self._last_seat.get("who")
        wi = {"right": 1, "top": 2, "left": 3}.get(who or "", 1)
        if len(obs.hand) >= 25:                      # 手牌回到满手 = 新一局 → 清历史
            self._rl_hist.clear()
            self._rl_played = [0.0, 0.0, 0.0, 0.0]
        if last is not None and (not self._rl_hist or self._rl_hist[-1][1] is not last):
            self._rl_hist.append((wi, last))
            self._rl_played[wi] = min(27.0, self._rl_played[wi] + len(cards))
        if self._rl is None:
            from ...guandan.rl_policy import RLPolicy

            self._rl = RLPolicy()
            print(f"▶ RL 决策器已加载: {os.path.basename(self._rl.path)}", flush=True)
        cands = AI.zhao_ke_chu_de_pai(obs.hand, last, JIPAI)
        mine = float(len(obs.hand))
        others = [max(0.0, 27 - self._rl_played[i]) for i in (1, 2, 3)]
        choice, info = self._rl.choose(cands, obs.hand, self._rl_hist[-16:],
                                       [mine] + others + [mine + sum(others)], (wi, last), 0)
        print(f"  [rl] 手牌{len(obs.hand)} 候选{info['n_cand']}(可映射{info['mapped']}) → "
              f"{R.group_to_str(choice) if choice is not None else '不出'} | value={info['value']:.3f}",
              flush=True)
        if choice is None:
            return Action("pass", meta={"why": "RL判不出/不出"})
        self._rl_hist.append((0, choice))
        self._rl_played[0] = min(27.0, self._rl_played[0] + len(choice.cards))
        return Action("play", combo=choice, meta={"why": "RL决策", "direct": True})

    # ---------- 执行 ----------
    def execute(self, action: Action, obs: Observation) -> ExecResult:
        if self._ex is None:
            self._build_executor()
        ex = self._ex
        assert ex is not None
        if action.kind == "pass":
            ex.pass_turn()
            return ExecResult(True, 0, "不出")
        # RL 臂: 打的是我们自己选的牌 → 必须点选直出(提示只会出游戏自己选的牌)
        if action.meta.get("direct") and action.combo is not None and obs.hand:
            idxs = _map_indices(obs.hand, action.combo.cards)
            if idxs:
                ranks = [getattr(obs.hand[i], "zhi", None) for i in idxs
                         if 0 <= i < len(obs.hand)]
                if ex.direct_play(idxs, len(obs.hand), ranks=ranks):
                    return ExecResult(True, 0, "直选出牌(RL)")
                rpt = getattr(ex, "last_report", None)
                if rpt is not None and (rpt.not_our_turn or rpt.skipped):
                    # 执行器规范: 识别/活性不满足 ⇒ 跳过, 不是失败(不计入失败率)
                    return ExecResult(True, 0, f"跳过 · {rpt.reason}", skipped=True)
                return ExecResult(False, 1, "直选失败(RL)")
        want = len(action.combo.cards) if action.combo is not None else None
        follow = bool(obs.table)
        r = ex.play_by_hint(want=want, follow=follow)
        if r == "ok":
            return ExecResult(True, 0, "出牌成功")
        if r == "none":
            if follow:
                ex.pass_turn()
                return ExecResult(True, 0, "提示无可出→不出")
            if obs.hand:      # 领出却提示为空 → 盲出最小单张(保流程)
                ex.dev.tap(ex.L.card_tap_x(0, len(obs.hand)), ex.L.hand_y, wait=0.4)
                ex.dev.tap(*ex.L.btn_play, wait=1.6)
                return ExecResult(True, 0, "提示空→盲出最小单张")
            return ExecResult(False, 0, "提示空且无手牌")
        # mismatch / fail → 直选我们的决策(有组合时), 否则回落失败
        if action.combo is not None and obs.hand:
            idxs = _map_indices(obs.hand, action.combo.cards)
            if idxs and ex.direct_play(idxs, len(obs.hand)):
                return ExecResult(True, 1, "直选成功")
        return ExecResult(False, 1, f"提示执行={r} 且直选未成")


def _map_indices(hand, cards):
    """把组合中的牌映射回手牌索引(用于直选)。"""
    from ...guandan.agent import map_indices

    try:
        return map_indices(hand, cards)
    except Exception:  # noqa: BLE001
        return None

    # ---------- 结算 ----------
    def settle(self, frame) -> SettleInfo | None:
        """结算解读: 优先无障碍文字(免 VLM), 否则回落 VLM 读弹窗。"""
        try:
            blob = self.a11y.text_blob(force=True)
        except Exception:  # noqa: BLE001
            blob = ""
        if "头游" in blob:
            head = ""
            m = re.search(r"头游[:：]\s*(\S+)", blob)
            if m:
                head = m.group(1)
            win = True if head in ("南", "北", "我方") else (False if head in ("西", "东") else None)
            up = ""
            m2 = re.search(r"升级[:：]?\s*([+\-]?\d+\s*级)", blob)
            if m2:
                up = m2.group(1)
            raw = f"头游={head};升级={up}"
            return SettleInfo(raw=raw, win=win)
        if self.vision is None:
            return None
        txt, win = P.read_settle(self.vision, frame)
        if "头游" not in txt and "升级" not in txt:
            return None
        return SettleInfo(raw=txt.strip()[:60], win=win)

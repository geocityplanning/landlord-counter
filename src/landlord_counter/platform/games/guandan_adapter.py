"""掼蛋(开源 Web 版)适配器: 把既有 percept/ai 接进平台通用接口。

过渡期说明: 复用 ../guandan 下已标定的几何常量与工具, 后续逐步下沉到 platform。
"""
from __future__ import annotations

import json
import os
import re
import time

from ..types import Action, ExecResult, GameAdapter, Observation, SettleInfo
from ..game_log import GameLog
from ..usage import UsageMeter
from ...guandan.tracker import CardTracker

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
        # 记牌器 + 牌局事件日志(追溯"谁打了什么牌"/"池子里还剩什么"; 见 docs/记牌器_调研.md)
        self.log = GameLog(game_id=f"gd-{time.strftime('%Y%m%d-%H%M')}", game_type="guandan")
        self.tracker = CardTracker()
        # AI 算力计量(伴随包 → 底座计费; 只记消耗, 不带价格)
        self.usage = UsageMeter(game="guandan")
        self._last_sig: dict = {}          # 座位 → 上次观测到的手牌签名(去重: 同一手只计一次)
        self._last_block: dict = {}        # 座位|块位置 → 上次读过的块(桌面变化去重)
        self._rl_played = [0.0, 0.0, 0.0, 0.0]
        self._read_fail_n = 0        # 连续读牌失败次数(空读治理: 不空转)
        self._turn_checked_at = 0.0  # 上次"游戏真值"复核时刻(CDP 用)
        self._n_truth = 0            # 实测(反推)到的确切张数
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
        # 拟人化输入(MaaTouch): 真实 MotionEvent(压力/接触/时长) —— 产品路径用这个
        if os.getenv("GUANDAN_NO_MAATOUCH", "0") != "1":
            try:
                from ..maatouch import MaaTouch

                mt = MaaTouch(getattr(self.device, "serial", "127.0.0.1:5555"))
                if mt.alive():
                    self._ex.mt = mt
                    print(f"▶ 输入走 MaaTouch 拟人化(压力/微移/随机时长) {mt.max_x}x{mt.max_y}", flush=True)
            except Exception as e:  # noqa: BLE001
                print(f"⚠ MaaTouch 不可用({e}) → 回落", flush=True)
        # 按钮点击走 CDP(可选, 调试用): 实测 adb tap 点"出牌"不生效, CDP 派发可以
        if os.getenv("GUANDAN_USE_CDP", "0") == "1":
            try:
                from ..cdp import CDP

                self._ex.cdp = CDP(url_filter="8123")
                print("▶ 按钮输入走 CDP(Bromite 调试口)", flush=True)
            except Exception as e:  # noqa: BLE001
                print(f"⚠ CDP 不可用({e}) → 按钮仍走 adb", flush=True)

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
        """进展信号 = **帧指纹**(降采样后哈希)。

        原来用 white_count: 画面冻住时它仍会因手牌带抖动而变 ✗ →
        看门狗永远不触发 → 牌局结束后整轮空转(实测 30 分钟里后 12 分钟全空转 ✗)。
        改成帧指纹: 画面不变 → 指纹不变 → 看门狗按时恢复。
        """
        try:
            import hashlib
            sub = frame[::12, ::12]
            return hashlib.md5(sub.tobytes()).hexdigest()[:16]
        except Exception:                            # noqa: BLE001
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

    def _probe_card_count(self, frame) -> int:
        """反推**确切张数**(边界判别法)。

        原理: 整排是"居中 + 固定间距" → 张数估**多**时, 算出的"第 1 张"位置会落到
        牌行**左边界之外**(点下去没反应); 张数估**少**时, 位置落在行内(会选中)。
        ⇒ 从大到小试, **第一个能点中的 n 就是真值**(它正好是行首那张)。
        代价: 每次标定最多 3 次点击, 且点完立刻取消, 不留残留。
        """
        ex = self._ex
        if ex is None or getattr(ex, "cdp", None) is None or self.device is None:
            return 0
        est = P.hand_card_count_est(frame) or P.hand_columns(frame)
        if est <= 0:
            return 0
        for cand in (est + 1, est, est - 1, est - 2, est - 3):
            if not (8 <= cand <= 27):
                continue
            try:
                pts = ex.cdp.card_tap_points(cand)
            except Exception:  # noqa: BLE001
                continue
            if len(pts) != cand:
                continue
            x, y = pts[0]                     # 只看"第 1 张": 估多会落到行外
            i0 = self.device.snap()
            if i0 is None:
                continue
            try:
                ex.cdp.click_screen(x, y, settle=0.55)
            except Exception:  # noqa: BLE001
                continue
            i1 = self.device.snap()
            if i1 is None:
                continue
            if P.lifted_px(i1) > P.lifted_px(i0) + 300:
                ex.cdp.click_screen(x, y, settle=0.45)      # 取消, 恢复干净
                print(f"  [张数标定] 视觉估{est} → 实测 **{cand}** 张(行首点中)", flush=True)
                return cand
            print(f"  [张数标定] 试 {cand}: 行首点不中(位置在行外)", flush=True)
        print(f"  [张数标定] 未定(沿用视觉估 {est})", flush=True)
        return est

    def _cal_positions(self, frame, n: int) -> list:
        """执行层取位(按可信度排序):

        ① **卡边界实测**(直接量出来的锚点, 不依赖任何假设) —— 手工验证过: 点它给的 x=208
           第 5 张确实被选中 ✓;
        ② 点选自标定图(从"点击→抬起"的对应关系反推的 x0, 会被游戏的"整组帮点"带偏 ✗);
        ③ 兜底: 块宽实测 / 公式。
        实测教训(2026-09-15): 标定给的 x0=47 反而把点选带偏(0 成功/13 失败),
        而卡边界给的 ~82 能选中 ⇒ 边界优先。
        """
        # ① 测试台真值几何(游戏源码公式, 需 CDP; 同时用于校准视觉)
        if os.getenv("GUANDAN_TRUTH_GEOM", "0") == "1" and self._ex is not None \
                and getattr(self._ex, "cdp", None) is not None:
            try:
                nc = self._n_truth or self._probe_card_count(frame) or n
                self._n_truth = nc
                pts = self._ex.cdp.card_tap_points(nc)
                if len(pts) == n:
                    self._truth_pts = pts
                    return [p[0] for p in pts]
            except Exception as e:  # noqa: BLE001
                print(f"    [真值几何] 失败({type(e).__name__}) → 回落卡边界", flush=True)
        # ①' **卡位实测(新版)**: card_slots 用"最长等距串 + 亮度判据", 实测对游戏真值 100% ✓✓
        # 教训(2026-09-17): 旧的 card_positions_by_edges 是过期几何 → 点位偏到邻牌/越界 → 
        # select() 里 `if not (0 < x < 720): continue` 静默跳过 → 直选永远失败 ✗
        try:
            xs = P.card_slots(frame)
            if xs and len(xs) == n:
                return [int(x + 6) for x in xs]      # 每张牌露出约 24px, 点其靠左内侧
        except Exception:                            # noqa: BLE001
            pass
        pe = P.card_positions_by_edges(frame)
        if pe:
            return pe
        cal = self._tap_cal
        if cal:
            x0 = cal["x0"] + (cal["n0"] - n) * 12
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
        self._observe_table_gated(frame)     # 记牌: 每帧都看桌面(别人的出牌也要记 ✓)
        if not P.my_turn(frame):          # 手牌白卡 + 按钮可用(防残局误判)
            return Observation(frame=frame, my_turn=False)
        # ① **先做模板读牌**(纯像素, 实测对真值 100% ✓) —— 读到了就不必再过老结构闸门
        # 教训(2026-09-16): 老的 hand_is_real/_band_looks_like_hand 是按旧几何估的,
        # 对残局 9 张手牌会误判(实测它估 15 张 vs 真值 9 张 ✗) → 把托管卡成 0 动作 ✗
        _tm_first = []
        _frame0 = frame                     # 记下"读牌时那一帧", 闸门换帧后要比对 ✓
        try:
            _tm_first = P.tm_read_hand(frame)[0]
        except Exception:  # noqa: BLE001
            _tm_first = []
        if not _tm_first and not self._band_looks_like_hand(frame):
            return Observation(frame=frame, my_turn=False)   # 假"我回合" → 跳过, 不空转
        # ★ 读牌时机闸门(2026-09-17): 有牌被抬起时**读不准** —— 抬起的牌会盖住右侧邻牌的
        #   竖条(实测 Q J 10 9 里抬起 10 → 只读出 J ✗) → 先点掉抬起的那张, 再重取帧读 ✓
        try:
            for _try in range(4):                  # 可能有多张被抬起 → 清到干净(最多 4 轮)
                lifted = P.lifted_xs(frame)
                if not lifted:
                    break
                if self._ex is not None:
                    for lx in lifted:
                        self._ex.dev.tap(int(lx), (self._ex.L.hand_y or 875) + 8, wait=0.35)
                time.sleep(0.35)
                frame = self.device.snap()         # ★ 每轮**重新取帧**再判:
                #   否则同一张被点偶数次(点掉又点回) → 永远清不干净 ✗ (2026-09-17 踩坑)
            frame2 = self.device.snap()
            if frame2 is not None and not P.lifted_xs(frame2):
                frame = frame2                     # 清干净了 → 用放平后的帧读 ✓
            else:
                # ★ 不再阻断(2026-09-17): 逐牌顶边裁切 + 两段式匹配已能让"有牌抬起"时照样读对
                #   (实测 3 张被选中时仍 42/42 = 100% ✓) —— 原来的阻断反而把托管卡成 0 动作 ✗
                print("  [读牌] 仍有牌抬起(清不净) → 不阻断, 用逐牌对齐照常读 ✓", flush=True)
        except Exception:  # noqa: BLE001
            pass
        # CDP 可用时: 用**游戏真值**复核"是不是我的回合"(像素启发式会被残局/动画骗)
        ex = self._ex
        if ex is not None and getattr(ex, "cdp", None) is not None:
            now = time.time()
            if now - getattr(self, "_turn_checked_at", 0.0) >= 4.0:
                try:
                    ok, why = ex.cdp.our_turn_probe(ex.L.btn_play)
                    self._turn_checked_at = now
                    if not ok:
                        print(f"    [真值] {why} → 跳过本帧", flush=True)
                        return Observation(frame=frame, my_turn=False)
                except Exception as e:  # noqa: BLE001
                    print(f"    [真值] 回合探针异常({type(e).__name__}) → 沿用像素判据", flush=True)
        # 期望张数: **模板读到的张数是权威**(实测真值 9 而老估算器给 12~15 ✗)
        # 教训(2026-09-16): 老 hand_card_count_est 过期 → 一致性闸门误判"离谱" → 判定不敢用 ✗
        n_vis = (len(_tm_first) if _tm_first
                 else (P.hand_card_count_est(frame) or P.hand_columns(frame)))
        if self.rl and self._tap_cal is None and n_vis >= 25:
            # ★ 停用"点选自标定"(2026-09-17): 它靠**试点牌**推点位/张数 ✗ → 会留下残留选中
            #   (实测: 重置后一跑起来就有 3137 抬起 ✗, 直选随即拒绝出牌 ✓)
            #   现在点位已是实测(card_slots ✓), 老标定纯属有害 → 不再调用 ✓
            # self._calibrate_taps(frame)
            self._tap_cal = {"deprecated": True}
        # 优先"实测几何分段读"(整排直读会只读左半排, 实测 27 张只读出 12 张); 失败再回落整排。
        # 整轮重试 2 次: VLM 偶发空返回(服务端排队), 实测同一帧 3 次里 1 次失手 → 重试可兜住。
        hand = None
        # ① **模板匹配优先**(纯像素, <5ms, 免费) —— 实测对游戏真值 100% ✓✓
        #    分层原则(2026-09-16 拍板): 大模型管"冷启动/兜底", 模板管"日常量产"。
        #    ⚠️ 花色编码要转换: 模板库 1♠2♣3♥4♦ → 牌库 0♠1♥2♣3♦ (不一致就全错 ✗)
        _TM_HUA2RULES = {1: 0, 2: 2, 3: 1, 4: 3, 0: None}
        # ⚠️ 闸门清过抬起并**换了帧** → 必须用新帧重读(否则用的是带遮挡那帧的旧读数 ✗)
        tm_reads = _tm_first
        if _tm_first and frame is not _frame0:
            try:
                tm_reads = P.tm_read_hand(frame)[0] or _tm_first
            except Exception:  # noqa: BLE001
                tm_reads = _tm_first
        if tm_reads:
            hand = [R.Card(zhi=z, hua=_TM_HUA2RULES.get(s)) for s, z, _x in tm_reads]
            self.usage.vlm_read(what="hand_tm", ok=True, n=len(hand))     # 计量: 0 成本路径
        if not hand:
            # ② 兜底: 大模型读(模板库尚未覆盖的牌型/界面改版)
            for _try in range(2):
                hand = P.read_hand_strips_measured(self.vision, frame, n_vis) if n_vis else None
                if hand:
                    break
            if not hand:
                hand = P.read_hand_ordered(self.vision, frame, expected=n_vis)
            self._meter_vlm("hand", ok=bool(hand), n_est=n_vis)
        if not hand:
            self._read_fail_evidence = {"n_est": n_vis, "n_read": None,
                                        "block": list(P.hand_block(frame) or (None, None))}
            self._dump_read_evidence(frame, "read_empty", self._read_fail_evidence)
            self._read_fail_n += 1
            if self._read_fail_n == 3:      # 连续读不到 → 打印一次, 但**不放弃**(保流程优先)
                print("  [读牌] 连续 3 次读不到手牌 → 退回提示驱动(牌局继续推进, 记牌器继续观测)",
                      flush=True)
            if getattr(self, "_last_hand", None):
                try:                              # 沿用上次成功读到的手牌(池子核算用), 决策仍走提示
                    self.log.set_my_hand(self._last_hand)
                except Exception:                 # noqa: BLE001
                    pass
            # 说明: 走到这里已经过了 my_turn + 手牌带结构 + 在局判据 3 道闸门, 是真牌局;
            # 读不到手牌就交给"提示驱动"(游戏自己挑合法牌) —— 比空转丢掉整局强。
            return Observation(frame=frame, my_turn=True, hand=None, extra={"read_fail": True})
        self._read_fail_n = 0
        table = P.read_table_last(self.vision, frame)
        cards = table or []
        self._observe_table(cards)               # 若与上面同帧重复 → 签名去重, 不重复计
        self._set_my_hand(hand)
        self._observe_table(cards)               # 记牌: 谁打了什么牌 → 事件日志 + 记牌器
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

    @staticmethod
    def _ranks_sig(cards):
        """牌的**点数**序列(排序) —— 去重签名用点数不用花色(VLM 花色会读错, 点数是稳的)。"""
        import re as _re

        out = []
        for c in cards:
            z = getattr(c, "zhi", None)
            if z is not None:
                out.append(int(z))
                continue
            t = str(c)
            if "王" in t:
                out.append(15 if "小" in t else 16)
                continue
            m = _re.search(r"(10|[2-9AJQK])", t.upper())
            tok = m.group(1) if m else "0"
            out.append({"A": 14, "J": 11, "Q": 12, "K": 13, "10": 10}.get(tok, int(tok) if tok.isdigit() else 0))
        return tuple(sorted(out))

    def _meter_vlm(self, what: str, ok: bool = True, **meta) -> None:
        """记一次视觉读牌算力(伴随包 → 底座计费)。"""
        try:
            self.usage.vlm_read(what=what, ok=bool(ok), **meta)
        except Exception:                            # noqa: BLE001
            pass

    def _log_plan(self, choice, why: str) -> None:
        """记一次决策(我们打算出的牌) → 操作准确率对账用。同时记下"决策前手牌张数"。"""
        try:
            hb = len(getattr(self, "_cur_hand", []) or [])
            self.log.plan("南", [str(c) for c in choice.cards], why=why, hand_before=hb or None)
        except Exception:                            # noqa: BLE001
            pass

    def _check_hand_delta(self, hand) -> None:
        """出牌后手牌张数校验: 掉了多少张 == 决策打多少张?

        这是"操作准确率"的**张数口径**(不依赖桌面读回):
        决定打 1 张、实际掉 3 张(游戏"自动带上同点数") → 立刻暴露 ✓
        """
        exp = getattr(self, "_expect_after", None)
        if exp is None or not hand:
            return
        try:
            self.log.verify("南", hand_after=len(hand), expected_after=exp)
        except Exception:                            # noqa: BLE001
            pass
        self._expect_after = None

    # ---------- 记牌(观测 → 事件日志 + 记牌器) ----------
    _SEAT_OF = {"right": "西", "top": "北", "left": "东"}     # 相对"我(南)"的座位

    def _log_seat_play(self, seat: str, cards, hand_left=None, src: str = "table") -> None:
        """记一次出牌: 写 GameLog + 更新 CardTracker。同一手重复看到只计一次。"""
        if not cards or not seat:
            return
        sig = self._ranks_sig(cards)             # 按**点数**做签名(花色读不稳, 点数稳)
        prev = self._last_sig.get(seat)
        if prev is not None:
            a, b = set(prev), set(sig)
            jac = len(a & b) / max(1, len(a | b))
            if jac >= 0.6 or (len(prev) == len(sig) and sorted(prev) == sorted(sig)):
                                                 # 近似同一手(花色读差) 或点数完全相同 → 不当新事件
                if len(sig) > len(prev):         # 这次读得更全 → 修正上一条
                    self._last_sig[seat] = sig
                    try:
                        self.log.amend_last_play(seat, [str(c) for c in cards])
                    except Exception:            # noqa: BLE001
                        pass
                return
        self._last_sig[seat] = sig
        self.log.play(seat, [str(c) for c in cards], hand_left, src=src)
        try:
            self.tracker.observe(seat, list(cards))
        except Exception as e:                   # noqa: BLE001
            print(f"  [记牌] tracker.observe 异常({type(e).__name__}: {e})", flush=True)

    def _table_changed(self, frame) -> bool:
        """桌面区是否变化(廉价像素闸门 → 决定是否花一次 VLM 读桌面)。"""
        try:
            import numpy as np
            h = frame.shape[0]
            band = frame[int(h * 0.28):int(h * 0.62), :, :]   # 出牌区(中上部)
            small = band[::8, ::8]
            prev = getattr(self, "_table_sig", None)
            self._table_sig = small
            if prev is None or prev.shape != small.shape:
                return True
            return float(np.mean(np.abs(small.astype("int16") - prev.astype("int16")))) > 3.0
        except Exception:                        # noqa: BLE001
            return True                          # 判断不了就老实读

    _SEAT_OF_BLOCK = {"right": "西", "top": "北", "left": "东", "bottom": "南"}

    def _observe_table_gated(self, frame) -> None:
        """每帧调用: 桌面有变化才读一次(控 VLM 成本), **逐座位**读牌块 → 记牌。

        为什么逐座位: 只读"最近一手"会漏掉其他家(而且我方出牌拿不到牌面 ✗)。
        逐块读 → 四家(含我方 bottom)的每一手都能进记牌器。
        """
        if not self._table_changed(frame):
            return
        try:
            blocks = P.table_plays(frame)
        except Exception:                        # noqa: BLE001
            blocks = []
        if not blocks:
            self._observe_table([])              # 桌面清空 → 一轮结束
            return
        seen = set()
        for name, box, _cnt in blocks:
            seat = self._SEAT_OF_BLOCK.get(name)
            if not seat:
                continue
            seen.add(seat)
            key = f"{seat}|{box}"
            if self._last_block.get(key) == box:  # 同块同位置 = 没变化
                continue
            self._last_block[key] = box
            try:
                cards = P.read_region_cards(self.vision, frame, box)
            except Exception:                    # noqa: BLE001
                cards = None
            self._meter_vlm("table", ok=bool(cards), seat=seat)
            if cards:
                self._log_seat_play(seat, cards)
        for k in list(self._last_block):
            if k.split("|")[0] not in seen:      # 该家的牌块消失了(清桌)
                self._last_block.pop(k, None)

    def _observe_table(self, cards) -> None:
        """每帧看桌面: 有牌 → 记一次; 桌面清空 → 一轮结束(签名清零, 允许同牌再计)。"""
        if not cards:
            self._last_sig.clear()
            return
        who = self._last_seat.get("who")
        seat = self._SEAT_OF.get(who or "", "")
        self._log_seat_play(seat, cards)

    def _set_my_hand(self, cards) -> None:
        """我方手牌 → 同时同步给 GameLog 与 CardTracker(两边不同步 → 池子对不上)。"""
        if not cards:
            return
        self._cur_hand = cards
        self._last_hand = cards                   # 记住最后一次成功读数(读失败时沿用)
        self._check_hand_delta(cards)             # 张数校验(决策后手牌应正好少 N 张)
        self.log.set_my_hand(cards)
        try:
            self.tracker.set_my_hand(list(cards))
        except Exception:                        # noqa: BLE001
            pass

    def _new_deal(self) -> None:
        """新一局: 记牌器/日志/RL 历史全部归零。"""
        self.log.deal_start()
        self.tracker.reset()
        self._last_sig.clear()
        self._rl_hist.clear()
        self._rl_played = [0.0, 0.0, 0.0, 0.0]
        print("  [记牌] 新一局 → 事件日志与记牌器已清零", flush=True)

    def board_state(self) -> dict:
        """给后台/决策用的当前牌局数据: 各家余牌 + 池子 + 守恒自检。"""
        try:
            self._set_my_hand(getattr(self, "_cur_hand", []) or [])
        except Exception:                        # noqa: BLE001
            pass
        return {"summary": self.log.summary(),
                "seat_remaining": self.log.seat_remaining(),
                "pool": self.log.pool(),
                "played": {s: dict(self.log.played[s]) for s in self.log.seats}}

    # ---------- 决策 ----------
    def decide(self, obs: Observation) -> Action:
        if obs.extra.get("read_fail") or not obs.hand:
            # 提示臂已禁用(2026-09-17): 读牌失败就**不动作**, 等下一帧重读 —— 绝不让游戏替我们打 ✗
            return Action("none", meta={"why": "读牌失败→等待重读(不用提示)"})
        cards = obs.table or []
        if cards:
            gl = R.identify(cards, JIPAI)
            if getattr(gl, "is_invalid", False):
                return Action("none", meta={"why": "待压牌非法→等待(不用提示)"})
        if not self.ours:
            # ours 未开 = 没启用我们自己的决策 → 不动作(提示臂已禁用, 不许偷偷退回 ✗)
            return Action("none", meta={"why": "ours 未开(提示臂已禁用)"})
        self.usage.decide(arm=("rl" if self.rl else "ours"), hand=len(obs.hand))
        st = AI.GameState()
        st.jipai = JIPAI
        st.shi_dui_you = self._last_seat.get("who") == "top"
        last = R.identify(cards, JIPAI) if cards else None
        if self.rl:
            return self._decide_rl(obs, last, cards)
        choice = AI.choose_play(obs.hand, last, st)
        if choice is None or getattr(choice, "is_invalid", False):
            return Action("pass", meta={"why": "引擎判不出"})
        return Action("play", combo=choice, meta={"why": "自研决策(direct)", "direct": True})

    def _decide_rl(self, obs: Observation, last, cards: list) -> Action:
        """RL 臂: 预训练权重在"我方全部合法出牌"里选 → 标记 direct(执行层点选直出)。"""
        who = self._last_seat.get("who")
        wi = {"right": 1, "top": 2, "left": 3}.get(who or "", 1)
        if len(obs.hand) >= 25 and self._rl_hist:    # 手牌回到满手且上局有记录 = 新一局
            self._new_deal()
        if last is not None and (not self._rl_hist or self._rl_hist[-1][1] is not last):
            self._rl_hist.append((wi, last))
        self._set_my_hand(obs.hand)                  # 我方手牌(精确) → 日志 + 记牌器
        if self._rl is None:
            from ...guandan.rl_policy import RLPolicy

            self._rl = RLPolicy()
            print(f"▶ RL 决策器已加载: {os.path.basename(self._rl.path)}", flush=True)
        cands = AI.zhao_ke_chu_de_pai(obs.hand, last, JIPAI)
        mine = float(len(obs.hand))
        rem = self.log.seat_remaining()              # 记牌器实测(他方 = 27 − 已出)
        others = [float(rem.get(s, 27)) for s in ("西", "北", "东")]
        self.usage.rl_infer(n_cand=len(cands), hand=len(obs.hand))
        choice, info = self._rl.choose(cands, obs.hand, self._rl_hist[-16:],
                                       [mine] + others + [mine + sum(others)], (wi, last), 0)
        print(f"  [rl] 手牌{len(obs.hand)} 候选{info['n_cand']}(可映射{info['mapped']}) → "
              f"{R.group_to_str(choice) if choice is not None else '不出'} | value={info['value']:.3f}",
              flush=True)
        if choice is None:
            return Action("pass", meta={"why": "RL判不出/不出"})
        self._rl_hist.append((0, choice))
        return Action("play", combo=choice, meta={"why": "RL决策", "direct": True, "planned": True})
        return Action("play", combo=choice, meta={"why": "RL决策", "direct": True})

    # ---------- 执行 ----------
    def execute(self, action: Action, obs: Observation) -> ExecResult:
        if self._ex is None:
            self._build_executor()
        ex = self._ex
        assert ex is not None
        if action.kind == "pass":
            ex.pass_turn()
            self._expect_after = None         # 不出 → 不做掉牌校验
            return ExecResult(True, 0, "不出")
        # RL 臂: 打的是我们自己选的牌 → 必须点选直出(提示只会出游戏自己选的牌)
        if action.meta.get("direct") and action.combo is not None and obs.hand:
            idxs = _map_indices(obs.hand, action.combo.cards)
            if idxs:
                ranks = [getattr(obs.hand[i], "zhi", None) for i in idxs
                         if 0 <= i < len(obs.hand)]
                if ex.direct_play(idxs, len(obs.hand), ranks=ranks):
                    self._log_plan(action.combo, action.meta.get("why", ""))   # 打出去了才记决策
                    self._log_seat_play("南", action.combo.cards,
                                        hand_left=max(0, len(obs.hand) - len(action.combo.cards)),
                                        src="own")
                    # 出牌**成功后**才设期望(按我们意图的张数) → 下次读手牌做校验
                    self._expect_after = max(0, len(obs.hand) - len(action.combo.cards))
                    return ExecResult(True, 0, "直选出牌(RL)")
                why = ""
                if getattr(ex, "cdp", None) is not None:
                    try:
                        why = ex.cdp.toast()
                    except Exception:  # noqa: BLE001
                        why = ""
                if why:
                    print(f"  [真值] 出牌被游戏拒绝: {why}", flush=True)
                rpt = getattr(ex, "last_report", None)
                if rpt is not None and (rpt.not_our_turn or rpt.skipped):
                    # 执行器规范: 识别/活性不满足 ⇒ 跳过, 不是失败(不计入失败率)
                    return ExecResult(True, 0, f"跳过 · {rpt.reason}", skipped=True)
                return ExecResult(False, 1, f"直选失败(RL){' · ' + why if why else ''}")
        # ★ 提示臂已禁用(2026-09-17 用户拍板): "点提示=游戏帮我们挑牌", 那不是我们的 AI ✗
        #   → 出牌只走**直选**(我们自己决定哪几张 → 点那几张), 失败就报失败, 绝不退化到提示 ✓
        if action.kind == "none":
            return ExecResult(True, 0, "本帧不动作(等待重读)", skipped=True)
        if action.combo is not None and obs.hand:
            idxs = _map_indices(obs.hand, action.combo.cards)
            if idxs:
                ranks = [getattr(obs.hand[i], "zhi", None) for i in idxs if 0 <= i < len(obs.hand)]
                if ex.direct_play(idxs, len(obs.hand), ranks=ranks):
                    self._log_plan(action.combo, action.meta.get("why", ""))
                    self._log_seat_play("南", action.combo.cards,
                                        hand_left=max(0, len(obs.hand) - len(action.combo.cards)),
                                        src="own")
                    self._expect_after = max(0, len(obs.hand) - len(action.combo.cards))
                    return ExecResult(True, 0, "直选出牌")
            return ExecResult(False, 1, "直选失败(未出牌)")
        return ExecResult(False, 1, "无组合可打(未出牌)")


    # ---------- 结算 ----------
    def settle(self, frame) -> SettleInfo | None:
        """结算解读: 优先无障碍文字(免 VLM), 否则回落 VLM 读弹窗。

        ⚠️ 防假结算(2026-09-17 实测): a11y 文本会**残留**上一次的"头游" →
        同一局被反复判成"结算"(10 分钟误记 11 局 ✗, 真局要几分钟) → 去重 + 冷却 ✓
        """
        try:
            blob = self.a11y.text_blob(force=True)
        except Exception:  # noqa: BLE001
            blob = ""
        _key = (blob or "").strip()[:200]
        _now = time.time()
        if _key and _key == getattr(self, "_last_settle_key", None):
            return None                       # 同一段文字 = 残留, 不是新结算 ✓
        if _now - getattr(self, "_last_settle_t", 0.0) < 60.0:
            return None                       # 冷却: 一局至少几分钟, 1 分钟内不可能结算两次 ✓
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
            try:
                self.log.deal_end(raw=raw, win=win)
            except Exception:                    # noqa: BLE001
                pass
            self._last_settle_key = _key         # 记住这次文本 + 时间 → 防止残留被反复计数 ✓
            self._last_settle_t = _now
            return SettleInfo(raw=raw, win=win)
        if self.vision is None:
            return None
        txt, win = P.read_settle(self.vision, frame)
        if "头游" not in txt and "升级" not in txt:
            return None
        return SettleInfo(raw=txt.strip()[:60], win=win)


def _map_indices(hand, cards):
    """把组合中的牌映射回手牌索引(用于直选)。"""
    from ...guandan.agent import map_indices

    try:
        return map_indices(hand, cards)
    except Exception:  # noqa: BLE001
        return None


"""掼蛋(开源 Web 版)适配器: 把既有 percept/ai 接进平台通用接口。

过渡期说明: 复用 ../guandan 下已标定的几何常量与工具, 后续逐步下沉到 platform。
"""
from __future__ import annotations

import json
import os
import re
import time

from ..types import Action, ExecResult, GameAdapter, Observation, SettleInfo
from .. import mode                      # ★ 真值/产品 模式开关(用户 2026-09-18 拍板解耦 ✓)
from ..game_log import GameLog
from ..usage import UsageMeter
from ...guandan.tracker import CardTracker

# 复用已标定常量(见 docs/M4_掼蛋几何参考.md)
from ...guandan import ai as AI
from ...guandan import percept as P
from ...guandan import rules as R
from ...guandan.agent import BTN_HINT, BTN_PASS, BTN_PLAY, JIPAI, gold_button

# 读牌帧留证目录(读牌与"块宽真值"分歧时存帧, 供离线判定谁对)
READ_DUMP_DIR = os.getenv("GUANDAN_READ_DUMP_DIR", "/tmp/guandan_read_dumps")
DUMP_MAX = int(os.getenv("GUANDAN_READ_DUMP_MAX", "20"))     # 单次运行最多存几帧
DUMP_GAP = float(os.getenv("GUANDAN_READ_DUMP_GAP", "15"))   # 两帧最小间隔(秒)


class GuandanAdapter(GameAdapter):
    name = "guandan"
    package = "org.bromite.bromite"   # 游戏跑在 Bromite 里(前台闸门用) ✓
    #   ⚠️ 本机实测: Firefox Focus 会抢前台 ⇒ 不判前台就会对着别的界面读牌/结算 ✗
    #      (2026-09-17: 浏览器欢迎页被当成结算弹窗 ⇒ 假局假结算的总源头 ✓)
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
        # ★ 伴随应用 M1 (2026-09-19): 给事件流挂上"旁观者" —— 牌局事件自动进本地库 ✓
        #   · 只收不发(bridge 只搬字段 ✗ 不算牌); 出事绝不影响牌局(GameLog.append 里兜住 ✓)
        #   · 任何环节出问题都只是"不记录", 打牌照常 ✓
        try:
            from landlord_counter.companion.bridge import make_sink
            from landlord_counter.companion.store import CompanionStore
            self._companion = CompanionStore()
            self.log.sink = make_sink(self.log, self._companion, self.log.game_id)
            print(f"  [companion] ✓ 伴随应用已挂上(库: {self._companion.path})", flush=True)
        except Exception as e:                       # noqa: BLE001
            self._companion = None
            print(f"  [companion] ⚠ 伴随应用未启用({type(e).__name__}: {e}) → 只打牌不记录 ✓",
                  flush=True)
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

    def attach(self, device, vision=None) -> None:
        super().attach(device, vision)
        self._build_executor()

    def _build_executor(self) -> None:
        from ..a11y import A11y
        from ..gestures import Executor, GestureLayout

        self.a11y = A11y(getattr(self.device, "serial", "127.0.0.1:5555"))

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
        # ★ 2026-09-17 修: 原来只在 GUANDAN_USE_CDP=1 时才挂 ⇒ 试跑没设它 ⇒
        #   **真值通道(自动采模板/读 toast 判决)整个没工作** ✗, 症状是"自动采集不触发、判决读不到"
        #   ⇒ 改成**总是尝试挂上**(实验室里这是我们的"裁判"; 拿不到就响亮说明并继续, 不静默 ✗)
        try:
            from ..cdp import CDP

            self._ex.cdp = CDP(url_filter="8123")
            print("▶ 真值/按钮通道: CDP 已挂上 ✓", flush=True)
        except Exception as e:  # noqa: BLE001
            self._ex.cdp = None
            print(f"⚠ CDP 不可用({e}) → 无真值通道(换局不自动采模板, 按钮走实测像素定位 ✓)", flush=True)

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

    def _hand_for_map(self, obs):
        """**决定"哪张牌是第几个位"用的手牌顺序**(2026-09-18 实测踩坑后定案)。

        坑: 旧实现用 `obs.hand`(读牌结果 ✗, 实测只有 ~70% 准) 去算位置 ⇒
          **打出去的牌 ≠ 决策的牌**(实测: 想打 ♥5, 真值记录里出的是 J ✗),
          而"位置级核对"还会给假 OK ✗(位置对上了, 但那张牌不是要打的牌)
        ⇒ 真值模式用**游戏真值的手牌顺序**(`hands['0']` 就是屏幕顺序 ✓, 与 handIds 同序) ✓
          产品模式仍用读牌结果(那是产品路径的唯一来源 ✓)
        """
        if mode.TRUTH:
            t = self._truth_now()
            # ★★ 2026-09-21 关键修复: **必须带 hua 和 id** ✗
            #   旧写法只取点数 `R.Card(zhi=int(v))` ⇒ map_indices 只能按**点数**匹配
            #   ⇒ 同点数的牌会混(想选 ♥4 却点到 ♠4 ✗)
            #   实测: 想选 [Q,Q,Q,♥4,♥4] 点成 [Q,Q,Q,♥4,♠4] ⇒ 游戏判"无效的牌型组合" ✗
            hf = (t.get("handsFull") or {}).get("0") or []
            if hf:
                return [R.Card(zhi=int(c["zhi"]), hua=int(c["hua"]),
                               id=int(c.get("id", -1))) for c in hf]
            hh = (t.get("hands") or {}).get("0") or []
            if hh:
                return [R.Card(zhi=int(v)) for v in hh]
        return obs.hand

    def _truth_now(self) -> dict:
        """读一次游戏真值(拿不到就空 dict ✓)"""
        cdp = getattr(getattr(self, "_ex", None), "cdp", None)
        if cdp is None:
            return {}
        try:
            return cdp.truth() or {}
        except Exception:  # noqa: BLE001
            return {}

    def _verify_identity(self, combo, why: str = "") -> None:
        """**即时对账**(2026-09-18 用户第一步): 出完一手, 立刻问游戏"你刚记的是哪几张",
        当场与我们的决策逐张比对 ⇒ **每一手都是铁证** ✓

        为什么必须"即时": 真值 `plays` 是**累积**的 ⇒ 事后按时间/序号配对容易错位 ✗
          (今天就被它坑过一次: 报告里三次都显示"出 J" ✗)
        判据: **点数 + 花色** 多重集一致(能分清 ♣J vs ♥J ✓); 拿不到花色就只比点数 ✓
        """
        if not mode.TRUTH:
            return
        cdp = getattr(getattr(self, "_ex", None), "cdp", None)
        if cdp is None:
            return
        cards = list(combo.cards) if combo is not None else []
        want_z = sorted(int(getattr(c, "zhi", 0)) for c in cards)
        want_h = sorted(int(getattr(c, "hua", 0) or 0) for c in cards)
        for _ in range(6):
            try:
                plays = (cdp.truth() or {}).get("plays") or []
            except Exception:  # noqa: BLE001
                return
            # ★ 不能只看最后一条(2026-09-18: 我们出完 2 秒内别人就接上了 ✗) ⇒
            #   往前找**最近的、座位 0 的、且 20 秒内**的那一条 = 刚打出的那一手 ✓
            last = None
            for p in reversed(plays):
                if int(p.get("seat", -1)) == 0:
                    if time.time() * 1000 - int(p.get("t") or 0) < 20000:
                        last = p
                    break
            if last is not None:
                z = sorted(int(v) for v in (last.get("zhi") or []))
                h = sorted(int(v) for v in (last.get("hua") or []))
                ok = (z == want_z) and (not h or h == want_h)
                extra = "" if ok or not h else f" 花色 期望{want_h} 实际{h}"
                print(f"  [对账] {'✓ 一致' if ok else '✗ 不一致!!'} "
                      f"决策={R.group_to_str(combo) if combo is not None else '-'} "
                      f"实出={' '.join(str(v) for v in z)}{extra}", flush=True)
                # ★ 2026-09-20 用户定: **对账结果直接进账** ✓ 这是唯一权威口径
                #   (旧口径"手牌掉几张"是间接推断, 读数一滞后就误判 ✗ 已删)
                try:
                    self.log.append("identity", ok=bool(ok), n=len(z),
                                    want_z=want_z, got_z=z, want_h=want_h, got_h=h)
                except Exception:            # noqa: BLE001
                    pass
                return
            time.sleep(0.4)
        print("  [对账] ? 真值里没看到这一手(还没写入?)", flush=True)

    _SEATS_TRUTH = ("南", "西", "北", "东")      # 真值座位序号 → 座位名(与 GameLog.seats 同序 ✓)

    def _observe_others_by_truth(self, t: dict) -> None:
        """真值模式: 从真值 `plays` 读**别人**出的牌 ✓

        用户 2026-09-20 定: "反正都已经用真值了, 索性就全用" ✓
        为什么需要它: 真值模式把整段视觉跳过了 ✗ ⇒ 原来"看桌面记别人牌"的路径也断了
          (实测库里只有我自己的 22 手, 别人一张没记 ✗ —— 一个意外的耦合)
        `plays` 每条自带 seat/zhi/hua/t ⇒ 取"新出现的"做差量即可 ✓
        """
        seen = getattr(self, "_truth_plays_seen", None)
        if seen is None:
            seen = self._truth_plays_seen = set()
        for p in (t.get("plays") or []):
            zhi = tuple(int(v) for v in (p.get("zhi") or []))
            hua = tuple(int(v) for v in (p.get("hua") or []))
            si = int(p.get("seat", -1))
            key = (si, int(p.get("t") or 0), zhi, hua)
            if key in seen:
                continue
            seen.add(key)
            if si <= 0 or not zhi:
                continue      # 0=我(另有路径: 带手牌+即时对账 ✓); 空牌=不出 ✓
            seat = self._SEATS_TRUTH[si] if si < len(self._SEATS_TRUTH) else f"座{si}"
            cards = [R.Card(zhi=z, hua=h) for z, h in
                     zip(zhi, hua or (0,) * len(zhi))]
            self._log_seat_play(seat, cards, src="truth")

    def _sense_by_truth(self, frame):
        """**纯真值观测**(2026-09-18 用户拍板: "如果真值就直接全部都用真值, 视觉去掉") ✓

        为什么要把视觉整段拿掉: 旧真值模式是"视觉为主 + 真值兜漏" ✗ —— 手牌还是视觉读的
          (~70% 准 ✗) ⇒ RL 可能拿错手牌做决策 ✗; 桌面视觉为空 ⇒ 靠真值兜 ✓ ……
          **每漏一处补一处, 永远在追漏** ✗
        现在: 手牌 / 轮到谁 / 是不是我 / 待压牌 **全部来自 `__truth()`** ✓(带花色 ✓),
          一行视觉都不用 ✓; 一次读取, 内部自洽 ✓
        拿不到真值 ⇒ 返回 None, 让调用方**响亮退回视觉**(绝不静默降级 ✗)
        """
        t = self._truth_now()
        if not t or t.get("err") or t.get("phase") is None:
            return None
        # ★ 2026-09-20: **先**记别人出的牌 —— 必须在下面"别人回合早退"之前 ✗
        #   (原来早退了, 别人那几手连读的机会都没有 ⇒ 库里只有自己的牌 ✗)
        self._observe_others_by_truth(t)
        phase = t.get("phase")
        if phase != "playing":                      # 结算/等待: 不动作, 交给 settle ✓
            return Observation(frame=frame, my_turn=False, extra={"truth_phase": phase})
        if int(t.get("current", -1)) != 0:           # 别人回合: 只看不动 ✓
            return Observation(frame=frame, my_turn=False)
        hf = (t.get("handsFull") or {}).get("0") or []
        if not hf:
            return Observation(frame=frame, my_turn=False)
        # ★★ 2026-09-20 关键修复: **必须带 id** ✗
        #   Card 的 id 默认 -1 ⇒ 三张 A 全变同一张 ⇒ find_all_plays 去重后只剩 1 个候选 ✗
        #   (实测: 手牌 3 张 A ⇒ 候选只 1 个; 真值里每张牌本来就有唯一 id, 是我们丢了 ✗)
        #   后果极严重: 决策器面前永远只有单张 ⇒ "只会出单张" / "领出却候选0" 全是这个根 ✓
        hand = [R.Card(zhi=int(c["zhi"]), hua=int(c["hua"]),
                       id=int(c.get("id", -1))) for c in hf]
        # ★★ 职责分工(2026-09-19 用户定, 避免"一个字段兼职两件事"):
        #   · "该不该压 / 能不能任意出" ⇒ **只看 needBeat**(一个布尔, 零歧义 ✓)
        #   · benLunChuPai(本轮各家出了什么) ⇒ **专门给记牌器用**, 不参与判断 ✓
        #   (教训: 之前 shangJiaPaiXing 兼职 ⇒ 它 null 时被误读成"没人压着" ⇒ 候选给 10 张 ✗)
        # ★★ 2026-09-20: **本局级牌以真值为准** ✓
        #   原来写死 JIPAI(环境变量默认 2) ✗ ⇒ 打A局时"逢人配/同花顺"判断全错 ✗
        #   实测: 真值 jiPai=14(A), 而 Python 里是 2 ⇒ 候选数都不一样(5 vs 6) ✗
        # ★★ 2026-09-21: 级牌以**游戏引擎真正用的那个**(jiPaiModule)为准 ✓
        #   实测两者会走岔: 真值 gameState.jiPai=2, 而 gameRules 模块内是 3 ✗
        #   而游戏判牌型用的是模块内那个 ⇒ 我们必须跟它一致, 否则算出"游戏不认"的牌型 ✗
        self._jipai_now = int(t.get("jiPaiModule") or t.get("jiPai") or 0) or None
        # ★★ 2026-09-21: "**过A通关**"是一瞬间的事(级牌 A→2) ⇒ 见到就**立刻落库** ✓
        #   实测教训: 大循环明明闭环了(级牌 14→2 ✓), 库里 matchOver 却是 0 条 ✗
        #   —— 因为我们是"等结算"才记账, 而那一局往往没等到结算就跑完了 ✓
        _mo = (t.get("result") or {}).get("matchOver")
        if _mo and getattr(self, "_mo_logged", None) != _mo:
            self._mo_logged = _mo
            try:
                self.log.append("match_over", data=_mo,
                                match_games=(t.get("result") or {}).get("matchGames"),
                                ji_pai=self._jipai_now)
            except Exception:                # noqa: BLE001
                pass
            print(f"  ★★ 过A通关(真值) → 已当场落库 ✓ {_mo}", flush=True)
        need_beat = bool(t.get("needBeat"))
        sj = t.get("shangJia") or [] if need_beat else []
        table = [R.Card(zhi=int(c["zhi"]), hua=int(c["hua"]),
                        id=int(c.get("id", -1))) for c in sj]
        self._set_my_hand(hand)                     # 喂日志/记牌器(它们要"我手里有什么" ✓)
        if table:
            self._observe_table(table)              # 记牌: 我该压的那一手 ✓
        # 本轮各家已出的牌 ⇒ 交给记牌器(不参与"该不该压"的判断 ✓)
        bl = t.get("benLunChuPai") or {}
        return Observation(frame=frame, my_turn=True, hand=hand, table=table,
                           extra={"truth": True, "need_beat": need_beat,
                                  "pass_count": int(t.get("passCount") or 0),
                                  "round_plays": bl})

    def sense(self, frame) -> Observation:
        if mode.TRUTH:                     # ★ 真值模式: **纯真值观测**, 视觉整段跳过 ✓
            _obs = self._sense_by_truth(frame)
            if _obs is not None:
                return _obs
            # ★ 用户 2026-09-19 定: 真值模式**不用视觉兜底** ✓
            #   理由: 视觉读牌只有 ~70% ✗, 兜进去只会把脏数据带进决策
            #   ⇒ 读不到就**这帧什么都不做**(CDP 已带自动重连 ✓, 下一帧大概率就好了 ✓)
            print("  [truth] ⚠ 真值读不到 → **跳过本帧**(真值模式不走视觉兜底 ✓)", flush=True)
            return Observation(frame=frame, my_turn=False, extra={"truth_miss": True})
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
            # ★ 滑动版读牌(2026-09-17): 与"量抬起"同一个匹配 → **有牌被抬起时也 100%** ✓
            #   (旧版用固定裁切, 有牌抬起时会掉到 24/27 ✗)
            _cards, _linfo = P.tm_read_hand(frame)
            _tm_first = [(s_, r_, x_) for s_, r_, x_, _l in _cards]
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
            if now - getattr(self, "_turn_checked_at", 0.0) >= 2.0:
                self._turn_checked_at = now
                # ★★ 正解(2026-09-17 实测): **真值能直接回答"该谁出牌"** ⇒ 直接问它 ✓
                #   旧法用"点一下出牌, 看游戏说不说『请选择要出的牌』" ⇒ 牌桌有残留选中时,
                #   游戏回的是『无效的牌型组合』⇒ 探针认不出 ⇒ **误判"不是我的回合"** ✗
                #   ⇒ 整帧跳过、读牌 0(实测踩到 ✓)。探针降级为"没有真值通道时的兜底" ✓
                _cur = None
                try:
                    _cur = (ex.cdp.truth() or {}).get("current")
                except Exception:  # noqa: BLE001
                    _cur = None
                if _cur is not None:
                    if _cur != 0:
                        print(f"    [真值] 轮到 {_cur}(不是我) → 跳过本帧", flush=True)
                        return Observation(frame=frame, my_turn=False)
                else:
                    try:
                        ok, why = ex.cdp.our_turn_probe(ex.L.btn_play)
                        if not ok:
                            print(f"    [真值] {why} → 跳过本帧", flush=True)
                            return Observation(frame=frame, my_turn=False)
                    except Exception:  # noqa: BLE001
                        pass
        # 期望张数: **模板读到的张数是权威**(实测真值 9 而老估算器给 12~15 ✗)
        # 教训(2026-09-16): 老 hand_card_count_est 过期 → 一致性闸门误判"离谱" → 判定不敢用 ✗
        n_vis = (len(_tm_first) if _tm_first
                 else (P.hand_card_count_est(frame) or P.hand_columns(frame)))
        # ★ 2026-09-21 清: "点选自标定"的残留代码已全部删除 ✗
        #   (它靠**试点牌**推点位/张数 ⇒ 会留下残留选中: 实测一跑起来就有 3137 抬起 ✗)
        #   现在点位一律走实测(locate/card_slots ✓), 老标定不许回来 ✓
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
            # ★ 兼容 3/4 元组(2026-09-19): 旧写法写死 `for s, z, _x, _l in tm_reads` ✗
            #   ⇒ 读法统一后元组变成 3 个 ⇒ **未定义解包 ⇒ 整个 sense 崩** ✗
            #   (实测: 真值掉线、首次走到视觉兜底时才发现 —— 兜底路径从没被跑过 ✓)
            #   只取**前两位**(花色/点数), 后面几位是什么都不影响 ✓
            hand = [R.Card(zhi=it[1], hua=_TM_HUA2RULES.get(it[0])) for it in tm_reads]
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
            # ★ 2026-09-20: 原来取 _cur_hand, 实测会滞后(记成 16 张、实际 9 张 ⇒ 假警报 ✗)
            #   真值在决策时的 obs.hand 里, 由 _decide_rl 存进 self._hand_n ✓
            hb = int(getattr(self, "_decision_hand_n", 0) or 0) or len(getattr(self, "_cur_hand", []) or [])
            self.log.plan("南", [str(c) for c in choice.cards], why=why, hand_before=hb or None,
                          need_beat=bool(getattr(self, "_last_need_beat", False)),
                          cand_n=int(getattr(self, "_last_n_cand", 0) or 0))
        except Exception:                            # noqa: BLE001
            pass

    # (2026-09-20 整段删除) `_check_hand_delta` —— 旧的"手牌掉几张"口径 ✗
    #   它是**间接推断**: 用"手牌数掉了几张"去倒推这手对不对, 读数一滞后就误判
    #   ⇒ 假警报(实测两次误报"决定≠实出", 一查牌其实一模一样 ✓)
    #   已被 `_verify_identity`(决定的牌 vs 真值实出牌, 逐张比点数+花色)取代 ✓
    #   用户 2026-09-20: "老的看看能不能删了, 不要留在代码里影响后面的判断" ✓

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
        self.log.set_my_hand(cards)
        # ★ 2026-09-21 用户要观察"红桃级牌(逢人配)": 每局第一次拿到手牌时报一次
        #   (**只打印**, 不改决策、不碰规则 ✓)
        if not getattr(self, "_wild_said", False):
            self._wild_said = True
            _jp = self._jp()
            _w = [c for c in cards
                  if getattr(c, "hua", -1) == 1 and getattr(c, "zhi", 0) == _jp]
            if _w:
                print(f"  ★ 本局手里有红桃级牌(逢人配) × {len(_w)} 张 (级牌={_jp}) ✓", flush=True)
            else:
                print(f"  ☆ 本局手里没有红桃级牌 (级牌={_jp})", flush=True)
        try:
            self.tracker.set_my_hand(list(cards))
        except Exception:                        # noqa: BLE001
            pass

    def _new_deal(self) -> None:
        """新一局: 记牌器/日志/RL 历史全部归零。"""
        # ★ 2026-09-21: 变量名写错(原来读 `_ji_pai`, 实际存的是 `_jipai_now`)
        #   ⇒ 桥那边一直在收 ji_pai, 但每次都是 None ⇒ 库里"这局打几"一直空 ✗
        self.log.deal_start(ji_pai=getattr(self, "_jipai_now", None))
        self._wild_said = False          # ★ 本局"红桃级牌"提示还没报过 ✓
        self.tracker.reset()
        self._last_sig.clear()
        self._rl_hist.clear()
        self._rl_played = [0.0, 0.0, 0.0, 0.0]
        print("  [记牌] 新一局 → 事件日志与记牌器已清零", flush=True)

    # ---------- 决策 ----------
    def decide(self, obs: Observation) -> Action:
        if not getattr(self, "_mode_logged", False):     # ★ 启动就亮明模式(演示/产品 ✓)
            self._mode_logged = True
            print("  " + mode.describe(), flush=True)
        if obs.extra.get("read_fail") or not obs.hand:
            # 提示臂已禁用(2026-09-17): 读牌失败就**不动作**, 等下一帧重读 —— 绝不让游戏替我们打 ✗
            return Action("none", meta={"why": "读牌失败→等待重读(不用提示)"})
        cards = obs.table or []
        if cards:
            gl = R.identify(cards, self._jp())
            if getattr(gl, "is_invalid", False):
                return Action("none", meta={"why": "待压牌非法→等待(不用提示)"})
        if not self.ours:
            # ours 未开 = 没启用我们自己的决策 → 不动作(提示臂已禁用, 不许偷偷退回 ✗)
            return Action("none", meta={"why": "ours 未开(提示臂已禁用)"})
        self.usage.decide(arm=("rl" if self.rl else "ours"), hand=len(obs.hand))
        st = AI.GameState()
        st.jipai = self._jp()
        st.shi_dui_you = self._last_seat.get("who") == "top"
        last = R.identify(cards, self._jp()) if cards else None
        if self.rl:
            return self._decide_rl(obs, last, cards)
        choice = AI.choose_play(obs.hand, last, st)
        if choice is None or getattr(choice, "is_invalid", False):
            # ★★ 2026-09-20 用户指出: **领出时不能不出** ✓(掼蛋规则)
            #   领出(need_beat=False)却 pass ⇒ 违规 ⇒ 局永远打不完(实测卡死 ✗)
            #   ⇒ 领出时一律兜底: 从候选里挑一手最小的(绝不允许 pass ✗)
            if not bool((obs.extra or {}).get("need_beat")):
                # 现算候选(此处作用域没有 cands ✓) —— 领出时总得出一手
                _fb = AI.zhao_ke_chu_de_pai(obs.hand, last, self._jp())
                if _fb:
                    choice = min(_fb, key=lambda g: (g.xing, g.chang_du, g.zhu_zhi))
            if choice is None or getattr(choice, "is_invalid", False):
                return Action("pass", meta={"why": "引擎判不出"})
        return Action("play", combo=choice, meta={"why": "自研决策(direct)", "direct": True})

    def _jp(self) -> int:
        """本局级牌 —— **以真值为准** ✓(2026-09-20)

        为什么必须同步: 级牌是"逢人配"(红桃级牌当万能)和"同花顺"的依据 ✓
        真值每局都给 jiPai; 拿不到(视觉模式)才退回环境变量 GUANDAN_JIPAI(默认 2) ✓
        """
        return int(getattr(self, "_jipai_now", None) or JIPAI)

    def _decide_rl(self, obs: Observation, last, cards: list) -> Action:
        """RL 臂: 预训练权重在"我方全部合法出牌"里选 → 标记 direct(执行层点选直出)。"""
        who = self._last_seat.get("who")
        wi = {"right": 1, "top": 2, "left": 3}.get(who or "", 1)
        # ★★ 新一局的判据必须是"**从少变多**"(2026-09-17 用户指令: 别留着反复影响 ✗)
        #   旧写法 `len(hand) >= 25 and self._rl_hist` ⇒ 满手 27 一直满足、历史又不断被写满
        #   ⇒ **几乎每帧都判"新一局"** ✗ ⇒ 日志/记牌器/统计反复清零 ⇒ 假局、假结算、假统计 ✓
        #   正解: 上一帧看到的手牌 **< 25**(打过的样子) 且这一帧回到 >= 25 ⇒ 才是新一局 ✓
        #   注意 `_last_hand_n` 只在**读到牌**时更新, 且读到少牌时不立刻清零(要等回升) ✓
        _n_now = len(obs.hand)
        _prev_n = getattr(self, "_last_hand_n", None)
        if _prev_n is not None and _prev_n < 25 and _n_now >= 25:
            self._new_deal()
        self._last_hand_n = _n_now
        if last is not None and (not self._rl_hist or self._rl_hist[-1][1] is not last):
            self._rl_hist.append((wi, last))
        self._set_my_hand(obs.hand)                  # 我方手牌(精确) → 日志 + 记牌器
        if self._rl is None:
            from ...guandan.rl_policy import RLPolicy

            self._rl = RLPolicy()
            print(f"▶ RL 决策器已加载: {os.path.basename(self._rl.path)}", flush=True)
        # ★★ 删掉"从出牌历史兜底 last"(2026-09-18):
        #   历史 `plays` 里**不记录"不出"** ⇒ 分不清"别人压着"和"四家都过、已开新一轮" ✗
        #   ⇒ 拿它当 last ⇒ 新一轮还在"必须压上一轮的旧牌" ⇒ 候选 0 ⇒ **一直不出**(实测死循环 16 次 ✗)
        #   正确来源 = 游戏自己的待压状态 `shangJia`(开新一轮时游戏会把它清空 ✓),
        #   它已经通过 `_sense_by_truth` 进了 `obs.table` ⇒ 这里**不需要任何兜底** ✓
        cands = AI.zhao_ke_chu_de_pai(obs.hand, last, self._jp())
        mine = float(len(obs.hand))
        rem = self.log.seat_remaining()              # 记牌器实测(他方 = 27 − 已出)
        others = [float(rem.get(s, 27)) for s in ("西", "北", "东")]
        self.usage.rl_infer(n_cand=len(cands), hand=len(obs.hand))
        # ★ 2026-09-20 补口子②: 决策当时的处境(候选数 + 压/领出) ⇒ 写进日志/伴随应用库
        self._last_n_cand = len(cands)
        # ★ 本轮真实手牌张数(供 _log_plan 记账 ✓) —— 名字别跟防抖用的 _last_hand_n 混 ✓
        self._decision_hand_n = len(obs.hand)
        self._last_need_beat = bool((obs.extra or {}).get("need_beat"))
        choice, info = self._rl.choose(cands, obs.hand, self._rl_hist[-16:],
                                       [mine] + others + [mine + sum(others)], (wi, last), 0)
        # ★★ 2026-09-21: RL 把选中的组**重新造了一遍** ⇒ 牌的 id 丢了(实测 id=[-1,-1] ✗)
        #   ⇒ 选牌时按 id 定位就找不到 ⇒ 卡住(用户看到"不断点1010又放下1010") ✓
        #   修: 按"点数+花色"在候选表里找回**原对象**(带 id ✓)
        if choice is not None and cands:
            _k = sorted((c.zhi, c.hua) for c in choice.cards)
            _orig = next((g for g in cands
                          if sorted((c.zhi, c.hua) for c in g.cards) == _k), None)
            if _orig is not None:
                choice = _orig
            else:
                print(f"  [注意] RL 选的 {R.group_to_str(choice)} 不在候选表里 ⇒ 按不出处理",
                      flush=True)
                choice = None
        # ★★ 2026-09-21 用户指出"为压一对K, 炸掉5张(含万能)": RL 会瞎炸 ✗
        #   掼蛋常识: 该压时若"**不用炸弹、不用万能**"就能压过 ⇒ 不许动它们 ✓
        #   (RL 的 value 分不出这种代价 —— 记忆里的"96% 挤在 ±0.05" ✗ —— 只能靠规则拦 ✓)
        if (choice is not None and cands
                and bool((obs.extra or {}).get("need_beat"))):
            _BOMB = (R.PAI_XING["ZHA_DAN"], R.PAI_XING["TONG_HUA_SHUN"],
                     R.PAI_XING["TIAN_WANG_ZHA"])
            _expensive = choice.xing in _BOMB or getattr(choice, "wild_used", 0) > 0
            _cheap = [g for g in cands
                      if g.xing not in _BOMB and not getattr(g, "wild_used", 0)]
            if _expensive and _cheap:
                _alt = min(_cheap, key=lambda g: (g.chang_du, g.zhu_zhi))
                print(f"  [代价] RL 想 {R.group_to_str(choice)}(炸弹/用万能 ✗)"
                      f" → 改用 {R.group_to_str(_alt)}(不用炸弹/万能也能压 ✓)", flush=True)
                choice = _alt
        # ★★ 2026-09-21 用户开工②: 代价过滤**扩展到领出** ✓
        #   实测: 领出时它拿**万能牌**去凑"对子5"这种小牌 ✗ (太浪费 —— 万能牌是宝贝 ✓)
        #   规则: 领出且这手用了万能 ⇒ 候选里若有"**同牌型、不用万能**"的, 换最省的那手 ✓
        #   边界(保守 ✓):
        #     · 只换"同牌型" —— 领出随便出什么, 换牌型等于改策略 ✗ (不动 ✓)
        #     · 只管"用万能" —— 领出打炸弹有时是战术(抢主动权), 不拦 ✓
        if (choice is not None and cands
                and not bool((obs.extra or {}).get("need_beat"))
                and getattr(choice, "wild_used", 0) > 0):
            _same = [g for g in cands
                     if g.xing == choice.xing and getattr(g, "wild_used", 0) == 0]
            if _same:
                _alt = min(_same, key=lambda g: (g.chang_du, g.zhu_zhi))
                print(f"  [代价·领出] RL 想 {R.group_to_str(choice)}(用了万能 ✗)"
                      f" → 改用 {R.group_to_str(_alt)}(同牌型、不用万能 ✓)", flush=True)
                choice = _alt
        _md = "压" if (obs.extra or {}).get("need_beat") else "领出"
        # ★ 2026-09-21 诊断: 打出"桌上那手 + 用的级牌 + 我们选的点数"
        #   目的: 出现"牌太小，压不过"时, 一眼看出是"读错桌上牌"还是"算错大小" ✓
        _tbl = (f"{R.group_to_str(last)}(zhi={last.zhu_zhi})" if last is not None else "无(我领出)")
        _me = (f"{R.group_to_str(choice)}(zhi={[c.zhi for c in choice.cards]})"
               if choice is not None else "不出")
        print(f"  [rl] 手牌{len(obs.hand)} [{_md}] 候选{info['n_cand']}(可映射{info['mapped']}) → "
              f"{_me} | value={info['value']:.3f}"
              f" | 桌上={_tbl} 级牌={self._jp()}",
              flush=True)
        if choice is None:
            # ★★ 同上: 领出不能不出 ⇒ 兜底挑一手 ✓
            if not bool((obs.extra or {}).get("need_beat")) and cands:
                choice = min(cands, key=lambda g: (g.xing, g.chang_du, g.zhu_zhi))
                print(f"  [rl] ⚠ 领出兜底(原判不出) → {R.group_to_str(choice)}", flush=True)
            else:
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
            # ★★ 2026-09-20: **领出时拒绝 pass** ✓(违规动作; 宁可响亮报错也不静默卡死 ✗)
            if not bool(((obs.extra if obs is not None else None) or {}).get("need_beat")):
                return ExecResult(False, 0, "✗ 领出不能不出(违规, 已拦截)")
            ex.pass_turn()
            return ExecResult(True, 0, "不出")
        # RL 臂: 打的是我们自己选的牌 → 必须点选直出(提示只会出游戏自己选的牌)
        if action.meta.get("direct") and action.combo is not None and obs.hand:
            idxs = _map_indices(self._hand_for_map(obs), action.combo.cards)
            if idxs:
                if ex.direct_play(idxs, len(obs.hand),
                                  want_cards=list(action.combo.cards)):
                    self._log_plan(action.combo, action.meta.get("why", ""))   # 打出去了才记决策
                    self._verify_identity(action.combo, action.meta.get("why", ""))  # ★ 即时对账 ✓
                    self._log_seat_play("南", action.combo.cards,
                                        hand_left=max(0, len(obs.hand) - len(action.combo.cards)),
                                        src="own")
                    # 出牌**成功后**才设期望(按我们意图的张数) → 下次读手牌做校验
                    return ExecResult(True, 0, "直选出牌(RL)")
                why = ""
                if getattr(ex, "cdp", None) is not None:
                    try:
                        why = (ex.cdp.toast() or "").strip()
                    except Exception:  # noqa: BLE001
                        why = ""
                # ★★ 2026-09-21 用户指出: toast 会取到**过期文本** ⇒ 假警报 ✗
                #   实测: 报的是"北 不出"/"西 不出" —— 那是**别人不出牌**的提示 ✓
                #        却把"选牌没选中"记成了"游戏拒绝出牌" ⇒ 4 次被拒全是假的 ✗
                #   判据: 只有**含拒绝关键词**的才算游戏拒绝; 其余一律归"未生效" ✓
                _REJECT = ("无效", "太小", "压不过", "不能出", "违规", "该你", "轮到你", "不是该你")
                if why and not any(k in why for k in _REJECT):
                    print(f"  [真值] 出牌未生效(提示文本与本次无关, 判为未生效): {why!r}", flush=True)
                    why = ""
                if why:
                    # ★ 2026-09-21 诊断: 被拒时把"我们想出的"和"游戏实际看到的"都记下来
                    #   ⇒ 一眼分清是"读错桌上牌"还是"算错大小" ✓
                    _want = [c.zhi for c in action.combo.cards]
                    _seen = ""
                    try:
                        _tfn = getattr(ex.cdp, "truth", None)
                        _t2 = (_tfn() if callable(_tfn) else None) or {}
                        _sh = _t2.get("shangJia") or []
                        _seen = (f" | 游戏看到: 桌上={[(c.get('zhi'), c.get('hua')) for c in _sh]} "
                                 f"needBeat={_t2.get('needBeat')} 级牌={_t2.get('jiPai')} "
                                 f"选中={_t2.get('selected')}")
                    except Exception:  # noqa: BLE001
                        _seen = ""
                    print(f"  [真值] 出牌被游戏拒绝: {why} | 我们想出={_want}{_seen}", flush=True)
                rpt = getattr(ex, "last_report", None)
                if rpt is not None and (rpt.not_our_turn or rpt.skipped):
                    # 执行器规范: 识别/活性不满足 ⇒ 跳过, 不是失败(不计入失败率)
                    return ExecResult(True, 0, f"跳过 · {rpt.reason}", skipped=True)
                return ExecResult(False, 1, f"直选失败(RL){' · ' + why if why else ''}")
        # ★ 提示臂已禁用(2026-09-17 用户拍板): "点提示=游戏帮我们挑牌", 那不是我们的 AI ✗
        #   → 出牌只走**直选**(我们自己决定哪几张 → 点那几张), 失败就报失败, 绝不退化到提示 ✓
        if action.kind == "none":
            return ExecResult(True, 0, "本帧不动作(等待重读)", skipped=True)
        # ★★ 出牌前自检(2026-09-17 用户实证: 游戏弹"无效的牌型组合" ✗ —— 是我们的决策错了)
        #    先用**我们自己的规则库**验一次: 牌型合法吗? 压得过桌上吗? 不合法就**不出** ✓
        #    (宁可不出, 也绝不去点一套游戏不认的牌 —— 后者还会在牌桌上留下残留选中 ✗)
        if action.combo is not None:
            try:
                _g = R.identify(list(action.combo.cards), self._jp())
                if getattr(_g, "is_invalid", False):
                    return ExecResult(False, 0, f"自检: 牌型非法({action.combo!r}) → 不出", skipped=True)
                if obs.table:
                    _last = R.identify(list(obs.table), self._jp())
                    if not R.can_beat(_g, _last):
                        return ExecResult(False, 0, "自检: 压不过桌上牌 → 不出", skipped=True)
            except Exception as e:  # noqa: BLE001
                print(f"  [自检] 异常({type(e).__name__}) → 放行", flush=True)
        if action.combo is not None and obs.hand:
            idxs = _map_indices(self._hand_for_map(obs), action.combo.cards)
            if idxs:
                if ex.direct_play(idxs, len(obs.hand),
                                  want_cards=list(action.combo.cards)):
                    self._verify_identity(action.combo, action.meta.get("why", ""))  # ★ 即时对账 ✓
                    self._log_plan(action.combo, action.meta.get("why", ""))
                    self._log_seat_play("南", action.combo.cards,
                                        hand_left=max(0, len(obs.hand) - len(action.combo.cards)),
                                        src="own")
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
        # ★★ 决定性闸门(2026-09-17 用户指令: 别留着反复影响 ✗):
        #   有真值通道时, **真值说还在打牌(playing)就绝不可能是结算** ⇒ 直接否掉 ✓
        #   (实测 a11y 文本每次都在变 ⇒ 文本去重失效; 60s 冷却也拦不住 ⇒ 200 秒里误记 9 局 ✗)
        try:
            _tr = self._ex.cdp.truth() if getattr(self._ex, "cdp", None) is not None else None
        except Exception:  # noqa: BLE001
            _tr = None
        if _tr and _tr.get("phase") == "playing":
            return None
        # ★★ 2026-09-20 用户定: **真值有结算就直接用它** ✓
        #   以前只把真值当"否决闸门"用 ✗ ⇒ 结算仍靠 a11y 文本猜, 没有 名次/结构,
        #   连 win 都解析不出来(实测 result={"raw":..., "win":null} ✗)
        #   现在: 真值 result(won/升级数/四家名次/头游/新级牌/炸弹数) 直接进库 ✓
        _res = (_tr or {}).get("result") if _tr else None
        if isinstance(_res, dict) and _res:
            raw = f"头游={_res.get('touYou')};升级={_res.get('shengJiShu')}级"
            try:
                self.log.deal_end(raw=raw, **{k: v for k, v in _res.items()})
            except Exception:                # noqa: BLE001
                pass
            _now2 = time.time()
            self._last_settle_key = raw.strip()[:200]
            self._last_settle_t = _now2
            return SettleInfo(raw=raw, win=bool(_res.get("won")))
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


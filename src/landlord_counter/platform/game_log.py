"""牌局事件日志: 追溯"谁打了什么牌" + "池子里还剩什么" + 可回放/可查询。

设计目标(用户 2026-09-16 要求):
  1. 掼蛋/斗地主**都要**有记牌器;
  2. 后台**能调出数据** —— 至少能追溯出牌历史(谁打了什么牌)、池子里还有哪些牌;
  3. 数据要能长期保留、可回放、可导出(为后面的伴随应用/后台看板打底)。

落盘格式(追加式, 一行一事件, 重启可恢复):
  data/games/<game_id>.jsonl
    {"t": 1789..., "seq": 1, "type": "deal_start", "seats": [...], "jipai": 2}
    {"t": ..., "seq": 2, "type": "play", "seat": "南", "cards": ["♠5","♥5"], "action": "play", "hand_left": 25}
    {"t": ..., "seq": 3, "type": "pass", "seat": "西"}
    {"t": ..., "seq": 4, "type": "deal_end", "result": {...}, "raw": "头游=北"}

查询(内存态由事件重放得到, 重启后 load() 即可恢复):
  .history(seat=None)   → 逐手(谁打了什么)
  .pool()               → 池子里还剩什么(未见牌)
  .seat_played(seat)    → 某家出过的所有牌
  .summary()            → 一行概览
"""
from __future__ import annotations

import json
import os
import time
from collections import Counter
from dataclasses import dataclass, field
from typing import Any

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
DATA_DIR = os.getenv("GAME_DATA_DIR", os.path.join(ROOT, "data", "games"))


def _zhi(card: Any) -> int:
    if isinstance(card, int):
        return card
    return int(getattr(card, "zhi", card))


def _name(card: Any) -> str:
    if isinstance(card, str):
        return card
    try:
        return str(card)
    except Exception:  # noqa: BLE001
        return str(_zhi(card))


@dataclass
class GameLog:
    """一局(或一"局牌")的事件流 + 记牌查询。"""

    game_id: str
    game_type: str = "guandan"            # guandan | ddz
    seats: tuple = ("南", "西", "北", "东")
    deck_total: int = 108                 # 掼蛋 108(2副) / 斗地主 54(1副)
    per_rank_total: dict = field(default_factory=dict)   # 点数→总张数
    path: str = ""
    events: list = field(default_factory=list)
    played: dict = field(default_factory=lambda: {})      # seat → Counter(点数)
    my_hand: Counter = field(default_factory=Counter)
    _seq: int = 0
    _fh: Any = None
    # ★ 旁观者插座 (2026-09-19 伴随应用 M1 ✓): 每写一条事件就**广播一份**给旁观者
    #   · 只收不发: 旁观者只许"收数据/存数据" ✗ 不许回写/改牌局
    #   · **旁观者出事绝不影响牌局** —— 下面用 try/except 全兜住 ✓(牌局 > 记录 ✓)
    sink: Any = None

    # ---------------- 生命周期 ----------------
    def __post_init__(self) -> None:
        os.makedirs(DATA_DIR, exist_ok=True)
        self.path = self.path or os.path.join(DATA_DIR, f"{self.game_id}.jsonl")
        if not self.played:
            self.played = {s: Counter() for s in self.seats}
        if not self.per_rank_total:
            # 掼蛋: 2..A 各 8 张, 王各 2; 斗地主: 各 4 张, 王各 1
            if self.game_type == "guandan":
                self.per_rank_total = {r: 8 for r in range(2, 15)} | {15: 2, 16: 2}
            else:
                self.per_rank_total = {r: 4 for r in range(2, 15)} | {15: 1, 16: 1}
                self.deck_total = 54

    def load(self) -> "GameLog":
        """从落盘文件重放, 恢复内存态(重启后可继续)。"""
        if not os.path.exists(self.path):
            return self
        with open(self.path, encoding="utf-8") as f:
            for line in f:
                try:
                    ev = json.loads(line)
                except Exception:  # noqa: BLE001
                    continue
                self.events.append(ev)                 # 事件流也要恢复(历史/回放靠它)
                self._seq = max(self._seq, int(ev.get("seq", 0)))
                self._apply(ev)
        return self

    def _fh_open(self):
        if self._fh is None:
            self._fh = open(self.path, "a", encoding="utf-8")
        return self._fh

    def close(self) -> None:
        try:
            if self._fh:
                self._fh.close()
        except Exception:  # noqa: BLE001
            pass
        self._fh = None

    # ---------------- 写事件 ----------------
    def append(self, type_: str, **kw) -> dict:
        self._seq += 1
        ev = {"t": round(time.time(), 3), "seq": self._seq, "type": type_, **kw}
        self.events.append(ev)
        if self.sink is not None:      # ★ 广播给旁观者(伴随应用) —— 出事绝不影响牌局 ✓
            try:
                self.sink(ev)
            except Exception as e:     # noqa: BLE001
                print(f"  [sink] ⚠ 旁观者出错({type(e).__name__}: {e}) → 已忽略, 牌局继续 ✓",
                      flush=True)
        try:
            fh = self._fh_open()
            fh.write(json.dumps(ev, ensure_ascii=False) + "\n")
            fh.flush()
        except Exception:  # noqa: BLE001
            pass
        self._apply(ev)
        return ev

    def deal_start(self, seats=None, **extra) -> dict:
        if seats:
            self.seats = tuple(seats)
            self.played = {s: Counter() for s in self.seats}
        self.my_hand = Counter()
        return self.append("deal_start", seats=list(self.seats), **extra)

    def play(self, seat: str, cards, hand_left: int | None = None, src: str = "table") -> dict:
        """记一手出牌。src: table=从画面读回(实测) / own=我们自己发起的。"""
        cards = list(cards)
        ev = self.append("play", seat=seat, action="play",
                         cards=[_name(c) for c in cards], hand_left=hand_left, src=src)
        return ev

    def plan(self, seat: str, cards, why: str = "", hand_before: int | None = None,
             **extra) -> dict:
        """记一次**决策**(我们打算出的牌) —— 用于"决定 vs 实际打出"的操作准确率对账。"""
        return self.append("plan", seat=seat, cards=[_name(c) for c in cards], why=why,
                           n=len(list(cards)), hand_before=hand_before, **extra,
                           src=("direct" if "RL" in why or "直选" in why else "hint"))

    def verify(self, seat: str, hand_after: int, expected_after: int) -> dict:
        """出牌后的**张数校验**: 实际掉牌数 是否等于 决策张数(抓"自动带上同点数")。"""
        return self.append("verify", seat=seat, hand_after=hand_after,
                           expected_after=expected_after,
                           ok=(hand_after == expected_after),
                           delta=(expected_after - hand_after) if expected_after is not None else None)

    def pass_(self, seat: str) -> dict:
        return self.append("pass", seat=seat, action="pass")

    def deal_end(self, **result) -> dict:
        return self.append("deal_end", **result)

    def amend_last_play(self, seat: str, cards) -> bool:
        """把**最后一条**出牌事件的牌面改成更全的读数(同一手被读两次、第二次更全时用)。

        记牌器要的是"某家出了哪些牌" —— 读到 8 张又读到 10 张时, 应以更全的为准。
        """
        for ev in reversed(self.events):
            if ev.get("type") == "play" and ev.get("seat") == seat:
                names = [str(c) for c in cards]
                if len(names) <= len(ev.get("cards", [])):
                    return False
                ev["cards"] = names
                ev["amended"] = True
                try:                                  # 同步改落盘的最后一行
                    if os.path.exists(self.path):
                        rows = open(self.path, encoding="utf-8").read().splitlines()
                        for i in range(len(rows) - 1, -1, -1):
                            if rows[i].strip():
                                rows[i] = json.dumps(ev, ensure_ascii=False)
                                break
                        open(self.path, "w", encoding="utf-8").write("\n".join(rows) + "\n")
                except Exception:                     # noqa: BLE001
                    pass
                return True
        return False

    def set_my_hand(self, cards) -> None:
        self.my_hand = Counter(_zhi(c) for c in cards)

    # ---------------- 重放 ----------------
    def _apply(self, ev: dict) -> None:
        t = ev.get("type")
        if t == "play":
            seat = ev.get("seat")
            if seat in self.played:
                for c in ev.get("cards", []):
                    self.played[seat][_rank_of(c)] += 1

    # ---------------- 查询(后台接口用) ----------------
    def history(self, seat: str | None = None, limit: int = 500) -> list:
        """逐手出牌记录: 谁、什么时候、打了什么(含不出)。"""
        out = []
        for ev in self.events:
            if ev.get("type") not in ("play", "pass"):
                continue
            if seat and ev.get("seat") != seat:
                continue
            out.append({"seq": ev.get("seq"), "t": ev.get("t"), "seat": ev.get("seat"),
                        "action": ev.get("action"), "cards": ev.get("cards", []),
                        "hand_left": ev.get("hand_left")})
        return out[-limit:]

    def seat_played(self, seat: str) -> Counter:
        return Counter(self.played.get(seat, Counter()))

    def pool(self) -> dict:
        """池子里还剩什么(未见牌, 按点数): 总数 − 我方手牌 − 各家已出。"""
        out = {}
        for r, tot in sorted(self.per_rank_total.items()):
            left = tot - self.my_hand.get(r, 0) - sum(self.played[s].get(r, 0) for s in self.seats)
            if left > 0:
                out[str(r)] = left
        return out

    def seat_remaining(self) -> dict:
        """各家余牌张数(我方=手牌数, 他方=每位初始 − 已出)。"""
        per_seat = self.deck_total // max(1, len(self.seats))
        out = {}
        for s in self.seats:
            out[s] = len(self.my_hand) if (s == self.seats[0] and self.my_hand) else \
                max(0, per_seat - sum(self.played[s].values()))
        return out

    def violations(self) -> list:
        """守恒自检: 手牌 + 已出 不得超过该点数总数(读错即暴露)。"""
        bad = []
        for r, tot in self.per_rank_total.items():
            used = self.my_hand.get(r, 0) + sum(self.played[s].get(r, 0) for s in self.seats)
            if used > tot:
                bad.append({"rank": r, "limit": tot, "used": used})
        return bad

    def summary(self) -> dict:
        return {"game_id": self.game_id, "type": self.game_type, "events": len(self.events),
                "plays": sum(1 for e in self.events if e.get("type") == "play"),
                "passes": sum(1 for e in self.events if e.get("type") == "pass"),
                "pool_left": sum(self.pool().values()),
                "seat_remaining": self.seat_remaining(),
                "violations": self.violations()}

    def to_dict(self) -> dict:
        return {"summary": self.summary(), "seats": list(self.seats),
                "played": {s: dict(self.played[s]) for s in self.seats},
                "pool": self.pool(), "history_tail": self.history(limit=20)}


def _rank_of(card_name: str) -> int:
    """从牌名反推点数(用于重放): '♠5' → 5; 大小王 → 15/16。"""
    s = str(card_name)
    if "小" in s and "王" in s:
        return 15
    if "王" in s:
        return 16
    import re

    m = re.search(r"(10|[2-9AJQK])", s.upper())
    if not m:
        return 0
    tok = m.group(1)
    return {"A": 14, "J": 11, "Q": 12, "K": 13, "10": 10}.get(tok, int(tok) if tok.isdigit() else 0)


def list_games() -> list:
    """列出落盘的所有牌局(供 /games 接口)。"""
    out = []
    if not os.path.isdir(DATA_DIR):
        return out
    for fn in sorted(os.listdir(DATA_DIR)):
        if not fn.endswith(".jsonl"):
            continue
        p = os.path.join(DATA_DIR, fn)
        gid = fn[:-6]
        try:
            with open(p, encoding="utf-8") as f:
                first = None
                last = None
                n = 0
                for line in f:
                    n += 1
                    if first is None:
                        first = line
                    last = line
            import json as _j

            f0 = _j.loads(first) if first else {}
            fl = _j.loads(last) if last else {}
            out.append({"game_id": gid, "events": n,
                        "started": f0.get("t"), "last": fl.get("t"),
                        "type": f0.get("game_type") or ("guandan" if "seats" in f0 else "?")})
        except Exception:  # noqa: BLE001
            continue
    return out

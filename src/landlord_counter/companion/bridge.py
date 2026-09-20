"""伴随应用: 水管 —— 把 GameLog 的事件流翻译成牌局库的四个写入口 ✓

一张图看懂它在哪:
    GameLog.append(事件)  ──sink──▶  bridge.sink(ev)  ──▶  CompanionStore(四张表)
       (现有逻辑 ✓)                    (本文件, 只搬字段 ✓)         (只落库 ✓)

**只收不发** ✓: 本文件只做"字段搬运 + 事件类型映射" ✗ 不算牌、不解析牌型、不碰画面/点击
越界检验: 出现 识别(cv2) / 牌型规则 / 点击(maatouch) ⇒ 就是造第二套, 越界 ✗
"""
from __future__ import annotations

from typing import Any


def make_sink(log: Any, store: Any, gid: str):
    """造一个可挂到 `GameLog.sink` 的函数 ✓

    参数为什么带 `log`: 事件里只有"变动的部分", 而开局手牌/牌池这些**状态**在 log 上
      —— 直接读它 = 复用现有实现 ✓(自己再算一遍就是第二套 ✗)
    """

    _last_hand: list = []          # 缓存最近一条 hand 事件(开局手牌) ✓
    _deal_n = 0                    # 同一个 gid 下的第几局
    _base_gid = gid                # 原始局号(分钟级)

    def sink(ev: dict) -> None:
        nonlocal _last_hand, _deal_n, gid
        t = ev.get("type")
        # ★ 优先用结构化牌(`cards_raw` = [{zhi,hua}]) ✓ 取不到才退回字符串名
        cards = ev.get("cards_raw") or ev.get("cards")

        if t == "hand":
            _last_hand = ev.get("cards_raw") or ev.get("cards") or []

        elif t == "deal_start":
            # ★ 2026-09-20: 局号加"第几局"后缀 —— 原局号是分钟级, 同一分钟多局会串 ✓
            _deal_n += 1
            gid = f"{_base_gid}#{_deal_n}"
            store.record_deal(gid, _last_hand or list(getattr(log, "my_hand", []) or []),
                              seat="南", ji_pai=ev.get("ji_pai"))

        elif t in ("play", "pass"):
            seat = ev.get("seat", "南")
            # 是不是我出的: 座位名对得上就算我出的 ✓(掼蛋我方坐"南")
            mine = seat == "南"
            store.record_play(gid, seat, cards if t == "play" else [],
                              # ★ 2026-09-20: 优先用事件里的真值(adapter 传的真·剩牌)
                              #   ✗ 旧写法用 len(log.my_hand) 是估的, 实测滞后
                              hand_left=ev.get("hand_left"),
                              mine=mine, kind=t, ts=ev.get("t"))
            # 牌池快照: 直接取 log.pool() ✓ —— **它本来就是算这个的** ✗ 这里绝不自己算
            try:
                store.snapshot_remains(gid, len(getattr(log, "my_hand", []) or []), log.pool())
            except Exception:            # noqa: BLE001
                pass                     # 快照失败不影响牌局/不影响落库主流程 ✓

        elif t == "plan":
            store.record_decision(
                gid,
                hand_n=int(ev.get("hand_before") or 0),
                need_beat=bool(ev.get("need_beat")),      # 唯一判据 ✓(领出/压)
                cand_n=int(ev.get("cand_n") or 0),
                chosen=cards,
                note=str(ev.get("why") or ""),
            )

        elif t == "identity":
            # ★ 2026-09-20 用户定: **唯一权威的对账** = 决定的牌 vs 真值实出的牌
            #   (逐张比点数+花色 ✓)。旧口径"手牌掉几张"是间接推断、读数滞后就误判 ✗ 已删。
            store.mark_last_decision(gid, agree=bool(ev.get("ok")))

    return sink

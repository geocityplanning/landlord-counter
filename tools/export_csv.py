#!/usr/bin/env python3
"""按需把库里的牌局数据导成 CSV(数据源 = sqlite ✓, 平时不落 csv 文件 ✓)

用户: "数据全部从 sql 拿" + 之前要过 csv
  ⇒ 所以 csv **不常驻**(库里是唯一数据源 ✓), 只在你要的时候生成 ✓

用法:
  PYTHONPATH=src python3 tools/export_csv.py [输出目录] [局号可选]
  默认输出目录: /tmp/csv_out  (utf-8-sig, Excel 直接打开不乱码 ✓)

产物:
  deals.csv      每局一行: 级牌/胜负/头游/升级/名次/结算原文
  plays.csv      每手: 谁在什么时候打了什么牌
  decisions.csv  每次决策: 手牌数/压或领出/候选数/选了哪手/对账
  summary.csv    汇总: 胜率/头游率/双上率/场均升级/准确率
"""
from __future__ import annotations

import csv
import json
import os
import sqlite3
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
from landlord_counter.companion.store import DEFAULT_DB  # noqa: E402

OUT = sys.argv[1] if len(sys.argv) > 1 else "/tmp/csv_out"
GID = sys.argv[2] if len(sys.argv) > 2 else None
SEATS = {0: "我(南)", 1: "西", 2: "队友(北)", 3: "东"}
ZHI = {11: "J", 12: "Q", 13: "K", 14: "A", 15: "小王", 16: "大王"}
HUA = {0: "♠", 1: "♥", 2: "♣", 3: "♦", 4: "★"}


def card_str(c) -> str:
    """{'zhi':13,'hua':0} → ♠K (可读 ✓)"""
    if isinstance(c, dict):
        z = int(c.get("zhi") or 0)
        h = int(c.get("hua") or 0)
    else:
        return str(c)
    return f"{HUA.get(h, '?')}{ZHI.get(z, str(z))}"


def cards_str(raw) -> str:
    try:
        cs = json.loads(raw) if isinstance(raw, str) else raw
    except Exception:  # noqa: BLE001
        return str(raw or "")
    if not isinstance(cs, list):
        return str(cs)
    return " ".join(card_str(c) for c in cs)


def main() -> int:
    os.makedirs(OUT, exist_ok=True)
    db = str(DEFAULT_DB if os.path.isabs(str(DEFAULT_DB)) else os.path.join(ROOT, str(DEFAULT_DB)))
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True, timeout=5)
    con.row_factory = sqlite3.Row
    where, args = ("WHERE gid LIKE ?", [GID + "%"]) if GID else ("", [])

    def dump(fn, header, rows):
        p = os.path.join(OUT, fn)
        with open(p, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            w.writerow(header)
            w.writerows(rows)
        print(f"  {fn:16s} {len(rows):>6d} 行")
        return p

    # ① 局
    deals = []
    for r in con.execute(f"SELECT gid, ji_pai, started_at, ended_at, result_json FROM deal {where} "
                         "ORDER BY started_at", args):
        d = {}
        if r["result_json"]:
            try:
                d = json.loads(r["result_json"])
            except Exception:  # noqa: BLE001
                d = {}
        yc = d.get("youCiList") or []
        mine = [i + 1 for i, s in enumerate(yc) if s in (0, 2)]
        deals.append([
            r["gid"], r["ji_pai"],
            time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(r["started_at"])) if r["started_at"] else "",
            time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(r["ended_at"])) if r["ended_at"] else "",
            "赢" if d.get("won") else ("输" if d.get("won") is False else ""),
            d.get("touYou", ""), d.get("shengJiShu", ""), min(mine) if mine else "",
            "/".join(str(x) for x in yc), d.get("xinJiPai", ""), d.get("zhaDanShu", ""),
            json.dumps(d.get("matchOver"), ensure_ascii=False) if d.get("matchOver") else "",
            d.get("raw", ""),
        ])
    dump("deals.csv",
         ["局号", "级牌", "开始", "结束", "我方胜负", "头游座位", "升级数", "我方较好名次",
          "名次顺序(座位)", "新级牌", "炸弹数", "整场结束", "结算原文"], deals)

    # ② 每手
    w2, a2 = ("WHERE gid LIKE ?", [GID + "%"]) if GID else ("", [])
    plays = []
    for r in con.execute(f"SELECT gid, seq, ts, seat, mine, cards_json, hand_left, kind, actor "
                         f"FROM play {w2} ORDER BY gid, seq", a2):
        plays.append([r["gid"], r["seq"],
                      time.strftime("%H:%M:%S", time.localtime(r["ts"])) if r["ts"] else "",
                      SEATS.get(r["seat"], r["seat"]),
                      # ★ 掼蛋是 2v2: 南(我)+北(队友) = 我方 ✓ (不看 mine 列 —— 那列只表示"是不是我点的" ✗)
                      "我方" if str(r["seat"]) in ("南", "北", "0", "2") else "对方",
                      cards_str(r["cards_json"]), r["hand_left"], r["kind"], r["actor"]])
    dump("plays.csv",
         ["局号", "第几手", "时间", "座位", "敌我", "出的牌", "出完剩几张", "类型", "来源"], plays)

    # ③ 决策
    w3, a3 = ("WHERE gid LIKE ?", [GID + "%"]) if GID else ("", [])
    decs = []
    for r in con.execute(f"SELECT gid, ts, hand_n, need_beat, cand_n, chosen_json, agree, note "
                         f"FROM decision {w3} ORDER BY ts", a3):
        decs.append([r["gid"],
                     time.strftime("%H:%M:%S", time.localtime(r["ts"])) if r["ts"] else "",
                     r["hand_n"], "要压" if r["need_beat"] else "领出", r["cand_n"],
                     cards_str(r["chosen_json"]) or "不出",
                     {1: "一致", 0: "不一致"}.get(r["agree"], ""), r["note"]])
    dump("decisions.csv",
         ["局号", "时间", "手牌数", "处境", "候选数", "选了哪手", "对账", "备注"], decs)

    # ④ 汇总
    ok = [d for d in deals if d[4] in ("赢", "输")]
    n = len(ok)
    wins = sum(1 for d in ok if d[4] == "赢")
    ty = sum(1 for d in ok if d[5] in (0, 2))
    ss = sum(1 for d in ok if d[8] and set(str(d[8]).split("/")[:2]) == {"0", "2"})
    ups = [(d[6] if d[4] == "赢" else -(d[6] or 0)) for d in ok if isinstance(d[6], (int, float))]
    acc = con.execute("SELECT COUNT(*) n, SUM(agree) a FROM decision WHERE agree IS NOT NULL").fetchone()
    rows = [
        ["有结算的局数", n],
        ["我方胜率", f"{100*wins/n:.1f}%" if n else ""],
        ["我方头游率", f"{100*ty/n:.1f}%" if n else ""],
        ["双上率", f"{100*ss/n:.1f}%" if n else ""],
        ["场均升级(我方净)", f"{sum(ups)/len(ups):+.2f}" if ups else ""],
        ["决策总次数", con.execute("SELECT COUNT(*) FROM decision").fetchone()[0]],
        ["操作对账一致", f"{acc['a']}/{acc['n']}" if acc["n"] else ""],
        ["每手记录", con.execute("SELECT COUNT(*) FROM play").fetchone()[0]],
    ]
    dump("summary.csv", ["指标", "值"], rows)
    con.close()
    print(f"\n输出目录: {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

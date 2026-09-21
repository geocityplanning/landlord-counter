"""伴随应用: 本地牌局库 (SQLite) —— 整套方案里**唯一的新东西** ✓

设计约定 (2026-09-19 与用户定稿 ✓)
------------------------------------------------
· **只收不发**: 数据全部来自现有逻辑 (GameLog 事件流水 / CardTracker 账本) ✓
  → 越界检验: 本文件里**不许出现** 图像识别 / 牌型规则 / 点击 / 自己的记牌算法 ✗
    出现任何一个 ⇒ 就是造第二套, 违反"一套逻辑"铁律 ✗
· **只落本地**: 库文件默认 `data/companion.db`, 已 gitignore ✓ (牌局数据敏感, 绝不进公开仓 ✓)
· 四张表 (用户 2026-09-18 定的内容 ✓):
    deal       每局开局: 我的手牌 / 级牌 / 局号 / 时间
    play       每一手: 谁出的 / 什么牌 (点+花色) / 剩几张 / 是不是我出的
    decision   每次决策: 候选 / 选中 / 对账结果 (✓一致 ✗不一致)
    remains    牌池快照: 每个点数剩几张 (可回放整局)

"记忆" 就是**对这四张表做长周期查询** (不另建表 ✓):
  胜率/头游率(组队口径) · 对手习惯 · 操作准确率历史曲线
"""
from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
from pathlib import Path

DEFAULT_DB = Path(os.getenv("COMPANION_DB", "data/companion.db"))

_SCHEMA = """
CREATE TABLE IF NOT EXISTS deal (
    gid         TEXT PRIMARY KEY,      -- 牌局编号(含"第几局"后缀, 同分钟不撞号 ✓)
    ts          REAL,                  -- 建行时间戳(老库靠迁移补的; 建表时**必须也写** ✗)
    game_type   TEXT,                  -- ★ 游戏分类: guandan / ddz / mahjong …
    started_at  REAL,                  -- ★ 开局日期时间
    ended_at    REAL,                  -- ★ 结束日期时间(结算时回填)
    result_json TEXT,                  -- ★ 结算结果(名次/升级/队友名次 … 供以后评指标)
    seat        TEXT,                  -- 我方座位
    hand_json   TEXT,                  -- 开局手牌 (点+花色)
    ji_pai      INTEGER,               -- 级牌点数 (打A=14; 掼蛋专有, 其它游戏可空)
    extra_json  TEXT
);
CREATE TABLE IF NOT EXISTS play (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    gid         TEXT,                  -- 哪一局
    seq         INTEGER,               -- 第几手 (局内递增)
    ts          REAL,
    seat        TEXT,                  -- 谁出的
    mine        INTEGER,               -- 是不是**我方**出的 (1/0; 0=对方)
    actor       TEXT,                  -- ★ 我方这一手是**谁决定的**: human 人 / ai 托管
    cards_json  TEXT,                  -- 牌 (点+花色)
    hand_left   INTEGER,               -- 出完还剩几张
    kind        TEXT                   -- 'play' | 'pass'
);
CREATE INDEX IF NOT EXISTS idx_play_gid ON play(gid, seq);
CREATE TABLE IF NOT EXISTS decision (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    gid         TEXT,
    ts          REAL,
    hand_n      INTEGER,               -- 决策时手牌张数
    need_beat   INTEGER,               -- 1=压 0=领出 (唯一判据 ✓)
    cand_n      INTEGER,               -- 候选数
    chosen_json TEXT,                  -- 选中的牌
    agree       INTEGER,               -- 对账: 1 一致 / 0 不一致 / NULL 未验
    note        TEXT
);
CREATE INDEX IF NOT EXISTS idx_dec_gid ON decision(gid, ts);
CREATE TABLE IF NOT EXISTS remains (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    gid         TEXT,
    ts          REAL,
    hand_n      INTEGER,               -- 快照时我的手牌张数
    counts_json TEXT                   -- {点数: 剩余张数}  ← 来自 CardTracker.remaining_counts() ✓
);
CREATE INDEX IF NOT EXISTS idx_rem_gid ON remains(gid, ts);
CREATE TABLE IF NOT EXISTS control (
    k           TEXT PRIMARY KEY,      -- 目前只有 "host"
    v           TEXT,                  -- "1"=想开托管 / "0"=想关
    ts          REAL
);
"""


class CompanionStore:
    """本地牌局库。**只收不发** —— 所有写入口都喂"现有逻辑"吐出来的东西 ✓"""

    def __init__(self, path: str | Path = DEFAULT_DB) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # ★ 服务是多线程的(ThreadingHTTPServer) ⇒ 连接必须允许跨线程 ✗ 否则一读就崩
        #   写操作再加锁(读多写少, 锁开销可忽略 ✓)
        self.db = sqlite3.connect(str(self.path), check_same_thread=False)
        self._lock = threading.Lock()
        self.db.executescript(_SCHEMA)
        self._migrate()                        # ★ 老库补新列(不丢历史数据 ✓)
        self.db.commit()
        self._seq: dict[str, int] = {}          # 局内手数计数

    # 新增列清单(老库升级用; 已存在则跳过 ✓)
    _MIGRATE = (
        ("deal", "game_type", "TEXT"),
        ("deal", "started_at", "REAL"),
        ("deal", "ended_at", "REAL"),
        ("deal", "result_json", "TEXT"),
        ("play", "actor", "TEXT"),
    )

    def _migrate(self) -> None:
        """老库补新列 —— 历史牌局数据一律保留 ✓(用户要拿它做回溯 ✓)"""
        for table, col, typ in self._MIGRATE:
            try:
                self.db.execute(f"ALTER TABLE {table} ADD COLUMN {col} {typ}")
            except sqlite3.OperationalError:
                pass                            # 列已存在 ✓
        # 老库只有 ts ⇒ 回填成 started_at(开局时间) ✓
        try:
            self.db.execute("UPDATE deal SET started_at = ts"
                            " WHERE started_at IS NULL AND ts IS NOT NULL")
        except sqlite3.OperationalError:
            pass

    # ---------------- 写入口 (四个, 对应四张表) ----------------
    def record_deal(self, gid: str, hand, seat: str = "0", ji_pai: int | None = None,
                    game_type: str = "guandan", **extra) -> None:
        self.db.execute(
            "INSERT OR REPLACE INTO deal(gid, game_type, started_at, ts, seat, hand_json,"
            " ji_pai, extra_json) VALUES(?,?,?,?,?,?,?,?)",
            (gid, game_type, time.time(), time.time(), seat, _cards_json(hand), ji_pai,
             json.dumps(extra, ensure_ascii=False)))
        self._seq[gid] = 0
        self.db.commit()

    def record_play(self, gid: str, seat: str, cards, hand_left: int | None = None,
                    mine: bool = False, kind: str = "play", ts: float | None = None,
                    actor: str = "ai") -> None:
        self._seq[gid] = self._seq.get(gid, 0) + 1
        self.db.execute(
            "INSERT INTO play(gid, seq, ts, seat, mine, actor, cards_json, hand_left, kind)"
            " VALUES(?,?,?,?,?,?,?,?,?)",
            (gid, self._seq[gid], ts or time.time(), seat, int(mine), actor,
             _cards_json(cards), hand_left, kind))
        self.db.commit()

    def record_decision(self, gid: str, hand_n: int, need_beat: bool, cand_n: int,
                        chosen, agree: bool | None = None, note: str = "") -> None:
        self.db.execute(
            "INSERT INTO decision(gid, ts, hand_n, need_beat, cand_n, chosen_json, agree, note)"
            " VALUES(?,?,?,?,?,?,?,?)",
            (gid, time.time(), hand_n, int(need_beat), cand_n, _cards_json(chosen),
             None if agree is None else int(agree), note))
        self.db.commit()

    def snapshot_remains(self, gid: str, hand_n: int, counts: dict) -> None:
        """牌池快照 —— counts 直接来自 CardTracker.remaining_counts() ✓ (这里不许自己算 ✗)"""
        self.db.execute(
            "INSERT INTO remains(gid, ts, hand_n, counts_json) VALUES(?,?,?,?)",
            (gid, time.time(), hand_n, json.dumps(counts, ensure_ascii=False)))
        self.db.commit()

    def mark_last_decision(self, gid: str, agree: bool | None = None,
                           note: str | None = None) -> None:
        """给**本局最后一次决策**补对账结果 ✓ (出牌后自检回填, 不是新写一条 ✗)"""
        row = self.db.execute("SELECT id FROM decision WHERE gid=? ORDER BY id DESC LIMIT 1",
                              (gid,)).fetchone()
        if not row:
            return
        if agree is not None:
            self.db.execute("UPDATE decision SET agree=? WHERE id=?", (int(agree), row[0]))
        if note:
            self.db.execute("UPDATE decision SET note=? WHERE id=?", (note, row[0]))
        self.db.commit()

    def end_deal(self, gid: str, result: dict | None = None) -> None:
        """结算回填: **结束日期时间** + 结果(名次/升级/队友名次 …) ✓"""
        self.db.execute("UPDATE deal SET ended_at=?, result_json=? WHERE gid=?",
                        (time.time(), json.dumps(result or {}, ensure_ascii=False), gid))
        self.db.commit()

    def mark_match_over(self, gid: str, data: dict, extra: dict | None = None) -> None:
        """把"**过A通关**"当场写进该局的结果里 ✓ —— 不必等结算(等结算常常就丢了 ✗)

        为什么需要(2026-09-21 实测): 大循环明明闭环了(级牌 14→2 ✓),
          但库里 matchOver **0 条** ✗ —— 因为"等结算"时那局往往还没结算就跑完了 ✓
        · 只**合并**这几个字段, 不动其它 ✓ (结算晚点来时 end_deal 会整体覆盖 ✓)
        · extra: 顺带记的(如 matchGames / jiPai ✓)
        """
        row = self.db.execute("SELECT result_json FROM deal WHERE gid=?", (gid,)).fetchone()
        try:
            cur = json.loads((row[0] if row else "") or "{}") or {}
        except Exception:                    # noqa: BLE001
            cur = {}
        cur["matchOver"] = data
        for k, v in (extra or {}).items():
            if v is not None:
                cur[k] = v
        self.db.execute("UPDATE deal SET result_json=? WHERE gid=?",
                        (json.dumps(cur, ensure_ascii=False), gid))
        self.db.commit()

    def list_games(self, game_type: str | None = None, limit: int = 50) -> list[dict]:
        """按**游戏分类**列牌局 —— 回溯入口 ✓

        三个游戏(掼蛋/斗地主/麻将)共用一张表, 靠 game_type 分流 ✓
        """
        sql = ("SELECT gid, game_type, started_at, ended_at, seat, ji_pai, result_json"
               " FROM deal")
        args: list = []
        if game_type:
            sql += " WHERE game_type=?"
            args.append(game_type)
        sql += " ORDER BY started_at DESC LIMIT ?"
        args.append(limit)
        return [{"gid": r[0], "game_type": r[1], "started_at": r[2], "ended_at": r[3],
                 "seat": r[4], "ji_pai": r[5], "result": json.loads(r[6] or "{}")}
                for r in self.db.execute(sql, args)]

    def replay(self, gid: str) -> dict:
        """**整局回放包**(回溯用 ✓): 开局信息 + 全部出牌 + 牌池快照 + 决策 + 准确率"""
        d = self.db.execute(
            "SELECT gid, game_type, started_at, ended_at, seat, hand_json, ji_pai, result_json"
            " FROM deal WHERE gid=?", (gid,)).fetchone()
        if not d:
            return {}
        return {"gid": d[0], "game_type": d[1], "started_at": d[2], "ended_at": d[3],
                "seat": d[4], "hand": json.loads(d[5] or "[]"), "ji_pai": d[6],
                "result": json.loads(d[7] or "{}"),
                "plays": self.plays_of(gid), "remains": self.remains_of(gid),
                "decisions": self.decisions_of(gid), "accuracy": self.accuracy(gid)}

    # ---------------- 读出口 (给前端 / 给"记忆") ----------------
    def remains_of(self, gid: str, last_only: bool = False) -> list[dict]:
        """牌池快照历史(前端"牌池"面板 / 回放用 ✓)"""
        sql = "SELECT ts, hand_n, counts_json FROM remains WHERE gid=? ORDER BY id"
        if last_only:
            sql += " DESC LIMIT 1"
        return [{"ts": r[0], "hand_n": r[1], "counts": json.loads(r[2] or "{}")}
                for r in self.db.execute(sql, (gid,))]

    def decisions_of(self, gid: str, limit: int = 50) -> list[dict]:
        """每次决策 + 是否对账一致(前端"推荐/准确率"用 ✓)"""
        cur = self.db.execute(
            "SELECT ts, hand_n, need_beat, cand_n, chosen_json, agree, note FROM decision"
            " WHERE gid=? ORDER BY id DESC LIMIT ?", (gid, limit))
        return [{"ts": r[0], "hand_n": r[1], "need_beat": bool(r[2]), "cand_n": r[3],
                 "chosen": json.loads(r[4] or "[]"), "agree": r[5], "note": r[6]}
                for r in cur.fetchall()]

    def set_host_intent(self, on: bool) -> None:
        """只记"我想开/关托管"的意图 ✓ 真正执行的是现有托管循环(它来读 ✓)"""
        self.db.execute("INSERT OR REPLACE INTO control(k, v, ts) VALUES('host',?,?)",
                        ("1" if on else "0", time.time()))
        self.db.commit()

    def host_intent(self) -> bool:
        row = self.db.execute("SELECT v FROM control WHERE k='host'").fetchone()
        return bool(row and row[0] == "1")

    def recent_deals(self, limit: int = 20) -> list[dict]:
        cur = self.db.execute(
            "SELECT gid, ts, seat, hand_json, ji_pai FROM deal ORDER BY ts DESC LIMIT ?", (limit,))
        return [{"gid": r[0], "ts": r[1], "seat": r[2], "hand": json.loads(r[3] or "[]"),
                 "ji_pai": r[4]} for r in cur.fetchall()]

    def plays_of(self, gid: str) -> list[dict]:
        cur = self.db.execute(
            "SELECT seq, ts, seat, mine, cards_json, hand_left, kind FROM play"
            " WHERE gid=? ORDER BY seq", (gid,))
        return [{"seq": r[0], "ts": r[1], "seat": r[2], "mine": bool(r[3]),
                 "cards": json.loads(r[4] or "[]"), "hand_left": r[5], "kind": r[6]}
                for r in cur.fetchall()]

    def accuracy(self, gid: str | None = None) -> dict:
        """操作准确率: 只算**我出的**、且已对账过的 ✓ (身份级准确率口径 ✓)"""
        sql = ("SELECT COUNT(*), SUM(agree), SUM(agree IS NULL) FROM decision"
               " WHERE 1=1")
        args: list = []
        if gid:
            sql += " AND gid=?"
            args.append(gid)
        n, ok, unknown = self.db.execute(sql, args).fetchone()
        decided = (n or 0) - (unknown or 0)
        return {"n": n or 0, "verified": decided, "agree": ok or 0,
                "accuracy": (ok / decided) if decided else None}

    def close(self) -> None:
        self.db.close()


def _cards_json(cards) -> str:
    """牌 → JSON。只做**格式转换**, 不解析牌型 ✗ (守住"只收不发" ✓)"""
    if cards is None:
        return "[]"
    out = []
    for c in cards:
        if isinstance(c, dict):
            out.append({k: c.get(k) for k in ("zhi", "hua") if k in c})
        else:
            out.append({"zhi": getattr(c, "zhi", None), "hua": getattr(c, "hua", None)})
    return json.dumps(out, ensure_ascii=False)

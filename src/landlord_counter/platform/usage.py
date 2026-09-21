"""AI 算力计量(底座计费的输入)。

产品背景(用户 2026-09-16 补充):
  主应用 = 云 OS 底座(登录 / Token 资产账户 / 充值扣费 / 云实例 / 生命周期 / **统一埋点计费**)
    → **计费主体是底座**; 所有 Token 交易、余额、订单都在底座。
  伴随应用 = 棋牌业务包(斗地主 / 掼蛋 + AI 记牌 + 托管, 完整业务 APK)
    → AI 算力消耗**由伴随应用上报到底座**, 底座扣减用户 Token。

因此本模块只做一件事: **记"消耗了多少"**, 不带价格(定价在底座)。
  伴随包每消耗一次算力 → 记一条计量事件 → 批量上报底座 → 底座按自己的价目表扣 Token。

计量口径(与底座对齐时改 KINDS 即可):
  vlm_read      视觉读牌调用(次)   —— 每次调 VLM 记 1(识别是本项目最大算力项)
  rl_infer      RL 决策推理(次)
  decide        决策(次)          —— 启发式/规则决策
  vision_frame  视觉处理帧(帧)     —— 可选: 只看变化的帧
  proxy_minute  托管时长(分钟)     —— 可选: 按分钟计费

★★ 2026-09-21(用户): "csv 和 json 之类, 受数据的全部换成从 sql 拿, 然后全删" ✗
   ⇒ 存储从 `data/usage/usage-<YYYYMMDD>.jsonl` 改成 **sqlite: data/usage.db(表 usage)** ✓
     顺带修掉旧写法的一个真 bug: 旧 seq 是**每进程从 1 重数**的 ✗ ⇒ 跨进程会重号,
     上报"取 seq > N"就会漏/重 ✗ ⇒ 现在 seq 一律用 sqlite 自增 id(全局单调 ✓)

上报: pending() 取未上报批次 → 上报底座 → ack(batch) 标记已上报(幂等: 重发不重复扣费)
"""
from __future__ import annotations

import json
import os
import sqlite3
import time
from dataclasses import dataclass, field

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
USAGE_DB = os.getenv("USAGE_DB", os.path.join(ROOT, "data", "usage.db"))

KINDS = ("vlm_read", "rl_infer", "decide", "vision_frame", "proxy_minute")

_DDL = """CREATE TABLE IF NOT EXISTS usage(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts REAL NOT NULL,
  kind TEXT NOT NULL,
  amount REAL NOT NULL DEFAULT 1,
  game TEXT, device TEXT, user_id TEXT, meta TEXT,
  reported INTEGER NOT NULL DEFAULT 0,
  reported_at REAL
)"""


def _today() -> str:
    return time.strftime("%Y%m%d")


def _con() -> sqlite3.Connection:
    d = os.path.dirname(USAGE_DB)
    if d:
        os.makedirs(d, exist_ok=True)
    con = sqlite3.connect(USAGE_DB, check_same_thread=False, timeout=5)
    con.execute(_DDL)
    return con


def _row_to_ev(r) -> dict:
    ev = {"t": r[1], "seq": r[0], "kind": r[2], "amount": r[3], "game": r[4],
          "device": r[5], "user": r[6] or "", "reported": bool(r[8])}
    if r[7]:
        try:
            ev["meta"] = json.loads(r[7])
        except Exception:  # noqa: BLE001
            pass
    if r[9]:
        ev["reported_at"] = r[9]
    return ev


_COLS = "id, ts, kind, amount, game, device, user_id, meta, reported, reported_at"


@dataclass
class UsageMeter:
    """AI 算力计量器: 记事件 / 取待上报批次 / 对账汇总。"""

    game: str = "guandan"
    device: str = os.getenv("DEVICE_ID", "cloudphone-1")
    user: str = os.getenv("USER_ID", "")          # 底座下发(上报时用)
    _buf: list = field(default_factory=list)

    # ---------------- 记一笔 ----------------
    def record(self, kind: str, amount: float = 1, **meta) -> dict:
        """记一次算力消耗(不带价格)。amount 缺省 1(次)。"""
        ev = {"t": round(time.time(), 3), "kind": kind, "amount": amount,
              "game": self.game, "device": self.device, "user": self.user,
              "reported": False}
        if meta:
            ev["meta"] = meta
        try:
            con = _con()
            cur = con.execute(
                "INSERT INTO usage(ts, kind, amount, game, device, user_id, meta, reported) "
                "VALUES(?,?,?,?,?,?,?,0)",
                (ev["t"], kind, float(amount), self.game, self.device, self.user,
                 json.dumps(meta, ensure_ascii=False) if meta else None))
            con.commit()
            ev["seq"] = int(cur.lastrowid or 0)   # ★ seq = sqlite 自增 id(全局单调 ✓)
            con.close()
        except Exception:                       # noqa: BLE001
            ev["seq"] = 0                        # 记不上也不许影响牌局 ✓
        self._buf.append(ev)
        return ev

    # 便捷方法
    def vlm_read(self, **m) -> dict:
        return self.record("vlm_read", 1, **m)

    def rl_infer(self, **m) -> dict:
        return self.record("rl_infer", 1, **m)

    def decide(self, **m) -> dict:
        return self.record("decide", 1, **m)

    def proxy_minutes(self, minutes: float, **m) -> dict:
        return self.record("proxy_minute", round(minutes, 3), **m)

    # ---------------- 上报(伴随包 → 底座) ----------------
    def pending(self, since_seq: int = 0) -> list:
        """取未上报事件(seq > since_seq)。伴随包上报后调用 ack()。"""
        try:
            con = _con()
            rows = con.execute(
                f"SELECT {_COLS} FROM usage WHERE reported=0 AND id > ? ORDER BY id",
                (int(since_seq),)).fetchall()
            con.close()
        except Exception:                       # noqa: BLE001
            return []
        return [_row_to_ev(r) for r in rows]

    def batch(self) -> dict:
        """打包一批待上报(底座侧按 batch_id 幂等)。"""
        evs = self.pending()
        bid = f"{self.device}-{int(time.time())}-{len(evs)}"
        return {"batch_id": bid, "device": self.device, "user": self.user,
                "count": len(evs), "by_kind": self.count_by_kind(evs), "events": evs}

    def ack(self, batch: dict) -> int:
        """底座确认收到 → 标记已上报(幂等)。"""
        ids = [int(e["seq"]) for e in batch.get("events", []) if e.get("seq")]
        if not ids:
            return 0
        try:
            con = _con()
            q = ",".join("?" * len(ids))
            cur = con.execute(
                f"UPDATE usage SET reported=1, reported_at=? WHERE reported=0 AND id IN ({q})",
                [round(time.time(), 3), *ids])
            con.commit()
            n = int(cur.rowcount or 0)
            con.close()
            return n
        except Exception:                       # noqa: BLE001
            return 0

    # ---------------- 对账 ----------------
    @staticmethod
    def count_by_kind(events: list) -> dict:
        out: dict = {}
        for e in events:
            k = e.get("kind", "?")
            out[k] = round(out.get(k, 0) + float(e.get("amount", 0)), 3)
        return out

    def summary(self, since: float | None = None) -> dict:
        sql = f"SELECT {_COLS} FROM usage"
        args: list = []
        if since is not None:
            sql += " WHERE ts >= ?"
            args.append(float(since))
        try:
            con = _con()
            evs = [_row_to_ev(r) for r in con.execute(sql, args).fetchall()]
            con.close()
        except Exception:                       # noqa: BLE001
            evs = []
        pend = [e for e in evs if not e.get("reported")]
        return {"events": len(evs), "by_kind": self.count_by_kind(evs),
                "unreported": len(pend), "unreported_by_kind": self.count_by_kind(pend),
                "user": self.user, "device": self.device, "game": self.game}

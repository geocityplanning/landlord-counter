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

落盘: data/usage/usage-<YYYYMMDD>.jsonl(按天分文件, 便于对账)
上报: pending() 取未上报批次 → 上报底座 → ack(batch) 标记已上报(幂等: 重发不重复扣费)
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
USAGE_DIR = os.getenv("USAGE_DATA_DIR", os.path.join(ROOT, "data", "usage"))

KINDS = ("vlm_read", "rl_infer", "decide", "vision_frame", "proxy_minute")


def _today() -> str:
    return time.strftime("%Y%m%d")


@dataclass
class UsageMeter:
    """AI 算力计量器: 记事件 / 取待上报批次 / 对账汇总。"""

    game: str = "guandan"
    device: str = os.getenv("DEVICE_ID", "cloudphone-1")
    user: str = os.getenv("USER_ID", "")          # 底座下发(上报时用)
    path: str = ""
    _n: int = 0
    _buf: list = field(default_factory=list)

    def __post_init__(self) -> None:
        os.makedirs(USAGE_DIR, exist_ok=True)
        if not self.path:
            self.path = os.path.join(USAGE_DIR, f"usage-{_today()}.jsonl")

    # ---------------- 记一笔 ----------------
    def record(self, kind: str, amount: float = 1, **meta) -> dict:
        """记一次算力消耗(不带价格)。amount 缺省 1(次)。"""
        self._n += 1
        ev = {"t": round(time.time(), 3), "seq": self._n, "kind": kind,
              "amount": amount, "game": self.game, "device": self.device,
              "user": self.user, "reported": False}
        if meta:
            ev["meta"] = meta
        try:
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(json.dumps(ev, ensure_ascii=False) + "\n")
        except Exception:                          # noqa: BLE001
            pass
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

    def _files(self) -> list:
        """要读的文件: 目录内按天分文件 + 显式 path(若在目录外)。"""
        out = []
        if os.path.isdir(USAGE_DIR):
            out += [os.path.join(USAGE_DIR, f) for f in sorted(os.listdir(USAGE_DIR))
                    if f.endswith(".jsonl")]
        if self.path and os.path.exists(self.path) and self.path not in out:
            out.append(self.path)
        return out

    # ---------------- 上报(伴随包 → 底座) ----------------
    def pending(self, since_seq: int = 0) -> list:
        """取未上报事件(seq > since_seq)。伴随包上报后调用 ack()。"""
        out = []
        for fn in self._files():
            with open(fn, encoding="utf-8") as f:
                for line in f:
                    try:
                        ev = json.loads(line)
                    except Exception:              # noqa: BLE001
                        continue
                    if not ev.get("reported") and int(ev.get("seq", 0)) > since_seq:
                        out.append(ev)
        return out

    def batch(self) -> dict:
        """打包一批待上报(底座侧按 batch_id 幂等)。"""
        evs = self.pending()
        bid = f"{self.device}-{int(time.time())}-{len(evs)}"
        return {"batch_id": bid, "device": self.device, "user": self.user,
                "count": len(evs), "by_kind": self.count_by_kind(evs), "events": evs}

    def ack(self, batch: dict) -> int:
        """底座确认收到 → 标记已上报(重写当天文件; 幂等)。"""
        ids = {(e.get("t"), e.get("seq")) for e in batch.get("events", [])}
        if not ids:
            return 0
        n = 0
        for p in self._files():
            rows, changed = [], False
            with open(p, encoding="utf-8") as f:
                for line in f:
                    try:
                        ev = json.loads(line)
                    except Exception:              # noqa: BLE001
                        rows.append(line)
                        continue
                    if (ev.get("t"), ev.get("seq")) in ids and not ev.get("reported"):
                        ev["reported"] = True
                        ev["reported_at"] = round(time.time(), 3)
                        changed = True
                        n += 1
                    rows.append(json.dumps(ev, ensure_ascii=False) + "\n")
            if changed:
                with open(p, "w", encoding="utf-8") as f:
                    f.writelines(rows)
        return n

    # ---------------- 对账 ----------------
    @staticmethod
    def count_by_kind(events: list) -> dict:
        out: dict = {}
        for e in events:
            k = e.get("kind", "?")
            out[k] = round(out.get(k, 0) + float(e.get("amount", 0)), 3)
        return out

    def summary(self, since: float | None = None) -> dict:
        evs = []
        for fn in self._files():
            with open(fn, encoding="utf-8") as f:
                for line in f:
                    try:
                        ev = json.loads(line)
                    except Exception:              # noqa: BLE001
                        continue
                    if since is None or float(ev.get("t", 0)) >= since:
                        evs.append(ev)
        pend = [e for e in evs if not e.get("reported")]
        return {"events": len(evs), "by_kind": self.count_by_kind(evs),
                "unreported": len(pend), "unreported_by_kind": self.count_by_kind(pend),
                "user": self.user, "device": self.device, "game": self.game}

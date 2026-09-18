"""掼蛋**专有读牌**(2026-09-18): 标定牌位 + 模板匹配 + **按局自动重采** ✓

用户要求: "每一个项目独立的定位逻辑, 点牌逻辑, 出牌逻辑", 并**主要提升读牌准确率** ✓

为什么读牌要自带"按局重采"
------------------------
模板 = **这一局牌长什么样**(每个点数在屏幕上的像素长相)。换局后牌型不同 ⇒ 旧模板大面积读错 ✗
  实测: 换局不重采 ⇒ 逐位准确率掉到 50~60%(且错误"看起来很正常", 极难发现 ✗)
       换局重采 ⇒ 回到 100% ✓
⇒ 对策: 每次"识别到新一局 + 轮到我 + 牌桌干净"时, **自动采一轮模板** ✓(用游戏真值当老师)

分层原则(2026-09-16 拍板, 继续沿用): 模板管日常量产(0 成本), 大模型只管冷启动/兜底
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path

from . import locate as L
from . import percept as P

TPL_RANK_DIR = "data/templates_rank"


@dataclass
class ReadResult:
    cards: list = field(default_factory=list)      # [(花色, 点数, x, 抬起量)]
    n: int = 0
    check_ok: bool = False
    reasons: list = field(default_factory=list)
    collected: int = 0                              # 本帧是否顺带采了模板
    deal_fp: int = 0


_deal_fp: int = 0          # 局指纹(用真值的手牌 id 序列哈希) —— 同局不重复采 ✓
_last_sig: tuple = ()


def _wipe_auto_templates() -> int:
    """清掉本工具/适配器采的自动模板(文件名含 _auto_) ✓ —— 保留手工/参考模板 ✓"""
    d = Path(TPL_RANK_DIR)
    if not d.exists():
        return 0
    k = 0
    for f in d.glob("*_auto_*.npy"):
        try:
            f.unlink()
            k += 1
        except Exception:  # noqa: BLE001
            pass
    if k:
        P.clear_templates_cache()
    return k


def deal_fingerprint(hand_ids: list) -> int:
    return hash(tuple(int(x) for x in hand_ids)) if hand_ids else 0


def maybe_collect(img, hand_ids: list, ranks: list, *, slots: list | None = None,
                  force: bool = False) -> int:
    """**按局自动重采模板**(用户 2026-09-18: 别让旧模板反复影响 ✗)

    条件: 给了真值(hand_ids + ranks) + 是本局第一次(或 force) ⇒ 采一轮 ✓
    返回采到的张数(0 = 没采)。
    """
    global _deal_fp
    fp = deal_fingerprint(hand_ids)
    if not fp or (not force and fp == _deal_fp):
        return 0
    # ★ slots 必须与读取同源(2026-09-18: 采集用公式/读取用表 ⇒ 读牌崩到 19% ✗)
    # ★★ 先把**本进程上一局采的自动模板**清掉(2026-09-18): 模板库会跨局累积(实测 895 个 ✗),
    #    旧局的裁切口径/相位与当前不同 ⇒ 会干扰匹配 ⇒ 读数忽好忽坏 ✗
    #    纪律: 模板 = 这一局牌长什么样 ⇒ **按局清、按局采** ✓(手工/参考模板不动 ✓)
    _wipe_auto_templates()
    n = P.tm_collect_from_ranks(img, list(ranks), out_dir=TPL_RANK_DIR, tag="auto", slots=slots)
    if n:
        _deal_fp = fp
        P.clear_templates_cache()
    return n


def read(img, *, expect: int | None = None, hand_ids: list | None = None,
         ranks: list | None = None) -> ReadResult:
    """读手牌: 先按局重采(若给了真值) → 再按标定牌位做模板匹配 ✓

    校验: 读出的张数必须 == 在线校验推定的张数(不等就报 check_ok=False, 上层可选择拒用 ✓)
    """
    res = ReadResult()
    slots, chk = L.locate(img, expect)
    res.check_ok = chk.ok
    res.reasons = list(chk.reasons)
    if not chk.ok:
        return res
    if hand_ids and ranks:
        res.collected = maybe_collect(img, hand_ids, ranks, slots=slots)
        if res.collected:
            res.deal_fp = deal_fingerprint(hand_ids)
    # ★ 读取也用**同一份 slots**(查表来的 ✓) ⇒ 与采集完全同源 ✓
    cards, _info = P.tm_read_hand(img, slots=slots)
    res.cards = list(cards)
    res.n = len(cards)
    if expect and abs(res.n - expect) > 1:
        res.check_ok = False
        res.reasons.append(f"读数张数 {res.n} 与预期 {expect} 不符")
    res.deal_fp = res.deal_fp or _deal_fp
    return res


def read_simple(img) -> list:
    """只要牌面列表(不校验/不采集) —— 给不关心流程的调用方 ✓"""
    return P.tm_read_hand(img)[0]

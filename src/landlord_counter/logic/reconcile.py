"""信念校正（reconcile）：把 VLM 观测修正为可信手牌。

识别层每帧 ~88% 正确且错误有固定模式（对子合并、幻觉单张）。
本模块用四把约束刀把观测拉回物理可能的手牌：

  1. 硬约束  每点数 ≤ 上限(普通牌4、王1)；超出即幻觉 → 删
  2. 单调性  一局内(除抢地主补底那一刻)手牌只会减少 → 相对上一信念只减不加
  3. 数量锚  手牌总数必须 = expected(17/20) → 删多了补、加多了删
  4. 置信回填 补牌优先补"上一信念里有、本帧没读出"的点数(对子漏读的恢复)

纯函数、无 I/O，可离线合成测试。
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field


def rank_caps() -> dict[str, int]:
    caps = {r: 4 for r in ["3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A", "2"]}
    caps["BJ"] = 1
    caps["RJ"] = 1
    return caps


@dataclass
class ReconcileReport:
    """校正过程记录（供日志/调参）。"""

    raw: list[str] = field(default_factory=list)          # VLM 原始读数
    belief: Counter = field(default_factory=Counter)      # 校正后信念
    dropped: Counter = field(default_factory=Counter)     # 因约束删掉的牌
    added_back: Counter = field(default_factory=Counter)  # 数量回填补回的牌
    notes: list[str] = field(default_factory=list)


def _total(c: Counter) -> int:
    return sum(c.values())


def reconcile_hand(
    obs: list[str],
    prev: Counter | None = None,
    *,
    expected: int = 17,
    gain: bool = False,
    caps: dict[str, int] | None = None,
) -> tuple[Counter, ReconcileReport]:
    """把一次 VLM 手牌观测校正成可信信念。

    Args:
        obs:      VLM 读出的点数列表（可含重复）
        prev:     上一帧校正后的信念；None = 本局第一次观测
        expected: 手牌总数（农民17 / 地主20）
        gain:     本帧是否允许手牌增加（仅"抢到地主补 3 张底牌"那个时刻）
        caps:     每点数上限（默认 4 张 + 王各 1）
    """
    caps = caps or rank_caps()
    rep = ReconcileReport(raw=list(obs))
    b: Counter = Counter(obs)

    # ---- 刀1: 硬约束(数量上限) ----
    for r, c in list(b.items()):
        mx = caps.get(r, 4)
        if c > mx:
            rep.dropped[r] += c - mx
            b[r] = mx
            rep.notes.append(f"超上限删{r}×{c - mx}")

    # ---- 刀2: 单调性(无 gain 时只减不加) ----
    if prev is not None and not gain:
        for r, c in list(b.items()):
            if c > prev.get(r, 0):
                rep.dropped[r] += c - prev[r]
                b[r] = prev[r]
                rep.notes.append(f"单调性删{r}×{c - prev[r]}")

    # ---- 刀3+4: 数量锚 + 置信回填 ----
    n = _total(b)
    if n < expected:
        short = expected - n
        # 优先从"上一信念有、本帧缺失"的点数补回（对子漏读场景）
        cand: list[tuple[str, int]] = []
        if prev is not None:
            cand += [(r, prev[r] - b[r]) for r in prev if prev[r] > b.get(r, 0)]
        # 仍不够再从牌堆里挑未超上限且最"常见"的点数（低期望，聊胜于无）
        seen = set(cand)
        for r in sorted(caps, key=lambda x: (caps[x], x)):
            if len(cand) >= short:
                break
            if r not in seen and b.get(r, 0) < caps[r]:
                cand.append((r, caps[r] - b.get(r, 0)))
        for r, avail in cand:
            if short <= 0:
                break
            take = min(avail, short)
            b[r] += take
            rep.added_back[r] += take
            short -= take
        if short > 0:
            rep.notes.append(f"缺{short}张无法回填(牌堆不足以解释)")
    elif n > expected:
        over = n - expected
        # 优先删"上一信念没有/超出的点数"(幻觉), 再删数量最多的
        order = sorted(
            b.keys(),
            key=lambda r: (
                0 if prev is not None and b[r] <= prev.get(r, 0) else 1,  # 幻觉优先删
                -b[r],
            ),
        )
        for r in order:
            if over <= 0:
                break
            cut = min(b[r], over)
            b[r] -= cut
            rep.dropped[r] += cut
            over -= cut

    # 清 0
    rep.belief = Counter({r: c for r, c in b.items() if c > 0})
    return rep.belief, rep


def vote_initial_hand(reads: list[list[str]], *, expected: int = 17) -> Counter:
    """发牌后手牌静止，连读 k 次做逐点数多数投票，建立高置信 prior。

    单卡正确率 p≈0.9 时，3 次投票后每张正确率 ≈ 0.9³+3·0.9²·0.1 ≈ 97%。
    """
    caps = rank_caps()
    agg: Counter = Counter()
    for obs in reads:
        agg.update(obs)
    b: Counter = Counter()
    for r in caps:
        k = max(1, len(reads))
        n_votes = agg.get(r, 0)
        # 多数票: 该点数出现次数 > k/2 才信它存在, 数量取 (出现次数的多数取整)
        if n_votes * 2 > k:
            b[r] = min(caps[r], round(n_votes / k))
    # 数量锚: 修到 expected（不足从"半数以上有票但被取整掉"的补；多了删最弱）
    n = sum(b.values())
    if n < expected:
        short = expected - n
        for r in sorted(b, key=lambda x: (b[x], x)):
            if short <= 0:
                break
            if b[r] < caps[r]:
                b[r] += 1
                short -= 1
    elif n > expected:
        over = n - expected
        for r in sorted(b, key=lambda x: b[x]):
            if over <= 0:
                break
            b[r] -= 1
            over -= 1
    return Counter({r: c for r, c in b.items() if c > 0})

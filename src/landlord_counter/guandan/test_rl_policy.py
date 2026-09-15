"""RL 决策适配器离线测试(不占真机, 不依赖游戏)。

验证:
 1) 预训练权重 strict 加载
 2) 状态编码 20 token 形状/归一化正确
 3) 候选→动作下标映射(含 pass)
 4) 推理: 在我们的合法候选里选出合法动作, 延迟可接受
"""
import sys
import time

sys.path.insert(0, "/project1/landlord-counter/src")

from landlord_counter.guandan import rules as R  # noqa: E402
from landlord_counter.guandan.rl_policy import (  # noqa: E402
    GTNet, NUM_ACTIONS, PASS_INDEX, RLPolicy, candidate_to_index, encode_tokens,
)


def C(zhi, hua=0, i=0):
    return R.Card(zhi, hua, i)


def test_load() -> None:
    net = GTNet()
    import torch
    sd = torch.load("/project1/landlord-counter/reference/guandan-rl/Bests/policy_value_net_1000.pt",
                    map_location="cpu")
    net.load_state_dict(sd, strict=True)
    n = sum(p.numel() for p in net.parameters())
    assert n == 453113, n
    print(f"✓ 权重加载(strict): 参数量 {n:,}")


def test_encode() -> None:
    hand = [C(5), C(7), C(7), C(2), C(16), C(15)]
    hist = [(0, R.identify([C(3), C(3)])), (1, R.identify([C(9)]))]
    toks = encode_tokens(hand, hist, [6, 5, 4, 3, 18], (1, R.identify([C(9)])), 2, 2)
    assert len(toks) == 20, len(toks)
    dims = [len(t) for t in toks]
    assert dims == [16] + [16] * 16 + [5] + [16] + [4], dims
    # 手牌 token: 15 计数 + 1 同花组数
    assert abs(toks[0][2] - 1 / 8) < 1e-6, toks[0]      # zhi=5 → 下标2 有 1 张
    assert abs(toks[0][4] - 2 / 8) < 1e-6, toks[0]      # 7 → 下标4 有 2 张
    assert abs(sum(toks[0][:15]) - 6 / 8) < 1e-6, toks[0]
    print(f"✓ 状态编码: 20 token, 维度 {dims[0]}/{dims[1]}/{dims[17]}/{dims[18]}/{dims[19]} ✓ 归一化正确")


def test_action_map() -> None:
    assert candidate_to_index(1, 1, 5) == 2                 # 单张5 → type1 段 + rank2
    assert candidate_to_index(2, 1, 7) == 15 + 4            # 对7
    assert candidate_to_index(10, 4, 9) == 72 + 6           # 4张炸9
    assert candidate_to_index(10, 6, 9) == 106 + 6          # 6张炸
    assert candidate_to_index(11, 5, 3) == 98               # 同花顺
    assert candidate_to_index(12, 4, 16) is None            # 天王炸不在其动作空间
    assert candidate_to_index(5, 6, 3) is None              # 6张顺子(他们只支持5张)
    print("✓ 候选→动作下标映射(含炸弹/同花顺/不可映射项)")


def test_inference() -> None:
    p = RLPolicy()
    # 构造: 手牌有单张+对子, 领出 → 候选 = 各单张/对子
    hand = [C(5), C(7), C(7), C(9)]
    cands = []
    for c in hand:
        g = R.identify([c])
        if not getattr(g, "is_invalid", False):
            cands.append(c)
    g = R.identify([C(7, 0, 1), C(7, 1, 2)])
    if not getattr(g, "is_invalid", False):
        cands.append([C(7, 0, 1), C(7, 1, 2)])
    t0 = time.time()
    pick, info = p.choose(cands, hand, [], [4, 4, 4, 4, 16], None, 0)
    dt = (time.time() - t0) * 1000
    assert info["mapped"] >= 3, info
    assert pick is None or pick in cands, pick
    print(f"✓ 推理: 候选{info['n_cand']}个(可映射{info['mapped']}) → 选择={'不出' if pick is None else pick}"
          f" | value={info['value']:.3f} | {dt:.1f}ms")
    # 必须跟牌的场景: 上家出对子7, 我方只有更大的对子9 → 掩码里只有这个+不出
    last = R.identify([C(7, 0), C(7, 1)])
    hand2 = [C(9, 0), C(9, 1), C(4)]
    cands2 = [[C(9, 0), C(9, 1)]]
    pick2, info2 = p.choose(cands2, hand2, [], [3, 4, 4, 3, 14], (3, last), 0)
    assert pick2 is None or pick2 == cands2[0]
    print(f"✓ 跟牌场景: 可映射 {info2['mapped']} → {'不出' if pick2 is None else '出对9'} (value={info2['value']:.3f})")


if __name__ == "__main__":
    test_load()
    test_encode()
    test_action_map()
    test_inference()
    print("\nRL 决策适配器: 4 组测试通过")

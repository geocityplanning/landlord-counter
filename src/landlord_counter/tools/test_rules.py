"""验证规则引擎：斗地主 + 掼蛋。

用法: uv run python -m landlord_counter.tools.test_rules
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from landlord_counter.logic.rules import DouDizhuRules, GuanDanRules, RULES_REGISTRY  # noqa: E402


def test_doudizhu():
    print("=" * 50)
    print("测试: 斗地主规则")
    rules = DouDizhuRules()
    deck = rules.build_deck()
    assert sum(deck.values()) == 54, f"斗地主应54张, got {sum(deck.values())}"

    ok, desc = rules.validate_play(["3", "3", "3", "3"])
    assert ok and "炸弹" in desc, f"4张3应是炸弹: {desc}"

    ok, desc = rules.validate_play(["BJ", "RJ"])
    assert ok and "王炸" in desc, f"大小王应是王炸: {desc}"

    ok, desc = rules.validate_play(["3", "4"])
    assert not ok, "3和4不能一起出(非顺子)"

    # 炸弹压单牌
    assert rules.beats(["9", "9", "9", "9"], ["A"]), "炸弹应能压A"
    # 王炸压炸弹
    assert rules.beats(["BJ", "RJ"], ["9", "9", "9", "9"]), "王炸应压炸弹"
    # 大单压小单
    assert rules.beats(["K"], ["5"]), "K应压5"
    assert not rules.beats(["5"], ["K"]), "5不应压K"
    print("✓ 斗地主规则全部通过")


def test_guandan():
    print("=" * 50)
    print("测试: 掼蛋规则")
    rules = GuanDanRules(level=2)
    deck = rules.build_deck()
    assert sum(deck.values()) == 108, f"掼蛋应108张, got {sum(deck.values())}"

    ok, desc = rules.validate_play(["2", "2", "2", "2", "2"])
    assert ok and "炸弹" in desc, f"5张2应是炸弹: {desc}"

    ok, desc = rules.validate_play(["3", "3", "3", "4", "4"])
    assert ok and "三带二" in desc, f"三带二应合法: {desc}"

    assert rules.beats(["9", "9", "9", "9", "9"], ["A"]), "5张9炸弹应压A"
    assert rules.beats(["2", "2", "2", "2"], ["K"]), "4张2应压K"

    # 两副牌应该有8张同点数
    assert deck["3"] == 8, f"掼蛋中3应有8张, got {deck['3']}"
    print("✓ 掼蛋规则全部通过")


def test_registry():
    print("=" * 50)
    print("测试: 规则注册表")
    assert "doudizhu" in RULES_REGISTRY
    assert "guandan" in RULES_REGISTRY
    rules = RULES_REGISTRY["guandan"]()
    print(f"✓ 注册表可用，当前规则: {[k for k in RULES_REGISTRY]}")
    print(f"  掼蛋参数: {rules.total_cards}张, {rules.num_players}人, 每人{rules.cards_per_player}张")


if __name__ == "__main__":
    test_doudizhu()
    test_guandan()
    test_registry()
    print("\n🎉 规则引擎全部验证通过！")

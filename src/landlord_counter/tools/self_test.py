"""自测：验证模板识别 + 记牌逻辑。

用法: uv run python -m landlord_counter.tools.self_test
"""
from __future__ import annotations

import sys
from pathlib import Path

import cv2
import numpy as np

# 确保 src 在路径中
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from landlord_counter.config import VisionConfig  # noqa: E402
from landlord_counter.logic.tracker import FULL_DECK, GameState  # noqa: E402
from landlord_counter.vision.card_recognizer import CardRecognizer  # noqa: E402


def test_recognition():
    """用模板拼一张手牌图，验证识别器能认出牌"""
    cfg = VisionConfig()
    rec = CardRecognizer(cfg)
    assert rec.template_available(), "模板未生成"

    # 拼一张手牌图：3, 7, K, A, 2
    ranks = ["3", "7", "K", "A", "2"]
    tpls = [cv2.imread(str(cfg.template_dir / f"{r}.png")) for r in ranks]
    h = max(t.shape[0] for t in tpls)
    w = sum(t.shape[1] for t in tpls) + 10
    canvas = np.full((h, w, 3), 255, dtype=np.uint8)
    x = 0
    for t in tpls:
        canvas[0 : t.shape[0], x : x + t.shape[1]] = t
        x += t.shape[1] + 2

    result = rec.recognize_hand(canvas)
    print(f"识别结果: {result}")
    assert sorted(result) == sorted(ranks), f"识别不匹配: {result} vs {ranks}"
    print("✓ 模板识别测试通过")
    return True


def test_tracker():
    """验证记牌逻辑"""
    s = GameState()
    assert sum(FULL_DECK.values()) == 54, "牌堆应为54张"
    # 自己出 3,3,4
    s.record_play("self", ["3", "3", "4"])
    assert s.remaining["3"] == 2, "出掉两张3后剩余应为2"
    assert s.remaining["4"] == 3
    assert s.remaining["2"] == 4
    # 记录手牌
    s.record_my_hand(["5", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A", "2", "2", "BJ", "RJ", "3", "4"])
    s.record_play("left", ["6", "6"])
    assert s.remaining["6"] == 2
    print("✓ 记牌逻辑测试通过")
    print(s.summary())
    return True


if __name__ == "__main__":
    ok1 = test_recognition()
    ok2 = test_tracker()
    print("\n" + ("🎉 全部测试通过!" if ok1 and ok2 else "❌ 有测试失败"))

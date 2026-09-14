"""麻将适配器离线单测(假 a11y + 假设备, 不占真机)。

覆盖: 轮次判据(mod 3 规律)、操作按钮决策(和了/跳过)、出手执行(ENTER 主路径 + 点击兜底)、
按钮点击回执。
"""
from __future__ import annotations

import sys
import types

sys.path.insert(0, "src")

from landlord_counter.platform.games.mahjong_adapter import MahjongAdapter  # noqa: E402
from landlord_counter.platform.types import Action  # noqa: E402


class FakeNode:
    def __init__(self, text, x, y, cls="android.widget.Button"):
        self.text = text
        self.center = (x, y)
        self.cls = cls
        self.box = (x - 20, y - 20, x + 20, y + 20)


class FakeA11y:
    """用可变状态模拟页面: hand/actions 列表 + 点按回调。"""

    def __init__(self) -> None:
        self.hand = []
        self.actions = []
        self.taps = []

    def dump(self, force=False):  # noqa: ARG002
        nodes = []
        for i, t in enumerate(self.hand):
            nodes.append(FakeNode(t, 126 + i * 36, 760))
        for i, t in enumerate(self.actions):
            nodes.append(FakeNode(t, 200 + i * 150, 1120))
        return nodes

    def button(self, text):
        for n in self.dump():
            if n.text.strip() == text:
                return n
        return None


class FakeDevice:
    def __init__(self, a11y: FakeA11y) -> None:
        self.a11y = a11y
        self.serial = "fake"
        self.enters = 0
        self.taps = []

    def tap(self, x, y, wait=0.0):  # noqa: ARG002
        self.taps.append((x, y))
        # 模拟"点手牌=出手": 去掉最后一张并补一张(张数 14→13)
        if self.a11y.hand:
            if y < 900 and len(self.a11y.hand) % 3 == 2:
                self.a11y.hand = self.a11y.hand[:-1] + ["ツモ"]
                return
            if y >= 900 and self.a11y.actions:   # 点操作按钮 → 按钮消失
                self.a11y.actions = []

    def shell(self, *args):
        if args[:2] == ("input", "keyevent"):
            self.enters += 1
        return types.SimpleNamespace(returncode=0, stdout="", stderr="")


def build(hand, actions=()):
    a = FakeA11y()
    a.hand = list(hand)
    a.actions = list(actions)
    d = FakeDevice(a)
    ad = MahjongAdapter()
    ad.attach(d)
    ad.a11y = a          # attach 会重建 A11y, 覆盖回假实现
    return ad, a, d  # type: ignore[return-value]


def test_turn_rule() -> None:
    """该我出手: 张数 ≡ 2 (mod 3)；等待中 ≡ 1 (mod 3)。副露后手牌变少也要正确。"""
    for n, expect in ((14, True), (13, False), (11, True), (10, False), (8, True), (7, False), (2, True), (1, False)):
        ad, a, _ = build(["牌"] * n)
        obs = ad.sense(None)
        assert obs.my_turn is expect, f"{n} 张应 my_turn={expect}, 实际 {obs.my_turn}"
    print("✓ 轮次判据(mod 3): 8 组用例全过")


def test_decide() -> None:
    """有和了 → 和; 有其它提示 → 取消; 无提示 → 打最后一张。"""
    ad, _, _ = build(["牌"] * 14, ["ツモ"])
    assert ad.decide(ad.sense(None)).meta["text"] == "ツモ"
    ad, _, _ = build(["牌"] * 14, ["チー"])
    assert ad.decide(ad.sense(None)).meta["text"] == "キャンセル"
    ad, _, _ = build(["牌"] * 14)
    act = ad.decide(ad.sense(None))
    assert act.kind == "play" and act.combo == 13, act
    print("✓ 决策: 和了优先 / 否则跳过提示 / 否则ツモ切り")


def test_execute_actions() -> None:
    """点操作按钮: 按钮消失=成功; 不消失=失败。"""
    ad, a, d = build(["牌"] * 14, ["キャンセル"])
    r = ad.execute(Action("act", meta={"text": "キャンセル"}), ad.sense(None))
    assert r.ok and "キャンセル" in r.detail, r
    assert d.taps and not a.actions
    # 点不掉的按钮 → 失败
    ad, a, d = build(["牌"] * 14, ["キャンセル"])
    a.actions = ["キャンセル"]
    d.tap = lambda x, y, wait=0.0: None       # 点了没反应
    r = ad.execute(Action("act", meta={"text": "キャンセル"}), ad.sense(None))
    assert not r.ok, r
    print("✓ 执行(操作按钮): 消失=成功 / 不消失=失败")


def test_execute_play() -> None:
    """出手: **点击为主路径**; 点不动时 ENTER 兜底。"""
    # 主路径: 点击生效(假设备点手牌区=出手)
    ad, a, d = build(["牌"] * 14)
    r = ad.execute(Action("play", combo=13), ad.sense(None))
    assert r.ok and "打出" in r.detail, r
    assert d.enters == 0, "主路径不该用 ENTER"
    # 点击无效 → ENTER 兜底
    ad, a, d = build(["牌"] * 14)
    d.tap = lambda x, y, wait=0.0: None          # 点不动
    orig_shell = d.shell

    def shell_enter(*args):
        if args[:2] == ("input", "keyevent"):
            a.hand = a.hand[:-1] + ["ツモ"]      # 模拟 ENTER 出手
        return orig_shell(*args)

    d.shell = shell_enter
    r = ad.execute(Action("play", combo=13), ad.sense(None))
    assert r.ok and "ENTER 兜底" in r.detail, r
    print("✓ 执行(出手): 点击主路径 + ENTER 兜底 均通过")


def test_no_hand() -> None:
    ad, _, _ = build([])
    assert ad.decide(ad.sense(None)).kind == "none"
    r = ad.execute(Action("play", combo=0), ad.sense(None))
    assert not r.ok and "读不到手牌" in r.detail
    print("✓ 空手牌: 不动作且不误报成功")


if __name__ == "__main__":
    test_turn_rule()
    test_decide()
    test_execute_actions()
    test_execute_play()
    test_no_hand()
    print("\n麻将适配器单测: 5 组全绿")

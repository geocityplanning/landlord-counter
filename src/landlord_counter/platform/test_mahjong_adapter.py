"""麻将适配器离线单测(假 a11y + 假设备, 不占真机)。

覆盖: 轮次判据(mod 3 规律)、提示阶段(手牌节点消失)、决策(和了/跳过/ツモ切り)、
执行(键盘通道为主 + 点按兜底)、空手牌保护。

关键环境事实(实测, 决定了实现):
- Bromite(Chromium) 下手牌节点是 **Image** 类(Focus 下是 Button) ⇒ 不能依赖控件类
- 本容器里 **touch 对页面无效**(点击后牌面/牌数零变化) ⇒ 只能走键盘(方向键+Enter)
"""
from __future__ import annotations

import sys
import types

sys.path.insert(0, "src")

from landlord_counter.platform.games.mahjong_adapter import ACTION_TEXTS, MahjongAdapter  # noqa: E402
from landlord_counter.platform.types import Action  # noqa: E402

TILES = ["イーワン", "リャンワン", "サンワン", "スーワン", "ウーワン", "ローワン",
         "チーワン", "パーワン", "キューワン", "イーピン", "リャンピン", "サンピン",
         "スーピン", "トン"]


def tile(i: int) -> str:
    return TILES[i % len(TILES)]


class FakeNode:
    def __init__(self, text, x, y, cls="android.widget.Image"):
        self.text = text
        self.center = (x, y)
        self.cls = cls
        self.box = (x - 20, y - 20, x + 20, y + 20)


class FakeA11y:
    def __init__(self) -> None:
        self.hand: list[str] = []
        self.actions: list[str] = []
        self.wall = 70

    def dump(self, force=False):  # noqa: ARG002
        nodes = [FakeNode(t, 126 + i * 36, 763) for i, t in enumerate(self.hand)]
        nodes += [FakeNode(t, 200 + i * 150, 709, cls="android.widget.Button")
                  for i, t in enumerate(self.actions)]
        nodes += [FakeNode("牌数:", 450, 466, cls="android.widget.View"),
                  FakeNode(str(self.wall), 474, 466, cls="android.widget.View")]
        return nodes

    def button(self, text):
        for n in self.dump():
            if (n.text or "").strip() == text:
                return n
        return None


class FakeDevice:
    """touch 对牌面无效(模拟真机); 键盘方向键+Enter 才出手。"""

    def __init__(self, a11y: FakeA11y) -> None:
        self.a11y = a11y
        self.arrows = 0
        self.enters = 0
        self.taps: list[tuple[int, int]] = []
        self.keyboard_dead = False      # True: 模拟键盘也无效(测点按兜底)
        self.touch_dead = True          # 默认: 本容器实测触控对页面无效

    def tap(self, x, y, wait=0.0):  # noqa: ARG002
        self.taps.append((x, y))
        for n in self.a11y.dump():
            t = (n.text or "").strip()
            if t in ACTION_TEXTS and abs(n.center[0] - x) < 60 and abs(n.center[1] - y) < 60:
                self.a11y.actions = [a for a in self.a11y.actions if a != t]
                return
        if self.touch_dead:
            return
        if self.a11y.hand:                      # 触控可用的环境: 点牌=弃牌
            self._discard()

    def shell(self, *args):
        if args[:2] == ("input", "keyevent"):
            code = str(args[2])
            if code == "22":
                self.arrows += 1
            elif code == "66":
                self.enters += 1
                if self.keyboard_dead or self.arrows == 0:
                    return types.SimpleNamespace(returncode=0, stdout="", stderr="")
                self._discard()
        return types.SimpleNamespace(returncode=0, stdout="", stderr="")

    def _discard(self) -> None:
        if not self.a11y.hand:
            return
        h = list(self.a11y.hand)
        del h[-1]                                # 弃最后一张(ツモ切り)
        self.a11y.hand = h + [tile(self.a11y.wall)]   # 摸一张新的
        self.a11y.wall -= 1


def build(hand, actions=()):
    a = FakeA11y()
    a.hand = list(hand)
    a.actions = list(actions)
    d = FakeDevice(a)
    ad = MahjongAdapter()
    ad.attach(d)
    ad.a11y = a  # type: ignore[assignment]     # attach 会重建 A11y → 覆盖回假实现
    return ad, a, d                             # type: ignore[return-value]


def test_turn_rule() -> None:
    """该我出手: 张数 ≡ 2 (mod 3)；等待中 ≡ 1 (mod 3)。副露后手牌变少也要正确。"""
    for n, expect in ((14, True), (13, False), (11, True), (10, False), (8, True), (7, False), (2, True), (1, False)):
        ad, _, _ = build([tile(i) for i in range(n)])
        obs = ad.sense(None)
        assert obs.my_turn is expect, f"{n} 张应 my_turn={expect}, 实际 {obs.my_turn}"
    print("✓ 轮次判据(mod 3): 8 组用例全过")


def test_prompt_without_hand() -> None:
    """提示阶段(手牌节点消失)也必须判为"该我应答", 否则永久卡住。"""
    ad, a, d = build([], ["チー", "キャンセル"])
    obs = ad.sense(None)
    assert obs.my_turn is True, obs
    assert obs.extra["phase"] == "prompt" and "チー" in obs.extra["actions"]
    assert ad.execute(ad.decide(obs), obs).ok
    print("✓ 提示阶段(无手牌): 判为待应答并成功应答")


def test_decide() -> None:
    """有和了 → 和; 有其它提示 → 取消; 无提示 → 打最后一张(ツモ切り)。"""
    ad, _, _ = build([tile(i) for i in range(14)], ["ツモ"])
    assert ad.decide(ad.sense(None)).meta["text"] == "ツモ"
    ad, _, _ = build([tile(i) for i in range(14)], ["チー"])
    assert ad.decide(ad.sense(None)).meta["text"] == "キャンセル"
    ad, _, _ = build([tile(i) for i in range(14)])
    act = ad.decide(ad.sense(None))
    assert act.kind == "play" and act.combo == 13, act
    print("✓ 决策: 和了优先 / 否则跳过提示 / 否则ツモ切り")


def test_execute_play_keyboard() -> None:
    """出手走键盘通道: 必须按方向键(选择器夹到最后一张)再 Enter; 牌数下降即为成功。"""
    ad, a, d = build([tile(i) for i in range(14)])
    wall0 = d.a11y.wall
    r = ad.execute(Action("play", combo=13), ad.sense(None))
    assert r.ok and "键盘出手" in r.detail, r
    assert d.arrows >= len(a.hand), f"应先把选择器夹到末张, 实际 arrows={d.arrows}"
    assert d.a11y.wall < wall0, "牌数应下降"
    print(f"✓ 执行(出手/键盘): arrows={d.arrows} enters={d.enters} → {r.detail}")


def test_execute_play_tap_fallback() -> None:
    """键盘通道完全无效时, 点按兜底仍要能出手(某些环境触控可用)。"""
    ad, a, d = build([tile(i) for i in range(14)])
    d.keyboard_dead = True
    d.touch_dead = False                      # 该环境触控可用
    r = ad.execute(Action("play", combo=13), ad.sense(None))
    assert r.ok and "点击兜底" in r.detail, r
    print("✓ 执行(出手/点按兜底): 通过")


def test_no_hand() -> None:
    ad, _, _ = build([])
    assert ad.decide(ad.sense(None)).kind == "none"
    r = ad.execute(Action("play", combo=0), ad.sense(None))
    assert not r.ok and "读不到手牌" in r.detail
    print("✓ 空手牌: 不动作且不误报成功")


if __name__ == "__main__":
    test_turn_rule()
    test_prompt_without_hand()
    test_decide()
    test_execute_play_keyboard()
    test_execute_play_tap_fallback()
    test_no_hand()
    print("\n麻将适配器单测: 6 组全绿")

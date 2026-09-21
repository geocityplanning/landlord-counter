"""游戏本体 AI 的 Python 包装 —— **第二个"脑子"**(决策臂), 与 RL 平级 ✓

用户(2026-09-21):
  "将游戏的AI复制出来处理一下，放在和RL同样的地位，加同样的护栏那一套东西"
  "这样可以测出来一个东西: 如果自己跟自己打胜率远低于50%，那就是我们的代码里面有拖后腿的代码"

做法: `game_ai/{aiLogic.js,gameRules.js}` 是**原样复制**的游戏 AI ✓
      本模块用 node 起一个**常驻小进程**(game_ai_worker.js), 每次问一句答一句 ✓
      · 保真: 逻辑完全是游戏那份, 没有任何改写/翻译 ✓
      · 快:   常驻进程, 单次决策约 1ms ✓
职责边界(重要 ✓): 它**只回答"出哪几张牌"** ✓
      执行/护栏(代价过滤 · 领出兜底 · 出牌前自检 · 身份定位点选 · 真值对账)
      都在适配器里统一做 ⇒ 和 RL 臂走的是**同一条链** ✓
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
from dataclasses import dataclass, field
from typing import Any

_WORKER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "game_ai_worker.js")

PROC: subprocess.Popen | None = None
LOCK = threading.Lock()


def _proc() -> subprocess.Popen:
    """惰性启动 node 常驻进程(找不到 node 才报错 ✓)。"""
    global PROC
    if PROC is None or PROC.poll() is not None:
        PROC = subprocess.Popen(
            ["node", _WORKER],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, bufsize=1,
        )
    return PROC


@dataclass
class GameAIPolicy:
    """游戏 AI 决策器 —— 接口与 RLPolicy 对齐, 方便适配器同一条链调用 ✓"""

    nan_du: int = int(os.getenv("GUANDAN_AI_NANDU", "2"))   # 1简单 2中等 3困难 ✓
    calls: int = 0
    last_debug: dict = field(default_factory=dict)

    @staticmethod
    def available() -> bool:
        """node 在不在(不在就用不了这个臂 ⇒ 明确报错, 别静默降级 ✗)"""
        try:
            return subprocess.run(["node", "--version"], capture_output=True).returncode == 0
        except Exception:  # noqa: BLE001
            return False

    def choose(self, hand: list, last_group: Any, shi_dui_you: bool,
               jipai: int) -> tuple[list | None, dict]:
        """问游戏 AI: 这手牌 + 桌上这手 + 是否队友 ⇒ 出哪几张?

        返回: (要出的牌列表(原样 Card), None=不出/问不到, 调试信息)
        """
        if not self.available():
            return None, {"error": "node 不可用"}
        req = {
            "hand": [[c.zhi, c.hua, c.id] for c in hand],
            "last": [[c.zhi, c.hua] for c in (getattr(last_group, "cards", None) or [])],
            "lastSeat": 1,
            "shiDuiYou": bool(shi_dui_you),
            "jipai": int(jipai),
            "nanDu": int(self.nan_du),
        }
        try:
            with LOCK:
                p = _proc()
                p.stdin.write(json.dumps(req) + "\n")
                p.stdin.flush()
                line = p.stdout.readline()
        except Exception as e:  # noqa: BLE001
            return None, {"error": f"{type(e).__name__}: {e}"}
        if not line:
            return None, {"error": "worker 没回话"}
        try:
            res = json.loads(line)
        except Exception as e:  # noqa: BLE001
            return None, {"error": f"回复解析失败: {e}"}
        if res.get("error"):
            return None, {"error": res["error"]}
        self.calls += 1
        self.last_debug = {"calls": self.calls}
        if res.get("guo") or not res.get("cards"):
            return None, {"arm": "game_ai", "guo": True}
        # 把 (zhi,hua,id) 还原成**手牌里的原对象**(和 RL 臂一样按声明找 ✓)
        want = [(int(z), int(h)) for z, h, *_ in res["cards"]]
        picked, used = [], set()
        for z, h in want:
            hit = next((c for c in hand if c.zhi == z and c.hua == h and id(c) not in used), None)
            if hit is None:                      # 花色对不上(万能之类) ⇒ 退回只按点数 ✓
                hit = next((c for c in hand if c.zhi == z and id(c) not in used), None)
            if hit is None:
                return None, {"error": "AI 出的牌不在手里"}
            used.add(id(hit))
            picked.append(hit)
        return picked, {"arm": "game_ai", "guo": False}


if __name__ == "__main__":                       # 手动试一把: python3 -m ...game_ai
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    from landlord_counter.guandan import rules as R   # noqa: E402

    R.she_zhi_ji_pai(2)
    hand = [R.Card(zhi=z, hua=h, id=i)
            for i, (z, h) in enumerate([(3, 0), (3, 1), (4, 0), (5, 0), (5, 1), (5, 2), (9, 0), (13, 1)])]
    g = GameAIPolicy()
    cards, info = g.choose(hand, None, False, 2)
    print("手牌:", R.cards_to_str(hand))
    print("游戏AI 决定:", (R.cards_to_str(cards) if cards else "不出"), info)

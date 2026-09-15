"""执行器规范: 识别 → 动作 → 校验 (perceive → act → verify)。

**由来(2026-09-15 实测踩坑)**: 云手机里的游戏 UI 没有 DOM(牌画在 canvas 上)、输入通道会
漂移/失灵, "按公式点坐标"必然翻车:
  · 公式左缘 124 vs 画面实际 78 → 点到邻牌;
  · 点一张却整组选中(游戏"帮点"), 再点第二张整组取消;
  · 他家回合手牌照样画在屏幕上, 点了"0 反应"却仍被判成我方回合 → 一堆假失败。
成熟框架(Airtest / MaaFramework)的共同纪律是: **识别锚点 → 得到坐标 → 动作 → 再识别验证**,
不猜、不静默失败。本模块把这条纪律固化成代码契约。

## 四步契约(所有动作必须走)

1. **PERCEIVE 识别** —— 动作依据必须来自**实测**(图像测量 / 无障碍树 / 帧差), 禁止纯公式常量;
   拿不到实测依据 ⇒ **不动作**(返回 skipped), 绝不用"猜的坐标"顶着上。
2. **PREPARE 前置校验** —— 记录"动作前"的可观测状态(lift/白像素/节点)作为校验基线;
   并检查动作是否被允许(非我回合不许出牌)。
3. **ACT 动作** —— 一次原子输入(单次 tap / 单次 key), 带序号, 便于日志与指标对账。
4. **VERIFY 校验** —— 用**可观测信号**确认生效(数值增量 / 状态跃迁 / 身份匹配);
   不生效 ⇒ 有限重试(默认 2) ⇒ 仍失败 ⇒ 返回 failed **并附证据**(绝不静默)。

## 活性探针(liveness probe)

"动作完全无反应"时, 优先归因为**不是我们的回合 / 输入通道失灵**, 而不是判动作失败:
  实测: 他家回合时手牌仍在画, 试点一张 → 抬起量 0 变化、画面 0 变化 ⇒ 判定为非我回合, 跳过本帧。
  连续多次无反应(默认 3) ⇒ 提示上层"输入通道可能失灵" ⇒ 交给看门狗重开页面恢复。
这也是 Airtest `exists/wait` 那条纪律的低成本版本: **先问它理不理我, 再决定打不打**。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

MEASURED_SOURCES = ("measured", "a11y", "vlm", "frame_diff")   # 可接受的"实测"来源
LIVENESS_FAIL_LIMIT = 3      # 连续多少次无反应就认为"通道失灵"(交上层重开)


@dataclass
class Evidence:
    """动作的证据: 依据来源 + 动作前后可观测信号。"""

    src: str = "measured"                  # measured | a11y | vlm | frame_diff | formula
    before: dict[str, Any] = field(default_factory=dict)
    after: dict[str, Any] = field(default_factory=dict)
    changed: bool = False

    def as_dict(self) -> dict:
        return {"src": self.src, "before": self.before, "after": self.after, "changed": self.changed}


@dataclass
class ActReport:
    """动作报告 —— 执行器唯一对外口径。"""

    kind: str = "act"
    ok: bool = False
    skipped: bool = False          # 前置不满足, 未动作(不是失败)
    not_our_turn: bool = False     # 活性探针判定: 非我回合/通道失灵
    retries: int = 0
    reason: str = ""
    evidence: Evidence | None = None

    def as_dict(self) -> dict:
        return {"kind": self.kind, "ok": self.ok, "skipped": self.skipped,
                "not_our_turn": self.not_our_turn, "retries": self.retries,
                "reason": self.reason, "evidence": self.evidence.as_dict() if self.evidence else None}


class ActContractError(RuntimeError):
    """违反执行器契约(如拿公式坐标去点)。"""


def require_measured(src: str) -> None:
    """契约第 1 步的守卫: 动作依据必须是实测来源。"""
    if src not in MEASURED_SOURCES:
        raise ActContractError(f"动作依据必须实测(允许 {MEASURED_SOURCES}), 收到: {src!r}")


def run_act(kind: str, *, perceive: Callable[[], Any], prepare: Callable[[Any], Any],
            act: Callable[[Any], Any], verify: Callable[[Any, Any], tuple[bool, Evidence]],
            retries: int = 2, src: str = "measured",
            on_fail: Callable[[], None] | None = None) -> ActReport:
    """按四步契约跑一个动作。任何执行器都可用它包一层。

    perceive → prepare → act → verify →(失败) 重试 → 报告
    perceive 返回 None = 识别不到依据 ⇒ skipped(不动作)。
    """
    require_measured(src)
    rpt = ActReport(kind=kind)
    ctx = perceive()
    if ctx is None:
        rpt.skipped = True
        rpt.reason = "识别不到实测依据 → 不动作"
        return rpt
    pre = prepare(ctx)
    for i in range(retries + 1):
        out = act(ctx)
        ok, ev = verify(pre, out)
        rpt.retries = i
        rpt.evidence = ev
        if ok:
            rpt.ok = True
            rpt.reason = "校验通过"
            return rpt
        if on_fail is not None:
            on_fail()
    rpt.reason = f"重试 {retries} 次后校验仍不通过"
    return rpt

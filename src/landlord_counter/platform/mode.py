"""运行模式: **真值(演示)** vs **产品(纯视觉)** —— 用户 2026-09-18 拍板解耦。

为什么要有这个开关
------------------
两条路共用**同一套**定位 / 点击 / 决策; 差别只在"**感知与校验的来源**":

  · truth(真值/演示): 走插桩版游戏的 `window.__truth()` —— 手牌/选中/上一手都是**游戏本人说的**,
    零读错 ⇒ 演示稳定可靠 ✓ (实测: 人工托管 27 张全出完、零失误)
  · product(产品/纯视觉): 一切靠截屏 + 模板 + 桌面牌块 ⇒ 面对**闭源游戏**也能用,
    但读数有误差 ⇒ 校验退化成"出牌回执 + 手牌张数下降" ✓

切换: 环境变量 ``LANDLORD_MODE=truth|product``(默认 truth —— 近期先出演示版 ✓)
纪律: **不要在业务代码里散落 if**; 需要分模式的地方一律 import 本模块 ✓
"""
from __future__ import annotations

import os

MODE = os.environ.get("LANDLORD_MODE", "truth").strip().lower()
TRUTH = MODE != "product"          # 除 "product" 之外一律按真值模式跑(演示优先 ✓)
LABEL = "真值(演示)" if TRUTH else "产品(纯视觉)"


def describe() -> str:
    """给人看的一行(启动时打印, 让人一眼知道现在跑的是哪个模式 ✓)"""
    return f"★ 运行模式: {LABEL}  [LANDLORD_MODE={MODE}]"

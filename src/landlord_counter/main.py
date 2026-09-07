"""主程序：轮询截屏 → 识别 → 记牌 → （可选）AI分析 → 输出提示。"""
from __future__ import annotations

import time
from typing import Optional

from .ai.analyzer import LandlordAnalyzer
from .config import load_config
from .logic.tracker import GameState
from .screen.adb_capture import ADBError, ScreenCapturer
from .vision.card_recognizer import CardRecognizer


class LandlordCounterApp:
    """斗地主记牌器主应用"""

    def __init__(self):
        self.cfg = load_config()
        self.capturer = ScreenCapturer(self.cfg.screen)
        self.recognizer = CardRecognizer(self.cfg.vision)
        self.analyzer = LandlordAnalyzer(self.cfg.llm)
        self.state = GameState()

    def _check_environment(self) -> bool:
        """检查 ADB 设备和模板"""
        try:
            devices = self.capturer.list_devices()
        except ADBError as e:
            print(f"✗ ADB 错误: {e}")
            return False
        if not devices:
            print(
                "✗ 未检测到安卓设备。请:\n"
                "  1. 手机开启「开发者选项 → USB调试」并连接电脑\n"
                "  2. 或启动安卓模拟器\n"
                "  3. adb devices 确认设备在线"
            )
            return False
        print(f"✓ 检测到设备: {devices}")
        if not self.recognizer.template_available():
            print(
                "⚠ 未找到牌面模板，将使用 VLM 识别（需配置 VLM_API_KEY）\n"
                "  或运行 tools/gen_templates.py 生成模板"
            )
        else:
            print(f"✓ 已加载 {len(self.recognizer.templates)} 张牌面模板")
        return True

    def run(self, rounds: Optional[int] = None, verbose: bool = True):
        """主循环。rounds=None 表示一直运行"""
        if not self._check_environment():
            return
        last_hand: list[str] = []
        n_round = 0
        print("▶ 记牌器运行中... (Ctrl+C 退出)\n")
        try:
            while rounds is None or n_round < rounds:
                try:
                    hand = self.recognizer.recognize_hand_best(
                        self.capturer.capture_roi(self.cfg.screen.hand_roi)
                    )
                except ADBError as e:
                    print(f"⚠ 截屏失败: {e}，1秒后重试")
                    time.sleep(1)
                    continue

                if hand and hand != last_hand:
                    # 手牌变化 → 推导谁出了什么牌
                    self._on_hand_change(last_hand, hand)
                    last_hand = hand

                if verbose:
                    self._print_status()
                time.sleep(self.cfg.screen.poll_interval)
                n_round += 1
        except KeyboardInterrupt:
            print("\n■ 已停止")

    def _on_hand_change(self, old: list[str], new: list[str]):
        """手牌变化时更新记牌状态"""
        self.state.record_my_hand(new)
        # 简单推导：手牌减少 = 自己出牌（实际需结合出牌区识别）
        if old and len(new) < len(old):
            # 差值即自己打出的牌（简化假设：自己刚出牌）
            from collections import Counter

            diff = Counter(old) - Counter(new)
            played_cards = list(diff.elements())
            if played_cards:
                self.state.record_play("self", played_cards)
                print(f"◆ 检测到自己出牌: {' '.join(played_cards)}")

    def _print_status(self):
        print("\033[2J\033[H")  # 清屏
        print(self.state.summary())
        if self.analyzer.available:
            print("\n" + self.analyzer.analyze(self.state))


def main():
    app = LandlordCounterApp()
    app.run()


if __name__ == "__main__":
    main()

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
        use_vlm = self.recognizer.cfg.vlm_available() and self.recognizer.profile.vlm_first
        last_hand: list[str] = []
        last_sig: Optional[bytes] = None  # 手牌行像素签名，变了才调 VLM（省调用）
        n_round = 0
        print(f"▶ 记牌器运行中... (Ctrl+C 退出)  识别链路: {'VLM直读(' + self.recognizer.cfg.vlm_model + ')' if use_vlm else '模板匹配'}\n")
        try:
            while rounds is None or n_round < rounds:
                try:
                    img = self.capturer.capture()  # 整屏（VLM 直读需自行定位手牌行）
                except ADBError as e:
                    print(f"⚠ 截屏失败: {e}，1秒后重试")
                    time.sleep(1)
                    continue

                if use_vlm:
                    sig = self._band_signature(img)
                    if sig != last_sig:
                        hand = self.recognizer.read_hand_vlm(img)
                        last_sig = sig
                    else:
                        hand = last_hand  # 画面没变，沿用上次结果，不重复调用 VLM
                else:
                    roi = img[
                        int(self.cfg.screen.hand_roi[1] * img.shape[0]) : int(self.cfg.screen.hand_roi[3] * img.shape[0]),
                        int(self.cfg.screen.hand_roi[0] * img.shape[1]) : int(self.cfg.screen.hand_roi[2] * img.shape[1]),
                    ]
                    hand = self.recognizer.recognize_hand_best(roi)

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

    @staticmethod
    def _band_signature(img) -> Optional[bytes]:
        """整屏缩小灰度指纹：画面变化(含对手出牌/切页)才触发 VLM，避免空轮询烧 token。"""
        try:
            import cv2

            small = cv2.resize(img, (64, 36), interpolation=cv2.INTER_AREA)
            gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
            return gray.tobytes()
        except Exception:
            return None

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

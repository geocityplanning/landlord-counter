"""一键读手牌 CLI：从安卓设备(或截图文件)读当前手牌点数。

用法:
    uv run python -m landlord_counter.tools.read_hand                # 连 adb 读当前屏幕
    uv run python -m landlord_counter.tools.read_hand 截图.png       # 读历史截图(调试/回归)
    uv run python -m landlord_counter.tools.read_hand 截图.png 17    # 指定期望张数

依赖 .env 里的 VLM_API_BASE / VLM_API_KEY / VLM_MODEL（glm-4v-plus 识别更准）。
"""
from __future__ import annotations

import sys
from pathlib import Path

import cv2

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))


def main() -> None:
    args = sys.argv[1:]
    expected = int(args[1]) if len(args) > 1 and args[1].isdigit() else 0

    from landlord_counter.config import VisionConfig, load_config
    from landlord_counter.vision.card_recognizer import CardRecognizer

    cfg = load_config()
    if args:
        img = cv2.imread(args[0])
        if img is None:
            print(f"✗ 无法读取图片: {args[0]}")
            sys.exit(1)
        source = args[0]
    else:
        from landlord_counter.screen.adb_capture import ScreenCapturer

        cap = ScreenCapturer(cfg.screen)
        img = cap.capture()
        source = f"设备 {cfg.screen.adb_serial or '(自动)'}"

    rec = CardRecognizer(cfg.vision)
    if not rec.cfg.vlm_available():
        print("✗ 未配置 VLM（检查 .env 的 VLM_API_KEY / VLM_API_BASE）")
        sys.exit(1)

    band = rec.locate_hand_band(img)
    print(f"来源: {source} | 模型: {rec.cfg.vlm_model} | 手牌行带: {band}")
    hand = rec.read_hand_vlm(img, expected)
    if not hand:
        print("⚠ 未识别到手牌（确认画面里有手牌 / VLM 调用是否成功）")
        sys.exit(1)
    print(f"手牌({len(hand)}张): {' '.join(hand)}")


if __name__ == "__main__":
    main()

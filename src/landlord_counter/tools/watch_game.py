"""对局观测器：挂机记录一整局的事件流，供状态机/评估使用。

每轮: 截屏 → 屏幕指纹变化? → VLM 读手牌 → 记录手牌/变化事件到 JSONL。
输出: 控制台实时 + logs/game_<ts>.jsonl（每行一个事件）。

用法:
    uv run python -m landlord_counter.tools.watch_game            # 一直跑
    uv run python -m landlord_counter.tools.watch_game 120        # 跑 120 秒
"""
from __future__ import annotations

import json
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from landlord_counter.config import PROJECT_ROOT, load_config
from landlord_counter.screen.adb_capture import ScreenCapturer
from landlord_counter.vision.card_recognizer import CardRecognizer


def main() -> None:
    limit = float(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].replace(".", "").isdigit() else None
    cfg = load_config()
    cap = ScreenCapturer(cfg.screen)
    rec = CardRecognizer(cfg.vision)
    if not rec.cfg.vlm_available():
        print("✗ 未配置 VLM（.env 的 VLM_API_KEY）")
        sys.exit(1)

    log_dir = PROJECT_ROOT / "logs"
    log_dir.mkdir(exist_ok=True)
    log_path = log_dir / f"game_{datetime.now():%Y%m%d_%H%M%S}.jsonl"
    print(f"▶ 观测器启动  model={rec.cfg.vlm_model}  log={log_path}")
    print(f"  屏幕指纹变化时读手牌并记事件 (Ctrl+C 退出)\n")

    import cv2

    def sig(img):
        small = cv2.resize(img, (64, 36))
        return cv2.cvtColor(small, cv2.COLOR_BGR2GRAY).tobytes()

    def log_event(ev: dict) -> None:
        ev["ts"] = datetime.now().isoformat(timespec="seconds")
        line = json.dumps(ev, ensure_ascii=False)
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(line + "\n")
        print(line)

    last_sig = None
    last_hand: list[str] = []
    t0 = time.time()
    try:
        while limit is None or time.time() - t0 < limit:
            img = cap.capture()
            s = sig(img)
            if s == last_sig:
                time.sleep(cfg.screen.poll_interval)
                continue
            last_sig = s
            band = rec.locate_hand_band(img)
            if band is None:
                log_event({"kind": "screen", "note": "无手牌亮带(非牌局画面?)"})
                time.sleep(cfg.screen.poll_interval)
                continue
            hand = rec.read_hand_vlm(img)
            if hand and hand != last_hand:
                log_event({"kind": "hand", "count": len(hand), "cards": " ".join(hand)})
                last_hand = hand
            else:
                log_event({"kind": "screen", "note": "画面变化但手牌未变", "hand_ok": bool(hand)})
            time.sleep(cfg.screen.poll_interval)
    except KeyboardInterrupt:
        print("\n■ 已停止")


if __name__ == "__main__":
    main()

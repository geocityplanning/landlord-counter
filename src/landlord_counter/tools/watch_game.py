"""对局追踪器 v2：相位机 + 三读投票建信念 + reconcile 逐帧校正。

流程:
  idle ──发现新发牌──▶ vote(连读3次, 多数投票建 prior) ──▶ live(每变化单读+reconcile)
  live ──出现结算/再来──▶ ended ──发现新发牌──▶ vote ...

事件写 logs/game_<ts>.jsonl：vote / hand(校正后) / raw(单帧观测) / phase。
用法: uv run python -m landlord_counter.tools.watch_game [秒数]
"""
from __future__ import annotations

import json
import sys
import time
from collections import Counter
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from landlord_counter.config import PROJECT_ROOT, load_config
from landlord_counter.logic.reconcile import reconcile_hand, vote_initial_hand
from landlord_counter.screen.adb_capture import ScreenCapturer
from landlord_counter.vision.card_recognizer import CardRecognizer

END_WORDS = ("胜利", "失败", "结算", "再来", "胜局", "输局", "恭喜")
GAME_WORDS = ("胜率", "积分", "农民", "地主")


def _words(img) -> str:
    import cv2, subprocess, tempfile, os

    p = tempfile.mktemp(suffix=".png")
    cv2.imwrite(p, img)
    try:
        r = subprocess.run(["tesseract", p, "stdout", "-l", "chi_sim", "--psm", "3"],
                           capture_output=True, text=True, timeout=6)
        return " ".join(r.stdout.split())
    except Exception:
        return ""
    finally:
        try:
            os.remove(p)
        except OSError:
            pass


class Tracker:
    def __init__(self, cap: ScreenCapturer, rec: CardRecognizer, poll: float = 1.2):
        self.cap, self.rec, self.poll = cap, rec, poll
        self.phase = "idle"
        self.belief: Counter | None = None

    def _img(self):
        return self.cap.capture()

    def _read(self, img) -> list[str]:
        return self.rec.read_hand_vlm(img)

    def _sig(self, img) -> bytes:
        import cv2

        small = cv2.resize(img, (64, 36))
        return cv2.cvtColor(small, cv2.COLOR_BGR2GRAY).tobytes()

    def loop(self, log_path: Path, limit: float | None):
        last_sig = None
        t0 = time.time()
        while limit is None or time.time() - t0 < limit:
            img = self._img()
            w = _words(img)
            s = self._sig(img)

            if s == last_sig:
                time.sleep(self.poll)
                continue
            last_sig = s

            # 相位推进
            if any(e in w for e in END_WORDS):
                if self.phase != "ended":
                    self.phase = "ended"
                    self.belief = None
                    self._log(log_path, {"kind": "phase", "phase": "ended", "words": w[:40]})
                time.sleep(self.poll)
                continue

            band = self.rec.locate_hand_band(img)
            if band is None:
                time.sleep(self.poll)
                continue

            # 新一局信号: live 中再次出现叫分按钮(不叫/1分…) = 上一局已结束、新局已发
            if self.phase == "live" and self.belief is not None and ("不叫" in w or "叫分" in w or "3分" in w):
                self.phase = "idle"
                self.belief = None
                self._hand_sig = None
                self._log(log_path, {"kind": "phase", "phase": "new_round(叫分重现, 重置)"})
                time.sleep(1.0)
                continue

            if self.phase in ("idle", "ended"):
                if any(g in w for g in GAME_WORDS):
                    self.phase = "voting"
                    self._log(log_path, {"kind": "phase", "phase": "voting(三读)"})
                    reads = []
                    for _ in range(3):
                        reads.append(self._read(self._img()))
                        time.sleep(0.9)
                    self.belief = vote_initial_hand(reads, expected=self.rec.profile.expected_cards)
                    self.phase = "live"
                    self._log(log_path, {"kind": "vote", "count": sum(self.belief.values()),
                                         "cards": " ".join(str(k) for k, v in sorted(self.belief.items()) for _ in range(v)),
                                         "reads": [len(r) for r in reads]})
                time.sleep(self.poll)
                continue

            # live: 手牌行局部变化才读(对手出牌/动画不烧 token)
            if self.belief is not None:
                import cv2

                x0, y0, x1, y1 = band
                sub = img[y0:y1, x0:x1]
                sub = cv2.resize(sub, (48, 20), interpolation=cv2.INTER_AREA)
                bhash = cv2.cvtColor(sub, cv2.COLOR_BGR2GRAY).tobytes()
                if getattr(self, "_hand_sig", None) == bhash:
                    time.sleep(self.poll)
                    continue
                self._hand_sig = bhash
                obs = self._read(img)
                prev_total = sum(self.belief.values())
                expected = len(obs) if len(obs) <= prev_total else prev_total
                belief, rep = reconcile_hand(obs, self.belief, expected=expected)
                if belief != self.belief:
                    self._log(log_path, {"kind": "hand", "count": sum(belief.values()),
                                         "cards": " ".join(str(k) for k, v in sorted(belief.items()) for _ in range(v)),
                                         "obs_count": len(obs), "dropped": dict(rep.dropped),
                                         "added_back": dict(rep.added_back), "notes": rep.notes})
                    self.belief = belief
                else:
                    self._log(log_path, {"kind": "hand_same", "count": sum(belief.values())})
            time.sleep(self.poll)

    @staticmethod
    def _log(path: Path, ev: dict):
        ev["ts"] = datetime.now().isoformat(timespec="seconds")
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(ev, ensure_ascii=False) + "\n")
        print(json.dumps(ev, ensure_ascii=False))


def main():
    limit = float(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].replace(".", "").isdigit() else None
    cfg = load_config()
    cap = ScreenCapturer(cfg.screen)
    rec = CardRecognizer(cfg.vision)
    if not rec.cfg.vlm_available():
        print("✗ 未配置 VLM"); sys.exit(1)
    log_dir = PROJECT_ROOT / "logs"
    log_dir.mkdir(exist_ok=True)
    log_path = log_dir / f"game_{datetime.now():%Y%m%d_%H%M%S}.jsonl"
    print(f"▶ 追踪器 v2  model={rec.cfg.vlm_model}  log={log_path}")
    Tracker(cap, rec, poll=cfg.screen.poll_interval).loop(log_path, limit)


if __name__ == "__main__":
    main()

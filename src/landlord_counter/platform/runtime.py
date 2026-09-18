"""通用托管运行时: 主循环 + 看门狗 + 统计 + 心跳(与游戏无关)。"""
from __future__ import annotations

import time

from .types import GameAdapter


class Runtime:
    """驱动一个 GameAdapter 持续托管。"""

    def __init__(self, adapter: GameAdapter, device, vision=None,
                 stats_path: str | None = None, tag: str = "",
                 watchdog_s: float = 240.0, heartbeat_s: float = 60.0,
                 idle_sleep: float = 1.2) -> None:
        self.ad = adapter
        self.dev = device
        self.vision = vision
        self.stats_path = stats_path
        self.tag = tag
        self.watchdog_s = watchdog_s
        self.heartbeat_s = heartbeat_s
        self.idle_sleep = idle_sleep
        self.deals = 0
        self.actions = 0
        self.ad.attach(device, vision)

    # ---- 统计 ----
    def _stats_append(self, row: str) -> None:
        if not self.stats_path:
            return
        try:
            with open(self.stats_path, "a") as fo:
                fo.write(row + "\n")
        except Exception:  # noqa: BLE001
            pass

    def _foreground_pkg(self) -> str | None:
        """当前前台的包名(前台闸门用) —— 云手机里**第二个浏览器会抢前台** ✗

        实测(2026-09-17): Firefox Focus 抢走前台后, 读牌/结算/点击全都在对着它的界面做
          ⇒ 浏览器欢迎页被当成结算弹窗, VLM 老实说"看不清"却被计成一局 ✗(假局假统计的总源头)
        """
        import subprocess as _sp

        try:
            out = _sp.run(["adb", "-s", getattr(self.dev, "serial", "127.0.0.1:5555"),
                           "shell", "dumpsys", "window"],
                          capture_output=True, text=True, timeout=8).stdout
        except Exception:  # noqa: BLE001
            return None
        for line in out.splitlines():
            if "mCurrentFocus" in line and "/" in line:
                m = line.split()
                for tok in m:
                    if "/" in tok:
                        return tok.split("/")[0]
        return None

    def _log(self, msg: str) -> None:
        print(msg, flush=True)

    # ---- 主循环 ----
    def run(self, seconds: float) -> dict:
        t_end = time.time() + seconds
        last_prog = time.time()
        last_signal = None
        last_hb = time.time()
        last_settle = 0.0
        last_fg = 0.0
        while time.time() < t_end:
            # ★★ 前台闸门(2026-09-17 用户指令: 发现错就即时堵掉, 别留着反复影响 ✗)
            #   云手机里常有**第二个浏览器抢前台**(实测 Firefox Focus 就抢过) ⇒
            #   此时"读牌 / 结算 / 点击"全都在**对着别的界面**做 ⇒ 假局/假结算/假统计的总源头 ✗
            #   (实测: Firefox 欢迎页被 VLM 当成结算弹窗, 它老实说"看不清", 却被计成一局 ✗)
            if time.time() - last_fg > 20.0:
                last_fg = time.time()
                fg = self._foreground_pkg()
                if fg and getattr(self.ad, "package", None) and fg != self.ad.package:
                    self._log(f"[前台] 游戏不在前台(现在是 {fg}) → 拉回来")
                    self.dev.recover(package=self.ad.package, url=self.ad.start_url)
                    last_prog = time.time()
                    last_signal = None
                    continue
            frame = self.dev.snap()
            if frame is None:
                time.sleep(1)
                continue

            # 心跳
            if time.time() - last_hb > self.heartbeat_s:
                last_hb = time.time()
                self._log(f"[HB] t={int(time.time())} 动作={self.actions} 局={self.deals}")

            # 进展信号(手牌像素等)
            sig = self.ad.progress_signal(frame)
            if sig is not None and sig != last_signal:
                last_signal = sig
                last_prog = time.time()
            _ws = getattr(self.ad, "watchdog_s", None) or self.watchdog_s
            if time.time() - last_prog > _ws:
                self._log(f"[看门狗] {int(time.time() - last_prog)}s 无进展 → 恢复")
                self.dev.recover(package=self.ad.package, url=self.ad.start_url)
                last_prog = time.time()
                last_signal = None
                continue

            # 结算: 周期性调用(局数推进类游戏没有"再来一局"按钮, 只在进桌时判会漏计)
            if time.time() - last_settle > 5.0:
                last_settle = time.time()
                info = self.ad.settle(frame)
                if info is not None:
                    self.deals += 1
                    w = info.win
                    self._stats_append(
                        f"{int(time.time())},{self.deals},{'win' if w else ('lose' if w is False else '?')},"
                        f"{self.tag or '-'},{info.raw.strip()[:60]}"
                    )
                    self._log(f"[结算] 第{self.deals}局: {'我方得分' if w else ('我方失分' if w is False else '未判定')} ({info.raw})")

            # 开始/续局按钮
            sb = self.ad.start_button(frame)
            if sb:
                info = self.ad.settle(frame)
                if info is not None:
                    self.deals += 1
                    w = info.win
                    self._stats_append(
                        f"{int(time.time())},{self.deals},{'win' if w else ('lose' if w is False else '?')},"
                        f"{self.tag or '-'},{info.raw.strip()[:60]}"
                    )
                    self._log(f"[结算] 第{self.deals}局: {'我方升级' if w else ('对手升级' if w is False else '未判定')}")
                self._log(f"[进桌] 点开始/续局 {sb}")
                self.dev.tap(sb[0], sb[1], wait=3.0)
                last_prog = time.time()
                last_signal = None
                continue

            # 感知 → 决策 → 执行
            obs = self.ad.sense(frame)
            if not obs.my_turn:
                time.sleep(self.idle_sleep)
                continue
            act = self.ad.decide(obs)
            if act.kind == "none":
                time.sleep(self.idle_sleep)
                continue
            res = self.ad.execute(act, obs)
            if not getattr(res, "ok", True) and not getattr(res, "skipped", False):
                self._fail_streak = getattr(self, "_fail_streak", 0) + 1
                if self._fail_streak >= 6:      # 连续失败 → 牌局多半结束了/界面卡住 → 恢复页面
                    self._log(f"[自愈] 连续 {self._fail_streak} 次失败 → 恢复页面")
                    self.dev.recover(package=self.ad.package, url=self.ad.start_url)
                    self._fail_streak = 0
                    last_prog = time.time()
                    last_signal = None
                    continue
            else:
                self._fail_streak = 0
            if getattr(res, "skipped", False):
                # 执⾏器规范: skipped = 前置不满足(如非我回合/通道无反应) → 不算动作、不喂看门狗
                self._log(f"[跳过] {act.kind} · {res.detail}")
                time.sleep(self.idle_sleep)
                continue
            self.actions += 1
            self._log(f"[动作] {act.kind} → ok={res.ok} retries={res.retries} {res.detail}")
            last_prog = time.time()
        return {"actions": self.actions, "deals": self.deals}

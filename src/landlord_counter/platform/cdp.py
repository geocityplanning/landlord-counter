"""CDP 客户端(同步): 直连安卓 Chromium 的调试口, 派发输入 / 读页面真值。

⚠️ 仅**调试/标定**通道(商业 App/小程序没有 DevTools) —— 产品路径仍是"纯视觉 + 实测锚点"。

为什么需要(2026-09-15 实测): `adb input tap` 点手牌能选中 ✓、点"提示"能用 ✓,
但点**"出牌"按钮完全无反应** ✗(普通/长按/Tab+Enter/纯 Enter 都试过, DOM 里 disabled 还是 False);
改用 CDP `Input.dispatchMouseEvent` 在精确 CSS 坐标上派发 → "选牌→出牌"一次成功 ✓。

坐标换算(安卓 Chromium 实测):
  视口 innerWidth/Height 是 **CSS** 尺寸, dpr=2 → 内容 720×1024 设备px; 屏幕 720×1280
  ⇒ 差额是浏览器工具栏(实测 ≈155px)
  screen_x = css_x * dpr ;  screen_y = css_y * dpr + offset
  验证: "出牌"按钮 DOM(180,481) → 屏幕(360,1116) ≈ 像素法(359,1119)

接法:
  adb shell 'echo "chrome --remote-debugging-port=9222" > /data/local/tmp/chrome-command-line'
  adb shell am force-stop <pkg>; adb shell am start ... (重启浏览器)
  adb forward tcp:9222 localabstract:chrome_devtools_remote
"""
from __future__ import annotations

import asyncio
import json
import os
import urllib.request
from typing import Any

import websockets


class CDPError(RuntimeError):
    pass


class CDP:
    """极简同步 CDP 客户端(每个动作短连接一次, 够用且无状态)。"""

    def __init__(self, port: int = 9222, offset: int | None = None,
                 url_filter: str | None = "8123") -> None:
        self.port = port
        self.offset = int(os.getenv("GUANDAN_CDP_OFFSET", "155")) if offset is None else offset
        self.url_filter = url_filter or os.getenv("GUANDAN_CDP_URL_FILTER", "")
        self._ws_url: str | None = None
        self._dpr: int = 2

    # ---------------- 目标发现 ----------------
    def _list(self) -> list:
        try:
            data = json.load(urllib.request.urlopen(f"http://127.0.0.1:{self.port}/json", timeout=6))
        except Exception as e:  # noqa: BLE001
            raise CDPError(f"调试口不可达: {e}") from e
        pages = [t for t in data if t.get("type") == "page" and self.url_filter in (t.get("url") or "")]
        pages.sort(key=lambda t: -int(str(t["id"]).split("/")[-1]) if str(t["id"]).isdigit() else 0)
        return pages

    def _connect(self):
        pages = self._list()
        if not pages:
            raise CDPError("没有匹配的页面目标")
        return pages[0]["webSocketDebuggerUrl"]

    # ---------------- 基础调用 ----------------
    def _call(self, method: str, params: dict | None = None, timeout: float = 12.0) -> Any:
        async def run() -> Any:
            url = self._ws_url or self._connect()
            async with websockets.connect(url, max_size=8 << 20, open_timeout=8) as ws:
                await ws.send(json.dumps({"id": 1, "method": method, "params": params or {}}))
                while True:
                    m = json.loads(await asyncio.wait_for(ws.recv(), timeout=timeout))
                    if m.get("id") == 1:
                        if "error" in m:
                            raise CDPError(str(m["error"])[:160])
                        return m.get("result")

        return asyncio.run(run())

    def eval_js(self, expr: str) -> Any:
        r = self._call("Runtime.evaluate", {"expression": expr, "returnByValue": True,
                                            "awaitPromise": True})
        return (r or {}).get("result", {}).get("value")

    def alive(self) -> bool:
        try:
            return bool(self.eval_js("document.visibilityState"))
        except Exception:  # noqa: BLE001
            return False

    # ---------------- 输入 ----------------
    def click_css(self, x: float, y: float, settle: float = 0.45) -> None:
        for t in ("mousePressed", "mouseReleased"):
            self._call("Input.dispatchMouseEvent",
                       {"type": t, "x": float(x), "y": float(y), "button": "left", "clickCount": 1})
        if settle:
            import time

            time.sleep(settle)

    def click_screen(self, sx: float, sy: float, settle: float = 0.45) -> None:
        """按**屏幕设备坐标**点击(内部换算成页面 CSS 坐标)。"""
        try:
            dpr = float(self.eval_js("window.devicePixelRatio") or 2)
        except Exception:  # noqa: BLE001
            dpr = 2.0
        self.click_css(sx / dpr, (sy - self.offset) / dpr, settle=settle)

    def canvas_rect(self) -> dict:
        v = self.eval_js("""(() => { const c=document.querySelector('canvas'); if(!c) return null;
            const r=c.getBoundingClientRect(); return JSON.stringify({x:r.x,y:r.y,w:r.width,h:r.height,dpr:window.devicePixelRatio,iw:innerWidth,ih:innerHeight}); })()""")
        return json.loads(v) if v else {}

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

    # ---------------- 游戏真值(源码依据: reference/guandan/www/js/main.js) ----------------
    #  chuPai(): phase!=='playing' 或 currentChuPaiZhe!==0(南=玩家) → 静默返回
    #            选中为空 → showToast('请选择要出的牌'); 牌型非法 → showToast(reason)
    def find_truth(self, max_pages: int = 8) -> bool:
        """在 8123 的页面里找到**带量测钩子**(window.__truth)的那个并连上去。

        背景: 设备上有几十个僵尸页(prep/重开都会留一个) ✗ →
        盲连 pages[0] 经常连到没钩子的旧页 → 读真值读到 None。
        做法: 只扫同源(172.18.0.1:8123)的最新若干页, 命中 __truth 就锁定。
        """
        try:
            pages = [x for x in self._list() if "8123" in (x.get("url") or "")][:max_pages]
        except Exception:                            # noqa: BLE001
            return False
        for pg in pages:
            try:
                self._ws_url = pg.get("webSocketDebuggerUrl")
                if self.eval_js("typeof window.__truth === 'function' ? 1 : 0") == 1:
                    return True
            except Exception:                        # noqa: BLE001
                continue
        self._ws_url = None
        return False

    def truth(self) -> dict:
        """读游戏真值(仅实验室! 需插桩版页面)。"""
        v = self.eval_js("typeof window.__truth === 'function' ? JSON.stringify(window.__truth()) : null")
        import json as _j

        try:
            return _j.loads(v) if v else {}
        except Exception:                            # noqa: BLE001
            return {}

    def toast(self) -> str:
        """读 #toast 文本(1.5s 内有效)。空串=当前没提示。"""
        try:
            v = self.eval_js("(() => { const t=document.getElementById('toast');"
                             " return t ? (t.textContent||'') : ''; })()")
            return (v or "").strip()
        except Exception:  # noqa: BLE001
            return ""

    def our_turn_probe(self, play_btn: tuple | None = None) -> tuple[bool, str]:
        """**回合真值探针**: 点一下"出牌"按钮, 看游戏怎么回。

        · toast='请选择要出的牌' ⇒ 闸门①(阶段+该谁)通过 ⇒ **是我们的回合**(未选中是正常的)
        · 完全静默 ⇒ 不是我们的回合(或阶段不对)
        返回值: (是否我方回合, 说明)。代价: 一次点击, 无副作用(不选牌不会出牌)。
        """
        if play_btn is None:
            v = self.eval_js("""(() => { const b=[...document.querySelectorAll('button')].find(e=>(e.innerText||'').trim()==='出牌');
                if(!b) return null; const r=b.getBoundingClientRect(); return JSON.stringify([r.x+r.width/2, r.y+r.height/2]); })()""")
            if not v:
                return False, "找不到出牌按钮"
            import json as _j

            play_btn = tuple(_j.loads(v))
        # 先清掉可能残留的旧 toast(读一次忽略)
        _ = self.toast()
        try:
            self.click_css(play_btn[0], play_btn[1], settle=0.9)
        except Exception as e:  # noqa: BLE001
            return False, f"点击失败: {type(e).__name__}"
        t = self.toast()
        if "请选择要出的牌" in t:
            return True, "我方回合(游戏确认)"
        if t:
            return True, f"我方回合(游戏提示: {t})"
        return False, "非我方回合(静默)"

    # ---------------- 真值几何(游戏源码 cardUI.js: getClickedCardIndex) ----------------
    #   totalWidth=(n-1)*cardGap+cardWidth; startX=(container.clientWidth-totalWidth)/2
    #   baseY=container.clientHeight-cardHeight-15; 命中判定**自右向左**取第一个 → 要安全命中第 i 张,
    #   必须点它"露出的左条带"中点(cardX+gap/2)。
    #   主题常量(实测与我们画面测量一致): cardWidth=44, cardHeight=62, cardGap=12 (CSS 单位)
    CARD_W, CARD_H, CARD_GAP = 44.0, 62.0, 12.0

    def card_tap_points(self, n: int) -> list:
        """按游戏真值几何给出每张牌的**屏幕设备坐标**点击点。"""
        v = self.eval_js("""(() => { const c=document.querySelector('canvas');
            const k=(c && c.parentElement) || c || document.body;
            return JSON.stringify({w:k.clientWidth, h:k.clientHeight}); })()""")
        import json as _j

        box = _j.loads(v) if v else {}
        W = float(box.get("w") or 360.0)
        H = float(box.get("h") or 404.0)
        total = (n - 1) * self.CARD_GAP + self.CARD_W
        start_x = (W - total) / 2.0
        base_y = H - self.CARD_H - 15.0
        pts = []
        for i in range(n):
            cx = start_x + i * self.CARD_GAP + self.CARD_GAP / 2.0     # 露出的左条带中点
            cy = base_y + self.CARD_H / 2.0
            pts.append((int(cx * 2), int(cy * 2 + self.offset)))       # CSS → 屏幕设备坐标
        return pts

    def canvas_rect(self) -> dict:
        v = self.eval_js("""(() => { const c=document.querySelector('canvas'); if(!c) return null;
            const r=c.getBoundingClientRect(); return JSON.stringify({x:r.x,y:r.y,w:r.width,h:r.height,dpr:window.devicePixelRatio,iw:innerWidth,ih:innerHeight}); })()""")
        return json.loads(v) if v else {}

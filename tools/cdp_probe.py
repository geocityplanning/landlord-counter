"""CDP 探针: 直连 Bromite 的调试口, 读**游戏内部状态**(DOM/JS)。

用途(仅调试/标定, 不进产品路径): 纯像素与无障碍树看不到"游戏到底认不认这手牌",
而 CDP 能直接问页面:
  · 提示/出牌/不出 三个按钮的 disabled / aria-disabled / 坐标
  · DOM 里有没有"已选中"的元素/类名
  · window 上暴露的游戏对象(开源游戏常有)

用法:
  adb -s 127.0.0.1:5555 forward tcp:9222 localabstract:chrome_devtools_remote
  python3 tools/cdp_probe.py '<js 表达式>'
"""
from __future__ import annotations

import asyncio
import json
import sys
import urllib.request

import websockets

DEFAULT_JS = r"""
(() => {
  const pick = ['提示','出牌','不出','再来一局','开始游戏'];
  const btns = [];
  document.querySelectorAll('button, [role=button], a, div, span').forEach(el => {
    const t = (el.innerText || '').trim();
    if (pick.includes(t) && el.children.length <= 1) {
      const r = el.getBoundingClientRect();
      btns.push({text: t, tag: el.tagName, disabled: el.disabled ?? null,
                 aria: el.getAttribute('aria-disabled'), cls: String(el.className).slice(0, 40),
                 x: Math.round(r.x + r.width / 2), y: Math.round(r.y + r.height / 2),
                 w: Math.round(r.width), h: Math.round(r.height)});
    }
  });
  const sel = [];
  document.querySelectorAll('*').forEach(el => {
    const c = String(el.className || '');
    if (/select|chosen|active|picked/i.test(c) && el.tagName !== 'BODY') {
      sel.push({tag: el.tagName, cls: c.slice(0, 50), n: el.innerText ? el.innerText.trim().slice(0, 20) : ''});
    }
  });
  const gk = Object.keys(window).filter(k => /game|player|hand|card|select|guard|guan/i.test(k)).slice(0, 15);
  return JSON.stringify({buttons: btns, selected_like: sel.slice(0, 12), globals: gk,
                         body: document.body.innerText.slice(0, 120)}, null, 1);
})()
"""


async def run(expr: str) -> None:
    data = json.load(urllib.request.urlopen("http://127.0.0.1:9222/json", timeout=8))
    pages = [t for t in data if t.get("type") == "page" and "8123" in (t.get("url") or "")]
    print(f"候选目标 {len(pages)} 个, 逐个试 ...")
    for t in pages:
        try:
            async with websockets.connect(t["webSocketDebuggerUrl"], max_size=8 << 20) as ws:
                await ws.send(json.dumps({"id": 1, "method": "Runtime.evaluate",
                                          "params": {"expression": expr, "returnByValue": True,
                                                     "awaitPromise": True}}))
                while True:
                    msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=10))
                    if msg.get("id") == 1:
                        break
                res = msg.get("result", {}).get("result", {})
                val = res.get("value")
                if not val:
                    continue
                if isinstance(val, str) and "buttons" in val:
                    print(f"\n=== 页面 {t['id']} ===")
                    print(val)
                    return
        except Exception as e:  # noqa: BLE001
            print(f"  目标 {t['id']} 失败: {type(e).__name__}")
    print("没找到能读取的页面")


if __name__ == "__main__":
    expr = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_JS
    asyncio.run(run(expr))

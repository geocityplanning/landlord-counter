"""设备实时画面 + 操作日志的网页直播(自用工具, 非产品路径)。

用法:
    PYTHONPATH=src python3 tools/live_view.py [端口=8140] [fps=2]

你自己电脑上看(SSH 隧道, 和你平时一样):
    ssh -L 8140:127.0.0.1:8140 root@223.4.23.64
    浏览器打开  http://127.0.0.1:8140/

页面:
    /            画面(MJPEG) + 实时操作日志 + 记牌事件
    /stream      MJPEG 流(浏览器 <img> 直接可用)
    /log         最近的运行日志(动作/结果/记牌)
    /events      最近的记牌事件(谁打了什么牌)
    /rec         录屏状态; /rec/start /rec/stop 开关(存 data/rec/*.mp4)

★ 2026-09-22 新增 **可点** (用户: "想能 H5/Windows 手动操作"):
    · 页面里点画面 = 点手机(坐标自动换算 ✓)
    · 默认**关闭**, 要手动勾上"允许点击"才生效(防误触 ✓)
    · 点下去走 **MaaTouch 拟人化**(压力/微移/随机时长 ✓) —— **不走 adb input** ✗
    · POST /tap  {"x":360,"y":1113}   设备坐标(720x1280 ✓)  需带 ?k=<口令> ✓
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# 点击要能 import 到平台层(和 manual_tap.py 同一份实现 ✓ 别再写第二套 ✗)
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

SERIAL = os.getenv("DEVICE_SERIAL", "127.0.0.1:5555")
LOG_FILE = os.getenv("LIVE_LOG", "/tmp/g1_long2.log")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REC_DIR = os.path.join(ROOT, "data", "rec")
FRAME = {"jpg": b"", "t": 0.0, "fps": 0.0, "err": ""}
# ★ 点击器: 单例 + 锁(MaaTouch 是常驻进程, 每次重建太贵 ✗)
_TAP = {"mt": None, "lock": threading.Lock()}


_TRUTH = {"cdp": None, "lock": threading.Lock(), "t": 0.0, "val": {}}


def _truth_cached() -> dict:
    """读游戏真值(缓存 0.5 秒 ✓ —— CDP 连接很贵, 页面每 2 秒问一次受不了 ✗)"""
    import json as _j
    import time as _t

    with _TRUTH["lock"]:
        if _TRUTH["cdp"] is None:
            from landlord_counter.platform.cdp import CDP

            _TRUTH["cdp"] = CDP()
        if _t.time() - _TRUTH["t"] < 0.5 and _TRUTH["val"]:
            return _TRUTH["val"]
        try:
            c = _TRUTH["cdp"]
            if not c.find_truth():
                return {"err": "找不到游戏页(它在前台吗?)"}
            t = c.truth()
            v = {"phase": t.get("phase"), "current": t.get("current"),
                 "ji_pai": t.get("jiPai"),
                 "hand": len((t.get("handsFull") or {}).get("0") or []),
                 "need_beat": t.get("needBeat")}
            if v["phase"] != "playing":
                v["need_beat"] = None
            _TRUTH["val"], _TRUTH["t"] = v, _t.time()
            return v
        except Exception as e:  # noqa: BLE001
            return {"err": type(e).__name__}


def _screen_to_css(x: int, y: int):
    """设备坐标 -> 页面 CSS 坐标(工具栏高度按当前页面实测, 不写死 ✗ 换屏也不怕 ✓)"""
    from landlord_counter.platform.cdp import CDP

    c = CDP(port=9222, url_filter="8123")
    d = float(c.eval_js("window.devicePixelRatio") or 2)
    off = float(os.getenv("GUANDAN_CDP_OFFSET", "155"))   # 浏览器工具栏高度(实测 ✓ 和 cdp.py 同一套)
    # ⚠️ 别用页面里的 screen.height 换算 ✗ —— 浏览器按 CSS 尺寸报, 算出来是错的
    return c, (x / d, (y - off) / d)


def _tap_device(x: int, y: int) -> str:
    """点一下设备 —— 走 **CDP 合成鼠标事件**。

    ⚠️ 2026-09-22 实测: 容器里**只有 CDP 合成的输入能到页面** ✓
    真触摸注入(adb input / MaaTouch)到不了浏览器页面 ✗(和"adb 点不动出牌"是同一个老毛病)
    ⇒ 手动操作台改走 CDP(等价于用户直接点页面 ✓); MaaTouch 留给**真机/闭源游戏**那条产品路 ✓
    """
    try:
        c, (cx, cy) = _screen_to_css(x, y)
        for t in ("mousePressed", "mouseReleased"):
            c._call("Input.dispatchMouseEvent",
                    {"type": t, "x": cx, "y": cy, "button": "left", "clickCount": 1,
                     "buttons": 1 if t == "mousePressed" else 0})
        return f"已点 ({int(x)},{int(y)}) · CDP ✓"
    except Exception as e:  # noqa: BLE001
        return f"点失败: {type(e).__name__} {str(e)[:70]}"


def _drag_device(x0: int, y0: int, x1: int, y1: int, ms: int = 400) -> str:
    """拖动(按住 -> 分步移动 -> 松手) —— 用来拖悬浮球 ✓"""
    try:
        c, (cx0, cy0) = _screen_to_css(x0, y0)
        _, (cx1, cy1) = _screen_to_css(x1, y1)
        c._call("Input.dispatchMouseEvent",
                {"type": "mousePressed", "x": cx0, "y": cy0, "button": "left", "clickCount": 1, "buttons": 1})
        steps = 8
        for i in range(1, steps + 1):
            t = i / steps
            c._call("Input.dispatchMouseEvent",
                    {"type": "mouseMoved", "x": cx0 + (cx1 - cx0) * t, "y": cy0 + (cy1 - cy0) * t,
                     "button": "left", "buttons": 1})
            time.sleep(ms / 1000.0 / steps)
        c._call("Input.dispatchMouseEvent",
                {"type": "mouseReleased", "x": cx1, "y": cy1, "button": "left", "clickCount": 1, "buttons": 0})
        return f"已拖 ({x0},{y0})->({x1},{y1}) · CDP ✓"
    except Exception as e:  # noqa: BLE001
        return f"拖动失败: {type(e).__name__} {str(e)[:70]}"
REC = {"on": False, "dir": "", "n": 0, "started": 0.0}


def _grab() -> bytes:
    """一次抓屏 → JPEG 字节。"""
    p = subprocess.run(["adb", "-s", SERIAL, "exec-out", "screencap", "-p"],
                       capture_output=True, timeout=20)
    return p.stdout or b""


def grabber(fps: float) -> None:
    """后台抓帧线程(顺带录屏)。"""
    n = 0
    t0 = time.time()
    while True:
        try:
            jpg = _grab()
            if jpg:
                FRAME["jpg"] = jpg
                FRAME["t"] = time.time()
                n += 1
                el = time.time() - t0
                if el > 5:
                    FRAME["fps"] = round(n / el, 2)
                if REC["on"]:
                    REC["n"] += 1
                    with open(os.path.join(REC["dir"], f"f{REC['n']:06d}.jpg"), "wb") as f:
                        f.write(jpg)
        except Exception as e:  # noqa: BLE001
            FRAME["err"] = f"{type(e).__name__}: {e}"
        time.sleep(max(0.05, 1.0 / max(0.5, fps)))


def _tail(path: str, n: int = 60) -> str:
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            return "".join(f.readlines()[-n:])
    except Exception:  # noqa: BLE001
        return "(暂无日志)"


_HUA = {0: "♠", 1: "♥", 2: "♣", 3: "♦", 4: "★"}
_ZHI = {11: "J", 12: "Q", 13: "K", 14: "A", 15: "小王", 16: "大王"}


def _events(n: int = 40) -> str:
    """最近 n 手 —— **从 sqlite 读**(2026-09-21 用户: 数据一律从 sql 拿, json 全删 ✗)"""
    import sqlite3

    db = os.path.join(ROOT, "data", "companion.db")
    if not os.path.exists(db):
        return "(还没有牌局数据)"
    try:
        con = sqlite3.connect(f"file:{db}?mode=ro", uri=True, timeout=3)
        rows = con.execute("SELECT gid, seq, ts, seat, mine, cards_json FROM play "
                           "ORDER BY id DESC LIMIT ?", (n,)).fetchall()
        con.close()
    except Exception as e:  # noqa: BLE001
        return f"(读库失败: {e})"
    if not rows:
        return "(还没有出牌记录)"
    import json as _j

    out = [f"# 最近 {len(rows)} 手(来自 sqlite: data/companion.db)"]
    for gid, seq, ts, seat, mine, cards in reversed(rows):
        try:
            cs = _j.loads(cards) if cards else []
        except Exception:  # noqa: BLE001
            cs = []
        def _c(c):
            if isinstance(c, dict):
                return f"{_HUA.get(int(c.get('hua') or 0), '?')}{_ZHI.get(int(c.get('zhi') or 0), c.get('zhi'))}"
            return str(c)

        txt = " ".join(_c(c) for c in cs)
        who = f"{seat}{'(我)' if mine else ''}"
        out.append(f"#{seq} {who} {txt}")
    return "\n".join(out)


PAGE = """<!doctype html><html><head><meta charset="utf-8"><title>云手机 · 手动操作台</title>
<style>body{background:#111;color:#ddd;font:14px/1.5 monospace;margin:0;padding:12px}
img{width:432px;border:1px solid #333;border-radius:6px;cursor:crosshair}
.row{display:flex;gap:16px;align-items:flex-start}
pre{background:#000;padding:8px;border-radius:6px;max-height:80vh;overflow:auto;flex:1}
h3{margin:8px 0}
button{padding:4px 10px;margin:2px;border-radius:6px;border:1px solid #444;background:#222;color:#ddd;cursor:pointer}
button:hover{background:#2c2c2c}
#truth{background:#000;border-radius:6px;padding:6px 8px;margin-top:6px;color:#9f9}
#truth.turn{color:#ff6;font-weight:700}
.k{color:#888}</style></head><body>
<div class="row">
  <div><h3>云手机画面（点画面 = 点手机 ✓）</h3>
    <div id="wrap" style="position:relative;display:inline-block">
      <img id="scr" src="/stream">
      <div id="mk" style="position:absolute;width:16px;height:16px;margin:-8px 0 0 -8px;border:2px solid #ff5555;
           border-radius:50%;display:none;pointer-events:none"></div>
    </div>
    <div style="margin-top:6px">
      <label style="color:#ffb"><input type="checkbox" id="allow"> 允许点击(必须先勾上 ✓)</label>
      <div style="margin-top:4px">
        <button onclick="snap()">📸 截图并保存</button>
        <button onclick="rec('start')" style="background:#3a2020;border-color:#633">● 开始录屏</button>
        <button onclick="rec('stop')" style="background:#203a24;border-color:#363">■ 停止并出片</button>
        <button onclick="qt(360,1113)">出牌键</button>
        <button onclick="qt(359,939)">大金钮</button>
        <button onclick="qt(360,875)">中区</button>
      </div>
      <div id="truth">读状态中…</div>
      <div id="tapinfo" style="color:#888">未点过</div>
    </div>
    <div id="meta" style="color:#888"></div></div>
  <div style="flex:1"><h3>操作日志(实时)</h3><pre id="log"></pre></div>
  <div style="flex:1"><h3>记牌事件(谁打了什么牌)</h3><pre id="ev"></pre></div>
</div>
<script>
const KW = new URLSearchParams(location.search).get('k') || '';
function snap(){                                   // ★ 截图: 把当前帧存成 PNG ✓
  const img = document.getElementById('scr');
  const c = document.createElement('canvas');
  c.width = img.naturalWidth || 720; c.height = img.naturalHeight || 1280;
  c.getContext('2d').drawImage(img, 0, 0, c.width, c.height);
  const a = document.createElement('a');
  a.download = 'yunji_' + new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19) + '.png';
  a.href = c.toDataURL('image/png');
  document.body.appendChild(a); a.click(); a.remove();
}
async function rec(a){                              // ★ 录屏开关(用户在页面上自己控制 ✓)
  try{
    const t = await (await fetch('/rec/' + a + (KW ? ('?k=' + KW) : ''))).text();
    if (a === 'stop') { alert(t); } else { document.getElementById('tapinfo').textContent = t; }
  }catch(e){ alert('录屏请求失败: ' + e); }
}
async function tickTruth(){                        // ★ 状态: 轮到我了吗 / 手牌几张 ✓
  try{
    const t = await (await fetch('/truth' + (KW ? ('?k=' + KW) : ''))).json();
    const el = document.getElementById('truth');
    if (t.err) { el.textContent = '状态读不到: ' + t.err; el.className = ''; return; }
    const mine = (t.current === 0);
    el.textContent = `phase=${t.phase} · 级牌 ${t.ji_pai} · 我手牌 ${t.hand} 张 · `
      + (mine ? '★ 轮到我出牌' : `轮到座位 ${t.current}`)
      + (t.need_beat === null ? '' : ` · ${t.need_beat ? '要压' : '可领出'}`);
    el.className = mine ? 'turn' : '';
  }catch(e){}
}
setInterval(tickTruth, 2000); tickTruth();
async function qt(x, y){                       // 发一次点击(设备坐标 ✓)
  if(!document.getElementById('allow').checked){ document.getElementById('tapinfo').textContent='先勾上"允许点击"'; return; }
  const mk=document.getElementById('mk'), img=document.getElementById('scr');
  const r=img.getBoundingClientRect();
  mk.style.left=(x*r.width/720)+'px'; mk.style.top=(y*r.height/1280)+'px'; mk.style.display='block';
  try{
    const res=await fetch('/tap'+(KW?('?k='+KW):''),{method:'POST',headers:{'Content-Type':'application/json'},
                     body:JSON.stringify({x:x,y:y})});
    document.getElementById('tapinfo').textContent=(await res.text())+'  →('+x+','+y+')';
  }catch(e){ document.getElementById('tapinfo').textContent='点击失败:'+e; }
}
document.getElementById('scr').addEventListener('click', ev => {     // 点画面 = 换算成设备坐标
  const r=ev.target.getBoundingClientRect();
  const x=Math.round((ev.clientX-r.left)*720/r.width), y=Math.round((ev.clientY-r.top)*1280/r.height);
  qt(x,y);
});
async function tick(){
  try{
    const r1=await fetch('/log?n=40'); document.getElementById('log').textContent=await r1.text();
    const r2=await fetch('/events'); document.getElementById('ev').textContent=await r2.text();
    const r3=await fetch('/meta'); document.getElementById('meta').textContent=await r3.text();
  }catch(e){}
}
setInterval(tick,3000); tick();
</script></body></html>"""


class H(BaseHTTPRequestHandler):
    def log_message(self, *a) -> None:
        pass

    def _send(self, body, ctype="text/plain; charset=utf-8", code=200):
        data = body.encode("utf-8") if isinstance(body, str) else body
        self.send_response(code)
        # ★ 2026-09-22: 禁止缓存(和 companion 那边同款 ✓)
        #   踩过: 页面改了但浏览器吃缓存 ⇒ 用户看到旧版, 还以为代码回退了 ✗
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self) -> None:  # noqa: N802
        """★ 2026-09-22 新增: 网页点一下 = 点手机(用户要的 H5 手动操作 ✓)"""
        tok = os.getenv("LIVE_TOKEN", "")
        got = ""
        if "?" in self.path:
            for kv in self.path.split("?", 1)[1].split("&"):
                if kv.startswith("k="):
                    got = kv[2:].split("&")[0]
        if tok and got != tok:
            return self._send("需要口令: 请在网址后加 ?k=<口令>", code=403)
        route = self.path.split("?")[0]
        if route not in ("/tap", "/drag"):
            return self._send("not found", code=404)
        try:
            n = int(self.headers.get("Content-Length") or 0)
            body = json.loads(self.rfile.read(n) or b"{}")
        except Exception as e:  # noqa: BLE001
            return self._send(f"参数错: {e}", code=400)
        if route == "/tap":
            x, y = int(body.get("x")), int(body.get("y"))
            if not (0 <= x <= 720 and 0 <= y <= 1280):
                return self._send(f"坐标越界: ({x},{y})", code=400)
            try:
                return self._send(_tap_device(x, y))
            except Exception as e:  # noqa: BLE001
                return self._send(f"点击异常: {type(e).__name__}: {e}", code=500)
        x0, y0, x1, y1 = (int(body.get(k, 0)) for k in ("x0", "y0", "x1", "y1"))
        try:
            return self._send(_drag_device(x0, y0, x1, y1))
        except Exception as e:  # noqa: BLE001
            return self._send(f"拖动异常: {type(e).__name__}: {e}", code=500)

    def do_GET(self) -> None:  # noqa: N802
        # ★ 临时口令(2026-09-17): 公网直连必须带 ?k=<口令> —— 不接受无鉴权直连 ✓
        tok = os.getenv("LIVE_TOKEN", "")
        got = ""
        if "?" in self.path:
            for kv in self.path.split("?", 1)[1].split("&"):
                if kv.startswith("k="):
                    got = kv[2:].split("&")[0]
        if tok and got != tok:
            return self._send("需要口令: 请在网址后加 ?k=<口令>", code=403)
        path = self.path.split("?")[0]
        if path in ("/", "/index.html"):
            html = PAGE
            if tok:
                for ep in ("/stream", "/log", "/events", "/meta"):
                    html = html.replace(f'"{ep}"', f'"{ep}?k={tok}"')
            return self._send(html, "text/html; charset=utf-8")
        if path == "/stream":
            self.send_response(200)
            self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
            self.end_headers()
            try:
                while True:
                    jpg = FRAME["jpg"]
                    if jpg:
                        self.wfile.write(b"--frame\r\nContent-Type: image/jpeg\r\n"
                                         b"Content-Length: " + str(len(jpg)).encode() + b"\r\n\r\n"
                                         + jpg + b"\r\n")
                    time.sleep(0.4)
            except Exception:  # noqa: BLE001
                return
        if path == "/log":
            n = int(self.path.split("n=")[-1]) if "n=" in self.path else 60
            return self._send(_tail(LOG_FILE, n))
        if path == "/events":
            return self._send(_events())
        if path == "/truth":                                  # ★ 给手动操作台的状态 ✓
            return self._send(json.dumps(_truth_cached(), ensure_ascii=False),
                              "application/json; charset=utf-8")
        if path == "/meta":
            age = round(time.time() - FRAME["t"], 1) if FRAME["t"] else -1
            return self._send(f"帧率 {FRAME['fps']}/s · 最后帧 {age}s 前 · 录屏 "
                              f"{'开' if REC['on'] else '关'}({REC['n']} 帧) {FRAME['err']}")
        if path == "/rec/start":
            REC.update(on=True, n=0, started=time.time(),
                       dir=os.path.join(REC_DIR, time.strftime("%Y%m%d_%H%M%S")))
            os.makedirs(REC["dir"], exist_ok=True)
            return self._send(f"录屏开始 → {REC['dir']}")
        if path == "/rec/stop":
            d, n = REC["dir"], REC["n"]
            REC["on"] = False
            if not d or n < 2:
                return self._send("没在录/帧太少")
            mp4 = d + ".mp4"
            cmd = ["ffmpeg", "-y", "-framerate", "2", "-i", os.path.join(d, "f%06d.jpg"),
                   "-c:v", "libx264", "-pix_fmt", "yuv420p", mp4]
            try:
                subprocess.run(cmd, capture_output=True, timeout=300)
                return self._send(f"录屏结束 → {mp4}" if os.path.exists(mp4) else "ffmpeg 失败(帧仍保留)")
            except Exception as e:  # noqa: BLE001
                return self._send(f"ffmpeg 异常: {e}(帧保留在 {d})")
        return self._send("not found", code=404)


def main() -> None:
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8140
    fps = float(sys.argv[2]) if len(sys.argv) > 2 else 2.0
    threading.Thread(target=grabber, args=(fps,), daemon=True).start()
    print(f"▶ 直播: http://0.0.0.0:{port}/  (画面 {fps}fps + 操作日志 + 记牌事件)", flush=True)
    ThreadingHTTPServer(("0.0.0.0", port), H).serve_forever()


if __name__ == "__main__":
    main()

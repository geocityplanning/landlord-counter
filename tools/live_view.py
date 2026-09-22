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


def _tap_device(x: int, y: int) -> str:
    """点一下设备 —— **走 MaaTouch 拟人化**(压力/微移/随机时长 ✓), 不走 adb input ✗"""
    from landlord_counter.platform.maatouch import MaaTouch

    with _TAP["lock"]:
        mt = _TAP["mt"]
        if mt is None or not mt.alive():
            mt = _TAP["mt"] = MaaTouch(SERIAL)
            if not mt.ensure():
                _TAP["mt"] = None
                return "MaaTouch 起不来(点不了 ✗)"
        mt.tap(int(x), int(y))
    return f"已点 ({int(x)},{int(y)}) · 拟人化 ✓"
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


PAGE = """<!doctype html><html><head><meta charset="utf-8"><title>云手机直播</title>
<style>body{background:#111;color:#ddd;font:14px/1.5 monospace;margin:0;padding:12px}
img{width:360px;border:1px solid #333;border-radius:6px}
.row{display:flex;gap:16px;align-items:flex-start}
pre{background:#000;padding:8px;border-radius:6px;max-height:80vh;overflow:auto;flex:1}
h3{margin:8px 0}</style></head><body>
<div class="row">
  <div><h3>画面 (MJPEG)</h3>
    <div id="wrap" style="position:relative;display:inline-block">
      <img id="scr" src="/stream">
      <div id="mk" style="position:absolute;width:14px;height:14px;margin:-7px 0 0 -7px;border:2px solid #ff5555;
           border-radius:50%;display:none;pointer-events:none"></div>
    </div>
    <div style="margin-top:6px">
      <label style="color:#ffb"><input type="checkbox" id="allow"> 允许点击(点画面 = 点手机)</label>
      <div style="margin-top:4px"><button onclick="qt(360,1113)">出牌键</button>
        <button onclick="qt(359,939)">大金钮</button>
        <button onclick="qt(360,875)">中区</button></div>
      <div id="tapinfo" style="color:#888">未点过</div>
    </div>
    <div id="meta" style="color:#888"></div></div>
  <div style="flex:1"><h3>操作日志(实时)</h3><pre id="log"></pre></div>
  <div style="flex:1"><h3>记牌事件(谁打了什么牌)</h3><pre id="ev"></pre></div>
</div>
<script>
const KW = new URLSearchParams(location.search).get('k') || '';
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
        if self.path.split("?")[0] != "/tap":
            return self._send("not found", code=404)
        try:
            n = int(self.headers.get("Content-Length") or 0)
            body = json.loads(self.rfile.read(n) or b"{}")
            x, y = int(body.get("x")), int(body.get("y"))
        except Exception as e:  # noqa: BLE001
            return self._send(f"参数错: {e}", code=400)
        if not (0 <= x <= 720 and 0 <= y <= 1280):
            return self._send(f"坐标越界: ({x},{y})", code=400)
        try:
            return self._send(_tap_device(x, y))
        except Exception as e:  # noqa: BLE001
            return self._send(f"点击异常: {type(e).__name__}: {e}", code=500)

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

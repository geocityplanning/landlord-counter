"""伴随应用: 服务 —— 把本地库(qi)和界面(脸)接起来 ✓

一个进程、一个端口(默认 8131), 只做三件事:
    GET  /                → 返回 web/companion/index.html (悬浮球+小面板)
    GET  /api/*           → 读本地库, 吐 JSON 给前端
    POST /api/host        → 记下"托管 开/关"的意图 (库里 control 表 ✓)

**只收不发** ✓: 本文件不碰画面/点击/决策 ✗; 要"开托管"只写一个意图 ✓,
真正执行的是现有托管循环(它读这个意图 ⇒ 现有逻辑一行不改 ✓)
越界检验: 出现 cv2 / Card( / maatouch / 牌型规则 ⇒ 越界 ✗
"""
from __future__ import annotations

import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

_SRC = Path(__file__).resolve().parents[2]      # …/src  (包在这里 ✓)
sys.path.insert(0, str(_SRC))
from landlord_counter.companion.store import CompanionStore    # noqa: E402

ROOT = _SRC.parent / "web" / "companion"          # 前端静态件(仓库根下 ✓)
STORE = CompanionStore()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):          # 静音(别刷屏 ✓)
        pass

    # ---------------- 输出小工具 ----------------
    def _json(self, obj, code: int = 200) -> None:
        body = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _file(self, p: Path) -> None:
        if not p.exists():
            self._json({"err": f"没有这个文件: {p.name}"}, 404)
            return
        body = p.read_bytes()
        ctype = {"html": "text/html; charset=utf-8", "js": "application/javascript",
                 "css": "text/css"}.get(p.suffix.lstrip("."), "application/octet-stream")
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    # ---------------- 路由 ----------------
    def do_GET(self) -> None:                                    # noqa: N802
        u = urlparse(self.path)
        q = parse_qs(u.query)
        p = u.path

        if p in ("/", "/index.html"):
            self._file(ROOT / "index.html")
        elif p.startswith("/static/"):
            self._file(ROOT / p[len("/static/"):])
        elif p == "/api/deals":                                  # 历史牌局列表
            self._json({"deals": STORE.recent_deals(int(q.get("limit", ["20"])[0]))})
        elif p == "/api/game":                                   # 某局的流水 + 决策
            gid = q.get("gid", [""])[0]
            self._json({"gid": gid, "plays": STORE.plays_of(gid),
                        "remains": STORE.remains_of(gid), "decisions": STORE.decisions_of(gid)})
        elif p == "/api/live":                                   # 最新一局的实时视图
            deals = STORE.recent_deals(1)
            if not deals:
                self._json({"empty": True}); return
            g = deals[0]
            plays = STORE.plays_of(g["gid"])
            self._json({"gid": g["gid"], "hand": g["hand"], "ji_pai": g["ji_pai"],
                        "plays": plays, "remains": STORE.remains_of(g["gid"], last_only=True),
                        "decisions": STORE.decisions_of(g["gid"]),
                        "host": STORE.host_intent()})
        elif p == "/api/accuracy":                               # "记忆": 操作准确率
            self._json(STORE.accuracy(q.get("gid", [None])[0]))
        elif p == "/api/metrics":                                # ★ 策略指标(团队口径 + 整场 ✓)
            # 口径: 场均升级数(有符号, 主指标) / 头游率 / 双上率 / 被双下率 / **过A率**
            # 数据源: 只认**有结构化结算**的局(宁缺毋滥 ✓ 老记录不计, 不充数 ✓)
            try:
                from landlord_counter.companion import metrics as M
                rep = M.from_store(STORE, game_type=q.get("game_type", ["guandan"])[0],
                                   limit=int(q.get("limit", ["200"])[0]))
            except Exception as e:                               # noqa: BLE001
                rep = {"err": f"{type(e).__name__}: {e}"}
            self._json({"metrics": rep})
        else:
            self._json({"err": "unknown", "path": p}, 404)

    def do_POST(self) -> None:                                   # noqa: N802
        if urlparse(self.path).path != "/api/host":
            self._json({"err": "unknown"}, 404)
            return
        n = int(self.headers.get("Content-Length") or 0)
        try:
            body = json.loads(self.rfile.read(n) or b"{}")
        except Exception:                                        # noqa: BLE001
            body = {}
        on = bool(body.get("on"))
        STORE.set_host_intent(on)
        self._json({"ok": True, "host": on})


def main() -> None:
    port = int(os.getenv("COMPANION_PORT", "8131"))
    print(f"[companion] 伴随应用服务 → http://127.0.0.1:{port}/  (库: {STORE.path})", flush=True)
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()


if __name__ == "__main__":
    main()

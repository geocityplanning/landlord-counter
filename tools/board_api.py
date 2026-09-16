"""牌局数据服务(后台可查): 追溯出牌历史 / 池子里还剩什么。

启动: cd /project1/landlord-counter && PYTHONPATH=src python3 tools/board_api.py [端口, 默认 8130]

接口:
  GET /health                     存活
  GET /games                      牌局列表
  GET /games/{id}                 概览(座位/各家已出/池子/最近 20 手)
  GET /games/{id}/history?seat=南  逐手记录: 谁、何时、打了什么牌(含"不出")
  GET /games/{id}/pool            池子里还剩哪些牌(未见牌, 按点数)
  GET /games/{id}/timeline?limit= 完整事件流(可回放)
  GET /games/{id}/export.csv      导出逐手记录

数据来自 platform/game_log.GameLog 的追加式 JSONL(默认 data/games/<id>.jsonl),
进程重启后自动从磁盘恢复 —— 所以历史可长期追溯。
"""
from __future__ import annotations

import csv
import io
import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from landlord_counter.platform.game_log import DATA_DIR, GameLog, list_games   # noqa: E402
from landlord_counter.platform.usage import UsageMeter   # noqa: E402

CACHE: dict = {}


def get_log(gid: str) -> GameLog | None:
    if gid in CACHE:
        return CACHE[gid]
    p = os.path.join(DATA_DIR, f"{gid}.jsonl")
    if not os.path.exists(p):
        return None
    log = GameLog(game_id=gid).load()
    CACHE[gid] = log
    return log


class Handler(BaseHTTPRequestHandler):
    def _send(self, obj, code: int = 200, ctype: str = "application/json") -> None:
        body = obj if isinstance(obj, (bytes, str)) else json.dumps(obj, ensure_ascii=False, indent=1)
        data = body.encode("utf-8") if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", f"{ctype}; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *a) -> None:      # 静音(避免刷屏)
        pass

    def do_POST(self) -> None:              # noqa: N802  (计量上报确认: 底座收到后回执)
        parts = [p for p in urlparse(self.path).path.split("/") if p]
        n = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(n) if n else b"{}"
        try:
            obj = json.loads(body or b"{}")
        except Exception:                    # noqa: BLE001
            obj = {}
        if parts[:2] == ["usage", "ack"]:
            return self._send({"ok": True, "acked": UsageMeter().ack(obj)})
        return self._send({"error": "not found"}, 404)

    def do_GET(self) -> None:               # noqa: N802
        u = urlparse(self.path)
        q = parse_qs(u.query)
        parts = [p for p in u.path.split("/") if p]
        try:
            if u.path in ("/", "/health"):
                return self._send({"ok": True, "data_dir": DATA_DIR, "games": len(list_games())})
            if parts and parts[0] == "usage":
                m = UsageMeter()
                if len(parts) == 1:
                    since = float((q.get("since") or ["0"])[0]) or None
                    return self._send(m.summary(since=since))
                if parts[1] == "batch":
                    return self._send(m.batch())
                if parts[1] == "events":
                    return self._send({"events": m.pending()[-200:]})
                return self._send({"error": f"未知子路径 {parts[1]}"}, 404)
            if parts and parts[0] == "games":
                if len(parts) == 1:
                    return self._send({"games": list_games()})
                gid = parts[1]
                log = get_log(gid)
                if log is None:
                    return self._send({"error": f"未找到牌局 {gid}"}, 404)
                if len(parts) == 2:
                    return self._send(log.to_dict())
                sub = parts[2]
                if sub == "history":
                    seat = (q.get("seat") or [None])[0]
                    limit = int((q.get("limit") or ["500"])[0])
                    return self._send({"game_id": gid, "seat": seat,
                                       "history": log.history(seat=seat, limit=limit)})
                if sub == "pool":
                    return self._send({"game_id": gid, "pool": log.pool(),
                                       "seat_remaining": log.seat_remaining(),
                                       "my_hand": dict(log.my_hand)})
                if sub == "timeline":
                    limit = int((q.get("limit") or ["1000"])[0])
                    return self._send({"game_id": gid, "events": log.events[-limit:]})
                if sub == "export.csv":
                    buf = io.StringIO()
                    w = csv.writer(buf)
                    w.writerow(["seq", "t", "seat", "action", "cards", "hand_left"])
                    for h in log.history(limit=100000):
                        w.writerow([h["seq"], h["t"], h["seat"], h["action"],
                                    " ".join(h["cards"]), h.get("hand_left", "")])
                    return self._send(buf.getvalue(), ctype="text/csv")
                return self._send({"error": f"未知子路径 {sub}"}, 404)
            return self._send({"error": "not found", "paths": ["/games", "/games/{id}",
                                                              "/games/{id}/history", "/games/{id}/pool",
                                                              "/games/{id}/timeline", "/games/{id}/export.csv"]}, 404)
        except Exception as e:  # noqa: BLE001
            return self._send({"error": f"{type(e).__name__}: {e}"}, 500)


def main() -> None:
    port = int(sys.argv[1]) if len(sys.argv) > 1 else int(os.getenv("BOARD_API_PORT", "8130"))
    srv = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    print(f"▶ 牌局数据服务: http://0.0.0.0:{port}/  (数据目录 {DATA_DIR})", flush=True)
    srv.serve_forever()


if __name__ == "__main__":
    main()

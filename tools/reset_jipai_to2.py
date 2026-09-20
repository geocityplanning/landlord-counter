#!/usr/bin/env python3
"""先改存档, 立刻刷新(不给页面存盘的机会) → 级牌才会真的回到 2"""
import subprocess
import sys
import time

sys.path.insert(0, "/project1/landlord-counter/src")
from landlord_counter.platform.cdp import CDP  # noqa: E402

c = CDP()
c.find_truth()

# ① 改存档到 2
v = c.eval_js('(() => { const s = JSON.parse(localStorage.getItem("guandan_settings")||"{}");'
              ' s.jiPai = 2; s.matchGames = 0;'
              ' localStorage.setItem("guandan_settings", JSON.stringify(s)); return s.jiPai; })()')
print("改后:", v)

# ② **立刻**刷新(同一口气里做, 不给页面结算存盘的机会 ✓)
try:
    c.eval_js("location.reload(); 1")
except Exception:  # noqa: BLE001
    pass
time.sleep(6)

c2 = CDP()
c2.find_truth()
print("刷新后存档:", c2.eval_js('localStorage.getItem("guandan_settings")'))

# ③ 回对局
r = subprocess.run([sys.executable, "tools/guandan_prep.py"],
                   cwd="/project1/landlord-counter", capture_output=True, text=True, timeout=280)
print("\n".join((r.stdout or "").strip().splitlines()[-2:]))

# ④ 验证
c3 = CDP()
c3.find_truth()
t = c3.truth() or {}
print(f"真值: phase={t.get('phase')} jiPai={t.get('jiPai')} (2=打2) 手牌={len((t.get('handsFull') or {}).get('0') or [])}张")

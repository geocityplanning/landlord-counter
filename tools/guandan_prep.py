#!/usr/bin/env python3
"""掼蛋进桌准备(幂等): 确保 www 服务在跑 → 重开浏览器页 → 点开始游戏直到进局。

用法: python3 tools/guandan_prep.py
"""
import subprocess
import sys
import time

sys.path.insert(0, "/project1/landlord-counter/src")

ADB = ["adb", "-s", "127.0.0.1:5555"]
URL = "http://172.18.0.1:8123/index.html"


def sh(*args):
    return subprocess.run(ADB + list(args), capture_output=True)


def main() -> int:
    from landlord_counter.guandan.agent import gold_button, snap, tap

    # 1) 确保 www 服务(幂等脚本)
    subprocess.run(["bash", "/project1/landlord-counter/tools/serve_guandan.sh"], capture_output=True)
    # 2) 重开浏览器(避免 Gecko 长时间运行后不响应点击)
    sh("shell", "am", "force-stop", "org.mozilla.focus")
    time.sleep(2)
    sh("shell", "am", "start", "-a", "android.intent.action.VIEW", "-d", URL)
    time.sleep(12)
    # 3) 若在开始/结算页 → 点大金钮(最多 3 次)
    for i in range(6):
        img = snap()
        if img is None:
            time.sleep(1)
            continue
        gb = gold_button(img)
        if gb:
            print(f"[prep] 点大金钮{gb} (i={i})", flush=True)
            tap(gb[0], gb[1], wait=3.0)
            continue
        break
    print("[prep] 完成", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())

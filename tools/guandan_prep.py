#!/usr/bin/env python3
"""掼蛋进桌准备 v2(幂等+可用性校验): 确保服务 → 重开页 → 校验页面真的可用 → 点开始。

页面"可用"判据(任一): ①大金钮(开始/再接一局) ②对局内按钮行(提示/出牌/不出)或我方手牌白卡
若连续不可用 → force-stop 重开(最多 3 轮)。返回 0=可用, 2=不可用(仍继续交给托管自愈)。
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
    from landlord_counter.guandan import percept as P
    from landlord_counter.guandan.agent import gold_button, snap, tap

    subprocess.run(["bash", "/project1/landlord-counter/tools/serve_guandan.sh"], capture_output=True)

    for rnd in range(3):
        sh("shell", "am", "force-stop", "org.mozilla.focus")
        time.sleep(2)
        sh("shell", "am", "start", "-a", "android.intent.action.VIEW", "-d", URL)
        time.sleep(12)
        for i in range(10):
            img = snap()
            if img is None:
                time.sleep(1)
                continue
            gb = gold_button(img)
            if gb:  # 开始页/结算页 → 点进局
                print(f"[prep] 点大金钮{gb} (轮{rnd} i={i})", flush=True)
                tap(gb[0], gb[1], wait=3.0)
                continue
            n = P.hand_columns(img)
            if n >= 1 or P.lifted_px(img) > 500:  # 对局中(有手牌/有选中)
                print(f"[prep] 已在对局内(手牌{n}) (轮{rnd})", flush=True)
                return 0
            if i >= 4:  # 多次都既无按钮又无手牌 → 判页面坏
                print(f"[prep] 页面不可用(轮{rnd} i={i}), 重开", flush=True)
                break
            time.sleep(1.5)
    print("[prep] 3 轮仍不可用 → 交给托管自愈", flush=True)
    return 2


if __name__ == "__main__":
    sys.exit(main())

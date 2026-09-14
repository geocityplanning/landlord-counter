"""麻将(電脳麻将)输入通道探针 —— 换承载(Bromite) + 新旧轮次判据对照。

用法: PYTHONPATH=src python3 tools/probe_mahjong.py [秒数]
输出: 手牌/操作按钮/轮次判定 + 每种输入通道(ENTER / 点击)的回执对照。
"""
import sys
import time

sys.path.insert(0, "src")
from landlord_counter.platform.a11y import A11y  # noqa: E402
from landlord_counter.platform.device import AdbDevice  # noqa: E402
from landlord_counter.platform.games.mahjong_adapter import ACTION_TEXTS, HAND_Y0, HAND_Y1  # noqa: E402

URL = "http://172.18.0.1:8124/index.html"
DUR = int(sys.argv[1]) if len(sys.argv) > 1 else 240

d = AdbDevice()
a = A11y(d.serial if hasattr(d, "serial") else "127.0.0.1:5555", ttl=0)


def snap():
    nodes = a.dump(force=True)
    hand = [n for n in nodes if n.cls.endswith("Button") and HAND_Y0 <= n.center[1] <= HAND_Y1
            and n.text.strip() and n.text.strip() not in ACTION_TEXTS]
    acts = [n for n in nodes if n.cls.endswith("Button") and (n.text or "").strip() in ACTION_TEXTS
            and not (HAND_Y0 <= n.center[1] <= HAND_Y1)]
    others = [n.text.strip() for n in nodes if n.text.strip() not in ACTION_TEXTS][:6]
    return hand, acts, others


def describe():
    hand, acts, others = snap()
    n = len(hand)
    return n, [h.text for h in hand], [x.text.strip() for x in acts], others


# 1) 开页面
d.shell("am", "force-stop", "org.bromite.bromite")
time.sleep(2)
d.shell("am", "start", "-a", "android.intent.action.VIEW", "-d", URL,
        "-n", "org.bromite.bromite/com.google.android.apps.chrome.Main")
time.sleep(20)

n, names, acts, others = describe()
print(f"[载入] 手牌{n} 提示{acts} 其他{others}", flush=True)

# 2) 标题页 → START(页面加载有延迟: 最多等 60s)
for _i in range(20):
    try:
        st = a.button("START")
    except Exception:  # noqa: BLE001
        st = None
    if st:
        print(f"[START] 点击 {st.center}", flush=True)
        d.tap(*st.center, wait=2.0)
        time.sleep(8)
        break
    time.sleep(3)
else:
    print("[START] 60s 内未出现 START(页面可能没加载)", flush=True)

# 3) 主循环: 轮到我(张数 % 3 == 2)时测两种输入通道
t_end = time.time() + DUR
stats = {"enter_ok": 0, "enter_fail": 0, "tap_ok": 0, "tap_fail": 0, "turns": 0}
while time.time() < t_end:
    n, names, acts, others = describe()
    my_turn = n >= 2 and n % 3 == 2
    print(f"[{time.strftime('%H:%M:%S')}] 手牌{n}(mod3={n % 3}) 提示{acts} {'★我出手' if my_turn else ''}", flush=True)
    if acts:
        tgt = next(x for x in snap()[1] if x.text.strip() == "キャンセル") if any(x.text.strip() == "キャンセル" for x in snap()[1]) else None
        if tgt:
            print(f"   → 点取消 {tgt.center}", flush=True)
            d.tap(*tgt.center, wait=1.2)
            time.sleep(1.2)
            n2, names2, acts2, _ = describe()
            print(f"   回执: 手牌{n2} 提示{acts2}", flush=True)
            continue
    if not my_turn:
        time.sleep(2.5)
        continue
    stats["turns"] += 1
    # 通道A: ENTER(键盘)
    d.shell("input", "keyevent", "66")
    time.sleep(1.2)
    n_a, names_a, _, _ = describe()
    if n_a != n:
        stats["enter_ok"] += 1
        print(f"   ✅ ENTER 生效: {n}→{n_a} {names[:6]}", flush=True)
        continue
    stats["enter_fail"] += 1
    # 通道B: 点击该牌
    tile = snap()[0][-1]
    print(f"   ✗ ENTER 未生效 → 试点 {tile.text}{tile.center}", flush=True)
    d.tap(*tile.center, wait=1.2)
    time.sleep(1.2)
    n_b, names_b, _, _ = describe()
    if n_b != n:
        stats["tap_ok"] += 1
        print(f"   ✅ 点击生效: {n}→{n_b}", flush=True)
    else:
        stats["tap_fail"] += 1
        print(f"   ✗ 点击也未生效 ({n}→{n_b})", flush=True)
        time.sleep(2.0)

print(f"[汇总] 轮到我 {stats['turns']} 次 | ENTER 生效 {stats['enter_ok']}/失败 {stats['enter_fail']} | 点击 生效 {stats['tap_ok']}/失败 {stats['tap_fail']}", flush=True)

#!/usr/bin/env python3
"""国标麻将(guobiao-majiang) 进桌 prep: 横屏 → 开页 → 登录 → 建房 → 补机器人 → 准备。

实测结论(2026-09-14):
- 本页**触控可用**(点「隐藏提示」能切换) → 优先按无障碍文字查坐标点击;
- 键盘兜底: 输入昵称 + Enter 提交; Tab 聚焦 + Enter 激活按钮(platform/keyboard.py);
- ⚠️ 必须横屏(user_rotation=1), 竖屏会被页面提示"请将手机横屏"。

返回 0=已进局/可托管, 2=未就绪(交给上层自愈)。
"""
import os
import subprocess
import sys
import time

sys.path.insert(0, "/project1/landlord-counter/src")

SERIAL = os.getenv("ANDROID_SERIAL", "127.0.0.1:5555")
URL = os.getenv("GBM_URL", "http://172.18.0.1:8125/")
BROWSER = os.getenv("BROWSER_PKG", "org.bromite.bromite")
BROWSER_ACT = os.getenv("BROWSER_ACT", "com.google.android.apps.chrome.Main")
NAME = os.getenv("GBM_NAME", "bot")


def adb(*args, timeout: int = 30):
    return subprocess.run(["adb", "-s", SERIAL, *args], capture_output=True, timeout=timeout)


def main() -> int:
    from landlord_counter.platform.a11y import A11y
    from landlord_counter.platform.device import AdbDevice
    from landlord_counter.platform.keyboard import activate

    dev = AdbDevice(serial=SERIAL)
    a = A11y(SERIAL, ttl=0)

    def tap_text(text: str, wait: float = 1.5) -> bool:
        """按文字找节点并点击(触控可用时首选)。"""
        n = a.any_node(text)
        if not n:
            for x in a.dump(force=True):
                if text.replace(" ", "") in (x.text or "").replace(" ", ""):
                    n = x
                    break
        if not n:
            return False
        dev.tap(*n.center, wait=wait)
        return True

    def texts() -> list[str]:
        return [x.text.strip() for x in a.dump(force=True) if x.text and x.text.strip()]

    # 1) 横屏
    adb("shell", "settings", "put", "system", "accelerometer_rotation", "0")
    adb("shell", "settings", "put", "system", "user_rotation", "1")
    time.sleep(2)

    def on_table() -> bool:
        t = " ".join(texts())
        return "该你出牌" in t or "余 " in t or "轮到：" in t

    if on_table():
        print("[prep] 已在对局内")
        return 0

    # 2) 开页
    adb("shell", "am", "force-stop", BROWSER)
    time.sleep(2)
    adb("shell", "am", "start", "-a", "android.intent.action.VIEW", "-d", URL, "-n", f"{BROWSER}/{BROWSER_ACT}")
    for _ in range(20):
        time.sleep(2)
        if a.any_node("进入大厅") or a.any_node("＋ 创建房间") or on_table():
            break
    texts_now = texts()
    print(f"[prep] 页面: {texts_now[:6]}")

    # 3) 登录(昵称 + Enter)
    if a.any_node("进入大厅"):
        ed = next((x for x in a.dump(force=True) if x.cls.endswith("EditText") and x.box[1] > 200), None)
        if ed:
            dev.tap(*ed.center, wait=0.8)
        dev.shell("input", "text", NAME)
        time.sleep(0.8)
        dev.shell("input", "keyevent", "66")          # 输入框 keydown Enter → 登录
        time.sleep(3)
        if not a.any_node("＋ 创建房间"):
            tap_text("进入大厅", wait=2.0)
            time.sleep(3)
        print(f"[prep] 登录后: {texts()[:6]}")

    # 4) 建房
    for _ in range(6):
        if a.any_node("＋ 创建房间"):
            tap_text("＋ 创建房间", wait=1.5) or activate(dev, a, "创建房间")
            time.sleep(1.5)
            tap_text("创建", wait=2.5) or activate(dev, a, "创建")
            time.sleep(3)
        t = " ".join(texts())
        if "添加机器人" in t or "准备" in t or on_table():
            break
        time.sleep(2)
    print(f"[prep] 进房后: {texts()[:8]}")

    # 5) 补满机器人(4 人) + 准备
    for i in range(6):
        t = " ".join(texts())
        if on_table():
            break
        if "添加机器人" in t:
            tap_text("添加机器人", wait=2.0) or activate(dev, a, "添加机器人")
            time.sleep(2.0)
            continue
        if "准备" in t:
            tap_text("准备", wait=2.5) or activate(dev, a, "准备")
            time.sleep(3)
            break
        time.sleep(2)
    print(f"[prep] 准备后: {texts()[:10]}")

    # 6) 等开局
    for _ in range(12):
        if on_table():
            print("[prep] ✅ 已开局")
            return 0
        time.sleep(3)
    print("[prep] ⚠️ 未确认开局(交给托管自愈)")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

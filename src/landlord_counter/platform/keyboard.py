"""键盘驱动(无触控环境下的通用网页驱动)。

背景: 这个 redroid 容器里 **touch 对网页常常整体失灵**(点击后帧差 0.00),
而键盘通道可用(实测国标麻将: 输入昵称 + Enter 能登录)。
Chrome 支持 Tab 键在可聚焦控件间移动焦点 → 用"Tab 到目标 + Enter"可确定性激活任意按钮,
不需要知道坐标、也不依赖触控。
"""
from __future__ import annotations


def focused_texts(a11y) -> list[str]:
    """当前所有"焦点"节点的文字。

    注意: 无障碍树里**会有多个 focused=true**(外层 WebView 容器 + 真正获得焦点的控件),
    只能看第一个会误判(实测: WebView 总报 focused → 永远匹配不上目标按钮)。
    这里过滤掉容器类, 返回真正可聚焦控件的文字列表。
    """
    out = []
    for n in a11y.focused():
        cls = n.cls.split(".")[-1]
        if cls in ("WebView", "FrameLayout", "LinearLayout", "ViewGroup", "View", "HtmlView"):
            continue
        t = (n.text or "").strip()
        if t:
            out.append(t)
    return out


def focused_text(a11y) -> str:
    t = focused_texts(a11y)
    return t[-1] if t else ""


def activate(dev, a11y, text: str, max_tabs: int = 30, wait: float = 0.45) -> bool:
    """Tab 逐个聚焦, 命中 `text`(去空格包含匹配) 后按 Enter。返回是否命中。"""
    want = text.replace(" ", "")
    if want and any(want in t.replace(" ", "") for t in focused_texts(a11y)):
        dev.shell("input", "keyevent", "66")
        return True
    for _ in range(max_tabs):
        dev.shell("input", "keyevent", "61")        # TAB
        try:
            import time

            time.sleep(wait)
        except Exception:  # noqa: BLE001
            pass
        if want and any(want in t.replace(" ", "") for t in focused_texts(a11y)):
            dev.shell("input", "keyevent", "66")    # ENTER
            return True
    return False


def press_tab(dev, n: int = 1, wait: float = 0.4) -> None:
    import time

    for _ in range(n):
        dev.shell("input", "keyevent", "61")
        time.sleep(wait)


def press(dev, key: str) -> None:
    dev.shell("input", "keyevent", str(key))

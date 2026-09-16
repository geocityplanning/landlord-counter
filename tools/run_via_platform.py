#!/usr/bin/env python3
"""通过 platform 通用层跑托管(首个适配器: 掼蛋)。

用法: PYTHONPATH=src python3 tools/run_via_platform.py [秒数] [guandan|fake]
"""
import os
import sys

sys.path.insert(0, "/project1/landlord-counter/src")


def main() -> int:
    secs = float(sys.argv[1]) if len(sys.argv) > 1 else 300.0
    name = sys.argv[2] if len(sys.argv) > 2 else "guandan"

    from landlord_counter.platform.device import AdbDevice

    dev = AdbDevice(serial="127.0.0.1:5555", url="http://172.18.0.1:8123/index.html")

    vision = None
    try:
        from landlord_counter.config import load_config
        from landlord_counter.vision.card_recognizer import CardRecognizer

        vision = CardRecognizer(load_config().vision)
    except Exception as e:  # noqa: BLE001
        print(f"[warn] 识别器未就绪: {e}")

    from landlord_counter.platform import registry

    if name not in registry.names():
        raise SystemExit(f"未知适配器: {name} (可选: {', '.join(registry.names())})")
    ad = registry.create(name)

    # 打开该游戏自己的页面(适配器 start_url), 再交给运行时进桌/托管
    if getattr(ad, "start_url", None):
        # 已在牌局里就**不要重开页面**: 重开会丢掉进行中的牌局 →
        # 接着"开始按钮"又认不出来 → 整轮 0 动作(2026-09-16 实测的元凶)。
        in_deal = False
        try:
            f0 = dev.snap()
            from landlord_counter.guandan import percept as P

            in_deal = bool(P.hand_is_real(f0)[0])
        except Exception:  # noqa: BLE001
            in_deal = False
        if in_deal:
            print("↻ 检测到已在牌局中 → 不重开页面(保护进行中的牌局)")
        else:
            print(f"↻ 打开页面: {ad.start_url}")
            dev.recover(package=getattr(ad, "package", None), url=ad.start_url)

    from landlord_counter.platform.runtime import Runtime

    rt = Runtime(ad, dev, vision=vision,
                 stats_path=os.getenv("STATS_FILE"), tag=os.getenv("STATS_TAG", "plat"))
    print(f"▶ platform 运行时启动: adapter={ad.name} ours={getattr(ad, 'ours', None)} 时长={secs}s")
    out = rt.run(seconds=secs)
    print(f"▶ 结束: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

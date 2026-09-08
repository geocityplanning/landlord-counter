"""douzero_bridge 冒烟: 合成状态决策, 断言合法性 + 计时。"""
import time

from landlord_counter.logic import ddz_engine as E
from landlord_counter.logic.douzero_bridge import DouZeroBot, seat_role

W = "/tmp/dz_w"
bot = DouZeroBot(W)
print("可用:", bot.available())

HAND = ['3', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'Q',
        'K', 'K', 'A', 'A', '2', '2', '小', '大']
COUNTS_LD = {"landlord": 20, "landlord_up": 17, "landlord_down": 17}   # 我做地主
COUNTS_FM = {"landlord": 17, "landlord_up": 17, "landlord_down": 20}  # 例: 我=down(20张?不对)

print("\n== 座位角色 ==")
for ld in ("human", "B", "A"):
    print(f"地主={ld}: human→{seat_role(ld,'human')} B→{seat_role(ld,'B')} A→{seat_role(ld,'A')}")

print("\n== 决策1: 地主领打(无上家) ==")
t0 = time.time()
out = bot.decide("landlord", HAND, COUNTS_LD, {}, None, can_pass=False)
dt = time.time() - t0
print(f"  选择: {out} ({dt*1000:.0f}ms)")
if out:
    g = E.identify_str(out)
    assert not g.is_invalid, "非法牌型!"
    assert all(HAND.count(t) >= out.count(t) for t in set(out)), "含手牌外牌!"
print("  合法性 ✓")

print("\n== 决策2: 农民压 对K ==")
last = ['K', 'K']
t0 = time.time()
out2 = bot.decide("landlord_down", HAND[:-3], COUNTS_FM, {}, last, can_pass=True)
dt = time.time() - t0
print(f"  选择: {out2} ({dt*1000:.0f}ms)")
if out2:
    g = E.identify_str(out2)
    lk = E.identify_str(last)
    ok_beat = E.is_valid_play(g, lk)
    assert ok_beat, f"压不过对K: {out2}"
    print("  合法且压过对K ✓")
else:
    print("  选择不出(pass) — 合法")
print("\n全通过")

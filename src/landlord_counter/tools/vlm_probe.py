"""VLM 提供商探针: 对同一张真实截图比对各家视觉模型的识别准确率。

用法:
  uv run python -m landlord_counter.tools.vlm_probe <provider> <截图> <真值(逗号分隔)>
例:
  uv run python -m landlord_counter.tools.vlm_probe deepseek /tmp/ddz_cur.png 5,5,6,7,7,8,9,9,10,J,Q,Q,K,A,2,2,BJ
说明: provider ∈ zhipu/deepseek/doubao/qianfan; .env 需有对应 key/模型。
"""
from __future__ import annotations

import sys
import time

import cv2

from landlord_counter.config import _load_dotenv, load_config
from landlord_counter.logic import ddz_engine as E
from landlord_counter.vision.card_recognizer import CardRecognizer

_load_dotenv()


def main() -> None:
    if len(sys.argv) < 4:
        print(__doc__)
        sys.exit(1)
    provider, img_path, truth_csv = sys.argv[1], sys.argv[2], sys.argv[3]
    truth = sorted(E.token_to_rank(t) for t in truth_csv.split(",") if t.strip())

    import os

    os.environ["VLM_PROVIDER"] = provider
    cfg = load_config()
    v = cfg.vision
    print(f"▶ provider={provider}  base={v.vlm_api_base}  model={v.vlm_model}  key={'有' if v.vlm_api_key else '无'}")
    if not v.vlm_available():
        print("✗ 未配置完整(key/model), 跳过")
        sys.exit(2)
    rec = CardRecognizer(v)
    img = cv2.imread(img_path)
    if img is None:
        print(f"✗ 读图失败: {img_path}")
        sys.exit(2)
    t0 = time.time()
    tokens = rec.read_hand_vlm(img, expected=len(truth))
    dt = time.time() - t0
    if not tokens:
        print("✗ VLM 返回空(额度/模型名/格式问题?)")
        sys.exit(3)
    got = sorted(E.token_to_rank(t) for t in tokens)
    # 多集逐张差
    miss = [r for r in truth if truth.count(r) > got.count(r)]
    extra = [r for r in got if got.count(r) > truth.count(r)]
    exact = miss == [] and extra == [] and len(got) == len(truth)
    per_card = 1 - (sum(max(0, truth.count(r) - got.count(r)) for r in set(truth)) + sum(max(0, got.count(r) - truth.count(r)) for r in set(got))) / len(truth)
    print(f"  真值({len(truth)}): {[E.rank_to_token(r) for r in truth]}")
    print(f"  读出({len(got)}):  {[E.rank_to_token(r) for r in got]}")
    print(f"  漏读: {[E.rank_to_token(r) for r in miss]}  多报: {[E.rank_to_token(r) for r in extra]}")
    print(f"  结果: {'✅ 完全一致' if exact else '❌ 有差'} | 逐张正确率 {per_card:.0%} | 耗时 {dt:.1f}s")
    sys.exit(0 if exact else 3)


if __name__ == "__main__":
    main()

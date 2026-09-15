# 上游来源: MonadMorph/guandan-RL

- **仓库**: https://github.com/MonadMorph/guandan-RL
- **拉取方式**: `curl -sL https://api.github.com/repos/MonadMorph/guandan-RL/tarball`
  (ECS 上 github.com 直连不通, 走 api.github.com tarball)
- **许可**: ⚠️ **仓库未声明 LICENSE** → 仅内部研究/演示使用; 对外发布前须联系作者或替换
- **内容**: Transformer + PPO 自对弈掼蛋智能体(约 45 万参数), 自评对自身早期版本
  胜率 57~63%(README 表格), 对随机策略 98% —— 属"社区中等强度 RL", 非 SOTA
- **权重**: `Bests/policy_value_net_{300,700,1000}.pt` (各 1.8MB, 随仓库发布)
  - 1000 = 训练 1000 epoch, 三档中最新, 本项目默认用它

## ⚠️ 权重与代码版本不一致(已解决)

仓库现版 `policy.py::PolicyValueNet` 是 **MLP 骨干**(输入 128 维展平向量),
而 `Bests/*.pt` 里的权重是 **旧版 Transformer 骨干**(20 个状态 token)。
直接 `PolicyValueNet(...).load_state_dict(...)` 会因维度不匹配报错。

**本项目做法**(见 `src/landlord_counter/guandan/rl_policy.py::GTNet`):
按 checkpoint 实测维度复刻结构(手牌 16 / 16×历史 16 / 余牌 5 / 上家 16 / 座位 4),
`strict=True` 加载通过(参数量 453,113), 并用作者 `deck.py`/`policy.py` 的编码规范
还原 20 个 token 的语义。

## 状态编码规范(从作者代码还原)

| token | 维度 | 含义 |
|---|---|---|
| 0 | 16 | 手牌: 15 个牌值计数(/8) + [同花可成组数] |
| 1..16 | 16×16 | 历史出牌(最近 16 手): 4 玩家 one-hot + 11 牌型 one-hot(含炸弹位) + rank/14 |
| 17 | 5 | 余牌: [我方, 下家, 对家, 上家, 合计](/108) |
| 18 | 16 | 上家最近一手: 同历史 token 结构 |
| 19 | 4 | 我方座位 one-hot |

牌值顺序(`orderofRanks`): `3 4 5 6 7 8 9 10 J Q K A 2 小王 大王` (与我们 zhi 的映射见 `ZHI_TO_THEIR`)。
动作空间 120: 各牌型段(15/15/13/10/8/11/13/13/8/13) + pass(119); 段下标见 `TYPE_SEG`。

## 本项目用法

```bash
GUANDAN_OURS=1 GUANDAN_DECIDE=rl ... python3 -u -m landlord_counter.guandan.agent 600
```

决策 = 我们用自家规则引擎枚举合法候选 → 模型在这批候选里打分选一个(或不出) →
执行层**点选直出**(因为打的是我们自己选的牌, 游戏"提示"只会出它自己选的牌)。

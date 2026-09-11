# 文档索引（landlord-counter）

## 斗地主（M0-M3，已闭环）
- `../README.md` — 项目总览（记牌器 + AI 托管 demo）
- 交付/里程碑细节见 git log 与 `reference/` 下上游源码

## 掼蛋（M4，进行中）
| 文档 | 内容 |
|---|---|
| `M4_掼蛋规划.md` | 选型（开源 guandan）、与斗地主差异表、M4a–M4f 分阶段与风险 |
| `M4_掼蛋几何参考.md` | 实测几何/配色/交互语义、标定值（手牌带/按钮/抬起系数/像素数牌）、运行要点与已知问题 |
| `M4c_集成设计.md` | 感知→决策→执行 三段设计；自研决策接入与回退策略 |
| `M4_进展_20260911.md` | 首夜数据（81 局/头游率 40%）、窗口失败根因与修复、A/B 设计、M4e 策略增强四项 |

## 演示（M5）
| 文档 | 内容 |
|---|---|
| `M5_演示包.md` | 一页演示材料：能力、一键演示命令、讲述线、已验证指标、技术要点、合规边界 |
| `media/demo_guandan_20260911.mp4` | 92 秒实拍（自动进局→出牌→结算→续局） |

## 参考代码（参考/第三方）
- `../reference/guandan/` — 上游掼蛋源码（www + config + APK）与来源说明 `UPSTREAM.md`
- `../reference/guandan/www/js/*.js` — 我们规则/AI 移植的权威来源（gameRules/aiLogic/teamLogic/cardUI）

## 技能库（Hermes 侧，非仓库）
- `cloud-phone-game-automation`（SKILL.md 铁律 1–22）
  - `references/wishday-ddz.md` — 斗地主实测几何/常量/引擎移植坑
  - `references/guandan-m4.md` — 掼蛋实况/API/指标/遗留
  - `references/web-game-hosting-on-redroid.md` — 网页游戏托管与排障（Focus 路线、APK 装挂 adbd 恢复、gh-proxy 下载）
  - `references/vlm-providers.md` — VLM 多商配置/成本/故障码/推理参数调优

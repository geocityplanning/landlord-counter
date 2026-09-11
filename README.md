# 🃏 Landlord Counter — 斗地主记牌器（RPA + 大模型）

基于 **ADB 截屏 + 模板匹配识别 + 大模型推理** 的斗地主记牌器。
识别手机/模拟器中的斗地主牌面，自动记牌，可选接入大模型分析对手牌型。

> ⚠️ 合规提示：仅用于记牌辅助（人脑决策），**不要**用于自动出牌等作弊场景，联机竞技请遵守平台规则。

## 🏗️ 架构

```
┌─────────────┐   ┌──────────────┐   ┌───────────┐   ┌────────────┐
│  ADB 截屏   │ → │ 模板匹配识别  │ → │  记牌逻辑  │ → │ 大模型推理  │
│  (手机/模拟器)│   │ (OpenCV掩码) │   │ (54张追踪) │   │ (可选)     │
└─────────────┘   └──────────────┘   └───────────┘   └────────────┘
```

## ☁️ 云手机 AI 托管（平台方向 · 进行中）

本仓库同时是**云手机 + 通用 GUI 托管**能力的试验场：在云手机（redroid）里跑真实手游，AI 纯"看图 → 决策 → 点屏"，不注入、不改客户端，无人值守连续对局并自动统计战绩。

- 已验证：斗地主（DouZero 决策托管）、掼蛋（开源 Web 版，自研规则+AI 决策，含夜跑统计与 A/B 对照）
- 一键演示：`bash tools/demo_guandan.sh 6 1 0`（进桌 + 托管 + 录屏）
- 文档：`docs/M5_演示包.md`（演示材料）、`docs/M4_进展_20260911.md`（数据与修复）、`docs/开发计划_通用GUI托管平台.md`

## 📁 目录结构

```
landlord-counter/
├── pyproject.toml            # uv 项目管理
├── assets/card_templates/    # 牌面模板（gen-templates 生成）
└── src/landlord_counter/
    ├── main.py               # 主程序入口
    ├── config.py             # 配置（环境变量读取密钥）
    ├── screen/adb_capture.py # ADB 截屏层
    ├── vision/card_recognizer.py  # 模板匹配 + VLM 兜底
    ├── logic/tracker.py      # 记牌逻辑（54张牌追踪/推理）
    ├── ai/analyzer.py        # 大模型分析（DeepSeek 等）
    └── tools/                # 工具：模板生成、自测
```

## 🚀 快速开始

```bash
# 1. 安装依赖（uv 管理）
uv sync

# 2. 生成牌面模板（PIL 绘制标准牌面）
uv run gen-templates

# 3. 连接手机：开启 USB 调试，确认设备可见
adb devices          # 应看到设备

# 4. 运行记牌器
uv run landlord-counter
```

## 🔧 配置（环境变量，或复制 `.env.example` 为 `.env`）

| 变量 | 说明 | 默认 |
|------|------|------|
| `ADB_SERIAL` | 设备序列号（多设备必填，如 127.0.0.1:5555） | 空(自动选唯一设备) |
| `GAME_PROFILE` | 游戏视觉适配包（`doudizhu_wishday`…） | `doudizhu_wishday` |
| `VLM_API_KEY` | **识别主链路**：视觉大模型密钥（智谱等） | 空（模板匹配兜底） |
| `VLM_API_BASE` | VLM 服务地址（智谱: open.bigmodel.cn/api/paas/v4） | 空 |
| `VLM_MODEL` | VLM 模型名（重度重叠画面建议 `glm-4v-plus`） | `glm-4v-plus` |
| `LLM_ENABLED` | 启用大模型牌型分析 | `0` |
| `LLM_API_KEY` | 大模型密钥 | 空 |
| `LLM_API_BASE` | 大模型 API 地址 | DeepSeek |
| `LLM_MODEL` | 分析模型 | `deepseek-v4-flash` |

> 识别双链路：模板匹配（OpenCV，本地免费）→ 失败/不适配时 **VLM 直读**（按
> `GAME_PROFILE` 定位手牌行→放大→视觉大模型读点数）。重度重叠画面（如 wishday 扇形牌）
> 直接走 VLM 主链路；`config.py` 会自动加载项目根 `.env`，无需手动 source。

示例：
```bash
export LLM_ENABLED=1
export LLM_API_KEY=sk-xxx
uv run landlord-counter
```

## 🛠️ 常见问题

- **识别不准**：不同游戏牌面风格不同，可用真实截图替换 `assets/card_templates/` 中的模板（保持文件名=点数）
- **手牌区域不对**：修改 `config.py` 中 `hand_roi` 归一化坐标
- **无设备**：`adb devices` 确认设备在线，模拟器需开启 ADB 端口
- **自测**：`uv run python -m landlord_counter.tools.self_test`

## 📊 输出示例

```
===== 第1局 记牌器 =====
地主: self
剩余牌: 3×4 4×4 5×2 6×3 ...
关键牌剩余: 2=4 A=3 K=4 BJ=1 RJ=0
left 可能持有: 2×2 A×1 K×2 ...
```

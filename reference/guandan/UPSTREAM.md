# 上游来源与说明（guandan 参考代码）

| 项 | 值 |
|---|---|
| 仓库 | https://github.com/yangfanconan/guandan |
| 分支/提交 | `main` @ `1c63af2614b4`（2026-02-27 最后推送） |
| 许可 | 上游仓库未声明 License（无 LICENSE 文件）→ 本目录**仅供项目内部学习/参考**，不对外分发 |
| 合并日期 | 2026-09-10 |
| 已并入 | `www/`（index.html + css + 7 个 js：gameRules/aiLogic/teamLogic/cardUI/main/sound/storage）、`config.xml`、`package.json`、`README.md`、`releases/guandan-v1.1-debug.apk` |
| 未并入 | `releases/guandan-v1.0-debug.apk`（旧版无保留价值）；如需可从上游 releases 下载 |

## 与我们代码的对应关系

| 上游文件 | 我们的使用 |
|---|---|
| `www/js/gameRules.js` | 已移植为 `src/landlord_counter/guandan/rules.py`（936 行，75 项测试） |
| `www/js/aiLogic.js` + `teamLogic.js` | 已移植为 `src/landlord_counter/guandan/ai.py`（choose_play 等） |
| `www/js/cardUI.js` / `main.js` | 几何/状态推导来源 → `docs/M4_掼蛋几何参考.md`（按钮/手牌带/选中抬起/轮次判据） |
| `www/`（整站） | 云手机托管用：ECS 上 `python3 -m http.server 8123` 服务本目录 www；手机端 Firefox Focus 打开 `http://172.18.0.1:8123/index.html` |
| `releases/*.apk` | 备用：直接 `adb install`（注：其 Cordova 用 https://localhost 资产加载器，在 redroid WebView 上加载失败，故不用 APK 路线） |

## 复现方式（如目录缺失）

```bash
curl -sL -o /tmp/guandan.tar.gz https://api.github.com/repos/yangfanconan/guandan/tarball
mkdir -p reference && tar xzf /tmp/guandan.tar.gz -C reference --strip-components=1
```

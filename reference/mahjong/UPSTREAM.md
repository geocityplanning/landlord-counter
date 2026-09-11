# 上游来源（麻将 · 電脳麻将）

- 仓库: https://github.com/kobalab/Majiang （作者 Satoshi Kobayashi / kobalab）
- 版本: v2.5.3（本次拉取 commit 31f8751）
- 许可: **MIT**（见同目录 LICENSE，允许分发与二次开发）
- 拉取方式: `curl -L https://api.github.com/repos/kobalab/majiang/tarball`（ECS 上 github.com 直连超时，走 api）
- 构建: `npm install --registry https://registry.npmmirror.com && npm run build` → 产物 `dist/`（本目录即 dist 内容）
- 用途: 云手机 GUI 托管平台的**第三款游戏（麻将）**适配器验收对象（四人完整规则 + 内置 CPU 对手）
- 交互: 轮到自家时点击手牌即打出；UI 由 npm 包 `majiang-ui` 以 canvas 绘制

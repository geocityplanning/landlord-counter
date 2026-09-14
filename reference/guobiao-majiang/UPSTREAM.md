# UPSTREAM：guobiao-majiang（网页版国标麻将）

- **上游**：https://github.com/guming-learning/guobiao-majiang
- **许可**：仓库**未声明 LICENSE**（⚠️ 因此本目录仅作**内部研究/演示**用途；对外发布前必须联系作者取得授权，或改用许可干净的替代品 `alexviolent/FishBallMahjong`(Apache-2.0)）
- **拉取方式**：ECS 上 github.com 直连超时 → 用 api tarball：
  `curl -sL https://api.github.com/repos/guming-learning/guobiao-majiang/tarball -o gbm.tar.gz`
- **技术栈**：Node.js + express + socket.io，**服务器权威**（牌局逻辑在服务端，前端是薄 UI），默认端口 3000（`PORT` 可覆盖）
- **规则**：中国标准麻将（MCR/国标），81 番种，8 番起胡，含花牌、吃/碰/明暗杠/加杠、抢杠和、自摸/点和、海底/妙手/杠上开花、流局；MCR 计分
- **为什么选它**：
  1. **单人可玩**——房间里一键「添加机器人」补满空位（自动化不需要凑真人）
  2. **手机横屏**响应式布局，CSS 绘制牌面（非 canvas → 无障碍树大概率可读）
  3. 完整算番，结算信息（番种/分数）自带，便于做统计

## 本地运行

```bash
cd reference/guobiao-majiang
npm install --registry https://registry.npmmirror.com --no-audit --no-fund
PORT=8125 node server.js        # 或 bash tools/serve_guobiao.sh
```
容器内访问：`http://172.18.0.1:8125/`

## 已验证 / 待验证

- [x] 源码可获取、依赖可装（express/socket.io，npmmirror 镜像）
- [ ] 服务起得来、页面可打开
- [ ] 无障碍树可读（昵称输入 / 创建房间 / 添加机器人 / 准备 / 手牌 / 吃碰杠和提示 / 结算番种）
- [ ] 手机横屏（redroid 需从 720×1280 竖屏切到横屏）
- [ ] 托管适配器（读牌→决策→出牌→应答→结算）

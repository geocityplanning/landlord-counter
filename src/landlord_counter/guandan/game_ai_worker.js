// game_ai_worker.js —— 把游戏本体 AI(aiLogic.js)包成一个常驻小服务
//
// 为什么用 node 常驻: 文件**原样搬运**(保真 ✓), 又不想每次决策都重启 node(慢 ✗)
//   协议: stdin 一行一个请求(JSON), stdout 一行一个回复(JSON) ✓
//
// 请求: {"hand": [[zhi,hua,id],...], "last": [[zhi,hua],...] 或 [], "lastSeat": 1,
//        "shiDuiYou": false, "jipai": 5, "nanDu": 2}
// 回复: {"cards": [[zhi,hua,id],...]}  或  {"guo": true}  或  {"error": "..."}
const path = require('path');
const DIR = path.join(__dirname, 'game_ai');
global.GameRules = require(path.join(DIR, 'gameRules.js'));
const AILogic = require(path.join(DIR, 'aiLogic.js'));

function toCards(arr, base) {
  return arr.map((c, i) => ({ zhi: c[0], hua: c[1], id: (c[2] === undefined ? base + i : c[2]) }));
}

function handle(q) {
  GameRules.sheZhiJiPai(q.jipai || 2);
  AILogic.sheZhiNanDu(q.nanDu || 2);

  const shouPai = toCards(q.hand || [], 0);
  let shangJia = null;
  const last = q.last || [];
  if (last.length) {
    const px = GameRules.jieXiPaiXing(toCards(last, 1000));
    shangJia = Object.assign({}, px, { chuPaiZhe: (q.lastSeat === undefined ? 1 : q.lastSeat) });
  }
  // 中等策略只用 (可出牌, 手牌) ⇒ gameState 给个合法壳即可 ✓
  const gs = {
    jiPai: q.jipai || 2, youCiList: [], benLunChuPai: {},
    zhaDanShu: 0, shangJiaPaiXing: shangJia, currentChuPaiZhe: 0
  };
  const r = AILogic.xuanZeChuPai(shouPai, shangJia, !!q.shiDuiYou, gs);
  if (!r || r.guo || !r.pai) return { guo: true };
  return { cards: r.pai.map(c => [c.zhi, c.hua, c.id]) };
}

let buf = '';
process.stdin.on('data', (d) => {
  buf += d.toString('utf8');
  let i;
  while ((i = buf.indexOf('\n')) >= 0) {
    const line = buf.slice(0, i); buf = buf.slice(i + 1);
    if (!line.trim()) continue;
    let out;
    try { out = handle(JSON.parse(line)); }
    catch (e) { out = { error: String((e && e.message) || e) }; }
    process.stdout.write(JSON.stringify(out) + '\n');
  }
});
process.stdin.on('end', () => process.exit(0));

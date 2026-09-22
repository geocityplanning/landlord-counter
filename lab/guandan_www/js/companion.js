/* ============================================================================
   掼蛋伴随 · 记牌助手（页面内版）
   ----------------------------------------------------------------------------
   来源: **逐字照搬** 2026-09-21 定稿的 web/companion/index.html ✓
     · 样式(:root 变量 / 悬浮球 / 面板 / 出牌记录 / 牌池 / 出牌推荐 / 托管 / 页脚) 原样 ✓
     · 结构(header + 三段 section + 托管 + footer) 原样 ✓
   只为"插进游戏页面"做了两处必要改动(不是重设计 ✗):
     1. 所有选择器加 #companion 前缀 —— 否则会污染游戏自己的 body/p/* ✗
     2. 数据源从 `fetch('/api/live')`(后台+sqlite) 换成**页面真值 + 本地 AI** ⇒ 离线可用 ✓
        对应的字段替换见下面 render() 的注释 ✓

   只在 ?companion=1 时加载 ✓ —— 实验室跑分那条路(index.html 原样)一行不受影响 ✓
   ============================================================================ */
(function () {
  'use strict';
  if (window.__companionLoaded) return;
  window.__companionLoaded = true;

  var ZHI = { 11:'J', 12:'Q', 13:'K', 14:'A', 15:'小王', 16:'大王' };
  var HUA = { 0:'♠', 1:'♥', 2:'♣', 3:'♦', 4:'' };
  var cname = function (z, h) { return (h === 4 ? '' : (HUA[h] || '')) + (ZHI[z] || z); };
  var INIT = {}; (function () { for (var r = 2; r <= 14; r++) INIT[r] = 8; INIT[15] = 2; INIT[16] = 2; })();
  var RANKS = [16, 15, 14, 13, 12, 11, 10, 9, 8, 7, 6, 5, 4, 3, 2];

  var auto = false, lastAct = 0, autoDelay = 2200, lastDragTs = 0;

  // ---------- 样式: 照搬定稿, 选择器全部收进 #companion ----------
  var CSS = `
  #companion {
    --panel: rgba(17,25,39,.9); --line: rgba(146,176,214,.16); --fg:#edf5ff;
    --muted:#9bb0c9; --ok:#53d78a; --warn:#f4c76d; --mine:#68a7ff;
    --shadow: 0 18px 42px rgba(0,0,0,.45);
    font: 12px/1.5 -apple-system,"PingFang SC","Microsoft YaHei",sans-serif; color: var(--fg);
  }
  #companion * { box-sizing: border-box; }
  #companion #ball {
    position: fixed; right: 16px; bottom: 16px; width: 44px; height: 44px; border-radius: 50%;
    background: linear-gradient(145deg, rgba(49,69,92,.96), rgba(17,27,41,.96));
    display: flex; align-items: center; justify-content: center; cursor: pointer;
    box-shadow: 0 10px 26px rgba(0,0,0,.42), inset 0 1px 0 rgba(255,255,255,.1);
    border: 1px solid rgba(146,176,214,.26); z-index: 9999;
    font-size: 18px; user-select: none; backdrop-filter: blur(12px); touch-action: none;
    transition: transform 160ms ease, border-color 160ms ease, box-shadow 160ms ease;
  }
  #companion #ball:hover { transform: translateY(-2px); border-color: rgba(104,167,255,.5); }
  #companion #ball .badge {
    position: absolute; top: -4px; right: -4px; background: var(--warn); color: #111;
    font-size: 10px; font-weight: 800; border-radius: 999px; min-width: 16px; height: 16px;
    line-height: 16px; padding: 0 4px; box-shadow: 0 5px 14px rgba(244,199,109,.35);
  }
  #companion #panel {
    position: fixed; right: 16px; bottom: 16px; width: 320px;
    max-height: 82vh; max-height: calc(100dvh - 24px);
    background: rgba(14,20,31,.86); border: 1px solid var(--line); border-radius: 15px;
    display: flex; flex-direction: column; box-shadow: var(--shadow); z-index: 9998;
    overflow: hidden; backdrop-filter: blur(12px);
  }
  #companion.collapsed #panel { display: none; }
  #companion.collapsed #ball { display: flex; }
  #companion:not(.collapsed) #ball { display: none; }
  #companion header {
    display: flex; align-items: center; gap: 6px; padding: 8px 10px;
    background: linear-gradient(180deg, rgba(38,54,75,.95), rgba(21,31,45,.9));
    border-bottom: 1px solid var(--line); cursor: move;
  }
  #companion header b { font-size: 13px; letter-spacing: .04em; }
  #companion header .tag {
    background: rgba(255,255,255,.04); border: 1px solid var(--line); color: var(--muted);
    border-radius: 7px; padding: 1px 6px; font-size: 10px;
  }
  #companion header .sp { flex: 1; }
  #companion header button {
    background: rgba(255,255,255,.03); color: var(--fg); border: 1px solid var(--line);
    border-radius: 7px; padding: 2px 7px; cursor: pointer; font-size: 11px;
  }
  #companion .body { overflow-y: auto; padding: 9px; display: flex; flex-direction: column; gap: 8px; }
  #companion section {
    background: rgba(255,255,255,.02); border: 1px solid var(--line); border-radius: 10px; padding: 8px;
  }
  #companion section h3 {
    font-size: 10px; color: var(--muted); font-weight: 600; margin: 0 0 6px;
    display: flex; justify-content: space-between; letter-spacing: .08em; text-transform: uppercase;
  }
  #companion .plays-box {
    max-height: 126px; overflow-y: auto; padding-right: 3px;
    display: flex; flex-direction: column; gap: 4px;
  }
  #companion .plays-box::-webkit-scrollbar { width: 5px; }
  #companion .plays-box::-webkit-scrollbar-thumb { background: rgba(255,255,255,.12); border-radius: 999px; }
  #companion .rec {
    display: flex; gap: 5px; align-items: flex-start; padding: 3px 5px; border-radius: 6px;
    background: rgba(255,255,255,.02); border: 1px solid rgba(255,255,255,.04);
  }
  #companion .rec .who { color: var(--muted); min-width: 22px; font-weight: 600; }
  #companion .rec.mine .who { color: var(--mine); }
  #companion .rec .cs { display: flex; gap: 3px; flex-wrap: wrap; align-items: center; }
  #companion .c {
    background: rgba(255,255,255,.03); border: 1px solid rgba(255,255,255,.06);
    border-radius: 4px; padding: 0 4px; font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  }
  #companion .c.pass { color: var(--muted); border-style: dashed; }
  #companion .pool { display: grid; grid-template-columns: repeat(5, minmax(0,1fr)); gap: 4px; }
  #companion .pcell {
    background: rgba(255,255,255,.02); border: 1px solid var(--line); border-radius: 6px;
    padding: 4px 3px; text-align: center; font-family: ui-monospace, monospace; min-height: 43px;
  }
  #companion .pcell .k { color: var(--muted); font-size: 10px; }
  #companion .pcell .v { font-size: 14px; font-weight: 700; margin-top: 1px; }
  #companion .pcell.z {
    background: linear-gradient(180deg, rgba(83,215,138,.12), rgba(14,27,24,.9));
    border-color: rgba(83,215,138,.3);
  }
  #companion .pcell.z .v { color: var(--ok); }
  #companion .recs-box { display: flex; flex-direction: column; gap: 6px; }
  #companion .rec-row {
    background: rgba(255,255,255,.02); border: 1px solid var(--line); border-radius: 7px;
    padding: 5px 7px; display: flex; justify-content: space-between; align-items: center; gap: 6px;
  }
  #companion .rec-row .main { flex: 1; min-width: 0; }
  #companion .rec-row .n { color: var(--muted); font-size: 10px; white-space: nowrap; }
  #companion #host {
    width: 100%; padding: 8px 10px; border: 1px solid rgba(255,255,255,.08); border-radius: 8px;
    font-size: 13px; font-weight: 700; cursor: pointer;
    background: linear-gradient(180deg, #1b2a3c, #172334); color: var(--fg);
  }
  #companion #host.on {
    background: linear-gradient(180deg, rgba(83,215,138,.2), rgba(35,90,60,.9));
    border-color: rgba(83,215,138,.38); color: #eafff3;
  }
  #companion footer {
    padding: 6px 10px; border-top: 1px solid var(--line); color: var(--muted); font-size: 10px;
    display: flex; justify-content: space-between;
  }
  @media (max-width: 420px) { #companion #panel { width: min(90vw, 310px); right: 8px; bottom: 8px; } }
  `;

  // ---------- 结构: 照搬定稿 ----------
  var HTML =
    '<div id="ball" title="当前手牌：–张">🃏<span class="badge" id="ballBadge">牌–</span></div>'
  + '<div id="panel">'
  +   '<header>'
  +     '<b>记牌助手</b>'
  +     '<span class="tag" id="gid">–</span>'
  +     '<span class="tag" id="ji">级牌 –</span>'
  +     '<span class="sp"></span>'
  +     '<button id="collapse" title="收起成悬浮球">—</button>'
  +   '</header>'
  +   '<div class="body">'
  +     '<section><h3>出牌记录 <span id="playCount"></span></h3><div class="plays-box" id="plays"></div></section>'
  +     '<section><h3>牌池 <span id="poolHint">剩余张数</span></h3><div class="pool" id="pool"></div></section>'
  +     '<section><h3>出牌推荐 <span id="recHint"></span></h3><div class="recs-box" id="recs"></div></section>'
  +     '<section><button id="host">AI 托管：关</button></section>'
  +   '</div>'
  +   '<footer><span id="acc">准确率 –</span><span id="updated">–</span></footer>'
  + '</div>';

  var root = document.createElement('div');
  root.id = 'companion';
  root.className = 'collapsed';                  // 定稿行为: 先给球 ✓ 点一下展开面板 ✓
  var st = document.createElement('style'); st.textContent = CSS;
  root.innerHTML = HTML;
  document.head.appendChild(st);
  document.body.appendChild(root);
  var $ = function (id) { return document.getElementById(id); };

  // ---------- 交互: 球/面板互斥(定稿行为) + 球可拖 ----------
  function toggleBall() { root.classList.toggle('collapsed'); tick(); }
  root.querySelector('#ball').addEventListener('click', function () {
    if (Date.now() - lastDragTs < 500) return;   // 拖动尾巴不算点击 ✓
    toggleBall();
  });
  root.querySelector('#collapse').addEventListener('click', toggleBall);
  root.querySelector('#host').addEventListener('click', function () {
    auto = !auto;
    $('host').textContent = 'AI 托管：' + (auto ? '开' : '关');
    $('host').classList.toggle('on', auto);
  });
  (function dragBall() {
    var el = root.querySelector('#ball'), sx = 0, sy = 0, ox = 0, oy = 0, on = false, moved = false;
    function down(e) { var t = e.touches ? e.touches[0] : e; on = true; moved = false;
      sx = t.clientX; sy = t.clientY; var r = el.getBoundingClientRect(); ox = r.left; oy = r.top; }
    function move(e) { if (!on) return; var t = e.touches ? e.touches[0] : e;
      var dx = t.clientX - sx, dy = t.clientY - sy;
      if (!moved && Math.abs(dx) + Math.abs(dy) < 8) return;
      moved = true; lastDragTs = Date.now();
      el.style.left = Math.max(2, Math.min(window.innerWidth - el.offsetWidth - 2, ox + dx)) + 'px';
      el.style.top = Math.max(2, Math.min(window.innerHeight - 40, oy + dy)) + 'px';
      el.style.right = 'auto'; el.style.bottom = 'auto'; e.preventDefault(); }
    function up() { on = false; }
    el.addEventListener('touchstart', down, { passive: false });
    el.addEventListener('touchmove', move, { passive: false });
    el.addEventListener('touchend', up);
    el.addEventListener('mousedown', down);
    document.addEventListener('mousemove', move);
    document.addEventListener('mouseup', up);
  })();

  // ---------- 数据: 定稿读 /api/live, 这里改成**页面真值 + 本地 AI**(离线 ✓) ----------
  function truth() { return (window.__truth ? window.__truth() : {}) || {}; }
  function myHand() { var t = truth(); return (t.handsFull && t.handsFull[0]) || []; }

  function remain() {                        // = 后台 CardTracker.remaining_counts 的等价物 ✓
    var left = {}, r;
    for (r in INIT) left[r] = INIT[r];
    myHand().forEach(function (c) { left[c.zhi] = Math.max(0, (left[c.zhi] || 0) - 1); });
    (window.__plays || []).forEach(function (p) {
      (p.zhi || []).forEach(function (z) { left[z] = Math.max(0, (left[z] || 0) - 1); });
    });
    return left;
  }

  // 出牌推荐 = 本地 AI(游戏自带) 现场算 ✓ 离线可算 ✓
  function recommend() {
    var D = window.__demo, t = truth();
    if (!D || t.phase !== 'playing' || t.current !== 0) return null;
    try {
      var s = D.state;
      var r = AILogic.xuanZeChuPai(s.wanJiaPai, s.shangJiaPaiXing, (s.shangJia === 2), s);
      if (r && r.pai && r.pai.length) return { cards: r.pai, beat: !!s.shangJiaPaiXing };
      if (s.shangJiaPaiXing) return { pass: true, beat: true };
      var c = s.wanJiaPai.slice().sort(function (a, b) { return a.zhi - b.zhi; });
      return c.length ? { cards: [c[0]], beat: false } : null;
    } catch (e) { return null; }
  }

  function tick() {
    var t = truth(), hand = myHand();
    $('ballBadge').textContent = '牌' + hand.length;
    $('ball').title = '当前手牌：' + hand.length + '张';
    $('updated').textContent = new Date().toLocaleTimeString();
    if (root.classList.contains('collapsed')) return;    // 收起时只更新角标 ✓(定稿也这样)

    $('gid').textContent = '本地';                       // 定稿是后台局号 ⇒ 离线版写"本地"
    $('ji').textContent = '级牌 ' + (ZHI[t.jiPai] || t.jiPai || '–');

    // ① 出牌记录(最近 12 手) —— 定稿读 j.plays ✓ 这里读 window.__plays
    var ps = (window.__plays || []).slice(-12);
    $('playCount').textContent = (window.__plays || []).length + ' 手';
    $('plays').innerHTML = ps.map(function (p) {
      return '<div class="rec ' + (p.seat === 0 ? 'mine' : '') + '">'
        + '<span class="who">' + (p.seat === 0 ? '我' : p.seat) + '</span>'
        + '<span class="cs">' + (p.zhi || []).map(function (z, i) {
            return '<span class="c">' + cname(z, (p.hua || [])[i]) + '</span>';
          }).join('') + '</span></div>';
    }).join('') || '<div style="color:#8b98a9">还没有记录</div>';

    // ② 牌池 —— 定稿读后台快照 j.remains ✓ 这里本地算(口径一致: 只手牌+已出)
    var rem = remain();
    $('pool').innerHTML = RANKS.map(function (k) {
      var v = rem[k];
      if (v === undefined) return '';
      return '<div class="pcell ' + (v === 0 ? 'z' : '') + '"><div class="k">' + (ZHI[k] || k) + '</div>'
        + '<div class="v">' + v + '</div></div>';
    }).join('');
    $('poolHint').textContent = '剩余张数';

    // ③ 出牌推荐 —— 定稿读后台 j.decisions ✓ 这里用本地 AI 现算
    var rec = recommend();
    $('recHint').textContent = !rec ? '' : (rec.beat ? '需压' : '领出');
    if (!rec) {
      $('recs').innerHTML = '<div style="color:#8b98a9">轮到我时给建议</div>';
    } else {
      var txt = rec.pass ? '<span class="c pass">不出</span>'
        : (rec.cards || []).map(function (c) { return '<span class="c">' + cname(c.zhi, c.hua) + '</span>'; }).join('');
      $('recs').innerHTML = '<div class="rec-row"><div class="main">1. ' + txt + '</div>'
        + '<span class="n">' + (rec.pass ? '可不出' : (rec.cards || []).length + ' 张') + ' · 本地AI</span></div>';
    }
    autoMaybe();
  }

  // ---------- AI 托管: 本地 AI 替"南"出牌(节奏 1.6~3.0 秒/手 ✓) ----------
  function autoMaybe() {
    if (!auto) return;
    var now = Date.now();
    if (now - lastAct < autoDelay) return;
    try {
      var t = truth(), D = window.__demo;
      if (!D || t.phase !== 'playing' || t.current !== 0) return;
      lastAct = now;
      autoDelay = 1600 + Math.random() * 1400;
      var s = D.state;
      var r = AILogic.xuanZeChuPai(s.wanJiaPai, s.shangJiaPaiXing, (s.shangJia === 2), s);
      if (r && r.pai && r.pai.length) {
        s.selectedPai = r.pai.map(function (p) { return p.id; });
        D.chuPai();
      } else if (s.shangJiaPaiXing) {
        D.guoPai();
      } else if (s.wanJiaPai.length) {
        var c = s.wanJiaPai.slice().sort(function (a, b) { return a.zhi - b.zhi; });
        s.selectedPai = [c[0].id];
        D.chuPai();
      }
    } catch (e) { /* 出错就放弃这一轮, 不硬来 */ }
  }

  $('acc').textContent = '准确率 暂无数据';   // 定稿的这一格来自后台 /api/accuracy ⇒ 离线版如实标
  tick();
  setInterval(tick, 1000);
})();

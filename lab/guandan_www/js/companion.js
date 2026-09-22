/* ============================================================================
   掼蛋伴随 · 记牌条（横版 · 2026-09-22）
   ----------------------------------------------------------------------------
   为什么要横版: 用户(2026-09-22)给的参考排版是一根**扁横条** ——
     左边一排在"剩几张"(点数格, 打光的用绿/红标出 ✓)
     右边按座位列出**各家出过的牌**(我/下/对/上 ✓ 分组显示 ✓)
   好处: 占屏只有一条, 不挡牌 ✓ (竖版 310x488 在小屏上占 82% ✗)

   数据源: 页面真值(__truth / __plays) + 本地 AI ⇒ 离线 ✓ (定稿那套样式变量沿用 ✓)
   只在 ?companion=1 时加载 ✓ 跑分那条路一行不动 ✓
   ============================================================================ */
(function () {
  'use strict';
  if (window.__companionLoaded) return;
  window.__companionLoaded = true;

  var ZHI = { 11:'J', 12:'Q', 13:'K', 14:'A', 15:'小', 16:'大' };
  var HUA = { 0:'♠', 1:'♥', 2:'♣', 3:'♦', 4:'' };
  var cname = function (z, h) { return (h === 4 ? '' : (HUA[h] || '')) + (ZHI[z] || z); };
  var INIT = {}; (function () { for (var r = 2; r <= 14; r++) INIT[r] = 8; INIT[15] = 2; INIT[16] = 2; })();
  var RANKS = [16, 15, 14, 13, 12, 11, 10, 9, 8, 7, 6, 5, 4, 3, 2];
  // 座位口径(照参考图): 我 / 下家 / 对家 / 上家
  var SEAT = ['我', '下', '对', '上'];

  var auto = false, lastAct = 0, autoDelay = 2200, lastDragTs = 0;

  var CSS = `
  #cpn { --line: rgba(146,176,214,.16); --fg:#edf5ff; --muted:#9bb0c9; --ok:#53d78a; --warn:#f4c76d; --mine:#68a7ff;
    font: 11px/1.35 -apple-system,"PingFang SC","Microsoft YaHei",sans-serif; color: var(--fg); }
  #cpn * { box-sizing: border-box; }
  #cpn #cpnBall {
    position: fixed; right: 12px; bottom: 96px; width: 40px; height: 40px; border-radius: 50%;
    display: flex; align-items: center; justify-content: center; cursor: pointer;
    z-index: 9999; font-size: 17px; user-select: none; touch-action: none; }
  #cpn #cpnBall .badge { position: absolute; top: -4px; right: -4px; background: var(--warn); color:#111;
    font-size: 10px; font-weight: 800; border-radius: 999px; min-width: 15px; height: 15px; line-height: 15px; padding: 0 4px; }
  #cpn.collapsed #cpnPanel { display: none; }
  #cpn:not(.collapsed) #cpnBall { display: none; }
  /* 横条本体 */
  #cpn #cpnPanel {
    position: fixed; left: 6px; right: 6px; bottom: 84px; z-index: 9998;
    background: rgba(12,18,28,.92); border: 1px solid var(--line); border-radius: 10px;
    box-shadow: 0 14px 34px rgba(0,0,0,.5); overflow: hidden; backdrop-filter: blur(10px); }
  #cpn .hd { display: flex; align-items: center; gap: 5px; padding: 0 7px; height: 14px;
    background: linear-gradient(180deg, rgba(38,54,75,.95), rgba(21,31,45,.9)); border-bottom: 1px solid var(--line); cursor: move; }
  #cpn .hd b { font-size: 10px; }
  #cpn .tag { background: rgba(255,255,255,.04); border: 1px solid var(--line); color: var(--muted);
    border-radius: 6px; padding: 0 5px; font-size: 10px; }
  #cpn .sp { flex: 1; }
  #cpn .hd button { background: rgba(255,255,255,.03); color: var(--fg); border: 1px solid var(--line);
    border-radius: 6px; padding: 1px 7px; font-size: 11px; cursor: pointer; }
  /* 竖着排: 牌池一排 → 推荐 → 各家(两列) ⇒ 高度只有竖版的一半 ✓ */
  #cpn .hbody { display: flex; flex-direction: column; gap: 2px; padding: 2px 5px; }
  #cpn .strip { display: grid; grid-template-columns: repeat(15, minmax(0,1fr)); gap: 2px; }
  #cpn .kc { background: rgba(255,255,255,.05); border: 1px solid rgba(146,176,214,.30); border-radius: 5px;
    display: flex; align-items: baseline; justify-content: center; gap: 2px; height: 17px;
    line-height: 17px; font-family: ui-monospace, monospace; overflow: hidden; }
  #cpn .kc .k { color: #cfe0f5; font-size: 11px; }
  #cpn .kc .v { font-size: 11px; font-weight: 800; color: #ffffff; }
  #cpn .kc.z { background: rgba(255,255,255,.02); border-color: rgba(146,176,214,.16); }
  #cpn .kc.z .v { color: #7f93a8; }
  #cpn .kc.ji .k { color: var(--warn); }
  /* 决策推荐: 就在牌池下方 ✓ */
  #cpn .recbar { display: flex; align-items: center; gap: 4px; height: 13px; padding: 0 2px;
    overflow: hidden; white-space: nowrap; }
  #cpn .recbar .lb { color: var(--muted); font-size: 10px; }
  #cpn .recbar .txt { overflow: hidden; text-overflow: ellipsis; }
  /* 各家出过的牌: 两列 ⇒ 只占两行 */
  #cpn .seats { display: grid; grid-template-columns: repeat(4, minmax(0,1fr)); gap: 2px; }
  #cpn .srow { display: flex; gap: 3px; align-items: center; background: rgba(255,255,255,.02);
    border: 1px solid rgba(255,255,255,.05); border-radius: 4px; padding: 0 3px; height: 13px;
    overflow: hidden; white-space: nowrap; }
  #cpn .srow .me { color: var(--mine); font-weight: 700; }
  #cpn .srow .nm { color: var(--muted); min-width: 11px; font-size: 9px; }
  #cpn .srow .cards { color: #cfe0f5; overflow: hidden; white-space: nowrap; text-overflow: ellipsis; }
  #cpn .srow .n { color: var(--muted); font-size: 9px; margin-left: auto; }
  /* 底: 推荐 + 托管 */
  #cpn .ft { display: flex; align-items: center; gap: 6px; padding: 0 6px; height: 15px; border-top: 1px solid var(--line); }
  #cpn .ft .upd { margin-left: auto; }
  #cpn .ci { display: inline-block; background: rgba(255,255,255,.04); border: 1px solid rgba(255,255,255,.1);
    border-radius: 4px; padding: 0 4px; margin-left: 3px; font-family: ui-monospace, monospace; }
  #cpn #cpnHost { border: 1px solid rgba(255,255,255,.08); border-radius: 6px; padding: 1px 8px;
    font-size: 10px; font-weight: 700; cursor: pointer; background: linear-gradient(180deg,#1b2a3c,#172334); color: var(--fg); white-space: nowrap; }
  #cpn #cpnHost.on { background: linear-gradient(180deg, rgba(83,215,138,.2), rgba(35,90,60,.9));
    border-color: rgba(83,215,138,.38); color: #eafff3; }
  #cpn .upd { color: var(--muted); font-size: 9px; white-space: nowrap; }
  
  /* 出过的牌/推荐: 白底牌面片(2026-09-22 用户: 不要红字, 统一颜色 ✓) */
  #cpn .pc { display: inline-block; background: #fbfaf3; color: #1b1c20; border: 1px solid #cfd6e2;
    border-radius: 3px; padding: 0 3px; margin-left: 2px; font-weight: 800;
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }
`;

  var root = document.createElement('div');
  root.id = 'cpn';
  root.className = 'collapsed';
  var st = document.createElement('style'); st.textContent = CSS;
  root.innerHTML =
      '<div id="cpnBall" title="点开记牌条">'
    + '<img alt="" style="width:100%;height:100%;border-radius:50%;display:block;pointer-events:none" src="data:image/png;base64,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">'
    + '<span class="badge" id="cpnBadge">牌–</span></div>'
    + '<div id="cpnPanel">'
    +   '<div class="hd" id="cpnHead"><b>记牌助手</b>'
    +     '<span class="tag" id="cpnJi">级牌 –</span><span class="tag" id="cpnCnt">–</span>'
    +     '<span class="sp"></span><button id="cpnFold" title="收起">—</button></div>'
    +   '<div class="hbody">'
    +     '<div class="strip" id="cpnPool"></div>'
    +     '<div class="recbar"><span class="lb">推荐</span><span class="txt" id="cpnRec">–</span></div>'
    +     '<div class="seats" id="cpnSeats"></div>'
    +   '</div>'
    +   '<div class="ft"><button id="cpnHost">AI 托管：关</button>'
    +     '<span class="upd" id="cpnUpd">–</span></div>'
    + '</div>';
  document.head.appendChild(st);
  document.body.appendChild(root);
  var $ = function (id) { return document.getElementById(id); };

  // ---------- 交互 ----------
  function toggle() { root.classList.toggle('collapsed'); tick(); }
  root.querySelector('#cpnBall').addEventListener('click', function () {
    if (Date.now() - lastDragTs < 500) return;
    toggle();
  });
  $('cpnFold').addEventListener('click', toggle);
  $('cpnHost').addEventListener('click', function () {
    auto = !auto;
    $('cpnHost').textContent = 'AI 托管：' + (auto ? '开' : '关');
    $('cpnHost').classList.toggle('on', auto);
  });
  // 球和条都能拖(条拖动了就固定在那个位置 ✓)
  (function () {
    function mk(el, handle) {
      var sx, sy, ox, oy, on = false, moved = false;
      handle.addEventListener('touchstart', function (e) { var t = e.touches[0]; on = true; moved = false;
        sx = t.clientX; sy = t.clientY; var r = el.getBoundingClientRect(); ox = r.left; oy = r.top; }, { passive: false });
      handle.addEventListener('touchmove', function (e) { if (!on) return; var t = e.touches[0];
        var dx = t.clientX - sx, dy = t.clientY - sy;
        if (!moved && Math.abs(dx) + Math.abs(dy) < 8) return;
        moved = true; lastDragTs = Date.now();
        el.style.left = Math.max(2, Math.min(window.innerWidth - el.offsetWidth - 2, ox + dx)) + 'px';
        el.style.top = Math.max(2, Math.min(window.innerHeight - 40, oy + dy)) + 'px';
        el.style.right = 'auto'; el.style.bottom = 'auto'; e.preventDefault(); }, { passive: false });
      handle.addEventListener('touchend', function () { on = false; });
      handle.addEventListener('mousedown', function (e) { on = true; moved = false; sx = e.clientX; sy = e.clientY;
        var r = el.getBoundingClientRect(); ox = r.left; oy = r.top; });
      document.addEventListener('mousemove', function (e) { if (!on) return;
        var dx = e.clientX - sx, dy = e.clientY - sy;
        if (!moved && Math.abs(dx) + Math.abs(dy) < 8) return;
        moved = true; lastDragTs = Date.now();
        el.style.left = Math.max(2, Math.min(window.innerWidth - el.offsetWidth - 2, ox + dx)) + 'px';
        el.style.top = Math.max(2, Math.min(window.innerHeight - 40, oy + dy)) + 'px';
        el.style.right = 'auto'; el.style.bottom = 'auto'; });
      document.addEventListener('mouseup', function () { on = false; });
    }
    mk(root.querySelector('#cpnBall'), root.querySelector('#cpnBall'));
    mk($('cpnPanel'), $('cpnHead'));
  })();

  // ---------- 数据 ----------
  function truth() { return (window.__truth ? window.__truth() : {}) || {}; }
  function myHand() { var t = truth(); return (t.handsFull && t.handsFull[0]) || []; }

  function remain() {
    var left = {}, r;
    for (r in INIT) left[r] = INIT[r];
    myHand().forEach(function (c) { left[c.zhi] = Math.max(0, (left[c.zhi] || 0) - 1); });
    (window.__plays || []).forEach(function (p) {
      (p.zhi || []).forEach(function (z) { left[z] = Math.max(0, (left[z] || 0) - 1); });
    });
    return left;
  }

  // 各家出过的牌: 按座位 + 按点数分组(仿参考图右侧那种"谁的什么牌")
  function bySeat() {
    var out = [[], [], [], []];                       // 每家: [ [ {z,h}, ... ], ... ] 每手一组
    (window.__plays || []).forEach(function (p) {
      var idx = (p.zhi || []).map(function (z, i) { return i; })
        .sort(function (a, b) { return (p.zhi[b] || 0) - (p.zhi[a] || 0); });
      if (idx.length) out[p.seat].push(idx.map(function (i) { return { z: p.zhi[i], h: (p.hua || [])[i] }; }));
    });
    return out;
  }
  function cardChip(c) {
    // 2026-09-22 用户: 推荐栏和各家栏都不要红字 ⇒ 全部同色 ✓
    return '<span class="pc">' + (ZHI[c.z] || c.z) + '</span>';
  }

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

  // ---------- 刷新 ----------
  function tick() {
    var t = truth(), hand = myHand();
    $('cpnBadge').textContent = '牌' + hand.length;
    $('cpnUpd').textContent = new Date().toLocaleTimeString().slice(0, 8);
    if (root.classList.contains('collapsed')) return;

    $('cpnJi').textContent = '级牌 ' + (ZHI[t.jiPai] || t.jiPai || '–');
    $('cpnCnt').textContent = '我 ' + hand.length + ' 张';

    // 左: 剩余池(打光的绿 ✓ 级牌标黄 ✓)
    var rem = remain();
    $('cpnPool').innerHTML = RANKS.map(function (r) {
      var v = rem[r] == null ? '' : rem[r];
      return '<div class="kc' + (v === 0 ? ' z' : '') + (r === t.jiPai ? ' ji' : '') + '">'
        + '<div class="k">' + (ZHI[r] || r) + '</div><div class="v">' + v + '</div></div>';
    }).join('');

    // 右: 各家出过的牌(每行 = 一家, 从新到旧列)
    var bs = bySeat();
    var tot = (window.__plays || []).reduce(function (a, p) { return a + (p.zhi || []).length; }, 0);
    $('cpnSeats').innerHTML = [0, 1, 2, 3].map(function (i) {
      var list = bs[i].slice(-6);
      return '<div class="srow"><span class="nm' + (i === 0 ? ' me' : '') + '">' + SEAT[i] + '</span>'
        + '<span class="cards">' + (list.map(function (hand) {
            return hand.map(cardChip).join('');
          }).join(' ') || '—') + '</span>'
        + '<span class="n">' + bs[i].length + '手</span></div>';
    }).join('') || '';

    // 底: 推荐 + 托管
    var rec = recommend();
    $('cpnRec').innerHTML = !rec ? '<span style="color:#9bb0c9">轮到我时给建议</span>'
      : (rec.beat ? '需压 ' : '领出 ') + (rec.pass ? '<span class="ci">不出</span>'
        : (rec.cards || []).map(function (c) { return cardChip({ z: c.zhi, h: c.hua }); }).join(''));
    autoMaybe();
  }

  function autoMaybe() {
    if (!auto) return;
    var now = Date.now();
    if (now - lastAct < autoDelay) return;
    try {
      var t = truth(), D = window.__demo;
      if (!D || t.phase !== 'playing' || t.current !== 0) return;
      lastAct = now; autoDelay = 1600 + Math.random() * 1400;
      var s = D.state;
      var r = AILogic.xuanZeChuPai(s.wanJiaPai, s.shangJiaPaiXing, (s.shangJia === 2), s);
      if (r && r.pai && r.pai.length) { s.selectedPai = r.pai.map(function (p) { return p.id; }); D.chuPai(); }
      else if (s.shangJiaPaiXing) { D.guoPai(); }
      else if (s.wanJiaPai.length) {
        var c = s.wanJiaPai.slice().sort(function (a, b) { return a.zhi - b.zhi; });
        s.selectedPai = [c[0].id]; D.chuPai();
      }
    } catch (e) { /* 出错就放弃这一轮 */ }
  }

  tick();
  setInterval(tick, 1000);
})();

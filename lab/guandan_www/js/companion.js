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
  #cpn .kc { background: rgba(255,255,255,.03); border: 1px solid var(--line); border-radius: 4px;
    display: flex; align-items: baseline; justify-content: center; gap: 1px; height: 13px;
    line-height: 13px; font-family: ui-monospace, monospace; overflow: hidden; }
  #cpn .kc .k { color: var(--muted); font-size: 9px; }
  #cpn .kc .v { font-size: 11px; font-weight: 700; }
  #cpn .kc.z { background: rgba(83,215,138,.14); border-color: rgba(83,215,138,.34); }
  #cpn .kc.z .v { color: var(--ok); }
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
    var out = [[], [], [], []];
    (window.__plays || []).forEach(function (p) {
      var zs = (p.zhi || []).slice().sort(function (a, b) { return b - a; });
      if (zs.length) out[p.seat].push(zs.map(function (z) { return ZHI[z] || z; }).join(''));
    });
    return out;
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
        + '<span class="cards">' + (list.join(' · ') || '—') + '</span>'
        + '<span class="n">' + bs[i].length + '手</span></div>';
    }).join('') || '';

    // 底: 推荐 + 托管
    var rec = recommend();
    $('cpnRec').innerHTML = !rec ? '<span style="color:#9bb0c9">轮到我时给建议</span>'
      : (rec.beat ? '需压 ' : '领出 ') + (rec.pass ? '<span class="ci">不出</span>'
        : (rec.cards || []).map(function (c) { return '<span class="ci">' + cname(c.zhi, c.hua) + '</span>'; }).join(''));
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

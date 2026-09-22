/* ============================================================================
   伴随应用 · 页面内浮窗版（2026-09-22）
   ----------------------------------------------------------------------------
   为什么做成"页面内浮窗"而不是 Android 悬浮窗:
     云手机容器把输入配成 `-touch`(无触摸屏 ✗) ⇒ 注入的点击到不了 Android 悬浮窗 ✗
     ⇒ 悬浮球拖不动、面板点不开 ✗
     做成页面里的普通元素 ⇒ 点/拖/选牌和正常用云手机一模一样 ✓

   只在 demo.html 或 ?demo=1 时加载 ✓ —— 实验室跑分那条路一行不受影响 ✓

   功能:
     · 🃏 悬浮球(页面内): 点一下展/收记牌窗口; 可拖动
     · 记牌窗口: 剩余牌池(只按"我的手牌 + 已出的牌"算, 和真记牌器一样) + 各家最近出牌
     · AI 托管开关: 开着就让游戏自带 AI 替"南"出牌 (全本地, 不用网络)

   ⚠ 坑(2026-09-22 实测): 游戏里 gameState / AILogic 是 `let`/`const` 声明的,
     挂在**全局词法环境**, **不在 window 上** ⇒ 必须用裸名字, window.gameState 取到 undefined
     (这个坑让剩余池没减手牌, 自洽检查 27+0+108=135≠108 抓出来的)
   ============================================================================ */
(function () {
  'use strict';
  if (window.__demoLoaded) return;
  window.__demoLoaded = true;

  var RANK_NAME = { 2:'2',3:'3',4:'4',5:'5',6:'6',7:'7',8:'8',9:'9',10:'10',11:'J',12:'Q',13:'K',14:'A',15:'小王',16:'大王' };
  // 掼蛋 = 两副牌: 2~A 各 8 张, 小王 2, 大王 2 ⇒ 共 108
  var INIT = {};
  (function () { for (var r = 2; r <= 14; r++) INIT[r] = 8; INIT[15] = 2; INIT[16] = 2; })();
  var RANKS = [16, 15, 14, 13, 12, 11, 10, 9, 8, 7, 6, 5, 4, 3, 2];

  var auto = false;            // AI 托管开关
  var panel = null, ball = null;
  var lastDragTs = 0;          // 刚拖过的时刻 —— 拖动结束浏览器照样派发 click, 会误开关面板 ✗

  // ---------- 数据: 剩余牌池(只手牌 + 已出的牌, 不看别人手牌) ----------
  function remain() {
    var left = {};
    for (var r in INIT) left[r] = INIT[r];
    try {
      var t = window.__truth ? window.__truth() : null;
      ((t && t.handsFull && t.handsFull[0]) || []).forEach(function (c) { left[c.zhi] = Math.max(0, (left[c.zhi] || 0) - 1); });
      (window.__plays || []).forEach(function (p) { (p.zhi || []).forEach(function (z) { left[z] = Math.max(0, (left[z] || 0) - 1); }); });
    } catch (e) { /* 状态没准备好就跳过 */ }
    return left;
  }

  function lastPlays() {
    var ps = (window.__plays || []).slice(-6);
    var NAME = ['南(我)', '西', '北(队友)', '东'];
    return ps.map(function (p) {
      return (NAME[p.seat] || p.seat) + ' ' + (p.zhi || []).map(function (z) { return RANK_NAME[z] || z; }).join(' ');
    });
  }

  // ---------- 建 UI ----------
  function build() {
    ball = document.createElement('div');
    ball.id = 'demo-ball';
    ball.textContent = '🃏';
    ball.style.cssText = 'position:fixed;right:14px;bottom:120px;width:46px;height:46px;border-radius:50%;'
      + 'background:linear-gradient(145deg,rgba(49,69,92,.96),rgba(17,27,41,.96));color:#fff;'
      + 'display:flex;align-items:center;justify-content:center;font-size:22px;cursor:pointer;'
      + 'box-shadow:0 8px 22px rgba(0,0,0,.5);border:1px solid rgba(146,176,214,.6);z-index:99999;'
      + 'user-select:none;touch-action:none';
    document.body.appendChild(ball);

    panel = document.createElement('div');
    panel.id = 'demo-panel';
    panel.style.cssText = 'position:fixed;right:14px;bottom:176px;width:236px;max-height:64vh;'
      + 'background:rgba(14,20,31,.94);border:1px solid rgba(146,176,214,.35);border-radius:12px;'
      + 'color:#EDF5FF;font:12px/1.45 -apple-system,"PingFang SC",sans-serif;z-index:99998;'
      + 'box-shadow:0 14px 34px rgba(0,0,0,.55);display:none;flex-direction:column;overflow:hidden';
    panel.innerHTML = '<div id="demo-head" style="padding:7px 9px;background:linear-gradient(180deg,#26364B,#151F2D);'
      + 'cursor:move;display:flex;align-items:center;gap:6px;touch-action:none">'
      + '<b style="font-size:12px">🃏 记牌器</b><span id="demo-ji" style="color:#9BB0C9;font-size:11px"></span>'
      + '<span style="flex:1"></span><span id="demo-close" style="cursor:pointer;color:#9BB0C9;padding:0 4px">✕</span></div>'
      // 结构: 头(可拖) + 中间可滚动(总览/牌池/最近出牌) + **底部钉住的托管开关**
      // ⚠ 2026-09-22: 原来全塞一个滚动区 ⇒ 出牌一多就把"AI 托管"顶出屏幕, 只能看一半 ✗
      + '<div id="demo-body" style="padding:8px 9px;overflow-y:auto;flex:1 1 auto;min-height:0">'
      + '<div id="demo-sum" style="margin-bottom:6px;padding:5px 6px;background:rgba(83,215,138,.10);'
      + 'border:1px solid rgba(83,215,138,.30);border-radius:6px;color:#BDEBCF;font-size:11px"></div>'
      + '<div id="demo-pool" style="display:grid;grid-template-columns:repeat(5,1fr);gap:3px"></div>'
      + '<div style="margin-top:7px;color:#9BB0C9;font-size:10px">各家最近出牌</div>'
      + '<div id="demo-plays" style="margin-top:3px;color:#CFE0F5;font-size:11px;'
      + 'max-height:84px;overflow-y:auto;border:1px solid rgba(146,176,214,.18);border-radius:6px;'
      + 'padding:3px 5px"></div>'
      + '</div>'
      + '<div style="padding:6px 9px;border-top:1px solid rgba(146,176,214,.25);flex:0 0 auto">'
      + '<label style="display:block;padding:5px 6px;background:rgba(255,255,255,.04);border-radius:7px;cursor:pointer">'
      + '<input type="checkbox" id="demo-auto"> <b>AI 托管</b></label>'
      + '</div>';
    document.body.appendChild(panel);

    ball.addEventListener('click', function () {
      if (Date.now() - lastDragTs < 500) return;     // 这次点击是拖动的尾巴, 不算 ✓
      if (panel.style.display === 'flex') { panel.style.display = 'none'; return; }
      // 展开时**贴着球**: 右对齐球, 面板下沿落在球顶上方 12px(上面放不下就改放下面)
      panel.style.right = 'auto'; panel.style.bottom = 'auto';
      panel.style.display = 'flex';
      refresh();                                     // ⚠ 必须先填内容再量高度 ✗ 量早了高度偏小, 面板会压到球上
      var br = ball.getBoundingClientRect();
      var pw = panel.offsetWidth, ph = panel.offsetHeight;
      panel.style.maxHeight = Math.max(160, br.top - 20) + 'px';   // 最多到球上方 12px, 多的部分内部滚 ✓
      var left = Math.max(4, Math.min(window.innerWidth - pw - 4, br.left + br.width - pw));
      // ⚠ 锚在**下沿**(不是上沿) —— 面板会越长越高 ✓ 越长越低就会压住球 ✗(实测间距 -48px)
      panel.style.left = left + 'px';
      panel.style.top = 'auto';
      panel.style.bottom = (window.innerHeight - (br.top - 12)) + 'px';
      refresh();
    });
    panel.querySelector('#demo-close').addEventListener('click', function () { panel.style.display = 'none'; });
    panel.querySelector('#demo-auto').addEventListener('change', function (e) { auto = !!e.target.checked; });

    // 拖动(球和面板头都能拖 —— 页面内元素, 云手机里正常收到触摸)
    drag(ball, ball);
    drag(panel.querySelector('#demo-head'), panel, true);
    refresh();
    setInterval(refresh, 1000);
  }

  function drag(handle, target, keepRight) {
    // ⚠ 坑(2026-09-22): touchstart 里 preventDefault 会让浏览器**不再派发 click** ✗
    //    ⇒ 点球没反应(用户报的"点了关不掉")。所以: 移动超过阈值才算拖, 只有拖才拦默认行为
    var sx = 0, sy = 0, ox = 0, oy = 0, moving = false, moved = false;
    function down(e) {
      var t = e.touches ? e.touches[0] : e;
      moving = true; moved = false; sx = t.clientX; sy = t.clientY;
      var r = target.getBoundingClientRect(); ox = r.left; oy = r.top;
    }
    function move(e) {
      if (!moving) return;
      var t = e.touches ? e.touches[0] : e;
      var dx = t.clientX - sx, dy = t.clientY - sy;
      if (!moved && Math.abs(dx) + Math.abs(dy) < 8) return;   // 8px 内 = 点击, 不动它 ✓
      moved = true; lastDragTs = Date.now();
      var x = ox + dx, y = oy + dy;
      x = Math.max(2, Math.min(window.innerWidth - target.offsetWidth - 2, x));
      y = Math.max(2, Math.min(window.innerHeight - 40, y));
      target.style.left = x + 'px'; target.style.top = y + 'px';
      if (keepRight) { target.style.right = 'auto'; target.style.bottom = 'auto'; }
      e.preventDefault();
    }
    function up() { moving = false; }
    handle.addEventListener('touchstart', down, { passive: false });
    handle.addEventListener('touchmove', move, { passive: false });
    handle.addEventListener('touchend', up);
    handle.addEventListener('mousedown', down);
    document.addEventListener('mousemove', move);
    document.addEventListener('mouseup', up);
  }

  // ---------- 刷新 ----------
  function refresh() {
    if (!panel || panel.style.display === 'none') { autoMaybe(); return; }
    var left = remain();
    var cells = RANKS.map(function (r) {
      var v = left[r] == null ? '' : left[r];
      var done = (v === 0);
      var isJi = false;
      try { isJi = (r === (window.__truth ? window.__truth().jiPai : -1)); } catch (e) {}
      return '<div style="background:rgba(255,255,255,.03);border:1px solid rgba(255,255,255,.07);'
        + 'border-radius:5px;padding:2px 0;text-align:center">'
        + '<div style="color:' + (isJi ? '#FFD86B' : '#9BB0C9') + ';font-size:10px">' + (RANK_NAME[r] || r)
        + (isJi ? ' ★' : '') + '</div>'
        + '<div style="font-weight:700;font-size:13px;color:' + (done ? '#53D78A' : '#EDF5FF') + '">' + v + '</div></div>';
    }).join('');
    panel.querySelector('#demo-pool').innerHTML = cells;
    var t0 = window.__truth ? window.__truth() : {};
    var played = (window.__plays || []).reduce(function (a, p) { return a + (p.zhi || []).length; }, 0);
    var unseen = 0; for (var k in left) unseen += left[k];
    panel.querySelector('#demo-sum').innerHTML = '场上未见 <b>' + unseen + '</b> 张 · 已出 ' + played + ' 张';
    var plBox = panel.querySelector('#demo-plays');
    plBox.innerHTML = lastPlays().join('<br>') || '—';
    plBox.scrollTop = plBox.scrollHeight;          // 自动滚到最新一手 ✓
    var t = window.__truth ? window.__truth() : {};
    panel.querySelector('#demo-ji').textContent = '级牌' + (t.jiPai || '?') + ' · 我' + ((t.handsFull && t.handsFull[0] || []).length) + '张'
      + (t.current === 0 ? ' · 轮到我' : '');
    autoMaybe();
  }

  // ---------- AI 托管: 用游戏自带 AI 替"南"出牌(全本地) ----------
  var lastAct = 0;
  var autoDelay = 2200;          // 出牌间隔**随机**(2026-09-22: 原来固定 1.2s, 用户反馈"打得好快" ✗)
                                 // 人类节奏: 每手 1.6~3.0 秒, 每次动作后重新摇一个 ✓
  function autoMaybe() {
    if (!auto) return;
    var now = Date.now();
    if (now - lastAct < autoDelay) return;
    try {
      var D = window.__demo;
      if (!D) return;                               // main.js 没开接口(非 demo 入口)就跳过
      var t = window.__truth ? window.__truth() : null;
      if (!t || t.phase !== 'playing' || t.current !== 0) return;
      lastAct = now;
      var st = D.state;
      var shiDuiYou = (st.shangJia === 2);          // 座位 0/2 = 我方
      var r = AILogic.xuanZeChuPai(st.wanJiaPai, st.shangJiaPaiXing, shiDuiYou, st);
      if (r && r.pai && r.pai.length) {
        st.selectedPai = r.pai.map(function (p) { return p.id; });
        D.chuPai();
      } else if (st.shangJiaPaiXing) {
        D.guoPai();                                 // 能不出就不出
      } else if (st.wanJiaPai.length) {
        var s = st.wanJiaPai.slice().sort(function (a, b) { return a.zhi - b.zhi; });
        st.selectedPai = [s[0].id];                 // 领出必须出牌(护栏)
        D.chuPai();
      }
    } catch (e) { /* 出错就放弃这一轮, 不硬来 */ }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', build);
  } else {
    build();
  }
})();

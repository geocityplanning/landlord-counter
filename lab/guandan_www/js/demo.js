/* ============================================================================
   伴随应用 · 页面内版（2026-09-22 按定稿版式重写）
   ----------------------------------------------------------------------------
   为什么是"页面内元素"(不是 Android 悬浮窗):
     云手机容器把输入配成 `-touch`(无触摸屏 ✗) ⇒ 注入点击到不了 Android 悬浮窗 ✗
     ⇒ 球拖不动、面板点不开 ✗ ; 做成页面内元素则点/拖/选牌和正常用云手机一模一样 ✓

   版式: 按 2026-09-21 定稿的 web/companion/index.html 原样搬 ✓
     悬浮球(带"牌N"角标) · 出牌记录 · 牌池 · **出牌推荐** · AI 托管按钮 · 页脚(更新时间)

   ⚠ 2026-09-22 补记: 上一版我图快另写了个简版 ✗ 把"出牌推荐"和版式丢了 ✗
     现在按定稿搬回来, 并且**数据源从后台 sqlite 改成页面真值 + 本地 AI** ⇒ 天然离线 ✓
     两版对照(用户问的"为什么不一样"): 决策建议在离线版里由本地 AI(游戏自带)算 ✓
     换脑子(RL↔游戏AI)与前端无关, 只影响"推荐栏的内容来源" ✓

   只在 demo.html 或 ?demo=1 时加载 ✓ —— 实验室跑分那条路一行不受影响 ✓

   ⚠ 坑(实测):
     · 游戏 main.js 包在 IIFE 里 ⇒ gameState/chuPai 必须由 main.js 开窗口(window.__demo) ✓
     · touchstart 里 preventDefault 会让浏览器不再派发 click ⇒ 点球没反应 ✗ (用 8px 阈值)
     · 面板锚在**下沿**往上长 ✓ 锚上沿会越来越低、压住球 ✗
     · 先填内容再量高度 ✗ 量早了高度偏小, 面板会压到球上
   ============================================================================ */
(function () {
  'use strict';
  if (window.__demoLoaded) return;
  window.__demoLoaded = true;

  var ZHI = { 11:'J', 12:'Q', 13:'K', 14:'A', 15:'小王', 16:'大王' };
  var HUA = { 0:'♠', 1:'♥', 2:'♣', 3:'♦', 4:'' };
  var SEAT = ['南(我)', '西', '北(队友)', '东'];
  var cname = function (z, h) { return (h === 4 ? '' : (HUA[h] || '')) + (ZHI[z] || z); };

  // 掼蛋 = 两副牌: 2~A 各 8 张, 小王 2, 大王 2 ⇒ 共 108
  var INIT = {}; (function () { for (var r = 2; r <= 14; r++) INIT[r] = 8; INIT[15] = 2; INIT[16] = 2; })();
  var RANKS = [16, 15, 14, 13, 12, 11, 10, 9, 8, 7, 6, 5, 4, 3, 2];

  var auto = false;                 // AI 托管开关
  var panel = null, ball = null, badge = null;
  var lastDragTs = 0;               // 刚拖过的时刻(拖动结束浏览器照样派发 click, 会误开关 ✗)
  var lastAct = 0, autoDelay = 2200;

  function truth() { return (window.__truth ? window.__truth() : {}) || {}; }
  function myHand() { var t = truth(); return (t.handsFull && t.handsFull[0]) || []; }

  // ---------- 数据 ----------
  function remain() {                                  // 剩余牌池: 只减"我的手牌 + 已出的牌" ✓
    var left = {};
    for (var r in INIT) left[r] = INIT[r];
    try {
      myHand().forEach(function (c) { left[c.zhi] = Math.max(0, (left[c.zhi] || 0) - 1); });
      (window.__plays || []).forEach(function (p) {
        (p.zhi || []).forEach(function (z) { left[z] = Math.max(0, (left[z] || 0) - 1); });
      });
    } catch (e) { /* 状态没准备好就跳过 */ }
    return left;
  }

  // ---------- 出牌推荐(本地 AI = 游戏自带, 离线可算 ✓) ----------
  function recommend() {
    var D = window.__demo, t = truth();
    if (!D || t.phase !== 'playing') return null;
    if (t.current !== 0) return { waiting: true };
    try {
      var st = D.state;
      var r = AILogic.xuanZeChuPai(st.wanJiaPai, st.shangJiaPaiXing, (st.shangJia === 2), st);
      if (r && r.pai && r.pai.length) return { cards: r.pai, beat: !!st.shangJiaPaiXing };
      if (st.shangJiaPaiXing) return { pass: true, beat: true };
      var s = st.wanJiaPai.slice().sort(function (a, b) { return a.zhi - b.zhi; });
      return s.length ? { cards: [s[0]], beat: false } : null;
    } catch (e) { return null; }
  }

  // ---------- 建 UI ----------
  function build() {
    ball = document.createElement('div');
    ball.id = 'demo-ball';
    ball.innerHTML = '🃏<span id="demo-badge" style="position:absolute;bottom:-3px;right:-3px;background:#2f6df6;'
      + 'color:#fff;font:700 10px/1 -apple-system,sans-serif;padding:3px 5px;border-radius:9px;'
      + 'box-shadow:0 1px 4px rgba(0,0,0,.5)">牌–</span>';
    ball.style.cssText = 'position:fixed;right:14px;bottom:120px;width:46px;height:46px;border-radius:50%;'
      + 'background:linear-gradient(145deg,rgba(49,69,92,.96),rgba(17,27,41,.96));color:#fff;'
      + 'display:flex;align-items:center;justify-content:center;font-size:22px;cursor:pointer;'
      + 'box-shadow:0 8px 22px rgba(0,0,0,.5);border:1px solid rgba(146,176,214,.6);z-index:99999;'
      + 'user-select:none;touch-action:none';
    document.body.appendChild(ball);

    panel = document.createElement('div');
    panel.id = 'demo-panel';
    panel.style.cssText = 'position:fixed;right:14px;bottom:176px;width:248px;max-height:64vh;'
      + 'background:rgba(14,20,31,.94);border:1px solid rgba(146,176,214,.35);border-radius:12px;'
      + 'color:#EDF5FF;font:12px/1.45 -apple-system,"PingFang SC",sans-serif;z-index:99998;'
      + 'box-shadow:0 14px 34px rgba(0,0,0,.55);display:none;flex-direction:column;overflow:hidden';
    panel.innerHTML =
        '<div id="demo-head" style="padding:7px 9px;background:linear-gradient(180deg,#26364B,#151F2D);'
      + 'cursor:move;display:flex;align-items:center;gap:6px;touch-action:none">'
      + '<b style="font-size:12px">🃏 伴随</b>'
      + '<span id="demo-tags" style="color:#9BB0C9;font-size:11px;overflow:hidden;white-space:nowrap"></span>'
      + '<span style="flex:1"></span><span id="demo-close" style="cursor:pointer;color:#9BB0C9;padding:0 4px">✕</span></div>'
      // 中间可滚动区: 出牌记录 / 牌池 / 出牌推荐
      + '<div id="demo-body" style="padding:8px 9px;overflow-y:auto;flex:1 1 auto;min-height:0">'
      +   '<div style="color:#9BB0C9;font-size:10px">出牌记录 <span id="demo-pc" style="color:#7E93AB"></span></div>'
      +   '<div id="demo-plays" style="margin-top:3px;color:#CFE0F5;font-size:11px;max-height:76px;'
      +   'overflow-y:auto;border:1px solid rgba(146,176,214,.18);border-radius:6px;padding:3px 5px"></div>'
      +   '<div style="margin-top:8px;color:#9BB0C9;font-size:10px">牌池 <span id="demo-sum" style="color:#7E93AB"></span></div>'
      +   '<div id="demo-pool" style="display:grid;grid-template-columns:repeat(5,1fr);gap:3px;margin-top:3px"></div>'
      +   '<div style="margin-top:8px;color:#9BB0C9;font-size:10px">出牌推荐 '
      +   '<span id="demo-rh" style="color:#7E93AB"></span></div>'
      +   '<div id="demo-rec" style="margin-top:3px;min-height:20px"></div>'
      + '</div>'
      // 底部钉住: 托管开关 + 页脚时间
      + '<div style="padding:6px 9px;border-top:1px solid rgba(146,176,214,.25);flex:0 0 auto">'
      +   '<button id="demo-host" style="width:100%;padding:6px;border-radius:7px;border:1px solid #444;'
      +   'background:#222;color:#ddd;font-size:12px;cursor:pointer">AI 托管：关</button>'
      +   '<div id="demo-upd" style="color:#7E93AB;font-size:10px;margin-top:4px;text-align:right">–</div>'
      + '</div>';
    document.body.appendChild(panel);
    badge = panel.querySelector('#demo-badge') || document.getElementById('demo-badge');

    ball.addEventListener('click', function () {
      if (Date.now() - lastDragTs < 500) return;      // 这次点击是拖动的尾巴, 不算 ✓
      if (panel.style.display === 'flex') { panel.style.display = 'none'; return; }
      panel.style.right = 'auto'; panel.style.bottom = 'auto';
      panel.style.display = 'flex';
      refresh();                                      // ⚠ 先填内容再量高度(量早了会压到球 ✗)
      var br = ball.getBoundingClientRect();
      var pw = panel.offsetWidth;
      panel.style.maxHeight = Math.max(160, br.top - 20) + 'px';
      var left = Math.max(4, Math.min(window.innerWidth - pw - 4, br.left + br.width - pw));
      panel.style.left = left + 'px';
      panel.style.top = 'auto';
      panel.style.bottom = (window.innerHeight - (br.top - 12)) + 'px';   // 锚下沿 → 往上长 ✓
    });
    panel.querySelector('#demo-close').addEventListener('click', function () { panel.style.display = 'none'; });
    panel.querySelector('#demo-host').addEventListener('click', function () {
      auto = !auto;
      panel.querySelector('#demo-host').textContent = 'AI 托管：' + (auto ? '开' : '关');
      panel.querySelector('#demo-host').style.background = auto ? '#1b3a24' : '#222';
      panel.querySelector('#demo-host').style.borderColor = auto ? '#3a7' : '#444';
    });

    drag(ball, ball);
    drag(panel.querySelector('#demo-head'), panel, true);
    refresh();
    setInterval(refresh, 1000);
  }

  function drag(handle, target, keepRight) {
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
      if (!moved && Math.abs(dx) + Math.abs(dy) < 8) return;   // 8px 内 = 点击 ✓
      moved = true; lastDragTs = Date.now();
      var x = Math.max(2, Math.min(window.innerWidth - target.offsetWidth - 2, ox + dx));
      var y = Math.max(2, Math.min(window.innerHeight - 40, oy + dy));
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
    var t = truth();
    var hand = myHand();
    if (badge) badge.textContent = '牌' + hand.length;
    if (!panel || panel.style.display === 'none') { autoMaybe(); return; }

    panel.querySelector('#demo-tags').textContent =
      '级牌' + (t.jiPai || '?') + ' · 我' + hand.length + '张' + (t.current === 0 ? ' · 轮到我' : '');

    // ① 出牌记录(最近 12 手)
    var ps = (window.__plays || []).slice(-12);
    panel.querySelector('#demo-pc').textContent = (window.__plays || []).length + ' 手';
    var plBox = panel.querySelector('#demo-plays');
    plBox.innerHTML = ps.map(function (p) {
      var mine = (p.seat === 0);
      return '<div style="display:flex;gap:6px;' + (mine ? 'color:#9BE7B6' : '') + '">'
        + '<span style="color:#7E93AB;min-width:52px">' + (SEAT[p.seat] || p.seat) + '</span>'
        + '<span>' + (p.zhi || []).map(function (z, i) { return cname(z, (p.hua || [])[i]); }).join(' ') + '</span>'
        + '</div>';
    }).join('') || '<div style="color:#7E93AB">还没有记录</div>';
    plBox.scrollTop = plBox.scrollHeight;              // 自动滚到最新一手 ✓

    // ② 牌池(0 = 打光 ✓ 绿字; ★ = 级牌)
    var left = remain(), unseen = 0;
    for (var k in left) unseen += left[k];
    panel.querySelector('#demo-sum').textContent = '未见 ' + unseen + ' · 已出 '
      + (window.__plays || []).reduce(function (a, p) { return a + (p.zhi || []).length; }, 0);
    panel.querySelector('#demo-pool').innerHTML = RANKS.map(function (r) {
      var v = left[r] == null ? '' : left[r];
      var isJi = (r === t.jiPai);
      return '<div style="background:rgba(255,255,255,.03);border:1px solid rgba(255,255,255,.07);'
        + 'border-radius:5px;padding:2px 0;text-align:center">'
        + '<div style="color:' + (isJi ? '#FFD86B' : '#9BB0C9') + ';font-size:10px">' + (ZHI[r] || r) + (isJi ? '★' : '') + '</div>'
        + '<div style="font-weight:700;font-size:13px;color:' + (v === 0 ? '#53D78A' : '#EDF5FF') + '">' + v + '</div></div>';
    }).join('');

    // ③ 出牌推荐(本地 AI 实时算 ✓ 离线可用 ✓)
    var rec = recommend(), rh = panel.querySelector('#demo-rh'), box = panel.querySelector('#demo-rec');
    if (!rec) { rh.textContent = ''; box.innerHTML = '<span style="color:#7E93AB">—</span>'; }
    else if (rec.waiting) { rh.textContent = ''; box.innerHTML = '<span style="color:#7E93AB">轮到我时给建议</span>'; }
    else {
      rh.textContent = rec.beat ? '需压' : '领出';
      var txt = rec.pass ? '<span style="color:#9BB0C9">不出（不压队友/留给队友）</span>'
        : (rec.cards || []).map(function (c) { return '<span style="display:inline-block;background:rgba(255,255,255,.07);'
            + 'border:1px solid rgba(255,255,255,.14);border-radius:4px;padding:1px 5px;margin:1px 2px 1px 0">'
            + cname(c.zhi, c.hua) + '</span>'; }).join('');
      box.innerHTML = '<div style="font-weight:700">' + txt + '</div>';
    }

    panel.querySelector('#demo-upd').textContent = new Date().toLocaleTimeString();
    autoMaybe();
  }

  // ---------- AI 托管: 用游戏自带 AI 替"南"出牌(全本地 ✓) ----------
  function autoMaybe() {
    if (!auto) return;
    var now = Date.now();
    if (now - lastAct < autoDelay) return;
    try {
      var t = truth(), D = window.__demo;
      if (!D || t.phase !== 'playing' || t.current !== 0) return;
      lastAct = now;
      autoDelay = 1600 + Math.random() * 1400;      // 人类节奏: 每手 1.6~3.0 秒 ✓
      var st = D.state;
      var r = AILogic.xuanZeChuPai(st.wanJiaPai, st.shangJiaPaiXing, (st.shangJia === 2), st);
      if (r && r.pai && r.pai.length) {
        st.selectedPai = r.pai.map(function (p) { return p.id; });
        D.chuPai();
      } else if (st.shangJiaPaiXing) {
        D.guoPai();                                 // 能不出就不出 ✓
      } else if (st.wanJiaPai.length) {
        var s = st.wanJiaPai.slice().sort(function (a, b) { return a.zhi - b.zhi; });
        st.selectedPai = [s[0].id];                 // 领出必须出牌(护栏 ✓)
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

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
    filter: drop-shadow(0 6px 16px rgba(0,0,0,.45));   /* 图标自带光球 ⇒ 只留投影 ✓ */
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
    + '<img alt="" style="width:100%;height:100%;border-radius:50%;display:block;pointer-events:none" src="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAGAAAABgCAYAAADimHc4AAAgAElEQVR4AezBeZCk933f9/f3ubp7eo6dnd2d7tkLe2FwTYMQQIIckCAFHqJl2qVSWXYUpcIqV/xHFNuUpVRJlstOlXNYSWQnkRNXaFUUUVRkisWSNTZLlETSDCWQIkjszJAgQIAgFsdiz57pubv7eZ7f7/dJ9w4HuwDRTuWv/OPXy/gP/n9ljHD//fdf+NrXnvwMA2YCIkCIARkg9hkg3mAMGAaIOxmGGAoSt0jcZphxixiQMDPAMAMBxj4xICGEYYAhDgjEgMDAMIaEOGAMGW8wMAxJCDFkGJhAxi1mIAYCYNxiDBhvELcZSGJ9bW3z/PkLH2QEY4RWa2F+eWV5yRgy7iQGJDADhCHAEEOGcZsAY8DAAMkQ4haJO5kZYAiBBGYYxgEzbpFACCRuMTAMMCQGxJuYMEBiwMDAEGDcJiRGM0DGPgECDMww7mSAGBJGu32z02w0FxnBGKHVWphfWVleAuOAECDAQIAZIAwDhNhnGGCAeIOBYQiBGBAHhGEIMDBAIMAYMswMIfYJJEQEiAPGj5LAjAEBAiLMQBJg7BNgCIGEGBJgGEPG2zMwbjEOCDAOCGOtfbPTaDQXGcEYodVamF9ZWV4yMySxzxBiyDDeTIDxowQYZtzBkAQIDBBgBgIMDOM2cUAYiAEhDBAgDAMEZhiGJG4T+wRE3GZggAJ3khgQEreYMWCAAGOfMWTGHQQYYIDYZ7TbNzuNRnOREYwRWq3W/OrqxSUxIAMEGG8m9hm3CWEY4oCZcZsBQoAxJCACxJAIGBFDAowhY0gMSAwJgQwzbjMwjCFJvD0hwDDAgAAY+4QYkJAEGBgYxm0GBkiYGfuMfeJNzGi3b3Yas81FRjBGaLUW5ldWlpf4ISGQcYuBMSQkw8wQQwIEGMaQYcaAAQGIAAHGjxJDQiADAyTMIgwQQuINEmCGsc9MgCEJM2NICoCxz8AAiX3GPgFinyEGJEAMSWBmgADDzBAGCGPIAHEnYRgCjHa73Wk0GouMYIzQarXmV1aXlxB3MECIAQkQt0XcJswMDIwIEHcyMyRxmwADxBsEMjCMO0kBMMQ+w4AAGBgYxgFJHDAMzAAhsc8AMRDAIpAYksQtBkiAcYsZBwwDxAEBhiGJNxi022udZqOxyAjGCK3WwvzKyvISGLeJfcaQFNhngGEGYkDCzLjFwDDAAAECjNuEEIYB4oAwDONHCTAkfkhgYAwZZiAZIMSAuMXMMAMkxD4xIAECDBAgwJAAA8Rtxi2GsU/cZkgMiFvMGFprr3UajcYiIxgjtFqt+ZWV5SUGxAFhGCDAEAEEmIGM24SZsc8wE/sMMCCwz9gnbjNAgHEnMwYiQAxJYsjMkMQ+wwAxJN7KLAIJMSSGJAHCzABDYiAAAgyJOxhmBggQZoYkQAgDMWCAMGPAaK+tdRqzjUVGMEZYaC3MryyvLIEAY8hMDJkZYkAgBcwihDAMELcZQ2YRELjN2GeA2CfuZBYBBgTAeHvGbWKfAOP/jcQPCUkMmRkGCCEZ+wICjAgIvMEMwxACgcSAwAzjtvbaWqcx21hkBGOEhdbC/MryxSVuiTBjQGCGYUhin3gTY58MEENmxpsZYGDiFonbDDPj30fihwQYQ2b8fyIxIECA8XYkAeI2A8Q+AwPDEAIxIMAQYOxrt9udRqO5yAjGCAsLC/MrK8tLHDAwjFuMAYEMEGCAGDIDYSCxz8DAGDKGDAMDSWBgGJIYMjOGJHA+0M8dZekJiMgMKWAyxIDEUMBAwswwM5IkplJJqKQRZvx7SQIMEHcSAjEgwBBDAoGZsc8wE2BI4hYDxIAwjJtr7U5jtrnICMYICwsL8ysrF5fA2CfMjDuZgWTsE0NmIAzEgADDzABhFgECjLcTBP1eSV44QhDmwTyEPvS2xe6OZ3vPk5dGrxAuGCDiCKq1mPF6RL0O1VogzgIkIkpjxuoVJscz4tgYRRJDkng7YkggARFm3GIGEgMCMwwQYp/RvrnWaTQai4xgjLCwsDC/vHxxiQEzAQZmGMZtAgwMDAMECAmEMWSAGRgRGAPGPnGgKD27uwXBexJBVERs3/BcveK5tl7Q3nZsFYFdZ/QEeTAKD6ULOCeK3OOdkRFTTyIOj0XMHYo4PhtxfC5m6kggm4xJawnTUzVq1ZhRJCExIECAMSQGJA4YBsYPCTDAMGNADAnRbq91GrPNRUYwRlhYWJhfXr64ZMaAMWRm3Cb2GRgYBwQCMWRgYBhmxlvlhWdrq0+kgBXG3prnyuuel68WtHsOl8ZUpipMHkoZG0+Jk4goAh+MshT9IrDbdWxsl3S2SjY2HVubJf2dEvUDmQKHMzgxnTJ/OuW+Vo1Dx40oizl2ZJyxsZS3ksSQGBKIAQMEiH3GkABjnwADzBgQYEii3V7rNBrNRUYwRlhYWJhfWVlZwgQCMwOMfQJjwABhGCDuJMAYMsyMfQYI5wIbWznBedy28cr3C154vcfV3YK4XmG2OcbJE1WOH0s4PBlRSSCOAIH3UJTQy6Gbw15f7O7B5q6ns1PS2XLc6BS8fj3n5o0e3c0ecV4wFYvT01UeujDBw++qM30SolpMY3aCaiVhnwECgRBggBBgCDAkMSQGBBi3GEMCDBAYIKPdbncajeYiIxgjLLQW5leWLy6BgRlDxgHDjFvMjANSAIwDZsY+A4QkdnYKut2c3nbg2e/mLP9gl2t9OHSkxsL8BPefqzJ3OGaiFlFJwIw3OA95IXoFdPvQzWGvL3a7sLsX2O0Hev1Ar+/Z3RNrmzmvXNvj8mvb7HV6JKXjSBZz4Widh+4Z552PjZHNislDNRrHJoiMOxggJAaEmTEkBSQQtxkGiH1inzHUXlvrNGYbi4xgjLDQWphfWb64xJBFDBkHDDMDE4axT0hgZrwd78V6p48vCr73bJcnn+nx4kaf6nSdR1uHefjCGKeOGIfGIuKIH+G96JfQz6FbwF4f9nLR7cNeN7DbDfTzQD8P9HORF6Lf93R7no2tgleu7HD59V3cbs44gbnxhPuO13nPj00x/3BMPJVx8uQhKlnMSAIBQkjigPFWAoyhdrvdaTSai4xgjNBqLcwvLy8vcYthJiACBBhm3GJm3GaAeKt+7lnf6FFsFzz5jR2e/H6XvTTlnvnDLC5McL6R0JiCLDHeSgLnRb8Q3cLY64u93Njri24uun1Ptyf2+p48F0URyAujLANlIcrC0+97dnsla+t9Xn19m+2NPqlzHM7g7FSVR+6e5LEn6mSNiJOnZ5gczxhFEmJAIMAQ+wQYIMA40G63O41Gc5ERjBFarYX55ZXlJWQMmQkwbjEwDBAQYcaAAeI2A8Rut2R7u8/a5S5ffHKL5at96scO8/53zTB/qsKZo8Z03YiMHxGCyEvo5rBXwG4udvqwl4teH3p5oNcP9PJAngf6hacoRFkK74QrhStFWTryfqDfL9nd63P1Rpf1m3uoKJiM4NR4yoOnx/nA+w8xfSFm9uRhjs3UeTuSEAMSQwIM8XYErLXXOo1Gc5ERjBFardb88sryEmIgYBZxwMy4zTAEZuwz9omd3YLdnZxXnt/ii9/Y5rm1krmzR/nwu49y/GjMyRmoVyLiWEQYQxJI4LzIHezmsJWLrS5s9WCvL/JCFIUoSk9eiDz3FGUgL0RRBspCuFJ4F3AOfOnwpacsPXnfsdfrs97psXZjDxUl9Shwsp5yf7PO+x+b4eSPVZhpTtKcneROAhQYEGJIIDATtxlDQiBot9udZnNukRGMEVqthfnl5ZUlEGCAMOMWs4h9Bggz4622dnJ2tvu8+Mw2X/7WDj/YKLj7vlk+8MgRZqZi5qaNWgZxDBEDBgJCgNKLvoPd3FjvwkYXdnPRzwNFGSidKJ0onShKUeSeovQURSAvAmUhylKURcCVHu+Ed47gPM4FityR9wq2NnM21ncJhaNucLye8cBcjfe95zBnHs44euIwjdkJDkhCCMkAIQljyDATGPvELRK02+1Oszm3yAjGCK3WwvzyyvISMjBAYGaAwAxjSIBhZuwzQOx1SzY3e3zv4jpfXe3y/FrJffcf5Yl3HWNiPGZmwhjLIE4gMm4REARlgG4BWz3Y6sFeCXuF6BUiLwPOCeeE94HSiaIMFGWgKANlEShLURaBovSUeaAsA2XpKYtAWXh86fClJ5SesnDsbvXZ2eqi0lOPEk7WE1onx3jvo9M035Fy/K4ZZo+Oc0ACAQoBEAfMjCEzQxIgJFhba3cajblFRjBGaLUW5ldWVpYYEPuMAQPDOGBmgAFiKM8dN9Z2eWGlw5MrPb5zvcfd98zy0cdmmRhPmKgZ1RSSGCwCGQgIgjLAbiG6OfRK6BawV4puIQonSi+8F84HnBPOibIUpRNl6XEuUBaiLAN57inLQFkEyjJQFoGycJS5oygcLveodPjCs7vTI++WRC4wGRmnJ1N+7Owk73nPFFPzCXffM8vURA0QQwIUhBgSQ8aAgWGAkBgQ7Xa702jMLTKCMUKrtTC/srKyBAGIAOMWAzMwjLcKQVy5tsGl5zb5+rdynnp1nWPHj/DTH76LQ5Mp9WpEJYU4FmAEEx4jIFyAroO+g8JB7qFbin4pcicKL5wX3oP3AeeFc6IshXeidJ7SBcpSuCKQ54Gi8JSlcIXHl56y8JS5o8g9Re5xRYkrSlzfkfcKQu5JfGA6MS7MVHnknhnetVgnOxmz8MAcWRoDBgiJASGJfYaZQIAZIKRAu73eaTSai4xgjLCwsDC/srK8hBlDBpgZQ4aB8SNuru9y/bUtvvQn23zz1S2KNOVvfOwczSN1xmsxaWpEkTAzvIFHBKAM0A+i8EYZROkj+j7Q91B4UXjhvfABvBfeC+c8zoFzovSB0gWcA1eKIoeiKCkKR1kIVwRc6SgLjys9ZR4oc0+Zl7iixOeOsl/g+h4rPJmM2WrEfXOTvOuBIyw8lpIcSXjg3gZmvEFiQEiAARL7DAOEaLfbnUajucgIxggLCwvzKysXl7glwgzMDBBmEW9m7HZz1to7fOFfX+PiKyWvbBX85I+fYuHuw9SrCZUsIorBEB4oDQJQCvIARQAncIJSogyiCOAE3kMIwgXwXngfcC7gnHAuUDpwXpQeylKUhSgKR5mX5IXHFYGyEGXpKQuPLx1lHnC5w+clvnCU/RLf94S+J/aBcTNOTFR5+MI0rfsPcaJVcPzsDM3GJG9HYkBIDIhbDNba7c7sbHOREYwRFhYW5ldWLi5xizCLwCCyGAnMeEMI4uqNbb7xZ6/z9Yue5at7XDh3mL/8+HEmx6vUKhFxDGYQAAc4oAAKQYFwAifhAYfhAwQgYAQJH8BLeCe8F855nA84B2UZKL1ROlGWoigDZREoCk9ZeIq8pCwCZREoi0BZenzhcLkj5A5fFLg84Hqe0PdY4agIDiUJF46N896HZzl1xjF1LuLBd5wgSxNA3CbAkIQkhGEIEGtr653Z2cYiIxgjLLQW5leWLy6BAAMDwzAzzCLutLHV48rlLX7n06/z7HXPjoyf+9h5jh8dY6yWkCUxZh4ZOAMHFILSjBJRmuGAYCIIgoEwzAwZSOAFPggfROkDwQWcE6ULOAeFE7kTZRkoC1GUoigCZe4ock9ZOPJcuNLjcocrPaF0+Nzjc4cvSsqex/c8yj2pF+NEHBvLeNf8YR5cOMTchS6HTk1y9/mj7DNAHJCEJIQBwoB2u91pNJqLjGCM0GotzK+sLC9JYsgMsBgDzIx9hveBqze2+YPPXeIb3/a8tNGndf9Rfvydx5kaT6hmMXFsmAUcUBiUgtLAG7jIKCMIkREAM0MRRJERxYAZklAAJwhByAfkPd6LwoleEegXIneicJAXgbIQReEp8kBROIq+p8gDrgi4IuBKRygdrvCE3OELh+s7XDcQ+p7IOWohYiqJuXCsxocea1Ib2+L0wxPM39dkrJbyZoYkgsQtEhistdudRqO5yAjGCK3WwvzKyvISAgFmYBYxZGaAAeLmepdXLnX4X/63V7iya+wF+Jm/dJYTx8YZqyVUUiOOjBBBjigFJYYz4WPDxxE+BiKw2LDYiGIjiY0kEmYQGUyn4kgFJjOYSKEWi9gCQYG8DGz1Au0949WNwPM3Hde2A/1CFEUg7weKvqcoHHkuXBkIhccXDl8EQuHweYnPS8q+J/QD5IHUBaYsZrae8p4HpnjowSnGj/Y4euEQF84f5a0kkAQIiVvW1tqdRqO5yAjGCK3WwvzKyvISCGGYGWaGYRyQxJVrO/zup7/PV5/ucW3PcfbsND/+6HGmxzMqWUISg0WGN8gNCsAZ+MjwsRGSCBIjSsFiSJKINDGyxJhIPWfHjUYNoijCiX0GCEwiUiBSILaA90bfp2Bwc7vgqVe6fP3lku1uoCwCRd+TF4GyEL70+L7H5x6VAZ87XF7gckfIHcoDcSEmBdNZyj1zVf7KR4/T7W9w+qFx7rl/jmo14U0EQQKEBBistdc6jUZjkRGMEVqt1vzKysUlhswwhgwz48Dubsnlyx1+7def57UO3Ngr+NDjp7hw+jD1akKWxESxITPKSJQG3gwfGS6GEEeQGpZFxKmRpkaWGNXUuDAZuDAV4c1IDGqRkZhhJjzQDaLvwXnwHkIAL3AeCg/eQc1ENy/4t9/Z5ulXHHnhKctAmQtXeHzu8X2PLzy+KPGFx+ee0HeEwhHlohbE4TihOZny0ccP0zyeMTkLs2cmuOvMDHeSQBL7xNDN9lqn2WgsMoIxQqvVml9dXV6SAmCYRZgZd7pxc4+vf/Uy//oLGzx3vUtUjfjI42c5cqhKJUtIkgiLDB8ZLjJcJLwZiiNCEqEELIuIs4g0i6hkxlQFHjkijo7HeMF4bKTGgAFiyCG6AfoeSg/Ogw+GD8IFKD2UDopS+EKMJZ7vXt7hc0/v0i2MovC4QvjC4/MS3w+E3OHKQCg9vudQHlDhyUrPTJwwU0155/01Hv/ALDdvbHLPo5Pc98AcZgwYICQhCWEYQkC73e40G81FRjBGaLUW5ldXl5ckMDPMIu5UusCNGzv8/u+8zNef6/H89R1OnprioQeOcWi8SppFxHGM4ogQGS42fAREhpIYUkNZRJTFZBWoZTETVfF4AybrMQKmIiM2kMBLBIELohDkAhcgCILABcMF8B5KD4WDwos8h729gvEkcKOzzae+vkO3iClL4cqA7zt84Qh5wBee4AKhFwh9h3JPXDoOWcSRrMqZuYSf/EtHuX5lj3e+f4rT8zNMTlQ4ECSQkBgQQ+32WqfZbC4ygjFCq9WaX11dXuIWw8y409Z2n5dfWudP/2iTL327w6udPRbub3LXyUnGxhLSNCaOY5REhDgmxEZIIogNJYZlMXElJqkY1UrMRAUea4jmVEwJTEWwvpmz8sI19ro9QnCMVRLiOMYBzgvnA93cg8WUgrHxCU4eP8pkPcN7I3eQl2KvF9je7jIzZly+scPvPdUld+BL4UqHzz0h94QiEMpAyD2h51AeiEpHPcCRNOPoRMqPv3+KajVhfr7K4bsyzp09woEggYTEgBDGWvtmp9mcW2QEY4RWa2F+dXVlCQQYZhFggBi60d5j5amrrH4n8Idfv8xG3/HQQyc5crhKrZqSpBFxEkESE9IIJREkCZYYIYmIKhFpNSKrxoxVjPumxbuPJ+wFKAvHv/vai8yMGe954AQz0+NEZgwVEj1B6aH0UHrwHvLSs9bZ4fuXrrOxkzMxNcWFCycIIabXF5s7fXp7OXc3Uv7NUzf5i0sB74VzAV84QiFUeELpCXkg5A71A1Z4Kl7MWMqhSsqDD1a4d36SWmqcf7jGvfcew4xbJIEgIAwhifbaeqfZaC4ygjFCq7Uwv7q6vAQGGGbGgRDgyvUtvvnVG/zFSo8/Xr6CkpQHWk0mJipUsoQ0jYlSgzRBaYylEZbGkERYasRZTFaLqFRjDteMnz5vKInZ65V84cvf5mc+eA/HDo0TmXHAS/QE/QClg9KD8+ACOA9FgMJB4cTV622ee+5lHnn4fiyps7WTs7HVo57CmZmI//pz19jOI7wXvvSEMhCKQCg9FIFQBELuiPJA6mBSCZNxzOkTMe999DC9Xcd7f2Kcc/NHybKYA5KQhBgQtNvtTrPZXGQEY4RWa2F+ZXVlyTCGzIwDee547fIGz3xji6U/W+Mbz9+gMl7nwr2zVMdS0jQmSWOiNIYsJsoSokpCnBqWRkRZTFKJqFRjarWIR44Zj55M6Trxxa8+ywfffYaj03UygRkgwyNKoB+g8FA64TyUwXABXADnoXAid0ZRir1ul+WL3+U9736Qzg50truUueMdp+p8+eJV/vhZh5chL4ILhNITigClUCmUe+h7EgcTIaZOxKFJeOyRCUIR+NhPzXDsrkmmD1U5IImgAALMWGu3O41Gc5ERjBFarYX51dXVJTDM+CEDxNZ2n1cvdXjte57f/DeXeO61DSqT45w+e5RKLSbJUpIsJkpjLIuIKilxLSbJYpJKRJTFpJWYai1hvBrxH90bUa/FvHJ5naLfpXXfSaoxxALvPRZFOIxSUAZwHkoPzkMZwAdwAbyHwkNeQu4gLxzr65vsba5zpHmKm5tdut2C49NjzNYK/v7vXaUgBYG8kINQeFQKlUK5sNyTOjEexVTKQCUWrfkqYxn8tZ8+xvTJMY4fn+RAkJCEARKsrbU7jUZzkRGMEVqt1vzq6sqSmbHPADHUXt/lhWfabF2v8j9/5lku3dgmHR+neWqaSi0lzlLiLMGyiKSSkNRi4mpGVolJKxFJNSarxozVYh6ahY9cqNL1xle/9iyPP3YP49WEhMAXlj7Pv/q9P+De+y7wC7/yyyiKcQLnofTgBT6AD1CUgWdXvsnm1g73PfI4noy88PT6JS88/yIPPXCGV9ZKdvZyJmsVHr9Q4xf/9+e43kuRxUBMcKDCQxlQEQj9gBWBLIipLCHqeqwsOdVMODIZ83N/4zjTJ1POnp0BBIIgIYYEEmtr7U6jMbfICMYIrdbC/Mrq6pIBZgwYB260e3znqRt0Nyv8s//rGS5v7GKVGkePT5DWUpKsQpTFRFlCWk2o1FOSWkpaTciqMWktplo1PnohZmFa1KfH2eqWPPPsq7zrneeophHf+rM/5wtLf8QDrQU+8Xd/kU995nd57IkP4SScN5wgBPABnBNf+sPP0l17nf/mn/yPfODDP8Ev/LefpFRMt1fyyqvXuOfUBFd2Unb2CipZSi0uiF3B7//5Bld2YiyKUTDkAsoDKjzqBywPVCSmqynaLXF7faYnYuaOxPzHP32cuXsrXDh/FDOQhCSEAQKJdnut02w2FxnBGKHVas2vrq4s8UNmxoFrN/dYfvIm+U6Nf/bpFa5sdgmVKuOHx6iNV4grKUk1JqqkVGoplbGUdCwjqyWktZRKLeLoZMQvva/CxmafiSNTXL6+Rdnvc/ZsgyyB/+5XfpXf/fTn6Bdd9nY2+fXf+A3++sf/Jl7gAgSBF3gP25tb/KO//be4+8JZPvnJTxJF4l989k9pnH0Hu92C9c4ek2mX3Wia7a7HTLiddT7w8F28cOk6/9Pnt/GWIGKCC6j0qAjQc1jfUQGms5Sw6yh2ulRTODNX5Wd/6jhnH6xw7vxRzEACSUgBIQyj3W53ms25RUYwRmi1FuZXV1eX+CEzAwwIXL3e5RtfvkbkJ/j1336aK5tdfJaR1jOqEzXSWkZSS0mqMVktI6ulZLWMSj0lG4upjCU8eDzhZ39sjI2tHvXDUzz7whXONKeYPlwnlfi1f/Rf8Zv/8pP0+z1mDh/lt37/M4xPTHLjtddoPfIozgV29/YoLUHE/PWPvI/r16+gUDJWrfPf/+bvce4dH2Brt2Bjq0uNHXrZUbZ7nq3tHR47V6EgJu/Bp754nVc3Y2QRCkJlgELQL4l6jizAZBzjdxxlt0sWi3tPT/BXPzLLPe8a49z5I0QRBAkJJIECQ+12uzM3d3yREYwRWq3W/Orq6pIZCDD2SeL6jS5f+9PrpDbBP/3U07ze6eGSiKiaEo9VyOoVsvGMuBaTVStktZRKNSOrp2RjMdWxhA+cr/Do2So1c8RjdS5+5xLvuNDkRC+nur7HM9de41f/xW+wt93lgz/5QX7u53+ep7/6Ff7Xj3+cxxZaTNTHefqZFd7zX/xtPvY3/w7/+Jf/Hl/+4p8Qy3PXyZP803/+2xRjR7jZdaxv9hiPu3TTGbZ6nq2tHZ5oHeHKRo+KJfy7b17jyZc9WIIEOEERIPfE/ZLUwVgwtFMSipxKZrzj7CSPv3uahcfqnLtwhDg2BIQgJCEJA9rtm525ueOLjGCM0Gq15ldXV5bMjDtJcO3GLl/7k2vETPAvP/sdXry+SxnFWCUiGktJalWy8YS4lpHWKmS1jKyaktVTKrWYWj3lifMJ9x4fY7YWsNoY3372Ze4/c4zz1zfItnt4i3nt1BTrRZ9Dx5oEi9hZv8nnPvZX+MjZ+zk51+Dy9cuEn/9bNB95nO3OGv/2s59hZ73Nxx/9AHeNz7JXOr57aIZLPc/hqmMrPsR2z3PjZof3vWOOyzd2mW9O8KWnrvFH3+1DnGBE4AMUHut7otyR5iIrhHUd5jyHJmIePFfnxx6Y4sH3jXHu7qPEsTHkg5ACEhii3W535uaOLzKCMUKr1ZpfXV1dMuNNJHHt+i5/8eUbhKLOH37pJS7+YJ0+gkqCVRPisSrJWIW4mpDUUtJaRjaWUKmlVGoJ1bGU951LOX8k49SUJ5uc4rXL16hYzLmJcerrW+RjNbZmpvBmeECAIbpPfoUHfvAaSRDrp5u0H/8QjoQQhPciKUrueu4SvrdHryj53tQhnumLe++a4pXtKru559VXrvLud5zm5sYuT9x/jN/6/CX+7JLDkgQsxnzACg99T9z3xP1A2vfEuScRnJ5LOdccp3XPBAuLGefmjxJFhgRBQhIIhFhba3fmmnOLjGCM0Gq15ldWV5YMAxOGceDK1S2+/Rcdtjcy/vxbV/nWC+us93NCEjmCqugAAB/kSURBVEM1Ja5ViOsV4kpCPJaQjqVk1YysGlMZS6lWU45PR/zV+2tkbpvZU8chlHzjWy/wwH33YGYEQTAQEUKAsU8k3R3M5RT1aRwRIYggUBDeeSrbe9Ta62yFwOvVOteuX6P1wFlebIte7rl85SbnT88Sm+ejD87wy//H93lly7AkwSzCJKzw0PMkvUDU8ySFyErP1BicOV5jbqpG655JLjwC5+ePYWYECQkkkAJDa2vtzlxzbpERjBFardb8ysryEgaGYWYcuHp9mxdXN7ly2bj4nZs8+2qP1za2yQlQSYiqVaKxjKiakIylJGMpWS0hq8Sk1YSskpFmCY+fNR5teI7MzbJTGNZd55mX1jnebHD6cIyZ4YJROJF7KLxwwQiAD8J7UThRhIggQwoEH/DOUxae3Hk6G+ucmTH24qO0dzylE+vrm6RJjbPNjPmjEf/lp6/jk5QoiYmiCJOw3GP9QNwNxH1PWgYmEjgyZZyYHuNYvcqDCxPM3Vty970NhoSQAgogwBBra2udZnNukRGMEVqt1vzq6sqSEIYBhpkB4sbNXV753gY/eN7z/IubPPtqj+s7OVtlQRmBVTKsmhLVUuJ6SjqWktYS0kpMkiXElZgkTUkTo3Us8J8/MctLG0YWQ0U98o2bvOveExgR3fU2lelpBAgwixgKIeB8wAd46rk2T9+IqWYJZhC8p9vNCcUuZ46lWG2G65uOvRyiKGIsEdeubvDhh5v81p+8wjPtiCRLSdKEKDLiIKzwRD0R9TxpKcYQEzFM1yNOT1eZSlMeXZxi6nTB+QvHACFAISCJA+21dmeueXyREYwRWq3W/MrqyhIDhjFkxi3t9T1uvLrJt58uePVyl+cu7XF9p2DHO/qRcFEMaQy1jHgsJa2nJLWItJKQZBFRlhClMUmSUEvg772/zvRkneu7whCTfpOHTk1BWfDCP/iHnPsHf59oagqJAYEZwjAMAS997yU+e7HNxNQk1UpKmmVM1KtUqnVubJXs9j39MuCCMVVLuK9ZJy03+dXffpXtkBHVKiS1hDRLSMyIg4gLiPuBpBDVUlSDqMeBI/WYu6YrVKOU9314nOpRz5kzMwgQQiEgiSEBa+12Z27u+CIjGCO0Wgvzq6urS9zBzBja3sm59lqHi1/bo73uefYHe1zdKth2jr6BS2JCGhOymKiWkIwlpNWYpBITZxFRlhClMXESk8RwuAJ/rZVxvePYK+Gu6Zi/fP84+UuXePV3/hXH3vseDn30w0hCCAQCBJhFXL10mV/7g+eZOXWW5uw0aZYgRRTe0y88RenxISJJIk4dqrLQgH/8Oy/yvRueqJKQ1DPSWkqWpiQYqSBxRpJ70kJUShjzYiKB2YmYE5MpSZSw+KGUeiNlbm4KSQiQhIIYEoG19lpnbu74IiMYI7RarfnV1ZUlMwaMOzkXuPL6Jt/8Spud3YzvvLDN5U7Bjvf0DYooxidGyGKsEhFXE+JqTJzFxFlEVImJ05gkMeIo4siY8YknJujlJZ/74+9yeO4cf/fxSW784ec58nCL9a8+ycn/7D9FGEJIIAkBZhFb19v8nd/4Cnv1OWaOTjM+XkdRzNbGDnubW1gcU6tPMFbLOHtsnM7VDp9fLYirCVE1IamnZNWELInJLCKTkTmIi0BaiGoZMe7hUCbmJhOOVGMqY8bC42LuzAzj4xWEkBgQUgAxINrtdmdu7sQiIxgjtFqt+dXV5SWziLeS4PUrWzz71A3W2xW+99IeL7f7bPlA36CMI1xshBiUxViWEFeMuBITZTFRJSZOI5IkppJEfOJ9dR4+N45zHu8cT7+0w4W648jmOr2v/N+oXmf64z8LZsgMCYICiAGjt7HNP/nUk7zzvQ9w6sQRXl/vMVHNGI9LalOHuNJxvHC5S+Hg2HjMTFLyDz99GWoVkrGEZCylWk3I4ogsislkVJwR9wOVEsbKiEnBTA1OTCakXhw9ZZx4MHD+niZRZAghCQRS4EC73e7MzR1fZARjhFarNb+yurxkRGDCMPYZIK5e2+XKD9q88F1x9Ybn+9d6dHJPHkGeRPgkIhgojVBqWBphlYgoS4iziCiLSdKYE5PGr/3UUfo+cLSegcFr24HvfftFHio2CJ/4RaJ3PszMP/8fIIoAI0iEIIQAo93eYHqmTlyf4LVd2O6Jnc1dxsfH2CsidrqOIi+5utbnUNU4PV7yS//nZUI1I6mnZLWEapaQJQmZGZVgZKWR5aJWRow7Y8rEsTFjbjKiu1Nw/2KVSsNx9z0NJCGBJCQQwhgS7fZaZ25ubpERjBFardb86uryEm+IMOMNO7slV169yTe/usteN+O5V/do9xz9KKJMI1xshMgICYQ4ghRIIyyNiLKYKItJs5jWXMonnjjMTuGoj1XInbi5bVx66QYnyxvcG3Wpnj5FcnQGhQBRhAJ4CRkoiB9cvs6Ze87Q6UN7R2zuBtrr20hGoYxeryTB0y8DR+oJJ8Ydv/Sp1wm1jHQ8pTaWUq3EVOKYTEbFGVlpVAsYLyImQ8R0Ejg2bhzOYLvraD0RUZ+tMHf8EAgCIgQhBZAAwwzW1tY6zebcIiMYI7RarfmVlYtLYAyZGWCYcUsI4uVLN/j2UxtsbdR44ZUuV3Y9vTjBZUaIDWfgDUIMIQFLDJIIyyKsEpOkKedmjF/60AybuVCc0Stha1dceuEyze7LfPgnHiVNjO2lP6L/6d9n7D/5GfI//yZhYoypX/kFFKd858UrHL3nAjs92NwJ/D/twUuMpel91/Hv7/8873sudel7d5322I7H4ylP7DpOCImghBBRhLINK1iEBbBgA6tsIlYERSABEgogFHGLUCKRTQKFQkCOE1kBDLEzVWU8mcQee9rjmbGn+5yuvlV3V53zPs+Pc6qmpycOZ82Gz+fo4Qm3Jw+ZzeY4+tRirqwF95+aT1ztsd7M+Nlf/S55vUdvvWUwzAzbTD9lmip6c+jNzeA02JwHlxCXe2K0DuV0TrMJox+e8eKnb9C2GRuMcTW2sQ0YSUynd49Go9EuK4gVdnZ2tg8PD/b4EElI4pm3vnPE7e/cY/8rhcn9ylv3Ko8EpU3UnCiCgukEJYEykIWaBL1EahL9JviZv7DG6dy43eDxSWEyfcIb//OL/OTOiB/6sR+kSXD003+dOHgdK9DclJRZ//V/S/PpT/HVr72Db77APPrce3DK9P4TpkePcTenbYd85PIa9x4/oXPmRz825PDWhF/6vcf0NwcM1jNrg4ZBm+hH0NSgP4f+TKyfBptdcC2JqwO4sWHe+d6M7T8bcKXj5e3rgLCNbWxjV4wRYmk6vXs0Go12WUGssLOzs31wuL8nwIAQCELBMycnHbfe/B5f/K373D9ueft+5UERpQloMjWgE8wwReBkyII2oyZQDnJOfOKS+IufCG4/MPcedex/9XV485Cf+5m/xJWtq+Qm8+Q//QanP/vzqBRw0H38Ba782r+BjYucPp3zG5//fcroFU7VMOsq9+894PqFTS6sZ966fZ+51vnoxZY/vz3g5379Fm8+aehv9lhba9joZwY50VPQlqA/N8OZ2JiJKw6ut+LGBmRXpo/NJ//cKWvX1rhyeYgEtrGhuoKNAXFuevfu0WhrtMsKYoWdnZ3tg8P9PSE+IBESH3brrSPeeG3Klw9mHJ0kpjNRUoY2IAUdMMfMVSlJkICcURsoJyIFiuBiU/irP9Tjv/zeO/z3P3iXz16Ev//XPkdvfYgiAebBL/4S5Rf+FWxtsfHPf57ezmexg2r4vS/+Pn/nV77CS5/7YS5dvcKgycxq5WRW2Lp6mcvrfT671QM94e/957s0GwOGmz02hy1rbaKfg9ZBvwsGM1ibmYsl2Irg+hrcuFz5zndg6xVTrxzz0svXkQIwIKor2NgGBBgEd6d3j7a2RrusIFYYj3e2Dw7290CcE5KQDIhnHh2f8vatO3z+C/e5/TBx5zQxt6BtUBPUEHPMXFACnKDmwDmIFEQSViCJn3xJfOKSePWNh5Qnx/zNH79Ob20IBBLgytEv/3s2f+xP03z6ZSAwwdK7t97hb/2L36V//QXWNzZYGw64fHGDi+sDBm3LlfWGl6+ZX/j897g9bxlutmyst6wPGoZNph9Bv4r+HNZmZqODaxHc6IsbF407uD3p+MiPzehf7HHt+gZgbM7YBowxGKTAwHQ6ORptjXZZQaywMx5vHx68uicFdgUF4hkhccaGt96a8q2vP+SLX3nM0Wnm8Vy4aYheg1OihCmCElDClBQ4BySICBwsiI9tFn7ixcL+tx6QKvyN3SusbWxgGQhASIANmCeHr+F5R42G+sIWf/eXv0xc/RjXr19iMOhTqrk7fcDDx6e88vFLHH77hO/NegwvtKxt9tgYNgzbhmEWAwe9IoYzsz4XVwQ3emJrEy5dMt/4WmH0g4XTtVM++fJVIgLbGIONzYcYFAiYTCZHo9FolxXECuPxzvbBwcEeMlggEAbEkhBILD1+MuOd79zlC799lzfeM4/miS5lUr+PmkRVUANqVLowJYmahLMgBBEsXeiZv/3jF7n9YM7/2n+Dv/KnLnJzdJ2KQGCDeO7BP/1FZv/sX/P4Uy9z49/9Av/gV77MHz1ItP0+/X6Pfr/HpWuXuXn9Ej/64oB/9JtTYq1lbbNlY61hrd8wzImBEj3DcG6Gs8rFGlzL4saGGN0wd98pPHxcufq5GcPNPleuDjELhkoFCzDYgDknQEyn06PRaLTLCmKF8Xhn++Bwf08Im3PiAyKQ+MDb79zn9nce8B+/8JDbj8WMRLQtadBCSjiCEqaE6TI4BSSoCRwJJIT56R9pWR8Muf9oxkvNXT7+0avYgACzIMCcmc2Y/sN/wsW//FPER1/gH//L3+KNcoVPffolrl9eo1Tx+KTjxa0h3/zeQ758O7G22bK+llgfZNbazCAn+k70qxnMzcbcXCW4MYCta4aucuu1OR//M+be/IRPv3IDCYoNBmMwCwabc+acmE7vHo1Go11WECuMxzvbhwf7e+YZ8WGSkMQzXVf55jcnfP0P7vOFV2c8OBVOmWbQI/canIKaRE1QEtQcOAsHOAUOYcQLm4WfGm9wdAzNyQM+udnRNkGvbWiaRISQgkgiRZATZ2anM37tt/6Ir0waRh+9zvpwwNMZrLVwecP8h6+d0N/ss7beY20QrPWCYZMYpETfoj83w5m5VOBaI25eqgwH5ttf7bj48cqTtWN+4MVrDAYNtqkGbJbMMwYM5pzEdDI9Go1Gu6wgVhiPd7YPDl7dY8kCARICbEBCgCSeefjolLfevM1/++8P+P1vVZ50oun3aAd9ci9Rc1CzqFk4BTULMjgFDoEEgh/ZKrx4uc/kYeGNt4+49+CYB/efMr39mF4OLl8YcmmzpZdgkDquXuyxdbHhD9+b8zj3uXBpgxSJHOLmZfP5b53iXsvaesvaMLPWTwwb0UvBMIJ+heEM1k/hEpUba+bihvne63OaDRMvnLC2OeDG9XUM2MYsGWxsQGJJGDC2WJpOJ0ej0c1dVhArjMc72/sH+3vifQIhlmw+IAlJPPPue49499aE3/7dY15/tzJz0Bv0aQct0Ta4DZwTNQuycAZSQAOKwAFUM6wn+PSUh8cnTI6ecu9RRyFRq4gkIgWKBBIKcXkt2L45oN9v6bcJAdFWbj01GvTYWG9YG2YGvWDYBP0sBiHWBP0i1k5gozOXc+Viv3L3Wx3FhQs/2PGkmJc+eZklY1xZMDagChZLkkCAWTBGTCd3jkajm7usIFbY2dnZPjh8dU8IEJI4Z2wWDBgIJCGJJRu+8eZd7r57j//6xWO+dccUEr3hkNxriH4DvQRZ0Ahn4QTRBmoCUiBM15mTpzNOTubMZoX5vKNUY0SEiCxSSkQWkogsckDtOlIWvbWGtQt9BsPMcNAwGCQGPTFoxKAR/QxrMsMq+qcwPIULVNYMR988wVSufbZwdFrYfvkKEgumGmxjG7EgwAYEMlhIYBskptPp0WhrtMsKYoXxeGf74GB/DwSqiADEkm2MwSAJMFIgiaVazWtfv8PD9475zd855ta0Q6lHb71PahvUa6Af0ATKggaiSUSTUCMUnKm1Mu8qXSmUUnE1FkQkIonUBJETKSBSEAmaxuReommDtg3aXqLXE4Ne0G9h2MAww0aGoU1zKvozs1FEemJu/+EJuPCRzxVuH8955ZUrpCTMgjlTa+WcAYEMCNkYAWZJEpPp3aPR1tYuK4gVxuOd7YOD/T0wIBAIYcCuYHFGIMSSJJYk0XWVr319yt237/M7XzrhnbsVcsNgs4+aDL0GtwmyUBOoDVIbRCOUhJKIAGSEAGMMgkgiksg5SE0QKYgEkUTOkFpomqBpRdOIfk/0G9NvxEY2m0msCdo5tDMYVigPKm//7znJc7Y+M+fOccf29hXaNrCFMWCwsY1tJPEBsSBw5ZyQgsl0cjTaGu2yglhhPN7ZPjjc32PJLAgQYMyCzQfEghAgCUkszbvK1/7wPe69+4gvvVp4a2KKxPDikNRvIAelSdAk1AapDdQEakTKosmQcpBTkDJEiEiQAiJBNBBJpEZEFjlByiJnSA20DTSNGDSwlmBdsCEYAj2gZ2gKPHqv8vZrc3ptx8WPnfDeo46dz16jaRLG2ICNWbABAwYEmHMCxDkjwMB0Oj0ajW7usoJYYTze2T443N/DvE8smecE2LzPSCwISUhiqZTK61+/w733HvLV1wpvfFc8KbB2YchwrYdzUHLCbUAj1AsiB6knmiZo26Bpg6YRTYaUIWVIWeRschbRQCSRk8mNyAlyhiZBP2AoWAfWgSEwQCSBC0y+XZjc6ljfnBOXT7j3FD77ymVyTtim2pgFG1w5Z0CcM88JBAJsFsRkcufo5s2P7LKCWGE83tk+ONjfAwPBOWNAPCPAGBBglowQkoBAAhvefOuI9965x3ff6fjqmw3TY9MOWi5c7JP7DTULN0Ftg2hE6omml+j1RK+XaFtoW8iNyNk0DeQGcgM5i5whJ8gJmoAGaIEe0AP6wDrQlxDw5LG5/fac7rhw4fKcuydPaYYDXvzYJpIBsWRMtcEGGzAgjBECDAgJbEC8T2CYTqdHo9FolxXECuPxePvwcH/PNgIqBgQWCDAg3mfAYM5IwTkhCYkzR/ef8o1vTDh9XHjtzcybt8VJB2sbLZuXeuS2QU1AK6IHbS/R9IN+T/R70PYgt9A00DSQW8gNpARNNo1EBhpEBhImCxrDOjAUnJyK6bRyctyx0S9EM+PW24/4xCcucu3aGufEM7bBlWfsCgibM5IBIYERS0IYA2I6nRyNtka7rCBWGI93tg8OD/bAYM7YgFgIcAUBBokFYZszAgFGSCIkQIDpSuXNNx9w/+iY+8fm9Xdavvsg8bRW1td7XFjv0faD3AtyT7T9oNcT/T60PWhbaFvILTQtpAyRIQKyoAFCEOZMAG2F+gge3Td05mK/Y9DrePf2AyJlPv2pq6QkbP4kV54zNtgsGARiQYEQHxBgg8RkMjkabY12WUGsMB6Ptw8O9vc4Y0CYDzOYBYEMCDDYCIHACCEkFoQEZsFw/GTOm99+yOmTpzyaZ14/6vH2w8RsBr0cXFzLbAwTg0Gi10LTirYHvR70WmhaaBqIDJFACSSIAAFdZ04ew5OHMDuurEfl5oXK5WFleu8pT07mvPQDl9jc6GEbA9V8HyOzUEEBNsZgYYwQZ2SEQAKDBAYETCbTo62trV1WECuMxzvb+wf7e0KAMAYbJMQfZwPifQLMkgBJfJgNiDNCPDye8c47j3j65JSSgjvdgFuPGu4eJ05nkARrbbAxEOv9YL0Paz3ot5AzhMCCUs1sDiczc3Jqujm0CS4POz5yEfo65d6DORHBR2+uc3GjBQQYAzbYYIx4TiyZJSPAYHNG4sOkAMwHDJPp5Gi0NdplBbHCzs7O9sHB/h5LEmCEMM8IsWSWzIIBsSCwQSAEMlgsGQPijCAQS7N54b3bx9y7e0yplTxoOY4e05OG6RPx8GmiK4ELRBWJSk/QZGgztA30m8J6X1xeq1zoF+jmHB/PmRdzYXPAC6M1+m3CiHPGZsHYYBZsJMCAjBRgc0ZiSYBtJDDnhECcM2eMmU6mR6PRaJcVxAo7453tg/2DPTCSAAPiGWOEMEsCmw9I2GZJGBDnjAGbM5IAsSRxxjYnp4W7d485fnTK7HSOFESqpJyJJohoIESSSFRsU0phPi+czsW8AynY3Gy4cbXPsN8AwjwnwDbGLAljsyAkY0AIhRBLRgoQCwKbJYkF8QEJ24DBMJ1Oj0aj0S4riBV2dna29w9e3RMLCoQAY84JsM2SWTDgilkSYGwwIJaMbWwwC+aMEUJgFowB2xghwIAN867w9LRyclroCgtGgGRCom0T/V7QJAFGLIklAWbJgBDmOYOEWDKSQCAJCSSQAgmkYEliQSxJLIgz4kOMEJPp9Gi0NdplBbHCznhn+2B/fw+BEEs2zwlsgyuuYCquphowGLA5Yxu7UquxDYZq4wo2mAWDAdvYwjbYWGCLJRuqzTMCbDAGG5sF8/3E+wQSCJBAAiEUIgQSSEIKFBASkYKQUEBEILEgJCGBJCSBQAbE+wSC6WR6NBqNdllBrDAe72wfHOzvcUbYYJtzBoRdqdXYlVqNbWo1tRobbFOrqdXUUqnV1Fqo1dRqajWlmlpNraYaSjW1VmoF29hQa6UaSq3UyjkbY0DY5oyFWJCRhMSCkIQkIkASIREyERARpCRCIlIQEimJFEHKQUpBSkGKIFIQISJACiIgIpCEJCQBQjJIYDOdTo9Go5u7rCBWGI93tg8PD/ZA2MY2ZsHGBrtiG1coLtRSqdVUm1pMKaba1GJKKXSlUkqllELpTKmFrlTmXaXrTFcqtVS6UigFaq2Uamo1pRZqhVIrtqkGmzO2MBUcSEYSQiAQQgpSQESQQiggJFKISJAikbLIKcgpSCnIKchZ5By0OZNzkFMiN4mURIogAiIFKSVSElIgCQkkgQSI6WRyNBqNdllBrDAej7cPDw/2WLBZMLUaMLVWbLBNrZVaK6VWXE0tUEqhVNMVU0ql6wrzeaHrKl0pzLtCKZXZvDLvCvN5ZdYVunmhK5V5VymlUEqlq5VSKrVUSjW1mlpNtTDmjMFiQUjBMyEREaQU5CRyClIEKUQkkXMi56DJQU5Bk4OcE00Ocg7aJtHkoM1BmxNNm2lyIiWRkkg5SClIKRERKAJJhIQESEzuTI5Go9EuK4gVxuPx9uHhwR4L1YCNbcDYYFdqNbVWaq2UWnGFWk0tpiuFUipdqcxLpZsX5vNK13XM54V5Z2ZdZd51zOeV+bww6wpd1zHvKl1X6EqhlEIpla5UulKpFWyoNksGbMBggRBmSYRERJBSkFMip0RKIieRUtDkRNsETU7knGiyaHKibRNNTrRNom1EmxNNTrRNJjdBTkHKIqcg5UREEBFEBAoREihYmk4mR1tbW7usIFYYj3e2Dw8P91iwwRgMxtiATXXF1dRaqbVSK9hQqymlUkul1Eopla5Uuq7SlUo3L8xLpesKXVfpusK8VObzQlc6uq5SSqXrCl2plFLpSqVWU2vFBgM2GLDBGCNsIYEkQkIhUgQpBTkFKURKQUpB2yRyClIKcg5yDnISbZNocqbNQdMEOSWaHKQU5BSknMgpSClISSgSEUISCiGEJJYmkztHW1ujXVYQK4zH4+3Dw4M9FmxjBBjbfMBgV6qNi6k21ZVawbXiaqpNrVBrpdRKKaYU05WCq+lKoZRKLabUQimVUiu1VEqt1GpKNaWaWivVxpUzZsFghG3OCYkFoRACFEGESClIIVKIiCClICWRIogU5BApiZwSKYmcgxwiUpAiiAhSEhEiIogIUhJSgIQEUgBGnJtM7hxtbd3cZQWxwng83j483N8zArNgjBDGnBNgs2BqNbVW7IoNNtjGgCtUG1fjWimuuJpaTa3GNnalVqiuuEKtprpiGxtsY4wNNpglYXPGNkIgY0CCkFgKBRJECCEUIgSKICQiiRQiQkgiIogQIREhJJBEhJACSSggJJAQAoFYkFgS5+5MJkejrdEuK4gVxuPx9sHB/h7/VwbEOQHGBtvYFdss2bzP2MIGu2Ib27iaamMMNrZYssE2tnnGZkGAsc0zZsEsCGPOGcyCkYRCiEACCSSBQAgJFCJCSEKAJCQhgRSAkYTEgkCckcQzQoA5IyEEmDuTydFoa7TLCmKF8Xhn++DgYI8z5jljCwRCgAADxjZLNgtmyYgzBmNwBYRtlmwWjA0SZ4wQYJ4RGJDBZskGJM4ZIWxjm3PGBiQkIUACxIIQCwIhJEBCPCMkAQaEMUJI5pw4IxYCMEt2ZUkKxJKZTCZHW1s3d1lBrDAe72wfHOzv8T6zYBYEVCCQeJ85J0AYgw2YZ2w+YIw4ZxZszgWSQAIM5pwENks25wQSYECAwSwYjDljI7EgzkicsUEsiCVhkBDinAEB5o8TEgvmjAUSYJbsii0kgYwQk8nkaGtrtMsKYoXxeGf74GB/jzMCjM2CMSDEksSCeM6YJYENGANCgDAVzIJBQohzBgRiIRDPmA+zKxAsSSyIc8YIMBjMkhEfJsCcEx8m8T5j8ydJgBHPiCUDQoCxzfebTidHW1s3d1lBrDAe72wfHOzvScIsGVvgigGxIBDBh9nmnEAgjM33MWckMGckYYxYEiDALEmcscE2IARYIP44YzALAgwYEEsSC8Is2IA5IwFCgFkwC2bJLBgkQAKMACMwCwbxnHmfATGZTo5GWzd3WUGs8JnPfOZTX/rS//hVBJgFY7NgDIglgQAbEEtmwUYSIKBinhPinAFxTiAWzJIQSzagigjO2BhjFiwQiGcMCrA5Z2wB5oyMECDO2JjnJBbEOWEM5jmBeM42EEBFAkmYBYMBcW46nd5/6aVP/QQriP/v/6n/A4maZFDXip9UAAAAAElFTkSuQmCC">'
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

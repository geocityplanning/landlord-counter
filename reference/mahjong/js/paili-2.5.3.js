/******/ (() => { // webpackBootstrap
/******/ 	"use strict";
/*!*************************!*\
  !*** ./src/js/paili.js ***!
  \*************************/
/*!
 *  電脳麻将: 牌理 v2.5.3
 *
 *  Copyright(C) 2017 Satoshi Kobayashi
 *  Released under the MIT license
 *  https://github.com/kobalab/Majiang/blob/master/LICENSE
 */


const { setSelector, clearSelector } = Majiang.UI.Util;

const model = {};
const view  = {};

const rule = Majiang.rule();

let pref;

function repair_shan(shan, shoupai) {
    let paistr = shoupai.toString();
    for (let suitstr of paistr.match(/[mpsz][\d\+\=\-]+/g)) {
        let s = suitstr[0];
        for (let n of suitstr.match(/\d/g)) {
            let i = shan._pai.indexOf(s+n);
            if (i >= 0) shan._pai.splice(i, 1);
        }
    }
}

function qipai(paistr) {

    model.shan = new Majiang.Shan(rule);

    if (paistr) {
        model.shoupai = Majiang.Shoupai.fromString(paistr);
        repair_shan(model.shan, model.shoupai);
    }
    else {
        let qipai = [];
        while (qipai.length < 13) qipai.push(model.shan.zimo());
        model.shoupai = new Majiang.Shoupai(qipai);
        model.shoupai.zimo(model.shan.zimo());
    }
    model.lizhi = false;

    while (model.shan.paishu > 17) model.shan.zimo();

    $('form input[name="paistr"]').val(model.shoupai.toString());
    if (paistr) history.replaceState('', '', `#${model.shoupai.toString()}`);

    view.shoupai = new Majiang.UI.Shoupai(
                                $('.shoupai'), view.pai, model.shoupai
                            ).redraw(true);

    model.he = new Majiang.He();
    view.he  = new Majiang.UI.He($('.he'), view.pai, model.he).redraw(true);

    paili(1);
}

function set_handler(focus = -1) {

    if (Majiang.Util.xiangting(model.shoupai) == -1) return;

    for (let p of model.shoupai.get_dapai()) {
        let pai = $(p.slice(-1) == '_'
                        ? `.zimo .pai[data-pai="${p.slice(0,2)}"]`
                        : `> .pai[data-pai="${p}"]`,
                    $('.shoupai .bingpai'));
        pai.attr('tabindex', 0).attr('role','button')
            .on('click.dapai', (ev)=>{
                $(ev.target).addClass('dapai');
                dapai(p);
            });
    }
    setSelector($('.shoupai .bingpai .pai[tabindex]'), 'dapai', {focus: focus});
}

function clear_handler() {
    view.shoupai.redraw();
    clearSelector('dapai');
}

function dapai(p) {

    clearSelector('dapai');

    if (pref.sound_on) view.audio('dapai').play();
    model.shoupai.dapai(p);
    view.shoupai.dapai(p);

    if (! model.lizhi && Majiang.Util.xiangting(model.shoupai) == 0) {
        model.lizhi = true;
        p += '*';
    }

    model.he.dapai(p);
    view.he.dapai(p);

    setTimeout(zimo, 600);
}

function zimo() {

    if (! model.shan.paishu) {
        view.shoupai.redraw();
        view.he.redraw();
        $('.status').text('流局……');
        $('.paili').empty();
        return;
    }

    model.shoupai.zimo(model.shan.zimo());
    view.shoupai.redraw();
    view.he.redraw();

    paili();
}

function paili(start) {

    $('.paili').empty();

    let n_xiangting = Majiang.Util.xiangting(model.shoupai);
    if      (n_xiangting == -1) $('.status').text('和了！！');
    else if (n_xiangting ==  0) $('.status').text('聴牌！');
    else                        $('.status').text(`${n_xiangting}向聴`);

    if (n_xiangting == -1) {
        if (pref.sound_on) view.audio('zimo').play();
        return;
    }
    else if (n_xiangting == 0 && ! model.lizhi) {
        if (pref.sound_on) view.audio('lizhi').play();
    }

    let dapai = [];
    for (let p of model.shoupai.get_dapai()) {

        let shoupai = model.shoupai.clone().dapai(p);
        if (Majiang.Util.xiangting(shoupai) > n_xiangting) continue;

        p = p[0] + (+p[1]||5);
        if (dapai.find(dapai => dapai.p == p)) continue;

        let tingpai = Majiang.Util.tingpai(shoupai);
        let n = tingpai.map(p => 4 - model.shoupai._bingpai[p[0]][p[1]])
                       .reduce((x, y)=> x + y, 0)

        dapai.push({ p: p, tingpai: tingpai, n: n });
    }

    const cmp = (a, b) => b.n - a.n
                       || b.tingpai.length - a.tingpai.length
                       || (a.p < b.p ? -1 : 1);
    for (let d of dapai.sort(cmp)) {
        let html = '<div>打: '
                 + $('<span>').append(view.pai(d.p)).html()
                 + ' 摸: '
                 + d.tingpai.map(
                     p => $('<span>').append(view.pai(p)).html()
                 ).join('')
                 + ` (${d.n}枚)</div>`;
        $('.paili').append($(html));
    }

    if (start) setTimeout(set_handler, 600);
    else       set_handler();
}

$(function(){

    view.pai   = Majiang.UI.pai('#loaddata');
    view.audio = Majiang.UI.audio('#loaddata');

    pref = localStorage.getItem('Majiang.pref')
                ? JSON.parse(localStorage.getItem('Majiang.pref'))
                : { sound_on: true };

    $('form input[type="button"]').on('click', function(){
        qipai();
        return false;
    });
    $('form').on('submit', function(){
        qipai($('form input[name="paistr"]').val());
        return false;
    });
    $('form').on('reset', function(){
        $('input[name="paistr"]').trigger('focus');
        history.replaceState('', '', location.href.replace(/#.*$/,''));
    });
    $('form [name="paistr"]').on('focus', clear_handler)
                             .on('blur',  ()=> set_handler(null));

    let paistr = location.hash.replace(/^#/,'');
    qipai(paistr);
});

/******/ })()
;
//# sourceMappingURL=data:application/json;charset=utf-8;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoicGFpbGktMi41LjMuanMiLCJtYXBwaW5ncyI6Ijs7Ozs7QUFBQTtBQUNBO0FBQ0E7QUFDQTtBQUNBO0FBQ0E7QUFDQTtBQUNhOztBQUViLFFBQVEsNkJBQTZCOztBQUVyQztBQUNBOztBQUVBOztBQUVBOztBQUVBO0FBQ0E7QUFDQTtBQUNBO0FBQ0E7QUFDQTtBQUNBO0FBQ0E7QUFDQTtBQUNBOztBQUVBOztBQUVBOztBQUVBO0FBQ0E7QUFDQTtBQUNBO0FBQ0E7QUFDQTtBQUNBO0FBQ0E7QUFDQTtBQUNBO0FBQ0E7O0FBRUE7O0FBRUE7QUFDQSxpREFBaUQseUJBQXlCOztBQUUxRTtBQUNBO0FBQ0E7O0FBRUE7QUFDQTs7QUFFQTtBQUNBOztBQUVBOztBQUVBOztBQUVBO0FBQ0E7QUFDQSxrREFBa0QsYUFBYTtBQUMvRCw4Q0FBOEMsRUFBRTtBQUNoRDtBQUNBO0FBQ0E7QUFDQTtBQUNBO0FBQ0EsYUFBYTtBQUNiO0FBQ0EsaUVBQWlFLGFBQWE7QUFDOUU7O0FBRUE7QUFDQTtBQUNBO0FBQ0E7O0FBRUE7O0FBRUE7O0FBRUE7QUFDQTtBQUNBOztBQUVBO0FBQ0E7QUFDQTtBQUNBOztBQUVBO0FBQ0E7O0FBRUE7QUFDQTs7QUFFQTs7QUFFQTtBQUNBO0FBQ0E7QUFDQTtBQUNBO0FBQ0E7QUFDQTs7QUFFQTtBQUNBO0FBQ0E7O0FBRUE7QUFDQTs7QUFFQTs7QUFFQTs7QUFFQTtBQUNBO0FBQ0E7QUFDQSxxREFBcUQsWUFBWTs7QUFFakU7QUFDQTtBQUNBO0FBQ0E7QUFDQTtBQUNBO0FBQ0E7O0FBRUE7QUFDQTs7QUFFQTtBQUNBOztBQUVBO0FBQ0E7O0FBRUE7QUFDQTtBQUNBOztBQUVBLHFCQUFxQiw4QkFBOEI7QUFDbkQ7O0FBRUE7QUFDQTtBQUNBO0FBQ0E7QUFDQTtBQUNBO0FBQ0E7QUFDQTtBQUNBO0FBQ0E7QUFDQSx3QkFBd0IsSUFBSTtBQUM1QjtBQUNBOztBQUVBO0FBQ0E7QUFDQTs7QUFFQTs7QUFFQTtBQUNBOztBQUVBO0FBQ0E7QUFDQSxvQkFBb0I7O0FBRXBCO0FBQ0E7QUFDQTtBQUNBLEtBQUs7QUFDTDtBQUNBO0FBQ0E7QUFDQSxLQUFLO0FBQ0w7QUFDQTtBQUNBO0FBQ0EsS0FBSztBQUNMO0FBQ0E7O0FBRUE7QUFDQTtBQUNBLENBQUMiLCJzb3VyY2VzIjpbIndlYnBhY2s6Ly9tYWppYW5nLy4vc3JjL2pzL3BhaWxpLmpzIl0sInNvdXJjZXNDb250ZW50IjpbIi8qIVxuICogIOmbu+iEs+m6u+Wwhjog54mM55CGIHYyLjUuM1xuICpcbiAqICBDb3B5cmlnaHQoQykgMjAxNyBTYXRvc2hpIEtvYmF5YXNoaVxuICogIFJlbGVhc2VkIHVuZGVyIHRoZSBNSVQgbGljZW5zZVxuICogIGh0dHBzOi8vZ2l0aHViLmNvbS9rb2JhbGFiL01hamlhbmcvYmxvYi9tYXN0ZXIvTElDRU5TRVxuICovXG5cInVzZSBzdHJpY3RcIjtcblxuY29uc3QgeyBzZXRTZWxlY3RvciwgY2xlYXJTZWxlY3RvciB9ID0gTWFqaWFuZy5VSS5VdGlsO1xuXG5jb25zdCBtb2RlbCA9IHt9O1xuY29uc3QgdmlldyAgPSB7fTtcblxuY29uc3QgcnVsZSA9IE1hamlhbmcucnVsZSgpO1xuXG5sZXQgcHJlZjtcblxuZnVuY3Rpb24gcmVwYWlyX3NoYW4oc2hhbiwgc2hvdXBhaSkge1xuICAgIGxldCBwYWlzdHIgPSBzaG91cGFpLnRvU3RyaW5nKCk7XG4gICAgZm9yIChsZXQgc3VpdHN0ciBvZiBwYWlzdHIubWF0Y2goL1ttcHN6XVtcXGRcXCtcXD1cXC1dKy9nKSkge1xuICAgICAgICBsZXQgcyA9IHN1aXRzdHJbMF07XG4gICAgICAgIGZvciAobGV0IG4gb2Ygc3VpdHN0ci5tYXRjaCgvXFxkL2cpKSB7XG4gICAgICAgICAgICBsZXQgaSA9IHNoYW4uX3BhaS5pbmRleE9mKHMrbik7XG4gICAgICAgICAgICBpZiAoaSA+PSAwKSBzaGFuLl9wYWkuc3BsaWNlKGksIDEpO1xuICAgICAgICB9XG4gICAgfVxufVxuXG5mdW5jdGlvbiBxaXBhaShwYWlzdHIpIHtcblxuICAgIG1vZGVsLnNoYW4gPSBuZXcgTWFqaWFuZy5TaGFuKHJ1bGUpO1xuXG4gICAgaWYgKHBhaXN0cikge1xuICAgICAgICBtb2RlbC5zaG91cGFpID0gTWFqaWFuZy5TaG91cGFpLmZyb21TdHJpbmcocGFpc3RyKTtcbiAgICAgICAgcmVwYWlyX3NoYW4obW9kZWwuc2hhbiwgbW9kZWwuc2hvdXBhaSk7XG4gICAgfVxuICAgIGVsc2Uge1xuICAgICAgICBsZXQgcWlwYWkgPSBbXTtcbiAgICAgICAgd2hpbGUgKHFpcGFpLmxlbmd0aCA8IDEzKSBxaXBhaS5wdXNoKG1vZGVsLnNoYW4uemltbygpKTtcbiAgICAgICAgbW9kZWwuc2hvdXBhaSA9IG5ldyBNYWppYW5nLlNob3VwYWkocWlwYWkpO1xuICAgICAgICBtb2RlbC5zaG91cGFpLnppbW8obW9kZWwuc2hhbi56aW1vKCkpO1xuICAgIH1cbiAgICBtb2RlbC5saXpoaSA9IGZhbHNlO1xuXG4gICAgd2hpbGUgKG1vZGVsLnNoYW4ucGFpc2h1ID4gMTcpIG1vZGVsLnNoYW4uemltbygpO1xuXG4gICAgJCgnZm9ybSBpbnB1dFtuYW1lPVwicGFpc3RyXCJdJykudmFsKG1vZGVsLnNob3VwYWkudG9TdHJpbmcoKSk7XG4gICAgaWYgKHBhaXN0cikgaGlzdG9yeS5yZXBsYWNlU3RhdGUoJycsICcnLCBgIyR7bW9kZWwuc2hvdXBhaS50b1N0cmluZygpfWApO1xuXG4gICAgdmlldy5zaG91cGFpID0gbmV3IE1hamlhbmcuVUkuU2hvdXBhaShcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgJCgnLnNob3VwYWknKSwgdmlldy5wYWksIG1vZGVsLnNob3VwYWlcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICApLnJlZHJhdyh0cnVlKTtcblxuICAgIG1vZGVsLmhlID0gbmV3IE1hamlhbmcuSGUoKTtcbiAgICB2aWV3LmhlICA9IG5ldyBNYWppYW5nLlVJLkhlKCQoJy5oZScpLCB2aWV3LnBhaSwgbW9kZWwuaGUpLnJlZHJhdyh0cnVlKTtcblxuICAgIHBhaWxpKDEpO1xufVxuXG5mdW5jdGlvbiBzZXRfaGFuZGxlcihmb2N1cyA9IC0xKSB7XG5cbiAgICBpZiAoTWFqaWFuZy5VdGlsLnhpYW5ndGluZyhtb2RlbC5zaG91cGFpKSA9PSAtMSkgcmV0dXJuO1xuXG4gICAgZm9yIChsZXQgcCBvZiBtb2RlbC5zaG91cGFpLmdldF9kYXBhaSgpKSB7XG4gICAgICAgIGxldCBwYWkgPSAkKHAuc2xpY2UoLTEpID09ICdfJ1xuICAgICAgICAgICAgICAgICAgICAgICAgPyBgLnppbW8gLnBhaVtkYXRhLXBhaT1cIiR7cC5zbGljZSgwLDIpfVwiXWBcbiAgICAgICAgICAgICAgICAgICAgICAgIDogYD4gLnBhaVtkYXRhLXBhaT1cIiR7cH1cIl1gLFxuICAgICAgICAgICAgICAgICAgICAkKCcuc2hvdXBhaSAuYmluZ3BhaScpKTtcbiAgICAgICAgcGFpLmF0dHIoJ3RhYmluZGV4JywgMCkuYXR0cigncm9sZScsJ2J1dHRvbicpXG4gICAgICAgICAgICAub24oJ2NsaWNrLmRhcGFpJywgKGV2KT0+e1xuICAgICAgICAgICAgICAgICQoZXYudGFyZ2V0KS5hZGRDbGFzcygnZGFwYWknKTtcbiAgICAgICAgICAgICAgICBkYXBhaShwKTtcbiAgICAgICAgICAgIH0pO1xuICAgIH1cbiAgICBzZXRTZWxlY3RvcigkKCcuc2hvdXBhaSAuYmluZ3BhaSAucGFpW3RhYmluZGV4XScpLCAnZGFwYWknLCB7Zm9jdXM6IGZvY3VzfSk7XG59XG5cbmZ1bmN0aW9uIGNsZWFyX2hhbmRsZXIoKSB7XG4gICAgdmlldy5zaG91cGFpLnJlZHJhdygpO1xuICAgIGNsZWFyU2VsZWN0b3IoJ2RhcGFpJyk7XG59XG5cbmZ1bmN0aW9uIGRhcGFpKHApIHtcblxuICAgIGNsZWFyU2VsZWN0b3IoJ2RhcGFpJyk7XG5cbiAgICBpZiAocHJlZi5zb3VuZF9vbikgdmlldy5hdWRpbygnZGFwYWknKS5wbGF5KCk7XG4gICAgbW9kZWwuc2hvdXBhaS5kYXBhaShwKTtcbiAgICB2aWV3LnNob3VwYWkuZGFwYWkocCk7XG5cbiAgICBpZiAoISBtb2RlbC5saXpoaSAmJiBNYWppYW5nLlV0aWwueGlhbmd0aW5nKG1vZGVsLnNob3VwYWkpID09IDApIHtcbiAgICAgICAgbW9kZWwubGl6aGkgPSB0cnVlO1xuICAgICAgICBwICs9ICcqJztcbiAgICB9XG5cbiAgICBtb2RlbC5oZS5kYXBhaShwKTtcbiAgICB2aWV3LmhlLmRhcGFpKHApO1xuXG4gICAgc2V0VGltZW91dCh6aW1vLCA2MDApO1xufVxuXG5mdW5jdGlvbiB6aW1vKCkge1xuXG4gICAgaWYgKCEgbW9kZWwuc2hhbi5wYWlzaHUpIHtcbiAgICAgICAgdmlldy5zaG91cGFpLnJlZHJhdygpO1xuICAgICAgICB2aWV3LmhlLnJlZHJhdygpO1xuICAgICAgICAkKCcuc3RhdHVzJykudGV4dCgn5rWB5bGA4oCm4oCmJyk7XG4gICAgICAgICQoJy5wYWlsaScpLmVtcHR5KCk7XG4gICAgICAgIHJldHVybjtcbiAgICB9XG5cbiAgICBtb2RlbC5zaG91cGFpLnppbW8obW9kZWwuc2hhbi56aW1vKCkpO1xuICAgIHZpZXcuc2hvdXBhaS5yZWRyYXcoKTtcbiAgICB2aWV3LmhlLnJlZHJhdygpO1xuXG4gICAgcGFpbGkoKTtcbn1cblxuZnVuY3Rpb24gcGFpbGkoc3RhcnQpIHtcblxuICAgICQoJy5wYWlsaScpLmVtcHR5KCk7XG5cbiAgICBsZXQgbl94aWFuZ3RpbmcgPSBNYWppYW5nLlV0aWwueGlhbmd0aW5nKG1vZGVsLnNob3VwYWkpO1xuICAgIGlmICAgICAgKG5feGlhbmd0aW5nID09IC0xKSAkKCcuc3RhdHVzJykudGV4dCgn5ZKM5LqG77yB77yBJyk7XG4gICAgZWxzZSBpZiAobl94aWFuZ3RpbmcgPT0gIDApICQoJy5zdGF0dXMnKS50ZXh0KCfogbTniYzvvIEnKTtcbiAgICBlbHNlICAgICAgICAgICAgICAgICAgICAgICAgJCgnLnN0YXR1cycpLnRleHQoYCR7bl94aWFuZ3Rpbmd95ZCR6IG0YCk7XG5cbiAgICBpZiAobl94aWFuZ3RpbmcgPT0gLTEpIHtcbiAgICAgICAgaWYgKHByZWYuc291bmRfb24pIHZpZXcuYXVkaW8oJ3ppbW8nKS5wbGF5KCk7XG4gICAgICAgIHJldHVybjtcbiAgICB9XG4gICAgZWxzZSBpZiAobl94aWFuZ3RpbmcgPT0gMCAmJiAhIG1vZGVsLmxpemhpKSB7XG4gICAgICAgIGlmIChwcmVmLnNvdW5kX29uKSB2aWV3LmF1ZGlvKCdsaXpoaScpLnBsYXkoKTtcbiAgICB9XG5cbiAgICBsZXQgZGFwYWkgPSBbXTtcbiAgICBmb3IgKGxldCBwIG9mIG1vZGVsLnNob3VwYWkuZ2V0X2RhcGFpKCkpIHtcblxuICAgICAgICBsZXQgc2hvdXBhaSA9IG1vZGVsLnNob3VwYWkuY2xvbmUoKS5kYXBhaShwKTtcbiAgICAgICAgaWYgKE1hamlhbmcuVXRpbC54aWFuZ3Rpbmcoc2hvdXBhaSkgPiBuX3hpYW5ndGluZykgY29udGludWU7XG5cbiAgICAgICAgcCA9IHBbMF0gKyAoK3BbMV18fDUpO1xuICAgICAgICBpZiAoZGFwYWkuZmluZChkYXBhaSA9PiBkYXBhaS5wID09IHApKSBjb250aW51ZTtcblxuICAgICAgICBsZXQgdGluZ3BhaSA9IE1hamlhbmcuVXRpbC50aW5ncGFpKHNob3VwYWkpO1xuICAgICAgICBsZXQgbiA9IHRpbmdwYWkubWFwKHAgPT4gNCAtIG1vZGVsLnNob3VwYWkuX2JpbmdwYWlbcFswXV1bcFsxXV0pXG4gICAgICAgICAgICAgICAgICAgICAgIC5yZWR1Y2UoKHgsIHkpPT4geCArIHksIDApXG5cbiAgICAgICAgZGFwYWkucHVzaCh7IHA6IHAsIHRpbmdwYWk6IHRpbmdwYWksIG46IG4gfSk7XG4gICAgfVxuXG4gICAgY29uc3QgY21wID0gKGEsIGIpID0+IGIubiAtIGEublxuICAgICAgICAgICAgICAgICAgICAgICB8fCBiLnRpbmdwYWkubGVuZ3RoIC0gYS50aW5ncGFpLmxlbmd0aFxuICAgICAgICAgICAgICAgICAgICAgICB8fCAoYS5wIDwgYi5wID8gLTEgOiAxKTtcbiAgICBmb3IgKGxldCBkIG9mIGRhcGFpLnNvcnQoY21wKSkge1xuICAgICAgICBsZXQgaHRtbCA9ICc8ZGl2PuaJkzogJ1xuICAgICAgICAgICAgICAgICArICQoJzxzcGFuPicpLmFwcGVuZCh2aWV3LnBhaShkLnApKS5odG1sKClcbiAgICAgICAgICAgICAgICAgKyAnIOaRuDogJ1xuICAgICAgICAgICAgICAgICArIGQudGluZ3BhaS5tYXAoXG4gICAgICAgICAgICAgICAgICAgICBwID0+ICQoJzxzcGFuPicpLmFwcGVuZCh2aWV3LnBhaShwKSkuaHRtbCgpXG4gICAgICAgICAgICAgICAgICkuam9pbignJylcbiAgICAgICAgICAgICAgICAgKyBgICgke2Qubn3mnpopPC9kaXY+YDtcbiAgICAgICAgJCgnLnBhaWxpJykuYXBwZW5kKCQoaHRtbCkpO1xuICAgIH1cblxuICAgIGlmIChzdGFydCkgc2V0VGltZW91dChzZXRfaGFuZGxlciwgNjAwKTtcbiAgICBlbHNlICAgICAgIHNldF9oYW5kbGVyKCk7XG59XG5cbiQoZnVuY3Rpb24oKXtcblxuICAgIHZpZXcucGFpICAgPSBNYWppYW5nLlVJLnBhaSgnI2xvYWRkYXRhJyk7XG4gICAgdmlldy5hdWRpbyA9IE1hamlhbmcuVUkuYXVkaW8oJyNsb2FkZGF0YScpO1xuXG4gICAgcHJlZiA9IGxvY2FsU3RvcmFnZS5nZXRJdGVtKCdNYWppYW5nLnByZWYnKVxuICAgICAgICAgICAgICAgID8gSlNPTi5wYXJzZShsb2NhbFN0b3JhZ2UuZ2V0SXRlbSgnTWFqaWFuZy5wcmVmJykpXG4gICAgICAgICAgICAgICAgOiB7IHNvdW5kX29uOiB0cnVlIH07XG5cbiAgICAkKCdmb3JtIGlucHV0W3R5cGU9XCJidXR0b25cIl0nKS5vbignY2xpY2snLCBmdW5jdGlvbigpe1xuICAgICAgICBxaXBhaSgpO1xuICAgICAgICByZXR1cm4gZmFsc2U7XG4gICAgfSk7XG4gICAgJCgnZm9ybScpLm9uKCdzdWJtaXQnLCBmdW5jdGlvbigpe1xuICAgICAgICBxaXBhaSgkKCdmb3JtIGlucHV0W25hbWU9XCJwYWlzdHJcIl0nKS52YWwoKSk7XG4gICAgICAgIHJldHVybiBmYWxzZTtcbiAgICB9KTtcbiAgICAkKCdmb3JtJykub24oJ3Jlc2V0JywgZnVuY3Rpb24oKXtcbiAgICAgICAgJCgnaW5wdXRbbmFtZT1cInBhaXN0clwiXScpLnRyaWdnZXIoJ2ZvY3VzJyk7XG4gICAgICAgIGhpc3RvcnkucmVwbGFjZVN0YXRlKCcnLCAnJywgbG9jYXRpb24uaHJlZi5yZXBsYWNlKC8jLiokLywnJykpO1xuICAgIH0pO1xuICAgICQoJ2Zvcm0gW25hbWU9XCJwYWlzdHJcIl0nKS5vbignZm9jdXMnLCBjbGVhcl9oYW5kbGVyKVxuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAub24oJ2JsdXInLCAgKCk9PiBzZXRfaGFuZGxlcihudWxsKSk7XG5cbiAgICBsZXQgcGFpc3RyID0gbG9jYXRpb24uaGFzaC5yZXBsYWNlKC9eIy8sJycpO1xuICAgIHFpcGFpKHBhaXN0cik7XG59KTtcbiJdLCJuYW1lcyI6W10sInNvdXJjZVJvb3QiOiIifQ==
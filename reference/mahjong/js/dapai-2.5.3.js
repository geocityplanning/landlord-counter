/******/ (() => { // webpackBootstrap
/******/ 	"use strict";
/*!*************************!*\
  !*** ./src/js/dapai.js ***!
  \*************************/
/*!
 *  電脳麻将: 何切る解答機 v2.5.3
 *
 *  Copyright(C) 2017 Satoshi Kobayashi
 *  Released under the MIT license
 *  https://github.com/kobalab/Majiang/blob/master/LICENSE
 */


const { hide, show, fadeIn, fadeOut, scale } = Majiang.UI.Util;
const minipaipu = Majiang.AI.minipaipu;

let pai, audio;

function init(fragment) {

    if (fragment) {

        let [ baseinfo, heinfo ] = fragment.split(/&/);

        let xun, param = baseinfo.split(/\//);
        if (param.length && param[param.length-1][0] == '+') xun = param.pop();
        let [ paistr, zhuangfeng, menfeng, baopai, hongpai ] = param;
        baopai  = (baopai   || '').split(/,/);
        hongpai = ! hongpai;

        $('input[name="paistr"]').val(paistr);
        $('select[name="zhuangfeng"]').val(+zhuangfeng||0);
        $('select[name="menfeng"]').val(+menfeng||0);
        $('select[name="xun"]').val(+xun||7);
        for (let i = 0; i < baopai.length; i++) {
            $('input[name="baopai"]').eq(i).val(baopai[i]);
        }
        $('input[name="hongpai"]').prop('checked', hongpai);

        if (heinfo != null) {
            $('form input[name="heinfo"]').prop('checked', true)
                                          .trigger('change');
            let hestr = heinfo.split(/\//);
            for (let l = 0; l < 4; l++) {
                $('input[name="hestr"]').eq(l).val(hestr[l]);
            }
        }

        submit();
    }
    else {
        $('input[name="paistr"]').val('m123p1234789s338s8').focus();
        $('input[name="baopai"]').eq(0).val('s3');
    }
}

function submit(ev) {

    hide($('.shan, .shoupai, .analyzer', $('#demo')));

    let paistr = $('input[name="paistr"]').val();
    if (! paistr) return false;

    let zhuangfeng = + $('select[name="zhuangfeng"]').val();
    let menfeng    = + $('select[name="menfeng"]').val();
    let xun        = + $('select[name="xun"]').val();
    let baopai     = $('input[name="baopai"]').map((i,n)=>$(n).val()).toArray()
                                    .filter(p => Majiang.Shoupai.valid_pai(p));
    let hongpai    = $('input[name="hongpai"]').prop('checked');

    if (! baopai.length) baopai = ['z2'];

    let heinfo = $('input[name="hestr"]').map((i,n)=>$(n).val()).toArray();

    if (! hongpai) {
        paistr = paistr.replace(/0/,'5');
        baopai = baopai.map(p => p.replace(/0/,'5'));
        heinfo = heinfo.map(hestr => hestr.replace(/0/,'5'));
    }

    let baseinfo = { paistr: paistr, zhuangfeng: zhuangfeng, menfeng: menfeng,
                     baopai: baopai, hongpai: hongpai, xun: xun };

    let analyzer;
    let kaiju = { id: 0, rule: Majiang.rule(), qijia: 0 };

    if ($('form input[name="heinfo"]').prop('checked')) {

        analyzer = new Majiang.UI.Analyzer($('#board >.analyzer'), kaiju, pai);

        heinfo = minipaipu(analyzer, baseinfo, heinfo, true);

        let view = new Majiang.UI.Board($('#board .board'),
                                        pai, audio, analyzer.model);
        view.no_player_name = true;
        view.open_he        = true;
        view.redraw();

        let zimo = analyzer.shoupai._zimo
        if (zimo) {
            if (zimo.length == 2)
                    analyzer.action_zimo({ l: menfeng, p: zimo });
            else    analyzer.action_fulou({ l: menfeng, m: zimo });
        }
        else {
            let l = analyzer.model.lunban;
            if (l != -1) {
                let p = analyzer.model.he[l]._pai.slice(-1)[0];
                analyzer.action_dapai({ l: l, p: p });
            }
            else {
                analyzer.action_qipai();
            }
        }
        $('body').attr('class','board analyzer');
        scale($('#board'), $('#space'));
    }
    else {
        analyzer = new Majiang.UI.Analyzer($('#demo >.analyzer'), kaiju, pai);

        minipaipu(analyzer, baseinfo);

        new Majiang.UI.Shan($('#demo .shan'), pai, analyzer.shan).redraw();
        new Majiang.UI.Shoupai($('#demo .shoupai'), pai, analyzer.shoupai)
                                                                .redraw(true);

        let zimo = analyzer.shoupai._zimo
        if (zimo) {
            if (zimo.length == 2)
                    analyzer.action_zimo({ l: menfeng, p: zimo });
            else    analyzer.action_fulou({ l: menfeng, m: zimo });
        }
        fadeIn($('.shan, .shoupai, .analyzer', $('#demo')));

        heinfo = null;
    }

    paistr = analyzer.shoupai.toString();
    $('input[name="paistr"]').val(paistr);

    baopai = analyzer.shan.baopai;
    for (let i = 0; i < 5; i++) {
        $('input[name="baopai"]').eq(i).val(baopai[i] || '');
    }

    if (heinfo) {
        for (let i = 0; i < 4; i++)  {
            $('input[name="hestr"]').eq(i).val(heinfo[i]);
        }
    }

    let fragment = '#'
                 + [ paistr, zhuangfeng, menfeng, baopai.join(',')].join('/');
    if (! hongpai) fragment += '/1';

    if (heinfo) fragment += '&' + heinfo.join('/');
    else        fragment += '/+' + xun;

    history.replaceState('', '', fragment)

    return false;
}

function set_controller(root) {
    root.addClass('paipu');
    $(window).on('keyup', (ev)=>{
        if (ev.key == 'q' || ev.key == 'Escape') {
            if ($('body').attr('class') != 'demo')
                                    $('body').attr('class','demo');
        }
    });
    hide($('> img', root));
    show($('> img.exit', root).on('click', ()=>$('body').attr('class','demo')));
}

$(function(){

    pai = Majiang.UI.pai('#loaddata');
    audio = Majiang.UI.audio('#loaddata');

    $('form input[name="heinfo"]').on('change', function(){
        if ($(this).prop('checked')) {
            show($('form .heinfo'));
            hide($('form .xun'));
        }
        else {
            hide($('form .heinfo'));
            show($('form .xun'));
        }
    });
    hide($('form .heinfo'));

    $('form').on('submit', submit);

    $('form').on('reset', function(){
        hide($('.shan, .shoupai, .analyzer', $('#demo')));
        hide($('form .heinfo'));
        $('form input[name="paistr"]').focus();
    });

    $(window).on('resize', ()=>scale($('#board'), $('#space')));

    set_controller($('#board .controller'));

    let fragment = location.hash.replace(/^#/,'');
    init(fragment);
});

/******/ })()
;
//# sourceMappingURL=data:application/json;charset=utf-8;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiZGFwYWktMi41LjMuanMiLCJtYXBwaW5ncyI6Ijs7Ozs7QUFBQTtBQUNBO0FBQ0E7QUFDQTtBQUNBO0FBQ0E7QUFDQTtBQUNhOztBQUViLFFBQVEscUNBQXFDO0FBQzdDOztBQUVBOztBQUVBOztBQUVBOztBQUVBOztBQUVBO0FBQ0E7QUFDQTtBQUNBO0FBQ0E7O0FBRUE7QUFDQTtBQUNBO0FBQ0E7QUFDQSx3QkFBd0IsbUJBQW1CO0FBQzNDO0FBQ0E7QUFDQTs7QUFFQTtBQUNBO0FBQ0E7QUFDQTtBQUNBLDRCQUE0QixPQUFPO0FBQ25DO0FBQ0E7QUFDQTs7QUFFQTtBQUNBO0FBQ0E7QUFDQTtBQUNBO0FBQ0E7QUFDQTs7QUFFQTs7QUFFQTs7QUFFQTtBQUNBOztBQUVBO0FBQ0E7QUFDQTtBQUNBO0FBQ0E7QUFDQTs7QUFFQTs7QUFFQTs7QUFFQTtBQUNBO0FBQ0E7QUFDQTtBQUNBOztBQUVBLHFCQUFxQjtBQUNyQjs7QUFFQTtBQUNBLGtCQUFrQjs7QUFFbEI7O0FBRUE7O0FBRUE7O0FBRUE7QUFDQTtBQUNBO0FBQ0E7QUFDQTs7QUFFQTtBQUNBO0FBQ0E7QUFDQSwyQ0FBMkMscUJBQXFCO0FBQ2hFLDRDQUE0QyxxQkFBcUI7QUFDakU7QUFDQTtBQUNBO0FBQ0E7QUFDQTtBQUNBLHdDQUF3QyxZQUFZO0FBQ3BEO0FBQ0E7QUFDQTtBQUNBO0FBQ0E7QUFDQTtBQUNBO0FBQ0E7QUFDQTtBQUNBOztBQUVBOztBQUVBO0FBQ0E7QUFDQTs7QUFFQTtBQUNBO0FBQ0E7QUFDQSwyQ0FBMkMscUJBQXFCO0FBQ2hFLDRDQUE0QyxxQkFBcUI7QUFDakU7QUFDQTs7QUFFQTtBQUNBOztBQUVBO0FBQ0E7O0FBRUE7QUFDQSxvQkFBb0IsT0FBTztBQUMzQjtBQUNBOztBQUVBO0FBQ0Esd0JBQXdCLE9BQU87QUFDL0I7QUFDQTtBQUNBOztBQUVBO0FBQ0E7QUFDQTs7QUFFQTtBQUNBOztBQUVBOztBQUVBO0FBQ0E7O0FBRUE7QUFDQTtBQUNBO0FBQ0E7QUFDQTtBQUNBO0FBQ0E7QUFDQSxLQUFLO0FBQ0w7QUFDQTtBQUNBOztBQUVBOztBQUVBO0FBQ0E7O0FBRUE7QUFDQTtBQUNBO0FBQ0E7QUFDQTtBQUNBO0FBQ0E7QUFDQTtBQUNBO0FBQ0EsS0FBSztBQUNMOztBQUVBOztBQUVBO0FBQ0E7QUFDQTtBQUNBO0FBQ0EsS0FBSzs7QUFFTDs7QUFFQTs7QUFFQTtBQUNBO0FBQ0EsQ0FBQyIsInNvdXJjZXMiOlsid2VicGFjazovL21hamlhbmcvLi9zcmMvanMvZGFwYWkuanMiXSwic291cmNlc0NvbnRlbnQiOlsiLyohXG4gKiAg6Zu76ISz6bq75bCGOiDkvZXliIfjgovop6PnrZTmqZ8gdjIuNS4zXG4gKlxuICogIENvcHlyaWdodChDKSAyMDE3IFNhdG9zaGkgS29iYXlhc2hpXG4gKiAgUmVsZWFzZWQgdW5kZXIgdGhlIE1JVCBsaWNlbnNlXG4gKiAgaHR0cHM6Ly9naXRodWIuY29tL2tvYmFsYWIvTWFqaWFuZy9ibG9iL21hc3Rlci9MSUNFTlNFXG4gKi9cblwidXNlIHN0cmljdFwiO1xuXG5jb25zdCB7IGhpZGUsIHNob3csIGZhZGVJbiwgZmFkZU91dCwgc2NhbGUgfSA9IE1hamlhbmcuVUkuVXRpbDtcbmNvbnN0IG1pbmlwYWlwdSA9IE1hamlhbmcuQUkubWluaXBhaXB1O1xuXG5sZXQgcGFpLCBhdWRpbztcblxuZnVuY3Rpb24gaW5pdChmcmFnbWVudCkge1xuXG4gICAgaWYgKGZyYWdtZW50KSB7XG5cbiAgICAgICAgbGV0IFsgYmFzZWluZm8sIGhlaW5mbyBdID0gZnJhZ21lbnQuc3BsaXQoLyYvKTtcblxuICAgICAgICBsZXQgeHVuLCBwYXJhbSA9IGJhc2VpbmZvLnNwbGl0KC9cXC8vKTtcbiAgICAgICAgaWYgKHBhcmFtLmxlbmd0aCAmJiBwYXJhbVtwYXJhbS5sZW5ndGgtMV1bMF0gPT0gJysnKSB4dW4gPSBwYXJhbS5wb3AoKTtcbiAgICAgICAgbGV0IFsgcGFpc3RyLCB6aHVhbmdmZW5nLCBtZW5mZW5nLCBiYW9wYWksIGhvbmdwYWkgXSA9IHBhcmFtO1xuICAgICAgICBiYW9wYWkgID0gKGJhb3BhaSAgIHx8ICcnKS5zcGxpdCgvLC8pO1xuICAgICAgICBob25ncGFpID0gISBob25ncGFpO1xuXG4gICAgICAgICQoJ2lucHV0W25hbWU9XCJwYWlzdHJcIl0nKS52YWwocGFpc3RyKTtcbiAgICAgICAgJCgnc2VsZWN0W25hbWU9XCJ6aHVhbmdmZW5nXCJdJykudmFsKCt6aHVhbmdmZW5nfHwwKTtcbiAgICAgICAgJCgnc2VsZWN0W25hbWU9XCJtZW5mZW5nXCJdJykudmFsKCttZW5mZW5nfHwwKTtcbiAgICAgICAgJCgnc2VsZWN0W25hbWU9XCJ4dW5cIl0nKS52YWwoK3h1bnx8Nyk7XG4gICAgICAgIGZvciAobGV0IGkgPSAwOyBpIDwgYmFvcGFpLmxlbmd0aDsgaSsrKSB7XG4gICAgICAgICAgICAkKCdpbnB1dFtuYW1lPVwiYmFvcGFpXCJdJykuZXEoaSkudmFsKGJhb3BhaVtpXSk7XG4gICAgICAgIH1cbiAgICAgICAgJCgnaW5wdXRbbmFtZT1cImhvbmdwYWlcIl0nKS5wcm9wKCdjaGVja2VkJywgaG9uZ3BhaSk7XG5cbiAgICAgICAgaWYgKGhlaW5mbyAhPSBudWxsKSB7XG4gICAgICAgICAgICAkKCdmb3JtIGlucHV0W25hbWU9XCJoZWluZm9cIl0nKS5wcm9wKCdjaGVja2VkJywgdHJ1ZSlcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIC50cmlnZ2VyKCdjaGFuZ2UnKTtcbiAgICAgICAgICAgIGxldCBoZXN0ciA9IGhlaW5mby5zcGxpdCgvXFwvLyk7XG4gICAgICAgICAgICBmb3IgKGxldCBsID0gMDsgbCA8IDQ7IGwrKykge1xuICAgICAgICAgICAgICAgICQoJ2lucHV0W25hbWU9XCJoZXN0clwiXScpLmVxKGwpLnZhbChoZXN0cltsXSk7XG4gICAgICAgICAgICB9XG4gICAgICAgIH1cblxuICAgICAgICBzdWJtaXQoKTtcbiAgICB9XG4gICAgZWxzZSB7XG4gICAgICAgICQoJ2lucHV0W25hbWU9XCJwYWlzdHJcIl0nKS52YWwoJ20xMjNwMTIzNDc4OXMzMzhzOCcpLmZvY3VzKCk7XG4gICAgICAgICQoJ2lucHV0W25hbWU9XCJiYW9wYWlcIl0nKS5lcSgwKS52YWwoJ3MzJyk7XG4gICAgfVxufVxuXG5mdW5jdGlvbiBzdWJtaXQoZXYpIHtcblxuICAgIGhpZGUoJCgnLnNoYW4sIC5zaG91cGFpLCAuYW5hbHl6ZXInLCAkKCcjZGVtbycpKSk7XG5cbiAgICBsZXQgcGFpc3RyID0gJCgnaW5wdXRbbmFtZT1cInBhaXN0clwiXScpLnZhbCgpO1xuICAgIGlmICghIHBhaXN0cikgcmV0dXJuIGZhbHNlO1xuXG4gICAgbGV0IHpodWFuZ2ZlbmcgPSArICQoJ3NlbGVjdFtuYW1lPVwiemh1YW5nZmVuZ1wiXScpLnZhbCgpO1xuICAgIGxldCBtZW5mZW5nICAgID0gKyAkKCdzZWxlY3RbbmFtZT1cIm1lbmZlbmdcIl0nKS52YWwoKTtcbiAgICBsZXQgeHVuICAgICAgICA9ICsgJCgnc2VsZWN0W25hbWU9XCJ4dW5cIl0nKS52YWwoKTtcbiAgICBsZXQgYmFvcGFpICAgICA9ICQoJ2lucHV0W25hbWU9XCJiYW9wYWlcIl0nKS5tYXAoKGksbik9PiQobikudmFsKCkpLnRvQXJyYXkoKVxuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgLmZpbHRlcihwID0+IE1hamlhbmcuU2hvdXBhaS52YWxpZF9wYWkocCkpO1xuICAgIGxldCBob25ncGFpICAgID0gJCgnaW5wdXRbbmFtZT1cImhvbmdwYWlcIl0nKS5wcm9wKCdjaGVja2VkJyk7XG5cbiAgICBpZiAoISBiYW9wYWkubGVuZ3RoKSBiYW9wYWkgPSBbJ3oyJ107XG5cbiAgICBsZXQgaGVpbmZvID0gJCgnaW5wdXRbbmFtZT1cImhlc3RyXCJdJykubWFwKChpLG4pPT4kKG4pLnZhbCgpKS50b0FycmF5KCk7XG5cbiAgICBpZiAoISBob25ncGFpKSB7XG4gICAgICAgIHBhaXN0ciA9IHBhaXN0ci5yZXBsYWNlKC8wLywnNScpO1xuICAgICAgICBiYW9wYWkgPSBiYW9wYWkubWFwKHAgPT4gcC5yZXBsYWNlKC8wLywnNScpKTtcbiAgICAgICAgaGVpbmZvID0gaGVpbmZvLm1hcChoZXN0ciA9PiBoZXN0ci5yZXBsYWNlKC8wLywnNScpKTtcbiAgICB9XG5cbiAgICBsZXQgYmFzZWluZm8gPSB7IHBhaXN0cjogcGFpc3RyLCB6aHVhbmdmZW5nOiB6aHVhbmdmZW5nLCBtZW5mZW5nOiBtZW5mZW5nLFxuICAgICAgICAgICAgICAgICAgICAgYmFvcGFpOiBiYW9wYWksIGhvbmdwYWk6IGhvbmdwYWksIHh1bjogeHVuIH07XG5cbiAgICBsZXQgYW5hbHl6ZXI7XG4gICAgbGV0IGthaWp1ID0geyBpZDogMCwgcnVsZTogTWFqaWFuZy5ydWxlKCksIHFpamlhOiAwIH07XG5cbiAgICBpZiAoJCgnZm9ybSBpbnB1dFtuYW1lPVwiaGVpbmZvXCJdJykucHJvcCgnY2hlY2tlZCcpKSB7XG5cbiAgICAgICAgYW5hbHl6ZXIgPSBuZXcgTWFqaWFuZy5VSS5BbmFseXplcigkKCcjYm9hcmQgPi5hbmFseXplcicpLCBrYWlqdSwgcGFpKTtcblxuICAgICAgICBoZWluZm8gPSBtaW5pcGFpcHUoYW5hbHl6ZXIsIGJhc2VpbmZvLCBoZWluZm8sIHRydWUpO1xuXG4gICAgICAgIGxldCB2aWV3ID0gbmV3IE1hamlhbmcuVUkuQm9hcmQoJCgnI2JvYXJkIC5ib2FyZCcpLFxuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIHBhaSwgYXVkaW8sIGFuYWx5emVyLm1vZGVsKTtcbiAgICAgICAgdmlldy5ub19wbGF5ZXJfbmFtZSA9IHRydWU7XG4gICAgICAgIHZpZXcub3Blbl9oZSAgICAgICAgPSB0cnVlO1xuICAgICAgICB2aWV3LnJlZHJhdygpO1xuXG4gICAgICAgIGxldCB6aW1vID0gYW5hbHl6ZXIuc2hvdXBhaS5femltb1xuICAgICAgICBpZiAoemltbykge1xuICAgICAgICAgICAgaWYgKHppbW8ubGVuZ3RoID09IDIpXG4gICAgICAgICAgICAgICAgICAgIGFuYWx5emVyLmFjdGlvbl96aW1vKHsgbDogbWVuZmVuZywgcDogemltbyB9KTtcbiAgICAgICAgICAgIGVsc2UgICAgYW5hbHl6ZXIuYWN0aW9uX2Z1bG91KHsgbDogbWVuZmVuZywgbTogemltbyB9KTtcbiAgICAgICAgfVxuICAgICAgICBlbHNlIHtcbiAgICAgICAgICAgIGxldCBsID0gYW5hbHl6ZXIubW9kZWwubHVuYmFuO1xuICAgICAgICAgICAgaWYgKGwgIT0gLTEpIHtcbiAgICAgICAgICAgICAgICBsZXQgcCA9IGFuYWx5emVyLm1vZGVsLmhlW2xdLl9wYWkuc2xpY2UoLTEpWzBdO1xuICAgICAgICAgICAgICAgIGFuYWx5emVyLmFjdGlvbl9kYXBhaSh7IGw6IGwsIHA6IHAgfSk7XG4gICAgICAgICAgICB9XG4gICAgICAgICAgICBlbHNlIHtcbiAgICAgICAgICAgICAgICBhbmFseXplci5hY3Rpb25fcWlwYWkoKTtcbiAgICAgICAgICAgIH1cbiAgICAgICAgfVxuICAgICAgICAkKCdib2R5JykuYXR0cignY2xhc3MnLCdib2FyZCBhbmFseXplcicpO1xuICAgICAgICBzY2FsZSgkKCcjYm9hcmQnKSwgJCgnI3NwYWNlJykpO1xuICAgIH1cbiAgICBlbHNlIHtcbiAgICAgICAgYW5hbHl6ZXIgPSBuZXcgTWFqaWFuZy5VSS5BbmFseXplcigkKCcjZGVtbyA+LmFuYWx5emVyJyksIGthaWp1LCBwYWkpO1xuXG4gICAgICAgIG1pbmlwYWlwdShhbmFseXplciwgYmFzZWluZm8pO1xuXG4gICAgICAgIG5ldyBNYWppYW5nLlVJLlNoYW4oJCgnI2RlbW8gLnNoYW4nKSwgcGFpLCBhbmFseXplci5zaGFuKS5yZWRyYXcoKTtcbiAgICAgICAgbmV3IE1hamlhbmcuVUkuU2hvdXBhaSgkKCcjZGVtbyAuc2hvdXBhaScpLCBwYWksIGFuYWx5emVyLnNob3VwYWkpXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgLnJlZHJhdyh0cnVlKTtcblxuICAgICAgICBsZXQgemltbyA9IGFuYWx5emVyLnNob3VwYWkuX3ppbW9cbiAgICAgICAgaWYgKHppbW8pIHtcbiAgICAgICAgICAgIGlmICh6aW1vLmxlbmd0aCA9PSAyKVxuICAgICAgICAgICAgICAgICAgICBhbmFseXplci5hY3Rpb25femltbyh7IGw6IG1lbmZlbmcsIHA6IHppbW8gfSk7XG4gICAgICAgICAgICBlbHNlICAgIGFuYWx5emVyLmFjdGlvbl9mdWxvdSh7IGw6IG1lbmZlbmcsIG06IHppbW8gfSk7XG4gICAgICAgIH1cbiAgICAgICAgZmFkZUluKCQoJy5zaGFuLCAuc2hvdXBhaSwgLmFuYWx5emVyJywgJCgnI2RlbW8nKSkpO1xuXG4gICAgICAgIGhlaW5mbyA9IG51bGw7XG4gICAgfVxuXG4gICAgcGFpc3RyID0gYW5hbHl6ZXIuc2hvdXBhaS50b1N0cmluZygpO1xuICAgICQoJ2lucHV0W25hbWU9XCJwYWlzdHJcIl0nKS52YWwocGFpc3RyKTtcblxuICAgIGJhb3BhaSA9IGFuYWx5emVyLnNoYW4uYmFvcGFpO1xuICAgIGZvciAobGV0IGkgPSAwOyBpIDwgNTsgaSsrKSB7XG4gICAgICAgICQoJ2lucHV0W25hbWU9XCJiYW9wYWlcIl0nKS5lcShpKS52YWwoYmFvcGFpW2ldIHx8ICcnKTtcbiAgICB9XG5cbiAgICBpZiAoaGVpbmZvKSB7XG4gICAgICAgIGZvciAobGV0IGkgPSAwOyBpIDwgNDsgaSsrKSAge1xuICAgICAgICAgICAgJCgnaW5wdXRbbmFtZT1cImhlc3RyXCJdJykuZXEoaSkudmFsKGhlaW5mb1tpXSk7XG4gICAgICAgIH1cbiAgICB9XG5cbiAgICBsZXQgZnJhZ21lbnQgPSAnIydcbiAgICAgICAgICAgICAgICAgKyBbIHBhaXN0ciwgemh1YW5nZmVuZywgbWVuZmVuZywgYmFvcGFpLmpvaW4oJywnKV0uam9pbignLycpO1xuICAgIGlmICghIGhvbmdwYWkpIGZyYWdtZW50ICs9ICcvMSc7XG5cbiAgICBpZiAoaGVpbmZvKSBmcmFnbWVudCArPSAnJicgKyBoZWluZm8uam9pbignLycpO1xuICAgIGVsc2UgICAgICAgIGZyYWdtZW50ICs9ICcvKycgKyB4dW47XG5cbiAgICBoaXN0b3J5LnJlcGxhY2VTdGF0ZSgnJywgJycsIGZyYWdtZW50KVxuXG4gICAgcmV0dXJuIGZhbHNlO1xufVxuXG5mdW5jdGlvbiBzZXRfY29udHJvbGxlcihyb290KSB7XG4gICAgcm9vdC5hZGRDbGFzcygncGFpcHUnKTtcbiAgICAkKHdpbmRvdykub24oJ2tleXVwJywgKGV2KT0+e1xuICAgICAgICBpZiAoZXYua2V5ID09ICdxJyB8fCBldi5rZXkgPT0gJ0VzY2FwZScpIHtcbiAgICAgICAgICAgIGlmICgkKCdib2R5JykuYXR0cignY2xhc3MnKSAhPSAnZGVtbycpXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAkKCdib2R5JykuYXR0cignY2xhc3MnLCdkZW1vJyk7XG4gICAgICAgIH1cbiAgICB9KTtcbiAgICBoaWRlKCQoJz4gaW1nJywgcm9vdCkpO1xuICAgIHNob3coJCgnPiBpbWcuZXhpdCcsIHJvb3QpLm9uKCdjbGljaycsICgpPT4kKCdib2R5JykuYXR0cignY2xhc3MnLCdkZW1vJykpKTtcbn1cblxuJChmdW5jdGlvbigpe1xuXG4gICAgcGFpID0gTWFqaWFuZy5VSS5wYWkoJyNsb2FkZGF0YScpO1xuICAgIGF1ZGlvID0gTWFqaWFuZy5VSS5hdWRpbygnI2xvYWRkYXRhJyk7XG5cbiAgICAkKCdmb3JtIGlucHV0W25hbWU9XCJoZWluZm9cIl0nKS5vbignY2hhbmdlJywgZnVuY3Rpb24oKXtcbiAgICAgICAgaWYgKCQodGhpcykucHJvcCgnY2hlY2tlZCcpKSB7XG4gICAgICAgICAgICBzaG93KCQoJ2Zvcm0gLmhlaW5mbycpKTtcbiAgICAgICAgICAgIGhpZGUoJCgnZm9ybSAueHVuJykpO1xuICAgICAgICB9XG4gICAgICAgIGVsc2Uge1xuICAgICAgICAgICAgaGlkZSgkKCdmb3JtIC5oZWluZm8nKSk7XG4gICAgICAgICAgICBzaG93KCQoJ2Zvcm0gLnh1bicpKTtcbiAgICAgICAgfVxuICAgIH0pO1xuICAgIGhpZGUoJCgnZm9ybSAuaGVpbmZvJykpO1xuXG4gICAgJCgnZm9ybScpLm9uKCdzdWJtaXQnLCBzdWJtaXQpO1xuXG4gICAgJCgnZm9ybScpLm9uKCdyZXNldCcsIGZ1bmN0aW9uKCl7XG4gICAgICAgIGhpZGUoJCgnLnNoYW4sIC5zaG91cGFpLCAuYW5hbHl6ZXInLCAkKCcjZGVtbycpKSk7XG4gICAgICAgIGhpZGUoJCgnZm9ybSAuaGVpbmZvJykpO1xuICAgICAgICAkKCdmb3JtIGlucHV0W25hbWU9XCJwYWlzdHJcIl0nKS5mb2N1cygpO1xuICAgIH0pO1xuXG4gICAgJCh3aW5kb3cpLm9uKCdyZXNpemUnLCAoKT0+c2NhbGUoJCgnI2JvYXJkJyksICQoJyNzcGFjZScpKSk7XG5cbiAgICBzZXRfY29udHJvbGxlcigkKCcjYm9hcmQgLmNvbnRyb2xsZXInKSk7XG5cbiAgICBsZXQgZnJhZ21lbnQgPSBsb2NhdGlvbi5oYXNoLnJlcGxhY2UoL14jLywnJyk7XG4gICAgaW5pdChmcmFnbWVudCk7XG59KTtcbiJdLCJuYW1lcyI6W10sInNvdXJjZVJvb3QiOiIifQ==
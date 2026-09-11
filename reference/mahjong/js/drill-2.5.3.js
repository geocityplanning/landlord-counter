/******/ (() => { // webpackBootstrap
/******/ 	"use strict";
/******/ 	var __webpack_modules__ = ({

/***/ "./src/js/conf/rule.json"
/*!*******************************!*\
  !*** ./src/js/conf/rule.json ***!
  \*******************************/
(module) {

module.exports = /*#__PURE__*/JSON.parse('{"Mリーグルール":{"配給原点":25000,"順位点":["+30.0","+10.0","-10.0","-30.0"],"赤牌":{"m":1,"p":1,"s":1},"連風牌は2符":true,"クイタンあり":true,"喰い替え許可レベル":0,"場数":2,"途中流局あり":false,"流し満貫あり":false,"ノーテン宣言あり":true,"ノーテン罰あり":true,"最大同時和了数":1,"連荘方式":2,"トビ終了あり":false,"オーラス止めあり":false,"延長戦方式":0,"一発あり":true,"裏ドラあり":true,"カンドラあり":true,"カン裏あり":true,"カンドラ後乗せ":false,"ツモ番なしリーチあり":true,"リーチ後暗槓許可レベル":1,"ダブル役満あり":false,"役満の複合あり":true,"数え役満あり":false,"役満パオあり":true,"切り上げ満貫あり":true},"Classicルール":{"配給原点":30000,"順位点":["+12.0","+4.0","-4.0","-12.0"],"赤牌":{"m":0,"p":0,"s":0},"連風牌は2符":false,"クイタンあり":true,"喰い替え許可レベル":2,"場数":2,"途中流局あり":false,"流し満貫あり":false,"ノーテン宣言あり":false,"ノーテン罰あり":false,"最大同時和了数":1,"連荘方式":1,"トビ終了あり":false,"オーラス止めあり":false,"延長戦方式":0,"一発あり":false,"裏ドラあり":false,"カンドラあり":false,"カン裏あり":false,"カンドラ後乗せ":false,"ツモ番なしリーチあり":true,"リーチ後暗槓許可レベル":0,"ダブル役満あり":false,"役満の複合あり":false,"数え役満あり":false,"役満パオあり":false,"切り上げ満貫あり":false}}');

/***/ }

/******/ 	});
/************************************************************************/
/******/ 	// The module cache
/******/ 	var __webpack_module_cache__ = {};
/******/ 	
/******/ 	// The require function
/******/ 	function __webpack_require__(moduleId) {
/******/ 		// Check if module is in cache
/******/ 		var cachedModule = __webpack_module_cache__[moduleId];
/******/ 		if (cachedModule !== undefined) {
/******/ 			return cachedModule.exports;
/******/ 		}
/******/ 		// Create a new module (and put it into the cache)
/******/ 		var module = __webpack_module_cache__[moduleId] = {
/******/ 			// no module.id needed
/******/ 			// no module.loaded needed
/******/ 			exports: {}
/******/ 		};
/******/ 	
/******/ 		// Execute the module function
/******/ 		if (!(moduleId in __webpack_modules__)) {
/******/ 			delete __webpack_module_cache__[moduleId];
/******/ 			var e = new Error("Cannot find module '" + moduleId + "'");
/******/ 			e.code = 'MODULE_NOT_FOUND';
/******/ 			throw e;
/******/ 		}
/******/ 		__webpack_modules__[moduleId](module, module.exports, __webpack_require__);
/******/ 	
/******/ 		// Return the exports of the module
/******/ 		return module.exports;
/******/ 	}
/******/ 	
/************************************************************************/
// This entry needs to be wrapped in an IIFE because it needs to be isolated against other modules in the chunk.
(() => {
/*!*************************!*\
  !*** ./src/js/drill.js ***!
  \*************************/
/*!
 *  電脳麻将: 点数計算ドリル v2.5.3
 *
 *  Copyright(C) 2017 Satoshi Kobayashi
 *  Released under the MIT license
 *  https://github.com/kobalab/Majiang/blob/master/LICENSE
 */


const { hide, show, fadeIn, fadeOut } = Majiang.UI.Util;

const preset = __webpack_require__(/*! ./conf/rule.json */ "./src/js/conf/rule.json");
const view = {};

const feng_hanzi = ['東','南','西','北'];

let player, next_exam, miss_exams, stat;

class Player extends Majiang.AI {
    select_lizhi(p) {
        return this.allow_lizhi(this.shoupai, p) && Math.random() < 0.3;
    }
}

function init_player() {

    let player = new Player();

    let rule = $('select[name="rule"]').val();
    rule = ! rule      ? {}
         : rule == '-' ? JSON.parse(localStorage.getItem('Majiang.rule')||'{}')
         :               preset[rule];
    rule = Majiang.rule(rule);

    player.kaiju({ id: 0, qijia: 0, title: '', player: [], rule: rule });

    return player;
}

function make_exam(player) {
    for (;;) {
        let zhuangfeng = (Math.random()*2)|0;
        let menfeng    = (Math.random()*4)|0;
        let shoupai    = [ '', '', '', '' ];
        let shan = new Majiang.Shan(player._rule);
        let qipai = [];
        for (let i = 0; i < 13; i++) qipai.push(shan.zimo());
        shoupai[menfeng] = (new Majiang.Shoupai(qipai)).toString();
        player.qipai({
            zhuangfeng: zhuangfeng,
            jushu:      [0,3,2,1][menfeng],
            changbang:  0,
            lizhibang:  0,
            defen:      [ 25000, 25000, 25000, 25000 ],
            baopai:     shan.baopai[0],
            shoupai:    shoupai
        });
        player.shan.paishu = shan.paishu + 4;
        let gang = null, lunban = 0;
        while (shan.paishu) {
            let p;
            if (gang) {
                p = shan.gangzimo();
                if (shan._weikaigang) shan.kaigang();
                gang = null;
            }
            else {
                p = shan.zimo();
            }
            let msg = { l: lunban, p: p };
            if (lunban == menfeng) {
                player.zimo(msg);
                if (player.select_hule()) {
                    shan.close();
                    return {
                        shoupai:    player.shoupai,
                        zhuangfeng: zhuangfeng,
                        menfeng:    menfeng,
                        baopai:     shan.baopai,
                        fubaopai:   player.shoupai.lizhi && shan.fubaopai
                    };
                }
                let m = player.select_gang();
                if (m)  {
                    player.gang({ l: menfeng, m: m});
                    gang = m;
                    continue;
                }
                player.dapai({ l: menfeng, p: player.select_dapai()});
            }
            else {
                player.zimo(msg);
                player.dapai(msg);
                player._neng_rong = true;
                if (player.select_hule(msg)) {
                    shan.close();
                    let rongpai
                            = p + ['','+','=','-'][(4 + lunban - menfeng) % 4];
                    return {
                        shoupai:    player.shoupai,
                        rongpai:    rongpai,
                        zhuangfeng: zhuangfeng,
                        menfeng:    menfeng,
                        baopai:     shan.baopai,
                        fubaopai:   player.shoupai.lizhi && shan.fubaopai
                    };
                }
                let m = player.select_fulou(msg);
                if (m) {
                    player.fulou({ l: menfeng, m: m });
                    if (m.match(/^[mpsz]\d{4}/)) {
                        gang = m;
                        continue;
                    }
                    player.dapai({ l: menfeng, p: player.select_dapai()});
                }
            }
            lunban = (lunban + 1) % 4;
        }
    }
}

function parse_fragment(hash) {
    let [ paistr, baopai, fubaopai, zimo, zhuangfeng, menfeng, lizhi ]
            = hash.split('/');
    let shoupai = Majiang.Shoupai.fromString(paistr);
    let rongpai;
    if (zimo != '1' && shoupai._zimo) {
        rongpai = shoupai._zimo + '=';
        shoupai.dapai(shoupai._zimo);
    }
    if (lizhi == '1') {
        shoupai._lizhi = true;
    }
    baopai      = baopai ? baopai.split(',') : [];
    fubaopai    = fubaopai ? fubaopai.split(',')
                : shoupai.lizhi ? [] : null;
    zhuangfeng  = +(zhuangfeng || 0);
    menfeng     = +(menfeng || 0);
    return {
        shoupai:    shoupai,
        rongpai:    rongpai,
        zhuangfeng: zhuangfeng,
        menfeng:    menfeng,
        baopai:     baopai,
        fubaopai:   fubaopai
    };
}

function show_exam(exam) {

    let hule = Majiang.Util.hule(
                    exam.shoupai,
                    exam.rongpai,
                    Majiang.Util.hule_param({
                        rule:       player._rule,
                        zhuangfeng: exam.zhuangfeng,
                        menfeng:    exam.menfeng,
                        baopai:     exam.baopai,
                        fubaopai:   exam.fubaopai,
                        lizhi:      exam.shoupai.lizhi
                    }));

    $('.zhuangfeng').text(feng_hanzi[exam.zhuangfeng]);
    $('.menfeng').text(feng_hanzi[exam.menfeng]);

    if (exam.shoupai.lizhi) show($('.lizhi'));
    else                    hide($('.lizhi'));

    let shan = {
        baopai:   exam.baopai,
        fubaopai: exam.fubaopai,
        paishu:   0
    };
    if (exam.fubaopai) show($('.shan.fubaopai'));
    else               hide($('.shan.fubaopai'));
    view.baopai = new Majiang.UI.Shan($('.shan'), view.pai, shan).redraw(true);

    let shoupai = exam.shoupai.clone();
    if (exam.rongpai) shoupai.zimo(exam.rongpai);

    view.shoupai = new Majiang.UI.Shoupai(
                            $('.shoupai'), view.pai, shoupai
                        ).redraw(true);
    if (exam.rongpai) $('.shoupai .zimo').prepend('<span>ロン</span>');
    else              $('.shoupai .zimo').append('<span>ツモ</span>');

    let defen;
    if (hule && hule.defen) {
        defen = (exam.rongpai ? 'ロン: ' : 'ツモ: ')
              + (exam.rongpai ? hule.defen
                    : exam.menfeng
                        ? (Math.ceil(hule.defen / 200) * 100 / 2)
                            + ' / ' + (Math.floor(hule.defen / 200) * 100)
                        : `${hule.defen / 3}オール`)
              + (hule.damanguan
                  ? (hule.damanguan > 1
                        ? ` (役満 ×${hule.damanguan})`
                        : ' (役満)')
                  : ` (${hule.fu}符 ${hule.fanshu}翻)`);
    }
    else {
        defen = '(役なし)';
    }
    $('.defen').text(defen);

    let hupai = '';
    if (hule && hule.hupai)
        hupai = hule.hupai.map(h =>
                    h.name.match(/^(赤|裏)?ドラ$/)
                        ? `${h.name} ×${h.fanshu}` : h.name
                ).join(' / ');
    $('.hupai').text(hupai);

    stat.total++;

    hide($('.answer'));
    show($('.button'));

    $('.answer button.miss').off('click').on('click', ()=>{
        miss_exams.push(exam);
        next();
    });

    show($('.exam'));
    hide($('.break'));
    show($('.drill'));

    next_exam = null;
    setTimeout(()=>{
        next_exam = miss_exams.splice(Math.random() * 5, 1)[0]
                        || make_exam(player);
    }, 10);
}

function next() {
    hide($('.drill'));
    $('.stat').text(
        `回答数: ${stat.total}、`
        + `正答率: ${(stat.right / stat.total * 100)|0}%`);
    if (stat.total % 10 == 0) take_break();
    else                      show_exam(next_exam || make_exam(player));
}

function take_break() {
    hide($('.exam'));
    show($('.break'));
    show($('.drill'));
}

function restart() {

    hide($('.drill'));
    $('.stat').text('');

    next_exam = null;
    miss_exams = [];
    player = init_player();
    stat = { total:  0, right:  0 };

    if (location.hash)
            show_exam(parse_fragment(location.hash.replace(/^#/,'')));
    else    show_exam(make_exam(player));
}

$(function(){

    view.pai = Majiang.UI.pai('#loaddata');

    for (let key of Object.keys(preset)) {
        $('select[name="rule"]').append($('<option>').val(key).text(key));
    }
    if (localStorage.getItem('Majiang.rule')) {
        $('select[name="rule"]').append($('<option>')
                                .val('-').text('カスタムルール')
                                .attr('selected',true));
    }

    $('select[name="rule"]').on('change', restart);

    $('.button button').on('click', ()=>{
        show($('.answer'));
        hide($('.button'));
    });
    $('.answer button.right').on('click', ()=>{
        stat.right++;
        next();
    });
    $('.break button').on('click', ()=>{
        show_exam(next_exam || make_exam(player));
    });

    restart();
});

})();

/******/ })()
;
//# sourceMappingURL=data:application/json;charset=utf-8;base64,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QUFDQTtBQUNBLEtBQUs7O0FBRUw7QUFDQSxDQUFDIiwic291cmNlcyI6WyJ3ZWJwYWNrOi8vbWFqaWFuZy93ZWJwYWNrL2Jvb3RzdHJhcCIsIndlYnBhY2s6Ly9tYWppYW5nLy4vc3JjL2pzL2RyaWxsLmpzIl0sInNvdXJjZXNDb250ZW50IjpbIi8vIFRoZSBtb2R1bGUgY2FjaGVcbnZhciBfX3dlYnBhY2tfbW9kdWxlX2NhY2hlX18gPSB7fTtcblxuLy8gVGhlIHJlcXVpcmUgZnVuY3Rpb25cbmZ1bmN0aW9uIF9fd2VicGFja19yZXF1aXJlX18obW9kdWxlSWQpIHtcblx0Ly8gQ2hlY2sgaWYgbW9kdWxlIGlzIGluIGNhY2hlXG5cdHZhciBjYWNoZWRNb2R1bGUgPSBfX3dlYnBhY2tfbW9kdWxlX2NhY2hlX19bbW9kdWxlSWRdO1xuXHRpZiAoY2FjaGVkTW9kdWxlICE9PSB1bmRlZmluZWQpIHtcblx0XHRyZXR1cm4gY2FjaGVkTW9kdWxlLmV4cG9ydHM7XG5cdH1cblx0Ly8gQ3JlYXRlIGEgbmV3IG1vZHVsZSAoYW5kIHB1dCBpdCBpbnRvIHRoZSBjYWNoZSlcblx0dmFyIG1vZHVsZSA9IF9fd2VicGFja19tb2R1bGVfY2FjaGVfX1ttb2R1bGVJZF0gPSB7XG5cdFx0Ly8gbm8gbW9kdWxlLmlkIG5lZWRlZFxuXHRcdC8vIG5vIG1vZHVsZS5sb2FkZWQgbmVlZGVkXG5cdFx0ZXhwb3J0czoge31cblx0fTtcblxuXHQvLyBFeGVjdXRlIHRoZSBtb2R1bGUgZnVuY3Rpb25cblx0aWYgKCEobW9kdWxlSWQgaW4gX193ZWJwYWNrX21vZHVsZXNfXykpIHtcblx0XHRkZWxldGUgX193ZWJwYWNrX21vZHVsZV9jYWNoZV9fW21vZHVsZUlkXTtcblx0XHR2YXIgZSA9IG5ldyBFcnJvcihcIkNhbm5vdCBmaW5kIG1vZHVsZSAnXCIgKyBtb2R1bGVJZCArIFwiJ1wiKTtcblx0XHRlLmNvZGUgPSAnTU9EVUxFX05PVF9GT1VORCc7XG5cdFx0dGhyb3cgZTtcblx0fVxuXHRfX3dlYnBhY2tfbW9kdWxlc19fW21vZHVsZUlkXShtb2R1bGUsIG1vZHVsZS5leHBvcnRzLCBfX3dlYnBhY2tfcmVxdWlyZV9fKTtcblxuXHQvLyBSZXR1cm4gdGhlIGV4cG9ydHMgb2YgdGhlIG1vZHVsZVxuXHRyZXR1cm4gbW9kdWxlLmV4cG9ydHM7XG59XG5cbiIsIi8qIVxuICogIOmbu+iEs+m6u+Wwhjog54K55pWw6KiI566X44OJ44Oq44OrIHYyLjUuM1xuICpcbiAqICBDb3B5cmlnaHQoQykgMjAxNyBTYXRvc2hpIEtvYmF5YXNoaVxuICogIFJlbGVhc2VkIHVuZGVyIHRoZSBNSVQgbGljZW5zZVxuICogIGh0dHBzOi8vZ2l0aHViLmNvbS9rb2JhbGFiL01hamlhbmcvYmxvYi9tYXN0ZXIvTElDRU5TRVxuICovXG5cInVzZSBzdHJpY3RcIjtcblxuY29uc3QgeyBoaWRlLCBzaG93LCBmYWRlSW4sIGZhZGVPdXQgfSA9IE1hamlhbmcuVUkuVXRpbDtcblxuY29uc3QgcHJlc2V0ID0gcmVxdWlyZSgnLi9jb25mL3J1bGUuanNvbicpO1xuY29uc3QgdmlldyA9IHt9O1xuXG5jb25zdCBmZW5nX2hhbnppID0gWyfmnbEnLCfljZcnLCfopb8nLCfljJcnXTtcblxubGV0IHBsYXllciwgbmV4dF9leGFtLCBtaXNzX2V4YW1zLCBzdGF0O1xuXG5jbGFzcyBQbGF5ZXIgZXh0ZW5kcyBNYWppYW5nLkFJIHtcbiAgICBzZWxlY3RfbGl6aGkocCkge1xuICAgICAgICByZXR1cm4gdGhpcy5hbGxvd19saXpoaSh0aGlzLnNob3VwYWksIHApICYmIE1hdGgucmFuZG9tKCkgPCAwLjM7XG4gICAgfVxufVxuXG5mdW5jdGlvbiBpbml0X3BsYXllcigpIHtcblxuICAgIGxldCBwbGF5ZXIgPSBuZXcgUGxheWVyKCk7XG5cbiAgICBsZXQgcnVsZSA9ICQoJ3NlbGVjdFtuYW1lPVwicnVsZVwiXScpLnZhbCgpO1xuICAgIHJ1bGUgPSAhIHJ1bGUgICAgICA/IHt9XG4gICAgICAgICA6IHJ1bGUgPT0gJy0nID8gSlNPTi5wYXJzZShsb2NhbFN0b3JhZ2UuZ2V0SXRlbSgnTWFqaWFuZy5ydWxlJyl8fCd7fScpXG4gICAgICAgICA6ICAgICAgICAgICAgICAgcHJlc2V0W3J1bGVdO1xuICAgIHJ1bGUgPSBNYWppYW5nLnJ1bGUocnVsZSk7XG5cbiAgICBwbGF5ZXIua2FpanUoeyBpZDogMCwgcWlqaWE6IDAsIHRpdGxlOiAnJywgcGxheWVyOiBbXSwgcnVsZTogcnVsZSB9KTtcblxuICAgIHJldHVybiBwbGF5ZXI7XG59XG5cbmZ1bmN0aW9uIG1ha2VfZXhhbShwbGF5ZXIpIHtcbiAgICBmb3IgKDs7KSB7XG4gICAgICAgIGxldCB6aHVhbmdmZW5nID0gKE1hdGgucmFuZG9tKCkqMil8MDtcbiAgICAgICAgbGV0IG1lbmZlbmcgICAgPSAoTWF0aC5yYW5kb20oKSo0KXwwO1xuICAgICAgICBsZXQgc2hvdXBhaSAgICA9IFsgJycsICcnLCAnJywgJycgXTtcbiAgICAgICAgbGV0IHNoYW4gPSBuZXcgTWFqaWFuZy5TaGFuKHBsYXllci5fcnVsZSk7XG4gICAgICAgIGxldCBxaXBhaSA9IFtdO1xuICAgICAgICBmb3IgKGxldCBpID0gMDsgaSA8IDEzOyBpKyspIHFpcGFpLnB1c2goc2hhbi56aW1vKCkpO1xuICAgICAgICBzaG91cGFpW21lbmZlbmddID0gKG5ldyBNYWppYW5nLlNob3VwYWkocWlwYWkpKS50b1N0cmluZygpO1xuICAgICAgICBwbGF5ZXIucWlwYWkoe1xuICAgICAgICAgICAgemh1YW5nZmVuZzogemh1YW5nZmVuZyxcbiAgICAgICAgICAgIGp1c2h1OiAgICAgIFswLDMsMiwxXVttZW5mZW5nXSxcbiAgICAgICAgICAgIGNoYW5nYmFuZzogIDAsXG4gICAgICAgICAgICBsaXpoaWJhbmc6ICAwLFxuICAgICAgICAgICAgZGVmZW46ICAgICAgWyAyNTAwMCwgMjUwMDAsIDI1MDAwLCAyNTAwMCBdLFxuICAgICAgICAgICAgYmFvcGFpOiAgICAgc2hhbi5iYW9wYWlbMF0sXG4gICAgICAgICAgICBzaG91cGFpOiAgICBzaG91cGFpXG4gICAgICAgIH0pO1xuICAgICAgICBwbGF5ZXIuc2hhbi5wYWlzaHUgPSBzaGFuLnBhaXNodSArIDQ7XG4gICAgICAgIGxldCBnYW5nID0gbnVsbCwgbHVuYmFuID0gMDtcbiAgICAgICAgd2hpbGUgKHNoYW4ucGFpc2h1KSB7XG4gICAgICAgICAgICBsZXQgcDtcbiAgICAgICAgICAgIGlmIChnYW5nKSB7XG4gICAgICAgICAgICAgICAgcCA9IHNoYW4uZ2FuZ3ppbW8oKTtcbiAgICAgICAgICAgICAgICBpZiAoc2hhbi5fd2Vpa2FpZ2FuZykgc2hhbi5rYWlnYW5nKCk7XG4gICAgICAgICAgICAgICAgZ2FuZyA9IG51bGw7XG4gICAgICAgICAgICB9XG4gICAgICAgICAgICBlbHNlIHtcbiAgICAgICAgICAgICAgICBwID0gc2hhbi56aW1vKCk7XG4gICAgICAgICAgICB9XG4gICAgICAgICAgICBsZXQgbXNnID0geyBsOiBsdW5iYW4sIHA6IHAgfTtcbiAgICAgICAgICAgIGlmIChsdW5iYW4gPT0gbWVuZmVuZykge1xuICAgICAgICAgICAgICAgIHBsYXllci56aW1vKG1zZyk7XG4gICAgICAgICAgICAgICAgaWYgKHBsYXllci5zZWxlY3RfaHVsZSgpKSB7XG4gICAgICAgICAgICAgICAgICAgIHNoYW4uY2xvc2UoKTtcbiAgICAgICAgICAgICAgICAgICAgcmV0dXJuIHtcbiAgICAgICAgICAgICAgICAgICAgICAgIHNob3VwYWk6ICAgIHBsYXllci5zaG91cGFpLFxuICAgICAgICAgICAgICAgICAgICAgICAgemh1YW5nZmVuZzogemh1YW5nZmVuZyxcbiAgICAgICAgICAgICAgICAgICAgICAgIG1lbmZlbmc6ICAgIG1lbmZlbmcsXG4gICAgICAgICAgICAgICAgICAgICAgICBiYW9wYWk6ICAgICBzaGFuLmJhb3BhaSxcbiAgICAgICAgICAgICAgICAgICAgICAgIGZ1YmFvcGFpOiAgIHBsYXllci5zaG91cGFpLmxpemhpICYmIHNoYW4uZnViYW9wYWlcbiAgICAgICAgICAgICAgICAgICAgfTtcbiAgICAgICAgICAgICAgICB9XG4gICAgICAgICAgICAgICAgbGV0IG0gPSBwbGF5ZXIuc2VsZWN0X2dhbmcoKTtcbiAgICAgICAgICAgICAgICBpZiAobSkgIHtcbiAgICAgICAgICAgICAgICAgICAgcGxheWVyLmdhbmcoeyBsOiBtZW5mZW5nLCBtOiBtfSk7XG4gICAgICAgICAgICAgICAgICAgIGdhbmcgPSBtO1xuICAgICAgICAgICAgICAgICAgICBjb250aW51ZTtcbiAgICAgICAgICAgICAgICB9XG4gICAgICAgICAgICAgICAgcGxheWVyLmRhcGFpKHsgbDogbWVuZmVuZywgcDogcGxheWVyLnNlbGVjdF9kYXBhaSgpfSk7XG4gICAgICAgICAgICB9XG4gICAgICAgICAgICBlbHNlIHtcbiAgICAgICAgICAgICAgICBwbGF5ZXIuemltbyhtc2cpO1xuICAgICAgICAgICAgICAgIHBsYXllci5kYXBhaShtc2cpO1xuICAgICAgICAgICAgICAgIHBsYXllci5fbmVuZ19yb25nID0gdHJ1ZTtcbiAgICAgICAgICAgICAgICBpZiAocGxheWVyLnNlbGVjdF9odWxlKG1zZykpIHtcbiAgICAgICAgICAgICAgICAgICAgc2hhbi5jbG9zZSgpO1xuICAgICAgICAgICAgICAgICAgICBsZXQgcm9uZ3BhaVxuICAgICAgICAgICAgICAgICAgICAgICAgICAgID0gcCArIFsnJywnKycsJz0nLCctJ11bKDQgKyBsdW5iYW4gLSBtZW5mZW5nKSAlIDRdO1xuICAgICAgICAgICAgICAgICAgICByZXR1cm4ge1xuICAgICAgICAgICAgICAgICAgICAgICAgc2hvdXBhaTogICAgcGxheWVyLnNob3VwYWksXG4gICAgICAgICAgICAgICAgICAgICAgICByb25ncGFpOiAgICByb25ncGFpLFxuICAgICAgICAgICAgICAgICAgICAgICAgemh1YW5nZmVuZzogemh1YW5nZmVuZyxcbiAgICAgICAgICAgICAgICAgICAgICAgIG1lbmZlbmc6ICAgIG1lbmZlbmcsXG4gICAgICAgICAgICAgICAgICAgICAgICBiYW9wYWk6ICAgICBzaGFuLmJhb3BhaSxcbiAgICAgICAgICAgICAgICAgICAgICAgIGZ1YmFvcGFpOiAgIHBsYXllci5zaG91cGFpLmxpemhpICYmIHNoYW4uZnViYW9wYWlcbiAgICAgICAgICAgICAgICAgICAgfTtcbiAgICAgICAgICAgICAgICB9XG4gICAgICAgICAgICAgICAgbGV0IG0gPSBwbGF5ZXIuc2VsZWN0X2Z1bG91KG1zZyk7XG4gICAgICAgICAgICAgICAgaWYgKG0pIHtcbiAgICAgICAgICAgICAgICAgICAgcGxheWVyLmZ1bG91KHsgbDogbWVuZmVuZywgbTogbSB9KTtcbiAgICAgICAgICAgICAgICAgICAgaWYgKG0ubWF0Y2goL15bbXBzel1cXGR7NH0vKSkge1xuICAgICAgICAgICAgICAgICAgICAgICAgZ2FuZyA9IG07XG4gICAgICAgICAgICAgICAgICAgICAgICBjb250aW51ZTtcbiAgICAgICAgICAgICAgICAgICAgfVxuICAgICAgICAgICAgICAgICAgICBwbGF5ZXIuZGFwYWkoeyBsOiBtZW5mZW5nLCBwOiBwbGF5ZXIuc2VsZWN0X2RhcGFpKCl9KTtcbiAgICAgICAgICAgICAgICB9XG4gICAgICAgICAgICB9XG4gICAgICAgICAgICBsdW5iYW4gPSAobHVuYmFuICsgMSkgJSA0O1xuICAgICAgICB9XG4gICAgfVxufVxuXG5mdW5jdGlvbiBwYXJzZV9mcmFnbWVudChoYXNoKSB7XG4gICAgbGV0IFsgcGFpc3RyLCBiYW9wYWksIGZ1YmFvcGFpLCB6aW1vLCB6aHVhbmdmZW5nLCBtZW5mZW5nLCBsaXpoaSBdXG4gICAgICAgICAgICA9IGhhc2guc3BsaXQoJy8nKTtcbiAgICBsZXQgc2hvdXBhaSA9IE1hamlhbmcuU2hvdXBhaS5mcm9tU3RyaW5nKHBhaXN0cik7XG4gICAgbGV0IHJvbmdwYWk7XG4gICAgaWYgKHppbW8gIT0gJzEnICYmIHNob3VwYWkuX3ppbW8pIHtcbiAgICAgICAgcm9uZ3BhaSA9IHNob3VwYWkuX3ppbW8gKyAnPSc7XG4gICAgICAgIHNob3VwYWkuZGFwYWkoc2hvdXBhaS5femltbyk7XG4gICAgfVxuICAgIGlmIChsaXpoaSA9PSAnMScpIHtcbiAgICAgICAgc2hvdXBhaS5fbGl6aGkgPSB0cnVlO1xuICAgIH1cbiAgICBiYW9wYWkgICAgICA9IGJhb3BhaSA/IGJhb3BhaS5zcGxpdCgnLCcpIDogW107XG4gICAgZnViYW9wYWkgICAgPSBmdWJhb3BhaSA/IGZ1YmFvcGFpLnNwbGl0KCcsJylcbiAgICAgICAgICAgICAgICA6IHNob3VwYWkubGl6aGkgPyBbXSA6IG51bGw7XG4gICAgemh1YW5nZmVuZyAgPSArKHpodWFuZ2ZlbmcgfHwgMCk7XG4gICAgbWVuZmVuZyAgICAgPSArKG1lbmZlbmcgfHwgMCk7XG4gICAgcmV0dXJuIHtcbiAgICAgICAgc2hvdXBhaTogICAgc2hvdXBhaSxcbiAgICAgICAgcm9uZ3BhaTogICAgcm9uZ3BhaSxcbiAgICAgICAgemh1YW5nZmVuZzogemh1YW5nZmVuZyxcbiAgICAgICAgbWVuZmVuZzogICAgbWVuZmVuZyxcbiAgICAgICAgYmFvcGFpOiAgICAgYmFvcGFpLFxuICAgICAgICBmdWJhb3BhaTogICBmdWJhb3BhaVxuICAgIH07XG59XG5cbmZ1bmN0aW9uIHNob3dfZXhhbShleGFtKSB7XG5cbiAgICBsZXQgaHVsZSA9IE1hamlhbmcuVXRpbC5odWxlKFxuICAgICAgICAgICAgICAgICAgICBleGFtLnNob3VwYWksXG4gICAgICAgICAgICAgICAgICAgIGV4YW0ucm9uZ3BhaSxcbiAgICAgICAgICAgICAgICAgICAgTWFqaWFuZy5VdGlsLmh1bGVfcGFyYW0oe1xuICAgICAgICAgICAgICAgICAgICAgICAgcnVsZTogICAgICAgcGxheWVyLl9ydWxlLFxuICAgICAgICAgICAgICAgICAgICAgICAgemh1YW5nZmVuZzogZXhhbS56aHVhbmdmZW5nLFxuICAgICAgICAgICAgICAgICAgICAgICAgbWVuZmVuZzogICAgZXhhbS5tZW5mZW5nLFxuICAgICAgICAgICAgICAgICAgICAgICAgYmFvcGFpOiAgICAgZXhhbS5iYW9wYWksXG4gICAgICAgICAgICAgICAgICAgICAgICBmdWJhb3BhaTogICBleGFtLmZ1YmFvcGFpLFxuICAgICAgICAgICAgICAgICAgICAgICAgbGl6aGk6ICAgICAgZXhhbS5zaG91cGFpLmxpemhpXG4gICAgICAgICAgICAgICAgICAgIH0pKTtcblxuICAgICQoJy56aHVhbmdmZW5nJykudGV4dChmZW5nX2hhbnppW2V4YW0uemh1YW5nZmVuZ10pO1xuICAgICQoJy5tZW5mZW5nJykudGV4dChmZW5nX2hhbnppW2V4YW0ubWVuZmVuZ10pO1xuXG4gICAgaWYgKGV4YW0uc2hvdXBhaS5saXpoaSkgc2hvdygkKCcubGl6aGknKSk7XG4gICAgZWxzZSAgICAgICAgICAgICAgICAgICAgaGlkZSgkKCcubGl6aGknKSk7XG5cbiAgICBsZXQgc2hhbiA9IHtcbiAgICAgICAgYmFvcGFpOiAgIGV4YW0uYmFvcGFpLFxuICAgICAgICBmdWJhb3BhaTogZXhhbS5mdWJhb3BhaSxcbiAgICAgICAgcGFpc2h1OiAgIDBcbiAgICB9O1xuICAgIGlmIChleGFtLmZ1YmFvcGFpKSBzaG93KCQoJy5zaGFuLmZ1YmFvcGFpJykpO1xuICAgIGVsc2UgICAgICAgICAgICAgICBoaWRlKCQoJy5zaGFuLmZ1YmFvcGFpJykpO1xuICAgIHZpZXcuYmFvcGFpID0gbmV3IE1hamlhbmcuVUkuU2hhbigkKCcuc2hhbicpLCB2aWV3LnBhaSwgc2hhbikucmVkcmF3KHRydWUpO1xuXG4gICAgbGV0IHNob3VwYWkgPSBleGFtLnNob3VwYWkuY2xvbmUoKTtcbiAgICBpZiAoZXhhbS5yb25ncGFpKSBzaG91cGFpLnppbW8oZXhhbS5yb25ncGFpKTtcblxuICAgIHZpZXcuc2hvdXBhaSA9IG5ldyBNYWppYW5nLlVJLlNob3VwYWkoXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgJCgnLnNob3VwYWknKSwgdmlldy5wYWksIHNob3VwYWlcbiAgICAgICAgICAgICAgICAgICAgICAgICkucmVkcmF3KHRydWUpO1xuICAgIGlmIChleGFtLnJvbmdwYWkpICQoJy5zaG91cGFpIC56aW1vJykucHJlcGVuZCgnPHNwYW4+44Ot44OzPC9zcGFuPicpO1xuICAgIGVsc2UgICAgICAgICAgICAgICQoJy5zaG91cGFpIC56aW1vJykuYXBwZW5kKCc8c3Bhbj7jg4Tjg6I8L3NwYW4+Jyk7XG5cbiAgICBsZXQgZGVmZW47XG4gICAgaWYgKGh1bGUgJiYgaHVsZS5kZWZlbikge1xuICAgICAgICBkZWZlbiA9IChleGFtLnJvbmdwYWkgPyAn44Ot44OzOiAnIDogJ+ODhOODojogJylcbiAgICAgICAgICAgICAgKyAoZXhhbS5yb25ncGFpID8gaHVsZS5kZWZlblxuICAgICAgICAgICAgICAgICAgICA6IGV4YW0ubWVuZmVuZ1xuICAgICAgICAgICAgICAgICAgICAgICAgPyAoTWF0aC5jZWlsKGh1bGUuZGVmZW4gLyAyMDApICogMTAwIC8gMilcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICArICcgLyAnICsgKE1hdGguZmxvb3IoaHVsZS5kZWZlbiAvIDIwMCkgKiAxMDApXG4gICAgICAgICAgICAgICAgICAgICAgICA6IGAke2h1bGUuZGVmZW4gLyAzfeOCquODvOODq2ApXG4gICAgICAgICAgICAgICsgKGh1bGUuZGFtYW5ndWFuXG4gICAgICAgICAgICAgICAgICA/IChodWxlLmRhbWFuZ3VhbiA+IDFcbiAgICAgICAgICAgICAgICAgICAgICAgID8gYCAo5b255rqAIMOXJHtodWxlLmRhbWFuZ3Vhbn0pYFxuICAgICAgICAgICAgICAgICAgICAgICAgOiAnICjlvbnmuoApJylcbiAgICAgICAgICAgICAgICAgIDogYCAoJHtodWxlLmZ1feespiAke2h1bGUuZmFuc2h1fee/uylgKTtcbiAgICB9XG4gICAgZWxzZSB7XG4gICAgICAgIGRlZmVuID0gJyjlvbnjgarjgZcpJztcbiAgICB9XG4gICAgJCgnLmRlZmVuJykudGV4dChkZWZlbik7XG5cbiAgICBsZXQgaHVwYWkgPSAnJztcbiAgICBpZiAoaHVsZSAmJiBodWxlLmh1cGFpKVxuICAgICAgICBodXBhaSA9IGh1bGUuaHVwYWkubWFwKGggPT5cbiAgICAgICAgICAgICAgICAgICAgaC5uYW1lLm1hdGNoKC9eKOi1pHzoo48pP+ODieODqSQvKVxuICAgICAgICAgICAgICAgICAgICAgICAgPyBgJHtoLm5hbWV9IMOXJHtoLmZhbnNodX1gIDogaC5uYW1lXG4gICAgICAgICAgICAgICAgKS5qb2luKCcgLyAnKTtcbiAgICAkKCcuaHVwYWknKS50ZXh0KGh1cGFpKTtcblxuICAgIHN0YXQudG90YWwrKztcblxuICAgIGhpZGUoJCgnLmFuc3dlcicpKTtcbiAgICBzaG93KCQoJy5idXR0b24nKSk7XG5cbiAgICAkKCcuYW5zd2VyIGJ1dHRvbi5taXNzJykub2ZmKCdjbGljaycpLm9uKCdjbGljaycsICgpPT57XG4gICAgICAgIG1pc3NfZXhhbXMucHVzaChleGFtKTtcbiAgICAgICAgbmV4dCgpO1xuICAgIH0pO1xuXG4gICAgc2hvdygkKCcuZXhhbScpKTtcbiAgICBoaWRlKCQoJy5icmVhaycpKTtcbiAgICBzaG93KCQoJy5kcmlsbCcpKTtcblxuICAgIG5leHRfZXhhbSA9IG51bGw7XG4gICAgc2V0VGltZW91dCgoKT0+e1xuICAgICAgICBuZXh0X2V4YW0gPSBtaXNzX2V4YW1zLnNwbGljZShNYXRoLnJhbmRvbSgpICogNSwgMSlbMF1cbiAgICAgICAgICAgICAgICAgICAgICAgIHx8IG1ha2VfZXhhbShwbGF5ZXIpO1xuICAgIH0sIDEwKTtcbn1cblxuZnVuY3Rpb24gbmV4dCgpIHtcbiAgICBoaWRlKCQoJy5kcmlsbCcpKTtcbiAgICAkKCcuc3RhdCcpLnRleHQoXG4gICAgICAgIGDlm57nrZTmlbA6ICR7c3RhdC50b3RhbH3jgIFgXG4gICAgICAgICsgYOato+etlOeOhzogJHsoc3RhdC5yaWdodCAvIHN0YXQudG90YWwgKiAxMDApfDB9JWApO1xuICAgIGlmIChzdGF0LnRvdGFsICUgMTAgPT0gMCkgdGFrZV9icmVhaygpO1xuICAgIGVsc2UgICAgICAgICAgICAgICAgICAgICAgc2hvd19leGFtKG5leHRfZXhhbSB8fCBtYWtlX2V4YW0ocGxheWVyKSk7XG59XG5cbmZ1bmN0aW9uIHRha2VfYnJlYWsoKSB7XG4gICAgaGlkZSgkKCcuZXhhbScpKTtcbiAgICBzaG93KCQoJy5icmVhaycpKTtcbiAgICBzaG93KCQoJy5kcmlsbCcpKTtcbn1cblxuZnVuY3Rpb24gcmVzdGFydCgpIHtcblxuICAgIGhpZGUoJCgnLmRyaWxsJykpO1xuICAgICQoJy5zdGF0JykudGV4dCgnJyk7XG5cbiAgICBuZXh0X2V4YW0gPSBudWxsO1xuICAgIG1pc3NfZXhhbXMgPSBbXTtcbiAgICBwbGF5ZXIgPSBpbml0X3BsYXllcigpO1xuICAgIHN0YXQgPSB7IHRvdGFsOiAgMCwgcmlnaHQ6ICAwIH07XG5cbiAgICBpZiAobG9jYXRpb24uaGFzaClcbiAgICAgICAgICAgIHNob3dfZXhhbShwYXJzZV9mcmFnbWVudChsb2NhdGlvbi5oYXNoLnJlcGxhY2UoL14jLywnJykpKTtcbiAgICBlbHNlICAgIHNob3dfZXhhbShtYWtlX2V4YW0ocGxheWVyKSk7XG59XG5cbiQoZnVuY3Rpb24oKXtcblxuICAgIHZpZXcucGFpID0gTWFqaWFuZy5VSS5wYWkoJyNsb2FkZGF0YScpO1xuXG4gICAgZm9yIChsZXQga2V5IG9mIE9iamVjdC5rZXlzKHByZXNldCkpIHtcbiAgICAgICAgJCgnc2VsZWN0W25hbWU9XCJydWxlXCJdJykuYXBwZW5kKCQoJzxvcHRpb24+JykudmFsKGtleSkudGV4dChrZXkpKTtcbiAgICB9XG4gICAgaWYgKGxvY2FsU3RvcmFnZS5nZXRJdGVtKCdNYWppYW5nLnJ1bGUnKSkge1xuICAgICAgICAkKCdzZWxlY3RbbmFtZT1cInJ1bGVcIl0nKS5hcHBlbmQoJCgnPG9wdGlvbj4nKVxuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAudmFsKCctJykudGV4dCgn44Kr44K544K/44Og44Or44O844OrJylcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgLmF0dHIoJ3NlbGVjdGVkJyx0cnVlKSk7XG4gICAgfVxuXG4gICAgJCgnc2VsZWN0W25hbWU9XCJydWxlXCJdJykub24oJ2NoYW5nZScsIHJlc3RhcnQpO1xuXG4gICAgJCgnLmJ1dHRvbiBidXR0b24nKS5vbignY2xpY2snLCAoKT0+e1xuICAgICAgICBzaG93KCQoJy5hbnN3ZXInKSk7XG4gICAgICAgIGhpZGUoJCgnLmJ1dHRvbicpKTtcbiAgICB9KTtcbiAgICAkKCcuYW5zd2VyIGJ1dHRvbi5yaWdodCcpLm9uKCdjbGljaycsICgpPT57XG4gICAgICAgIHN0YXQucmlnaHQrKztcbiAgICAgICAgbmV4dCgpO1xuICAgIH0pO1xuICAgICQoJy5icmVhayBidXR0b24nKS5vbignY2xpY2snLCAoKT0+e1xuICAgICAgICBzaG93X2V4YW0obmV4dF9leGFtIHx8IG1ha2VfZXhhbShwbGF5ZXIpKTtcbiAgICB9KTtcblxuICAgIHJlc3RhcnQoKTtcbn0pO1xuIl0sIm5hbWVzIjpbXSwic291cmNlUm9vdCI6IiJ9
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
/*!************************!*\
  !*** ./src/js/hule.js ***!
  \************************/
/*!
 *  電脳麻将: 和了点計算 v2.5.3
 *
 *  Copyright(C) 2017 Satoshi Kobayashi
 *  Released under the MIT license
 *  https://github.com/kobalab/Majiang/blob/master/LICENSE
 */


const { hide, show, fadeIn, fadeOut } = Majiang.UI.Util;

const preset = __webpack_require__(/*! ./conf/rule.json */ "./src/js/conf/rule.json");
const view = {};

function init(fragment) {

    if (fragment) {

        let [ paistr, baopai, fubaopai, zimo, zhuangfeng, menfeng,
              lizhi, yifa, haidi, lingshang, qianggang, tianhu, rule ]
                    = fragment.split(/\//);
        baopai   = (baopai   || '').split(/,/);
        fubaopai = (fubaopai || '').split(/,/);
        rule     = decodeURIComponent(rule||'');

        $('input[name="paistr"]').val(paistr);
        for (let i = 0; i < baopai.length; i++) {
            $('input[name="baopai"]').eq(i).val(baopai[i]);
        }
        for (let i = 0; i < fubaopai.length; i++) {
            $('input[name="fubaopai"]').eq(i).val(fubaopai[i]);
        }
        $(`input[name="zimo"][value="${zimo}"]`).click();
        $('select[name="zhuangfeng"]').val(zhuangfeng || 0);
        $('select[name="menfeng"]').val(menfeng || 0);
        $(`input[name="lizhi"][value="${lizhi}"]`).click();
        if (+yifa)      $('input[name="yifa"]').click();
        if (+haidi)     $('input[name="haidi"]').click();
        if (+lingshang) $('input[name="lingshang"]').click();
        if (+qianggang) $('input[name="qianggang"]').click();
        if (+tianhu)    $('input[name="tianhu"]').click();
        if (rule)       $('select[name="rule"]').val(rule);

        $('form').submit();
    }
    else {
        let paistr = 'm123p123z1z1,s1-23,z222=';
        let baopai = ['z1'];

        $('input[name="paistr"]').val(paistr).focus();
        for (let i = 0; i < baopai.length; i++) {
            $('input[name="baopai"]').eq(i).val(baopai[i]);
        }
    }
}

function submit() {

    let paistr = $('input[name="paistr"]').val();
    if (! paistr) {
        return false;
    }
    let shoupai = Majiang.Shoupai.fromString(paistr);
    $('input[name="paistr"]').val(shoupai.toString());

    let rongpai;
    if ($('input[name="zimo"]:checked').val() == 0) {
        if (shoupai._zimo) {
            rongpai = shoupai._zimo + '=';
            shoupai.dapai(shoupai._zimo);
        }
    }

    if (! shoupai.menqian) {
        $('input[name="lizhi"]').prop('checked', false);
        $('input[name="fubaopai"]').parent().addClass('hide');
        $('input[name="yifa"]').prop('checked', false)
                               .prop('disabled', true);
        $('input[name="tianhu"]').prop('checked', false);
    }
    if (! shoupai._fulou
            .find(m=>m.replace(/0/g,'5').match(/^[mpsz](\d)\1\1.*\1.*$/)))
    {
        $('input[name="lingshang"]').prop('checked', false);
    }

    let baopai   = $.makeArray($('input[name="baopai"]'))
                        .map(n => Majiang.Shoupai.valid_pai($(n).val()))
                        .filter(p => p);
    let fubaopai = $.makeArray($('input[name="fubaopai"]'))
                        .map(n => Majiang.Shoupai.valid_pai($(n).val()))
                        .filter(p => p);

    let lizhi = + $('input[name="lizhi"]:checked').val() || 0;

    let rule = $('select[name="rule"]').val();
    rule = ! rule      ? {}
         : rule == '-' ? JSON.parse(localStorage.getItem('Majiang.rule')||'{}')
         :               preset[rule];
    rule = Majiang.rule(rule);

    if (! rule['一発あり']) {
        $('input[name="yifa"]').prop('checked', false);
    }
    if (! rule['カンドラあり']) {
        while (baopai.length > 1) baopai.pop();
        while (fubaopai.length > 1) fubaopai.pop();
    }
    if (! rule['カン裏あり']) {
        while (fubaopai.length > 1) fubaopai.pop();
    }
    if (! rule['裏ドラあり']) {
        fubaopai = null;
    }

    let param = {
        rule:       rule,
        zhuangfeng: + $('select[name="zhuangfeng"]').val(),
        menfeng:    + $('select[name="menfeng"]').val(),
        hupai: {
            lizhi:      lizhi,
            yifa:       $('input[name="yifa"]').prop('checked'),
            qianggang:  $('input[name="qianggang"]').prop('checked'),
            lingshang:  $('input[name="lingshang"]').prop('checked'),
            haidi:      ! $('input[name="haidi"]').prop('checked') ? 0
                            : ! rongpai                            ? 1
                            :                                        2,
            tianhu:     + $('input[name="tianhu"]:checked').val() || 0,
        },
        baopai:     baopai,
        fubaopai:   lizhi ? fubaopai : null,
        jicun:      { changbang: 0, lizhibang: 0 }
    };

    let hule = Majiang.Util.hule(shoupai, rongpai, param) || {};

    const model = {
        player: ['','','',''],
        defen:  [0,0,0,0],
        changbang: param.jicun.changbang,
        lizhibang: param.jicun.lizhibang,
        shan: {
            baopai:   param.baopai,
            fubaopai: param.fubaopai,
            paishu:   0
        },
        player_id:  [0,1,2,3],
    };
    const paipu = {
        l:          param.menfeng,
        shoupai:    paistr,
        baojia:     rongpai ? (param.menfeng + 2) % 4 : null,
        fubaopai:   param.fubaopai,
        fu:         hule.fu,
        fanshu:     hule.fanshu,
        damanguan:  hule.damanguan,
        defen:      hule.defen,
        hupai:      hule.hupai,
        fenpei:     hule.fenpei,
    };

    new Majiang.UI.HuleDialog($('.hule-dialog'), view.pai, model).hule(paipu);
    fadeIn($('.hule-dialog'));

    $('input[name="baopai"]').val('');
    for (let i = 0; i < baopai.length; i++) {
        $('input[name="baopai"]').eq(i).val(baopai[i]);
    }
    $('input[name="fubaopai"]').val('');
    if (! fubaopai) fubaopai = [];
    for (let i = 0; i < fubaopai.length; i++) {
        $('input[name="fubaopai"]').eq(i).val(fubaopai[i]);
    }

    let fragment = '#' + [
                    paistr,
                    baopai.join(','),
                    fubaopai.join(','),
                    $('input[name="zimo"]:checked').val(),
                    $('select[name="zhuangfeng"]').val(),
                    $('select[name="menfeng"]').val(),
                    $('input[name="lizhi"]:checked').val(),
                    + $('input[name="yifa"]').prop('checked'),
                    + $('input[name="haidi"]').prop('checked'),
                    + $('input[name="lingshang"]').prop('checked'),
                    + $('input[name="qianggang"]').prop('checked'),
                    + $('input[name="tianhu"]:checked').val() || 0
                ].join('/');
    rule = $('select[name="rule"]').val();
    if (rule) fragment += `/${rule}`;

    if (rule == '-')
            history.replaceState('', '', location.href.replace(/#.*$/,''));
    else    history.replaceState('', '', fragment);

    return false;
}

$(function(){

    view.pai = Majiang.UI.pai('#loaddata');

    for (let key of Object.keys(preset)) {
        $('select[name="rule"]').append($('<option>').val(key).text(key));
    }
    if (localStorage.getItem('Majiang.rule')) {
        $('select[name="rule"]').append($('<option>')
                                .val('-').text('カスタムルール'));
    }

    $('form').on('submit', submit);

    $('form').on('reset', function(){
        hide($('.hule-dialog'));
        $('input[name="fubaopai"]').parent().addClass('hide');
        $('input[name="tianhu"]').next().text('地和');
        $('input[name="tianhu"]').val(2);
        $('form input[name="paistr"]').focus();
    });

    $('input[name="zimo"]').on('change', function(){
        if ($(this, ':checked').val() == 1) {
            $('input[name="qianggang"]').prop('checked', false);
        }
        else {
            $('input[name="lingshang"]').prop('checked', false);
            $('input[name="tianhu"]').prop('checked', false);
        }
    });
    $('select[name="menfeng"]').on('change', function(){
        if ($(this, ':selected').val() == 0) {
            $('input[name="tianhu"]').next().text('天和');
            $('input[name="tianhu"]').val(1);
        }
        else {
            $('input[name="tianhu"]').next().text('地和');
            $('input[name="tianhu"]').val(2);
        }
    });
    $('input[name="lizhi"]').on('change', function(){
        if ($(this).prop('checked')) {
            let val = $(this).val() == 1 ? 2 : 1;
            $(`input[name="lizhi"][value="${val}"]`).prop('checked', false);
            $('input[name="fubaopai"]').parent().removeClass('hide');
            $('input[name="yifa"]').prop('disabled', false);
            $('input[name="tianhu"]').prop('checked', false);
        }
        else {
            $('input[name="fubaopai"]').parent().addClass('hide');
            $('input[name="yifa"]').prop('checked', false)
                                   .prop('disabled', true);
        }
    });
    $('input[name="yifa"]').on('change', function(){
        if ($(this).prop('checked')) {
            $('input[name="lingshang"]').prop('checked', false);
        }
    });
    $('input[name="haidi"]').on('change', function(){
        if ($(this).prop('checked')) {
            $('input[name="lingshang"]').prop('checked', false);
            $('input[name="qianggang"]').prop('checked', false);
            $('input[name="tianhu"]').prop('checked', false);
        }
    });
    $('input[name="lingshang"]').on('change', function(){
        if ($(this).prop('checked')) {
            $('input[name="yifa"]').prop('checked', false);
            $('input[name="haidi"]').prop('checked', false);
            $('input[name="qianggang"]').prop('checked', false);
            $('input[name="tianhu"]').prop('checked', false);
            $('input[name="zimo"][value="1"]').click();
        }
    });
    $('input[name="qianggang"]').on('change', function(){
        if ($(this).prop('checked')) {
            $('input[name="haidi"]').prop('checked', false);
            $('input[name="lingshang"]').prop('checked', false);
            $('input[name="tianhu"]').prop('checked', false);
            $('input[name="zimo"][value="0"]').click();
        }
    });
    $('input[name="tianhu"]').on('change', function(){
        if ($(this).prop('checked')) {
            $('input[name="lizhi"]').prop('checked', false);
            $('input[name="fubaopai"]').parent().addClass('hide');
            $('input[name="yifa"]').prop('checked', false)
                                   .prop('disabled', true);
            $('input[name="haidi"]').prop('checked', false);
            $('input[name="lingshang"]').prop('checked', false);
            $('input[name="qianggang"]').prop('checked', false);
            $('input[name="zimo"][value="1"]').click();
        }
    });

    let fragment = location.hash.replace(/^#/,'');
    init(fragment);
});

})();

/******/ })()
;
//# sourceMappingURL=data:application/json;charset=utf-8;base64,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O0FBQ0EsQ0FBQyIsInNvdXJjZXMiOlsid2VicGFjazovL21hamlhbmcvd2VicGFjay9ib290c3RyYXAiLCJ3ZWJwYWNrOi8vbWFqaWFuZy8uL3NyYy9qcy9odWxlLmpzIl0sInNvdXJjZXNDb250ZW50IjpbIi8vIFRoZSBtb2R1bGUgY2FjaGVcbnZhciBfX3dlYnBhY2tfbW9kdWxlX2NhY2hlX18gPSB7fTtcblxuLy8gVGhlIHJlcXVpcmUgZnVuY3Rpb25cbmZ1bmN0aW9uIF9fd2VicGFja19yZXF1aXJlX18obW9kdWxlSWQpIHtcblx0Ly8gQ2hlY2sgaWYgbW9kdWxlIGlzIGluIGNhY2hlXG5cdHZhciBjYWNoZWRNb2R1bGUgPSBfX3dlYnBhY2tfbW9kdWxlX2NhY2hlX19bbW9kdWxlSWRdO1xuXHRpZiAoY2FjaGVkTW9kdWxlICE9PSB1bmRlZmluZWQpIHtcblx0XHRyZXR1cm4gY2FjaGVkTW9kdWxlLmV4cG9ydHM7XG5cdH1cblx0Ly8gQ3JlYXRlIGEgbmV3IG1vZHVsZSAoYW5kIHB1dCBpdCBpbnRvIHRoZSBjYWNoZSlcblx0dmFyIG1vZHVsZSA9IF9fd2VicGFja19tb2R1bGVfY2FjaGVfX1ttb2R1bGVJZF0gPSB7XG5cdFx0Ly8gbm8gbW9kdWxlLmlkIG5lZWRlZFxuXHRcdC8vIG5vIG1vZHVsZS5sb2FkZWQgbmVlZGVkXG5cdFx0ZXhwb3J0czoge31cblx0fTtcblxuXHQvLyBFeGVjdXRlIHRoZSBtb2R1bGUgZnVuY3Rpb25cblx0aWYgKCEobW9kdWxlSWQgaW4gX193ZWJwYWNrX21vZHVsZXNfXykpIHtcblx0XHRkZWxldGUgX193ZWJwYWNrX21vZHVsZV9jYWNoZV9fW21vZHVsZUlkXTtcblx0XHR2YXIgZSA9IG5ldyBFcnJvcihcIkNhbm5vdCBmaW5kIG1vZHVsZSAnXCIgKyBtb2R1bGVJZCArIFwiJ1wiKTtcblx0XHRlLmNvZGUgPSAnTU9EVUxFX05PVF9GT1VORCc7XG5cdFx0dGhyb3cgZTtcblx0fVxuXHRfX3dlYnBhY2tfbW9kdWxlc19fW21vZHVsZUlkXShtb2R1bGUsIG1vZHVsZS5leHBvcnRzLCBfX3dlYnBhY2tfcmVxdWlyZV9fKTtcblxuXHQvLyBSZXR1cm4gdGhlIGV4cG9ydHMgb2YgdGhlIG1vZHVsZVxuXHRyZXR1cm4gbW9kdWxlLmV4cG9ydHM7XG59XG5cbiIsIi8qIVxuICogIOmbu+iEs+m6u+Wwhjog5ZKM5LqG54K56KiI566XIHYyLjUuM1xuICpcbiAqICBDb3B5cmlnaHQoQykgMjAxNyBTYXRvc2hpIEtvYmF5YXNoaVxuICogIFJlbGVhc2VkIHVuZGVyIHRoZSBNSVQgbGljZW5zZVxuICogIGh0dHBzOi8vZ2l0aHViLmNvbS9rb2JhbGFiL01hamlhbmcvYmxvYi9tYXN0ZXIvTElDRU5TRVxuICovXG5cInVzZSBzdHJpY3RcIjtcblxuY29uc3QgeyBoaWRlLCBzaG93LCBmYWRlSW4sIGZhZGVPdXQgfSA9IE1hamlhbmcuVUkuVXRpbDtcblxuY29uc3QgcHJlc2V0ID0gcmVxdWlyZSgnLi9jb25mL3J1bGUuanNvbicpO1xuY29uc3QgdmlldyA9IHt9O1xuXG5mdW5jdGlvbiBpbml0KGZyYWdtZW50KSB7XG5cbiAgICBpZiAoZnJhZ21lbnQpIHtcblxuICAgICAgICBsZXQgWyBwYWlzdHIsIGJhb3BhaSwgZnViYW9wYWksIHppbW8sIHpodWFuZ2ZlbmcsIG1lbmZlbmcsXG4gICAgICAgICAgICAgIGxpemhpLCB5aWZhLCBoYWlkaSwgbGluZ3NoYW5nLCBxaWFuZ2dhbmcsIHRpYW5odSwgcnVsZSBdXG4gICAgICAgICAgICAgICAgICAgID0gZnJhZ21lbnQuc3BsaXQoL1xcLy8pO1xuICAgICAgICBiYW9wYWkgICA9IChiYW9wYWkgICB8fCAnJykuc3BsaXQoLywvKTtcbiAgICAgICAgZnViYW9wYWkgPSAoZnViYW9wYWkgfHwgJycpLnNwbGl0KC8sLyk7XG4gICAgICAgIHJ1bGUgICAgID0gZGVjb2RlVVJJQ29tcG9uZW50KHJ1bGV8fCcnKTtcblxuICAgICAgICAkKCdpbnB1dFtuYW1lPVwicGFpc3RyXCJdJykudmFsKHBhaXN0cik7XG4gICAgICAgIGZvciAobGV0IGkgPSAwOyBpIDwgYmFvcGFpLmxlbmd0aDsgaSsrKSB7XG4gICAgICAgICAgICAkKCdpbnB1dFtuYW1lPVwiYmFvcGFpXCJdJykuZXEoaSkudmFsKGJhb3BhaVtpXSk7XG4gICAgICAgIH1cbiAgICAgICAgZm9yIChsZXQgaSA9IDA7IGkgPCBmdWJhb3BhaS5sZW5ndGg7IGkrKykge1xuICAgICAgICAgICAgJCgnaW5wdXRbbmFtZT1cImZ1YmFvcGFpXCJdJykuZXEoaSkudmFsKGZ1YmFvcGFpW2ldKTtcbiAgICAgICAgfVxuICAgICAgICAkKGBpbnB1dFtuYW1lPVwiemltb1wiXVt2YWx1ZT1cIiR7emltb31cIl1gKS5jbGljaygpO1xuICAgICAgICAkKCdzZWxlY3RbbmFtZT1cInpodWFuZ2ZlbmdcIl0nKS52YWwoemh1YW5nZmVuZyB8fCAwKTtcbiAgICAgICAgJCgnc2VsZWN0W25hbWU9XCJtZW5mZW5nXCJdJykudmFsKG1lbmZlbmcgfHwgMCk7XG4gICAgICAgICQoYGlucHV0W25hbWU9XCJsaXpoaVwiXVt2YWx1ZT1cIiR7bGl6aGl9XCJdYCkuY2xpY2soKTtcbiAgICAgICAgaWYgKCt5aWZhKSAgICAgICQoJ2lucHV0W25hbWU9XCJ5aWZhXCJdJykuY2xpY2soKTtcbiAgICAgICAgaWYgKCtoYWlkaSkgICAgICQoJ2lucHV0W25hbWU9XCJoYWlkaVwiXScpLmNsaWNrKCk7XG4gICAgICAgIGlmICgrbGluZ3NoYW5nKSAkKCdpbnB1dFtuYW1lPVwibGluZ3NoYW5nXCJdJykuY2xpY2soKTtcbiAgICAgICAgaWYgKCtxaWFuZ2dhbmcpICQoJ2lucHV0W25hbWU9XCJxaWFuZ2dhbmdcIl0nKS5jbGljaygpO1xuICAgICAgICBpZiAoK3RpYW5odSkgICAgJCgnaW5wdXRbbmFtZT1cInRpYW5odVwiXScpLmNsaWNrKCk7XG4gICAgICAgIGlmIChydWxlKSAgICAgICAkKCdzZWxlY3RbbmFtZT1cInJ1bGVcIl0nKS52YWwocnVsZSk7XG5cbiAgICAgICAgJCgnZm9ybScpLnN1Ym1pdCgpO1xuICAgIH1cbiAgICBlbHNlIHtcbiAgICAgICAgbGV0IHBhaXN0ciA9ICdtMTIzcDEyM3oxejEsczEtMjMsejIyMj0nO1xuICAgICAgICBsZXQgYmFvcGFpID0gWyd6MSddO1xuXG4gICAgICAgICQoJ2lucHV0W25hbWU9XCJwYWlzdHJcIl0nKS52YWwocGFpc3RyKS5mb2N1cygpO1xuICAgICAgICBmb3IgKGxldCBpID0gMDsgaSA8IGJhb3BhaS5sZW5ndGg7IGkrKykge1xuICAgICAgICAgICAgJCgnaW5wdXRbbmFtZT1cImJhb3BhaVwiXScpLmVxKGkpLnZhbChiYW9wYWlbaV0pO1xuICAgICAgICB9XG4gICAgfVxufVxuXG5mdW5jdGlvbiBzdWJtaXQoKSB7XG5cbiAgICBsZXQgcGFpc3RyID0gJCgnaW5wdXRbbmFtZT1cInBhaXN0clwiXScpLnZhbCgpO1xuICAgIGlmICghIHBhaXN0cikge1xuICAgICAgICByZXR1cm4gZmFsc2U7XG4gICAgfVxuICAgIGxldCBzaG91cGFpID0gTWFqaWFuZy5TaG91cGFpLmZyb21TdHJpbmcocGFpc3RyKTtcbiAgICAkKCdpbnB1dFtuYW1lPVwicGFpc3RyXCJdJykudmFsKHNob3VwYWkudG9TdHJpbmcoKSk7XG5cbiAgICBsZXQgcm9uZ3BhaTtcbiAgICBpZiAoJCgnaW5wdXRbbmFtZT1cInppbW9cIl06Y2hlY2tlZCcpLnZhbCgpID09IDApIHtcbiAgICAgICAgaWYgKHNob3VwYWkuX3ppbW8pIHtcbiAgICAgICAgICAgIHJvbmdwYWkgPSBzaG91cGFpLl96aW1vICsgJz0nO1xuICAgICAgICAgICAgc2hvdXBhaS5kYXBhaShzaG91cGFpLl96aW1vKTtcbiAgICAgICAgfVxuICAgIH1cblxuICAgIGlmICghIHNob3VwYWkubWVucWlhbikge1xuICAgICAgICAkKCdpbnB1dFtuYW1lPVwibGl6aGlcIl0nKS5wcm9wKCdjaGVja2VkJywgZmFsc2UpO1xuICAgICAgICAkKCdpbnB1dFtuYW1lPVwiZnViYW9wYWlcIl0nKS5wYXJlbnQoKS5hZGRDbGFzcygnaGlkZScpO1xuICAgICAgICAkKCdpbnB1dFtuYW1lPVwieWlmYVwiXScpLnByb3AoJ2NoZWNrZWQnLCBmYWxzZSlcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAucHJvcCgnZGlzYWJsZWQnLCB0cnVlKTtcbiAgICAgICAgJCgnaW5wdXRbbmFtZT1cInRpYW5odVwiXScpLnByb3AoJ2NoZWNrZWQnLCBmYWxzZSk7XG4gICAgfVxuICAgIGlmICghIHNob3VwYWkuX2Z1bG91XG4gICAgICAgICAgICAuZmluZChtPT5tLnJlcGxhY2UoLzAvZywnNScpLm1hdGNoKC9eW21wc3pdKFxcZClcXDFcXDEuKlxcMS4qJC8pKSlcbiAgICB7XG4gICAgICAgICQoJ2lucHV0W25hbWU9XCJsaW5nc2hhbmdcIl0nKS5wcm9wKCdjaGVja2VkJywgZmFsc2UpO1xuICAgIH1cblxuICAgIGxldCBiYW9wYWkgICA9ICQubWFrZUFycmF5KCQoJ2lucHV0W25hbWU9XCJiYW9wYWlcIl0nKSlcbiAgICAgICAgICAgICAgICAgICAgICAgIC5tYXAobiA9PiBNYWppYW5nLlNob3VwYWkudmFsaWRfcGFpKCQobikudmFsKCkpKVxuICAgICAgICAgICAgICAgICAgICAgICAgLmZpbHRlcihwID0+IHApO1xuICAgIGxldCBmdWJhb3BhaSA9ICQubWFrZUFycmF5KCQoJ2lucHV0W25hbWU9XCJmdWJhb3BhaVwiXScpKVxuICAgICAgICAgICAgICAgICAgICAgICAgLm1hcChuID0+IE1hamlhbmcuU2hvdXBhaS52YWxpZF9wYWkoJChuKS52YWwoKSkpXG4gICAgICAgICAgICAgICAgICAgICAgICAuZmlsdGVyKHAgPT4gcCk7XG5cbiAgICBsZXQgbGl6aGkgPSArICQoJ2lucHV0W25hbWU9XCJsaXpoaVwiXTpjaGVja2VkJykudmFsKCkgfHwgMDtcblxuICAgIGxldCBydWxlID0gJCgnc2VsZWN0W25hbWU9XCJydWxlXCJdJykudmFsKCk7XG4gICAgcnVsZSA9ICEgcnVsZSAgICAgID8ge31cbiAgICAgICAgIDogcnVsZSA9PSAnLScgPyBKU09OLnBhcnNlKGxvY2FsU3RvcmFnZS5nZXRJdGVtKCdNYWppYW5nLnJ1bGUnKXx8J3t9JylcbiAgICAgICAgIDogICAgICAgICAgICAgICBwcmVzZXRbcnVsZV07XG4gICAgcnVsZSA9IE1hamlhbmcucnVsZShydWxlKTtcblxuICAgIGlmICghIHJ1bGVbJ+S4gOeZuuOBguOCiiddKSB7XG4gICAgICAgICQoJ2lucHV0W25hbWU9XCJ5aWZhXCJdJykucHJvcCgnY2hlY2tlZCcsIGZhbHNlKTtcbiAgICB9XG4gICAgaWYgKCEgcnVsZVsn44Kr44Oz44OJ44Op44GC44KKJ10pIHtcbiAgICAgICAgd2hpbGUgKGJhb3BhaS5sZW5ndGggPiAxKSBiYW9wYWkucG9wKCk7XG4gICAgICAgIHdoaWxlIChmdWJhb3BhaS5sZW5ndGggPiAxKSBmdWJhb3BhaS5wb3AoKTtcbiAgICB9XG4gICAgaWYgKCEgcnVsZVsn44Kr44Oz6KOP44GC44KKJ10pIHtcbiAgICAgICAgd2hpbGUgKGZ1YmFvcGFpLmxlbmd0aCA+IDEpIGZ1YmFvcGFpLnBvcCgpO1xuICAgIH1cbiAgICBpZiAoISBydWxlWyfoo4/jg4njg6njgYLjgoonXSkge1xuICAgICAgICBmdWJhb3BhaSA9IG51bGw7XG4gICAgfVxuXG4gICAgbGV0IHBhcmFtID0ge1xuICAgICAgICBydWxlOiAgICAgICBydWxlLFxuICAgICAgICB6aHVhbmdmZW5nOiArICQoJ3NlbGVjdFtuYW1lPVwiemh1YW5nZmVuZ1wiXScpLnZhbCgpLFxuICAgICAgICBtZW5mZW5nOiAgICArICQoJ3NlbGVjdFtuYW1lPVwibWVuZmVuZ1wiXScpLnZhbCgpLFxuICAgICAgICBodXBhaToge1xuICAgICAgICAgICAgbGl6aGk6ICAgICAgbGl6aGksXG4gICAgICAgICAgICB5aWZhOiAgICAgICAkKCdpbnB1dFtuYW1lPVwieWlmYVwiXScpLnByb3AoJ2NoZWNrZWQnKSxcbiAgICAgICAgICAgIHFpYW5nZ2FuZzogICQoJ2lucHV0W25hbWU9XCJxaWFuZ2dhbmdcIl0nKS5wcm9wKCdjaGVja2VkJyksXG4gICAgICAgICAgICBsaW5nc2hhbmc6ICAkKCdpbnB1dFtuYW1lPVwibGluZ3NoYW5nXCJdJykucHJvcCgnY2hlY2tlZCcpLFxuICAgICAgICAgICAgaGFpZGk6ICAgICAgISAkKCdpbnB1dFtuYW1lPVwiaGFpZGlcIl0nKS5wcm9wKCdjaGVja2VkJykgPyAwXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgOiAhIHJvbmdwYWkgICAgICAgICAgICAgICAgICAgICAgICAgICAgPyAxXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgOiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAyLFxuICAgICAgICAgICAgdGlhbmh1OiAgICAgKyAkKCdpbnB1dFtuYW1lPVwidGlhbmh1XCJdOmNoZWNrZWQnKS52YWwoKSB8fCAwLFxuICAgICAgICB9LFxuICAgICAgICBiYW9wYWk6ICAgICBiYW9wYWksXG4gICAgICAgIGZ1YmFvcGFpOiAgIGxpemhpID8gZnViYW9wYWkgOiBudWxsLFxuICAgICAgICBqaWN1bjogICAgICB7IGNoYW5nYmFuZzogMCwgbGl6aGliYW5nOiAwIH1cbiAgICB9O1xuXG4gICAgbGV0IGh1bGUgPSBNYWppYW5nLlV0aWwuaHVsZShzaG91cGFpLCByb25ncGFpLCBwYXJhbSkgfHwge307XG5cbiAgICBjb25zdCBtb2RlbCA9IHtcbiAgICAgICAgcGxheWVyOiBbJycsJycsJycsJyddLFxuICAgICAgICBkZWZlbjogIFswLDAsMCwwXSxcbiAgICAgICAgY2hhbmdiYW5nOiBwYXJhbS5qaWN1bi5jaGFuZ2JhbmcsXG4gICAgICAgIGxpemhpYmFuZzogcGFyYW0uamljdW4ubGl6aGliYW5nLFxuICAgICAgICBzaGFuOiB7XG4gICAgICAgICAgICBiYW9wYWk6ICAgcGFyYW0uYmFvcGFpLFxuICAgICAgICAgICAgZnViYW9wYWk6IHBhcmFtLmZ1YmFvcGFpLFxuICAgICAgICAgICAgcGFpc2h1OiAgIDBcbiAgICAgICAgfSxcbiAgICAgICAgcGxheWVyX2lkOiAgWzAsMSwyLDNdLFxuICAgIH07XG4gICAgY29uc3QgcGFpcHUgPSB7XG4gICAgICAgIGw6ICAgICAgICAgIHBhcmFtLm1lbmZlbmcsXG4gICAgICAgIHNob3VwYWk6ICAgIHBhaXN0cixcbiAgICAgICAgYmFvamlhOiAgICAgcm9uZ3BhaSA/IChwYXJhbS5tZW5mZW5nICsgMikgJSA0IDogbnVsbCxcbiAgICAgICAgZnViYW9wYWk6ICAgcGFyYW0uZnViYW9wYWksXG4gICAgICAgIGZ1OiAgICAgICAgIGh1bGUuZnUsXG4gICAgICAgIGZhbnNodTogICAgIGh1bGUuZmFuc2h1LFxuICAgICAgICBkYW1hbmd1YW46ICBodWxlLmRhbWFuZ3VhbixcbiAgICAgICAgZGVmZW46ICAgICAgaHVsZS5kZWZlbixcbiAgICAgICAgaHVwYWk6ICAgICAgaHVsZS5odXBhaSxcbiAgICAgICAgZmVucGVpOiAgICAgaHVsZS5mZW5wZWksXG4gICAgfTtcblxuICAgIG5ldyBNYWppYW5nLlVJLkh1bGVEaWFsb2coJCgnLmh1bGUtZGlhbG9nJyksIHZpZXcucGFpLCBtb2RlbCkuaHVsZShwYWlwdSk7XG4gICAgZmFkZUluKCQoJy5odWxlLWRpYWxvZycpKTtcblxuICAgICQoJ2lucHV0W25hbWU9XCJiYW9wYWlcIl0nKS52YWwoJycpO1xuICAgIGZvciAobGV0IGkgPSAwOyBpIDwgYmFvcGFpLmxlbmd0aDsgaSsrKSB7XG4gICAgICAgICQoJ2lucHV0W25hbWU9XCJiYW9wYWlcIl0nKS5lcShpKS52YWwoYmFvcGFpW2ldKTtcbiAgICB9XG4gICAgJCgnaW5wdXRbbmFtZT1cImZ1YmFvcGFpXCJdJykudmFsKCcnKTtcbiAgICBpZiAoISBmdWJhb3BhaSkgZnViYW9wYWkgPSBbXTtcbiAgICBmb3IgKGxldCBpID0gMDsgaSA8IGZ1YmFvcGFpLmxlbmd0aDsgaSsrKSB7XG4gICAgICAgICQoJ2lucHV0W25hbWU9XCJmdWJhb3BhaVwiXScpLmVxKGkpLnZhbChmdWJhb3BhaVtpXSk7XG4gICAgfVxuXG4gICAgbGV0IGZyYWdtZW50ID0gJyMnICsgW1xuICAgICAgICAgICAgICAgICAgICBwYWlzdHIsXG4gICAgICAgICAgICAgICAgICAgIGJhb3BhaS5qb2luKCcsJyksXG4gICAgICAgICAgICAgICAgICAgIGZ1YmFvcGFpLmpvaW4oJywnKSxcbiAgICAgICAgICAgICAgICAgICAgJCgnaW5wdXRbbmFtZT1cInppbW9cIl06Y2hlY2tlZCcpLnZhbCgpLFxuICAgICAgICAgICAgICAgICAgICAkKCdzZWxlY3RbbmFtZT1cInpodWFuZ2ZlbmdcIl0nKS52YWwoKSxcbiAgICAgICAgICAgICAgICAgICAgJCgnc2VsZWN0W25hbWU9XCJtZW5mZW5nXCJdJykudmFsKCksXG4gICAgICAgICAgICAgICAgICAgICQoJ2lucHV0W25hbWU9XCJsaXpoaVwiXTpjaGVja2VkJykudmFsKCksXG4gICAgICAgICAgICAgICAgICAgICsgJCgnaW5wdXRbbmFtZT1cInlpZmFcIl0nKS5wcm9wKCdjaGVja2VkJyksXG4gICAgICAgICAgICAgICAgICAgICsgJCgnaW5wdXRbbmFtZT1cImhhaWRpXCJdJykucHJvcCgnY2hlY2tlZCcpLFxuICAgICAgICAgICAgICAgICAgICArICQoJ2lucHV0W25hbWU9XCJsaW5nc2hhbmdcIl0nKS5wcm9wKCdjaGVja2VkJyksXG4gICAgICAgICAgICAgICAgICAgICsgJCgnaW5wdXRbbmFtZT1cInFpYW5nZ2FuZ1wiXScpLnByb3AoJ2NoZWNrZWQnKSxcbiAgICAgICAgICAgICAgICAgICAgKyAkKCdpbnB1dFtuYW1lPVwidGlhbmh1XCJdOmNoZWNrZWQnKS52YWwoKSB8fCAwXG4gICAgICAgICAgICAgICAgXS5qb2luKCcvJyk7XG4gICAgcnVsZSA9ICQoJ3NlbGVjdFtuYW1lPVwicnVsZVwiXScpLnZhbCgpO1xuICAgIGlmIChydWxlKSBmcmFnbWVudCArPSBgLyR7cnVsZX1gO1xuXG4gICAgaWYgKHJ1bGUgPT0gJy0nKVxuICAgICAgICAgICAgaGlzdG9yeS5yZXBsYWNlU3RhdGUoJycsICcnLCBsb2NhdGlvbi5ocmVmLnJlcGxhY2UoLyMuKiQvLCcnKSk7XG4gICAgZWxzZSAgICBoaXN0b3J5LnJlcGxhY2VTdGF0ZSgnJywgJycsIGZyYWdtZW50KTtcblxuICAgIHJldHVybiBmYWxzZTtcbn1cblxuJChmdW5jdGlvbigpe1xuXG4gICAgdmlldy5wYWkgPSBNYWppYW5nLlVJLnBhaSgnI2xvYWRkYXRhJyk7XG5cbiAgICBmb3IgKGxldCBrZXkgb2YgT2JqZWN0LmtleXMocHJlc2V0KSkge1xuICAgICAgICAkKCdzZWxlY3RbbmFtZT1cInJ1bGVcIl0nKS5hcHBlbmQoJCgnPG9wdGlvbj4nKS52YWwoa2V5KS50ZXh0KGtleSkpO1xuICAgIH1cbiAgICBpZiAobG9jYWxTdG9yYWdlLmdldEl0ZW0oJ01hamlhbmcucnVsZScpKSB7XG4gICAgICAgICQoJ3NlbGVjdFtuYW1lPVwicnVsZVwiXScpLmFwcGVuZCgkKCc8b3B0aW9uPicpXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIC52YWwoJy0nKS50ZXh0KCfjgqvjgrnjgr/jg6Djg6vjg7zjg6snKSk7XG4gICAgfVxuXG4gICAgJCgnZm9ybScpLm9uKCdzdWJtaXQnLCBzdWJtaXQpO1xuXG4gICAgJCgnZm9ybScpLm9uKCdyZXNldCcsIGZ1bmN0aW9uKCl7XG4gICAgICAgIGhpZGUoJCgnLmh1bGUtZGlhbG9nJykpO1xuICAgICAgICAkKCdpbnB1dFtuYW1lPVwiZnViYW9wYWlcIl0nKS5wYXJlbnQoKS5hZGRDbGFzcygnaGlkZScpO1xuICAgICAgICAkKCdpbnB1dFtuYW1lPVwidGlhbmh1XCJdJykubmV4dCgpLnRleHQoJ+WcsOWSjCcpO1xuICAgICAgICAkKCdpbnB1dFtuYW1lPVwidGlhbmh1XCJdJykudmFsKDIpO1xuICAgICAgICAkKCdmb3JtIGlucHV0W25hbWU9XCJwYWlzdHJcIl0nKS5mb2N1cygpO1xuICAgIH0pO1xuXG4gICAgJCgnaW5wdXRbbmFtZT1cInppbW9cIl0nKS5vbignY2hhbmdlJywgZnVuY3Rpb24oKXtcbiAgICAgICAgaWYgKCQodGhpcywgJzpjaGVja2VkJykudmFsKCkgPT0gMSkge1xuICAgICAgICAgICAgJCgnaW5wdXRbbmFtZT1cInFpYW5nZ2FuZ1wiXScpLnByb3AoJ2NoZWNrZWQnLCBmYWxzZSk7XG4gICAgICAgIH1cbiAgICAgICAgZWxzZSB7XG4gICAgICAgICAgICAkKCdpbnB1dFtuYW1lPVwibGluZ3NoYW5nXCJdJykucHJvcCgnY2hlY2tlZCcsIGZhbHNlKTtcbiAgICAgICAgICAgICQoJ2lucHV0W25hbWU9XCJ0aWFuaHVcIl0nKS5wcm9wKCdjaGVja2VkJywgZmFsc2UpO1xuICAgICAgICB9XG4gICAgfSk7XG4gICAgJCgnc2VsZWN0W25hbWU9XCJtZW5mZW5nXCJdJykub24oJ2NoYW5nZScsIGZ1bmN0aW9uKCl7XG4gICAgICAgIGlmICgkKHRoaXMsICc6c2VsZWN0ZWQnKS52YWwoKSA9PSAwKSB7XG4gICAgICAgICAgICAkKCdpbnB1dFtuYW1lPVwidGlhbmh1XCJdJykubmV4dCgpLnRleHQoJ+WkqeWSjCcpO1xuICAgICAgICAgICAgJCgnaW5wdXRbbmFtZT1cInRpYW5odVwiXScpLnZhbCgxKTtcbiAgICAgICAgfVxuICAgICAgICBlbHNlIHtcbiAgICAgICAgICAgICQoJ2lucHV0W25hbWU9XCJ0aWFuaHVcIl0nKS5uZXh0KCkudGV4dCgn5Zyw5ZKMJyk7XG4gICAgICAgICAgICAkKCdpbnB1dFtuYW1lPVwidGlhbmh1XCJdJykudmFsKDIpO1xuICAgICAgICB9XG4gICAgfSk7XG4gICAgJCgnaW5wdXRbbmFtZT1cImxpemhpXCJdJykub24oJ2NoYW5nZScsIGZ1bmN0aW9uKCl7XG4gICAgICAgIGlmICgkKHRoaXMpLnByb3AoJ2NoZWNrZWQnKSkge1xuICAgICAgICAgICAgbGV0IHZhbCA9ICQodGhpcykudmFsKCkgPT0gMSA/IDIgOiAxO1xuICAgICAgICAgICAgJChgaW5wdXRbbmFtZT1cImxpemhpXCJdW3ZhbHVlPVwiJHt2YWx9XCJdYCkucHJvcCgnY2hlY2tlZCcsIGZhbHNlKTtcbiAgICAgICAgICAgICQoJ2lucHV0W25hbWU9XCJmdWJhb3BhaVwiXScpLnBhcmVudCgpLnJlbW92ZUNsYXNzKCdoaWRlJyk7XG4gICAgICAgICAgICAkKCdpbnB1dFtuYW1lPVwieWlmYVwiXScpLnByb3AoJ2Rpc2FibGVkJywgZmFsc2UpO1xuICAgICAgICAgICAgJCgnaW5wdXRbbmFtZT1cInRpYW5odVwiXScpLnByb3AoJ2NoZWNrZWQnLCBmYWxzZSk7XG4gICAgICAgIH1cbiAgICAgICAgZWxzZSB7XG4gICAgICAgICAgICAkKCdpbnB1dFtuYW1lPVwiZnViYW9wYWlcIl0nKS5wYXJlbnQoKS5hZGRDbGFzcygnaGlkZScpO1xuICAgICAgICAgICAgJCgnaW5wdXRbbmFtZT1cInlpZmFcIl0nKS5wcm9wKCdjaGVja2VkJywgZmFsc2UpXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIC5wcm9wKCdkaXNhYmxlZCcsIHRydWUpO1xuICAgICAgICB9XG4gICAgfSk7XG4gICAgJCgnaW5wdXRbbmFtZT1cInlpZmFcIl0nKS5vbignY2hhbmdlJywgZnVuY3Rpb24oKXtcbiAgICAgICAgaWYgKCQodGhpcykucHJvcCgnY2hlY2tlZCcpKSB7XG4gICAgICAgICAgICAkKCdpbnB1dFtuYW1lPVwibGluZ3NoYW5nXCJdJykucHJvcCgnY2hlY2tlZCcsIGZhbHNlKTtcbiAgICAgICAgfVxuICAgIH0pO1xuICAgICQoJ2lucHV0W25hbWU9XCJoYWlkaVwiXScpLm9uKCdjaGFuZ2UnLCBmdW5jdGlvbigpe1xuICAgICAgICBpZiAoJCh0aGlzKS5wcm9wKCdjaGVja2VkJykpIHtcbiAgICAgICAgICAgICQoJ2lucHV0W25hbWU9XCJsaW5nc2hhbmdcIl0nKS5wcm9wKCdjaGVja2VkJywgZmFsc2UpO1xuICAgICAgICAgICAgJCgnaW5wdXRbbmFtZT1cInFpYW5nZ2FuZ1wiXScpLnByb3AoJ2NoZWNrZWQnLCBmYWxzZSk7XG4gICAgICAgICAgICAkKCdpbnB1dFtuYW1lPVwidGlhbmh1XCJdJykucHJvcCgnY2hlY2tlZCcsIGZhbHNlKTtcbiAgICAgICAgfVxuICAgIH0pO1xuICAgICQoJ2lucHV0W25hbWU9XCJsaW5nc2hhbmdcIl0nKS5vbignY2hhbmdlJywgZnVuY3Rpb24oKXtcbiAgICAgICAgaWYgKCQodGhpcykucHJvcCgnY2hlY2tlZCcpKSB7XG4gICAgICAgICAgICAkKCdpbnB1dFtuYW1lPVwieWlmYVwiXScpLnByb3AoJ2NoZWNrZWQnLCBmYWxzZSk7XG4gICAgICAgICAgICAkKCdpbnB1dFtuYW1lPVwiaGFpZGlcIl0nKS5wcm9wKCdjaGVja2VkJywgZmFsc2UpO1xuICAgICAgICAgICAgJCgnaW5wdXRbbmFtZT1cInFpYW5nZ2FuZ1wiXScpLnByb3AoJ2NoZWNrZWQnLCBmYWxzZSk7XG4gICAgICAgICAgICAkKCdpbnB1dFtuYW1lPVwidGlhbmh1XCJdJykucHJvcCgnY2hlY2tlZCcsIGZhbHNlKTtcbiAgICAgICAgICAgICQoJ2lucHV0W25hbWU9XCJ6aW1vXCJdW3ZhbHVlPVwiMVwiXScpLmNsaWNrKCk7XG4gICAgICAgIH1cbiAgICB9KTtcbiAgICAkKCdpbnB1dFtuYW1lPVwicWlhbmdnYW5nXCJdJykub24oJ2NoYW5nZScsIGZ1bmN0aW9uKCl7XG4gICAgICAgIGlmICgkKHRoaXMpLnByb3AoJ2NoZWNrZWQnKSkge1xuICAgICAgICAgICAgJCgnaW5wdXRbbmFtZT1cImhhaWRpXCJdJykucHJvcCgnY2hlY2tlZCcsIGZhbHNlKTtcbiAgICAgICAgICAgICQoJ2lucHV0W25hbWU9XCJsaW5nc2hhbmdcIl0nKS5wcm9wKCdjaGVja2VkJywgZmFsc2UpO1xuICAgICAgICAgICAgJCgnaW5wdXRbbmFtZT1cInRpYW5odVwiXScpLnByb3AoJ2NoZWNrZWQnLCBmYWxzZSk7XG4gICAgICAgICAgICAkKCdpbnB1dFtuYW1lPVwiemltb1wiXVt2YWx1ZT1cIjBcIl0nKS5jbGljaygpO1xuICAgICAgICB9XG4gICAgfSk7XG4gICAgJCgnaW5wdXRbbmFtZT1cInRpYW5odVwiXScpLm9uKCdjaGFuZ2UnLCBmdW5jdGlvbigpe1xuICAgICAgICBpZiAoJCh0aGlzKS5wcm9wKCdjaGVja2VkJykpIHtcbiAgICAgICAgICAgICQoJ2lucHV0W25hbWU9XCJsaXpoaVwiXScpLnByb3AoJ2NoZWNrZWQnLCBmYWxzZSk7XG4gICAgICAgICAgICAkKCdpbnB1dFtuYW1lPVwiZnViYW9wYWlcIl0nKS5wYXJlbnQoKS5hZGRDbGFzcygnaGlkZScpO1xuICAgICAgICAgICAgJCgnaW5wdXRbbmFtZT1cInlpZmFcIl0nKS5wcm9wKCdjaGVja2VkJywgZmFsc2UpXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIC5wcm9wKCdkaXNhYmxlZCcsIHRydWUpO1xuICAgICAgICAgICAgJCgnaW5wdXRbbmFtZT1cImhhaWRpXCJdJykucHJvcCgnY2hlY2tlZCcsIGZhbHNlKTtcbiAgICAgICAgICAgICQoJ2lucHV0W25hbWU9XCJsaW5nc2hhbmdcIl0nKS5wcm9wKCdjaGVja2VkJywgZmFsc2UpO1xuICAgICAgICAgICAgJCgnaW5wdXRbbmFtZT1cInFpYW5nZ2FuZ1wiXScpLnByb3AoJ2NoZWNrZWQnLCBmYWxzZSk7XG4gICAgICAgICAgICAkKCdpbnB1dFtuYW1lPVwiemltb1wiXVt2YWx1ZT1cIjFcIl0nKS5jbGljaygpO1xuICAgICAgICB9XG4gICAgfSk7XG5cbiAgICBsZXQgZnJhZ21lbnQgPSBsb2NhdGlvbi5oYXNoLnJlcGxhY2UoL14jLywnJyk7XG4gICAgaW5pdChmcmFnbWVudCk7XG59KTtcbiJdLCJuYW1lcyI6W10sInNvdXJjZVJvb3QiOiIifQ==
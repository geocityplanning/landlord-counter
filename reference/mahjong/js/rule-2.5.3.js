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
  !*** ./src/js/rule.js ***!
  \************************/
/*!
 *  電脳麻将: ルール設定 v2.5.3
 *
 *  Copyright(C) 2017 Satoshi Kobayashi
 *  Released under the MIT license
 *  https://github.com/kobalab/Majiang/blob/master/LICENSE
 */


const preset = __webpack_require__(/*! ./conf/rule.json */ "./src/js/conf/rule.json");

function set_form(rule) {

    for (let key of Object.keys(rule)) {

        let value;

        if (key == '順位点') {
            value = rule[key].find(n=>n.match(/\./)) ? 0 : 1;
            $('input[name="順位点四捨五入あり"]').val([value]);
            for (let i = 1; i < 4; i++) {
                $('input[name="順位点"]').eq(i).val(rule[key][i]);
            }
            continue;
        }
        if (key == '赤牌') {
            $('input[name="赤牌"]').eq(0).val(rule[key].m);
            $('input[name="赤牌"]').eq(1).val(rule[key].p);
            $('input[name="赤牌"]').eq(2).val(rule[key].s);
            continue;
        }

        if ($(`input[name="${key}"]`).attr('type') == 'radio' ||
            $(`input[name="${key}"]`).attr('type') == 'checkbox')
        {
            value = rule[key] === false ? [0]
                  : rule[key] === true  ? [1]
                  :                       [rule[key]];
        }
        else {
            value = rule[key];
        }
        $(`input[name="${key}"]`).val(value);
    }

    repair_point();
    repair_gang();
    repair_damanguan();

    Majiang.UI.Util.fadeIn($('form'));
}

function get_form() {

    let rule = Majiang.rule();

    for (let key of Object.keys(rule)) {

        if (key == '順位点') {
            for (let i = 0; i < 4; i++) {
                rule[key][i] = $('input[name="順位点"]').eq(i).val();
            }
            continue;
        }
        if (key == '赤牌') {
            rule[key].m = + $('input[name="赤牌"]').eq(0).val();
            rule[key].p = + $('input[name="赤牌"]').eq(1).val();
            rule[key].s = + $('input[name="赤牌"]').eq(2).val();
            continue;
        }

        if ($(`input[name="${key}"]`).attr('type') == 'radio') {
            rule[key] = + $(`input[name="${key}"]:checked`).val();
            if ($(`input[name="${key}"]`).length == 2) {
                rule[key] = rule[key] != 0;
            }
        }
        else if ($(`input[name="${key}"]`).attr('type') == 'checkbox') {
            rule[key] = $(`input[name="${key}"]`).prop('checked');
        }
        else {
            rule[key] = + $(`input[name="${key}"]`).val();
        }
    }
    return rule;
}

function round_point(p, round) {
    p = isNaN(p) ? '0'
      : + p > 0  ? '+' + (+ p)
      :            ''  + (+ p);
    if (round) p.replace(/\.\d*$/,'');
    else       p = ! p.match(/\./) ? p + '.0' : p;
    return p;
}

function repair_point() {
    let round = $('input[name="順位点四捨五入あり"]').prop('checked');
    let sum = 0;
    for (let i = 1; i < 4; i++) {
        let p = + $('input[name="順位点"]').eq(i).val();
        sum += p;
        $('input[name="順位点"]').eq(i).val(round_point(p, round))
    }
    $('input[name="順位点"]').eq(0).val(round_point(-sum, round))
}

function repair_gang() {
    if (+ $('input[name="裏ドラあり"]:checked').val()
        && + $('input[name="カンドラあり"]:checked').val())
    {
        $('input[name="カン裏あり"]').prop('disabled', false);
    }
    else {
        $('input[name="カン裏あり"]').prop('disabled', true).val([0]);
    }

    if (+ $('input[name="カンドラあり"]:checked').val()) {
        $('input[name="カンドラ後乗せ"]').prop('disabled', false);
    }
    else {
        $('input[name="カンドラ後乗せ"]').prop('disabled', true)
                                        .prop('checked', false);
    }
}

function repair_damanguan() {
    if (+ $('input[name="役満の複合あり"]:checked').val()) {
        $('input[name="ダブル役満あり"]').prop('disabled', false);
    }
    else {
        $('input[name="ダブル役満あり"]').prop('disabled', true).val([0]);
    }
}

function unsaved() {
    $(window).on('beforeunload', (ev)=>{
        const message = 'ページを離れますがよろしいですか？';
        ev.returnValue = message;
        return message;
    });
}

$(function(){

    for (let key of Object.keys(preset)) {
        $('select[name="プリセット"]').append($('<option>').val(key).text(key));
    }
    if (localStorage.getItem('Majiang.rule')) {
        $('select[name="プリセット"]').append($('<option>')
                                    .val('-').text('カスタムルール'));
        $('select[name="プリセット"]').val('-');
    }

    let rule = Majiang.rule(
                    JSON.parse(localStorage.getItem('Majiang.rule')||'{}'));
    set_form(rule);

    $('input[name="配給原点"]').on('change', function(){
        let p = $(this).val();
        if (isNaN(p) || p <= 0) $(this).val(Majiang.rule()['配給原点']);
    });
    $('input[name="順位点"]').on('change', repair_point);
    $('input[name="順位点四捨五入あり"]').on('change', repair_point);
    $('input[name="赤牌"]').on('change', function(){
        let n = $(this).val();
        if (isNaN(n) || n < 0 || 4 < n) $(this).val(0);
    });
    $('input[name="裏ドラあり"]').on('change', repair_gang);
    $('input[name="カンドラあり"]').on('change', repair_gang);
    $('input[name="役満の複合あり"]').on('change', repair_damanguan);

    $('input[name="プリセット"]').on('click', ()=>{
        let key = $('select[name="プリセット"]').val();
        set_form(Majiang.rule(key == '-'
                    ? JSON.parse(localStorage.getItem('Majiang.rule')||'{}')
                    : preset[key] || {}));
        unsaved();
        return false;
    });

    $('form input').on('change', unsaved);

    $('form').on('submit', ()=>{
        if (! localStorage.getItem('Majiang.rule')) {
            $('select[name="プリセット"]').append($('<option>')
                                        .val('-').text('カスタムルール'));
        }
        localStorage.setItem('Majiang.rule', JSON.stringify(get_form()));

        $(window).off('beforeunload');
        $('select[name="プリセット"]').val('-');
        Majiang.UI.Util.fadeIn($('form'));
        Majiang.UI.Util.fadeIn($('.message'));
        setTimeout(()=>$('.message').trigger('click'), 2000);
        return false;
    });

    $('.message').on('click', function(){
        Majiang.UI.Util.fadeOut($(this));
        return false;
    });
});

})();

/******/ })()
;
//# sourceMappingURL=data:application/json;charset=utf-8;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoicnVsZS0yLjUuMy5qcyIsIm1hcHBpbmdzIjoiOzs7Ozs7Ozs7Ozs7Ozs7O1VBQUE7VUFDQTs7VUFFQTtVQUNBO1VBQ0E7VUFDQTtVQUNBO1VBQ0E7VUFDQTtVQUNBO1VBQ0E7VUFDQTtVQUNBO1VBQ0E7VUFDQTs7VUFFQTtVQUNBO1VBQ0E7VUFDQTtVQUNBO1VBQ0E7VUFDQTtVQUNBOztVQUVBO1VBQ0E7VUFDQTs7Ozs7Ozs7QUM1QkE7QUFDQTtBQUNBO0FBQ0E7QUFDQTtBQUNBO0FBQ0E7QUFDYTs7QUFFYixlQUFlLG1CQUFPLENBQUMsaURBQWtCOztBQUV6Qzs7QUFFQTs7QUFFQTs7QUFFQTtBQUNBO0FBQ0E7QUFDQSw0QkFBNEIsT0FBTztBQUNuQztBQUNBO0FBQ0E7QUFDQTtBQUNBO0FBQ0E7QUFDQTtBQUNBO0FBQ0E7QUFDQTs7QUFFQSw2QkFBNkIsSUFBSTtBQUNqQyw2QkFBNkIsSUFBSTtBQUNqQztBQUNBO0FBQ0E7QUFDQTtBQUNBO0FBQ0E7QUFDQTtBQUNBO0FBQ0EseUJBQXlCLElBQUk7QUFDN0I7O0FBRUE7QUFDQTtBQUNBOztBQUVBO0FBQ0E7O0FBRUE7O0FBRUE7O0FBRUE7O0FBRUE7QUFDQSw0QkFBNEIsT0FBTztBQUNuQztBQUNBO0FBQ0E7QUFDQTtBQUNBO0FBQ0E7QUFDQTtBQUNBO0FBQ0E7QUFDQTs7QUFFQSw2QkFBNkIsSUFBSTtBQUNqQywyQ0FBMkMsSUFBSTtBQUMvQyxpQ0FBaUMsSUFBSTtBQUNyQztBQUNBO0FBQ0E7QUFDQSxrQ0FBa0MsSUFBSTtBQUN0Qyx5Q0FBeUMsSUFBSTtBQUM3QztBQUNBO0FBQ0EsMkNBQTJDLElBQUk7QUFDL0M7QUFDQTtBQUNBO0FBQ0E7O0FBRUE7QUFDQTtBQUNBO0FBQ0E7QUFDQTtBQUNBO0FBQ0E7QUFDQTs7QUFFQTtBQUNBO0FBQ0E7QUFDQSxvQkFBb0IsT0FBTztBQUMzQjtBQUNBO0FBQ0E7QUFDQTtBQUNBO0FBQ0E7O0FBRUE7QUFDQTtBQUNBO0FBQ0E7QUFDQTtBQUNBO0FBQ0E7QUFDQTtBQUNBOztBQUVBO0FBQ0E7QUFDQTtBQUNBO0FBQ0E7QUFDQTtBQUNBO0FBQ0E7O0FBRUE7QUFDQTtBQUNBO0FBQ0E7QUFDQTtBQUNBO0FBQ0E7QUFDQTs7QUFFQTtBQUNBO0FBQ0E7QUFDQTtBQUNBO0FBQ0EsS0FBSztBQUNMOztBQUVBOztBQUVBO0FBQ0E7QUFDQTtBQUNBO0FBQ0E7QUFDQTtBQUNBO0FBQ0E7O0FBRUE7QUFDQSx3RUFBd0U7QUFDeEU7O0FBRUE7QUFDQTtBQUNBO0FBQ0EsS0FBSztBQUNMO0FBQ0E7QUFDQTtBQUNBO0FBQ0E7QUFDQSxLQUFLO0FBQ0w7QUFDQTtBQUNBOztBQUVBO0FBQ0E7QUFDQTtBQUNBLDBFQUEwRTtBQUMxRSx1Q0FBdUM7QUFDdkM7QUFDQTtBQUNBLEtBQUs7O0FBRUw7O0FBRUE7QUFDQTtBQUNBO0FBQ0E7QUFDQTtBQUNBOztBQUVBO0FBQ0E7QUFDQTtBQUNBO0FBQ0E7QUFDQTtBQUNBLEtBQUs7O0FBRUw7QUFDQTtBQUNBO0FBQ0EsS0FBSztBQUNMLENBQUMiLCJzb3VyY2VzIjpbIndlYnBhY2s6Ly9tYWppYW5nL3dlYnBhY2svYm9vdHN0cmFwIiwid2VicGFjazovL21hamlhbmcvLi9zcmMvanMvcnVsZS5qcyJdLCJzb3VyY2VzQ29udGVudCI6WyIvLyBUaGUgbW9kdWxlIGNhY2hlXG52YXIgX193ZWJwYWNrX21vZHVsZV9jYWNoZV9fID0ge307XG5cbi8vIFRoZSByZXF1aXJlIGZ1bmN0aW9uXG5mdW5jdGlvbiBfX3dlYnBhY2tfcmVxdWlyZV9fKG1vZHVsZUlkKSB7XG5cdC8vIENoZWNrIGlmIG1vZHVsZSBpcyBpbiBjYWNoZVxuXHR2YXIgY2FjaGVkTW9kdWxlID0gX193ZWJwYWNrX21vZHVsZV9jYWNoZV9fW21vZHVsZUlkXTtcblx0aWYgKGNhY2hlZE1vZHVsZSAhPT0gdW5kZWZpbmVkKSB7XG5cdFx0cmV0dXJuIGNhY2hlZE1vZHVsZS5leHBvcnRzO1xuXHR9XG5cdC8vIENyZWF0ZSBhIG5ldyBtb2R1bGUgKGFuZCBwdXQgaXQgaW50byB0aGUgY2FjaGUpXG5cdHZhciBtb2R1bGUgPSBfX3dlYnBhY2tfbW9kdWxlX2NhY2hlX19bbW9kdWxlSWRdID0ge1xuXHRcdC8vIG5vIG1vZHVsZS5pZCBuZWVkZWRcblx0XHQvLyBubyBtb2R1bGUubG9hZGVkIG5lZWRlZFxuXHRcdGV4cG9ydHM6IHt9XG5cdH07XG5cblx0Ly8gRXhlY3V0ZSB0aGUgbW9kdWxlIGZ1bmN0aW9uXG5cdGlmICghKG1vZHVsZUlkIGluIF9fd2VicGFja19tb2R1bGVzX18pKSB7XG5cdFx0ZGVsZXRlIF9fd2VicGFja19tb2R1bGVfY2FjaGVfX1ttb2R1bGVJZF07XG5cdFx0dmFyIGUgPSBuZXcgRXJyb3IoXCJDYW5ub3QgZmluZCBtb2R1bGUgJ1wiICsgbW9kdWxlSWQgKyBcIidcIik7XG5cdFx0ZS5jb2RlID0gJ01PRFVMRV9OT1RfRk9VTkQnO1xuXHRcdHRocm93IGU7XG5cdH1cblx0X193ZWJwYWNrX21vZHVsZXNfX1ttb2R1bGVJZF0obW9kdWxlLCBtb2R1bGUuZXhwb3J0cywgX193ZWJwYWNrX3JlcXVpcmVfXyk7XG5cblx0Ly8gUmV0dXJuIHRoZSBleHBvcnRzIG9mIHRoZSBtb2R1bGVcblx0cmV0dXJuIG1vZHVsZS5leHBvcnRzO1xufVxuXG4iLCIvKiFcbiAqICDpm7vohLPpurvlsIY6IOODq+ODvOODq+ioreWumiB2Mi41LjNcbiAqXG4gKiAgQ29weXJpZ2h0KEMpIDIwMTcgU2F0b3NoaSBLb2JheWFzaGlcbiAqICBSZWxlYXNlZCB1bmRlciB0aGUgTUlUIGxpY2Vuc2VcbiAqICBodHRwczovL2dpdGh1Yi5jb20va29iYWxhYi9NYWppYW5nL2Jsb2IvbWFzdGVyL0xJQ0VOU0VcbiAqL1xuXCJ1c2Ugc3RyaWN0XCI7XG5cbmNvbnN0IHByZXNldCA9IHJlcXVpcmUoJy4vY29uZi9ydWxlLmpzb24nKTtcblxuZnVuY3Rpb24gc2V0X2Zvcm0ocnVsZSkge1xuXG4gICAgZm9yIChsZXQga2V5IG9mIE9iamVjdC5rZXlzKHJ1bGUpKSB7XG5cbiAgICAgICAgbGV0IHZhbHVlO1xuXG4gICAgICAgIGlmIChrZXkgPT0gJ+mghuS9jeeCuScpIHtcbiAgICAgICAgICAgIHZhbHVlID0gcnVsZVtrZXldLmZpbmQobj0+bi5tYXRjaCgvXFwuLykpID8gMCA6IDE7XG4gICAgICAgICAgICAkKCdpbnB1dFtuYW1lPVwi6aCG5L2N54K55Zub5o2o5LqU5YWl44GC44KKXCJdJykudmFsKFt2YWx1ZV0pO1xuICAgICAgICAgICAgZm9yIChsZXQgaSA9IDE7IGkgPCA0OyBpKyspIHtcbiAgICAgICAgICAgICAgICAkKCdpbnB1dFtuYW1lPVwi6aCG5L2N54K5XCJdJykuZXEoaSkudmFsKHJ1bGVba2V5XVtpXSk7XG4gICAgICAgICAgICB9XG4gICAgICAgICAgICBjb250aW51ZTtcbiAgICAgICAgfVxuICAgICAgICBpZiAoa2V5ID09ICfotaTniYwnKSB7XG4gICAgICAgICAgICAkKCdpbnB1dFtuYW1lPVwi6LWk54mMXCJdJykuZXEoMCkudmFsKHJ1bGVba2V5XS5tKTtcbiAgICAgICAgICAgICQoJ2lucHV0W25hbWU9XCLotaTniYxcIl0nKS5lcSgxKS52YWwocnVsZVtrZXldLnApO1xuICAgICAgICAgICAgJCgnaW5wdXRbbmFtZT1cIui1pOeJjFwiXScpLmVxKDIpLnZhbChydWxlW2tleV0ucyk7XG4gICAgICAgICAgICBjb250aW51ZTtcbiAgICAgICAgfVxuXG4gICAgICAgIGlmICgkKGBpbnB1dFtuYW1lPVwiJHtrZXl9XCJdYCkuYXR0cigndHlwZScpID09ICdyYWRpbycgfHxcbiAgICAgICAgICAgICQoYGlucHV0W25hbWU9XCIke2tleX1cIl1gKS5hdHRyKCd0eXBlJykgPT0gJ2NoZWNrYm94JylcbiAgICAgICAge1xuICAgICAgICAgICAgdmFsdWUgPSBydWxlW2tleV0gPT09IGZhbHNlID8gWzBdXG4gICAgICAgICAgICAgICAgICA6IHJ1bGVba2V5XSA9PT0gdHJ1ZSAgPyBbMV1cbiAgICAgICAgICAgICAgICAgIDogICAgICAgICAgICAgICAgICAgICAgIFtydWxlW2tleV1dO1xuICAgICAgICB9XG4gICAgICAgIGVsc2Uge1xuICAgICAgICAgICAgdmFsdWUgPSBydWxlW2tleV07XG4gICAgICAgIH1cbiAgICAgICAgJChgaW5wdXRbbmFtZT1cIiR7a2V5fVwiXWApLnZhbCh2YWx1ZSk7XG4gICAgfVxuXG4gICAgcmVwYWlyX3BvaW50KCk7XG4gICAgcmVwYWlyX2dhbmcoKTtcbiAgICByZXBhaXJfZGFtYW5ndWFuKCk7XG5cbiAgICBNYWppYW5nLlVJLlV0aWwuZmFkZUluKCQoJ2Zvcm0nKSk7XG59XG5cbmZ1bmN0aW9uIGdldF9mb3JtKCkge1xuXG4gICAgbGV0IHJ1bGUgPSBNYWppYW5nLnJ1bGUoKTtcblxuICAgIGZvciAobGV0IGtleSBvZiBPYmplY3Qua2V5cyhydWxlKSkge1xuXG4gICAgICAgIGlmIChrZXkgPT0gJ+mghuS9jeeCuScpIHtcbiAgICAgICAgICAgIGZvciAobGV0IGkgPSAwOyBpIDwgNDsgaSsrKSB7XG4gICAgICAgICAgICAgICAgcnVsZVtrZXldW2ldID0gJCgnaW5wdXRbbmFtZT1cIumghuS9jeeCuVwiXScpLmVxKGkpLnZhbCgpO1xuICAgICAgICAgICAgfVxuICAgICAgICAgICAgY29udGludWU7XG4gICAgICAgIH1cbiAgICAgICAgaWYgKGtleSA9PSAn6LWk54mMJykge1xuICAgICAgICAgICAgcnVsZVtrZXldLm0gPSArICQoJ2lucHV0W25hbWU9XCLotaTniYxcIl0nKS5lcSgwKS52YWwoKTtcbiAgICAgICAgICAgIHJ1bGVba2V5XS5wID0gKyAkKCdpbnB1dFtuYW1lPVwi6LWk54mMXCJdJykuZXEoMSkudmFsKCk7XG4gICAgICAgICAgICBydWxlW2tleV0ucyA9ICsgJCgnaW5wdXRbbmFtZT1cIui1pOeJjFwiXScpLmVxKDIpLnZhbCgpO1xuICAgICAgICAgICAgY29udGludWU7XG4gICAgICAgIH1cblxuICAgICAgICBpZiAoJChgaW5wdXRbbmFtZT1cIiR7a2V5fVwiXWApLmF0dHIoJ3R5cGUnKSA9PSAncmFkaW8nKSB7XG4gICAgICAgICAgICBydWxlW2tleV0gPSArICQoYGlucHV0W25hbWU9XCIke2tleX1cIl06Y2hlY2tlZGApLnZhbCgpO1xuICAgICAgICAgICAgaWYgKCQoYGlucHV0W25hbWU9XCIke2tleX1cIl1gKS5sZW5ndGggPT0gMikge1xuICAgICAgICAgICAgICAgIHJ1bGVba2V5XSA9IHJ1bGVba2V5XSAhPSAwO1xuICAgICAgICAgICAgfVxuICAgICAgICB9XG4gICAgICAgIGVsc2UgaWYgKCQoYGlucHV0W25hbWU9XCIke2tleX1cIl1gKS5hdHRyKCd0eXBlJykgPT0gJ2NoZWNrYm94Jykge1xuICAgICAgICAgICAgcnVsZVtrZXldID0gJChgaW5wdXRbbmFtZT1cIiR7a2V5fVwiXWApLnByb3AoJ2NoZWNrZWQnKTtcbiAgICAgICAgfVxuICAgICAgICBlbHNlIHtcbiAgICAgICAgICAgIHJ1bGVba2V5XSA9ICsgJChgaW5wdXRbbmFtZT1cIiR7a2V5fVwiXWApLnZhbCgpO1xuICAgICAgICB9XG4gICAgfVxuICAgIHJldHVybiBydWxlO1xufVxuXG5mdW5jdGlvbiByb3VuZF9wb2ludChwLCByb3VuZCkge1xuICAgIHAgPSBpc05hTihwKSA/ICcwJ1xuICAgICAgOiArIHAgPiAwICA/ICcrJyArICgrIHApXG4gICAgICA6ICAgICAgICAgICAgJycgICsgKCsgcCk7XG4gICAgaWYgKHJvdW5kKSBwLnJlcGxhY2UoL1xcLlxcZCokLywnJyk7XG4gICAgZWxzZSAgICAgICBwID0gISBwLm1hdGNoKC9cXC4vKSA/IHAgKyAnLjAnIDogcDtcbiAgICByZXR1cm4gcDtcbn1cblxuZnVuY3Rpb24gcmVwYWlyX3BvaW50KCkge1xuICAgIGxldCByb3VuZCA9ICQoJ2lucHV0W25hbWU9XCLpoIbkvY3ngrnlm5vmjajkupTlhaXjgYLjgopcIl0nKS5wcm9wKCdjaGVja2VkJyk7XG4gICAgbGV0IHN1bSA9IDA7XG4gICAgZm9yIChsZXQgaSA9IDE7IGkgPCA0OyBpKyspIHtcbiAgICAgICAgbGV0IHAgPSArICQoJ2lucHV0W25hbWU9XCLpoIbkvY3ngrlcIl0nKS5lcShpKS52YWwoKTtcbiAgICAgICAgc3VtICs9IHA7XG4gICAgICAgICQoJ2lucHV0W25hbWU9XCLpoIbkvY3ngrlcIl0nKS5lcShpKS52YWwocm91bmRfcG9pbnQocCwgcm91bmQpKVxuICAgIH1cbiAgICAkKCdpbnB1dFtuYW1lPVwi6aCG5L2N54K5XCJdJykuZXEoMCkudmFsKHJvdW5kX3BvaW50KC1zdW0sIHJvdW5kKSlcbn1cblxuZnVuY3Rpb24gcmVwYWlyX2dhbmcoKSB7XG4gICAgaWYgKCsgJCgnaW5wdXRbbmFtZT1cIuijj+ODieODqeOBguOCilwiXTpjaGVja2VkJykudmFsKClcbiAgICAgICAgJiYgKyAkKCdpbnB1dFtuYW1lPVwi44Kr44Oz44OJ44Op44GC44KKXCJdOmNoZWNrZWQnKS52YWwoKSlcbiAgICB7XG4gICAgICAgICQoJ2lucHV0W25hbWU9XCLjgqvjg7Poo4/jgYLjgopcIl0nKS5wcm9wKCdkaXNhYmxlZCcsIGZhbHNlKTtcbiAgICB9XG4gICAgZWxzZSB7XG4gICAgICAgICQoJ2lucHV0W25hbWU9XCLjgqvjg7Poo4/jgYLjgopcIl0nKS5wcm9wKCdkaXNhYmxlZCcsIHRydWUpLnZhbChbMF0pO1xuICAgIH1cblxuICAgIGlmICgrICQoJ2lucHV0W25hbWU9XCLjgqvjg7Pjg4njg6njgYLjgopcIl06Y2hlY2tlZCcpLnZhbCgpKSB7XG4gICAgICAgICQoJ2lucHV0W25hbWU9XCLjgqvjg7Pjg4njg6nlvozkuZfjgZtcIl0nKS5wcm9wKCdkaXNhYmxlZCcsIGZhbHNlKTtcbiAgICB9XG4gICAgZWxzZSB7XG4gICAgICAgICQoJ2lucHV0W25hbWU9XCLjgqvjg7Pjg4njg6nlvozkuZfjgZtcIl0nKS5wcm9wKCdkaXNhYmxlZCcsIHRydWUpXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgLnByb3AoJ2NoZWNrZWQnLCBmYWxzZSk7XG4gICAgfVxufVxuXG5mdW5jdGlvbiByZXBhaXJfZGFtYW5ndWFuKCkge1xuICAgIGlmICgrICQoJ2lucHV0W25hbWU9XCLlvbnmuoDjga7opIflkIjjgYLjgopcIl06Y2hlY2tlZCcpLnZhbCgpKSB7XG4gICAgICAgICQoJ2lucHV0W25hbWU9XCLjg4Djg5bjg6vlvbnmuoDjgYLjgopcIl0nKS5wcm9wKCdkaXNhYmxlZCcsIGZhbHNlKTtcbiAgICB9XG4gICAgZWxzZSB7XG4gICAgICAgICQoJ2lucHV0W25hbWU9XCLjg4Djg5bjg6vlvbnmuoDjgYLjgopcIl0nKS5wcm9wKCdkaXNhYmxlZCcsIHRydWUpLnZhbChbMF0pO1xuICAgIH1cbn1cblxuZnVuY3Rpb24gdW5zYXZlZCgpIHtcbiAgICAkKHdpbmRvdykub24oJ2JlZm9yZXVubG9hZCcsIChldik9PntcbiAgICAgICAgY29uc3QgbWVzc2FnZSA9ICfjg5rjg7zjgrjjgpLpm6Ljgozjgb7jgZnjgYzjgojjgo3jgZfjgYTjgafjgZnjgYvvvJ8nO1xuICAgICAgICBldi5yZXR1cm5WYWx1ZSA9IG1lc3NhZ2U7XG4gICAgICAgIHJldHVybiBtZXNzYWdlO1xuICAgIH0pO1xufVxuXG4kKGZ1bmN0aW9uKCl7XG5cbiAgICBmb3IgKGxldCBrZXkgb2YgT2JqZWN0LmtleXMocHJlc2V0KSkge1xuICAgICAgICAkKCdzZWxlY3RbbmFtZT1cIuODl+ODquOCu+ODg+ODiFwiXScpLmFwcGVuZCgkKCc8b3B0aW9uPicpLnZhbChrZXkpLnRleHQoa2V5KSk7XG4gICAgfVxuICAgIGlmIChsb2NhbFN0b3JhZ2UuZ2V0SXRlbSgnTWFqaWFuZy5ydWxlJykpIHtcbiAgICAgICAgJCgnc2VsZWN0W25hbWU9XCLjg5fjg6rjgrvjg4Pjg4hcIl0nKS5hcHBlbmQoJCgnPG9wdGlvbj4nKVxuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgLnZhbCgnLScpLnRleHQoJ+OCq+OCueOCv+ODoOODq+ODvOODqycpKTtcbiAgICAgICAgJCgnc2VsZWN0W25hbWU9XCLjg5fjg6rjgrvjg4Pjg4hcIl0nKS52YWwoJy0nKTtcbiAgICB9XG5cbiAgICBsZXQgcnVsZSA9IE1hamlhbmcucnVsZShcbiAgICAgICAgICAgICAgICAgICAgSlNPTi5wYXJzZShsb2NhbFN0b3JhZ2UuZ2V0SXRlbSgnTWFqaWFuZy5ydWxlJyl8fCd7fScpKTtcbiAgICBzZXRfZm9ybShydWxlKTtcblxuICAgICQoJ2lucHV0W25hbWU9XCLphY3ntabljp/ngrlcIl0nKS5vbignY2hhbmdlJywgZnVuY3Rpb24oKXtcbiAgICAgICAgbGV0IHAgPSAkKHRoaXMpLnZhbCgpO1xuICAgICAgICBpZiAoaXNOYU4ocCkgfHwgcCA8PSAwKSAkKHRoaXMpLnZhbChNYWppYW5nLnJ1bGUoKVsn6YWN57Wm5Y6f54K5J10pO1xuICAgIH0pO1xuICAgICQoJ2lucHV0W25hbWU9XCLpoIbkvY3ngrlcIl0nKS5vbignY2hhbmdlJywgcmVwYWlyX3BvaW50KTtcbiAgICAkKCdpbnB1dFtuYW1lPVwi6aCG5L2N54K55Zub5o2o5LqU5YWl44GC44KKXCJdJykub24oJ2NoYW5nZScsIHJlcGFpcl9wb2ludCk7XG4gICAgJCgnaW5wdXRbbmFtZT1cIui1pOeJjFwiXScpLm9uKCdjaGFuZ2UnLCBmdW5jdGlvbigpe1xuICAgICAgICBsZXQgbiA9ICQodGhpcykudmFsKCk7XG4gICAgICAgIGlmIChpc05hTihuKSB8fCBuIDwgMCB8fCA0IDwgbikgJCh0aGlzKS52YWwoMCk7XG4gICAgfSk7XG4gICAgJCgnaW5wdXRbbmFtZT1cIuijj+ODieODqeOBguOCilwiXScpLm9uKCdjaGFuZ2UnLCByZXBhaXJfZ2FuZyk7XG4gICAgJCgnaW5wdXRbbmFtZT1cIuOCq+ODs+ODieODqeOBguOCilwiXScpLm9uKCdjaGFuZ2UnLCByZXBhaXJfZ2FuZyk7XG4gICAgJCgnaW5wdXRbbmFtZT1cIuW9uea6gOOBruikh+WQiOOBguOCilwiXScpLm9uKCdjaGFuZ2UnLCByZXBhaXJfZGFtYW5ndWFuKTtcblxuICAgICQoJ2lucHV0W25hbWU9XCLjg5fjg6rjgrvjg4Pjg4hcIl0nKS5vbignY2xpY2snLCAoKT0+e1xuICAgICAgICBsZXQga2V5ID0gJCgnc2VsZWN0W25hbWU9XCLjg5fjg6rjgrvjg4Pjg4hcIl0nKS52YWwoKTtcbiAgICAgICAgc2V0X2Zvcm0oTWFqaWFuZy5ydWxlKGtleSA9PSAnLSdcbiAgICAgICAgICAgICAgICAgICAgPyBKU09OLnBhcnNlKGxvY2FsU3RvcmFnZS5nZXRJdGVtKCdNYWppYW5nLnJ1bGUnKXx8J3t9JylcbiAgICAgICAgICAgICAgICAgICAgOiBwcmVzZXRba2V5XSB8fCB7fSkpO1xuICAgICAgICB1bnNhdmVkKCk7XG4gICAgICAgIHJldHVybiBmYWxzZTtcbiAgICB9KTtcblxuICAgICQoJ2Zvcm0gaW5wdXQnKS5vbignY2hhbmdlJywgdW5zYXZlZCk7XG5cbiAgICAkKCdmb3JtJykub24oJ3N1Ym1pdCcsICgpPT57XG4gICAgICAgIGlmICghIGxvY2FsU3RvcmFnZS5nZXRJdGVtKCdNYWppYW5nLnJ1bGUnKSkge1xuICAgICAgICAgICAgJCgnc2VsZWN0W25hbWU9XCLjg5fjg6rjgrvjg4Pjg4hcIl0nKS5hcHBlbmQoJCgnPG9wdGlvbj4nKVxuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIC52YWwoJy0nKS50ZXh0KCfjgqvjgrnjgr/jg6Djg6vjg7zjg6snKSk7XG4gICAgICAgIH1cbiAgICAgICAgbG9jYWxTdG9yYWdlLnNldEl0ZW0oJ01hamlhbmcucnVsZScsIEpTT04uc3RyaW5naWZ5KGdldF9mb3JtKCkpKTtcblxuICAgICAgICAkKHdpbmRvdykub2ZmKCdiZWZvcmV1bmxvYWQnKTtcbiAgICAgICAgJCgnc2VsZWN0W25hbWU9XCLjg5fjg6rjgrvjg4Pjg4hcIl0nKS52YWwoJy0nKTtcbiAgICAgICAgTWFqaWFuZy5VSS5VdGlsLmZhZGVJbigkKCdmb3JtJykpO1xuICAgICAgICBNYWppYW5nLlVJLlV0aWwuZmFkZUluKCQoJy5tZXNzYWdlJykpO1xuICAgICAgICBzZXRUaW1lb3V0KCgpPT4kKCcubWVzc2FnZScpLnRyaWdnZXIoJ2NsaWNrJyksIDIwMDApO1xuICAgICAgICByZXR1cm4gZmFsc2U7XG4gICAgfSk7XG5cbiAgICAkKCcubWVzc2FnZScpLm9uKCdjbGljaycsIGZ1bmN0aW9uKCl7XG4gICAgICAgIE1hamlhbmcuVUkuVXRpbC5mYWRlT3V0KCQodGhpcykpO1xuICAgICAgICByZXR1cm4gZmFsc2U7XG4gICAgfSk7XG59KTtcbiJdLCJuYW1lcyI6W10sInNvdXJjZVJvb3QiOiIifQ==
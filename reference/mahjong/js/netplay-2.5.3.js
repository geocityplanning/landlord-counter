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
/*!***************************!*\
  !*** ./src/js/netplay.js ***!
  \***************************/
/*!
 *  電脳麻将: ネット対戦 v2.5.3
 *
 *  Copyright(C) 2017 Satoshi Kobayashi
 *  Released under the MIT license
 *  https://github.com/kobalab/Majiang/blob/master/LICENSE
 */


const { hide, show, fadeIn, scale,
        setSelector, clearSelector  } = Majiang.UI.Util;

const preset = __webpack_require__(/*! ./conf/rule.json */ "./src/js/conf/rule.json");

const base = location.pathname.replace(/\/[^\/]*?$/,'');

let loaded;

$(function(){

    const pai   = Majiang.UI.pai($('#loaddata'));
    const audio = Majiang.UI.audio($('#loaddata'));

    const analyzer = (kaiju)=>{
        $('body').addClass('analyzer');
        return new Majiang.UI.Analyzer($('#board > .analyzer'), kaiju, pai,
                                        ()=>$('body').removeClass('analyzer'));
    };
    const viewer = (paipu)=>{
        $('#board .controller').addClass('paipu')
        $('body').attr('class','board');
        scale($('#board'), $('#space'));
        return new Majiang.UI.Paipu(
                        $('#board'), paipu, pai, audio, 'Majiang.pref',
                        ()=>fadeIn($('body').attr('class','file')),
                        analyzer);
    };
    const stat = (paipu_list)=>{
        fadeIn($('body').attr('class','stat'));
        return new Majiang.UI.PaipuStat($('#stat'), paipu_list,
                        ()=>fadeIn($('body').attr('class','file')));
    };
    const file = new Majiang.UI.PaipuFile($('#file'), 'Majiang.netplay',
                                            viewer, stat);
    let sock, myuid;

    function init() {

        sock = io('/', { path: `${base}/server/socket.io/`});

        $(window).on('pagehide', ()=>sock.disconnect());
        $(window).on('pageshow', ()=>sock.connect());

        sock.on('HELLO', hello);
        sock.on('ROOM', room);
        sock.on('START', start);
        sock.on('END', end);
        sock.on('ERROR', file.error);
        sock.on('disconnect', ()=>hide($('#file .netplay form.room')));

        hide($('#title .loading'));
    }

    function hello(user) {
        if (! user) {
            $('body').attr('class','title');
            show($('#title .login'));
            return;
        }
        myuid = user.uid;
        show($('#file .netplay form'));
        fadeIn($('body').attr('class','file'));
        if (user.icon)
            $('#file .netplay img').attr('src', user.icon)
                                   .attr('title', user.uid);
        $('#file .netplay .name').text(user.name);
        file.redraw();
    }

    let row, src;

    function room(msg) {
        if (! row) {
            row = $('#room .user').eq(0);
            src = $('img', row).attr('src');
        }
        $('body').attr('class','room');
        $('#room input[name="room_no"]').val(msg.room_no);
        $('#room .room').empty();
        for (let user of msg.user) {
            let r = row.clone();
            if (user.icon) $('img', r).attr('src', user.icon)
                                      .attr('title', user.uid);
            else           $('img', r).attr('src', src);
            $('.name', r).text(user.name);
            if (msg.user[0].uid == myuid || user.uid == myuid )
                show($('input[name="quit"]', r).on('click', ()=> {
                        sock.emit('ROOM', msg.room_no, user.uid);
                        return false;
                    }));
            if (user.offline) r.addClass('offline');
            else              r.removeClass('offline');
            $('#room .room').append(r);
        }
        if (msg.user[0].uid == myuid) {
            show($('#room select[name="rule"]'));
            show($('#room input[name="timer"]'));
            show($('#room input[type="submit"]'));
        }
        else {
            hide($('#room select[name="rule"]'));
            hide($('#room input[name="timer"]'));
            hide($('#room input[type="submit"]'));
        }
    }

    function start() {

        const player = new Majiang.UI.Player($('#board'), pai, audio);
        player.view  = new Majiang.UI.Board($('#board .board'), pai, audio,
                                                player.model);

        const gameCtl = new Majiang.UI.GameCtl($('#board'), 'Majiang.pref',
                                                null, player, player._view);
        gameCtl._view.no_player_name = false;

        let players = [];

        $('#board .controller').removeClass('paipu')
        $('body').attr('class','board');
        scale($('#board'), $('#space'));
        let seq = 0;
        sock.removeAllListeners('GAME');
        sock.on('GAME', (msg)=>{
            if (msg.players) {
                players = msg.players;
            }
            else if (msg.say) {
                player._view.say(msg.say.name, msg.say.l);
            }
            else if (msg.seq) {
                if (seq && msg.seq != seq) location.reload();
                player.action(msg, (reply = {})=>{
                    reply.seq = msg.seq;
                    sock.emit('GAME', reply);
                    seq = msg.seq + 1;
                });
                if (msg.jieju) {
                    file.add(msg.jieju, 10);
                }
            }
            else {
                player.action(msg);
                if (msg.kaiju && msg.kaiju.log) {
                    let log = msg.kaiju.log.pop();
                    for (let data of log) {
                        player.action(data);
                    }
                }
            }
            player._view.players(players);
        });
    }

    function end(paipu) {
        sock.removeAllListeners('GAME');
        fadeIn($('body').attr('class','file'));
        file.redraw();
        $('#file input[name="room_no"]').val('');
    }

    for (let key of Object.keys(preset)) {
        $('select[name="rule"]').append($('<option>').val(key).text(key));
    }
    if (localStorage.getItem('Majiang.rule')) {
        $('select[name="rule"]').append($('<option>')
                                .val('-').text('カスタムルール'));
    }

    $('#file form.room').on('submit', (ev)=>{
        let room = $('input[name="room_no"]', $(ev.target)).val();
        sock.emit('ROOM', room);
        return false;
    });
    $('#room form').on('submit', (ev)=>{
        let room = $('input[name="room_no"]', $(ev.target)).val();

        let rule = $('select[name="rule"]', $(ev.target)).val();
        rule = ! rule      ? {}
             : rule == '-' ? JSON.parse(
                                localStorage.getItem('Majiang.rule')||'{}')
             :               preset[rule];
        rule = Majiang.rule(rule);

        let timer = $('input[name="timer"]', $(ev.target)).val();
        timer = timer.match(/(\d+)/g);
        if (timer) timer = timer.map(t=>+t);

        sock.emit('START', room, rule, timer);
        return false;
    });

    $(window).on('resize', ()=>scale($('#board'), $('#space')));

    $(window).on('load', ()=>setTimeout(init, 500));
    if (loaded) $(window).trigger('load');

    $('#title .login form').each(function(){
        let method = $(this).attr('method')
        let url    = $(this).attr('action');
        fetch(url, { method: method, redirect: 'manual' }).then(res =>{
            if (res.status == 404) hide($(this));
        });
    });
});
$(window).on('load', ()=> loaded = true);

})();

/******/ })()
;
//# sourceMappingURL=data:application/json;charset=utf-8;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoibmV0cGxheS0yLjUuMy5qcyIsIm1hcHBpbmdzIjoiOzs7Ozs7Ozs7Ozs7Ozs7O1VBQUE7VUFDQTs7VUFFQTtVQUNBO1VBQ0E7VUFDQTtVQUNBO1VBQ0E7VUFDQTtVQUNBO1VBQ0E7VUFDQTtVQUNBO1VBQ0E7VUFDQTs7VUFFQTtVQUNBO1VBQ0E7VUFDQTtVQUNBO1VBQ0E7VUFDQTtVQUNBOztVQUVBO1VBQ0E7VUFDQTs7Ozs7Ozs7QUM1QkE7QUFDQTtBQUNBO0FBQ0E7QUFDQTtBQUNBO0FBQ0E7QUFDYTs7QUFFYixRQUFRO0FBQ1Isc0NBQXNDOztBQUV0QyxlQUFlLG1CQUFPLENBQUMsaURBQWtCOztBQUV6Qzs7QUFFQTs7QUFFQTs7QUFFQTtBQUNBOztBQUVBO0FBQ0E7QUFDQTtBQUNBO0FBQ0E7QUFDQTtBQUNBO0FBQ0E7QUFDQTtBQUNBO0FBQ0E7QUFDQTtBQUNBO0FBQ0E7QUFDQTtBQUNBO0FBQ0E7QUFDQTtBQUNBO0FBQ0E7QUFDQTtBQUNBOztBQUVBOztBQUVBLHlCQUF5QixTQUFTLEtBQUssb0JBQW9COztBQUUzRDtBQUNBOztBQUVBO0FBQ0E7QUFDQTtBQUNBO0FBQ0E7QUFDQTs7QUFFQTtBQUNBOztBQUVBO0FBQ0E7QUFDQTtBQUNBO0FBQ0E7QUFDQTtBQUNBO0FBQ0E7QUFDQTtBQUNBO0FBQ0E7QUFDQTtBQUNBO0FBQ0E7QUFDQTs7QUFFQTs7QUFFQTtBQUNBO0FBQ0E7QUFDQTtBQUNBO0FBQ0E7QUFDQTtBQUNBO0FBQ0E7QUFDQTtBQUNBO0FBQ0E7QUFDQTtBQUNBO0FBQ0E7QUFDQTtBQUNBO0FBQ0E7QUFDQSxxQkFBcUI7QUFDckI7QUFDQTtBQUNBO0FBQ0E7QUFDQTtBQUNBO0FBQ0E7QUFDQTtBQUNBO0FBQ0E7QUFDQTtBQUNBO0FBQ0E7QUFDQTtBQUNBOztBQUVBOztBQUVBO0FBQ0E7QUFDQTs7QUFFQTtBQUNBO0FBQ0E7O0FBRUE7O0FBRUE7QUFDQTtBQUNBO0FBQ0E7QUFDQTtBQUNBO0FBQ0E7QUFDQTtBQUNBO0FBQ0E7QUFDQTtBQUNBO0FBQ0E7QUFDQTtBQUNBLDhDQUE4QztBQUM5QztBQUNBO0FBQ0E7QUFDQSxpQkFBaUI7QUFDakI7QUFDQTtBQUNBO0FBQ0E7QUFDQTtBQUNBO0FBQ0E7QUFDQTtBQUNBO0FBQ0E7QUFDQTtBQUNBO0FBQ0E7QUFDQTtBQUNBLFNBQVM7QUFDVDs7QUFFQTtBQUNBO0FBQ0E7QUFDQTtBQUNBO0FBQ0E7O0FBRUE7QUFDQTtBQUNBO0FBQ0E7QUFDQTtBQUNBO0FBQ0E7O0FBRUE7QUFDQTtBQUNBO0FBQ0E7QUFDQSxLQUFLO0FBQ0w7QUFDQTs7QUFFQTtBQUNBO0FBQ0E7QUFDQSx5RUFBeUU7QUFDekU7QUFDQTs7QUFFQTtBQUNBO0FBQ0E7O0FBRUE7QUFDQTtBQUNBLEtBQUs7O0FBRUw7O0FBRUE7QUFDQTs7QUFFQTtBQUNBO0FBQ0E7QUFDQSxxQkFBcUIsb0NBQW9DO0FBQ3pEO0FBQ0EsU0FBUztBQUNULEtBQUs7QUFDTCxDQUFDO0FBQ0QiLCJzb3VyY2VzIjpbIndlYnBhY2s6Ly9tYWppYW5nL3dlYnBhY2svYm9vdHN0cmFwIiwid2VicGFjazovL21hamlhbmcvLi9zcmMvanMvbmV0cGxheS5qcyJdLCJzb3VyY2VzQ29udGVudCI6WyIvLyBUaGUgbW9kdWxlIGNhY2hlXG52YXIgX193ZWJwYWNrX21vZHVsZV9jYWNoZV9fID0ge307XG5cbi8vIFRoZSByZXF1aXJlIGZ1bmN0aW9uXG5mdW5jdGlvbiBfX3dlYnBhY2tfcmVxdWlyZV9fKG1vZHVsZUlkKSB7XG5cdC8vIENoZWNrIGlmIG1vZHVsZSBpcyBpbiBjYWNoZVxuXHR2YXIgY2FjaGVkTW9kdWxlID0gX193ZWJwYWNrX21vZHVsZV9jYWNoZV9fW21vZHVsZUlkXTtcblx0aWYgKGNhY2hlZE1vZHVsZSAhPT0gdW5kZWZpbmVkKSB7XG5cdFx0cmV0dXJuIGNhY2hlZE1vZHVsZS5leHBvcnRzO1xuXHR9XG5cdC8vIENyZWF0ZSBhIG5ldyBtb2R1bGUgKGFuZCBwdXQgaXQgaW50byB0aGUgY2FjaGUpXG5cdHZhciBtb2R1bGUgPSBfX3dlYnBhY2tfbW9kdWxlX2NhY2hlX19bbW9kdWxlSWRdID0ge1xuXHRcdC8vIG5vIG1vZHVsZS5pZCBuZWVkZWRcblx0XHQvLyBubyBtb2R1bGUubG9hZGVkIG5lZWRlZFxuXHRcdGV4cG9ydHM6IHt9XG5cdH07XG5cblx0Ly8gRXhlY3V0ZSB0aGUgbW9kdWxlIGZ1bmN0aW9uXG5cdGlmICghKG1vZHVsZUlkIGluIF9fd2VicGFja19tb2R1bGVzX18pKSB7XG5cdFx0ZGVsZXRlIF9fd2VicGFja19tb2R1bGVfY2FjaGVfX1ttb2R1bGVJZF07XG5cdFx0dmFyIGUgPSBuZXcgRXJyb3IoXCJDYW5ub3QgZmluZCBtb2R1bGUgJ1wiICsgbW9kdWxlSWQgKyBcIidcIik7XG5cdFx0ZS5jb2RlID0gJ01PRFVMRV9OT1RfRk9VTkQnO1xuXHRcdHRocm93IGU7XG5cdH1cblx0X193ZWJwYWNrX21vZHVsZXNfX1ttb2R1bGVJZF0obW9kdWxlLCBtb2R1bGUuZXhwb3J0cywgX193ZWJwYWNrX3JlcXVpcmVfXyk7XG5cblx0Ly8gUmV0dXJuIHRoZSBleHBvcnRzIG9mIHRoZSBtb2R1bGVcblx0cmV0dXJuIG1vZHVsZS5leHBvcnRzO1xufVxuXG4iLCIvKiFcbiAqICDpm7vohLPpurvlsIY6IOODjeODg+ODiOWvvuaIpiB2Mi41LjNcbiAqXG4gKiAgQ29weXJpZ2h0KEMpIDIwMTcgU2F0b3NoaSBLb2JheWFzaGlcbiAqICBSZWxlYXNlZCB1bmRlciB0aGUgTUlUIGxpY2Vuc2VcbiAqICBodHRwczovL2dpdGh1Yi5jb20va29iYWxhYi9NYWppYW5nL2Jsb2IvbWFzdGVyL0xJQ0VOU0VcbiAqL1xuXCJ1c2Ugc3RyaWN0XCI7XG5cbmNvbnN0IHsgaGlkZSwgc2hvdywgZmFkZUluLCBzY2FsZSxcbiAgICAgICAgc2V0U2VsZWN0b3IsIGNsZWFyU2VsZWN0b3IgIH0gPSBNYWppYW5nLlVJLlV0aWw7XG5cbmNvbnN0IHByZXNldCA9IHJlcXVpcmUoJy4vY29uZi9ydWxlLmpzb24nKTtcblxuY29uc3QgYmFzZSA9IGxvY2F0aW9uLnBhdGhuYW1lLnJlcGxhY2UoL1xcL1teXFwvXSo/JC8sJycpO1xuXG5sZXQgbG9hZGVkO1xuXG4kKGZ1bmN0aW9uKCl7XG5cbiAgICBjb25zdCBwYWkgICA9IE1hamlhbmcuVUkucGFpKCQoJyNsb2FkZGF0YScpKTtcbiAgICBjb25zdCBhdWRpbyA9IE1hamlhbmcuVUkuYXVkaW8oJCgnI2xvYWRkYXRhJykpO1xuXG4gICAgY29uc3QgYW5hbHl6ZXIgPSAoa2FpanUpPT57XG4gICAgICAgICQoJ2JvZHknKS5hZGRDbGFzcygnYW5hbHl6ZXInKTtcbiAgICAgICAgcmV0dXJuIG5ldyBNYWppYW5nLlVJLkFuYWx5emVyKCQoJyNib2FyZCA+IC5hbmFseXplcicpLCBrYWlqdSwgcGFpLFxuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICgpPT4kKCdib2R5JykucmVtb3ZlQ2xhc3MoJ2FuYWx5emVyJykpO1xuICAgIH07XG4gICAgY29uc3Qgdmlld2VyID0gKHBhaXB1KT0+e1xuICAgICAgICAkKCcjYm9hcmQgLmNvbnRyb2xsZXInKS5hZGRDbGFzcygncGFpcHUnKVxuICAgICAgICAkKCdib2R5JykuYXR0cignY2xhc3MnLCdib2FyZCcpO1xuICAgICAgICBzY2FsZSgkKCcjYm9hcmQnKSwgJCgnI3NwYWNlJykpO1xuICAgICAgICByZXR1cm4gbmV3IE1hamlhbmcuVUkuUGFpcHUoXG4gICAgICAgICAgICAgICAgICAgICAgICAkKCcjYm9hcmQnKSwgcGFpcHUsIHBhaSwgYXVkaW8sICdNYWppYW5nLnByZWYnLFxuICAgICAgICAgICAgICAgICAgICAgICAgKCk9PmZhZGVJbigkKCdib2R5JykuYXR0cignY2xhc3MnLCdmaWxlJykpLFxuICAgICAgICAgICAgICAgICAgICAgICAgYW5hbHl6ZXIpO1xuICAgIH07XG4gICAgY29uc3Qgc3RhdCA9IChwYWlwdV9saXN0KT0+e1xuICAgICAgICBmYWRlSW4oJCgnYm9keScpLmF0dHIoJ2NsYXNzJywnc3RhdCcpKTtcbiAgICAgICAgcmV0dXJuIG5ldyBNYWppYW5nLlVJLlBhaXB1U3RhdCgkKCcjc3RhdCcpLCBwYWlwdV9saXN0LFxuICAgICAgICAgICAgICAgICAgICAgICAgKCk9PmZhZGVJbigkKCdib2R5JykuYXR0cignY2xhc3MnLCdmaWxlJykpKTtcbiAgICB9O1xuICAgIGNvbnN0IGZpbGUgPSBuZXcgTWFqaWFuZy5VSS5QYWlwdUZpbGUoJCgnI2ZpbGUnKSwgJ01hamlhbmcubmV0cGxheScsXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIHZpZXdlciwgc3RhdCk7XG4gICAgbGV0IHNvY2ssIG15dWlkO1xuXG4gICAgZnVuY3Rpb24gaW5pdCgpIHtcblxuICAgICAgICBzb2NrID0gaW8oJy8nLCB7IHBhdGg6IGAke2Jhc2V9L3NlcnZlci9zb2NrZXQuaW8vYH0pO1xuXG4gICAgICAgICQod2luZG93KS5vbigncGFnZWhpZGUnLCAoKT0+c29jay5kaXNjb25uZWN0KCkpO1xuICAgICAgICAkKHdpbmRvdykub24oJ3BhZ2VzaG93JywgKCk9PnNvY2suY29ubmVjdCgpKTtcblxuICAgICAgICBzb2NrLm9uKCdIRUxMTycsIGhlbGxvKTtcbiAgICAgICAgc29jay5vbignUk9PTScsIHJvb20pO1xuICAgICAgICBzb2NrLm9uKCdTVEFSVCcsIHN0YXJ0KTtcbiAgICAgICAgc29jay5vbignRU5EJywgZW5kKTtcbiAgICAgICAgc29jay5vbignRVJST1InLCBmaWxlLmVycm9yKTtcbiAgICAgICAgc29jay5vbignZGlzY29ubmVjdCcsICgpPT5oaWRlKCQoJyNmaWxlIC5uZXRwbGF5IGZvcm0ucm9vbScpKSk7XG5cbiAgICAgICAgaGlkZSgkKCcjdGl0bGUgLmxvYWRpbmcnKSk7XG4gICAgfVxuXG4gICAgZnVuY3Rpb24gaGVsbG8odXNlcikge1xuICAgICAgICBpZiAoISB1c2VyKSB7XG4gICAgICAgICAgICAkKCdib2R5JykuYXR0cignY2xhc3MnLCd0aXRsZScpO1xuICAgICAgICAgICAgc2hvdygkKCcjdGl0bGUgLmxvZ2luJykpO1xuICAgICAgICAgICAgcmV0dXJuO1xuICAgICAgICB9XG4gICAgICAgIG15dWlkID0gdXNlci51aWQ7XG4gICAgICAgIHNob3coJCgnI2ZpbGUgLm5ldHBsYXkgZm9ybScpKTtcbiAgICAgICAgZmFkZUluKCQoJ2JvZHknKS5hdHRyKCdjbGFzcycsJ2ZpbGUnKSk7XG4gICAgICAgIGlmICh1c2VyLmljb24pXG4gICAgICAgICAgICAkKCcjZmlsZSAubmV0cGxheSBpbWcnKS5hdHRyKCdzcmMnLCB1c2VyLmljb24pXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIC5hdHRyKCd0aXRsZScsIHVzZXIudWlkKTtcbiAgICAgICAgJCgnI2ZpbGUgLm5ldHBsYXkgLm5hbWUnKS50ZXh0KHVzZXIubmFtZSk7XG4gICAgICAgIGZpbGUucmVkcmF3KCk7XG4gICAgfVxuXG4gICAgbGV0IHJvdywgc3JjO1xuXG4gICAgZnVuY3Rpb24gcm9vbShtc2cpIHtcbiAgICAgICAgaWYgKCEgcm93KSB7XG4gICAgICAgICAgICByb3cgPSAkKCcjcm9vbSAudXNlcicpLmVxKDApO1xuICAgICAgICAgICAgc3JjID0gJCgnaW1nJywgcm93KS5hdHRyKCdzcmMnKTtcbiAgICAgICAgfVxuICAgICAgICAkKCdib2R5JykuYXR0cignY2xhc3MnLCdyb29tJyk7XG4gICAgICAgICQoJyNyb29tIGlucHV0W25hbWU9XCJyb29tX25vXCJdJykudmFsKG1zZy5yb29tX25vKTtcbiAgICAgICAgJCgnI3Jvb20gLnJvb20nKS5lbXB0eSgpO1xuICAgICAgICBmb3IgKGxldCB1c2VyIG9mIG1zZy51c2VyKSB7XG4gICAgICAgICAgICBsZXQgciA9IHJvdy5jbG9uZSgpO1xuICAgICAgICAgICAgaWYgKHVzZXIuaWNvbikgJCgnaW1nJywgcikuYXR0cignc3JjJywgdXNlci5pY29uKVxuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAuYXR0cigndGl0bGUnLCB1c2VyLnVpZCk7XG4gICAgICAgICAgICBlbHNlICAgICAgICAgICAkKCdpbWcnLCByKS5hdHRyKCdzcmMnLCBzcmMpO1xuICAgICAgICAgICAgJCgnLm5hbWUnLCByKS50ZXh0KHVzZXIubmFtZSk7XG4gICAgICAgICAgICBpZiAobXNnLnVzZXJbMF0udWlkID09IG15dWlkIHx8IHVzZXIudWlkID09IG15dWlkIClcbiAgICAgICAgICAgICAgICBzaG93KCQoJ2lucHV0W25hbWU9XCJxdWl0XCJdJywgcikub24oJ2NsaWNrJywgKCk9PiB7XG4gICAgICAgICAgICAgICAgICAgICAgICBzb2NrLmVtaXQoJ1JPT00nLCBtc2cucm9vbV9ubywgdXNlci51aWQpO1xuICAgICAgICAgICAgICAgICAgICAgICAgcmV0dXJuIGZhbHNlO1xuICAgICAgICAgICAgICAgICAgICB9KSk7XG4gICAgICAgICAgICBpZiAodXNlci5vZmZsaW5lKSByLmFkZENsYXNzKCdvZmZsaW5lJyk7XG4gICAgICAgICAgICBlbHNlICAgICAgICAgICAgICByLnJlbW92ZUNsYXNzKCdvZmZsaW5lJyk7XG4gICAgICAgICAgICAkKCcjcm9vbSAucm9vbScpLmFwcGVuZChyKTtcbiAgICAgICAgfVxuICAgICAgICBpZiAobXNnLnVzZXJbMF0udWlkID09IG15dWlkKSB7XG4gICAgICAgICAgICBzaG93KCQoJyNyb29tIHNlbGVjdFtuYW1lPVwicnVsZVwiXScpKTtcbiAgICAgICAgICAgIHNob3coJCgnI3Jvb20gaW5wdXRbbmFtZT1cInRpbWVyXCJdJykpO1xuICAgICAgICAgICAgc2hvdygkKCcjcm9vbSBpbnB1dFt0eXBlPVwic3VibWl0XCJdJykpO1xuICAgICAgICB9XG4gICAgICAgIGVsc2Uge1xuICAgICAgICAgICAgaGlkZSgkKCcjcm9vbSBzZWxlY3RbbmFtZT1cInJ1bGVcIl0nKSk7XG4gICAgICAgICAgICBoaWRlKCQoJyNyb29tIGlucHV0W25hbWU9XCJ0aW1lclwiXScpKTtcbiAgICAgICAgICAgIGhpZGUoJCgnI3Jvb20gaW5wdXRbdHlwZT1cInN1Ym1pdFwiXScpKTtcbiAgICAgICAgfVxuICAgIH1cblxuICAgIGZ1bmN0aW9uIHN0YXJ0KCkge1xuXG4gICAgICAgIGNvbnN0IHBsYXllciA9IG5ldyBNYWppYW5nLlVJLlBsYXllcigkKCcjYm9hcmQnKSwgcGFpLCBhdWRpbyk7XG4gICAgICAgIHBsYXllci52aWV3ICA9IG5ldyBNYWppYW5nLlVJLkJvYXJkKCQoJyNib2FyZCAuYm9hcmQnKSwgcGFpLCBhdWRpbyxcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIHBsYXllci5tb2RlbCk7XG5cbiAgICAgICAgY29uc3QgZ2FtZUN0bCA9IG5ldyBNYWppYW5nLlVJLkdhbWVDdGwoJCgnI2JvYXJkJyksICdNYWppYW5nLnByZWYnLFxuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgbnVsbCwgcGxheWVyLCBwbGF5ZXIuX3ZpZXcpO1xuICAgICAgICBnYW1lQ3RsLl92aWV3Lm5vX3BsYXllcl9uYW1lID0gZmFsc2U7XG5cbiAgICAgICAgbGV0IHBsYXllcnMgPSBbXTtcblxuICAgICAgICAkKCcjYm9hcmQgLmNvbnRyb2xsZXInKS5yZW1vdmVDbGFzcygncGFpcHUnKVxuICAgICAgICAkKCdib2R5JykuYXR0cignY2xhc3MnLCdib2FyZCcpO1xuICAgICAgICBzY2FsZSgkKCcjYm9hcmQnKSwgJCgnI3NwYWNlJykpO1xuICAgICAgICBsZXQgc2VxID0gMDtcbiAgICAgICAgc29jay5yZW1vdmVBbGxMaXN0ZW5lcnMoJ0dBTUUnKTtcbiAgICAgICAgc29jay5vbignR0FNRScsIChtc2cpPT57XG4gICAgICAgICAgICBpZiAobXNnLnBsYXllcnMpIHtcbiAgICAgICAgICAgICAgICBwbGF5ZXJzID0gbXNnLnBsYXllcnM7XG4gICAgICAgICAgICB9XG4gICAgICAgICAgICBlbHNlIGlmIChtc2cuc2F5KSB7XG4gICAgICAgICAgICAgICAgcGxheWVyLl92aWV3LnNheShtc2cuc2F5Lm5hbWUsIG1zZy5zYXkubCk7XG4gICAgICAgICAgICB9XG4gICAgICAgICAgICBlbHNlIGlmIChtc2cuc2VxKSB7XG4gICAgICAgICAgICAgICAgaWYgKHNlcSAmJiBtc2cuc2VxICE9IHNlcSkgbG9jYXRpb24ucmVsb2FkKCk7XG4gICAgICAgICAgICAgICAgcGxheWVyLmFjdGlvbihtc2csIChyZXBseSA9IHt9KT0+e1xuICAgICAgICAgICAgICAgICAgICByZXBseS5zZXEgPSBtc2cuc2VxO1xuICAgICAgICAgICAgICAgICAgICBzb2NrLmVtaXQoJ0dBTUUnLCByZXBseSk7XG4gICAgICAgICAgICAgICAgICAgIHNlcSA9IG1zZy5zZXEgKyAxO1xuICAgICAgICAgICAgICAgIH0pO1xuICAgICAgICAgICAgICAgIGlmIChtc2cuamllanUpIHtcbiAgICAgICAgICAgICAgICAgICAgZmlsZS5hZGQobXNnLmppZWp1LCAxMCk7XG4gICAgICAgICAgICAgICAgfVxuICAgICAgICAgICAgfVxuICAgICAgICAgICAgZWxzZSB7XG4gICAgICAgICAgICAgICAgcGxheWVyLmFjdGlvbihtc2cpO1xuICAgICAgICAgICAgICAgIGlmIChtc2cua2FpanUgJiYgbXNnLmthaWp1LmxvZykge1xuICAgICAgICAgICAgICAgICAgICBsZXQgbG9nID0gbXNnLmthaWp1LmxvZy5wb3AoKTtcbiAgICAgICAgICAgICAgICAgICAgZm9yIChsZXQgZGF0YSBvZiBsb2cpIHtcbiAgICAgICAgICAgICAgICAgICAgICAgIHBsYXllci5hY3Rpb24oZGF0YSk7XG4gICAgICAgICAgICAgICAgICAgIH1cbiAgICAgICAgICAgICAgICB9XG4gICAgICAgICAgICB9XG4gICAgICAgICAgICBwbGF5ZXIuX3ZpZXcucGxheWVycyhwbGF5ZXJzKTtcbiAgICAgICAgfSk7XG4gICAgfVxuXG4gICAgZnVuY3Rpb24gZW5kKHBhaXB1KSB7XG4gICAgICAgIHNvY2sucmVtb3ZlQWxsTGlzdGVuZXJzKCdHQU1FJyk7XG4gICAgICAgIGZhZGVJbigkKCdib2R5JykuYXR0cignY2xhc3MnLCdmaWxlJykpO1xuICAgICAgICBmaWxlLnJlZHJhdygpO1xuICAgICAgICAkKCcjZmlsZSBpbnB1dFtuYW1lPVwicm9vbV9ub1wiXScpLnZhbCgnJyk7XG4gICAgfVxuXG4gICAgZm9yIChsZXQga2V5IG9mIE9iamVjdC5rZXlzKHByZXNldCkpIHtcbiAgICAgICAgJCgnc2VsZWN0W25hbWU9XCJydWxlXCJdJykuYXBwZW5kKCQoJzxvcHRpb24+JykudmFsKGtleSkudGV4dChrZXkpKTtcbiAgICB9XG4gICAgaWYgKGxvY2FsU3RvcmFnZS5nZXRJdGVtKCdNYWppYW5nLnJ1bGUnKSkge1xuICAgICAgICAkKCdzZWxlY3RbbmFtZT1cInJ1bGVcIl0nKS5hcHBlbmQoJCgnPG9wdGlvbj4nKVxuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAudmFsKCctJykudGV4dCgn44Kr44K544K/44Og44Or44O844OrJykpO1xuICAgIH1cblxuICAgICQoJyNmaWxlIGZvcm0ucm9vbScpLm9uKCdzdWJtaXQnLCAoZXYpPT57XG4gICAgICAgIGxldCByb29tID0gJCgnaW5wdXRbbmFtZT1cInJvb21fbm9cIl0nLCAkKGV2LnRhcmdldCkpLnZhbCgpO1xuICAgICAgICBzb2NrLmVtaXQoJ1JPT00nLCByb29tKTtcbiAgICAgICAgcmV0dXJuIGZhbHNlO1xuICAgIH0pO1xuICAgICQoJyNyb29tIGZvcm0nKS5vbignc3VibWl0JywgKGV2KT0+e1xuICAgICAgICBsZXQgcm9vbSA9ICQoJ2lucHV0W25hbWU9XCJyb29tX25vXCJdJywgJChldi50YXJnZXQpKS52YWwoKTtcblxuICAgICAgICBsZXQgcnVsZSA9ICQoJ3NlbGVjdFtuYW1lPVwicnVsZVwiXScsICQoZXYudGFyZ2V0KSkudmFsKCk7XG4gICAgICAgIHJ1bGUgPSAhIHJ1bGUgICAgICA/IHt9XG4gICAgICAgICAgICAgOiBydWxlID09ICctJyA/IEpTT04ucGFyc2UoXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIGxvY2FsU3RvcmFnZS5nZXRJdGVtKCdNYWppYW5nLnJ1bGUnKXx8J3t9JylcbiAgICAgICAgICAgICA6ICAgICAgICAgICAgICAgcHJlc2V0W3J1bGVdO1xuICAgICAgICBydWxlID0gTWFqaWFuZy5ydWxlKHJ1bGUpO1xuXG4gICAgICAgIGxldCB0aW1lciA9ICQoJ2lucHV0W25hbWU9XCJ0aW1lclwiXScsICQoZXYudGFyZ2V0KSkudmFsKCk7XG4gICAgICAgIHRpbWVyID0gdGltZXIubWF0Y2goLyhcXGQrKS9nKTtcbiAgICAgICAgaWYgKHRpbWVyKSB0aW1lciA9IHRpbWVyLm1hcCh0PT4rdCk7XG5cbiAgICAgICAgc29jay5lbWl0KCdTVEFSVCcsIHJvb20sIHJ1bGUsIHRpbWVyKTtcbiAgICAgICAgcmV0dXJuIGZhbHNlO1xuICAgIH0pO1xuXG4gICAgJCh3aW5kb3cpLm9uKCdyZXNpemUnLCAoKT0+c2NhbGUoJCgnI2JvYXJkJyksICQoJyNzcGFjZScpKSk7XG5cbiAgICAkKHdpbmRvdykub24oJ2xvYWQnLCAoKT0+c2V0VGltZW91dChpbml0LCA1MDApKTtcbiAgICBpZiAobG9hZGVkKSAkKHdpbmRvdykudHJpZ2dlcignbG9hZCcpO1xuXG4gICAgJCgnI3RpdGxlIC5sb2dpbiBmb3JtJykuZWFjaChmdW5jdGlvbigpe1xuICAgICAgICBsZXQgbWV0aG9kID0gJCh0aGlzKS5hdHRyKCdtZXRob2QnKVxuICAgICAgICBsZXQgdXJsICAgID0gJCh0aGlzKS5hdHRyKCdhY3Rpb24nKTtcbiAgICAgICAgZmV0Y2godXJsLCB7IG1ldGhvZDogbWV0aG9kLCByZWRpcmVjdDogJ21hbnVhbCcgfSkudGhlbihyZXMgPT57XG4gICAgICAgICAgICBpZiAocmVzLnN0YXR1cyA9PSA0MDQpIGhpZGUoJCh0aGlzKSk7XG4gICAgICAgIH0pO1xuICAgIH0pO1xufSk7XG4kKHdpbmRvdykub24oJ2xvYWQnLCAoKT0+IGxvYWRlZCA9IHRydWUpO1xuIl0sIm5hbWVzIjpbXSwic291cmNlUm9vdCI6IiJ9
/******/ (() => { // webpackBootstrap
/******/ 	"use strict";
/*!****************************!*\
  !*** ./src/js/autoplay.js ***!
  \****************************/
/*!
 *  電脳麻将: 自動対戦 v2.5.3
 *
 *  Copyright(C) 2017 Satoshi Kobayashi
 *  Released under the MIT license
 *  https://github.com/kobalab/Majiang/blob/master/LICENSE
 */


const { hide, show, fadeIn, scale,
        setSelector, clearSelector  } = Majiang.UI.Util;

let loaded;

$(function(){

    let game;
    const pai   = Majiang.UI.pai($('#loaddata'));
    const audio = Majiang.UI.audio($('#loaddata'));

    const rule = Majiang.rule(
                    JSON.parse(localStorage.getItem('Majiang.rule')||'{}'));

    let open_shoupai = false;
    let open_he      = false;

    function start() {
        if (game) {
            open_shoupai = game._view.open_shoupai;
            open_he      = game._view.open_he;
        }
        let players = [];
        for (let i = 0; i < 4; i++) {
            players[i] = new Majiang.AI();
        }
        game = new Majiang.Game(players, start, rule);
        game.view = new Majiang.UI.Board($('#board .board'),
                                        pai, audio, game.model);
        game.wait  = 5000;
        game._model.title
            = game._model.title.replace(/^[^\n]*/, $('title').text());
        game._view.open_shoupai = open_shoupai;
        game._view.open_he      = open_he;

        $('body').attr('class','board');
        scale($('#board'), $('#space'));

        $(window).off('keyup').on('keyup', (ev)=>{
            if (ev.key == ' ') {
                if (gamectl.stoped) gamectl.start();
                else                gamectl.stop();
                game.handler = ()=> gamectl.stop();
            }
            else if (ev.key == 's') gamectl.shoupai();
            else if (ev.key == 'h') gamectl.he();
            return false;
        });
        $('#board .board').off('click').on('click', ()=>{
            if (gamectl.stoped) gamectl.start();
            else                gamectl.stop();
            game.handler = ()=> gamectl.stop();
        });
        $('#board .board > .shoupai')
            .off('click', '.pai')
            .on('click', '.pai', ()=>gamectl.shoupai());
        $('#board .board > .he')
            .off('click', '.pai')
            .on('click', '.pai', ()=>gamectl.he());

        const gamectl = new Majiang.UI.GameCtl($('#board'), 'Majiang.pref',
                                                game, game._view);
        game.kaiju();
    }

    $(window).on('resize', ()=>scale($('#board'), $('#space')));

    $(window).on('load', function(){
        hide($('#title .loading'));
        $('#title .start').on('click', start)
        show($('#title .start'));
    });
    if (loaded) $(window).trigger('load');
});

$(window).on('load', ()=> loaded = true);

/******/ })()
;
//# sourceMappingURL=data:application/json;charset=utf-8;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiYXV0b3BsYXktMi41LjMuanMiLCJtYXBwaW5ncyI6Ijs7Ozs7QUFBQTtBQUNBO0FBQ0E7QUFDQTtBQUNBO0FBQ0E7QUFDQTtBQUNhOztBQUViLFFBQVE7QUFDUixzQ0FBc0M7O0FBRXRDOztBQUVBOztBQUVBO0FBQ0E7QUFDQTs7QUFFQTtBQUNBLHdFQUF3RTs7QUFFeEU7QUFDQTs7QUFFQTtBQUNBO0FBQ0E7QUFDQTtBQUNBO0FBQ0E7QUFDQSx3QkFBd0IsT0FBTztBQUMvQjtBQUNBO0FBQ0E7QUFDQTtBQUNBO0FBQ0E7QUFDQTtBQUNBO0FBQ0E7QUFDQTs7QUFFQTtBQUNBOztBQUVBO0FBQ0E7QUFDQTtBQUNBO0FBQ0E7QUFDQTtBQUNBO0FBQ0E7QUFDQTtBQUNBLFNBQVM7QUFDVDtBQUNBO0FBQ0E7QUFDQTtBQUNBLFNBQVM7QUFDVDtBQUNBO0FBQ0E7QUFDQTtBQUNBO0FBQ0E7O0FBRUE7QUFDQTtBQUNBO0FBQ0E7O0FBRUE7O0FBRUE7QUFDQTtBQUNBO0FBQ0E7QUFDQSxLQUFLO0FBQ0w7QUFDQSxDQUFDOztBQUVEIiwic291cmNlcyI6WyJ3ZWJwYWNrOi8vbWFqaWFuZy8uL3NyYy9qcy9hdXRvcGxheS5qcyJdLCJzb3VyY2VzQ29udGVudCI6WyIvKiFcbiAqICDpm7vohLPpurvlsIY6IOiHquWLleWvvuaIpiB2Mi41LjNcbiAqXG4gKiAgQ29weXJpZ2h0KEMpIDIwMTcgU2F0b3NoaSBLb2JheWFzaGlcbiAqICBSZWxlYXNlZCB1bmRlciB0aGUgTUlUIGxpY2Vuc2VcbiAqICBodHRwczovL2dpdGh1Yi5jb20va29iYWxhYi9NYWppYW5nL2Jsb2IvbWFzdGVyL0xJQ0VOU0VcbiAqL1xuXCJ1c2Ugc3RyaWN0XCI7XG5cbmNvbnN0IHsgaGlkZSwgc2hvdywgZmFkZUluLCBzY2FsZSxcbiAgICAgICAgc2V0U2VsZWN0b3IsIGNsZWFyU2VsZWN0b3IgIH0gPSBNYWppYW5nLlVJLlV0aWw7XG5cbmxldCBsb2FkZWQ7XG5cbiQoZnVuY3Rpb24oKXtcblxuICAgIGxldCBnYW1lO1xuICAgIGNvbnN0IHBhaSAgID0gTWFqaWFuZy5VSS5wYWkoJCgnI2xvYWRkYXRhJykpO1xuICAgIGNvbnN0IGF1ZGlvID0gTWFqaWFuZy5VSS5hdWRpbygkKCcjbG9hZGRhdGEnKSk7XG5cbiAgICBjb25zdCBydWxlID0gTWFqaWFuZy5ydWxlKFxuICAgICAgICAgICAgICAgICAgICBKU09OLnBhcnNlKGxvY2FsU3RvcmFnZS5nZXRJdGVtKCdNYWppYW5nLnJ1bGUnKXx8J3t9JykpO1xuXG4gICAgbGV0IG9wZW5fc2hvdXBhaSA9IGZhbHNlO1xuICAgIGxldCBvcGVuX2hlICAgICAgPSBmYWxzZTtcblxuICAgIGZ1bmN0aW9uIHN0YXJ0KCkge1xuICAgICAgICBpZiAoZ2FtZSkge1xuICAgICAgICAgICAgb3Blbl9zaG91cGFpID0gZ2FtZS5fdmlldy5vcGVuX3Nob3VwYWk7XG4gICAgICAgICAgICBvcGVuX2hlICAgICAgPSBnYW1lLl92aWV3Lm9wZW5faGU7XG4gICAgICAgIH1cbiAgICAgICAgbGV0IHBsYXllcnMgPSBbXTtcbiAgICAgICAgZm9yIChsZXQgaSA9IDA7IGkgPCA0OyBpKyspIHtcbiAgICAgICAgICAgIHBsYXllcnNbaV0gPSBuZXcgTWFqaWFuZy5BSSgpO1xuICAgICAgICB9XG4gICAgICAgIGdhbWUgPSBuZXcgTWFqaWFuZy5HYW1lKHBsYXllcnMsIHN0YXJ0LCBydWxlKTtcbiAgICAgICAgZ2FtZS52aWV3ID0gbmV3IE1hamlhbmcuVUkuQm9hcmQoJCgnI2JvYXJkIC5ib2FyZCcpLFxuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIHBhaSwgYXVkaW8sIGdhbWUubW9kZWwpO1xuICAgICAgICBnYW1lLndhaXQgID0gNTAwMDtcbiAgICAgICAgZ2FtZS5fbW9kZWwudGl0bGVcbiAgICAgICAgICAgID0gZ2FtZS5fbW9kZWwudGl0bGUucmVwbGFjZSgvXlteXFxuXSovLCAkKCd0aXRsZScpLnRleHQoKSk7XG4gICAgICAgIGdhbWUuX3ZpZXcub3Blbl9zaG91cGFpID0gb3Blbl9zaG91cGFpO1xuICAgICAgICBnYW1lLl92aWV3Lm9wZW5faGUgICAgICA9IG9wZW5faGU7XG5cbiAgICAgICAgJCgnYm9keScpLmF0dHIoJ2NsYXNzJywnYm9hcmQnKTtcbiAgICAgICAgc2NhbGUoJCgnI2JvYXJkJyksICQoJyNzcGFjZScpKTtcblxuICAgICAgICAkKHdpbmRvdykub2ZmKCdrZXl1cCcpLm9uKCdrZXl1cCcsIChldik9PntcbiAgICAgICAgICAgIGlmIChldi5rZXkgPT0gJyAnKSB7XG4gICAgICAgICAgICAgICAgaWYgKGdhbWVjdGwuc3RvcGVkKSBnYW1lY3RsLnN0YXJ0KCk7XG4gICAgICAgICAgICAgICAgZWxzZSAgICAgICAgICAgICAgICBnYW1lY3RsLnN0b3AoKTtcbiAgICAgICAgICAgICAgICBnYW1lLmhhbmRsZXIgPSAoKT0+IGdhbWVjdGwuc3RvcCgpO1xuICAgICAgICAgICAgfVxuICAgICAgICAgICAgZWxzZSBpZiAoZXYua2V5ID09ICdzJykgZ2FtZWN0bC5zaG91cGFpKCk7XG4gICAgICAgICAgICBlbHNlIGlmIChldi5rZXkgPT0gJ2gnKSBnYW1lY3RsLmhlKCk7XG4gICAgICAgICAgICByZXR1cm4gZmFsc2U7XG4gICAgICAgIH0pO1xuICAgICAgICAkKCcjYm9hcmQgLmJvYXJkJykub2ZmKCdjbGljaycpLm9uKCdjbGljaycsICgpPT57XG4gICAgICAgICAgICBpZiAoZ2FtZWN0bC5zdG9wZWQpIGdhbWVjdGwuc3RhcnQoKTtcbiAgICAgICAgICAgIGVsc2UgICAgICAgICAgICAgICAgZ2FtZWN0bC5zdG9wKCk7XG4gICAgICAgICAgICBnYW1lLmhhbmRsZXIgPSAoKT0+IGdhbWVjdGwuc3RvcCgpO1xuICAgICAgICB9KTtcbiAgICAgICAgJCgnI2JvYXJkIC5ib2FyZCA+IC5zaG91cGFpJylcbiAgICAgICAgICAgIC5vZmYoJ2NsaWNrJywgJy5wYWknKVxuICAgICAgICAgICAgLm9uKCdjbGljaycsICcucGFpJywgKCk9PmdhbWVjdGwuc2hvdXBhaSgpKTtcbiAgICAgICAgJCgnI2JvYXJkIC5ib2FyZCA+IC5oZScpXG4gICAgICAgICAgICAub2ZmKCdjbGljaycsICcucGFpJylcbiAgICAgICAgICAgIC5vbignY2xpY2snLCAnLnBhaScsICgpPT5nYW1lY3RsLmhlKCkpO1xuXG4gICAgICAgIGNvbnN0IGdhbWVjdGwgPSBuZXcgTWFqaWFuZy5VSS5HYW1lQ3RsKCQoJyNib2FyZCcpLCAnTWFqaWFuZy5wcmVmJyxcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIGdhbWUsIGdhbWUuX3ZpZXcpO1xuICAgICAgICBnYW1lLmthaWp1KCk7XG4gICAgfVxuXG4gICAgJCh3aW5kb3cpLm9uKCdyZXNpemUnLCAoKT0+c2NhbGUoJCgnI2JvYXJkJyksICQoJyNzcGFjZScpKSk7XG5cbiAgICAkKHdpbmRvdykub24oJ2xvYWQnLCBmdW5jdGlvbigpe1xuICAgICAgICBoaWRlKCQoJyN0aXRsZSAubG9hZGluZycpKTtcbiAgICAgICAgJCgnI3RpdGxlIC5zdGFydCcpLm9uKCdjbGljaycsIHN0YXJ0KVxuICAgICAgICBzaG93KCQoJyN0aXRsZSAuc3RhcnQnKSk7XG4gICAgfSk7XG4gICAgaWYgKGxvYWRlZCkgJCh3aW5kb3cpLnRyaWdnZXIoJ2xvYWQnKTtcbn0pO1xuXG4kKHdpbmRvdykub24oJ2xvYWQnLCAoKT0+IGxvYWRlZCA9IHRydWUpO1xuIl0sIm5hbWVzIjpbXSwic291cmNlUm9vdCI6IiJ9
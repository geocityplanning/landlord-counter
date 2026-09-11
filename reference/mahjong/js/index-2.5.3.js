/******/ (() => { // webpackBootstrap
/******/ 	"use strict";
/*!*************************!*\
  !*** ./src/js/index.js ***!
  \*************************/
/*!
 *  電脳麻将 v2.5.3
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

    const analyzer = (kaiju)=>{
        $('body').addClass('analyzer');
        return new Majiang.UI.Analyzer($('#board > .analyzer'), kaiju, pai,
                                        ()=>$('body').removeClass('analyzer'));
    };
    const viewer = (paipu)=>{
        $('#board .controller').addClass('paipu')
        $('body').attr('class','board');
        scale($('#board'), $('#space'));
        const _viewer
                = new Majiang.UI.Paipu(
                        $('#board'), paipu, pai, audio, 'Majiang.pref',
                        ()=>fadeIn($('body').attr('class','file')),
                        analyzer);
        delete _viewer._view.dummy_name;
        return _viewer;
    };
    const stat = (paipu_list)=>{
        fadeIn($('body').attr('class','stat'));
        return new Majiang.UI.PaipuStat($('#stat'), paipu_list,
                        ()=>fadeIn($('body').attr('class','file')));
    };
    const file = new Majiang.UI.PaipuFile($('#file'), 'Majiang.game',
                                            viewer, stat);
    const rule = Majiang.rule(
                    JSON.parse(localStorage.getItem('Majiang.rule')||'{}'));

    function start() {
        let players = [ new Majiang.UI.Player($('#board'), pai, audio) ];
        for (let i = 1; i < 4; i++) {
            players[i] = new Majiang.AI();
        }
        game = new Majiang.Game(players, end, rule);
        game.view = new Majiang.UI.Board($('#board .board'),
                                        pai, audio, game.model);

        $('#board .controller').removeClass('paipu')
        $('body').attr('class','board');
        scale($('#board'), $('#space'));

        new Majiang.UI.GameCtl($('#board'), 'Majiang.pref', game, game._view);
        game.kaiju();
    }

    function end(paipu) {
        if (paipu) file.add(paipu, 10);
        fadeIn($('body').attr('class','file'));
        file.redraw();
    }

    $('#file .start').on('click', start);

    $(window).on('resize', ()=>scale($('#board'), $('#space')));

    setTimeout(()=>{
        $(window).on('load', function(){
            if (! file.isEmpty) return end();
            hide($('#title .loading'));
            $('#title .start')
                .attr('tabindex', 0).attr('role','button')
                .on('click', ()=>{
                    clearSelector('title');
                    start();
                });
            show(setSelector($('#title .start'), 'title',
                            { focus: null, touch: false }));
        });
        if (loaded) $(window).trigger('load');
    }, 1000);
});

$(window).on('load', ()=> loaded = true);

/******/ })()
;
//# sourceMappingURL=data:application/json;charset=utf-8;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiaW5kZXgtMi41LjMuanMiLCJtYXBwaW5ncyI6Ijs7Ozs7QUFBQTtBQUNBO0FBQ0E7QUFDQTtBQUNBO0FBQ0E7QUFDQTtBQUNhOztBQUViLFFBQVE7QUFDUixzQ0FBc0M7O0FBRXRDOztBQUVBOztBQUVBO0FBQ0E7QUFDQTs7QUFFQTtBQUNBO0FBQ0E7QUFDQTtBQUNBO0FBQ0E7QUFDQTtBQUNBO0FBQ0E7QUFDQTtBQUNBO0FBQ0E7QUFDQTtBQUNBO0FBQ0E7QUFDQTtBQUNBO0FBQ0E7QUFDQTtBQUNBO0FBQ0E7QUFDQTtBQUNBO0FBQ0E7QUFDQTtBQUNBLHdFQUF3RTs7QUFFeEU7QUFDQTtBQUNBLHdCQUF3QixPQUFPO0FBQy9CO0FBQ0E7QUFDQTtBQUNBO0FBQ0E7O0FBRUE7QUFDQTtBQUNBOztBQUVBO0FBQ0E7QUFDQTs7QUFFQTtBQUNBO0FBQ0E7QUFDQTtBQUNBOztBQUVBOztBQUVBOztBQUVBO0FBQ0E7QUFDQTtBQUNBO0FBQ0E7QUFDQTtBQUNBO0FBQ0E7QUFDQTtBQUNBLGlCQUFpQjtBQUNqQjtBQUNBLDhCQUE4QiwyQkFBMkI7QUFDekQsU0FBUztBQUNUO0FBQ0EsS0FBSztBQUNMLENBQUM7O0FBRUQiLCJzb3VyY2VzIjpbIndlYnBhY2s6Ly9tYWppYW5nLy4vc3JjL2pzL2luZGV4LmpzIl0sInNvdXJjZXNDb250ZW50IjpbIi8qIVxuICogIOmbu+iEs+m6u+WwhiB2Mi41LjNcbiAqXG4gKiAgQ29weXJpZ2h0KEMpIDIwMTcgU2F0b3NoaSBLb2JheWFzaGlcbiAqICBSZWxlYXNlZCB1bmRlciB0aGUgTUlUIGxpY2Vuc2VcbiAqICBodHRwczovL2dpdGh1Yi5jb20va29iYWxhYi9NYWppYW5nL2Jsb2IvbWFzdGVyL0xJQ0VOU0VcbiAqL1xuXCJ1c2Ugc3RyaWN0XCI7XG5cbmNvbnN0IHsgaGlkZSwgc2hvdywgZmFkZUluLCBzY2FsZSxcbiAgICAgICAgc2V0U2VsZWN0b3IsIGNsZWFyU2VsZWN0b3IgIH0gPSBNYWppYW5nLlVJLlV0aWw7XG5cbmxldCBsb2FkZWQ7XG5cbiQoZnVuY3Rpb24oKXtcblxuICAgIGxldCBnYW1lO1xuICAgIGNvbnN0IHBhaSAgID0gTWFqaWFuZy5VSS5wYWkoJCgnI2xvYWRkYXRhJykpO1xuICAgIGNvbnN0IGF1ZGlvID0gTWFqaWFuZy5VSS5hdWRpbygkKCcjbG9hZGRhdGEnKSk7XG5cbiAgICBjb25zdCBhbmFseXplciA9IChrYWlqdSk9PntcbiAgICAgICAgJCgnYm9keScpLmFkZENsYXNzKCdhbmFseXplcicpO1xuICAgICAgICByZXR1cm4gbmV3IE1hamlhbmcuVUkuQW5hbHl6ZXIoJCgnI2JvYXJkID4gLmFuYWx5emVyJyksIGthaWp1LCBwYWksXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgKCk9PiQoJ2JvZHknKS5yZW1vdmVDbGFzcygnYW5hbHl6ZXInKSk7XG4gICAgfTtcbiAgICBjb25zdCB2aWV3ZXIgPSAocGFpcHUpPT57XG4gICAgICAgICQoJyNib2FyZCAuY29udHJvbGxlcicpLmFkZENsYXNzKCdwYWlwdScpXG4gICAgICAgICQoJ2JvZHknKS5hdHRyKCdjbGFzcycsJ2JvYXJkJyk7XG4gICAgICAgIHNjYWxlKCQoJyNib2FyZCcpLCAkKCcjc3BhY2UnKSk7XG4gICAgICAgIGNvbnN0IF92aWV3ZXJcbiAgICAgICAgICAgICAgICA9IG5ldyBNYWppYW5nLlVJLlBhaXB1KFxuICAgICAgICAgICAgICAgICAgICAgICAgJCgnI2JvYXJkJyksIHBhaXB1LCBwYWksIGF1ZGlvLCAnTWFqaWFuZy5wcmVmJyxcbiAgICAgICAgICAgICAgICAgICAgICAgICgpPT5mYWRlSW4oJCgnYm9keScpLmF0dHIoJ2NsYXNzJywnZmlsZScpKSxcbiAgICAgICAgICAgICAgICAgICAgICAgIGFuYWx5emVyKTtcbiAgICAgICAgZGVsZXRlIF92aWV3ZXIuX3ZpZXcuZHVtbXlfbmFtZTtcbiAgICAgICAgcmV0dXJuIF92aWV3ZXI7XG4gICAgfTtcbiAgICBjb25zdCBzdGF0ID0gKHBhaXB1X2xpc3QpPT57XG4gICAgICAgIGZhZGVJbigkKCdib2R5JykuYXR0cignY2xhc3MnLCdzdGF0JykpO1xuICAgICAgICByZXR1cm4gbmV3IE1hamlhbmcuVUkuUGFpcHVTdGF0KCQoJyNzdGF0JyksIHBhaXB1X2xpc3QsXG4gICAgICAgICAgICAgICAgICAgICAgICAoKT0+ZmFkZUluKCQoJ2JvZHknKS5hdHRyKCdjbGFzcycsJ2ZpbGUnKSkpO1xuICAgIH07XG4gICAgY29uc3QgZmlsZSA9IG5ldyBNYWppYW5nLlVJLlBhaXB1RmlsZSgkKCcjZmlsZScpLCAnTWFqaWFuZy5nYW1lJyxcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgdmlld2VyLCBzdGF0KTtcbiAgICBjb25zdCBydWxlID0gTWFqaWFuZy5ydWxlKFxuICAgICAgICAgICAgICAgICAgICBKU09OLnBhcnNlKGxvY2FsU3RvcmFnZS5nZXRJdGVtKCdNYWppYW5nLnJ1bGUnKXx8J3t9JykpO1xuXG4gICAgZnVuY3Rpb24gc3RhcnQoKSB7XG4gICAgICAgIGxldCBwbGF5ZXJzID0gWyBuZXcgTWFqaWFuZy5VSS5QbGF5ZXIoJCgnI2JvYXJkJyksIHBhaSwgYXVkaW8pIF07XG4gICAgICAgIGZvciAobGV0IGkgPSAxOyBpIDwgNDsgaSsrKSB7XG4gICAgICAgICAgICBwbGF5ZXJzW2ldID0gbmV3IE1hamlhbmcuQUkoKTtcbiAgICAgICAgfVxuICAgICAgICBnYW1lID0gbmV3IE1hamlhbmcuR2FtZShwbGF5ZXJzLCBlbmQsIHJ1bGUpO1xuICAgICAgICBnYW1lLnZpZXcgPSBuZXcgTWFqaWFuZy5VSS5Cb2FyZCgkKCcjYm9hcmQgLmJvYXJkJyksXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgcGFpLCBhdWRpbywgZ2FtZS5tb2RlbCk7XG5cbiAgICAgICAgJCgnI2JvYXJkIC5jb250cm9sbGVyJykucmVtb3ZlQ2xhc3MoJ3BhaXB1JylcbiAgICAgICAgJCgnYm9keScpLmF0dHIoJ2NsYXNzJywnYm9hcmQnKTtcbiAgICAgICAgc2NhbGUoJCgnI2JvYXJkJyksICQoJyNzcGFjZScpKTtcblxuICAgICAgICBuZXcgTWFqaWFuZy5VSS5HYW1lQ3RsKCQoJyNib2FyZCcpLCAnTWFqaWFuZy5wcmVmJywgZ2FtZSwgZ2FtZS5fdmlldyk7XG4gICAgICAgIGdhbWUua2FpanUoKTtcbiAgICB9XG5cbiAgICBmdW5jdGlvbiBlbmQocGFpcHUpIHtcbiAgICAgICAgaWYgKHBhaXB1KSBmaWxlLmFkZChwYWlwdSwgMTApO1xuICAgICAgICBmYWRlSW4oJCgnYm9keScpLmF0dHIoJ2NsYXNzJywnZmlsZScpKTtcbiAgICAgICAgZmlsZS5yZWRyYXcoKTtcbiAgICB9XG5cbiAgICAkKCcjZmlsZSAuc3RhcnQnKS5vbignY2xpY2snLCBzdGFydCk7XG5cbiAgICAkKHdpbmRvdykub24oJ3Jlc2l6ZScsICgpPT5zY2FsZSgkKCcjYm9hcmQnKSwgJCgnI3NwYWNlJykpKTtcblxuICAgIHNldFRpbWVvdXQoKCk9PntcbiAgICAgICAgJCh3aW5kb3cpLm9uKCdsb2FkJywgZnVuY3Rpb24oKXtcbiAgICAgICAgICAgIGlmICghIGZpbGUuaXNFbXB0eSkgcmV0dXJuIGVuZCgpO1xuICAgICAgICAgICAgaGlkZSgkKCcjdGl0bGUgLmxvYWRpbmcnKSk7XG4gICAgICAgICAgICAkKCcjdGl0bGUgLnN0YXJ0JylcbiAgICAgICAgICAgICAgICAuYXR0cigndGFiaW5kZXgnLCAwKS5hdHRyKCdyb2xlJywnYnV0dG9uJylcbiAgICAgICAgICAgICAgICAub24oJ2NsaWNrJywgKCk9PntcbiAgICAgICAgICAgICAgICAgICAgY2xlYXJTZWxlY3RvcigndGl0bGUnKTtcbiAgICAgICAgICAgICAgICAgICAgc3RhcnQoKTtcbiAgICAgICAgICAgICAgICB9KTtcbiAgICAgICAgICAgIHNob3coc2V0U2VsZWN0b3IoJCgnI3RpdGxlIC5zdGFydCcpLCAndGl0bGUnLFxuICAgICAgICAgICAgICAgICAgICAgICAgICAgIHsgZm9jdXM6IG51bGwsIHRvdWNoOiBmYWxzZSB9KSk7XG4gICAgICAgIH0pO1xuICAgICAgICBpZiAobG9hZGVkKSAkKHdpbmRvdykudHJpZ2dlcignbG9hZCcpO1xuICAgIH0sIDEwMDApO1xufSk7XG5cbiQod2luZG93KS5vbignbG9hZCcsICgpPT4gbG9hZGVkID0gdHJ1ZSk7XG4iXSwibmFtZXMiOltdLCJzb3VyY2VSb290IjoiIn0=
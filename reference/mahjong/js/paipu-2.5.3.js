/******/ (() => { // webpackBootstrap
/******/ 	"use strict";
/*!*************************!*\
  !*** ./src/js/paipu.js ***!
  \*************************/
/*!
 *  電脳麻将: 牌譜ビューア v2.5.3
 *
 *  Copyright(C) 2017 Satoshi Kobayashi
 *  Released under the MIT license
 *  https://github.com/kobalab/Majiang/blob/master/LICENSE
 */


const { hide, show, fadeIn, scale   } = Majiang.UI.Util;

$(function(){

    const tenhou_log = 'https://kobalab.net/majiang/tenhou-log/';

    const pai   = Majiang.UI.pai($('#loaddata'));
    const audio = Majiang.UI.audio($('#loaddata'));

    const rule  = Majiang.rule(
                    JSON.parse(localStorage.getItem('Majiang.rule')||'{}'));

    let file;
    let _viewer;

    const analyzer = (kaiju)=>{
        $('body').addClass('analyzer');
        return new Majiang.UI.Analyzer($('#board > .analyzer'), kaiju, pai,
                                        ()=>$('body').removeClass('analyzer'));
    };
    const viewer = (paipu)=>{
        $('#board .controller').addClass('paipu')
        $('body').attr('class','board');
        scale($('#board'), $('#space'));
        _viewer = new Majiang.UI.Paipu(
                        $('#board'), paipu, pai, audio, 'Majiang.pref',
                        ()=>{ fadeIn($('body').attr('class','file'));
                              _viewer = null },
                        analyzer);
        return _viewer;
    };
    const stat = (paipu_list)=>{
        fadeIn($('body').attr('class','stat'));
        return new Majiang.UI.PaipuStat($('#stat'), paipu_list,
                        ()=>fadeIn($('body').attr('class','file')));
    };
    const preview = (paipu)=>{
        $('#board .controller').addClass('paipu')
        $('body').attr('class','board');
        scale($('#board'), $('#space'));
        _viewer = new Majiang.UI.Paipu(
                        $('#board'), paipu, pai, audio, 'Majiang.pref',
                        ()=>{ fadeIn($('body').attr('class','editor'));
                              _viewer = null },
                        analyzer);
        delete _viewer._view.dummy_name;
        return _viewer;
    };
    const editor = (paipu, save)=>{
        new Majiang.UI.PaipuEditor($('#editor'), paipu, rule, pai,
                        ()=>{ file.storage(true);
                              fadeIn($('body').attr('class','file')) },
                        save, preview);
        fadeIn($('body').attr('class','editor'));
    };

    if (location.search) {
        file = new Majiang.UI.PaipuFile(
                                $('#file'), 'Majiang.paipu',
                                viewer, stat, editor,
                                tenhou_log,
                                location.search.replace(/^\?/,''),
                                location.hash.replace(/^#/,''));
    }
    else {
        file = new Majiang.UI.PaipuFile(
                                $('#file'), 'Majiang.paipu',
                                viewer, stat, editor,
                                tenhou_log);
    }
    file.redraw();

    $(window).on('resize', ()=>scale($('#board'), $('#space')));
});

/******/ })()
;
//# sourceMappingURL=data:application/json;charset=utf-8;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoicGFpcHUtMi41LjMuanMiLCJtYXBwaW5ncyI6Ijs7Ozs7QUFBQTtBQUNBO0FBQ0E7QUFDQTtBQUNBO0FBQ0E7QUFDQTtBQUNhOztBQUViLFFBQVEsOEJBQThCOztBQUV0Qzs7QUFFQTs7QUFFQTtBQUNBOztBQUVBO0FBQ0Esd0VBQXdFOztBQUV4RTtBQUNBOztBQUVBO0FBQ0E7QUFDQTtBQUNBO0FBQ0E7QUFDQTtBQUNBO0FBQ0E7QUFDQTtBQUNBO0FBQ0E7QUFDQSw4QkFBOEI7QUFDOUIsOENBQThDO0FBQzlDO0FBQ0E7QUFDQTtBQUNBO0FBQ0E7QUFDQTtBQUNBO0FBQ0E7QUFDQTtBQUNBO0FBQ0E7QUFDQTtBQUNBO0FBQ0E7QUFDQSw4QkFBOEI7QUFDOUIsOENBQThDO0FBQzlDO0FBQ0E7QUFDQTtBQUNBO0FBQ0E7QUFDQTtBQUNBLDhCQUE4QjtBQUM5QixzRUFBc0U7QUFDdEU7QUFDQTtBQUNBOztBQUVBO0FBQ0E7QUFDQTtBQUNBO0FBQ0E7QUFDQTtBQUNBO0FBQ0E7QUFDQTtBQUNBO0FBQ0E7QUFDQTtBQUNBO0FBQ0E7QUFDQTs7QUFFQTtBQUNBLENBQUMiLCJzb3VyY2VzIjpbIndlYnBhY2s6Ly9tYWppYW5nLy4vc3JjL2pzL3BhaXB1LmpzIl0sInNvdXJjZXNDb250ZW50IjpbIi8qIVxuICogIOmbu+iEs+m6u+Wwhjog54mM6K2c44OT44Ol44O844KiIHYyLjUuM1xuICpcbiAqICBDb3B5cmlnaHQoQykgMjAxNyBTYXRvc2hpIEtvYmF5YXNoaVxuICogIFJlbGVhc2VkIHVuZGVyIHRoZSBNSVQgbGljZW5zZVxuICogIGh0dHBzOi8vZ2l0aHViLmNvbS9rb2JhbGFiL01hamlhbmcvYmxvYi9tYXN0ZXIvTElDRU5TRVxuICovXG5cInVzZSBzdHJpY3RcIjtcblxuY29uc3QgeyBoaWRlLCBzaG93LCBmYWRlSW4sIHNjYWxlICAgfSA9IE1hamlhbmcuVUkuVXRpbDtcblxuJChmdW5jdGlvbigpe1xuXG4gICAgY29uc3QgdGVuaG91X2xvZyA9ICdodHRwczovL2tvYmFsYWIubmV0L21hamlhbmcvdGVuaG91LWxvZy8nO1xuXG4gICAgY29uc3QgcGFpICAgPSBNYWppYW5nLlVJLnBhaSgkKCcjbG9hZGRhdGEnKSk7XG4gICAgY29uc3QgYXVkaW8gPSBNYWppYW5nLlVJLmF1ZGlvKCQoJyNsb2FkZGF0YScpKTtcblxuICAgIGNvbnN0IHJ1bGUgID0gTWFqaWFuZy5ydWxlKFxuICAgICAgICAgICAgICAgICAgICBKU09OLnBhcnNlKGxvY2FsU3RvcmFnZS5nZXRJdGVtKCdNYWppYW5nLnJ1bGUnKXx8J3t9JykpO1xuXG4gICAgbGV0IGZpbGU7XG4gICAgbGV0IF92aWV3ZXI7XG5cbiAgICBjb25zdCBhbmFseXplciA9IChrYWlqdSk9PntcbiAgICAgICAgJCgnYm9keScpLmFkZENsYXNzKCdhbmFseXplcicpO1xuICAgICAgICByZXR1cm4gbmV3IE1hamlhbmcuVUkuQW5hbHl6ZXIoJCgnI2JvYXJkID4gLmFuYWx5emVyJyksIGthaWp1LCBwYWksXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgKCk9PiQoJ2JvZHknKS5yZW1vdmVDbGFzcygnYW5hbHl6ZXInKSk7XG4gICAgfTtcbiAgICBjb25zdCB2aWV3ZXIgPSAocGFpcHUpPT57XG4gICAgICAgICQoJyNib2FyZCAuY29udHJvbGxlcicpLmFkZENsYXNzKCdwYWlwdScpXG4gICAgICAgICQoJ2JvZHknKS5hdHRyKCdjbGFzcycsJ2JvYXJkJyk7XG4gICAgICAgIHNjYWxlKCQoJyNib2FyZCcpLCAkKCcjc3BhY2UnKSk7XG4gICAgICAgIF92aWV3ZXIgPSBuZXcgTWFqaWFuZy5VSS5QYWlwdShcbiAgICAgICAgICAgICAgICAgICAgICAgICQoJyNib2FyZCcpLCBwYWlwdSwgcGFpLCBhdWRpbywgJ01hamlhbmcucHJlZicsXG4gICAgICAgICAgICAgICAgICAgICAgICAoKT0+eyBmYWRlSW4oJCgnYm9keScpLmF0dHIoJ2NsYXNzJywnZmlsZScpKTtcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIF92aWV3ZXIgPSBudWxsIH0sXG4gICAgICAgICAgICAgICAgICAgICAgICBhbmFseXplcik7XG4gICAgICAgIHJldHVybiBfdmlld2VyO1xuICAgIH07XG4gICAgY29uc3Qgc3RhdCA9IChwYWlwdV9saXN0KT0+e1xuICAgICAgICBmYWRlSW4oJCgnYm9keScpLmF0dHIoJ2NsYXNzJywnc3RhdCcpKTtcbiAgICAgICAgcmV0dXJuIG5ldyBNYWppYW5nLlVJLlBhaXB1U3RhdCgkKCcjc3RhdCcpLCBwYWlwdV9saXN0LFxuICAgICAgICAgICAgICAgICAgICAgICAgKCk9PmZhZGVJbigkKCdib2R5JykuYXR0cignY2xhc3MnLCdmaWxlJykpKTtcbiAgICB9O1xuICAgIGNvbnN0IHByZXZpZXcgPSAocGFpcHUpPT57XG4gICAgICAgICQoJyNib2FyZCAuY29udHJvbGxlcicpLmFkZENsYXNzKCdwYWlwdScpXG4gICAgICAgICQoJ2JvZHknKS5hdHRyKCdjbGFzcycsJ2JvYXJkJyk7XG4gICAgICAgIHNjYWxlKCQoJyNib2FyZCcpLCAkKCcjc3BhY2UnKSk7XG4gICAgICAgIF92aWV3ZXIgPSBuZXcgTWFqaWFuZy5VSS5QYWlwdShcbiAgICAgICAgICAgICAgICAgICAgICAgICQoJyNib2FyZCcpLCBwYWlwdSwgcGFpLCBhdWRpbywgJ01hamlhbmcucHJlZicsXG4gICAgICAgICAgICAgICAgICAgICAgICAoKT0+eyBmYWRlSW4oJCgnYm9keScpLmF0dHIoJ2NsYXNzJywnZWRpdG9yJykpO1xuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgX3ZpZXdlciA9IG51bGwgfSxcbiAgICAgICAgICAgICAgICAgICAgICAgIGFuYWx5emVyKTtcbiAgICAgICAgZGVsZXRlIF92aWV3ZXIuX3ZpZXcuZHVtbXlfbmFtZTtcbiAgICAgICAgcmV0dXJuIF92aWV3ZXI7XG4gICAgfTtcbiAgICBjb25zdCBlZGl0b3IgPSAocGFpcHUsIHNhdmUpPT57XG4gICAgICAgIG5ldyBNYWppYW5nLlVJLlBhaXB1RWRpdG9yKCQoJyNlZGl0b3InKSwgcGFpcHUsIHJ1bGUsIHBhaSxcbiAgICAgICAgICAgICAgICAgICAgICAgICgpPT57IGZpbGUuc3RvcmFnZSh0cnVlKTtcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIGZhZGVJbigkKCdib2R5JykuYXR0cignY2xhc3MnLCdmaWxlJykpIH0sXG4gICAgICAgICAgICAgICAgICAgICAgICBzYXZlLCBwcmV2aWV3KTtcbiAgICAgICAgZmFkZUluKCQoJ2JvZHknKS5hdHRyKCdjbGFzcycsJ2VkaXRvcicpKTtcbiAgICB9O1xuXG4gICAgaWYgKGxvY2F0aW9uLnNlYXJjaCkge1xuICAgICAgICBmaWxlID0gbmV3IE1hamlhbmcuVUkuUGFpcHVGaWxlKFxuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAkKCcjZmlsZScpLCAnTWFqaWFuZy5wYWlwdScsXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIHZpZXdlciwgc3RhdCwgZWRpdG9yLFxuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICB0ZW5ob3VfbG9nLFxuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICBsb2NhdGlvbi5zZWFyY2gucmVwbGFjZSgvXlxcPy8sJycpLFxuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICBsb2NhdGlvbi5oYXNoLnJlcGxhY2UoL14jLywnJykpO1xuICAgIH1cbiAgICBlbHNlIHtcbiAgICAgICAgZmlsZSA9IG5ldyBNYWppYW5nLlVJLlBhaXB1RmlsZShcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgJCgnI2ZpbGUnKSwgJ01hamlhbmcucGFpcHUnLFxuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICB2aWV3ZXIsIHN0YXQsIGVkaXRvcixcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgdGVuaG91X2xvZyk7XG4gICAgfVxuICAgIGZpbGUucmVkcmF3KCk7XG5cbiAgICAkKHdpbmRvdykub24oJ3Jlc2l6ZScsICgpPT5zY2FsZSgkKCcjYm9hcmQnKSwgJCgnI3NwYWNlJykpKTtcbn0pO1xuIl0sIm5hbWVzIjpbXSwic291cmNlUm9vdCI6IiJ9
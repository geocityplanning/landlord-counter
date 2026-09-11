/******/ (() => { // webpackBootstrap
/******/ 	"use strict";
/*!*************************!*\
  !*** ./src/js/paiga.js ***!
  \*************************/
/*!
 *  電脳麻将: 牌画入力 v2.5.3
 *
 *  Copyright(C) 2017 Satoshi Kobayashi
 *  Released under the MIT license
 *  https://github.com/kobalab/Majiang/blob/master/LICENSE
 */


const example = 'このような記述ができます。\n'
              + '{s067z1 z1}(ツモ) {p2-13} {z666=6} {_z77_} {  }(ドラ){m1}';

const imgbase = 'https://kobalab.github.io/paiga/2/';

function markup(paistr, w, h) {

    let url, v = 0;
    let html = '<span style="white-space:pre;">';

    for (let pai of paistr.match(/[mpsz](?:\d\d\=|\d\-|\d)+|[ _]|.+/g)||[]) {

        if (pai == ' ') {
            html += '&nbsp;';
        }
        else if (pai == '_') {
            url = imgbase + 'pai.png';
            html += `<img src="${url}" width="${w}" height="${h}"`
                  + ` alt="${pai}">`;
        }
        else if (pai.match(/^[mpsz](?:\d\d\=|\d\-|\d)+$/)) {
            let s = pai[0];
            for (let n of pai.match(/\d\d\=|\d\-|\d/g)) {
                let url = imgbase, x, y;
                if (n.slice(-1) == '=') {
                    url += s + n.slice(0,2) + '_.png';
                    x = h; y = w * 2;
                }
                else if (n.slice(-1) == '-') {
                    url += s + n.slice(0,1) + '_.png';
                    x = h; y = w;
                }
                else {
                    url += s + n + '.png';
                    x = w; y = h;
                }
                html += `<img src="${url}" width="${x}" height="${y}"`
                            + ` alt="${s+n}">`;
            }
        }
        else {
            html += `<span style="color:red;">${pai}</span>`;
        }
    }
    html += '</span>';
    return html;
}

function parse(text, w, h) {
    return text.replace(/\\.|{(.+?)}/g, (match, mark)=>
        match[0] == '\\' ? match.slice(1)
                         : markup(mark, w, h)
    );
}

$(function(){

    $('textarea[name="text"]').val(example).focus();

    $('form').on('submit', ()=>{

        let [ , w, h ] = $('input[name="size"]:checked').val()
                                                        .match(/^(\d+)x(\d+)$/);
        let text = $('textarea[name="text"]').val();
        let html = parse(text, w, h);
        $('.paiga div')
            .empty()
            .append($(`<p  style="white-space:pre-line">${html}</p>`));
        $('.paiga textarea').val(html).select();

        return false;
    });

    $('form').on('reset', ()=>{
        $('.paiga div').empty();
        $('.paiga textarea').val('');
        $('textarea[name="text"]').focus();
    });
});

/******/ })()
;
//# sourceMappingURL=data:application/json;charset=utf-8;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoicGFpZ2EtMi41LjMuanMiLCJtYXBwaW5ncyI6Ijs7Ozs7QUFBQTtBQUNBO0FBQ0E7QUFDQTtBQUNBO0FBQ0E7QUFDQTtBQUNhOztBQUViO0FBQ0Esa0JBQWtCLFVBQVUsTUFBTSxRQUFRLFNBQVMsV0FBVyxLQUFLLEdBQUc7O0FBRXRFOztBQUVBOztBQUVBO0FBQ0EsNkNBQTZDOztBQUU3Qzs7QUFFQTtBQUNBLDJCQUEyQjtBQUMzQjtBQUNBO0FBQ0E7QUFDQSxpQ0FBaUMsSUFBSSxXQUFXLEVBQUUsWUFBWSxFQUFFO0FBQ2hFLDZCQUE2QixJQUFJO0FBQ2pDO0FBQ0E7QUFDQTtBQUNBO0FBQ0E7QUFDQTtBQUNBO0FBQ0EsMkJBQTJCO0FBQzNCO0FBQ0E7QUFDQTtBQUNBLDJCQUEyQjtBQUMzQjtBQUNBO0FBQ0E7QUFDQSwyQkFBMkI7QUFDM0I7QUFDQSxxQ0FBcUMsSUFBSSxXQUFXLEVBQUUsWUFBWSxFQUFFO0FBQ3BFLHVDQUF1QyxJQUFJO0FBQzNDO0FBQ0E7QUFDQTtBQUNBLDRDQUE0QyxJQUFJLElBQUk7QUFDcEQ7QUFDQTtBQUNBO0FBQ0E7QUFDQTs7QUFFQTtBQUNBLDhCQUE4QixNQUFNO0FBQ3BDO0FBQ0E7QUFDQTtBQUNBOztBQUVBOztBQUVBOztBQUVBOztBQUVBO0FBQ0E7QUFDQTtBQUNBO0FBQ0E7QUFDQTtBQUNBLDBEQUEwRCxLQUFLO0FBQy9EOztBQUVBO0FBQ0EsS0FBSzs7QUFFTDtBQUNBO0FBQ0E7QUFDQTtBQUNBLEtBQUs7QUFDTCxDQUFDIiwic291cmNlcyI6WyJ3ZWJwYWNrOi8vbWFqaWFuZy8uL3NyYy9qcy9wYWlnYS5qcyJdLCJzb3VyY2VzQ29udGVudCI6WyIvKiFcbiAqICDpm7vohLPpurvlsIY6IOeJjOeUu+WFpeWKmyB2Mi41LjNcbiAqXG4gKiAgQ29weXJpZ2h0KEMpIDIwMTcgU2F0b3NoaSBLb2JheWFzaGlcbiAqICBSZWxlYXNlZCB1bmRlciB0aGUgTUlUIGxpY2Vuc2VcbiAqICBodHRwczovL2dpdGh1Yi5jb20va29iYWxhYi9NYWppYW5nL2Jsb2IvbWFzdGVyL0xJQ0VOU0VcbiAqL1xuXCJ1c2Ugc3RyaWN0XCI7XG5cbmNvbnN0IGV4YW1wbGUgPSAn44GT44Gu44KI44GG44Gq6KiY6L+w44GM44Gn44GN44G+44GZ44CCXFxuJ1xuICAgICAgICAgICAgICArICd7czA2N3oxIHoxfSjjg4Tjg6IpIHtwMi0xM30ge3o2NjY9Nn0ge196NzdffSB7ICB9KOODieODqSl7bTF9JztcblxuY29uc3QgaW1nYmFzZSA9ICdodHRwczovL2tvYmFsYWIuZ2l0aHViLmlvL3BhaWdhLzIvJztcblxuZnVuY3Rpb24gbWFya3VwKHBhaXN0ciwgdywgaCkge1xuXG4gICAgbGV0IHVybCwgdiA9IDA7XG4gICAgbGV0IGh0bWwgPSAnPHNwYW4gc3R5bGU9XCJ3aGl0ZS1zcGFjZTpwcmU7XCI+JztcblxuICAgIGZvciAobGV0IHBhaSBvZiBwYWlzdHIubWF0Y2goL1ttcHN6XSg/OlxcZFxcZFxcPXxcXGRcXC18XFxkKSt8WyBfXXwuKy9nKXx8W10pIHtcblxuICAgICAgICBpZiAocGFpID09ICcgJykge1xuICAgICAgICAgICAgaHRtbCArPSAnJm5ic3A7JztcbiAgICAgICAgfVxuICAgICAgICBlbHNlIGlmIChwYWkgPT0gJ18nKSB7XG4gICAgICAgICAgICB1cmwgPSBpbWdiYXNlICsgJ3BhaS5wbmcnO1xuICAgICAgICAgICAgaHRtbCArPSBgPGltZyBzcmM9XCIke3VybH1cIiB3aWR0aD1cIiR7d31cIiBoZWlnaHQ9XCIke2h9XCJgXG4gICAgICAgICAgICAgICAgICArIGAgYWx0PVwiJHtwYWl9XCI+YDtcbiAgICAgICAgfVxuICAgICAgICBlbHNlIGlmIChwYWkubWF0Y2goL15bbXBzel0oPzpcXGRcXGRcXD18XFxkXFwtfFxcZCkrJC8pKSB7XG4gICAgICAgICAgICBsZXQgcyA9IHBhaVswXTtcbiAgICAgICAgICAgIGZvciAobGV0IG4gb2YgcGFpLm1hdGNoKC9cXGRcXGRcXD18XFxkXFwtfFxcZC9nKSkge1xuICAgICAgICAgICAgICAgIGxldCB1cmwgPSBpbWdiYXNlLCB4LCB5O1xuICAgICAgICAgICAgICAgIGlmIChuLnNsaWNlKC0xKSA9PSAnPScpIHtcbiAgICAgICAgICAgICAgICAgICAgdXJsICs9IHMgKyBuLnNsaWNlKDAsMikgKyAnXy5wbmcnO1xuICAgICAgICAgICAgICAgICAgICB4ID0gaDsgeSA9IHcgKiAyO1xuICAgICAgICAgICAgICAgIH1cbiAgICAgICAgICAgICAgICBlbHNlIGlmIChuLnNsaWNlKC0xKSA9PSAnLScpIHtcbiAgICAgICAgICAgICAgICAgICAgdXJsICs9IHMgKyBuLnNsaWNlKDAsMSkgKyAnXy5wbmcnO1xuICAgICAgICAgICAgICAgICAgICB4ID0gaDsgeSA9IHc7XG4gICAgICAgICAgICAgICAgfVxuICAgICAgICAgICAgICAgIGVsc2Uge1xuICAgICAgICAgICAgICAgICAgICB1cmwgKz0gcyArIG4gKyAnLnBuZyc7XG4gICAgICAgICAgICAgICAgICAgIHggPSB3OyB5ID0gaDtcbiAgICAgICAgICAgICAgICB9XG4gICAgICAgICAgICAgICAgaHRtbCArPSBgPGltZyBzcmM9XCIke3VybH1cIiB3aWR0aD1cIiR7eH1cIiBoZWlnaHQ9XCIke3l9XCJgXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgKyBgIGFsdD1cIiR7cytufVwiPmA7XG4gICAgICAgICAgICB9XG4gICAgICAgIH1cbiAgICAgICAgZWxzZSB7XG4gICAgICAgICAgICBodG1sICs9IGA8c3BhbiBzdHlsZT1cImNvbG9yOnJlZDtcIj4ke3BhaX08L3NwYW4+YDtcbiAgICAgICAgfVxuICAgIH1cbiAgICBodG1sICs9ICc8L3NwYW4+JztcbiAgICByZXR1cm4gaHRtbDtcbn1cblxuZnVuY3Rpb24gcGFyc2UodGV4dCwgdywgaCkge1xuICAgIHJldHVybiB0ZXh0LnJlcGxhY2UoL1xcXFwufHsoLis/KX0vZywgKG1hdGNoLCBtYXJrKT0+XG4gICAgICAgIG1hdGNoWzBdID09ICdcXFxcJyA/IG1hdGNoLnNsaWNlKDEpXG4gICAgICAgICAgICAgICAgICAgICAgICAgOiBtYXJrdXAobWFyaywgdywgaClcbiAgICApO1xufVxuXG4kKGZ1bmN0aW9uKCl7XG5cbiAgICAkKCd0ZXh0YXJlYVtuYW1lPVwidGV4dFwiXScpLnZhbChleGFtcGxlKS5mb2N1cygpO1xuXG4gICAgJCgnZm9ybScpLm9uKCdzdWJtaXQnLCAoKT0+e1xuXG4gICAgICAgIGxldCBbICwgdywgaCBdID0gJCgnaW5wdXRbbmFtZT1cInNpemVcIl06Y2hlY2tlZCcpLnZhbCgpXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIC5tYXRjaCgvXihcXGQrKXgoXFxkKykkLyk7XG4gICAgICAgIGxldCB0ZXh0ID0gJCgndGV4dGFyZWFbbmFtZT1cInRleHRcIl0nKS52YWwoKTtcbiAgICAgICAgbGV0IGh0bWwgPSBwYXJzZSh0ZXh0LCB3LCBoKTtcbiAgICAgICAgJCgnLnBhaWdhIGRpdicpXG4gICAgICAgICAgICAuZW1wdHkoKVxuICAgICAgICAgICAgLmFwcGVuZCgkKGA8cCAgc3R5bGU9XCJ3aGl0ZS1zcGFjZTpwcmUtbGluZVwiPiR7aHRtbH08L3A+YCkpO1xuICAgICAgICAkKCcucGFpZ2EgdGV4dGFyZWEnKS52YWwoaHRtbCkuc2VsZWN0KCk7XG5cbiAgICAgICAgcmV0dXJuIGZhbHNlO1xuICAgIH0pO1xuXG4gICAgJCgnZm9ybScpLm9uKCdyZXNldCcsICgpPT57XG4gICAgICAgICQoJy5wYWlnYSBkaXYnKS5lbXB0eSgpO1xuICAgICAgICAkKCcucGFpZ2EgdGV4dGFyZWEnKS52YWwoJycpO1xuICAgICAgICAkKCd0ZXh0YXJlYVtuYW1lPVwidGV4dFwiXScpLmZvY3VzKCk7XG4gICAgfSk7XG59KTtcbiJdLCJuYW1lcyI6W10sInNvdXJjZVJvb3QiOiIifQ==
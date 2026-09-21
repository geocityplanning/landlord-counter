/**
 * 掼蛋核心规则模块
 * 包含牌型定义、牌型解析、出牌校验、贡牌逻辑、升级规则
 */

const GameRules = (function() {
    'use strict';

    /**
     * 牌值常量
     * 掼蛋中2最小，A最大（作为级牌时除外）
     */
    const PAI_ZHI = {
        ER: 2, SAN: 3, SI: 4, WU: 5, LIU: 6, QI: 7, BA: 8, JIU: 9, SHI: 10,
        J: 11, Q: 12, K: 13, A: 14,
        XIAO_WANG: 15, DA_WANG: 16
    };

    /**
     * 花色常量
     */
    const HUA_SE = {
        HEI_TAO: 0, HONG_TAO: 1, MEI_HUA: 2, FANG_KUAI: 3,
        WANG: 4
    };

    /**
     * 牌型常量
     */
    const PAI_XING = {
        WU_XIAO: 0,           // 无效牌型
        DAN_ZHANG: 1,         // 单张
        DUI_ZI: 2,            // 对子
        SAN_ZHANG: 3,         // 三张
        SAN_DAI_ER: 4,        // 三带二（必须是三+对）
        SHUN_ZI: 5,           // 顺子（**恰好 5 张** ✓ 官方规则）
                    LIAN_DUI: 6,          // 连对（**恰好 3 对** ✓ 官方规则）
        GANG_BAN: 9,          // 钢板（两个三张 —— 恰好 2 组 ✓）
        ZHA_DAN: 10,          // 炸弹（4~8张相同 ✓ 两副牌同点最多 8 张）
        TONG_HUA_SHUN: 11,    // 同花顺（恰好 5 张 ✓）
        TIAN_WANG_ZHA: 12     // 天王炸（4个王）
        // ★★ 2026-09-21(用户查证官方规则): 掼蛋**没有 飞机/四带二/三连** ✗(那是斗地主的)
        //    7/8/13 三个编号从此不用(保留空洞, 不动其它编号 ✓)
    };

    /**
     * 牌型名称
     */
    const PAI_XING_NAME = {
        0: '无效', 1: '单张', 2: '对子', 3: '三张',
        4: '三带二', 5: '顺子', 6: '连对',
        9: '钢板', 10: '炸弹', 11: '同花顺',
        12: '天王炸'
    };

    /**
     * 当前级牌（默认从2开始）
     */
    let dangQianJiPai = PAI_ZHI.ER;

    /**
     * 设置当前级牌
     */
    function sheZhiJiPai(zhi) {
        dangQianJiPai = zhi;
    }

    /**
     * 获取实际牌值（考虑级牌）
     * 级牌在该局中比A大
     */
    function huoQuShiJiPaiZhi(zhi) {
        // 小王、大王始终最大
        if (zhi >= PAI_ZHI.XIAO_WANG) return zhi + 100;
        
        // 级牌在该局中最大（仅次于王）
        if (zhi === dangQianJiPai) return zhi + 50;
        
        // A是第二大的（级牌除外）
        if (zhi === PAI_ZHI.A) return zhi + 30;
        
        return zhi;
    }

    /**
     * 判断是否是级牌
     */
    function shiJiPai(zhi) {
        return zhi === dangQianJiPai;
    }

    /**
     * 判断是否是主牌（红桃级牌）
     */
    function shiZhuPai(pai) {
        return pai.zhi === dangQianJiPai && pai.hua === HUA_SE.HONG_TAO;
    }

    /**
     * 创建两副完整牌（108张）
     */
    function chuangJianPaiZu() {
        const paiZu = [];
        let id = 0;

        // 创建两副普通牌（不含王）
        for (let fu = 0; fu < 2; fu++) {
            for (let zhi = PAI_ZHI.ER; zhi <= PAI_ZHI.A; zhi++) {
                for (let hua = HUA_SE.HEI_TAO; hua <= HUA_SE.FANG_KUAI; hua++) {
                    paiZu.push({ zhi, hua, id: id++ });
                }
            }
        }

        // 添加4张王（2小王+2大王）
        for (let i = 0; i < 2; i++) {
            paiZu.push({ zhi: PAI_ZHI.XIAO_WANG, hua: HUA_SE.WANG, id: id++ });
            paiZu.push({ zhi: PAI_ZHI.DA_WANG, hua: HUA_SE.WANG, id: id++ });
        }

        return paiZu;
    }

    /**
     * 洗牌
     */
    function xiPai(paiZu) {
        const xiHao = [...paiZu];
        for (let i = xiHao.length - 1; i > 0; i--) {
            const j = Math.floor(Math.random() * (i + 1));
            [xiHao[i], xiHao[j]] = [xiHao[j], xiHao[i]];
        }
        return xiHao;
    }

    /**
     * 发牌（4人，每人27张）
     */
    function faPai() {
        const paiZu = xiPai(chuangJianPaiZu());
        
        return {
            wanJia1Pai: paiZu.slice(0, 27),
            ai1Pai: paiZu.slice(27, 54),
            ai2Pai: paiZu.slice(54, 81),
            ai3Pai: paiZu.slice(81, 108)
        };
    }

    /**
     * 按牌值排序（从大到小，考虑级牌）
     */
    function paiXu(paiList) {
        return [...paiList].sort((a, b) => {
            const zhiA = huoQuShiJiPaiZhi(a.zhi);
            const zhiB = huoQuShiJiPaiZhi(b.zhi);
            if (zhiB !== zhiA) return zhiB - zhiA;
            return a.hua - b.hua;
        });
    }

    /**
     * 统计各牌值出现次数
     */
    function tongJiPaiZhi(paiList) {
        const tongJi = new Map();
        for (const pai of paiList) {
            const count = tongJi.get(pai.zhi) || 0;
            tongJi.set(pai.zhi, count + 1);
        }
        return tongJi;
    }

    /**
     * 按出现次数分组
     */
    function fenZu(tongJi) {
        const result = { dan: [], dui: [], san: [], si: [], wu: [], liu: [] };
        for (const [zhi, count] of tongJi) {
            if (count === 1) result.dan.push(zhi);
            else if (count === 2) result.dui.push(zhi);
            else if (count === 3) result.san.push(zhi);
            else if (count === 4) result.si.push(zhi);
            else if (count === 5) result.wu.push(zhi);
            else if (count >= 6) result.liu.push(zhi);
        }
        // 排序
        for (const key of Object.keys(result)) {
            result[key].sort((a, b) => huoQuShiJiPaiZhi(b) - huoQuShiJiPaiZhi(a));
        }
        return result;
    }

    /**
     * 检查是否连续（不含王和2）
     */
    function shiFouLianXu(zhiList, minLen = 1) {
        if (zhiList.length < minLen) return false;
        
        // 王和2不能参与顺子
        for (const zhi of zhiList) {
            if (zhi >= PAI_ZHI.XIAO_WANG || zhi === PAI_ZHI.ER) return false;
        }
        
        // 检查连续性
        const sorted = [...zhiList].sort((a, b) => a - b);
        for (let i = 1; i < sorted.length; i++) {
            if (sorted[i] !== sorted[i - 1] + 1) return false;
        }
        return true;
    }

    /**
     * 解析牌型
     */
    // ★★ 2026-09-21 用户定: **逢人配** —— 红桃级牌可当任意牌(掼蛋普遍规则) ✓
    //   背景: 游戏本身只定义了 shiZhuPai() 却没在解析牌型时用它 ✗
    //        ⇒ 托管侧算出的合法牌型被游戏判"无效的牌型组合" ⇒ 出牌被拒 ⇒ 卡死
    //        (实测: 想用 ♥2+♠4♦4 出 444, 游戏回"无效的牌型组合" ✓)
    //   做法: 抽出红桃级牌(逢人配) ⇒ 枚举它替代的点数(2..A, 不能替王) ⇒
    //        用**官方比较函数** biJiaoPaiXing 取能组出的最大牌型 ✓
    function jieXiPaiXing(paiList) {
        if (!paiList || paiList.length === 0) {
            return { xing: PAI_XING.WU_XIAO, zhuZhi: 0, changDu: 0 };
        }
        const wilds = paiList.filter(shiZhuPai);
        if (wilds.length === 0) {
            return jieXiPaiXingYuanShi(paiList);
        }
        const others = paiList.filter(function (p) { return !shiZhuPai(p); });
        let best = null;
        for (let zhi = PAI_ZHI.ER; zhi <= PAI_ZHI.A; zhi++) {
            const fake = others.concat(wilds.map(function (w) {
                return { zhi: zhi, hua: w.hua, id: w.id };
            }));
            const r = jieXiPaiXingYuanShi(fake);
            if (r.xing === PAI_XING.WU_XIAO) continue;
            if (!best || biJiaoPaiXing(r, best) > 0) best = r;
        }
        return best || { xing: PAI_XING.WU_XIAO, zhuZhi: 0, changDu: 0 };
    }

    function jieXiPaiXingYuanShi(paiList) {
        if (!paiList || paiList.length === 0) {
            return { xing: PAI_XING.WU_XIAO, zhuZhi: 0, changDu: 0 };
        }

        const n = paiList.length;
        const tongJi = tongJiPaiZhi(paiList);
        const fz = fenZu(tongJi);

        // 天王炸：4个王
        const wangCount = (tongJi.get(PAI_ZHI.XIAO_WANG) || 0) + (tongJi.get(PAI_ZHI.DA_WANG) || 0);
        if (wangCount === 4 && n === 4) {
            return { xing: PAI_XING.TIAN_WANG_ZHA, zhuZhi: 100, changDu: 4 };
        }

        // 单张
        if (n === 1) {
            return { xing: PAI_XING.DAN_ZHANG, zhuZhi: huoQuShiJiPaiZhi(paiList[0].zhi), changDu: 1 };
        }

        // 对子
        if (n === 2 && fz.dui.length === 1) {
            return { xing: PAI_XING.DUI_ZI, zhuZhi: huoQuShiJiPaiZhi(fz.dui[0]), changDu: 1 };
        }

        // 三张
        if (n === 3 && fz.san.length === 1) {
            return { xing: PAI_XING.SAN_ZHANG, zhuZhi: huoQuShiJiPaiZhi(fz.san[0]), changDu: 1 };
        }

        // 三带二（三张+对子）
        if (n === 5 && fz.san.length === 1 && fz.dui.length === 1) {
            return { xing: PAI_XING.SAN_DAI_ER, zhuZhi: huoQuShiJiPaiZhi(fz.san[0]), changDu: 1 };
        }

        // 炸弹（4~8张相同 ✓ 官方: 四张及以上; 两副牌同点最多 8 张）
        if (n >= 4 && n <= 8) {
            if (fz.si.length === 1 && n === 4) {
                return { xing: PAI_XING.ZHA_DAN, zhuZhi: huoQuShiJiPaiZhi(fz.si[0]), changDu: 4 };
            }
            if (fz.wu.length === 1 && n === 5) {
                return { xing: PAI_XING.ZHA_DAN, zhuZhi: huoQuShiJiPaiZhi(fz.wu[0]), changDu: 5 };
            }
            if (fz.liu.length === 1 && n >= 6) {     // 6/7/8 张都落在 liu 桶(≥6) ✓
                return { xing: PAI_XING.ZHA_DAN, zhuZhi: huoQuShiJiPaiZhi(fz.liu[0]), changDu: n };
            }
        }
        // (2026-09-21 删) 四带二 —— 斗地主牌型, 掼蛋没有 ✗

        // 钢板（两个三张）
        if (n === 6 && fz.san.length === 2) {
            const sanList = fz.san.sort((a, b) => a - b);
            if (shiFouLianXu(sanList)) {
                return { xing: PAI_XING.GANG_BAN, zhuZhi: huoQuShiJiPaiZhi(sanList[1]), changDu: 2 };
            }
        }

        // 同花顺（★ 官方: **恰好 5 张** ✓ —— 原来 n>=5 ✗ 是斗地主式放宽）
        if (n === 5) {
            const huaSeMap = new Map();
            for (const pai of paiList) {
                if (!huaSeMap.has(pai.hua)) huaSeMap.set(pai.hua, []);
                huaSeMap.get(pai.hua).push(pai.zhi);
            }
            
            for (const [hua, zhiList] of huaSeMap) {
                if (zhiList.length === n && shiFouLianXu(zhiList)) {
                    const maxZhi = Math.max(...zhiList);
                    return { xing: PAI_XING.TONG_HUA_SHUN, zhuZhi: huoQuShiJiPaiZhi(maxZhi), changDu: n, huaSe: hua };
                }
            }
        }

        // 顺子（★ 官方: **恰好 5 张** ✓）
        if (n === 5 && fz.dan.length === 5) {
            if (shiFouLianXu(fz.dan)) {
                return { xing: PAI_XING.SHUN_ZI, zhuZhi: huoQuShiJiPaiZhi(fz.dan[0]), changDu: n };
            }
        }

        // 连对（★ 官方: **恰好 3 对** ✓ —— 不可二连对, 也不可四连对以上）
        if (n === 6 && fz.dui.length === 3) {
            if (shiFouLianXu(fz.dui)) {
                return { xing: PAI_XING.LIAN_DUI, zhuZhi: huoQuShiJiPaiZhi(fz.dui[0]), changDu: 3 };
            }
        }

        // (2026-09-21 删) 三连(>=3组) 与 飞机 —— 都是斗地主牌型, 掼蛋没有 ✗
        //   注: "两个连续三张"在掼蛋里叫**钢板**, 上面已处理 ✓

        return { xing: PAI_XING.WU_XIAO, zhuZhi: 0, changDu: 0 };
    }

    /**
     * 比较牌型大小
     * @returns {number} 1=前者大, -1=后者大, 0=相等
     */
    function biJiaoPaiXing(paiXing1, paiXing2) {
        // 天王炸最大
        if (paiXing1.xing === PAI_XING.TIAN_WANG_ZHA) return 1;
        if (paiXing2.xing === PAI_XING.TIAN_WANG_ZHA) return -1;

        // 同花顺 > 普通炸弹
        if (paiXing1.xing === PAI_XING.TONG_HUA_SHUN && paiXing2.xing === PAI_XING.ZHA_DAN) {
            if (paiXing1.changDu >= paiXing2.changDu) return 1;
            return -1;
        }
        if (paiXing2.xing === PAI_XING.TONG_HUA_SHUN && paiXing1.xing === PAI_XING.ZHA_DAN) {
            if (paiXing2.changDu >= paiXing1.changDu) return -1;
            return 1;
        }

        // 炸弹比较
        if (paiXing1.xing === PAI_XING.ZHA_DAN && paiXing2.xing !== PAI_XING.ZHA_DAN &&
            paiXing2.xing !== PAI_XING.TONG_HUA_SHUN) return 1;
        if (paiXing2.xing === PAI_XING.ZHA_DAN && paiXing1.xing !== PAI_XING.ZHA_DAN &&
            paiXing1.xing !== PAI_XING.TONG_HUA_SHUN) return -1;

        // 同花顺比较
        if (paiXing1.xing === PAI_XING.TONG_HUA_SHUN && paiXing2.xing !== PAI_XING.TONG_HUA_SHUN) return 1;
        if (paiXing2.xing === PAI_XING.TONG_HUA_SHUN && paiXing1.xing !== PAI_XING.TONG_HUA_SHUN) return -1;

        // 同牌型比较
        if (paiXing1.xing === paiXing2.xing && paiXing1.changDu === paiXing2.changDu) {
            if (paiXing1.zhuZhi > paiXing2.zhuZhi) return 1;
            if (paiXing1.zhuZhi < paiXing2.zhuZhi) return -1;
            return 0;
        }

        // 不同牌型，不能比较
        return null;
    }

    /**
     * 验证出牌
     */
    function yanZhengChuPai(chuPai, shouPai, shangJiaPaiXing) {
        if (!chuPai || chuPai.length === 0) {
            return { valid: false, reason: '请选择要出的牌' };
        }

        // 检查是否拥有这些牌
        const shouPaiIds = new Set(shouPai.map(p => p.id));
        for (const pai of chuPai) {
            if (!shouPaiIds.has(pai.id)) {
                return { valid: false, reason: '你没有这些牌' };
            }
        }

        const paiXing = jieXiPaiXing(chuPai);
        
        if (paiXing.xing === PAI_XING.WU_XIAO) {
            return { valid: false, reason: '无效的牌型组合' };
        }

        // 自由出牌
        if (!shangJiaPaiXing || shangJiaPaiXing.xing === PAI_XING.WU_XIAO) {
            return { valid: true, paiXing };
        }

        // 比较
        const biJiao = biJiaoPaiXing(paiXing, shangJiaPaiXing);
        
        if (biJiao === null) {
            return { valid: false, reason: '牌型不匹配，无法压过' };
        }
        
        if (biJiao > 0) {
            return { valid: true, paiXing };
        }

        return { valid: false, reason: '牌太小，压不过' };
    }

    /**
     * 贡牌逻辑：找出最大的牌
     */
    function zhaoZuiDaPai(shouPai) {
        if (!shouPai || shouPai.length === 0) return null;
        
        const paiXuPai = paiXu(shouPai);
        return paiXuPai[0];
    }

    /**
     * 还牌逻辑：找出最小的牌（非级牌）
     */
    function zhaoZuiXiaoPai(shouPai, excludeId) {
        if (!shouPai || shouPai.length === 0) return null;
        
        const paiXuPai = paiXu(shouPai);
        // 从后往前找最小的
        for (let i = paiXuPai.length - 1; i >= 0; i--) {
            if (paiXuPai[i].id !== excludeId) {
                return paiXuPai[i];
            }
        }
        return paiXuPai[paiXuPai.length - 1];
    }

    /**
     * 升级计算
     * @param {number} youCi 游次（1=头游, 2=二游, 3=三游, 4=末游）
     * @param {number} duiYouYouCi 队友游次
     * @returns {number} 升级数
     */
    function jiSuanShengJi(youCi, duiYouYouCi) {
        // 双下：对手双游，升3级
        if (youCi >= 3 && duiYouYouCi >= 3) return 3;
        
        // 双上：己方双游，升3级
        if (youCi <= 2 && duiYouYouCi <= 2) return 3;
        
        // 单下：对手头游，升2级
        if (youCi === 4 || duiYouYouCi === 4) return 2;
        
        // 正常：升1级
        return 1;
    }

    /**
     * 获取下一个级牌
     */
    function huoQuXiaYiJiPai(dangQian) {
        if (dangQian >= PAI_ZHI.A) return PAI_ZHI.A; // A打完还是A（逢A必打）
        return dangQian + 1;
    }

    /**
     * 获取牌面显示文本
     */
    function getPaiMian(zhi) {
        if (zhi === PAI_ZHI.XIAO_WANG) return '🃏';
        if (zhi === PAI_ZHI.DA_WANG) return '👑';
        if (zhi >= PAI_ZHI.ER && zhi <= PAI_ZHI.SHI) return String(zhi);
        if (zhi === PAI_ZHI.J) return 'J';
        if (zhi === PAI_ZHI.Q) return 'Q';
        if (zhi === PAI_ZHI.K) return 'K';
        if (zhi === PAI_ZHI.A) return 'A';
        return '';
    }

    /**
     * 获取花色符号
     */
    function getHuaSeFuHao(hua) {
        switch (hua) {
            case HUA_SE.HEI_TAO: return '♠';
            case HUA_SE.HONG_TAO: return '♥';
            case HUA_SE.MEI_HUA: return '♣';
            case HUA_SE.FANG_KUAI: return '♦';
            default: return '';
        }
    }

    /**
     * 判断是否红色花色
     */
    function shiHongSe(hua) {
        return hua === HUA_SE.HONG_TAO || hua === HUA_SE.FANG_KUAI;
    }

    /**
     * 获取级牌名称
     */
    function huoQuJiPaiMingCheng(zhi) {
        return getPaiMian(zhi);
    }

    return {
        PAI_ZHI,
        HUA_SE,
        PAI_XING,
        PAI_XING_NAME,
        sheZhiJiPai,
        huoQuShiJiPaiZhi,
        shiJiPai,
        shiZhuPai,
        chuangJianPaiZu,
        xiPai,
        faPai,
        paiXu,
        tongJiPaiZhi,
        fenZu,
        jieXiPaiXing,
        biJiaoPaiXing,
        yanZhengChuPai,
        zhaoZuiDaPai,
        zhaoZuiXiaoPai,
        jiSuanShengJi,
        huoQuXiaYiJiPai,
        getPaiMian,
        getHuaSeFuHao,
        shiHongSe,
        huoQuJiPaiMingCheng,
        get dangQianJiPai() { return dangQianJiPai; }
    };
})();

if (typeof module !== 'undefined' && module.exports) {
    module.exports = GameRules;
}

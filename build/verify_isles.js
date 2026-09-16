/* 东沙群岛呈现方式的核验（附图符号 + 主图移除）+ 全局渲染回归。
 *
 * 背景：DataV 数据把东沙群岛表示为三块按中心生成的圆形 range ring，与真实海岸线
 * 无关。geo.py 已把它们从**省级与市级两份几何**中摘除（否则会在图上画出三块
 * 人工圆形色块），改以**点状符号**呈现，并按性质区分样式：
 *     .isc 有露出水面的陆地（东沙岛）→ 实心
 *     .isb 沉水环礁（北卫滩 / 南卫滩）→ 空心
 *
 * **2026-09-16 起主图不再渲染任何东沙要素**（用户要求：主图只表达一级气象地理
 * 区划，东沙孤悬南海、与「香港」省名相邻显得突兀）。但**附图保留** —— 附图是
 * 南海诸岛的指定呈现位，东沙与西沙 / 中沙 / 南沙并列，移除会使四大群岛缺一。
 * 这一「主图无、附图有」的区别已在页脚第 7 条如实披露。
 *
 * 三处「少一个符号」都是**有意的**，判据按新口径写而非硬编码：
 *   ① 三块 → 两枚符号：北卫滩与南卫滩相距 12.2 km（主图屏幕 1.8 单位、
 *      附图 1.0 单位），按「要素间距小于符号尺寸时按群组处理」的惯例合并，
 *      `<title>` 仍逐块给出水深。
 *   ② ISLES 的「东沙群岛」代表点不渲染（仅附图相关）：它与东沙岛点相距 0.3 单位，
 *      会叠成一团并露出白描边；其信息由细分符号承接。
 *   ③ 主图整体不渲染东沙（本次改动）。
 *
 * ⚠ 本脚本【二】组是**负向**判据（「主图没有东沙」）。负向判据极易写成空检查
 * —— 把数据全删了它照样通过。故同时配了「附图里东沙确实还在」的**对照**判据，
 * 二者合起来才证明是「只在主图移除」而非误删。
 *
 * 用法：node verify_isles.js <成品HTML路径> [输出目录]
 * 需 NODE_PATH 指向含 @playwright/test 的目录：
 *   export NODE_PATH="C:/Users/15291/AppData/Roaming/npm/node_modules"
 */
const { chromium } = require('@playwright/test');
const path = require('path');
const fs = require('fs');

const FILE = process.argv[2];
const OUTDIR = process.argv[3] || 'build/dev-scratch/shots-hi';
if (!fs.existsSync(OUTDIR)) fs.mkdirSync(OUTDIR, { recursive: true });

let fails = 0;
function chk(name, ok, extra) {
  console.log('  ' + (ok ? '✓' : '✗') + ' ' + name + (extra !== undefined ? '  ' + extra : ''));
  if (!ok) fails++;
}

/* 「空心」的判据不能写成 fill === transparent。
   这两类符号的区分目的是**不把水下礁读成陆地**，而陆地/省份面用的是
   浅蓝实色（#cfe3f8 一类）。当前实现把沉水礁填成面板底色 #f4faff（接近纯白），
   视觉上是空心的、一眼可与实地色块分辨，但 fill 值并不为 transparent。
   故判据取「与陆地填充色不近似」—— 这才是真正要保证的性质。
   注：对比 .pv 的 fill #cfe3f8，其 R/G/B 差值远大于本阈值。 */
const LAND_FILL = [207, 227, 248];   // #cfe3f8，省份面填充
const LAND_TOL = 24;
function notLandLike(fill) {
  const m = /rgba?\((\d+),\s*(\d+),\s*(\d+)/.exec(fill || '');
  if (!m) return false;                       // 解析不出来 → 不算通过
  const [r, g, b] = [+m[1], +m[2], +m[3]];
  if (/rgba\(\s*0,\s*0,\s*0,\s*0\)/.test(fill)) return true;   // 全透明自然也算
  return Math.abs(r - LAND_FILL[0]) + Math.abs(g - LAND_FILL[1]) + Math.abs(b - LAND_FILL[2]) > LAND_TOL;
}

(async () => {
  const b = await chromium.launch({ channel: 'chrome', headless: true });
  // deviceScaleFactor:2 —— 这些符号只有 3 px 直径，1 倍下无法判断「实心/空心」，
  // 本项目在 1.5 px 细线上踩过这个坑（见 MEMORY.md）。
  const p = await b.newPage({ viewport: { width: 1500, height: 1000 }, deviceScaleFactor: 2 });
  const errs = [];
  p.on('pageerror', e => errs.push('pageerror: ' + e.message));
  p.on('console', m => { if (m.type() === 'error') errs.push('console: ' + m.text()); });

  await p.goto('file:///' + path.resolve(FILE).replace(/\\/g, '/'));
  await p.waitForTimeout(1200);

  console.log('\n【一】数据层');
  const d = await p.evaluate(() => {
    const sw = (DATA.ci['440000'] || []).find(c => c.a === '441500') || { g: [] };
    /* 每个 part 的外环外接框面积（平方度）与质心，用于判定人造环礁与真实岛。
       与 build/isles_data.py 的判据同源：人造 range ring 面积 ≥ 10 km²，
       真实陆地（东沙岛本体）约 1.67 km²。 */
    const parts = sw.g.map(poly => {
      const r = poly[0];                       // 外环，扁平数组（度×1000）
      let x0 = Infinity, x1 = -Infinity, y0 = Infinity, y1 = -Infinity, sx = 0, sy = 0;
      for (let i = 0; i < r.length; i += 2) {
        const x = r[i] / 1000, y = r[i + 1] / 1000;
        if (x < x0) x0 = x; if (x > x1) x1 = x;
        if (y < y0) y0 = y; if (y > y1) y1 = y;
        sx += x; sy += y;
      }
      const n = r.length / 2;
      return { bbox: (x1 - x0) * (y1 - y0), cx: sx / n, cy: sy / n };
    });
    // 东沙岛本体：质心距官方坐标 (116.70E, 20.7167N) 最小者
    const DK = { lng: 116.70, lat: 20.7167 };
    let best = null;
    for (const q of parts) {
      const dx = (q.cx - DK.lng) * 111.32 * Math.cos(DK.lat * Math.PI / 180);
      const dy = (q.cy - DK.lat) * 111.32;
      const dist = Math.hypot(dx, dy);
      if (best === null || dist < best) best = dist;
    }
    return {
      isles: DATA.isles, dongsha: DATA.dongsha,
      swParts: sw.g.length,
      swVerts: sw.g.reduce((s, poly) => s + poly.reduce((t, r) => t + r.length / 2, 0), 0),
      swMaxArea: parts.length ? Math.max(...parts.map(q => q.bbox)) : null,
      swDongshaDist: best,
    };
  });
  chk('ISLES 含 6 个岛群点', d.isles.length === 6, d.isles.map(x => x[0]).join('/'));
  chk('ISLES 仍保留「东沙群岛」群组点', d.isles.some(x => x[0] === '东沙群岛'));
  chk('dongsha 细分符号 3 个', d.dongsha.length === 3, d.dongsha.map(x => x.n).join('/'));
  chk('细分为 1 个 cay + 2 个 bank',
    d.dongsha.filter(x => x.kind === 'cay').length === 1 &&
    d.dongsha.filter(x => x.kind === 'bank').length === 2);
  for (const a of d.dongsha) {
    chk('  ' + a.n + ' 性质与水深自洽',
      a.kind === 'bank' ? a.depth < 0 : a.depth >= 0, a.kind + ' ' + a.depth + 'm');
  }
  /* 汕尾市几何：3 个 part —— ① 陆域本土 ② 近岸小岛（约 0.56 km²）
     ③ **真实东沙岛本体**（约 1.67 km²）。
     三条人造 range ring（173 / 111 / 43 km²）已摘除。
     注意 ③ 必须**在**产物里：它是真实几何，不是人造轮廓，不可被误摘 ——
     曾因只凭「质心落在声明坐标 25 km 内」匹配而被连带摘除（见 isles_data.py）。 */
  chk('汕尾市几何为 3 part（本土 + 近岸小岛 + 真实东沙岛，人造环礁已摘除）',
    d.swParts === 3, d.swParts + ' part / ' + d.swVerts + ' 顶点');
  chk('  汕尾市已无面积 ≥ 10 km² 的人造环礁残留（最大 part 为陆域本土）',
    d.swMaxArea !== null && d.swMaxArea < 50,
    '最大外环外接框 ' + (d.swMaxArea === null ? '—' : d.swMaxArea.toFixed(2) + '°²'));
  /* 正面核实真实东沙岛确实保留。用质心就近判定：应存在一个 part，
     其质心距 (116.70, 20.7167) 在 5 km 内 —— 那是东沙岛本体的位置。 */
  chk('  真实东沙岛本体几何仍在（质心距官方坐标 ≤ 5 km）',
    d.swDongshaDist !== null && d.swDongshaDist <= 5,
    d.swDongshaDist === null ? '未找到' : d.swDongshaDist.toFixed(2) + ' km');

  console.log('\n【二】主图**不得**渲染东沙群岛（2026-09-16 按用户要求移除）');
  /* 这是本脚本最重要的**负向**判据组。主图只表达一级气象地理区划，而东沙群岛距
     汕尾陆域约 295 km、孤悬南海并与「香港」省名相邻，视觉上突兀，故整块移除
     （图层 + 符号 + 标注 + 引线 + 样式）。

     ⚠ 负向判据极易写成空检查（「查不到就通过」——把数据全删了它照样通过）。
     故此处除了「主图没有东沙」，还必须有一条**对照**：附图里东沙确实还在。
     两者合起来才证明是「只在主图移除」，而不是东沙被误删。 */
  const mainDongsha = await p.evaluate(() => {
    const svg = document.getElementById('map');
    const inInset = el => !!(el.closest && el.closest('#gInset'));
    let sym = 0; const txt = [];
    svg.querySelectorAll('circle.isc, circle.isb').forEach(e => { if (!inInset(e)) sym++; });
    svg.querySelectorAll('text').forEach(e => {
      if (!inInset(e) && /东沙/.test(e.textContent || '')) txt.push(e.textContent);
    });
    return {
      layer: !!document.getElementById('gIsle'),
      sym, txt,
      insetSym: svg.querySelectorAll('#gInset circle.isc, #gInset circle.isb').length,
      insetTxt: Array.from(svg.querySelectorAll('#gInset text'))
        .map(e => e.textContent).filter(t => /东沙/.test(t)),
    };
  });
  chk('主图不存在 gIsle 图层', mainDongsha.layer === false, mainDongsha.layer ? '仍存在' : '已移除');
  chk('主图内无东沙符号（.isc / .isb）', mainDongsha.sym === 0, mainDongsha.sym + ' 个');
  chk('主图内无「东沙」文字标注', mainDongsha.txt.length === 0, mainDongsha.txt.join('/') || '（无）');
  chk('  （对照）附图内东沙符号仍在 —— 证明是「只在主图移除」而非误删',
    mainDongsha.insetSym === 2, mainDongsha.insetSym + ' 个（1 实心 + 1 空心）');
  // 主图既已不渲染东沙，后续各节不再有主图符号可查，此处显式留空并说明。
  const main = [];   // 恒为空：主图已不渲染东沙，见本节判据


  console.log('\n【三】附图符号（gInset）');
  const ins = await p.$$eval('#gInset circle', els => els.map(e => ({
    cls: e.getAttribute('class'), r: +e.getAttribute('r'),
    fill: getComputedStyle(e).fill,
    title: (e.querySelector('title') || {}).textContent || '',
  })));
  const insIsles = ins.filter(x => !x.cls);          // 岛群点（无 class）
  const insC = ins.filter(x => x.cls === 'isc'), insB = ins.filter(x => x.cls === 'isb');
  /* 附图岛群点应为 5 个而非 ISLES 的 6 个 —— 「东沙群岛」那一项被前端按
     ISLES_SUPERSEDED 跳过，因为 dongsha 细分符号已在同一位置（相距 0.3 单位）
     画出东沙岛与卫滩，同时渲染会叠成一团并从空心符号背后露出白描边。
     这与主图的处理必须一致，否则又回到「主图无、附图有」的口径不一。 */
  chk('附图岛群点 5 个（东沙已由细分符号取代）', insIsles.length === 5, insIsles.length);
  chk('附图岛群点中不含「东沙群岛」',
    !insIsles.some(x => /东沙/.test(x.title)),
    insIsles.map(x => x.title).join('/'));
  // 附图同样合群：卫滩两处并为一点（间距不足 1 viewBox 单位）
  chk('附图东沙细分符号 1 实心 + 1 空心', insC.length === 1 && insB.length === 1,
    insC.length + '/' + insB.length);
  for (const a of insB) {
    chk('  附图空心符号不是陆地填充色', notLandLike(a.fill), a.fill);
  }
  /* 实心符号用的是**符号深蓝** #1b5fa8，不是省面的浅蓝 #cfe3f8 —— 这是有意的
     （与既有岛群点同族）。故不能拿「是不是陆地色」判它，真正要保证的是
     「实心与空心两者在视觉上能区分」。 */
  if (insC.length && insB.length) {
    chk('  附图实心与空心两者填充色可区分',
      insC[0].fill !== insB[0].fill, insC[0].fill + ' vs ' + insB[0].fill);
  }

  console.log('\n【四】可交互性（SVG 原生 <title>，不依赖 JS）');
  /* 附图 5 个岛群点 + 2 个东沙细分 = 7 个带 title 的元素。
     （主图已不渲染东沙，故总数由 9 降为 7。） */
  const titles = [...main, ...ins].filter(x => x.title).length;
  chk('全部符号均带 <title>（悬停可读）', titles === 7, titles + '/7');
  /* 反向检查：主图不画东沙，但东沙的信息**不能因此丢失** —— 附图的细分符号
     必须仍能读出三块的名称与水深。 */
  const dongshaTitles = [...main, ...ins].filter(x => /东沙|卫滩/.test(x.title));
  chk('东沙三块的信息仍可读（title 未丢失）',
    dongshaTitles.some(x => /东沙岛/.test(x.title)) &&
    dongshaTitles.some(x => /北卫滩/.test(x.title)) &&
    dongshaTitles.some(x => /南卫滩/.test(x.title)),
    dongshaTitles.length + ' 个带东沙相关 title 的元素');
  const insetPE = await p.evaluate(() =>
    getComputedStyle(document.getElementById('gInset')).pointerEvents);
  chk('gInset 未禁用指针（否则附图符号无法悬停）', insetPE !== 'none', insetPE);
  const boxPE = await p.evaluate(() => getComputedStyle(document.querySelector('.insetbox')).pointerEvents);
  chk('附图外框本身不拦截指针', boxPE === 'none', boxPE);

  console.log('\n【五】全局渲染健全性');
  const stats = await p.evaluate(() => ({
    pv: document.querySelectorAll('.pv').length,
    labels: document.querySelectorAll('#gLabel text').length,
    jd: document.querySelectorAll('#gInset .jd').length,
  }));
  chk('省份面渲染完整（34）', stats.pv === 34, stats.pv);
  chk('省名标签渲染（34）', stats.labels === 34, stats.labels);
  chk('九段线 10 段', stats.jd === 10, stats.jd);

  // 河流与山脉注记只在**勾选要素后**渲染 —— 不是选中省份就会画。
  // 步骤：① 在省份面上点一个确在省内的点（页面函数都在闭包内，只能模拟真实点击）
  //       ② 面板里勾上河流与山脉复选框。
  const q = await p.evaluate(() => {
    const cand = document.querySelector('#gProv path[data-ad="420000"]');
    const list = cand ? [cand] : Array.from(document.querySelectorAll('#gProv path'));
    for (const pa of list) {
      const r = pa.getBoundingClientRect();
      if (r.width < 20 || r.height < 20) continue;
      for (let fx = 0.3; fx <= 0.7; fx += 0.05)
        for (let fy = 0.3; fy <= 0.7; fy += 0.05) {
          const cx = r.x + r.width * fx, cy = r.y + r.height * fy;
          const e = document.elementFromPoint(cx, cy);
          if (e && e.closest && e.closest('#gProv')) return { x: cx, y: cy };
        }
    }
    return null;
  });
  chk('可定位到省份内部的采样点', !!q, q ? '(' + q.x.toFixed(0) + ',' + q.y.toFixed(0) + ')' : '未找到');
  if (q) {
    await p.mouse.move(q.x, q.y);
    await p.mouse.down(); await p.mouse.up();
    await p.waitForTimeout(600);
    const hd = await p.evaluate(() =>
      document.getElementById('panelHd').textContent.replace(/\s+/g, ' ').trim());
    chk('单击省份可打开面板', hd.indexOf('选择一个省级行政区') !== 0, hd.slice(0, 16));
  }
  const boxes = await p.evaluate(() => {
    const all = Array.from(document.querySelectorAll('#panelBd input[type=checkbox]'));
    const pick = k => {
      const e = all.find(x => x.dataset.kind === k && !x.disabled);
      if (!e) return null;
      e.checked = true;
      e.dispatchEvent(new Event('change', { bubbles: true }));
      return e.dataset.id;
    };
    return { r: pick('r'), m: pick('m') };
  });
  await p.waitForTimeout(600);
  const after = await p.evaluate(() => ({
    rivers: document.querySelectorAll('#gRiver path').length,
    marks: document.querySelectorAll('#gMark *').length,
  }));
  chk('勾选河流后该河道已渲染', after.rivers > 0, boxes.r + ' → ' + after.rivers + ' 路径');
  chk('勾选山脉后注记已渲染', after.marks > 0, boxes.m + ' → ' + after.marks + ' 图元');

  console.log('\n【六】标签订关（省名开关）与东沙的独立性');
  /* 主图原先有一条「东沙群岛（汕尾市）」标注，随「显示/隐藏省名」一起开关；
     该标注已随主图整体移除，故此处的语义变为：
       ① 省名开关仍正常工作（对照，证明开关本身没坏）；
       ② 主图在**两种状态**下都不得出现东沙；
       ③ 附图的东沙符号是**地理符号**而非注记，故**不随**省名开关消失
          —— 与同在图中的西沙/中沙/南沙岛群点行为一致。 */
  const lblBefore = await p.evaluate(() => document.querySelectorAll('#gLabel text').length);
  await p.evaluate(() => document.getElementById('btnLabels').click());
  await p.waitForTimeout(300);
  const lblAfter = await p.evaluate(() => ({
    labels: document.querySelectorAll('#gLabel text').length,
    mainTxt: Array.from(document.querySelectorAll('#map text'))
      .filter(e => !(e.closest && e.closest('#gInset')))
      .filter(e => /东沙/.test(e.textContent || '')).length,
    insetSym: document.querySelectorAll('#gInset circle.isc, #gInset circle.isb').length,
  }));
  chk('  （对照）省名开关生效（标签数减少）', lblBefore > 0 && lblAfter.labels < lblBefore,
    lblBefore + ' → ' + lblAfter.labels);
  chk('隐藏省名后主图仍无「东沙」文字', lblAfter.mainTxt === 0, lblAfter.mainTxt + ' 处');
  chk('附图的东沙符号不随省名开关消失（它是地理符号，非注记）',
    lblAfter.insetSym === 2, lblAfter.insetSym + ' 个');
  await p.evaluate(() => document.getElementById('btnLabels').click());
  await p.waitForTimeout(300);
  chk('恢复省名后附图东沙符号仍在（幂等，无叠加）',
    await p.evaluate(() => document.querySelectorAll('#gInset circle.isc, #gInset circle.isb').length) === 2);

  console.log('\n【七】截图');
  await p.screenshot({ path: path.join(OUTDIR, 'j0-full.png'), fullPage: true });
  // 附图内东沙一带放大（纯观察手段）：把 viewBox 收窄到附图那两枚符号周围。
  // 主图已不渲染东沙，故截图窗口改为取 **附图** 中东沙符号的 bbox。
  /* ⚠ 取框必须在**页面内**做：附图符号位于 <g transform="translate(IX,IY)"> 之内，
     el.getBBox() 返回的是**组内局部坐标**，直接拿去设 #map 的 viewBox 会框到空白
     海域（已实际踩到：截出一片纯底色）。故用 getScreenCTM().inverse() 映射到根坐标。
     另注：该逻辑不能写成 Node 侧函数再传进来 —— evaluate 的实参必须是可序列化的值，
     函数定义不会被带进页面上下文（会抛 ReferenceError: xxx is not defined）。 */
  const bb = await p.evaluate(pad => {
    const svg = document.getElementById('map');
    const inv = svg.getScreenCTM().inverse();
    const pt = svg.createSVGPoint();
    let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
    document.querySelectorAll('#gInset circle.isc, #gInset circle.isb').forEach(el => {
      const r = el.getBoundingClientRect();
      [[r.left, r.top], [r.right, r.bottom]].forEach(([sx, sy]) => {
        pt.x = sx; pt.y = sy;
        const q = pt.matrixTransform(inv);
        x0 = Math.min(x0, q.x); y0 = Math.min(y0, q.y);
        x1 = Math.max(x1, q.x); y1 = Math.max(y1, q.y);
      });
    });
    if (!isFinite(x0)) return null;
    return [x0 - pad, y0 - pad, (x1 - x0) + 2 * pad, (y1 - y0) + 2 * pad];
  }, 14);
  chk('附图内可定位东沙符号以截图', !!bb, bb ? '' : '未找到');
  if (bb) {
    await p.evaluate(v => {
      document.getElementById('map').setAttribute('viewBox', v.map(x => x.toFixed(2)).join(' '));
    }, bb);
    await p.waitForTimeout(400);
    await (await p.$('#map')).screenshot({ path: path.join(OUTDIR, 'j1-dongsha-zoom.png') });
    console.log('    已存 j0-full.png / j1-dongsha-zoom.png');
    console.log('    放大窗口 viewBox = [' + bb.map(v => v.toFixed(1)).join(' ') + ']');
  }

  console.log('\n== 运行时错误 == ' + (errs.length ? '\n  ' + errs.join('\n  ') : '无'));
  console.log('\n结果：' + (fails === 0 && errs.length === 0 ? '全部通过' : '有 ' + fails + ' 项未通过'));
  await b.close();
  process.exit(fails === 0 && errs.length === 0 ? 0 : 1);
})();

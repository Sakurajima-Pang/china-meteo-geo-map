// 验证「经纬网」：格线位置是否与独立复算的投影一致 + 与既有交互不冲突
//
// 用法: node verify_grid.js <成品HTML路径> <输出目录>
// 需要 NODE_PATH 指向含 @playwright/test 的目录（Windows Git Bash）：
//   export NODE_PATH="$APPDATA/npm/node_modules"
//
// 本脚本独立复算墨卡托投影，不引用页面内部状态 —— 否则页面算错时脚本也会跟着错。
const { chromium } = require('@playwright/test');
const { pathToFileURL } = require('url');
const path = require('path');
const fs = require('fs');

const FILE = process.argv[2];
const OUTDIR = process.argv[3];
if (!fs.existsSync(OUTDIR)) fs.mkdirSync(OUTDIR, { recursive: true });

// ---- 独立复算：与页面同一套公式，参数在此重新声明 ----
const R = Math.PI / 180;
const BB = { lng: [73, 135.5], lat: [17.6, 53.8] };
const VW = 1000, VH = 739, PAD = 6, STEP = 5;
const merc = (lng, lat) => [lng * R, Math.log(Math.tan(Math.PI / 4 + lat * R / 2))];
const p0 = merc(BB.lng[0], BB.lat[0]), p1 = merc(BB.lng[1], BB.lat[1]);
const w = p1[0] - p0[0], h = p1[1] - p0[1];
const S = Math.min((VW - 2 * PAD) / w, (VH - 2 * PAD) / h);
const OX = (VW - w * S) / 2, OY = (VH - h * S) / 2;
const fwd = (lng, lat) => { const m = merc(lng, lat); return [OX + (m[0] - p0[0]) * S, OY + (p1[1] - m[1]) * S]; };

let bad = 0;
const chk = (label, ok, detail = '') => {
  if (!ok) bad++;
  console.log('  ' + (ok ? '✓' : '✗') + ' ' + label + (detail ? '  ' + detail : ''));
};

(async () => {
  const b = await chromium.launch({ channel: 'chrome', headless: true });
  const p = await b.newPage({ viewport: { width: 1800, height: 1100 }, deviceScaleFactor: 1 });
  const errs = [];
  p.on('console', m => { if (m.type() === 'error') errs.push('console: ' + m.text()); });
  p.on('pageerror', e => errs.push('pageerror: ' + e.message));
  await p.goto(pathToFileURL(FILE).href, { waitUntil: 'load' });
  await p.waitForTimeout(900);

  console.log('【一】开关与基础渲染');
  chk('初始状态经纬网为空（默认关闭）',
    await p.evaluate(() => document.querySelectorAll('#gGrid > *').length) === 0);
  await p.evaluate(() => document.getElementById('btnGrid').click());
  await p.waitForTimeout(300);
  chk('按钮文案切换为「隐藏经纬网」',
    await p.evaluate(() => document.getElementById('btnGrid').textContent) === '隐藏经纬网');
  chk('aria-pressed 置为 true',
    await p.evaluate(() => document.getElementById('btnGrid').getAttribute('aria-pressed')) === 'true');

  const st = await p.evaluate(() => ({
    lines: Array.from(document.querySelectorAll('#gGrid line')).map(l => ({
      c: l.getAttribute('class') || '', x1: +l.getAttribute('x1'), y1: +l.getAttribute('y1'),
      x2: +l.getAttribute('x2'), y2: +l.getAttribute('y2')
    })),
    texts: Array.from(document.querySelectorAll('#gGrid text')).map(t => t.textContent),
    g0lines: document.querySelectorAll('#gGrid line.g0').length
  }));
  const vlines = st.lines.filter(l => Math.abs(l.x1 - l.x2) < 0.5);
  const hlines = st.lines.filter(l => Math.abs(l.y1 - l.y2) < 0.5);
  console.log('  经线 ' + vlines.length + ' 条、纬线 ' + hlines.length + ' 条、整十度加粗 ' +
    st.g0lines + ' 条、度标 ' + st.texts.length + ' 个');
  /* 格线生成范围是「视图矩形」而非「数据 bbox」——向外 floor/ceil 到整 GRID_STEP，
     故条数由 view.x/y/w/h 反算的经纬度决定，不由 73–135.5°E 决定。
     复位视图 (0,0,1000,739) 对应 72.48–136.02°E / 17.24–54.02°N
     → lng0=70, lng1=140（15 条）；lat0=15, lat1=55（9 条）。此处独立复算该条数。 */
  const vbb = await p.evaluate(() => document.getElementById('map').getAttribute('viewBox')
    .split(' ').map(Number));
  const invCorner = (x, y) => {
    const mx = (x - OX) / S + p0[0];
    const my = p0[1] + (OY + h * S - y) / S;
    return [mx / R, (2 * Math.atan(Math.exp(my)) - Math.PI / 2) / R];
  };
  const cLO = invCorner(vbb[0], vbb[1] + vbb[3]);   // 左下
  const cRU = invCorner(vbb[0] + vbb[2], vbb[1]);   // 右上
  const expV = (Math.ceil(cRU[0] / STEP) * STEP - Math.floor(cLO[0] / STEP) * STEP) / STEP + 1;
  const expH = (Math.ceil(cRU[1] / STEP) * STEP - Math.floor(cLO[1] / STEP) * STEP) / STEP + 1;
  chk('经线数量与视图范围独立复算一致（期望 ' + expV + '）', vlines.length === expV,
    '实得 ' + vlines.length + '，跨度 ' + cLO[0].toFixed(2) + '–' + cRU[0].toFixed(2) + '°E');
  chk('纬线数量与视图范围独立复算一致（期望 ' + expH + '）', hlines.length === expH,
    '实得 ' + hlines.length + '，跨度 ' + cLO[1].toFixed(2) + '–' + cRU[1].toFixed(2) + '°N');
  chk('度标数量 = 经线 + 纬线', st.texts.length === st.lines.length, '实得 ' + st.texts.length);

  console.log('');
  console.log('【二】格线位置与独立复算一致');
  // 经线：x 应等于 fwd(lng, *) 的 x
  let maxErr = 0, checked = 0;
  for (const l of vlines) {
    // 反推该线对应的经度：x = OX + (lng*R - p0[0])*S
    const lng = ((l.x1 - OX) / S + p0[0]) / R;
    const exp = fwd(lng, 35)[0];
    const e = Math.abs(exp - l.x1); maxErr = Math.max(maxErr, e); checked++;
    if (e > 0.15) chk('经线 ' + lng.toFixed(2) + '°E 的 x 与复算一致', false, '偏差 ' + e.toFixed(3) + ' px');
  }
  chk(checked + ' 条经线的 x 位置与独立复算一致（最大偏差 ' + maxErr.toFixed(4) + ' px）', maxErr < 0.15);
  // 纬线：y 应等于 fwd(*, lat) 的 y —— 墨卡托下间距不等，重点验这一点
  let maxErrY = 0, latList = [];
  for (const l of hlines) {
    const my = p0[1] + (OY + h * S - l.y1) / S;      // 反墨卡托纵坐标
    const lat = (2 * Math.atan(Math.exp(my)) - Math.PI / 2) / R;
    latList.push(lat);
    const e = Math.abs(fwd(0, lat)[1] - l.y1); maxErrY = Math.max(maxErrY, e);
  }
  latList.sort((a, b) => a - b);
  chk(hlines.length + ' 条纬线的 y 位置与独立复算一致（最大偏差 ' + maxErrY.toFixed(4) + ' px）', maxErrY < 0.15,
    '纬度 ' + latList.map(v => v.toFixed(1)).join('/'));
  // 明确验证「非等距」：墨卡托下高纬度的 5° 间距应明显大于低纬度
  /* 注意 y 轴向下增大、纬度向上增大，故 ys[i]-ys[i-1] 为负值。
     必须比较绝对值，否则「两个负数比大小」永远不成立。 */
  const ys = hlines.map(l => l.y1).sort((a, b) => b - a);   // y 递减 = 自低纬到高纬
  const absGaps = [];
  for (let i = 1; i < ys.length; i++) absGaps.push(Math.abs(ys[i] - ys[i - 1]));
  const lowGap = absGaps[0], highGap = absGaps[absGaps.length - 1];
  chk('纬线间距随纬度增大而增大（墨卡托特性，未误用等分）',
    highGap > lowGap * 1.1,
    '低纬 5° ≈ ' + lowGap.toFixed(1) + ' px，高纬 5° ≈ ' + highGap.toFixed(1) +
    ' px，比值 ' + (highGap / lowGap).toFixed(2));
  chk('纬线间距严格单调递增（逐段核对）',
    absGaps.every((v, i) => i === 0 || v > absGaps[i - 1]),
    absGaps.map(v => v.toFixed(1)).join(' < '));

  console.log('');
  console.log('【三】度标文字');
  const lngLabels = st.texts.filter(t => /°E$/.test(t));
  const latLabels = st.texts.filter(t => /°N$/.test(t));
  chk('经度度标 ' + lngLabels.length + ' 个、纬度度标 ' + latLabels.length + ' 个',
    lngLabels.length === vlines.length && latLabels.length === hlines.length);
  chk('度标无负数（不出现「-5°E」这类自相矛盾值）', !st.texts.some(t => t.indexOf('-') === 0),
    st.texts.filter(t => t.indexOf('-') === 0).join(','));
  chk('度标格式为整数度（如 120°E）', lngLabels.every(t => /^\d+°E$/.test(t)),
    lngLabels.slice(0, 4).join(' '));
  await p.screenshot({ path: path.join(OUTDIR, 'g1-grid-on.png') });

  console.log('');
  console.log('【四】缩放平移后仍正确');
  // 放大后格线应更疏（可见范围变小）且度标随视图变化
  const box = await p.evaluate(() => {
    const r = document.getElementById('map').getBoundingClientRect();
    return { x: r.x, y: r.y, w: r.width, h: r.height };
  });
  await p.mouse.move(box.x + box.w / 2, box.y + box.h / 2);
  for (let i = 0; i < 4; i++) { await p.mouse.wheel(0, -120); await p.waitForTimeout(80); }
  await p.waitForTimeout(150);
  const zoom = await p.evaluate(() => ({
    vlines: Array.from(document.querySelectorAll('#gGrid line')).filter(l => Math.abs(+l.getAttribute('x1') - +l.getAttribute('x2')) < 0.5).length,
    texts: Array.from(document.querySelectorAll('#gGrid text')).map(t => t.textContent),
    vb: document.getElementById('map').getAttribute('viewBox').split(' ').map(Number)
  }));
  console.log('  放大 4 档后 viewBox =', JSON.stringify(zoom.vb.map(v => Math.round(v))));
  chk('放大后可见经线数减少（' + vlines.length + ' → ' + zoom.vlines + '）', zoom.vlines < vlines.length);
  chk('放大后度标仍在渲染', zoom.texts.length > 0, zoom.texts.slice(0, 6).join(' '));
  chk('放大后度标不含负号', !zoom.texts.some(t => t.indexOf('-') === 0));
  await p.screenshot({ path: path.join(OUTDIR, 'g2-grid-zoom.png') });

  // 拖到地图西侧边缘，检查不会出现负经度度标
  await p.evaluate(() => document.getElementById('btnResetView').click());
  await p.waitForTimeout(150);
  await p.mouse.move(box.x + 400, box.y + 400);
  await p.mouse.down();
  await p.mouse.move(box.x + 1500, box.y + 400, { steps: 10 });
  await p.mouse.up();
  await p.waitForTimeout(200);
  const pan = await p.evaluate(() => Array.from(document.querySelectorAll('#gGrid text')).map(t => t.textContent));
  console.log('  向右拖拽（视图西移）后度标 =', pan.slice(0, 8).join(' '));
  chk('拖到西边缘仍无负经度（' + (pan.find(t => t.indexOf('-') === 0) || '无') + '）',
    !pan.some(t => t.indexOf('-') === 0));
  await p.evaluate(() => document.getElementById('btnResetView').click());
  await p.waitForTimeout(150);

  console.log('');
  console.log('【五】与既有交互不冲突');
  // 经纬网不得拦截指针事件（pointer-events:none）——省份仍可悬停与单击
  chk('gGrid 设为 pointer-events:none',
    await p.evaluate(() => getComputedStyle(document.getElementById('gGrid')).pointerEvents) === 'none');
  const hd0 = await p.evaluate(() => document.getElementById('panelHd').textContent.replace(/\s+/g, ' ').trim());
  chk('初始面板为占位文案', hd0.indexOf('选择一个省级行政区') === 0);
  // 网格上线处单击省份，应正常打开面板。
  /* 不能硬编码屏幕坐标：随手取的点可能落在海洋/境外，本就点不出面板，
     会让检查恒失败而掩盖真实回归。此处按命中测试动态找一个确在省内、
     且贴近某条经纬线的点。 */
  const q = await p.evaluate(() => {
    const paths = Array.from(document.querySelectorAll('#gProv path'));
    for (const pa of paths) {
      const r2 = pa.getBoundingClientRect();
      if (r2.width < 20 || r2.height < 20) continue;
      for (let fx = 0.3; fx <= 0.7; fx += 0.05) {
        for (let fy = 0.3; fy <= 0.7; fy += 0.05) {
          const cx = r2.x + r2.width * fx, cy = r2.y + r2.height * fy;
          const e = document.elementFromPoint(cx, cy);
          if (e && e.closest && e.closest('#gProv')) return { x: cx, y: cy };
        }
      }
    }
    return null;
  });
  chk('可定位到一个确在省内的采样点', !!q, q ? '(' + q.x.toFixed(0) + ',' + q.y.toFixed(0) + ')' : '未找到');
  await p.mouse.move(q.x, q.y);
  await p.mouse.down(); await p.mouse.up();
  await p.waitForTimeout(300);
  const hd1 = await p.evaluate(() => document.getElementById('panelHd').textContent.replace(/\s+/g, ' ').trim());
  chk('开启经纬网后单击省份仍能打开面板（' + hd1.slice(0, 10) + '）', hd1.indexOf('选择一个省级行政区') !== 0);
  chk('该次单击未产生测距点', await p.evaluate(() => document.querySelectorAll('#gMeas circle').length) === 0);
  /* 同一采样点在「无网格」下也应命中同一个省 —— 证明 gGrid 未改变命中测试结果 */
  await p.evaluate(() => document.getElementById('btnGrid').click());
  await p.waitForTimeout(200);
  const hitWithout = await p.evaluate(([x, y]) => {
    const e = document.elementFromPoint(x, y);
    return !!(e && e.closest && e.closest('#gProv'));
  }, [q.x, q.y]);
  chk('同一采样点在无网格时同样命中省份（网格未拦截指针）', hitWithout);
  await p.evaluate(() => document.getElementById('btnGrid').click());
  await p.waitForTimeout(200);

  // 经纬网与经纬度读数、测距可同时开启
  await p.evaluate(() => { document.getElementById('btnCoord').click(); document.getElementById('btnMeasure').click(); });
  await p.waitForTimeout(250);
  chk('三者可同时开启（网格 + 读数 + 测距）',
    await p.evaluate(() => document.querySelectorAll('#gGrid line').length > 0 &&
      !document.getElementById('meas').hidden));
  await p.evaluate(() => { document.getElementById('btnMeasure').click(); document.getElementById('btnCoord').click(); });
  await p.waitForTimeout(200);

  // 关闭后图层清空
  await p.evaluate(() => document.getElementById('btnGrid').click());
  await p.waitForTimeout(200);
  chk('关闭后经纬网图层被清空', await p.evaluate(() => document.querySelectorAll('#gGrid > *').length) === 0);
  chk('关闭后按钮文案复位', await p.evaluate(() => document.getElementById('btnGrid').textContent) === '显示经纬网');
  // 反复开关不残留
  for (let i = 0; i < 3; i++) {
    await p.evaluate(() => document.getElementById('btnGrid').click());
    await p.waitForTimeout(70);
    await p.evaluate(() => document.getElementById('btnGrid').click());
    await p.waitForTimeout(70);
  }
  await p.evaluate(() => document.getElementById('btnGrid').click());
  await p.waitForTimeout(200);
  const n1 = await p.evaluate(() => document.querySelectorAll('#gGrid line').length);
  await p.evaluate(() => document.getElementById('btnGrid').click());
  await p.evaluate(() => document.getElementById('btnGrid').click());
  await p.waitForTimeout(200);
  const n2 = await p.evaluate(() => document.querySelectorAll('#gGrid line').length);
  chk('反复开关不叠加格线（' + n1 + ' → ' + n2 + '）', n1 === n2 && n1 > 0);
  await p.screenshot({ path: path.join(OUTDIR, 'g3-grid-final.png') });
  await p.evaluate(() => document.getElementById('btnGrid').click());

  console.log('');
  console.log('== 运行时错误 ==', errs.length ? JSON.stringify(errs, null, 1) : '无');
  if (errs.length) bad++;
  console.log('');
  console.log(bad ? '结果：' + bad + ' 项失败' : '结果：全部通过');
  await b.close();
  process.exit(bad ? 1 : 0);
})().catch(e => { console.error('FATAL', e); process.exit(1); });

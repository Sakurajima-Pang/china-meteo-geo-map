// 验证「经纬度显示」与「测距」两个工具：功能正确性 + 与既有交互不冲突
//
// 用法: node verify_tools.js <成品HTML路径> <输出目录>
// 需要 NODE_PATH 指向含 @playwright/test 的目录（Windows Git Bash）：
//   export NODE_PATH="$APPDATA/npm/node_modules"
//
// 本脚本独立复算逆投影与 Haversine，不引用页面内部状态 —— 否则页面算错时脚本也会跟着错。
const { chromium } = require('@playwright/test');
const { pathToFileURL } = require('url');
const path = require('path');
const fs = require('fs');

const FILE = process.argv[2];
const OUTDIR = process.argv[3];
if (!fs.existsSync(OUTDIR)) fs.mkdirSync(OUTDIR, { recursive: true });

// ---- 独立复算：与页面同一套公式，但参数在此重新声明 ----
const R = Math.PI / 180;
const BB = { lng: [73, 135.5], lat: [17.6, 53.8] };
const VW = 1000, VH = 739, PAD = 6;
/* 投影：兰勃特等角圆锥（与 template.html 同一套参数，在此独立重声明）。
   ⚠ 本脚本原按墨卡托复算，改投影后若不改这里，fwd 算出的坐标与页面完全不符，
     所有依赖 fwd/inv 的检查都会静默失效（典型空检查）。 */
const LAT1 = 30, LAT2 = 60, LNG0 = 105;
const N_ = Math.log(Math.cos(LAT1 * R) / Math.cos(LAT2 * R)) /
           Math.log(Math.tan(Math.PI / 4 + LAT2 * R / 2) / Math.tan(Math.PI / 4 + LAT1 * R / 2));
const F_ = Math.cos(LAT1 * R) * Math.pow(Math.tan(Math.PI / 4 + LAT1 * R / 2), N_) / N_;
const lcc = (lng, lat) => {
  const rho = F_ / Math.pow(Math.tan(Math.PI / 4 + lat * R / 2), N_);
  const th = N_ * (lng - LNG0) * R;
  return [rho * Math.sin(th), rho * Math.cos(th)];   // y = +rho*cos（北在上）
};
/* 沿边界密集采样求投影外接盒（不能用四角：纬线是下凹圆弧） */
function projBounds(bb) {
  let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
  const N = 2000;
  const acc = (lng, lat) => {
    const p = lcc(lng, lat);
    if (p[0] < x0) x0 = p[0]; if (p[0] > x1) x1 = p[0];
    if (p[1] < y0) y0 = p[1]; if (p[1] > y1) y1 = p[1];
  };
  for (let i = 0; i <= N; i++) {
    const t = i / N;
    acc(bb.lng[0] + (bb.lng[1] - bb.lng[0]) * t, bb.lat[0]);
    acc(bb.lng[0] + (bb.lng[1] - bb.lng[0]) * t, bb.lat[1]);
    acc(bb.lng[0], bb.lat[0] + (bb.lat[1] - bb.lat[0]) * t);
    acc(bb.lng[1], bb.lat[0] + (bb.lat[1] - bb.lat[0]) * t);
  }
  return [x0, y0, x1, y1];
}
const PB = projBounds(BB);
const w = PB[2] - PB[0], h = PB[3] - PB[1];
const S = Math.min((VW - 2 * PAD) / w, (VH - 2 * PAD) / h);
const OX = (VW - w * S) / 2, OY = (VH - h * S) / 2;
const fwd = (lng, lat) => { const p = lcc(lng, lat); return [OX + (p[0] - PB[0]) * S, OY + (p[1] - PB[1]) * S]; };
/* 逆投影：与 fwd 严格互逆，供「经纬度读数」检查复算用 */
const inv = (x, y) => {
  const px = (x - OX) / S + PB[0], py = (y - OY) / S + PB[1];
  const rho = Math.hypot(px, py), th = Math.atan2(px, py);
  return [LNG0 + th / (N_ * R), (2 * Math.atan(Math.pow(F_ / rho, 1 / N_)) - Math.PI / 2) / R];
};
const hav = (a, b) => {
  const dLat = (b[1] - a[1]) * R, dLng = (b[0] - a[0]) * R;
  const s1 = Math.sin(dLat / 2), s2 = Math.sin(dLng / 2);
  return 2 * 6371.0088 * Math.asin(Math.min(1, Math.sqrt(s1 * s1 + Math.cos(a[1] * R) * Math.cos(b[1] * R) * s2 * s2)));
};

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

  // 地图在屏幕上的像素矩形
  const box = await p.evaluate(() => {
    const r = document.getElementById('map').getBoundingClientRect();
    return { x: r.x, y: r.y, w: r.width, h: r.height };
  });
  // viewBox 坐标 → 屏幕像素
  const toPx = (vx, vy) => ({
    x: box.x + (vx / VW) * box.w,
    y: box.y + (vy / VH) * box.h
  });

  console.log('【一】经纬度读数');
  await p.evaluate(() => document.getElementById('btnCoord').click());
  chk('按钮切换为「隐藏经纬度」', await p.evaluate(() => document.getElementById('btnCoord').textContent) === '隐藏经纬度');

  // 取三个已知地理位置的屏幕像素点，移动指针后比对读数。
  // 采样点必须落在 map 的可视像素矩形内：三亚在北京时间戳下 y≈1141 px 会超出
  // 1100 px 的视口，mouse.move 被裁到视口边缘，读数自然对不上（脚本自身的问题）。
  const inView = (px) => px.x > box.x + 2 && px.x < box.x + box.w - 2 &&
                        px.y > box.y + 2 && px.y < box.y + box.h - 2;
  const samples = [
    ['北京', 116.40, 39.90],
    ['乌鲁木齐', 87.60, 43.80],
    ['武汉', 114.30, 30.60],
    ['兰州', 103.80, 36.06]
  ];
  let maxErr = 0, nSample = 0;
  for (const [nm, lng, lat] of samples) {
    const v = fwd(lng, lat), px = toPx(v[0], v[1]);
    if (!inView(px)) { chk(nm + '（跳过：落在可视区外 ' + Math.round(px.x) + ',' + Math.round(px.y) + '）', true); continue; }
    await p.mouse.move(px.x, px.y);
    await p.waitForTimeout(70);
    const txt = await p.evaluate(() => document.getElementById('coord').textContent);
    const m = txt.match(/([\d.]+)°E\s+([\d.]+)°N/);
    if (!m) { chk(nm + ' 读数可解析', false, JSON.stringify(txt)); continue; }
    const e = Math.max(Math.abs(+m[1] - lng), Math.abs(+m[2] - lat));
    maxErr = Math.max(maxErr, e); nSample++;
    chk(nm + ' 读数 = ' + m[1] + '°E ' + m[2] + '°N', e < 0.05, '期望 ' + lng + '°E ' + lat + '°N，偏差 ' + e.toFixed(3) + '°');
  }
  chk(nSample + ' 个可视采样点最大偏差 < 0.05°', nSample >= 3 && maxErr < 0.05,
    'n=' + nSample + ' max=' + maxErr.toFixed(4) + '°');

  // 同一指针位置缩放后读数应基本不变（验证用的是 viewBox 坐标而非屏幕像素）
  const zl = 116.40, zlat = 39.90, vz = fwd(zl, zlat), bz = toPx(vz[0], vz[1]);
  await p.mouse.move(bz.x, bz.y);
  const readBefore = await p.evaluate(() => document.getElementById('coord').textContent);
  for (let i = 0; i < 3; i++) { await p.mouse.wheel(0, -120); await p.waitForTimeout(80); }
  await p.mouse.move(bz.x + 1, bz.y);
  await p.waitForTimeout(80);
  const txtZ = await p.evaluate(() => document.getElementById('coord').textContent);
  const mz = txtZ.match(/([\d.]+)°E\s+([\d.]+)°N/);
  chk('以指针为锚点放大 3 档后，读数基本不变（' + readBefore.replace(/^WGS-84 /, '') + ' → ' + txtZ.replace(/^WGS-84 /, '') + '）',
    !!mz && Math.max(Math.abs(+mz[1] - zl), Math.abs(+mz[2] - zlat)) < 0.15);
  await p.screenshot({ path: path.join(OUTDIR, 't1-coord-zoom.png') });

  // 关掉再开，确认可逆
  await p.evaluate(() => document.getElementById('btnCoord').click());
  await p.evaluate(() => document.getElementById('btnResetView').click());
  await p.waitForTimeout(150);
  const hidden = await p.evaluate(() => document.getElementById('coord').classList.contains('on'));
  await p.mouse.move(box.x + 400, box.y + 300);
  await p.waitForTimeout(80);
  chk('关闭后指针移动不再显示读数',
    !await p.evaluate(() => document.getElementById('coord').classList.contains('on')));
  await p.evaluate(() => document.getElementById('btnCoord').click());
  await p.waitForTimeout(80);

  console.log('');
  console.log('【二】测距');
  await p.evaluate(() => document.getElementById('btnMeasure').click());
  await p.waitForTimeout(150);
  chk('测距面板出现', await p.evaluate(() => !document.getElementById('meas').hidden));
  chk('按钮切换为「退出测距」', await p.evaluate(() => document.getElementById('btnMeasure').textContent) === '退出测距');
  chk('svgbox 加 measuring 类', await p.evaluate(() => document.getElementById('svgbox').classList.contains('measuring')));

  // 沿「北京 → 上海 → 广州」三点量算，与独立 Haversine 复算比对
  const pts = [['北京', 116.40, 39.90], ['上海', 121.47, 31.23], ['广州', 113.26, 23.13]];
  for (const [, lng, lat] of pts) {
    const v = fwd(lng, lat), px = toPx(v[0], v[1]);
    await p.mouse.move(px.x, px.y);
    await p.mouse.down();
    await p.mouse.up();
    await p.waitForTimeout(120);
  }
  const st = await p.evaluate(() => ({
    pts: document.querySelectorAll('#gMeas circle').length,
    line: document.querySelectorAll('#gMeas path').length,
    texts: Array.from(document.querySelectorAll('#gMeas text')).map(t => t.textContent),
    rows: Array.from(document.querySelectorAll('.meas-row')).map(r => r.textContent.replace(/\s+/g, ' ').trim()),
    total: document.querySelector('.meas-ft b').textContent
  }));
  console.log('  落点圆点 =', st.pts, ' 折线路径 =', st.line, ' 里程标注 =', JSON.stringify(st.texts));
  console.log('  面板总距离 =', st.total);
  chk('落点数量 = 3', st.pts === 3, '实得 ' + st.pts);

  const exp1 = hav([116.40, 39.90], [121.47, 31.23]);
  const exp2 = hav([121.47, 31.23], [113.26, 23.13]);
  const expT = exp1 + exp2;
  const fmt = km => km < 1 ? Math.round(km * 1000) + ' m' : (km < 10 ? km.toFixed(2) : (km < 100 ? km.toFixed(1) : Math.round(km))) + ' km';
  console.log('  独立复算: 北京→上海 =', fmt(exp1), ' 上海→广州 =', fmt(exp2), ' 合计 =', fmt(expT));
  chk('总距离与独立复算一致', st.total === fmt(expT), '页面 ' + st.total + ' vs 复算 ' + fmt(expT));
  chk('两段里程标注与独立复算一致',
    st.texts.length === 2 && st.texts[0] === fmt(exp1) && st.texts[1] === fmt(exp2),
    JSON.stringify(st.texts));
  chk('面板列出 3 个测点', st.rows.length === 3, JSON.stringify(st.rows));
  await p.screenshot({ path: path.join(OUTDIR, 't2-measure-3pts.png') });

  // 跨 60 经度的大跨距测量：验证用的是大圆距离而非平面距离
  await p.evaluate(() => document.getElementById('btnMeasureClear').click());
  await p.waitForTimeout(120);
  const big = [['喀什', 75.99, 39.47], ['上海', 121.47, 31.23]];
  for (const [, lng, lat] of big) {
    const v = fwd(lng, lat), px = toPx(v[0], v[1]);
    await p.mouse.move(px.x, px.y); await p.mouse.down(); await p.mouse.up();
    await p.waitForTimeout(120);
  }
  const bigTotal = await p.evaluate(() => document.querySelector('.meas-ft b').textContent);
  const expBig = hav([75.99, 39.47], [121.47, 31.23]);
  // 平面欧氏距离（错误的做法）作对照：纬度按平均纬度换算
  const midLat = (39.47 + 31.23) / 2 * R;
  const flat = Math.hypot((121.47 - 75.99) * 111.32 * Math.cos(midLat), (31.23 - 39.47) * 110.57);
  console.log('  喀什→上海: 页面 =', bigTotal, ' 大圆复算 =', fmt(expBig), ' 平面近似(对照) =', fmt(flat));
  chk('跨 60 经度时取大圆距离（而非平面近似）',
    bigTotal === fmt(expBig) && fmt(expBig) !== fmt(flat),
    '页面 ' + bigTotal + ' / 大圆 ' + fmt(expBig) + ' / 平面 ' + fmt(flat));
  await p.screenshot({ path: path.join(OUTDIR, 't3-measure-long.png') });

  // 删末点
  const before = await p.evaluate(() => document.querySelectorAll('#gMeas circle').length);
  await p.evaluate(() => document.getElementById('measDel').click());
  await p.waitForTimeout(120);
  const after = await p.evaluate(() => document.querySelectorAll('#gMeas circle').length);
  chk('「删末点」使落点数 ' + before + ' → ' + after, after === before - 1);

  console.log('');
  console.log('【三】与既有交互不冲突');
  chk('测距期间省名已隐藏（给折线与里程标注让位）',
    await p.evaluate(() => document.querySelectorAll('#gLabel text').length) === 0);

  // 测距模式下拖拽平移不应落点
  await p.evaluate(() => document.getElementById('btnMeasureClear').click());
  await p.waitForTimeout(100);
  const n0 = await p.evaluate(() => document.querySelectorAll('#gMeas circle').length);
  await p.mouse.move(box.x + 300, box.y + 300);
  await p.mouse.down();
  await p.mouse.move(box.x + 420, box.y + 380, { steps: 8 });
  await p.mouse.up();
  await p.waitForTimeout(150);
  const n1 = await p.evaluate(() => document.querySelectorAll('#gMeas circle').length);
  chk('拖拽平移不留下测点（' + n0 + ' → ' + n1 + '）', n1 === n0);
  chk('拖拽确实平移了视图（viewBox.x ≠ 0）', await p.evaluate(() => {
    const vb = document.getElementById('map').getAttribute('viewBox').split(' ').map(Number);
    return Math.abs(vb[0]) > 1;
  }));
  await p.evaluate(() => document.getElementById('btnResetView').click());
  await p.waitForTimeout(120);

  // 测距模式下单击省份不应打开右侧面板。
  // 判据必须用「初始态」（未选省占位文案）而非"文本有变化" ——
  // 上一项测试可能已把面板标题改为某个省名，用变化的字符串比较会漏判。
  const PLACEHOLDER = '选择一个省级行政区';
  const hd0 = await p.evaluate(() => document.getElementById('panelHd').textContent.replace(/\s+/g, ' ').trim());
  const sc = fwd(104.0, 30.6), spx = toPx(sc[0], sc[1]);
  await p.mouse.move(spx.x, spx.y); await p.mouse.down(); await p.mouse.up();
  await p.waitForTimeout(250);
  const hd1 = await p.evaluate(() => document.getElementById('panelHd').textContent.replace(/\s+/g, ' ').trim());
  chk('测距中单击省份不会打开面板', hd1.indexOf(PLACEHOLDER) === 0,
    '面板 = 「' + hd1.slice(0, 26) + '」（测距前为「' + hd0.slice(0, 16) + '」）');
  chk('该次单击已落点', await p.evaluate(() => document.querySelectorAll('#gMeas circle').length) === 1);

  // 测距中双击 = 结束并清空
  await p.mouse.dblclick(spx.x, spx.y);
  await p.waitForTimeout(350);
  chk('双击结束测距（按钮复位）', await p.evaluate(() => document.getElementById('btnMeasure').textContent) === '测距');
  chk('双击结束同时清空折线', await p.evaluate(() => document.querySelectorAll('#gMeas circle').length) === 0);

  // 退出测距后一切恢复：单击省份应正常打开面板、省名应回来
  await p.mouse.move(spx.x, spx.y); await p.mouse.down(); await p.mouse.up();
  await p.waitForTimeout(350);
  const hd2 = await p.evaluate(() => document.getElementById('panelHd').textContent.replace(/\s+/g, ' ').trim());
  chk('退出测距后单击省份恢复正常（面板 = ' + hd2.slice(0, 16) + '）', hd2.indexOf(PLACEHOLDER) !== 0);
  const nLbl = await p.evaluate(() => document.querySelectorAll('#gLabel text').length);
  chk('省名已恢复显示（' + nLbl + ' 个标签）', nLbl > 20);

  // Escape 退出
  await p.evaluate(() => document.getElementById('btnMeasure').click());
  await p.waitForTimeout(150);
  await p.keyboard.press('Escape');
  await p.waitForTimeout(200);
  chk('Esc 退出测距', await p.evaluate(() => document.getElementById('btnMeasure').textContent) === '测距');
  chk('Esc 退出后省名亦恢复', await p.evaluate(() => document.querySelectorAll('#gLabel text').length) > 20);

  // 反复进出不得让省名丢失（labelsBak 被二次覆盖的回归项）
  for (let i = 0; i < 3; i++) {
    await p.evaluate(() => document.getElementById('btnMeasure').click());
    await p.waitForTimeout(80);
    await p.evaluate(() => document.getElementById('btnMeasure').click());
    await p.waitForTimeout(80);
  }
  chk('连续进出 3 次后省名仍正常', await p.evaluate(() => document.querySelectorAll('#gLabel text').length) > 20,
    '实得 ' + await p.evaluate(() => document.querySelectorAll('#gLabel text').length));

  // Backspace 删末点
  await p.evaluate(() => document.getElementById('btnMeasure').click());
  await p.waitForTimeout(120);
  const v1 = fwd(100, 35), q1 = toPx(v1[0], v1[1]);
  await p.mouse.move(q1.x, q1.y); await p.mouse.down(); await p.mouse.up(); await p.waitForTimeout(100);
  const v2 = fwd(105, 33), q2 = toPx(v2[0], v2[1]);
  await p.mouse.move(q2.x, q2.y); await p.mouse.down(); await p.mouse.up(); await p.waitForTimeout(150);
  const nb = await p.evaluate(() => document.querySelectorAll('#gMeas circle').length);
  await p.keyboard.press('Backspace');
  await p.waitForTimeout(180);
  const na = await p.evaluate(() => document.querySelectorAll('#gMeas circle').length);
  chk('Backspace 删末点（' + nb + ' → ' + na + '）', na === nb - 1);
  await p.evaluate(() => document.getElementById('btnMeasureClear').click());
  await p.evaluate(() => document.getElementById('btnMeasure').click());
  await p.waitForTimeout(150);
  chk('关闭测距后测量图层被清空', await p.evaluate(() => document.querySelectorAll('#gMeas > *').length) === 0);

  console.log('');
  console.log('== 运行时错误 ==', errs.length ? JSON.stringify(errs, null, 1) : '无');
  if (errs.length) bad++;
  console.log('');
  console.log(bad ? '结果：' + bad + ' 项失败' : '结果：全部通过');
  await b.close();
  process.exit(bad ? 1 : 0);
})().catch(e => { console.error('FATAL', e); process.exit(1); });

// 验证「经纬网」在**兰勃特等角圆锥投影**下的正确性 + 与既有交互不冲突
//
// 用法: node verify_grid.js <成品HTML路径> <输出目录>
// 需要 NODE_PATH 指向含 @playwright/test 的目录（Windows Git Bash）：
//   export NODE_PATH="$APPDATA/npm/node_modules"
//
// 本脚本独立复算兰勃特投影，不引用页面内部状态 —— 否则页面算错时脚本也会跟着错。
//
// 兰勃特下格线形状与墨卡托完全不同，判据也必须相应改变：
//   · 经线是自圆锥顶点发散的**射线**（斜率非零），不能再用 |x1-x2|<eps 识别；
//   · 纬线是**同心圆弧**（渲染为 <path>），不是水平线。
// 故识别方式是：<line> 即经线，<path> 即纬线。
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
const LAT1 = 30, LAT2 = 60, LNG0 = 105;

const N_ = Math.log(Math.cos(LAT1 * R) / Math.cos(LAT2 * R)) /
           Math.log(Math.tan(Math.PI / 4 + LAT2 * R / 2) / Math.tan(Math.PI / 4 + LAT1 * R / 2));
const F_ = Math.cos(LAT1 * R) * Math.pow(Math.tan(Math.PI / 4 + LAT1 * R / 2), N_) / N_;
const lcc = (lng, lat) => {
  const rho = F_ / Math.pow(Math.tan(Math.PI / 4 + lat * R / 2), N_);
  const th = N_ * (lng - LNG0) * R;
  return [rho * Math.sin(th), rho * Math.cos(th)];   // y = +rho*cos（北在上）
};
// 沿边界密集采样求投影外接盒（不能用四角：纬线是下凹圆弧）
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
const B = projBounds(BB);
const W = B[2] - B[0], H = B[3] - B[1];
const S = Math.min((VW - 2 * PAD) / W, (VH - 2 * PAD) / H);
const OX = (VW - W * S) / 2, OY = (VH - H * S) / 2;
const fwd = (lng, lat) => { const p = lcc(lng, lat); return [OX + (p[0] - B[0]) * S, OY + (p[1] - B[1]) * S]; };
// 逆投影（供缩放后校验）
const inv = (x, y) => {
  const px = (x - OX) / S + B[0], py = (y - OY) / S + B[1];
  const rho = Math.hypot(px, py), th = Math.atan2(px, py);
  return [LNG0 + th / (N_ * R), (2 * Math.atan(Math.pow(F_ / rho, 1 / N_)) - Math.PI / 2) / R];
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

  console.log('【〇】投影自检（独立复算）');
  chk('圆锥常数 n ≈ 0.7156（30/60 双标准纬线的文献值）', Math.abs(N_ - 0.7156) < 0.001,
    'n = ' + N_.toFixed(6));
  // 标准纬线上长度比恰为 1 —— 这是兰勃特的核心性质，算错则必不成立
  const mscale = (lat) => Math.sin(LAT1 * R) / Math.sin(lat * R) *
    Math.pow(Math.tan(lat * R / 2) / Math.tan(LAT1 * R / 2), N_);
  chk('30°N 处长度比 = 1（标准纬线定义）', Math.abs(mscale(30) - 1) < 1e-9, mscale(30).toFixed(9));
  chk('60°N 处长度比 = 1（标准纬线定义）', Math.abs(mscale(60) - 1) < 1e-9, mscale(60).toFixed(9));
  chk('投影为扇形：西边界经线斜率 ≠ 0（区别于墨卡托的竖直）',
    Math.abs(fwd(73, 53.8)[0] - fwd(73, 17.6)[0]) > 5,
    '73°E 上下端点 x 相差 ' + Math.abs(fwd(73, 53.8)[0] - fwd(73, 17.6)[0]).toFixed(1) + ' px');
  chk('北在上：高纬的屏幕 y 小于低纬',
    fwd(105, 53.8)[1] < fwd(105, 17.6)[1],
    'y(53.8°N)=' + fwd(105, 53.8)[1].toFixed(1) + ' < y(17.6°N)=' + fwd(105, 17.6)[1].toFixed(1));
  chk('经线间距自南向北收窄（圆锥投影特征）',
    Math.abs(fwd(110, 17.6)[0] - fwd(105, 17.6)[0]) >
    Math.abs(fwd(110, 53.8)[0] - fwd(105, 53.8)[0]) * 1.3,
    '南 ' + Math.abs(fwd(110, 17.6)[0] - fwd(105, 17.6)[0]).toFixed(1) +
    ' px vs 北 ' + Math.abs(fwd(110, 53.8)[0] - fwd(105, 53.8)[0]).toFixed(1) + ' px');

  console.log('');
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
      x1: +l.getAttribute('x1'), y1: +l.getAttribute('y1'),
      x2: +l.getAttribute('x2'), y2: +l.getAttribute('y2'), c: l.getAttribute('class') || ''
    })),
    arcs: Array.from(document.querySelectorAll('#gGrid path')).map(e => ({
      d: e.getAttribute('d'), c: e.getAttribute('class') || ''
    })),
    texts: Array.from(document.querySelectorAll('#gGrid text')).map(t => t.textContent),
    g0: document.querySelectorAll('#gGrid line.g0, #gGrid path.g0').length
  }));
  console.log('  经线(直线) ' + st.lines.length + ' 条、纬线(圆弧) ' + st.arcs.length +
    ' 条、整十度加粗 ' + st.g0 + ' 条、度标 ' + st.texts.length + ' 个');
  const expV = (Math.ceil(BB.lng[1] / STEP) * STEP - Math.floor(BB.lng[0] / STEP) * STEP) / STEP + 1;
  const expH = (Math.ceil(BB.lat[1] / STEP) * STEP - Math.floor(BB.lat[0] / STEP) * STEP) / STEP + 1;
  chk('经线数量与数据包围盒复算一致（期望 ' + expV + '）', st.lines.length === expV,
    '实得 ' + st.lines.length);
  chk('纬线数量与数据包围盒复算一致（期望 ' + expH + '）', st.arcs.length === expH,
    '实得 ' + st.arcs.length);
  chk('度标数量 = 经线 + 纬线', st.texts.length === st.lines.length + st.arcs.length,
    '实得 ' + st.texts.length);
  chk('经线以 <line> 渲染、纬线以 <path> 圆弧渲染（形状不同）',
    st.lines.length > 0 && st.arcs.length > 0);

  console.log('');
  console.log('【二】经线位置与独立复算一致');
  /* 判据一：经线两端点必须落在同一条**复算射线**上，即两端反算经度相等。
     容差取 0.02° 而非机器精度：页面把端点坐标 toFixed(1) 后才写入 SVG，
     0.05 px 的舍入在斜线上（斜率最大约 tan22.9°≈0.42，见下一条检查）
     反算成经度约 0.05·cos/21px-per-deg ≈ 0.0025°。实测最差 0.008952°，对应约 0.2 px，
     远小于线宽 0.7 px，视觉不可见。
     ⚠ 该容差若调到 1e-6（机器精度）会恒失败 —— 那不是页面缺陷，是本判据不可实现。 */
  let maxE = 0, checkedV = 0, worstLine = null;
  for (const l of st.lines) {
    const lngA = inv(l.x1, l.y1)[0], lngB = inv(l.x2, l.y2)[0];
    const dl = Math.abs(lngA - lngB);
    if (dl > maxE) { maxE = dl; worstLine = l; }
    checkedV++;
  }
  chk(checkedV + ' 条经线的两端反算经度自洽（最大偏差 ' + maxE.toFixed(6) + '°，容差 0.02°）',
    maxE < 0.02);
  /* 端点距其标称经线的横向偏移（像素），这是使用者真正能看到的量 */
  let maxOff = 0;
  for (const l of st.lines) {
    const nom = Math.round(inv(l.x1, l.y1)[0] / STEP) * STEP;
    for (const [x, y] of [[l.x1, l.y1], [l.x2, l.y2]]) {
      maxOff = Math.max(maxOff, Math.abs(fwd(nom, inv(x, y)[1])[0] - x));
    }
  }
  chk('端点相对标称经线的横向偏移 < 1 px（视觉不可见）', maxOff < 1,
    '最大偏移 ' + maxOff.toFixed(3) + ' px');
  // 再验证斜率：兰勃特下经线必须倾斜（除中央经线外）
  const slopes = st.lines.map(l => Math.abs((l.x2 - l.x1) / (l.y2 - l.y1 || 1e-9)));
  chk('非中央经线确有倾斜（扇形特征）', slopes.filter(s => s > 0.02).length >= 8,
    '倾斜经线 ' + slopes.filter(s => s > 0.02).length + ' / ' + slopes.length + ' 条');

  console.log('');
  console.log('【三】纬线为圆弧（凹陷量可测）');
  /* 圆弧的判据：取 path 的 d，两端点的中点连线与路径中点的 y 之差 —— 即「弓高」。
     兰勃特下纬线向赤道方向凸出（本图 y 向下，故圆弧中点应比两端连线更靠下/更靠上，
     取决于弯曲方向），关键是该差值必须显著非零。 */
  let maxSag = 0, sagOK = 0;
  for (const a of st.arcs) {
    const nums = (a.d.match(/-?\d+(\.\d+)?/g) || []).map(Number);
    if (nums.length < 6) continue;
    // d 形如 M x y L x y L x y ...（每两个数一个点）
    const pts = [];
    for (let i = 0; i + 1 < nums.length; i += 2) pts.push([nums[i], nums[i + 1]]);
    if (pts.length < 4) continue;
    const p0 = pts[0], pN = pts[pts.length - 1];
    const mid = pts[Math.floor(pts.length / 2)];
    const chordY = (p0[1] + pN[1]) / 2;
    const sag = Math.abs(mid[1] - chordY);
    maxSag = Math.max(maxSag, sag);
    if (sag > 0.5) sagOK++;
  }
  chk('纬线均为圆弧（弓高显著非零，非直线）', sagOK === st.arcs.length && st.arcs.length > 0,
    '最大弓高 ' + maxSag.toFixed(1) + ' px，合格 ' + sagOK + '/' + st.arcs.length);
  /* 独立复算弓高：取 105°E 附近与两端的 y 差，应与页面量出的同量级 */
  const sagRef = Math.abs(fwd(105, 30)[1] - (fwd(73, 30)[1] + fwd(135.5, 30)[1]) / 2);
  chk('弓高与独立复算同量级（30°N 参考值 ' + sagRef.toFixed(1) + ' px）',
    maxSag > sagRef * 0.4 && maxSag < sagRef * 2.5);

  console.log('');
  console.log('【四】度标文字');
  const lngLabels = st.texts.filter(t => /°E$/.test(t));
  const latLabels = st.texts.filter(t => /°N$/.test(t));
  chk('经度度标 ' + lngLabels.length + ' 个、纬度度标 ' + latLabels.length + ' 个',
    lngLabels.length === st.lines.length && latLabels.length === st.arcs.length);
  chk('度标无负数（不出现「-5°E」这类自相矛盾值）', !st.texts.some(t => t.indexOf('-') === 0),
    st.texts.filter(t => t.indexOf('-') === 0).join(','));
  chk('经度度标格式为整数度', lngLabels.every(t => /^\d+°E$/.test(t)), lngLabels.slice(0, 4).join(' '));
  chk('纬度度标格式为整数度', latLabels.every(t => /^\d+°N$/.test(t)), latLabels.slice(0, 4).join(' '));
  /* 度标必须落在**画面内**。
     ⚠ 判据变迁记录：本项原判据是「度标落在 gProv（省界）bbox ±40 px 内」，
     实测恒为 14/24 失败 —— 因为该判据本身是错的：
       · 内容 bbox 是**省界几何**的极值；在纬度 17.6°N 一带，真实省界只到
         108–110°E（海南岛），而格线沿 MAIN_BB 的 73–135.5°E 铺开。
         两者不同源，不能用后者约束前者 —— 否则最西/最东各 5 个度标必然"越界"。
       · 纬度方向同理：55°N 的弧线在 MAIN_BB 北缘 y≈28，高于省界 bbox 顶 97.8，
         但那里正对黑龙江以北，是合法的空白区。
     正确的判据是画布边界：度标（及夹取逻辑）只应保证不画到画面之外。 */
  const inContent = await p.evaluate(() => {
    let ok = 0, total = 0, out = [];
    document.querySelectorAll('#gGrid text').forEach(t => {
      total++;
      const x = +t.getAttribute('x'), y = +t.getAttribute('y');
      // VW/VH 由页面 viewBox 起始值给出（复位状态下即画面全幅）
      if (x >= 0 && x <= 1000 && y >= 0 && y <= 739) ok++;
      else out.push(t.textContent + '(' + x + ',' + y + ')');
    });
    return { ok, total, out };
  });
  chk('度标未越出画面（' + inContent.ok + '/' + inContent.total + '）',
    inContent.ok === inContent.total, inContent.out.slice(0, 4).join(' '));
  /* 度标不得互相重叠：夹取到内容 bbox 会把最西/最东各 5 个经度标挤到同一条竖线上 */
  const overlap = await p.evaluate(() => {
    const items = [];
    document.querySelectorAll('#gGrid text').forEach(t => {
      const b = t.getBBox();
      items.push({ s: t.textContent, x: b.x, y: b.y, w: b.width, h: b.height });
    });
    const hits = [];
    for (let i = 0; i < items.length; i++) {
      for (let j = i + 1; j < items.length; j++) {
        const a = items[i], c = items[j];
        if (a.x < c.x + c.w && c.x < a.x + a.w && a.y < c.y + c.h && c.y < a.y + a.h) {
          hits.push(a.s + '×' + c.s);
        }
      }
    }
    return hits;
  });
  chk('度标互不重叠（' + (overlap.length ? overlap.slice(0, 3).join(' ') : '无重叠') + '）',
    overlap.length === 0);
  await p.screenshot({ path: path.join(OUTDIR, 'g1-grid-on.png') });

  console.log('');
  console.log('【五】缩放平移后仍正确');
  const box = await p.evaluate(() => {
    const r = document.getElementById('map').getBoundingClientRect();
    return { x: r.x, y: r.y, w: r.width, h: r.height };
  });
  await p.mouse.move(box.x + box.w / 2, box.y + box.h / 2);
  for (let i = 0; i < 4; i++) { await p.mouse.wheel(0, -120); await p.waitForTimeout(80); }
  await p.waitForTimeout(200);
  const zoom = await p.evaluate(() => ({
    lines: document.querySelectorAll('#gGrid line').length,
    arcs: document.querySelectorAll('#gGrid path').length,
    texts: Array.from(document.querySelectorAll('#gGrid text')).map(t => t.textContent),
    vb: document.getElementById('map').getAttribute('viewBox').split(' ').map(Number)
  }));
  console.log('  放大 4 档后 viewBox =', JSON.stringify(zoom.vb.map(v => Math.round(v))));
  chk('放大后仍渲染格线（经线 ' + zoom.lines + ' / 纬线 ' + zoom.arcs + '）',
    zoom.lines > 0 && zoom.arcs > 0);
  chk('放大后度标仍在渲染', zoom.texts.length > 0, zoom.texts.slice(0, 6).join(' '));
  chk('放大后度标不含负号', !zoom.texts.some(t => t.indexOf('-') === 0));
  await p.screenshot({ path: path.join(OUTDIR, 'g2-grid-zoom.png') });
  await p.evaluate(() => document.getElementById('btnResetView').click());
  await p.waitForTimeout(200);
  // 拖到西侧
  await p.mouse.move(box.x + 400, box.y + 400);
  await p.mouse.down();
  await p.mouse.move(box.x + 1500, box.y + 400, { steps: 10 });
  await p.mouse.up();
  await p.waitForTimeout(250);
  const pan = await p.evaluate(() => Array.from(document.querySelectorAll('#gGrid text')).map(t => t.textContent));
  chk('拖到西边缘仍无负经度', !pan.some(t => t.indexOf('-') === 0),
    '度标 ' + pan.slice(0, 6).join(' '));
  await p.evaluate(() => document.getElementById('btnResetView').click());
  await p.waitForTimeout(200);

  console.log('');
  console.log('【六】与既有交互不冲突');
  chk('gGrid 设为 pointer-events:none',
    await p.evaluate(() => getComputedStyle(document.getElementById('gGrid')).pointerEvents) === 'none');
  const hd0 = await p.evaluate(() => document.getElementById('panelHd').textContent.replace(/\s+/g, ' ').trim());
  chk('初始面板为占位文案', hd0.indexOf('选择一个省级行政区') === 0);
  // 动态找一个确在省内的采样点（硬编码坐标可能落在海上）
  const q = await p.evaluate(() => {
    for (const pa of document.querySelectorAll('#gProv path')) {
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
  const hitWithout = await (async () => {
    await p.evaluate(() => document.getElementById('btnGrid').click());
    await p.waitForTimeout(200);
    const r = await p.evaluate(([x, y]) => {
      const e = document.elementFromPoint(x, y);
      return !!(e && e.closest && e.closest('#gProv'));
    }, [q.x, q.y]);
    await p.evaluate(() => document.getElementById('btnGrid').click());
    await p.waitForTimeout(200);
    return r;
  })();
  chk('同一采样点在无网格时同样命中省份（网格未拦截指针）', hitWithout);

  await p.evaluate(() => { document.getElementById('btnCoord').click(); document.getElementById('btnMeasure').click(); });
  await p.waitForTimeout(250);
  chk('三者可同时开启（网格 + 读数 + 测距）',
    await p.evaluate(() => document.querySelectorAll('#gGrid line, #gGrid path').length > 0 &&
      !document.getElementById('meas').hidden));
  await p.evaluate(() => { document.getElementById('btnMeasure').click(); document.getElementById('btnCoord').click(); });
  await p.waitForTimeout(200);

  await p.evaluate(() => document.getElementById('btnGrid').click());
  await p.waitForTimeout(200);
  chk('关闭后经纬网图层被清空', await p.evaluate(() => document.querySelectorAll('#gGrid > *').length) === 0);
  chk('关闭后按钮文案复位', await p.evaluate(() => document.getElementById('btnGrid').textContent) === '显示经纬网');
  for (let i = 0; i < 3; i++) {
    await p.evaluate(() => document.getElementById('btnGrid').click());
    await p.waitForTimeout(70);
    await p.evaluate(() => document.getElementById('btnGrid').click());
    await p.waitForTimeout(70);
  }
  await p.evaluate(() => document.getElementById('btnGrid').click());
  await p.waitForTimeout(200);
  const n1 = await p.evaluate(() => document.querySelectorAll('#gGrid line, #gGrid path').length);
  await p.evaluate(() => document.getElementById('btnGrid').click());
  await p.evaluate(() => document.getElementById('btnGrid').click());
  await p.waitForTimeout(200);
  const n2 = await p.evaluate(() => document.querySelectorAll('#gGrid line, #gGrid path').length);
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

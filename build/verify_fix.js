// 验证河名标注落点、山脉范围着色、键盘可达性
const { chromium } = require('@playwright/test');
const { pathToFileURL } = require('url');
const path = require('path');

const FILE = process.argv[2];
const OUTDIR = process.argv[3];

(async () => {
  const b = await chromium.launch({ channel: 'chrome', headless: true });
  const p = await b.newPage({ viewport: { width: 1800, height: 1100 }, deviceScaleFactor: 1 });
  const errs = [];
  p.on('console', m => { if (m.type() === 'error') errs.push('console: ' + m.text()); });
  p.on('pageerror', e => errs.push('pageerror: ' + e.message));
  await p.goto(pathToFileURL(FILE).href, { waitUntil: 'load' });
  await p.waitForTimeout(1000);

  // 逆投影：把 SVG 用户坐标换算回经纬度（与页面同一算法）
  const inv = (x, y) => {
    const R = Math.PI / 180;
    const m = (lng, lat) => [lng * R, Math.log(Math.tan(Math.PI / 4 + lat * R / 2))];
    const p0 = m(73, 17.6), p1 = m(135.5, 53.8);
    const w = p1[0] - p0[0], h = p1[1] - p0[1];
    const s = Math.min((1000 - 12) / w, (739 - 12) / h), ox = (1000 - w * s) / 2, oy = (739 - h * s) / 2;
    const mx = (x - ox) / s + p0[0], my = p0[1] + (oy + h * s - y) / s;
    return [mx / R, (2 * Math.atan(Math.exp(my)) - Math.PI / 2) / R];
  };

  // 勾选 广东/广西/贵州/云南 的珠江 + 四川山脉
  for (const ad of ['440000', '450000', '520000']) {
    await p.evaluate(a => document.querySelector('.pv[data-ad="' + a + '"]').dispatchEvent(new MouseEvent('click', { bubbles: true })), ad);
    await p.waitForTimeout(120);
    await p.evaluate(() => {
      const el = document.querySelector('#panelBd input[data-kind=r][data-id="zhujiang"]');
      if (el && !el.checked) { el.checked = true; el.dispatchEvent(new Event('change', { bubbles: true })); }
    });
  }
  await p.waitForTimeout(400);

  const labels = await p.evaluate(() => Array.from(document.querySelectorAll('#gRiver text')).map(t => ({
    name: t.textContent, x: parseFloat(t.getAttribute('x')), y: parseFloat(t.getAttribute('y'))
  })));
  console.log('河流名称标注落点:');
  for (const L of labels) {
    const ll = inv(L.x, L.y + 6);
    console.log('  ' + L.name + '  =  ' + ll[0].toFixed(2) + 'E ' + ll[1].toFixed(2) + 'N');
  }

  // 珠江各段路径数
  console.log('珠江 绘制段数 =', await p.evaluate(() => document.querySelectorAll('#gRiver path').length));

  // 键盘可达性
  const kb = await p.evaluate(() => {
    const el = document.querySelector('.pv[data-ad="510000"]');
    return { tabindex: el.getAttribute('tabindex'), role: el.getAttribute('role'), aria: el.getAttribute('aria-label') };
  });
  console.log('键盘可达性:', JSON.stringify(kb));
  await p.evaluate(() => {
    const el = document.querySelector('.pv[data-ad="510000"]');
    el.focus();
    el.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true }));
  });
  await p.waitForTimeout(300);
  console.log('回车选中后面板标题 =', await p.evaluate(() => document.getElementById('panelHd').textContent.replace(/\s+/g, ' ').trim().slice(0, 40)));

  // 澳门无边界堂区应被禁用
  await p.evaluate(() => document.querySelector('.pv[data-ad="820000"]').dispatchEvent(new MouseEvent('click', { bubbles: true })));
  await p.waitForTimeout(350);
  console.log('澳门面板禁用项 =', await p.evaluate(() => Array.from(document.querySelectorAll('#panelBd input[data-kind=c]')).filter(i => i.disabled).length),
    '/ 总数', await p.evaluate(() => document.querySelectorAll('#panelBd input[data-kind=c]').length));
  console.log('澳门面板含"无边界数据"字样 =', await p.evaluate(() => document.getElementById('panelBd').textContent.indexOf('无边界数据') >= 0));

  // 截图：珠江
  const box = await p.evaluate(() => { const r = document.getElementById('map').getBoundingClientRect(); return { x: r.x, y: r.y, w: r.width, h: r.height }; });
  await p.evaluate(() => { document.getElementById('btnClear').click(); });
  for (const ad of ['440000', '450000']) {
    await p.evaluate(a => document.querySelector('.pv[data-ad="' + a + '"]').dispatchEvent(new MouseEvent('click', { bubbles: true })), ad);
    await p.waitForTimeout(120);
    await p.evaluate(() => {
      const el = document.querySelector('#panelBd input[data-kind=r][data-id="zhujiang"]');
      if (el && !el.checked) { el.checked = true; el.dispatchEvent(new Event('change', { bubbles: true })); }
    });
  }
  await p.waitForTimeout(400);
  const t = await p.evaluate(() => { const e = document.querySelector('#gRiver text'); const a = e.getAttribute('x') * 1, c = e.getAttribute('y') * 1; return [a, c]; });
  const sx = box.x + t[0] / 1000 * box.w, sy = box.y + t[1] / 739 * box.h;
  await p.screenshot({ path: path.join(OUTDIR, 'f1-zhujiang-label.png'), clip: { x: Math.max(0, sx - 320), y: Math.max(0, sy - 240), width: 700, height: 480 } });

  console.log('\n== 运行时错误 ==', errs.length ? JSON.stringify(errs, null, 1) : '无');
  await b.close();
})().catch(e => { console.error('FATAL', e); process.exit(1); });

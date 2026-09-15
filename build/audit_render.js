// 只读渲染核查：加载成品 HTML，检查运行时错误、渲染元素计数、关键区域截图
//
// 用法: node audit_render.js <成品HTML路径> <输出目录>
// 需要 NODE_PATH 指向含 @playwright/test 的目录，例如 Windows Git Bash：
//   export NODE_PATH="$APPDATA/npm/node_modules"
//
// 交付前必须确认「运行时错误」一栏为「无」（pageerror 与 console.error 均为零）。
// 注意低对比度细线（1.5 px 浅色虚线）需 deviceScaleFactor:2 截图，否则会误判未渲染。
const { chromium } = require('@playwright/test');
const { pathToFileURL } = require('url');
const path = require('path');
const fs = require('fs');

const FILE = process.argv[2];
const OUTDIR = process.argv[3];
if (!fs.existsSync(OUTDIR)) fs.mkdirSync(OUTDIR, { recursive: true });

(async () => {
  const browser = await chromium.launch({ channel: 'chrome', headless: true });
  const page = await browser.newPage({ viewport: { width: 1800, height: 1100 }, deviceScaleFactor: 1 });
  const errs = [];
  page.on('console', m => { if (m.type() === 'error') errs.push('console: ' + m.text()); });
  page.on('pageerror', e => errs.push('pageerror: ' + e.message));

  await page.goto(pathToFileURL(FILE).href, { waitUntil: 'load' });
  await page.waitForTimeout(1200);

  const r = await page.evaluate(() => ({
    provPaths: document.querySelectorAll('#gProv path').length,
    provWithD: Array.from(document.querySelectorAll('#gProv path')).filter(p => (p.getAttribute('d') || '').length > 0).length,
    insetPaths: document.querySelectorAll('#gInset path').length,
    jdPaths: document.querySelectorAll('#gInset path.jd').length,
    islandDots: document.querySelectorAll('#gInset circle').length,
    labels: document.querySelectorAll('#gLabel text').length,
    labelTexts: Array.from(document.querySelectorAll('#gLabel text')).map(t => t.textContent),
    stats: document.getElementById('panelBd').textContent.replace(/\s+/g, ' ').trim().slice(0, 120),
    legend: document.getElementById('legend').textContent.replace(/\s+/g, ' ').trim(),
    insetLabel: Array.from(document.querySelectorAll('#gInset text')).map(t => t.textContent),
    mapAspect: (() => { const b = document.getElementById('map').getBoundingClientRect(); return [Math.round(b.width), Math.round(b.height)]; })(),
  }));
  console.log('初始渲染:', JSON.stringify(r, null, 1));

  // ---- 截图 1：整页初始态 ----
  await page.screenshot({ path: path.join(OUTDIR, 'v1-initial.png'), fullPage: false });

  // ---- 南海诸岛附图放大截图 ----
  const mapBox = await page.evaluate(() => { const b = document.getElementById('map').getBoundingClientRect(); return { x: b.x, y: b.y, w: b.width, h: b.height }; });
  await page.screenshot({
    path: path.join(OUTDIR, 'v2-inset.png'),
    clip: { x: Math.max(0, mapBox.x + mapBox.w * 0.78), y: Math.max(0, mapBox.y + mapBox.h * 0.68), width: Math.min(360, mapBox.w * 0.24), height: Math.min(300, mapBox.h * 0.34) }
  });

  // ---- 勾选全部 11 个区划，看整体框选 ----
  await page.evaluate(() => {
    document.querySelectorAll('#panelBd input[data-kind=region]').forEach(el => { el.checked = true; el.dispatchEvent(new Event('change', { bubbles: true })); });
  });
  await page.waitForTimeout(700);
  const r2 = await page.evaluate(() => ({
    regionPaths: document.querySelectorAll('#gReg path').length,
    regionTexts: Array.from(document.querySelectorAll('#gRText text')).map(t => t.textContent),
    legend: document.getElementById('legend').textContent.replace(/\s+/g, ' ').trim(),
    labelsLeft: document.querySelectorAll('#gLabel text').length,
  }));
  console.log('全选区划:', JSON.stringify(r2, null, 1));
  await page.screenshot({ path: path.join(OUTDIR, 'v3-allregions.png') });

  // ---- 清空后选台湾，验证 710000 展示 ----
  await page.evaluate(() => document.getElementById('btnClear').click());
  await page.waitForTimeout(200);
  await page.evaluate(() => document.querySelector('.pv[data-ad="710000"]').dispatchEvent(new MouseEvent('click', { bubbles: true })));
  await page.waitForTimeout(400);
  const r3 = await page.evaluate(() => ({
    hd: document.getElementById('panelHd').textContent.replace(/\s+/g, ' ').trim(),
    pointItems: Array.from(document.querySelectorAll('#panelBd input[data-kind=p]')).map(i => i.dataset.id),
    cityItems: document.querySelectorAll('#panelBd input[data-kind=c]').length,
    mountainItems: Array.from(document.querySelectorAll('#panelBd input[data-kind=m]')).map(i => i.dataset.id),
    lakeItems: Array.from(document.querySelectorAll('#panelBd input[data-kind=l]')).map(i => i.dataset.id),
    riverItems: Array.from(document.querySelectorAll('#panelBd input[data-kind=r]')).map(i => i.dataset.id),
    regionItems: Array.from(document.querySelectorAll('#panelBd input[data-kind=region]')).map(i => i.dataset.id),
    cityPaths: document.querySelectorAll('#gCity path').length,
  }));
  console.log('台湾选中:', JSON.stringify(r3, null, 1));
  await page.screenshot({ path: path.join(OUTDIR, 'v4-taiwan.png') });

  // ---- 澳门：验证空几何堂区 ----
  await page.evaluate(() => document.querySelector('.pv[data-ad="820000"]').dispatchEvent(new MouseEvent('click', { bubbles: true })));
  await page.waitForTimeout(400);
  const r4 = await page.evaluate(() => ({
    hd: document.getElementById('panelHd').textContent.replace(/\s+/g, ' ').trim(),
    cities: Array.from(document.querySelectorAll('#panelBd input[data-kind=c]')).map(i => i.dataset.id),
    cityPaths: document.querySelectorAll('#gCity path').length,
  }));
  console.log('澳门选中:', JSON.stringify(r4, null, 1));

  // ---- 澳门堂区勾选（空几何）是否报错、是否有反馈 ----
  await page.evaluate(() => {
    const el = document.querySelector('#panelBd input[data-kind=c]');
    if (el) { el.checked = true; el.dispatchEvent(new Event('change', { bubbles: true })); }
  });
  await page.waitForTimeout(400);
  const r5 = await page.evaluate(() => ({
    markChildren: document.querySelectorAll('#gMark > *').length,
    markTexts: Array.from(document.querySelectorAll('#gMark text')).map(t => t.textContent),
    legend: document.getElementById('legend').textContent.replace(/\s+/g, ' ').trim(),
  }));
  console.log('澳门空几何堂区勾选后:', JSON.stringify(r5, null, 1));

  // ---- 山东：检查华北/黄淮归属与描述文字矛盾 ----
  await page.evaluate(() => { document.getElementById('btnClear').click(); });
  await page.waitForTimeout(150);
  await page.evaluate(() => document.querySelector('.pv[data-ad="370000"]').dispatchEvent(new MouseEvent('click', { bubbles: true })));
  await page.waitForTimeout(400);
  const r6 = await page.evaluate(() => {
    const items = Array.from(document.querySelectorAll('#panelBd .item'));
    return items.slice(0, 4).map(it => it.textContent.replace(/\s+/g, ' ').trim());
  });
  console.log('山东区划条目:', JSON.stringify(r6, null, 1));
  await page.screenshot({ path: path.join(OUTDIR, 'v5-shandong.png') });

  // ---- 福建：检查江南/华南方位矛盾 ----
  await page.evaluate(() => document.querySelector('.pv[data-ad="350000"]').dispatchEvent(new MouseEvent('click', { bubbles: true })));
  await page.waitForTimeout(400);
  const r7 = await page.evaluate(() => Array.from(document.querySelectorAll('#panelBd .item')).slice(0, 4).map(it => it.textContent.replace(/\s+/g, ' ').trim()));
  console.log('福建区划条目:', JSON.stringify(r7, null, 1));

  // ---- 放大看山脉范围与河流（四川）----
  await page.evaluate(() => document.querySelector('.pv[data-ad="510000"]').dispatchEvent(new MouseEvent('click', { bubbles: true })));
  await page.waitForTimeout(300);
  await page.evaluate(() => {
    document.querySelectorAll('#panelBd input[data-kind=m]').forEach(el => { el.checked = true; el.dispatchEvent(new Event('change', { bubbles: true })); });
  });
  await page.waitForTimeout(700);
  const r8 = await page.evaluate(() => ({ markPaths: document.querySelectorAll('#gMark path.mka').length, texts: document.querySelectorAll('#gMark text').length }));
  console.log('四川全部山脉范围:', JSON.stringify(r8, null, 1));
  await page.screenshot({ path: path.join(OUTDIR, 'v6-sichuan-mtn.png') });

  console.log('\n== 运行时错误 ==', errs.length ? JSON.stringify(errs, null, 1) : '无');
  await browser.close();
})().catch(e => { console.error('FATAL', e); process.exit(1); });

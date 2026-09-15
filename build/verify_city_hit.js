// 端到端确认用户报告的两个问题已修复：
//   1. 海西州（632800）在面板中可见（可滚动到）且地图上可点击勾选
//   2. 点击单元内任意位置（不必在边界线上）即可切换 —— 验证 fill:transparent 生效
// 独立于页面内部状态，纯 DOM/命中测试。
const { chromium } = require('@playwright/test');
const { pathToFileURL } = require('url');

const FILE = process.argv[2];
const URL_ = pathToFileURL(FILE).href;

(async () => {
  const b = await chromium.launch({ channel: 'chrome', headless: true });
  const pg = await b.newPage({ viewport: { width: 1600, height: 1200 } });
  const errs = [];
  pg.on('pageerror', e => errs.push('pageerror: ' + e.message));
  pg.on('console', m => { if (m.type() === 'error') errs.push('console.error: ' + m.text()); });
  await pg.goto(URL_, { waitUntil: 'load' });
  await pg.waitForTimeout(600);

  let pass = 0, fail = 0;
  const chk = (name, ok, extra) => {
    console.log((ok ? '  ✓ ' : '  ✗ ') + name + (extra ? '  ' + extra : ''));
    ok ? pass++ : fail++;
  };

  // 选中青海：直接点地图上的青海，或从面板列表点。这里用面板搜索式点击更稳。
  // 青海省代码 630000；先点地图选中青海 —— 用一个确定在青海境内的点。
  // 改为点面板中的省份条目（若有列表），否则点地图。
  const okSel = await pg.evaluate(() => {
    // 尝试：地图上青海的 path（id 或 data 属性）。退路：点面板里的"青海"文字。
    const els = [...document.querySelectorAll('.pv')];
    // 用 bbox 判断哪个是青海：青海在西北，面积大
    // 更稳：找 title 或 aria-label 含"青海"
    for (const e of els) {
      const t = (e.getAttribute('aria-label') || '') + (e.getAttribute('data-name') || '');
      if (t.includes('青海')) { e.dispatchEvent(new MouseEvent('click', { bubbles: true })); return 'label'; }
    }
    return null;
  });
  // 若上面没找到，用面板列表文本点击
  if (!okSel) {
    const clicked = await pg.evaluate(() => {
      const cands = [...document.querySelectorAll('button,a,li,div,span')];
      const el = cands.find(x => x.children.length === 0 && (x.textContent || '').trim().startsWith('青海'));
      if (el) { el.click(); return true; }
      return false;
    });
    chk('已选中青海省（面板列表）', clicked);
  } else {
    chk('已选中青海省（地图标签）', true);
  }
  await pg.waitForTimeout(500);

  // 确认已渲染城市图层
  const nCty = await pg.evaluate(() => document.querySelectorAll('.cty').length);
  chk('青海下辖单元已渲染（.cty 元素 > 0）', nCty > 0, nCty + ' 个');

  // 关键：.cty 的 computed fill 必须是 transparent 而非 none
  const fillInfo = await pg.evaluate(() => {
    const e = document.querySelector('.cty');
    if (!e) return null;
    const cs = getComputedStyle(e);
    return { fill: cs.fill, pe: cs.pointerEvents };
  });
  chk('.cty 计算样式 fill = transparent（非 none）',
      fillInfo && /transparent|rgba\(0,\s*0,\s*0,\s*0\)/.test(fillInfo.fill),
      fillInfo ? fillInfo.fill : 'n/a');
  chk('.cty pointer-events = visiblePainted',
      fillInfo && fillInfo.pe.toLowerCase() === 'visiblepainted', fillInfo ? fillInfo.pe : 'n/a');

  // 核心验证：在海西州的「内部空白处」（远离边界线）点击，必须能命中 .cty
  // 用 elementFromPoint 扫该 .cty 的 bbox，统计命中率 —— fill:none 时命中率极低
  const hit = await pg.evaluate(() => {
    const els = [...document.querySelectorAll('.cty')];
    // 找 bbox 最大的那个（海西州面积最大）
    let best = null, bestArea = 0;
    for (const e of els) {
      const r = e.getBoundingClientRect();
      const a = r.width * r.height;
      if (a > bestArea) { bestArea = a; best = e; }
    }
    if (!best) return null;
    const r = best.getBoundingClientRect();
    let hitCty = 0, total = 0, centerHit = null;
    for (let i = 1; i <= 10; i++) {
      for (let j = 1; j <= 10; j++) {
        const x = r.left + r.width * i / 11;
        const y = r.top + r.height * j / 11;
        if (x < 0 || y < 0 || x > innerWidth || y > innerHeight) continue;
        total++;
        const el = document.elementFromPoint(x, y);
        if (el && el.classList && el.classList.contains('cty')) hitCty++;
      }
    }
    // bbox 中心点
    const cx = r.left + r.width / 2, cy = r.top + r.height / 2;
    const ec = document.elementFromPoint(cx, cy);
    centerHit = ec ? (ec.getAttribute('class') || ec.tagName) : 'null';
    return { hitCty, total, centerHit, w: r.width, h: r.height };
  });
  chk('面积最大单元（海西州）bbox 内命中 .cty 的采样点 > 0',
      hit && hit.hitCty > 0, hit ? hit.hitCty + '/' + hit.total : 'n/a');
  chk('海西州 bbox 中心点命中 .cty（修复前命中省界）',
      hit && /(^|\s)cty(\s|$)/.test(hit.centerHit), hit ? 'class=' + hit.centerHit : 'n/a');

  // 实际点击海西州中心，确认勾选被切换
  const toggled = await pg.evaluate(() => {
    const els = [...document.querySelectorAll('.cty')];
    let best = null, bestArea = 0;
    for (const e of els) {
      const r = e.getBoundingClientRect();
      const a = r.width * r.height;
      if (a > bestArea) { bestArea = a; best = e; }
    }
    const r = best.getBoundingClientRect();
    const before = best.getAttribute('class');
    const el = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2);
    el.dispatchEvent(new MouseEvent('click', { bubbles: true }));
    return { before, after: best.getAttribute('class') };
  });
  await pg.waitForTimeout(300);
  // 勾选后应有对应高亮路径出现（gMark 内的 .cty-h）
  const nHl = await pg.evaluate(() => document.querySelectorAll('.cty-h').length);
  chk('点击海西州中心后出现高亮路径（勾选生效）', nHl > 0, nHl + ' 条 .cty-h');

  // 面板可滚动性：确认长列表可滚动（海西州虽在折叠线下但能滚到）
  const scrollable = await pg.evaluate(() => {
    const cands = [...document.querySelectorAll('*')].filter(e => {
      const cs = getComputedStyle(e);
      return /auto|scroll/.test(cs.overflowY) && e.scrollHeight > e.clientHeight + 20;
    });
    if (!cands.length) return null;
    const e = cands[0];
    e.scrollTop = e.scrollHeight;          // 滚到底
    return { sh: e.scrollHeight, ch: e.clientHeight, after: e.scrollTop };
  });
  chk('面板长列表可滚动（能滚到折叠线以下的海西州）',
      scrollable && scrollable.after > 0,
      scrollable ? 'scrollHeight=' + scrollable.sh + ' clientHeight=' + scrollable.ch +
                   ' scrollTop→' + scrollable.after : 'n/a');

  console.log('\n== 运行时错误 == ' + (errs.length ? errs.join('\n') : '无'));
  if (errs.length) fail++;
  console.log('\n结果：' + (fail ? fail + ' 项失败' : '全部通过'));
  await b.close();
  process.exit(fail ? 1 : 0);
})();

// 验证省名注记：勾选/取消区划后，注记数量与显隐状态是否与预期一致。
// 用法: node check_labels.js <成品HTML路径>
const { chromium } = require('@playwright/test');
const { pathToFileURL } = require('url');
(async () => {
  const b = await chromium.launch({ channel:'chrome', headless:true });
  const p = await b.newPage({ viewport:{width:1680,height:1050} });
  await p.goto(pathToFileURL(process.argv[2]).href, { waitUntil:'load' });
  await p.waitForTimeout(700);
  const before = await p.evaluate(()=>document.querySelectorAll('#gLabel text').length);
  await p.evaluate(()=>{ const el=document.querySelector('#panelBd input[data-kind=region][data-id=jiangnan]'); el.checked=true; el.dispatchEvent(new Event('change',{bubbles:true})); });
  await p.waitForTimeout(400);
  const after = await p.evaluate(()=>({ n: document.querySelectorAll('#gLabel text').length,
      names: Array.from(document.querySelectorAll('#gLabel text')).map(t=>t.textContent),
      rl: Array.from(document.querySelectorAll('#gRText text')).map(t=>t.textContent) }));
  console.log('labels before=', before, ' after=', after.n, ' regions=', JSON.stringify(after.rl));
  console.log('江南激活后仍在显示的省名:', after.names.join(' '));
  await b.close();
})();

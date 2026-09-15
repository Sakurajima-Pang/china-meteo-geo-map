// 分省截取河流走向（默认广东/广西/贵州），用于人工核对珠江系统的拼接效果。
// 用法: node shot_river.js <成品HTML路径> <输出目录>
const { chromium } = require('@playwright/test');
const { pathToFileURL } = require('url');
const path = require('path');
(async () => {
  const b = await chromium.launch({ channel:'chrome', headless:true });
  const p = await b.newPage({ viewport:{width:1300,height:950}, deviceScaleFactor:2 });
  const errs=[]; p.on('pageerror',e=>errs.push(e.message)); p.on('console',m=>{if(m.type()==='error')errs.push(m.text());});
  await p.goto(pathToFileURL(process.argv[2]).href,{waitUntil:'load'});
  await p.waitForTimeout(700);
  for (const ad of ['440000','450000','520000']) {
    await p.evaluate(a => document.querySelector('.pv[data-ad="'+a+'"]').dispatchEvent(new MouseEvent('click',{bubbles:true})), ad);
    await p.waitForTimeout(200);
    await p.evaluate(() => { const el=document.querySelector('#panelBd input[data-kind=r][data-id="zhujiang"]');
      if(el && !el.checked){ el.checked=true; el.dispatchEvent(new Event('change',{bubbles:true})); } });
  }
  await p.waitForTimeout(300);
  console.log('gRiver 路径数 =', await p.evaluate(()=>document.querySelectorAll('#gRiver path').length));
  const box = await p.evaluate(()=>{ const r=document.getElementById('map').getBoundingClientRect(); return {x:r.x,y:r.y,w:r.width,h:r.height}; });
  console.log('svg box', JSON.stringify(box));
  // 经纬度 -> 屏幕坐标（与页面同一投影算法）
  const at = (lng,lat)=>{
    const R=Math.PI/180, m=(x,y)=>[x*R, Math.log(Math.tan(Math.PI/4+y*R/2))];
    const p0=m(73,17.6), p1=m(135.5,53.8);
    const w=p1[0]-p0[0], h=p1[1]-p0[1];
    const s=Math.min((1000-12)/w,(739-12)/h), ox=(1000-w*s)/2, oy=(739-h*s)/2;
    const q=m(lng,lat);
    return [ox+(q[0]-p0[0])*s, oy+(p1[1]-q[1])*s];
  };
  const t = at(110.5, 23.2);
  const sx = box.x + t[0]/1000*box.w, sy = box.y + t[1]/739*box.h;
  console.log('目标屏幕坐标', sx.toFixed(0), sy.toFixed(0));
  for(let i=0;i<8;i++){ await p.mouse.move(sx, sy); await p.mouse.wheel(0,-400); await p.waitForTimeout(70); }
  await p.waitForTimeout(400);
  console.log('viewBox', await p.evaluate(()=>document.getElementById('map').getAttribute('viewBox')));
  await p.screenshot({ path: path.join(process.argv[3],'shot-14-zhujiang.png'), clip:{x:Math.max(0,sx-420),y:Math.max(90,sy-360),width:840,height:640} });
  console.log('错误:', errs.length?JSON.stringify(errs):'无');
  await b.close();
})();

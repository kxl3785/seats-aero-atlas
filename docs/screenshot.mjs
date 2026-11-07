import { spawn } from 'node:child_process';
// Regenerates the README screenshots with headless Chrome (Node 22+, no dependencies).
// Serve dist/ first, e.g.  python3 -m http.server 8766 --directory dist
// then:                    node docs/screenshot.mjs http://127.0.0.1:8766/index.html docs/screenshots
import { writeFileSync, mkdirSync, mkdtempSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
const [,, pageUrl, outDir] = process.argv;
mkdirSync(outDir, { recursive: true });
const chrome = spawn(process.env.CHROME || "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
  ['--headless=new', '--remote-debugging-port=9333', `--user-data-dir=${mkdtempSync(join(tmpdir(), 'atlas-chrome-'))}`, '--hide-scrollbars',
   '--window-size=1440,900', '--force-color-profile=srgb', 'about:blank'], { stdio: 'ignore' });
const sleep = ms => new Promise(r => setTimeout(r, ms));
let target;
for (let i = 0; i < 50 && !target; i++) {
  await sleep(200);
  try { target = (await (await fetch('http://127.0.0.1:9333/json/list')).json()).find(t => t.type === 'page'); } catch {}
}
const ws = new WebSocket(target.webSocketDebuggerUrl);
await new Promise(r => ws.onopen = r);
let id = 0; const pending = new Map();
ws.onmessage = ev => { const m = JSON.parse(ev.data); if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); } };
const send = (method, params = {}) => new Promise(r => { const i = ++id; pending.set(i, r); ws.send(JSON.stringify({ id: i, method, params })); });
const evalJs = async expr => (await send('Runtime.evaluate', { expression: expr, awaitPromise: true, returnByValue: true })).result?.result?.value;
await send('Emulation.setDeviceMetricsOverride', { width: 1440, height: 900, deviceScaleFactor: 1.5, mobile: false });
await send('Page.enable');
await send('Page.navigate', { url: pageUrl });
await sleep(4000);
const rect = sel => evalJs(`(()=>{const e=document.querySelector(${JSON.stringify(sel)}); const r=e.getBoundingClientRect(); return {x:r.left+scrollX, y:r.top+scrollY, w:r.width, h:r.height};})()`);
async function shot(name, clip, pad = 16) {
  const res = await send('Page.captureScreenshot', { format: 'png', captureBeyondViewport: true,
    clip: { x: Math.max(0, clip.x - pad), y: Math.max(0, clip.y - pad), width: clip.w + 2 * pad, height: clip.h + 2 * pad, scale: 1 } });
  writeFileSync(`${outDir}/${name}.png`, Buffer.from(res.result.data, 'base64'));
  console.log('saved', name, Math.round(clip.w), 'x', Math.round(clip.h));
}
// 1. Header, stats and filters
const top = await rect('.top'), filt = await rect('.filters');
await shot('overview', { x: top.x, y: top.y, w: Math.max(top.w, filt.w), h: filt.y + filt.h - top.y });
// 2. Globe and best picks, turned to Europe
await evalJs(`document.querySelector('#f-region button[data-v="Europe"]').click()`); await sleep(2500);
await shot('globe', await rect('.atlas'));
await evalJs(`document.querySelector('#f-region button[data-v="all"]').click()`); await sleep(1500);
// 3. Points vs cash chart
await shot('chart', await rect('.scatter-card'));
// 4. Table: Europe, one city expanded with its date chips open
await evalJs(`(async()=>{ document.querySelector('#f-region button[data-v="Europe"]').click(); await new Promise(r=>setTimeout(r,800));
  document.getElementById('t-collapse').click();
  const g=[...document.querySelectorAll('#rows tr.grp')].find(t=>t.dataset.g==='JFK'||t.dataset.g==='MAD') || document.querySelector('#rows tr.grp');
  g.querySelector('.grp-btn').click(); await new Promise(r=>setTimeout(r,300));
  const d=document.querySelector('#rows tr.opt:not([hidden]) details'); if(d) d.open=true; return true; })()`);
await sleep(800);
const tbl = await rect('.table-card');
await shot('table', { x: tbl.x, y: tbl.y, w: tbl.w, h: Math.min(tbl.h, 1150) });
ws.close(); chrome.kill();

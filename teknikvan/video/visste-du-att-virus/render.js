// Renderar scen.html bildruta för bildruta till MP4 (utan ljud).
// Användning:
//   node render.js preview <utmapp> t1 t2 ...   -> PNG-bilder vid angivna sekunder
//   node render.js video <ut.mp4> <timeline.json> [fps]
const { chromium } = require('playwright');
const { spawn } = require('child_process');
const fs = require('fs');
const path = require('path');

(async () => {
  const [mode, out, ...rest] = process.argv.slice(2);
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1080, height: 1920 }, deviceScaleFactor: 1 });
  await page.goto('file://' + path.join(__dirname, 'scen.html'));
  await page.evaluate(() => document.fonts.ready);
  const info = await page.evaluate(() => window.TIMELINE);

  if (mode === 'preview') {
    fs.mkdirSync(out, { recursive: true });
    const times = rest.length ? rest.map(Number) : [];
    for (const t of times) {
      await page.evaluate(t => render(t), t);
      await page.screenshot({ path: path.join(out, `f_${t.toFixed(2)}.png`) });
    }
    console.log('total', info.total.toFixed(2));
  } else {
    const [tlPath, fpsArg] = rest;
    fs.writeFileSync(tlPath, JSON.stringify(info, null, 1));
    const fps = Number(fpsArg || 30);
    const N = Math.ceil(info.total * fps);
    const ff = spawn('ffmpeg', ['-y', '-loglevel', 'error', '-f', 'image2pipe', '-framerate', String(fps), '-c:v', 'mjpeg', '-i', '-',
      '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '18', '-preset', 'medium', '-movflags', '+faststart', out], { stdio: ['pipe', 'inherit', 'inherit'] });
    const t0 = Date.now();
    for (let i = 0; i < N; i++) {
      await page.evaluate(t => render(t), i / fps);
      const buf = await page.screenshot({ type: 'jpeg', quality: 93 });
      if (!ff.stdin.write(buf)) await new Promise(r => ff.stdin.once('drain', r));
      if (i % 150 === 0) console.log(`ruta ${i}/${N} (${((Date.now() - t0) / 1000).toFixed(0)} s)`);
    }
    ff.stdin.end();
    await new Promise(r => ff.on('close', r));
    console.log('klar', out, N, 'rutor');
  }
  await browser.close();
})();

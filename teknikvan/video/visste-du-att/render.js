// Renderar motor.html bildruta för bildruta.
//   node render.js preview <voice.json> <utmapp> t1 t2 ...   -> PNG vid angivna sekunder
//   node render.js video   <voice.json> <ut.mp4>              -> MP4 utan ljud
const { chromium } = require('playwright');
const { spawn } = require('child_process');
const fs = require('fs');
const path = require('path');

(async () => {
  const [mode, voicePath, out, ...rest] = process.argv.slice(2);
  const data = JSON.parse(fs.readFileSync(voicePath, 'utf8'));
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1080, height: 1920 }, deviceScaleFactor: 1 });
  await page.goto('file://' + path.join(__dirname, 'motor.html'));
  await page.evaluate(() => document.fonts.ready);
  await page.evaluate(d => init(d), data);
  const fps = data.fps || 30;

  if (mode === 'preview') {
    fs.mkdirSync(out, { recursive: true });
    for (const t of rest.map(Number)) {
      await page.evaluate(t => render(t), t);
      await page.screenshot({ path: path.join(out, `f_${String(t.toFixed(2)).padStart(6, '0')}.png`) });
    }
  } else {
    const N = Math.ceil(data.total * fps);
    const ff = spawn('ffmpeg', ['-y', '-loglevel', 'error', '-f', 'image2pipe', '-framerate', String(fps), '-c:v', 'mjpeg', '-i', '-',
      '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '18', '-preset', 'medium', '-movflags', '+faststart', out], { stdio: ['pipe', 'inherit', 'inherit'] });
    const t0 = Date.now();
    for (let i = 0; i < N; i++) {
      await page.evaluate(t => render(t), i / fps);
      const buf = await page.screenshot({ type: 'jpeg', quality: 93 });
      if (!ff.stdin.write(buf)) await new Promise(r => ff.stdin.once('drain', r));
      if (i % 300 === 0) console.log(`${path.basename(out)}: ruta ${i}/${N} (${((Date.now() - t0) / 1000).toFixed(0)} s)`);
    }
    ff.stdin.end();
    await new Promise(r => ff.on('close', r));
    console.log('klar', out);
  }
  await browser.close();
})();

// Renders index.html frame by frame with headless Chromium and encodes with ffmpeg.
//   node scripts/render.mjs                    -> out/paperdrop-sales.mp4 (needs out/music.wav)
//   node scripts/render.mjs --stills 1,9.5,30  -> out/stills/*.png for quick review
//   node scripts/render.mjs --cues             -> out/cues.json (sound-effect timeline)
import { spawn, execSync } from 'node:child_process';
import { mkdirSync, writeFileSync, existsSync, rmSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import os from 'node:os';

// Use a local playwright if installed, otherwise the globally installed one.
const { chromium } = await import('playwright').catch(() => import(execSync('npm root -g').toString().trim() + '/playwright/index.mjs'));
const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..');
const OUT = join(ROOT, 'out');
const URL = pathToFileURL(join(ROOT, 'index.html')).href;
const args = process.argv.slice(2);
const flag = n => { const i = args.indexOf(n); return i < 0 ? null : (args[i + 1] ?? true); };
mkdirSync(OUT, { recursive: true });

const launch = () => chromium.launch({ args: ['--force-color-profile=srgb', '--disable-lcd-text', '--font-render-hinting=none'] });
async function openPage(browser) {
  const page = await browser.newPage({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 1 });
  await page.goto(URL);
  await page.evaluate(() => window.READY);
  return page;
}

const browser = await launch();
try {
  if (flag('--cues')) {
    const page = await openPage(browser);
    const cues = await page.evaluate(() => ({ cues: window.CUES, ...window.VIDEO }));
    writeFileSync(join(OUT, 'cues.json'), JSON.stringify(cues, null, 1));
    console.log(`cues: ${cues.cues.length}`);
  } else if (flag('--stills')) {
    const page = await openPage(browser);
    const dir = join(OUT, 'stills'); mkdirSync(dir, { recursive: true });
    for (const t of String(flag('--stills')).split(',').map(Number)) {
      await page.evaluate(t => window.seek(t), t);
      await page.screenshot({ path: join(dir, `t${t.toFixed(2).padStart(6, '0')}.png`) });
    }
    console.log('stills ->', dir);
  } else {
    const { FPS, DURATION } = await (await openPage(browser)).evaluate(() => window.VIDEO);
    const total = Math.round(FPS * DURATION);
    const workers = Math.max(1, Math.min(os.cpus().length, 4));
    const per = Math.ceil(total / workers);
    const segs = [];
    const t0 = Date.now();
    let done = 0;
    await Promise.all([...Array(workers)].map(async (_, w) => {
      const from = w * per, to = Math.min(total, from + per);
      const seg = join(OUT, `seg${w}.mp4`); segs[w] = seg;
      const ff = spawn('ffmpeg', ['-y', '-loglevel', 'error', '-f', 'image2pipe', '-framerate', String(FPS), '-i', '-',
        '-c:v', 'libx264', '-preset', 'medium', '-crf', '18', '-pix_fmt', 'yuv420p', '-r', String(FPS), seg], { stdio: ['pipe', 'inherit', 'inherit'] });
      const page = await openPage(browser);
      for (let f = from; f < to; f++) {
        await page.evaluate(t => window.seek(t), f / FPS);
        const buf = await page.screenshot({ type: 'jpeg', quality: 95 });
        if (!ff.stdin.write(buf)) await new Promise(r => ff.stdin.once('drain', r));
        if (++done % 150 === 0) console.log(`${done}/${total} frames  ${((Date.now() - t0) / 1000).toFixed(0)}s`);
      }
      ff.stdin.end();
      await new Promise((res, rej) => ff.on('close', c => c ? rej(new Error('ffmpeg ' + c)) : res()));
    }));
    const list = join(OUT, 'segs.txt');
    writeFileSync(list, segs.map(s => `file '${s}'`).join('\n'));
    const music = join(OUT, 'music.wav');
    const final = join(OUT, 'paperdrop-sales.mp4');
    const ffArgs = ['-y', '-loglevel', 'error', '-f', 'concat', '-safe', '0', '-i', list];
    if (existsSync(music)) ffArgs.push('-i', music, '-af', 'loudnorm=I=-14:TP=-1.5:LRA=11', '-ar', '48000', '-c:a', 'aac', '-b:a', '192k', '-shortest');
    ffArgs.push('-c:v', 'copy', '-movflags', '+faststart', final);
    await new Promise((res, rej) => spawn('ffmpeg', ffArgs, { stdio: 'inherit' }).on('close', c => c ? rej(new Error('ffmpeg concat ' + c)) : res()));
    segs.forEach(s => rmSync(s)); rmSync(list);
    console.log('video ->', final, `${((Date.now() - t0) / 1000).toFixed(0)}s`);
  }
} finally {
  await browser.close();
}

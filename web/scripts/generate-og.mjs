// Renders the 1200x630 social-share images (public/og-es.png, public/og-en.png).
//
//   PLAYWRIGHT_CORE=/path/to/playwright-core CHROME=/path/to/chrome node scripts/generate-og.mjs
//
// Both variables are optional: `playwright-core` is resolved normally and Playwright's
// own browser cache is used when CHROME is not set. Output is committed, so the
// site build never needs a browser.
import { pathToFileURL } from "node:url";
import { resolve } from "node:path";
import { readFileSync } from "node:fs";

const core = process.env.PLAYWRIGHT_CORE ? resolve(process.env.PLAYWRIGHT_CORE, "index.mjs") : "playwright-core";
const { chromium } = await import(process.env.PLAYWRIGHT_CORE ? pathToFileURL(core).href : core);

const root = resolve(import.meta.dirname, "..");
const font = readFileSync(
  resolve(root, "node_modules/@fontsource-variable/bricolage-grotesque/files/bricolage-grotesque-latin-wdth-normal.woff2"),
).toString("base64");

const copy = {
  es: { title: "Cierra la cámara con la mano abierta.", sub: "Cámara virtual con control por gestos para videollamadas", chip: "Gratis · código abierto · privada" },
  en: { title: "Cover the camera with an open palm.", sub: "A virtual camera you control with your hands, for video calls", chip: "Free · open source · private" },
};

const page = (lang) => `<!doctype html><html><head><meta charset="utf-8"><style>
@font-face { font-family: "Bricolage"; src: url(data:font/woff2;base64,${font}) format("woff2"); font-weight: 200 800; font-stretch: 75% 100%; }
* { box-sizing: border-box; margin: 0; }
body { width: 1200px; height: 630px; background: #0f1214; color: #eceee9; font-family: "Bricolage", system-ui, sans-serif; position: relative; overflow: hidden; }
.glow { position: absolute; right: -140px; top: -120px; width: 720px; height: 720px; border-radius: 50%; background: radial-gradient(circle, rgba(255,91,56,.28), rgba(255,91,56,0) 62%); }
.wrap { position: absolute; inset: 0; padding: 68px 76px; display: flex; flex-direction: column; justify-content: space-between; }
.brand { display: flex; align-items: center; gap: 18px; font-size: 40px; font-weight: 700; font-stretch: 82%; letter-spacing: -.01em; }
.brand svg { width: 56px; height: 56px; }
h1 { font-size: 88px; line-height: .98; font-weight: 720; font-stretch: 78%; letter-spacing: -.015em; max-width: 690px; }
.sub { margin-top: 22px; font-size: 30px; color: #9ba4ab; max-width: 720px; line-height: 1.25; }
.foot { display: flex; align-items: center; justify-content: space-between; font-size: 26px; color: #9ba4ab; }
.chip { border: 2px solid #2a3036; border-radius: 999px; padding: 10px 22px; color: #eceee9; }
.lens { position: absolute; right: 96px; top: 170px; width: 290px; height: 290px; }
</style></head><body>
<div class="glow"></div>
<svg class="lens" viewBox="0 0 32 32"><rect width="32" height="32" rx="9" fill="#15191c" stroke="#2a3036" stroke-width=".3"/><circle cx="16" cy="16" r="9" fill="none" stroke="#e8ebe6" stroke-width="2.4"/><circle cx="16" cy="16" r="3.4" fill="#e8ebe6"/><circle cx="25" cy="7" r="2.6" fill="#ff5b38"/></svg>
<div class="wrap">
  <div class="brand"><svg viewBox="0 0 32 32"><rect width="32" height="32" rx="9" fill="#e8ebe6"/><circle cx="16" cy="16" r="9" fill="none" stroke="#0f1214" stroke-width="2.4"/><circle cx="16" cy="16" r="3.4" fill="#0f1214"/><circle cx="25" cy="7" r="2.6" fill="#d93a17"/></svg>MirrorLab</div>
  <div><h1>${copy[lang].title}</h1><p class="sub">${copy[lang].sub}</p></div>
  <div class="foot"><span>Windows · macOS · Linux</span><span class="chip">${copy[lang].chip}</span><span>by TrinaxCode</span></div>
</div></body></html>`;

const browser = await chromium.launch({ executablePath: process.env.CHROME || undefined });
const context = await browser.newContext({ viewport: { width: 1200, height: 630 }, deviceScaleFactor: 1 });
for (const lang of ["es", "en"]) {
  const tab = await context.newPage();
  await tab.setContent(page(lang));
  await tab.evaluate(() => document.fonts.ready);
  await tab.screenshot({ path: resolve(root, `public/og-${lang}.png`) });
  await tab.close();
}
await browser.close();
console.log("wrote public/og-es.png and public/og-en.png");

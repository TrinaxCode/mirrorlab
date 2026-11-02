/**
 * Build-time SEO for a single-page app.
 *
 * A crawler that does not run JavaScript (social-card fetchers, most AI
 * crawlers, some search engines) only sees the HTML the server sends. Left alone,
 * that is an empty `<div id="root">`. This plugin makes the HTML itself carry
 * everything that matters, once per language:
 *
 *  - `/`    Spanish and `/en/` English, each with its own title, description,
 *           canonical URL, hreflang alternates, Open Graph / Twitter tags and
 *           JSON-LD (SoftwareApplication, WebSite, author, FAQPage);
 *  - a `<noscript>` copy of the page text, so the content is readable without JS;
 *  - `sitemap.xml` listing both languages with their alternates.
 *
 * The text comes from the same dictionary the React app renders, so the static
 * HTML and the live page cannot drift apart.
 */

import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import type { Plugin } from "vite";

import { STRINGS, pathForLang, type Dict, type Lang } from "./src/lib/i18n";
import { AUTHOR_NAME, AUTHOR_URL, RELEASES_URL, REPO_URL, SITE_NAME, SITE_URL } from "./src/lib/site";

const START = "<!--seo:start-->";
const END = "<!--seo:end-->";
const BODY_START = "<!--seo:body-start-->";
const BODY_END = "<!--seo:body-end-->";
const OG_IMAGE = { es: "/og-es.png", en: "/og-en.png" } as const;
const SCREENSHOT = "/screenshots/desktop-app.png";

const escapeHtml = (value: string): string =>
  value.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");

/** The package version, so the structured data never advertises a stale release. */
function packageVersion(): string {
  const file = resolve(import.meta.dirname, "../src/mirrorlab/version.py");
  if (!existsSync(file)) return "";
  const match = /__version_info__\s*=\s*\((\d+),\s*(\d+),\s*(\d+)\)/.exec(readFileSync(file, "utf8"));
  return match ? `${match[1]}.${match[2]}.${match[3]}` : "";
}

function urlFor(lang: Lang): string {
  return `${SITE_URL}${pathForLang(lang)}`;
}

function jsonLd(strings: Dict, lang: Lang, version: string): string {
  const author = { "@id": `${SITE_URL}/#author` };
  const graph = [
    {
      "@type": "WebSite",
      "@id": `${SITE_URL}/#website`,
      url: `${SITE_URL}/`,
      name: SITE_NAME,
      inLanguage: ["es", "en"],
      publisher: author,
    },
    {
      "@type": "Person",
      "@id": `${SITE_URL}/#author`,
      name: AUTHOR_NAME,
      url: AUTHOR_URL,
      sameAs: [AUTHOR_URL],
    },
    {
      "@type": "SoftwareApplication",
      "@id": `${SITE_URL}/#app`,
      name: SITE_NAME,
      url: urlFor(lang),
      description: strings.seo.description,
      applicationCategory: "MultimediaApplication",
      operatingSystem: "Windows, macOS, Linux",
      ...(version ? { softwareVersion: version } : {}),
      downloadUrl: RELEASES_URL,
      license: "https://opensource.org/licenses/MIT",
      isAccessibleForFree: true,
      inLanguage: lang,
      offers: { "@type": "Offer", price: "0", priceCurrency: "USD" },
      author,
      image: `${SITE_URL}${OG_IMAGE[lang]}`,
      screenshot: `${SITE_URL}${SCREENSHOT}`,
      sameAs: [REPO_URL],
    },
    {
      "@type": "FAQPage",
      "@id": `${urlFor(lang)}#faq`,
      inLanguage: lang,
      mainEntity: strings.faq.items.map((item) => ({
        "@type": "Question",
        name: item.q,
        acceptedAnswer: { "@type": "Answer", text: item.a },
      })),
    },
  ];
  // `<` is escaped so a stray "</script>" in the copy can never end the block early.
  return JSON.stringify({ "@context": "https://schema.org", "@graph": graph }).replace(/</g, "\\u003c");
}

/** Everything `<head>` needs for one language, between markers so it can be swapped. */
export function headTags(lang: Lang, version = ""): string {
  const strings = STRINGS[lang];
  const { seo } = strings;
  const other: Lang = lang === "es" ? "en" : "es";
  const image = `${SITE_URL}${OG_IMAGE[lang]}`;
  const tags = [
    `<title>${escapeHtml(seo.title)}</title>`,
    `<meta name="description" content="${escapeHtml(seo.description)}" />`,
    `<meta name="keywords" content="${escapeHtml(seo.keywords)}" />`,
    `<meta name="author" content="${AUTHOR_NAME}" />`,
    `<meta name="robots" content="index,follow,max-image-preview:large,max-snippet:-1" />`,
    `<link rel="canonical" href="${urlFor(lang)}" />`,
    `<link rel="alternate" hreflang="es" href="${urlFor("es")}" />`,
    `<link rel="alternate" hreflang="en" href="${urlFor("en")}" />`,
    `<link rel="alternate" hreflang="x-default" href="${urlFor("es")}" />`,
    `<link rel="me" href="${AUTHOR_URL}" />`,
    `<meta property="og:type" content="website" />`,
    `<meta property="og:site_name" content="${SITE_NAME}" />`,
    `<meta property="og:title" content="${escapeHtml(seo.ogTitle)}" />`,
    `<meta property="og:description" content="${escapeHtml(seo.ogDescription)}" />`,
    `<meta property="og:url" content="${urlFor(lang)}" />`,
    `<meta property="og:locale" content="${seo.ogLocale}" />`,
    `<meta property="og:locale:alternate" content="${STRINGS[other].seo.ogLocale}" />`,
    `<meta property="og:image" content="${image}" />`,
    `<meta property="og:image:width" content="1200" />`,
    `<meta property="og:image:height" content="630" />`,
    `<meta property="og:image:alt" content="${escapeHtml(seo.ogTitle)}" />`,
    `<meta name="twitter:card" content="summary_large_image" />`,
    `<meta name="twitter:title" content="${escapeHtml(seo.ogTitle)}" />`,
    `<meta name="twitter:description" content="${escapeHtml(seo.ogDescription)}" />`,
    `<meta name="twitter:image" content="${image}" />`,
    `<script type="application/ld+json">${jsonLd(strings, lang, version)}</script>`,
  ];
  return `${START}\n    ${tags.join("\n    ")}\n    ${END}`;
}

/** The page's text as plain HTML, for visitors and crawlers without JavaScript. */
export function noscriptBody(lang: Lang): string {
  const strings = STRINGS[lang];
  const { hero, features, download, privacy, faq, footer, install } = strings;
  const list = (items: string[]) => `<ul>${items.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>`;
  const html = `
      <main style="max-width:46rem;margin:0 auto;padding:2rem 1rem;font-family:system-ui,sans-serif;line-height:1.6">
        <h1>${escapeHtml(hero.title)}</h1>
        <p>${escapeHtml(strings.seo.description)}</p>
        <p><a href="${RELEASES_URL}">${escapeHtml(download.platforms.map((p) => p.name).join(" · "))} — ${escapeHtml(download.title)}</a></p>
        <h2>${escapeHtml(features.title)}</h2>
        <ul>${features.items.map((item) => `<li><strong>${escapeHtml(item.name)}.</strong> ${escapeHtml(item.body)}</li>`).join("")}</ul>
        <h2>${escapeHtml(download.title)}</h2>
        ${list(download.platforms.map((p) => `${p.name}: ${p.file} (${p.requirements})`))}
        <h2>${escapeHtml(privacy.title)}</h2>
        <ul>${privacy.facts.map((fact) => `<li><strong>${escapeHtml(fact.title)}.</strong> ${escapeHtml(fact.body)}</li>`).join("")}</ul>
        <h2>${escapeHtml(install.title)}</h2>
        <pre>pip install mirrorlab[vcam]\nmirrorlab doctor\nmirrorlab cam --profile meeting</pre>
        <h2>${escapeHtml(faq.title)}</h2>
        ${faq.items.map((item) => `<h3>${escapeHtml(item.q)}</h3><p>${escapeHtml(item.a)}</p>`).join("")}
        <p>${escapeHtml(footer.createdBy)} <a href="${AUTHOR_URL}" rel="author">${AUTHOR_NAME}</a> · <a href="${REPO_URL}">GitHub</a> · ${escapeHtml(footer.license)}</p>
        <p><a href="${urlFor(lang === "es" ? "en" : "es")}" hreflang="${lang === "es" ? "en" : "es"}">${escapeHtml(strings.other)}</a></p>
      </main>`;
  return `${BODY_START}\n    <noscript>${html}\n    </noscript>\n    ${BODY_END}`;
}

export function sitemap(lastmod: string): string {
  const alternates = (["es", "en"] as const)
    .map((lang) => `    <xhtml:link rel="alternate" hreflang="${lang}" href="${urlFor(lang)}" />`)
    .concat(`    <xhtml:link rel="alternate" hreflang="x-default" href="${urlFor("es")}" />`)
    .join("\n");
  const entries = (["es", "en"] as const)
    .map(
      (lang) => `  <url>
    <loc>${urlFor(lang)}</loc>
    <lastmod>${lastmod}</lastmod>
    <changefreq>monthly</changefreq>
    <priority>${lang === "es" ? "1.0" : "0.9"}</priority>
${alternates}
  </url>`,
    )
    .join("\n");
  return `<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:xhtml="http://www.w3.org/1999/xhtml">
${entries}
</urlset>
`;
}

/** Swap the language-specific blocks of an already generated page for another language's. */
function retarget(html: string, lang: Lang, version: string): string {
  const between = (source: string, start: string, end: string, replacement: string): string => {
    const from = source.indexOf(start);
    const to = source.indexOf(end);
    if (from === -1 || to === -1) throw new Error(`seo-plugin: marker ${start} is missing from index.html`);
    return source.slice(0, from) + replacement + source.slice(to + end.length);
  };
  let output = between(html, START, END, headTags(lang, version));
  output = between(output, BODY_START, BODY_END, noscriptBody(lang));
  return output.replace(/<html lang="[^"]*"/, `<html lang="${STRINGS[lang].htmlLang}"`);
}

export function seoPlugin(): Plugin {
  const version = packageVersion();
  let outDir = "dist";
  return {
    name: "mirrorlab-seo",
    configResolved(config) {
      outDir = resolve(config.root, config.build.outDir);
    },
    transformIndexHtml: {
      order: "pre",
      handler(html) {
        if (!html.includes("<!--seo:head-->") || !html.includes("<!--seo:body-->")) {
          throw new Error("seo-plugin: index.html needs the <!--seo:head--> and <!--seo:body--> placeholders");
        }
        return html
          .replace("<!--seo:head-->", headTags("es", version))
          .replace("<!--seo:body-->", noscriptBody("es"));
      },
    },
    closeBundle() {
      const source = resolve(outDir, "index.html");
      if (!existsSync(source)) return;
      const english = retarget(readFileSync(source, "utf8"), "en", version);
      const target = resolve(outDir, "en/index.html");
      mkdirSync(dirname(target), { recursive: true });
      writeFileSync(target, english);
      writeFileSync(resolve(outDir, "sitemap.xml"), sitemap(new Date().toISOString().slice(0, 10)));
    },
  };
}

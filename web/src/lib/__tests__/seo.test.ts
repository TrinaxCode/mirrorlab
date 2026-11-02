import { describe, expect, it } from "vitest";

import { headTags, noscriptBody, sitemap } from "../../../seo-plugin";
import { langFromPath, pathForLang, STRINGS } from "../i18n";
import { SITE_URL } from "../site";

function jsonLdOf(head: string): { "@graph": Array<Record<string, unknown>> } {
  const match = /<script type="application\/ld\+json">(.*?)<\/script>/s.exec(head);
  expect(match).not.toBeNull();
  return JSON.parse(match?.[1] ?? "{}") as { "@graph": Array<Record<string, unknown>> };
}

describe("language routing", () => {
  it("serves English from /en/ and leaves every other path to the stored choice", () => {
    expect(langFromPath("/en/")).toBe("en");
    expect(langFromPath("/en")).toBe("en");
    expect(langFromPath("/")).toBeNull();
    expect(langFromPath("/english")).toBeNull();
    expect(langFromPath("/index.html")).toBeNull();
  });

  it("round-trips a language through its path", () => {
    expect(pathForLang("en")).toBe("/en/");
    expect(pathForLang("es")).toBe("/");
    expect(langFromPath(pathForLang("en"))).toBe("en");
  });
});

describe.each(["es", "en"] as const)("head tags (%s)", (lang) => {
  const head = headTags(lang, "2.2.0");

  it("carries a title, description and canonical URL for that language", () => {
    expect(head).toContain(`<title>${STRINGS[lang].seo.title}</title>`);
    expect(head).toContain(`rel="canonical" href="${SITE_URL}${pathForLang(lang)}"`);
    expect(head).toContain('name="description"');
  });

  it("links both languages and a default for hreflang", () => {
    expect(head).toContain(`hreflang="es" href="${SITE_URL}/"`);
    expect(head).toContain(`hreflang="en" href="${SITE_URL}/en/"`);
    expect(head).toContain(`hreflang="x-default" href="${SITE_URL}/"`);
  });

  it("has Open Graph and Twitter cards pointing at an absolute image", () => {
    expect(head).toContain(`property="og:image" content="${SITE_URL}/og-${lang}.png"`);
    expect(head).toContain('name="twitter:card" content="summary_large_image"');
    expect(head).toContain(`property="og:locale" content="${STRINGS[lang].seo.ogLocale}"`);
  });

  it("describes the app, its author and its questions as valid JSON-LD", () => {
    const graph = jsonLdOf(head)["@graph"];
    const types = graph.map((node) => node["@type"]);
    expect(types).toEqual(["WebSite", "Person", "SoftwareApplication", "FAQPage"]);
    const app = graph.find((node) => node["@type"] === "SoftwareApplication");
    expect(app?.operatingSystem).toBe("Windows, macOS, Linux");
    expect(app?.softwareVersion).toBe("2.2.0");
    expect(app?.isAccessibleForFree).toBe(true);
    const author = graph.find((node) => node["@type"] === "Person");
    expect(author?.name).toBe("TrinaxCode");
    const faq = graph.find((node) => node["@type"] === "FAQPage");
    expect(faq?.mainEntity).toHaveLength(STRINGS[lang].faq.items.length);
  });

  it("keeps the title and description within what search results show", () => {
    expect(STRINGS[lang].seo.title.length).toBeLessThanOrEqual(70);
    expect(STRINGS[lang].seo.description.length).toBeLessThanOrEqual(320);
    expect(STRINGS[lang].seo.ogTitle.length).toBeLessThanOrEqual(70);
  });
});

describe("static body and sitemap", () => {
  it("includes the headline, the FAQ and the author link without JavaScript", () => {
    const body = noscriptBody("en");
    expect(body).toContain("<noscript>");
    expect(body).toContain(STRINGS.en.hero.title);
    expect(body).toContain(STRINGS.en.faq.items[0]?.q ?? "missing");
    expect(body).toContain("https://github.com/TrinaxCode");
  });

  it("escapes markup in copy instead of injecting it", () => {
    expect(noscriptBody("es")).not.toMatch(/<script/i);
  });

  it("lists both languages with alternates", () => {
    const xml = sitemap("2026-11-02");
    expect(xml).toContain(`<loc>${SITE_URL}/</loc>`);
    expect(xml).toContain(`<loc>${SITE_URL}/en/</loc>`);
    expect(xml.match(/hreflang="x-default"/g)).toHaveLength(2);
    expect(xml).toContain("<lastmod>2026-11-02</lastmod>");
  });
});

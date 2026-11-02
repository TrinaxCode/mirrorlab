import type { Dict, Lang } from "./i18n";
import { pathForLang } from "./i18n";
import { SITE_URL } from "./site";

function setMeta(selector: string, attribute: "content" | "href", value: string): void {
  document.head.querySelector(selector)?.setAttribute(attribute, value);
}

/**
 * Keep the tags a crawler or a share preview reads in step with the language the
 * visitor switched to. The static HTML already carries the right values for the
 * URL it was served from (see `seo-plugin.ts`), so this only matters after a switch.
 */
export function applySeo(strings: Dict, lang: Lang): void {
  const { seo } = strings;
  document.documentElement.lang = strings.htmlLang;
  document.title = seo.title;
  const url = `${SITE_URL}${pathForLang(lang)}`;
  setMeta('meta[name="description"]', "content", seo.description);
  setMeta('meta[property="og:title"]', "content", seo.ogTitle);
  setMeta('meta[property="og:description"]', "content", seo.ogDescription);
  setMeta('meta[property="og:locale"]', "content", seo.ogLocale);
  setMeta('meta[property="og:url"]', "content", url);
  setMeta('meta[name="twitter:title"]', "content", seo.ogTitle);
  setMeta('meta[name="twitter:description"]', "content", seo.ogDescription);
  setMeta('link[rel="canonical"]', "href", url);
}

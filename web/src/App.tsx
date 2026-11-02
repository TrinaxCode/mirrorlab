import { useCallback, useEffect, useState } from "react";

import { DemoSection } from "./components/DemoSection";
import { Download } from "./components/Download";
import { Faq } from "./components/Faq";
import { ExpressionTable } from "./components/ExpressionTable";
import { FilterGallery } from "./components/FilterBar";
import { Footer } from "./components/Footer";
import { GestureGuide } from "./components/GestureGuide";
import { Header } from "./components/Header";
import { Hero } from "./components/Hero";
import { Features } from "./components/Features";
import { Control } from "./components/Control";
import { Install } from "./components/Install";
import { Privacy } from "./components/Privacy";
import { Reference } from "./components/Reference";
import { Section } from "./components/Section";
import { ShortcutsTable } from "./components/ShortcutsTable";
import { ToastHost } from "./components/Toast";
import { STORAGE_KEYS, useLocalStorage } from "./hooks/useLocalStorage";
import { useToasts } from "./hooks/useToasts";
import { DEFAULT_FILTER_ID, FILTER_BY_ID, filterLabel, getFilter } from "./lib/filters";
import { STRINGS, coerceLang, langFromPath, nextLang, pathForLang, type Lang } from "./lib/i18n";
import { applySeo } from "./lib/seo-client";

/** Keep the address bar in step with the language, without adding history entries. */
function replacePath(lang: Lang): void {
  try {
    const target = pathForLang(lang);
    if (window.location.pathname !== target) {
      window.history.replaceState(window.history.state, "", `${target}${window.location.hash}`);
    }
  } catch {
    // A sandboxed frame may refuse history changes; the language still switches.
  }
}

export default function App() {
  const [storedLang, setStoredLang] = useLocalStorage<Lang>(STORAGE_KEYS.lang, "es", {
    parse: (value) => coerceLang(value),
  });
  // `/en/` is the English page and wins over the stored choice, so a shared link
  // always shows the language it was published in. `/` follows the stored choice.
  const [pathLang, setPathLang] = useState<Lang | null>(langFromPath);
  const lang = pathLang ?? storedLang;
  const setLang = useCallback(
    (next: Lang) => {
      setStoredLang(next);
      setPathLang(next);
      replacePath(next);
    },
    [setStoredLang],
  );
  const [filterId, setFilterId] = useLocalStorage<string>(STORAGE_KEYS.filter, DEFAULT_FILTER_ID, {
    parse: (value) => (typeof value === "string" && FILTER_BY_ID.has(value) ? value : null),
  });
  const { toasts, push, dismiss } = useToasts();

  const strings = STRINGS[lang];

  useEffect(() => {
    applySeo(strings, lang);
  }, [strings, lang]);

  const selectLang = useCallback(
    (next: Lang) => {
      setLang(next);
      push({ emoji: "🌐", title: STRINGS[next].toast.languageChanged });
    },
    [push, setLang],
  );

  const toggleLang = useCallback(() => {
    selectLang(nextLang(lang));
  }, [lang, selectLang]);

  /** Single entry point for filter changes, so every path announces itself. */
  const selectFilter = useCallback(
    (id: string) => {
      const filter = getFilter(id);
      setFilterId(filter.id);
      push({
        emoji: filter.emoji,
        title: `${STRINGS[lang].toast.filterChanged}: ${filterLabel(filter, lang)}`,
      });
    },
    [lang, push, setFilterId],
  );

  return (
    <div className="min-h-screen bg-paper text-ink">
      <a
        href="#demo"
        className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded-full focus:bg-ink focus:px-4 focus:py-2 focus:text-sm focus:text-paper"
      >
        {strings.nav.demo}
      </a>

      <Header strings={strings} lang={lang} onSelectLang={selectLang} />

      <main>
        <Hero strings={strings} />

        <Download strings={strings} />

        <Features strings={strings} />

        <Control strings={strings} />

        <DemoSection
          strings={strings}
          lang={lang}
          filterId={filterId}
          onSelectFilter={selectFilter}
          onToggleLang={toggleLang}
          notify={push}
        />

        <Section id="filters" title={strings.gallery.title} subtitle={strings.gallery.subtitle}>
          <FilterGallery strings={strings} lang={lang} activeId={filterId} onSelect={selectFilter} />
        </Section>

        <Privacy strings={strings} />

        <Install strings={strings} />

        <Faq strings={strings} />

        <Reference strings={strings}>
          <GestureGuide strings={strings} lang={lang} />
          <ExpressionTable strings={strings} lang={lang} />
          <ShortcutsTable strings={strings} />
        </Reference>
      </main>

      <Footer strings={strings} />
      <ToastHost toasts={toasts} onDismiss={dismiss} label={strings.toast.gesture} />
    </div>
  );
}

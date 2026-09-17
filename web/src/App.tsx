import { useCallback, useEffect } from "react";

import { DemoSection } from "./components/DemoSection";
import { ExpressionTable } from "./components/ExpressionTable";
import { FilterGallery } from "./components/FilterBar";
import { Footer } from "./components/Footer";
import { GestureGuide } from "./components/GestureGuide";
import { Header } from "./components/Header";
import { Hero } from "./components/Hero";
import { HowItWorks } from "./components/HowItWorks";
import { Section } from "./components/Section";
import { ShortcutsTable } from "./components/ShortcutsTable";
import { ToastHost } from "./components/Toast";
import { STORAGE_KEYS, useLocalStorage } from "./hooks/useLocalStorage";
import { useToasts } from "./hooks/useToasts";
import { DEFAULT_FILTER_ID, FILTER_BY_ID, filterLabel, getFilter } from "./lib/filters";
import { STRINGS, coerceLang, nextLang, type Lang } from "./lib/i18n";
import { SITE_NAME } from "./lib/site";

export default function App() {
  const [lang, setLang] = useLocalStorage<Lang>(STORAGE_KEYS.lang, "es", {
    parse: (value) => coerceLang(value),
  });
  const [filterId, setFilterId] = useLocalStorage<string>(STORAGE_KEYS.filter, DEFAULT_FILTER_ID, {
    parse: (value) => (typeof value === "string" && FILTER_BY_ID.has(value) ? value : null),
  });
  const { toasts, push, dismiss } = useToasts();

  const strings = STRINGS[lang];

  useEffect(() => {
    document.documentElement.lang = strings.htmlLang;
    document.title = `${SITE_NAME} — ${strings.hero.kicker}`;
  }, [strings]);

  const selectLang = useCallback(
    (next: Lang) => {
      setLang(next);
      push({ emoji: "🌐", title: STRINGS[next].toast.languageChanged });
    },
    [push, setLang],
  );

  const toggleLang = useCallback(() => {
    setLang((current) => {
      const next = nextLang(current);
      push({ emoji: "🌐", title: STRINGS[next].toast.languageChanged });
      return next;
    });
  }, [push, setLang]);

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
    <div className="min-h-screen bg-ink-950">
      <a
        href="#demo"
        className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded-lg focus:bg-white focus:px-3 focus:py-2 focus:text-sm focus:text-ink-950"
      >
        {strings.nav.demo}
      </a>

      <Header strings={strings} lang={lang} onSelectLang={selectLang} />

      <main>
        <Hero strings={strings} />

        <DemoSection
          strings={strings}
          lang={lang}
          filterId={filterId}
          onSelectFilter={selectFilter}
          onToggleLang={toggleLang}
          notify={push}
        />

        <HowItWorks strings={strings} />

        <Section id="filters" title={strings.gallery.title} subtitle={strings.gallery.subtitle}>
          <FilterGallery strings={strings} lang={lang} activeId={filterId} onSelect={selectFilter} />
        </Section>

        <GestureGuide strings={strings} lang={lang} />
        <ExpressionTable strings={strings} lang={lang} />
        <ShortcutsTable strings={strings} />
      </main>

      <Footer strings={strings} />
      <ToastHost toasts={toasts} onDismiss={dismiss} label={strings.toast.gesture} />
    </div>
  );
}

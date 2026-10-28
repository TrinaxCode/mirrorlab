import type { Dict, Lang } from "../lib/i18n";
import { REPO_URL, SITE_NAME } from "../lib/site";

export interface HeaderProps {
  strings: Dict;
  lang: Lang;
  onSelectLang: (lang: Lang) => void;
}

const NAV_ITEMS = [
  { href: "#demo", key: "demo" },
  { href: "#features", key: "features" },
  { href: "#control", key: "control" },
  { href: "#install", key: "install" },
] as const;

/** A lens seen from the front: housing, ring, and the tally light. */
export function LensMark({ className = "h-7 w-7" }: { className?: string }) {
  return (
    <svg viewBox="0 0 32 32" className={className} aria-hidden="true">
      <rect width="32" height="32" rx="9" fill="var(--ink)" />
      <circle cx="16" cy="16" r="9" fill="none" stroke="var(--paper)" strokeWidth="2.4" />
      <circle cx="16" cy="16" r="3.4" fill="var(--paper)" />
      <circle cx="25" cy="7" r="2.6" fill="var(--tally)" />
    </svg>
  );
}

export function Header({ strings, lang, onSelectLang }: HeaderProps) {
  return (
    <header className="sticky top-0 z-40 border-b border-line bg-paper/90 backdrop-blur-md">
      <div className="mx-auto flex max-w-6xl items-center gap-4 px-4 py-2.5 sm:px-6">
        <a href="#top" className="flex items-center gap-2.5 rounded-lg py-1 pr-1">
          <LensMark />
          <span className="heading text-xl">{SITE_NAME}</span>
        </a>

        <nav aria-label={SITE_NAME} className="ml-4 hidden items-center gap-1 md:flex">
          {NAV_ITEMS.map((item) => (
            <a
              key={item.href}
              href={item.href}
              className="rounded-full px-3.5 py-2 text-sm font-medium text-ink-soft transition-colors hover:bg-paper-deep hover:text-ink"
            >
              {strings.nav[item.key]}
            </a>
          ))}
        </nav>

        <div className="ml-auto flex items-center gap-2">
          <div role="group" aria-label={strings.switchLabel} className="flex items-center rounded-full border border-line p-0.5">
            {(["es", "en"] as const).map((code) => (
              <button
                key={code}
                type="button"
                onClick={() => onSelectLang(code)}
                aria-pressed={lang === code}
                className={`min-h-9 min-w-10 rounded-full px-3 text-sm font-semibold transition-colors ${
                  lang === code ? "bg-ink text-paper" : "text-ink-soft hover:text-ink"
                }`}
              >
                {code.toUpperCase()}
              </button>
            ))}
          </div>

          <a
            href={REPO_URL}
            target="_blank"
            rel="noreferrer noopener"
            className="btn btn-quiet btn-sm hidden sm:inline-flex"
          >
            <svg viewBox="0 0 16 16" className="h-4 w-4" fill="currentColor" aria-hidden="true">
              <path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.07-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82a7.4 7.4 0 0 1 2-.27c.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.01 8.01 0 0 0 16 8c0-4.42-3.58-8-8-8Z" />
            </svg>
            {strings.nav.repo}
          </a>
        </div>
      </div>
    </header>
  );
}

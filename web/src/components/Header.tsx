import type { Dict, Lang } from "../lib/i18n";
import { REPO_URL, SITE_NAME } from "../lib/site";

export interface HeaderProps {
  strings: Dict;
  lang: Lang;
  onSelectLang: (lang: Lang) => void;
}

const NAV_ITEMS = [
  { href: "#demo", key: "demo" },
  { href: "#filters", key: "filters" },
  { href: "#gestures", key: "gestures" },
  { href: "#expressions", key: "expressions" },
  { href: "#shortcuts", key: "shortcuts" },
] as const;

export function Header({ strings, lang, onSelectLang }: HeaderProps) {
  return (
    <header className="sticky top-0 z-40 border-b border-white/5 bg-ink-950/85 backdrop-blur-md">
      <div className="mx-auto flex max-w-6xl items-center gap-3 px-4 py-3 sm:px-6">
        <a href="#top" className="flex items-center gap-2.5 rounded-lg py-1 pr-2">
          <span className="grid h-8 w-8 place-items-center rounded-xl accent-gradient">
            <svg viewBox="0 0 24 24" className="h-4.5 w-4.5" aria-hidden="true">
              <rect x="2.5" y="6" width="19" height="12.5" rx="3.5" fill="#05070d" opacity="0.85" />
              <circle cx="12" cy="12.25" r="3.4" fill="#5eead4" />
              <circle cx="12" cy="12.25" r="1.4" fill="#05070d" />
            </svg>
          </span>
          <span className="text-sm font-semibold tracking-tight text-white sm:text-base">{SITE_NAME}</span>
        </a>

        <nav aria-label={SITE_NAME} className="ml-2 hidden items-center gap-0.5 lg:flex">
          {NAV_ITEMS.map((item) => (
            <a
              key={item.href}
              href={item.href}
              className="rounded-lg px-3 py-2 text-sm text-slate-400 transition-colors hover:bg-white/5 hover:text-white"
            >
              {strings.nav[item.key]}
            </a>
          ))}
        </nav>

        <div className="ml-auto flex items-center gap-2">
          <div
            role="group"
            aria-label={strings.switchLabel}
            className="flex items-center rounded-xl border border-white/10 bg-white/[0.04] p-0.5"
          >
            {(["es", "en"] as const).map((code) => (
              <button
                key={code}
                type="button"
                onClick={() => onSelectLang(code)}
                aria-pressed={lang === code}
                className={`rounded-[0.6rem] px-2.5 py-1 text-xs font-semibold uppercase transition-colors ${
                  lang === code ? "accent-gradient text-ink-950" : "text-slate-400 hover:text-white"
                }`}
              >
                {code}
              </button>
            ))}
          </div>

          <a
            href={REPO_URL}
            target="_blank"
            rel="noreferrer noopener"
            className="hidden items-center gap-2 rounded-xl border border-white/10 bg-white/[0.04] px-3 py-2 text-sm font-medium text-slate-300 transition-colors hover:border-white/20 hover:text-white sm:flex"
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

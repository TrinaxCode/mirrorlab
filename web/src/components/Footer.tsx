import type { Dict } from "../lib/i18n";
import { REPO_URL, SITE_NAME } from "../lib/site";

export interface FooterProps {
  strings: Dict;
}

export function Footer({ strings }: FooterProps) {
  return (
    <footer className="border-t border-white/5 px-4 py-12 sm:px-6">
      <div className="mx-auto flex max-w-6xl flex-col gap-6 sm:flex-row sm:items-start sm:justify-between">
        <div className="max-w-md">
          <div className="flex items-center gap-2">
            <span className="grid h-8 w-8 place-items-center rounded-xl accent-gradient">
              <svg viewBox="0 0 24 24" className="h-4 w-4" aria-hidden="true">
                <rect x="2.5" y="6" width="19" height="12.5" rx="3.5" fill="#05070d" opacity="0.85" />
                <circle cx="12" cy="12.25" r="3.4" fill="#5eead4" />
                <circle cx="12" cy="12.25" r="1.4" fill="#05070d" />
              </svg>
            </span>
            <span className="font-semibold tracking-tight text-white">{SITE_NAME}</span>
          </div>
          <p className="mt-3 text-sm leading-relaxed text-slate-400">{strings.footer.tagline}</p>
          <p className="mt-3 text-xs text-slate-500">{strings.footer.built}</p>
        </div>

        <div className="flex flex-col gap-3 text-sm">
          <a
            href={REPO_URL}
            target="_blank"
            rel="noreferrer noopener"
            className="inline-flex items-center gap-2 font-medium text-brand-teal transition-opacity hover:opacity-80"
          >
            {strings.footer.repo}
            <span aria-hidden="true">↗</span>
          </a>
          <span className="text-slate-500">{strings.footer.license}</span>
          <span className="text-slate-500">{strings.footer.privacy}</span>
        </div>
      </div>
    </footer>
  );
}

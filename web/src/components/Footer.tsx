import type { Dict } from "../lib/i18n";
import { REPO_URL, SITE_NAME } from "../lib/site";
import { LensMark } from "./Header";

export interface FooterProps {
  strings: Dict;
}

export function Footer({ strings }: FooterProps) {
  return (
    <footer className="border-t border-line px-4 py-14 sm:px-6">
      <div className="mx-auto flex max-w-6xl flex-col gap-8 sm:flex-row sm:items-end sm:justify-between">
        <div className="max-w-md">
          <div className="flex items-center gap-2.5">
            <LensMark className="h-8 w-8" />
            <span className="heading text-2xl">{SITE_NAME}</span>
          </div>
          <p className="mt-4 text-base leading-relaxed text-ink-soft">{strings.footer.tagline}</p>
          <p className="mt-3 text-sm text-ink-soft">{strings.footer.built}</p>
        </div>

        <div className="flex flex-col gap-2 text-sm text-ink-soft sm:items-end">
          <a
            href={REPO_URL}
            target="_blank"
            rel="noreferrer noopener"
            className="font-semibold text-ink underline underline-offset-4 hover:text-tally"
          >
            {strings.footer.repo}
          </a>
          <span>{strings.footer.license}</span>
          <span>{strings.footer.privacy}</span>
        </div>
      </div>
    </footer>
  );
}

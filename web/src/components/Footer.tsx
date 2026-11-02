import { useAnalyticsConsent } from "../hooks/useAnalyticsConsent";
import type { Dict } from "../lib/i18n";
import { AUTHOR_NAME, AUTHOR_URL, REPO_URL, SITE_NAME } from "../lib/site";
import { LensMark } from "./Header";

export interface FooterProps {
  strings: Dict;
}

export function Footer({ strings }: FooterProps) {
  const { footer } = strings;
  const stats = useAnalyticsConsent();

  return (
    <footer className="border-t border-line px-4 py-14 sm:px-6">
      <div className="mx-auto flex max-w-6xl flex-col gap-10 sm:flex-row sm:items-start sm:justify-between">
        <div className="max-w-md">
          <div className="flex items-center gap-2.5">
            <LensMark className="h-8 w-8" />
            <span className="heading text-2xl">{SITE_NAME}</span>
          </div>
          <p className="mt-4 text-base leading-relaxed text-ink-soft">{footer.tagline}</p>
          <p className="mt-3 text-sm text-ink-soft">
            {footer.createdBy}{" "}
            <a
              href={AUTHOR_URL}
              target="_blank"
              rel="author noreferrer noopener"
              className="font-semibold text-ink underline underline-offset-4 hover:text-tally"
            >
              {AUTHOR_NAME}
            </a>
            . {footer.built}
          </p>
        </div>

        <div className="flex max-w-xs flex-col gap-2 text-sm text-ink-soft sm:items-end sm:text-right">
          <a
            href={REPO_URL}
            target="_blank"
            rel="noreferrer noopener"
            className="font-semibold text-ink underline underline-offset-4 hover:text-tally"
          >
            {footer.repo}
          </a>
          <span>{footer.license}</span>
          <span>{footer.privacy}</span>

          <div className="mt-3 sm:text-right">
            <button
              type="button"
              role="switch"
              aria-checked={stats.enabled}
              disabled={stats.refused}
              onClick={stats.toggle}
              className="inline-flex min-h-11 items-center gap-3 rounded-full border border-line px-4 text-sm font-semibold text-ink transition-colors hover:border-ink disabled:cursor-not-allowed disabled:opacity-50"
            >
              <span
                aria-hidden="true"
                className={`h-2.5 w-2.5 rounded-full ${stats.enabled ? "bg-tally" : "bg-ink-soft"}`}
              />
              {footer.stats.label}: {stats.enabled ? footer.stats.on : footer.stats.off}
            </button>
            <p className="mt-2 text-xs leading-relaxed">
              {stats.refused ? footer.stats.refused : stats.failed ? footer.stats.failed : footer.stats.hint}
            </p>
          </div>
        </div>
      </div>
    </footer>
  );
}

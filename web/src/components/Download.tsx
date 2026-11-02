import { useMemo } from "react";

import { trackEvent } from "../lib/analytics";
import type { Dict } from "../lib/i18n";
import { RELEASES_URL } from "../lib/site";
import { Section } from "./Section";

export interface DownloadProps {
  strings: Dict;
}

type PlatformId = "windows" | "macos" | "linux";

/** The visitor's operating system, so the first card is probably the right one. */
function detectPlatform(): PlatformId {
  if (typeof navigator === "undefined") return "linux";
  const hint = `${navigator.platform} ${navigator.userAgent}`.toLowerCase();
  if (hint.includes("win")) return "windows";
  if (hint.includes("mac") && !hint.includes("iphone") && !hint.includes("ipad")) return "macos";
  return "linux";
}

/** Neutral glyphs (windows, laptop, terminal) rather than vendor logos. */
function PlatformIcon({ id }: { id: string }) {
  const common = {
    viewBox: "0 0 24 24",
    className: "h-7 w-7",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: 1.8,
    strokeLinecap: "round",
    strokeLinejoin: "round",
    "aria-hidden": true,
  } as const;
  if (id === "windows") {
    return (
      <svg {...common}>
        <rect x="3" y="3" width="8" height="8" rx="1" />
        <rect x="13" y="3" width="8" height="8" rx="1" />
        <rect x="3" y="13" width="8" height="8" rx="1" />
        <rect x="13" y="13" width="8" height="8" rx="1" />
      </svg>
    );
  }
  if (id === "macos") {
    return (
      <svg {...common}>
        <rect x="4" y="5" width="16" height="11" rx="2" />
        <path d="M2 19h20" />
      </svg>
    );
  }
  return (
    <svg {...common}>
      <rect x="3" y="4" width="18" height="16" rx="2" />
      <path d="m7 9 3 3-3 3M13 15h4" />
    </svg>
  );
}

export function Download({ strings }: DownloadProps) {
  const { download } = strings;
  const detected = useMemo(() => detectPlatform(), []);
  const ordered = useMemo(
    () => [...download.platforms].sort((a, b) => Number(b.id === detected) - Number(a.id === detected)),
    [download.platforms, detected],
  );

  return (
    <Section id="download" title={download.title} subtitle={download.subtitle}>
      <ul className="grid gap-4 md:grid-cols-3">
        {ordered.map((platform) => {
          const recommended = platform.id === detected;
          return (
            <li
              key={platform.id}
              className={`flex flex-col rounded-2xl border p-6 ${
                recommended ? "border-ink bg-paper-deep" : "border-line"
              }`}
            >
              {recommended ? (
                <span className="mb-3 w-fit rounded-full bg-tally px-2.5 py-1 text-xs font-semibold whitespace-nowrap text-on-tally">
                  {download.recommended}
                </span>
              ) : null}
              <div className="flex items-center gap-3">
                <PlatformIcon id={platform.id} />
                <h3 className="heading text-2xl">{platform.name}</h3>
              </div>
              <p className="mt-4 text-base font-medium">{platform.file}</p>
              <p className="mt-1 text-sm text-ink-soft">{platform.requirements}</p>
              <p className="mt-4 flex-1 text-sm leading-relaxed text-ink-soft">{platform.note}</p>
              <a
                href={RELEASES_URL}
                target="_blank"
                rel="noreferrer noopener"
                onClick={() => trackEvent("download_click", { platform: platform.id })}
                className={`btn mt-6 ${recommended ? "btn-primary" : "btn-quiet"}`}
              >
                {download.cta.replace("{os}", platform.name)}
              </a>
            </li>
          );
        })}
      </ul>

      <ol className="mt-12 grid gap-8 md:grid-cols-3">
        {download.steps.map((step, index) => (
          <li key={step.title} className="grid grid-cols-[2rem_minmax(0,1fr)] gap-x-4">
            <span
              aria-hidden="true"
              className="grid h-8 w-8 place-items-center rounded-full border border-ink text-sm font-semibold"
            >
              {index + 1}
            </span>
            <div>
              <h3 className="pt-1 text-lg font-semibold leading-tight">{step.title}</h3>
              <p className="mt-1.5 text-base leading-relaxed text-ink-soft">{step.body}</p>
            </div>
          </li>
        ))}
      </ol>

      <figure className="mt-12 max-w-3xl">
        <img
          src={download.screenshot.src}
          alt={download.screenshot.alt}
          width={1080}
          height={655}
          loading="lazy"
          decoding="async"
          className="h-auto w-full rounded-2xl border border-line"
        />
        <figcaption className="mt-3 text-sm text-ink-soft">{download.screenshot.caption}</figcaption>
      </figure>

      <p className="mt-10 text-sm text-ink-soft">
        <a
          href={RELEASES_URL}
          target="_blank"
          rel="noreferrer noopener"
          className="font-semibold text-ink underline underline-offset-4 hover:text-tally"
        >
          {download.allReleases}
        </a>
        {" · "}
        {download.license}
      </p>
    </Section>
  );
}

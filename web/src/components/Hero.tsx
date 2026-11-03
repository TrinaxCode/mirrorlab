import { useState } from "react";

import type { Dict } from "../lib/i18n";
import { CodeBlock } from "./CodeBlock";
import { Monitor, type MonitorMode } from "./Monitor";

export interface HeroProps {
  strings: Dict;
}

type Pinned = Exclude<MonitorMode, "auto">;

const CHIPS: ReadonlyArray<{ mode: Pinned; emoji: string; key: "palm" | "heart" | "thumb" }> = [
  { mode: "covered", emoji: "🖐️", key: "palm" },
  { mode: "heart", emoji: "🤟", key: "heart" },
  { mode: "thumb", emoji: "👍", key: "thumb" },
];

/**
 * The stage: the headline on the left, a call tile on the right that the visitor can
 * drive with the same three gestures the product reacts to.
 */
export function Hero({ strings }: HeroProps) {
  const { hero } = strings;
  const [pinned, setPinned] = useState<Pinned | null>(null);

  return (
    <section id="top" className="tone-stage relative isolate overflow-hidden px-4 pb-20 pt-12 sm:px-6 sm:pb-28 sm:pt-20">
      <div aria-hidden="true" className="stage-grid absolute inset-0 -z-10" />
      <div className="mx-auto grid max-w-6xl items-center gap-14 lg:grid-cols-[minmax(0,5fr)_minmax(0,6fr)] lg:gap-16">
        <div>
          <p className="flex items-center gap-2.5 text-base font-medium text-ink-soft">
            <span aria-hidden="true" className="h-2.5 w-2.5 rounded-full bg-tally" />
            {hero.kicker}
          </p>
          <h1 className="display mt-5 text-[3.5rem] sm:text-7xl lg:text-[5.75rem]">{hero.title}</h1>
          <p className="mt-6 max-w-[44ch] text-lg leading-relaxed text-ink-soft">{hero.pitch}</p>

          <div className="mt-9 flex flex-wrap items-center gap-3">
            <a href="#download" className="btn btn-primary">
              {hero.ctaPrimary}
            </a>
            <a href="#demo" className="btn btn-screen">
              {hero.ctaSecondary}
            </a>
          </div>
          <p className="mt-4 text-sm text-ink-soft">{hero.platforms}</p>

          <div className="mt-10 max-w-md">
            <p className="mb-2 text-sm text-ink-soft">{hero.commandLabel}</p>
            <CodeBlock code="mirrorlab cam --profile meeting" copyLabel={hero.copy} copiedLabel={hero.copied} />
          </div>
        </div>

        <div>
          <div className="brackets">
            <Monitor strings={strings} mode={pinned ?? "auto"} />
          </div>
          <p className="mt-6 max-w-[52ch] text-sm text-ink-soft">{hero.caption}</p>
          <div className="mt-6" role="group" aria-label={hero.try.label}>
            <p className="text-sm text-ink-soft">{hero.try.label}</p>
            <div className="mt-3 flex flex-wrap gap-2.5">
              {CHIPS.map((chip) => (
                <button
                  key={chip.mode}
                  type="button"
                  className="chip"
                  aria-pressed={pinned === chip.mode}
                  onClick={() => setPinned((current) => (current === chip.mode ? null : chip.mode))}
                >
                  <span aria-hidden="true">{chip.emoji}</span>
                  {hero.try[chip.key]}
                </button>
              ))}
            </div>
            <p className="mt-3 min-h-5 text-sm text-ink-soft" aria-live="polite">
              {pinned ? hero.try.hint : ""}
            </p>
          </div>
        </div>
      </div>
    </section>
  );
}

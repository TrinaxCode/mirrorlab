import type { Dict } from "../lib/i18n";
import { CodeBlock } from "./CodeBlock";
import { Monitor } from "./Monitor";

export interface HeroProps {
  strings: Dict;
}

export function Hero({ strings }: HeroProps) {
  const { hero } = strings;

  return (
    <section id="top" className="px-4 pb-16 pt-10 sm:px-6 sm:pb-24 sm:pt-16">
      <div className="mx-auto grid max-w-6xl items-center gap-12 lg:grid-cols-[minmax(0,5fr)_minmax(0,6fr)] lg:gap-14">
        <div>
          <p className="text-base font-medium text-ink-soft">{hero.kicker}</p>
          <h1 className="display mt-4 text-[3.25rem] sm:text-7xl lg:text-[5.5rem]">{hero.title}</h1>
          <p className="mt-6 max-w-[44ch] text-lg leading-relaxed text-ink-soft">{hero.pitch}</p>

          <div className="mt-8 flex flex-wrap items-center gap-3">
            <a href="#demo" className="btn btn-primary">
              {hero.ctaPrimary}
            </a>
            <a href="#install" className="btn btn-quiet">
              {hero.ctaSecondary}
            </a>
          </div>

          <div className="mt-10 max-w-md">
            <p className="mb-2 text-sm text-ink-soft">{hero.commandLabel}</p>
            <CodeBlock code="mirrorlab cam --profile meeting" copyLabel={hero.copy} copiedLabel={hero.copied} />
          </div>
        </div>

        <Monitor strings={strings} />
      </div>
    </section>
  );
}

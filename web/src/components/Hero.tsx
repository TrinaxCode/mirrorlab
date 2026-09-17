import type { Dict } from "../lib/i18n";
import { FILTERS } from "../lib/filters";
import { GESTURES, DYNAMIC_GESTURES } from "../lib/gestures";
import { SITE_NAME } from "../lib/site";

export interface HeroProps {
  strings: Dict;
}

export function Hero({ strings }: HeroProps) {
  // The headline numbers are read from the registries so they can never drift
  // away from what the demo actually ships.
  const stats = [
    { value: "52", label: strings.hero.stats[0]?.label ?? "" },
    { value: String(GESTURES.length + DYNAMIC_GESTURES.length), label: strings.hero.stats[1]?.label ?? "" },
    { value: String(FILTERS.length), label: strings.hero.stats[2]?.label ?? "" },
    { value: "0", label: strings.hero.stats[3]?.label ?? "" },
  ];

  return (
    <section id="top" className="relative overflow-hidden px-4 pb-14 pt-14 sm:px-6 sm:pb-20 sm:pt-20">
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-0 grid-backdrop opacity-60 [mask-image:radial-gradient(70%_60%_at_50%_0%,black,transparent)]"
      />
      <div
        aria-hidden="true"
        className="pointer-events-none absolute -top-40 left-1/2 h-96 w-[46rem] -translate-x-1/2 rounded-full opacity-25 blur-3xl"
        style={{ background: "radial-gradient(circle at 30% 50%, #5eead4, transparent 60%), radial-gradient(circle at 70% 50%, #a78bfa, transparent 60%)" }}
      />

      <div className="relative mx-auto max-w-6xl">
        <span className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/[0.04] px-3 py-1.5 text-xs text-slate-300">
          <span className="h-1.5 w-1.5 rounded-full bg-brand-teal" />
          {strings.hero.badge}
        </span>

        <h1 className="mt-6 text-5xl font-semibold tracking-tight text-white sm:text-6xl lg:text-7xl">
          <span className="text-gradient">{SITE_NAME}</span>
        </h1>
        <p className="mt-3 text-lg font-medium text-slate-300 sm:text-xl">{strings.hero.kicker}</p>
        <p className="mt-5 max-w-2xl text-sm leading-relaxed text-slate-400 sm:text-base">{strings.hero.pitch}</p>

        <div className="mt-8 flex flex-wrap items-center gap-3">
          <a
            href="#demo"
            className="inline-flex items-center gap-2 rounded-xl accent-gradient px-5 py-3 text-sm font-semibold text-ink-950 shadow-lg shadow-brand-violet/20 transition-transform hover:-translate-y-0.5"
          >
            {strings.hero.ctaPrimary}
            <span aria-hidden="true">→</span>
          </a>
          <a
            href="#how"
            className="inline-flex items-center gap-2 rounded-xl border border-white/10 bg-white/[0.04] px-5 py-3 text-sm font-semibold text-slate-200 transition-colors hover:border-white/20 hover:text-white"
          >
            {strings.hero.ctaSecondary}
          </a>
        </div>

        <dl className="mt-12 grid grid-cols-2 gap-4 sm:grid-cols-4">
          {stats.map((stat) => (
            <div key={stat.label} className="card px-4 py-4">
              <dt className="text-xs uppercase tracking-wider text-slate-500">{stat.label}</dt>
              <dd className="mt-1 text-2xl font-semibold text-gradient sm:text-3xl">{stat.value}</dd>
            </div>
          ))}
        </dl>
      </div>
    </section>
  );
}

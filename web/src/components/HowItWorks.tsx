import type { Dict } from "../lib/i18n";
import { Section } from "./Section";

export interface HowItWorksProps {
  strings: Dict;
}

export function HowItWorks({ strings }: HowItWorksProps) {
  return (
    <Section id="how" title={strings.how.title} subtitle={strings.how.subtitle}>
      <ol className="grid gap-4 md:grid-cols-3">
        {strings.how.steps.map((step, index) => (
          <li key={step.title} className="card relative overflow-hidden p-5">
            <span
              aria-hidden="true"
              className="absolute right-4 top-3 text-4xl font-semibold text-white/5"
            >
              {index + 1}
            </span>
            <span className="grid h-11 w-11 place-items-center rounded-xl border border-white/10 bg-white/[0.04] text-xl">
              {step.emoji}
            </span>
            <h3 className="mt-4 text-base font-semibold text-white">{step.title}</h3>
            <p className="mt-2 text-sm leading-relaxed text-slate-400">{step.body}</p>
          </li>
        ))}
      </ol>
    </Section>
  );
}

import type { Dict } from "../lib/i18n";
import { Section } from "./Section";

export interface FeaturesProps {
  strings: Dict;
}

/** A ruled list rather than a card grid: these are five parallel entries, read top to bottom. */
export function Features({ strings }: FeaturesProps) {
  const { features } = strings;
  return (
    <Section id="features" title={features.title} subtitle={features.subtitle}>
      <dl className="border-t border-line">
        {features.items.map((item) => (
          <div
            key={item.name}
            className="grid gap-x-8 gap-y-2 border-b border-line py-7 sm:grid-cols-[9rem_minmax(0,1fr)]"
          >
            <dt className="heading text-2xl">{item.name}</dt>
            <dd className="m-0">
              <p className="max-w-[52ch] text-base leading-relaxed">{item.body}</p>
              <p className="mt-2 text-sm text-ink-soft">{item.readout}</p>
            </dd>
          </div>
        ))}
      </dl>
    </Section>
  );
}

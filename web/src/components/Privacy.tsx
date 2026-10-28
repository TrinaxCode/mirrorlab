import type { Dict } from "../lib/i18n";
import { Section } from "./Section";

export interface PrivacyProps {
  strings: Dict;
}

export function Privacy({ strings }: PrivacyProps) {
  const { privacy } = strings;
  return (
    <Section id="privacy" title={privacy.title} subtitle={privacy.subtitle}>
      <ul className="grid gap-x-10 gap-y-8 sm:grid-cols-2">
        {privacy.facts.map((fact) => (
          <li key={fact.title} className="border-t border-ink pt-4">
            <h3 className="text-lg font-semibold leading-snug">{fact.title}</h3>
            <p className="mt-2 text-base leading-relaxed text-ink-soft">{fact.body}</p>
          </li>
        ))}
      </ul>
    </Section>
  );
}

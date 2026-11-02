import type { Dict } from "../lib/i18n";
import { Section } from "./Section";

export interface FaqProps {
  strings: Dict;
}

/** Native <details> so it works without JavaScript and is keyboard-accessible for free. */
export function Faq({ strings }: FaqProps) {
  const { faq } = strings;
  return (
    <Section id="faq" title={faq.title} subtitle={faq.subtitle}>
      <div className="divide-y divide-line border-y border-line">
        {faq.items.map((item) => (
          <details key={item.q} className="group py-5">
            <summary className="flex cursor-pointer list-none items-center justify-between gap-6 text-lg font-semibold [&::-webkit-details-marker]:hidden">
              {item.q}
              <span
                aria-hidden="true"
                className="grid h-7 w-7 shrink-0 place-items-center rounded-full border border-line text-base transition-transform group-open:rotate-45"
              >
                +
              </span>
            </summary>
            <p className="mt-3 max-w-[62ch] text-base leading-relaxed text-ink-soft">{item.a}</p>
          </details>
        ))}
      </div>
    </Section>
  );
}

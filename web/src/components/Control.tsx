import type { Dict } from "../lib/i18n";
import { Section } from "./Section";

export interface ControlProps {
  strings: Dict;
}

/** Gesture → action, with the hold time drawn to scale so "1.6 s" is something you can see. */
export function Control({ strings }: ControlProps) {
  const { control } = strings;
  const longest = Math.max(...control.rows.map((row) => row.hold));

  return (
    <Section id="control" title={control.title} subtitle={control.subtitle}>
      <ul className="border-t border-line">
        {control.rows.map((row) => {
          const share = (row.hold / longest) * 100;
          return (
            <li
              key={row.gesture}
              className="grid grid-cols-[3rem_minmax(0,1fr)] items-center gap-x-4 gap-y-3 border-b border-line py-5 sm:grid-cols-[3rem_minmax(0,1fr)_minmax(0,14rem)]"
            >
              <span aria-hidden="true" className="text-4xl leading-none">
                {row.emoji}
              </span>
              <div>
                <p className="text-lg font-semibold leading-tight">{row.gesture}</p>
                <p className="mt-0.5 text-base text-ink-soft">{row.action}</p>
              </div>
              <div
                className="col-span-2 sm:col-span-1"
                role="img"
                aria-label={`${control.holdLabel}: ${row.hold.toLocaleString(strings.htmlLang)} ${control.holdUnit}`}
              >
                <div className="h-2 rounded-full bg-paper-deep">
                  <div className="h-full rounded-full bg-tally" style={{ width: `${share}%` }} />
                </div>
                <p className="mt-1.5 text-sm tabular-nums text-ink-soft">
                  {row.hold.toLocaleString(strings.htmlLang, { minimumFractionDigits: 1 })} {control.holdUnit}
                </p>
              </div>
            </li>
          );
        })}
      </ul>
      <p className="mt-6 max-w-[56ch] text-base leading-relaxed text-ink-soft">{control.alt}</p>
    </Section>
  );
}

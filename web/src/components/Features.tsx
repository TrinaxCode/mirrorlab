import type { ReactNode } from "react";

import type { Dict } from "../lib/i18n";
import { BackgroundArt, FramingArt, LightArt, ReactionsArt, ShutterArt } from "./SceneArt";
import { Section } from "./Section";

export interface FeaturesProps {
  strings: Dict;
}

/** The art for each entry, in the order the copy lists them. */
const ART: ReadonlyArray<{ art: ReactNode; span: string }> = [
  { art: <BackgroundArt />, span: "lg:col-span-3" },
  { art: <FramingArt />, span: "lg:col-span-3" },
  { art: <LightArt />, span: "lg:col-span-2" },
  { art: <ShutterArt />, span: "lg:col-span-2" },
  { art: <ReactionsArt />, span: "lg:col-span-2" },
];

/** A bento of five screens: each adjustment is shown on the picture before it is described. */
export function Features({ strings }: FeaturesProps) {
  const { features } = strings;
  return (
    <Section id="features" title={features.title} subtitle={features.subtitle} wide className="tone-stage">
      <ul className="grid gap-5 lg:grid-cols-6">
        {features.items.map((item, index) => {
          const slot = ART[index];
          return (
            <li
              key={item.name}
              className={`flex flex-col overflow-hidden rounded-3xl border border-line bg-paper-deep ${slot?.span ?? "lg:col-span-2"}`}
            >
              <div className="aspect-[16/9] overflow-hidden bg-screen">{slot?.art}</div>
              <div className="flex flex-1 flex-col p-6">
                <h3 className="heading text-3xl">{item.name}</h3>
                <p className="mt-3 max-w-[52ch] text-base leading-relaxed text-ink">{item.body}</p>
                <p className="mt-auto pt-4 text-sm text-ink-soft">{item.readout}</p>
              </div>
            </li>
          );
        })}
      </ul>
    </Section>
  );
}

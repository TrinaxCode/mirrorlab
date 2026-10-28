import type { ReactNode } from "react";

import type { Dict } from "../lib/i18n";
import { Section } from "./Section";

export interface ReferenceProps {
  strings: Dict;
  children: ReactNode;
}

/** Gestures, expressions and shortcuts of the browser demo, collapsed so the page stays short. */
export function Reference({ strings, children }: ReferenceProps) {
  return (
    <Section id="reference" title={strings.reference.title} subtitle={strings.reference.subtitle}>
      <div className="border-t border-line">{children}</div>
    </Section>
  );
}

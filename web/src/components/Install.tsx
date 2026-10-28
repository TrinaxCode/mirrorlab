import { useId, useState } from "react";

import type { Dict } from "../lib/i18n";
import { REPO_URL } from "../lib/site";
import { CodeBlock } from "./CodeBlock";
import { Section } from "./Section";

export interface InstallProps {
  strings: Dict;
}

/** Guess the visitor's OS so the first tab is probably the right one. */
function guessPlatform(): string {
  if (typeof navigator === "undefined") return "linux";
  const hint = `${navigator.platform} ${navigator.userAgent}`.toLowerCase();
  if (hint.includes("win")) return "windows";
  if (hint.includes("mac")) return "macos";
  return "linux";
}

export function Install({ strings }: InstallProps) {
  const { install } = strings;
  const [active, setActive] = useState(guessPlatform);
  const base = useId();
  const platform = install.platforms.find((item) => item.id === active) ?? install.platforms[0];

  return (
    <Section id="install" title={install.title} subtitle={install.subtitle}>
      <div role="tablist" aria-label={install.tabsLabel} className="inline-flex rounded-full border border-line p-0.5">
        {install.platforms.map((item) => (
          <button
            key={item.id}
            id={`${base}-tab-${item.id}`}
            role="tab"
            type="button"
            aria-selected={item.id === active}
            aria-controls={`${base}-panel`}
            tabIndex={item.id === active ? 0 : -1}
            onClick={() => setActive(item.id)}
            onKeyDown={(event) => {
              if (event.key !== "ArrowRight" && event.key !== "ArrowLeft") return;
              const index = install.platforms.findIndex((entry) => entry.id === active);
              const step = event.key === "ArrowRight" ? 1 : -1;
              const next = install.platforms[(index + step + install.platforms.length) % install.platforms.length];
              if (next) {
                setActive(next.id);
                document.getElementById(`${base}-tab-${next.id}`)?.focus();
              }
            }}
            className={`min-h-10 rounded-full px-5 text-sm font-semibold transition-colors ${
              item.id === active ? "bg-ink text-paper" : "text-ink-soft hover:text-ink"
            }`}
          >
            {item.name}
          </button>
        ))}
      </div>

      {platform ? (
        <div id={`${base}-panel`} role="tabpanel" aria-labelledby={`${base}-tab-${platform.id}`} className="mt-8">
          <ol className="flex flex-col gap-8">
            {platform.steps.map((step, index) => (
              <li key={step.title} className="grid grid-cols-[2rem_minmax(0,1fr)] gap-x-4">
                <span
                  aria-hidden="true"
                  className="grid h-8 w-8 place-items-center rounded-full border border-ink text-sm font-semibold"
                >
                  {index + 1}
                </span>
                <div className="min-w-0">
                  <h3 className="pt-1 text-lg font-semibold leading-tight">{step.title}</h3>
                  {"body" in step && step.body ? (
                    <p className="mt-1.5 max-w-[56ch] text-base leading-relaxed text-ink-soft">{step.body}</p>
                  ) : null}
                  {"code" in step && step.code ? (
                    <CodeBlock
                      code={step.code}
                      copyLabel={install.copy}
                      copiedLabel={install.copied}
                      className="mt-3"
                    />
                  ) : null}
                </div>
              </li>
            ))}
          </ol>
        </div>
      ) : null}

      <p className="mt-10 text-sm text-ink-soft">
        {install.notOnPypi}{" "}
        <a
          href={`${REPO_URL}/blob/main/docs/STUDIO.md`}
          target="_blank"
          rel="noreferrer noopener"
          className="font-semibold text-ink underline underline-offset-4 hover:text-tally"
        >
          {install.docs}
        </a>
      </p>
    </Section>
  );
}

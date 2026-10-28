import type { ReactNode } from "react";

export interface SectionProps {
  id: string;
  title: string;
  subtitle?: string;
  children: ReactNode;
  className?: string;
  /** Stack the heading above full-width content (the demo needs the room). */
  wide?: boolean;
}

/**
 * Shared section shell. Headings sit in a left column and stay put while the
 * content scrolls past on the right; `wide` stacks them instead.
 */
export function Section({ id, title, subtitle, children, className = "", wide = false }: SectionProps) {
  return (
    <section id={id} className={`scroll-mt-16 border-t border-line px-4 py-16 sm:px-6 sm:py-24 ${className}`}>
      <div
        className={`mx-auto max-w-6xl ${wide ? "" : "lg:grid lg:grid-cols-[minmax(0,4fr)_minmax(0,8fr)] lg:gap-x-14"}`}
      >
        <header className={wide ? "mb-10 max-w-3xl" : "mb-10 lg:mb-0"}>
          <div className={wide ? "" : "lg:sticky lg:top-24"}>
            <h2 className="heading text-4xl sm:text-5xl">{title}</h2>
            {subtitle ? <p className="mt-4 max-w-[46ch] text-base leading-relaxed text-ink-soft">{subtitle}</p> : null}
          </div>
        </header>
        <div>{children}</div>
      </div>
    </section>
  );
}

export interface TableProps {
  columns: string[];
  children: ReactNode;
  caption?: string;
}

/** Table shell with the responsive wrapper and the shared header styling. */
export function DataTable({ columns, children, caption }: TableProps) {
  return (
    <div className="overflow-x-auto rounded-2xl border border-line">
      <table className="w-full min-w-[34rem] border-collapse text-left text-sm">
        {caption ? <caption className="sr-only">{caption}</caption> : null}
        <thead>
          <tr className="border-b border-line bg-paper-deep">
            {columns.map((column) => (
              <th key={column} scope="col" className="px-4 py-3 text-sm font-semibold text-ink-soft">
                {column}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-line">{children}</tbody>
      </table>
    </div>
  );
}

export interface DisclosureProps {
  id: string;
  title: string;
  subtitle?: string;
  children: ReactNode;
}

/** A collapsed reference block: the heading is always visible, the table opens on demand. */
export function Disclosure({ id, title, subtitle, children }: DisclosureProps) {
  return (
    <details id={id} className="group scroll-mt-20 border-b border-line">
      <summary className="flex cursor-pointer list-none items-center justify-between gap-4 py-5 [&::-webkit-details-marker]:hidden">
        <span>
          <h3 className="text-xl font-semibold leading-tight">{title}</h3>
          {subtitle ? <span className="mt-1 block max-w-[60ch] text-sm leading-relaxed text-ink-soft">{subtitle}</span> : null}
        </span>
        <span
          aria-hidden="true"
          className="grid h-9 w-9 shrink-0 place-items-center rounded-full border border-line text-lg leading-none transition-transform group-open:rotate-45"
        >
          +
        </span>
      </summary>
      <div className="pb-8">{children}</div>
    </details>
  );
}

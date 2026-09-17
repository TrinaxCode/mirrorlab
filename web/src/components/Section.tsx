import type { ReactNode } from "react";

export interface SectionProps {
  id: string;
  title: string;
  subtitle?: string;
  children: ReactNode;
  className?: string;
}

/** Shared section shell: anchor target, heading rhythm and max width. */
export function Section({ id, title, subtitle, children, className = "" }: SectionProps) {
  return (
    <section id={id} className={`scroll-mt-24 px-4 py-14 sm:px-6 sm:py-20 ${className}`}>
      <div className="mx-auto max-w-6xl">
        <div className="mb-8 max-w-2xl">
          <h2 className="text-2xl font-semibold tracking-tight text-white sm:text-3xl">{title}</h2>
          {subtitle ? <p className="mt-3 text-sm leading-relaxed text-slate-400 sm:text-base">{subtitle}</p> : null}
        </div>
        {children}
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
    <div className="card overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full min-w-[36rem] border-collapse text-left text-sm">
          {caption ? <caption className="sr-only">{caption}</caption> : null}
          <thead>
            <tr className="border-b border-white/10 bg-white/[0.03]">
              {columns.map((column) => (
                <th
                  key={column}
                  scope="col"
                  className="px-4 py-3 text-xs font-semibold uppercase tracking-wider text-slate-400"
                >
                  {column}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-white/5">{children}</tbody>
        </table>
      </div>
    </div>
  );
}

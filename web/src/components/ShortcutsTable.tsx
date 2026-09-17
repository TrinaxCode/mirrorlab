import type { Dict } from "../lib/i18n";
import { DataTable, Section } from "./Section";

export interface ShortcutsTableProps {
  strings: Dict;
}

export function ShortcutsTable({ strings }: ShortcutsTableProps) {
  return (
    <Section id="shortcuts" title={strings.shortcuts.title} subtitle={strings.shortcuts.subtitle}>
      <DataTable
        columns={[strings.shortcuts.columns.keys, strings.shortcuts.columns.action]}
        caption={strings.shortcuts.title}
      >
        {strings.shortcuts.rows.map((row) => (
          <tr key={row.keys} className="transition-colors hover:bg-white/[0.03]">
            <td className="w-44 px-4 py-3">
              <kbd className="rounded-md border border-white/15 bg-white/[0.06] px-2.5 py-1.5 font-mono text-[11px] font-semibold text-white shadow-sm">
                {row.keys}
              </kbd>
            </td>
            <td className="px-4 py-3 text-slate-300">{row.action}</td>
          </tr>
        ))}
      </DataTable>
    </Section>
  );
}

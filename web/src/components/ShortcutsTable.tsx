import type { Dict } from "../lib/i18n";
import { DataTable, Disclosure } from "./Section";

export interface ShortcutsTableProps {
  strings: Dict;
}

export function ShortcutsTable({ strings }: ShortcutsTableProps) {
  return (
    <Disclosure id="shortcuts" title={strings.shortcuts.title} subtitle={strings.shortcuts.subtitle}>
      <DataTable
        columns={[strings.shortcuts.columns.keys, strings.shortcuts.columns.action]}
        caption={strings.shortcuts.title}
      >
        {strings.shortcuts.rows.map((row) => (
          <tr key={row.keys}>
            <td className="w-44 px-4 py-3">
              <kbd className="kbd">{row.keys}</kbd>
            </td>
            <td className="px-4 py-3">{row.action}</td>
          </tr>
        ))}
      </DataTable>
    </Disclosure>
  );
}

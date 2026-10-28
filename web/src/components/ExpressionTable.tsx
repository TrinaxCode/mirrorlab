import { EXPRESSIONS, RANKED_EXPRESSIONS } from "../lib/expressions";
import type { Dict, Lang } from "../lib/i18n";
import { DataTable, Disclosure } from "./Section";

export interface ExpressionTableProps {
  strings: Dict;
  lang: Lang;
}

export function ExpressionTable({ strings, lang }: ExpressionTableProps) {
  const rows = RANKED_EXPRESSIONS.map((name) => EXPRESSIONS[name]).filter(
    (definition) => definition !== undefined,
  );

  return (
    <Disclosure id="expressions" title={strings.expressions.title} subtitle={strings.expressions.subtitle}>
      <DataTable
        columns={[
          strings.expressions.columns.emoji,
          strings.expressions.columns.name,
          strings.expressions.columns.what,
        ]}
        caption={strings.expressions.title}
      >
        {rows.map((definition) => (
          <tr key={definition.name} className="align-top">
            <td className="w-16 px-4 py-3">
              <span aria-hidden="true" className="text-2xl leading-none">
                {definition.emoji}
              </span>
            </td>
            <td className="px-4 py-3">
              <div className="font-semibold">
                {lang === "es" ? definition.labelEs : definition.label}
              </div>
              <div className="text-sm text-ink-soft">
                {lang === "es" ? definition.label : definition.labelEs}
              </div>
              <code className="mt-1 inline-block rounded bg-paper-deep px-1.5 py-0.5 text-xs">{definition.name}</code>
            </td>
            <td className="px-4 py-3">
              {lang === "es" ? definition.descriptionEs : definition.description}
            </td>
          </tr>
        ))}
      </DataTable>

      <p className="mt-4 text-sm leading-relaxed text-ink-soft">{strings.expressions.note}</p>
    </Disclosure>
  );
}

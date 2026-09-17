import { EXPRESSIONS, RANKED_EXPRESSIONS } from "../lib/expressions";
import type { Dict, Lang } from "../lib/i18n";
import { DataTable, Section } from "./Section";

export interface ExpressionTableProps {
  strings: Dict;
  lang: Lang;
}

export function ExpressionTable({ strings, lang }: ExpressionTableProps) {
  const rows = RANKED_EXPRESSIONS.map((name) => EXPRESSIONS[name]).filter(
    (definition) => definition !== undefined,
  );

  return (
    <Section
      id="expressions"
      title={strings.expressions.title}
      subtitle={strings.expressions.subtitle}
    >
      <DataTable
        columns={[
          strings.expressions.columns.emoji,
          strings.expressions.columns.name,
          strings.expressions.columns.what,
        ]}
        caption={strings.expressions.title}
      >
        {rows.map((definition) => (
          <tr key={definition.name} className="align-top transition-colors hover:bg-white/[0.03]">
            <td className="w-16 px-4 py-3">
              <span className="grid h-10 w-10 place-items-center rounded-xl border border-white/10 bg-white/[0.04] text-lg">
                {definition.emoji}
              </span>
            </td>
            <td className="px-4 py-3">
              <div className="font-medium text-white">
                {lang === "es" ? definition.labelEs : definition.label}
              </div>
              <div className="text-xs text-slate-500">
                {lang === "es" ? definition.label : definition.labelEs}
              </div>
              <code className="mt-1 inline-block rounded bg-white/[0.05] px-1.5 py-0.5 font-mono text-[11px] text-brand-violet">
                {definition.name}
              </code>
            </td>
            <td className="px-4 py-3 text-slate-300">
              {lang === "es" ? definition.descriptionEs : definition.description}
            </td>
          </tr>
        ))}
      </DataTable>

      <p className="mt-4 text-xs leading-relaxed text-slate-500">{strings.expressions.note}</p>
    </Section>
  );
}

import { DYNAMIC_GESTURES, GESTURES, type GestureDefinition } from "../lib/gestures";
import type { Dict, Lang } from "../lib/i18n";
import { DataTable, Section } from "./Section";

export interface GestureGuideProps {
  strings: Dict;
  lang: Lang;
}

function label(gesture: GestureDefinition, lang: Lang): string {
  return lang === "es" ? gesture.labelEs : gesture.label;
}

function otherLabel(gesture: GestureDefinition, lang: Lang): string {
  return lang === "es" ? gesture.label : gesture.labelEs;
}

function actionLabel(gesture: GestureDefinition, lang: Lang): string {
  return lang === "es" ? gesture.actionLabelEs : gesture.actionLabel;
}

function Rows({ gestures, lang }: { gestures: readonly GestureDefinition[]; lang: Lang }) {
  return (
    <>
      {gestures.map((gesture) => (
        <tr key={gesture.name} className="align-top transition-colors hover:bg-white/[0.03]">
          <td className="w-16 px-4 py-3">
            <span className="grid h-10 w-10 place-items-center rounded-xl border border-white/10 bg-white/[0.04] text-lg">
              {gesture.emoji}
            </span>
          </td>
          <td className="px-4 py-3">
            <div className="font-medium text-white">{label(gesture, lang)}</div>
            <div className="text-xs text-slate-500">{otherLabel(gesture, lang)}</div>
            <code className="mt-1 inline-block rounded bg-white/[0.05] px-1.5 py-0.5 font-mono text-[11px] text-brand-teal">
              {gesture.name}
            </code>
          </td>
          <td className="px-4 py-3">
            <div className={gesture.action ? "text-slate-200" : "text-slate-500"}>
              {actionLabel(gesture, lang)}
            </div>
            <div className="mt-1 text-xs text-slate-500">
              {lang === "es" ? gesture.descriptionEs : gesture.description}
            </div>
          </td>
        </tr>
      ))}
    </>
  );
}

export function GestureGuide({ strings, lang }: GestureGuideProps) {
  return (
    <Section id="gestures" title={strings.gestureGuide.title} subtitle={strings.gestureGuide.subtitle}>
      <DataTable
        columns={[
          strings.gestureGuide.columns.emoji,
          strings.gestureGuide.columns.name,
          strings.gestureGuide.columns.action,
        ]}
        caption={strings.gestureGuide.title}
      >
        <Rows gestures={GESTURES} lang={lang} />
      </DataTable>

      <h3 className="mb-4 mt-10 text-lg font-semibold text-white">{strings.gestureGuide.dynamicTitle}</h3>
      <DataTable
        columns={[
          strings.gestureGuide.columns.emoji,
          strings.gestureGuide.columns.name,
          strings.gestureGuide.columns.action,
        ]}
        caption={strings.gestureGuide.dynamicTitle}
      >
        <Rows gestures={DYNAMIC_GESTURES} lang={lang} />
      </DataTable>

      <p className="mt-4 text-xs leading-relaxed text-slate-500">{strings.gestureGuide.note}</p>
    </Section>
  );
}

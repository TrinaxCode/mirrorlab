import { DYNAMIC_GESTURES, GESTURES, type GestureDefinition } from "../lib/gestures";
import type { Dict, Lang } from "../lib/i18n";
import { DataTable, Disclosure } from "./Section";

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
        <tr key={gesture.name} className="align-top">
          <td className="w-16 px-4 py-3">
            <span aria-hidden="true" className="text-2xl leading-none">
              {gesture.emoji}
            </span>
          </td>
          <td className="px-4 py-3">
            <div className="font-semibold">{label(gesture, lang)}</div>
            <div className="text-sm text-ink-soft">{otherLabel(gesture, lang)}</div>
            <code className="mt-1 inline-block rounded bg-paper-deep px-1.5 py-0.5 text-xs">{gesture.name}</code>
          </td>
          <td className="px-4 py-3">
            <div className={gesture.action ? "" : "text-ink-soft"}>
              {actionLabel(gesture, lang)}
            </div>
            <div className="mt-1 text-sm text-ink-soft">
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
    <Disclosure id="gestures" title={strings.gestureGuide.title} subtitle={strings.gestureGuide.subtitle}>
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

      <h4 className="mb-4 mt-10 text-lg font-semibold">{strings.gestureGuide.dynamicTitle}</h4>
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

      <p className="mt-4 text-sm leading-relaxed text-ink-soft">{strings.gestureGuide.note}</p>
    </Disclosure>
  );
}

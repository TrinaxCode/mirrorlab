import { expressionEmoji, expressionLabel } from "../lib/expressions";
import type { FilterDefinition } from "../lib/filters";
import type { Dict, Lang } from "../lib/i18n";
import type { VisionStats } from "../hooks/useVision";
import type { VisionStage } from "../lib/vision";

export interface StatsPanelProps {
  strings: Dict;
  lang: Lang;
  stats: VisionStats;
  filter: FilterDefinition;
  visible: boolean;
  active: boolean;
  stage: VisionStage | null;
  modelError: string | null;
  usingGpu: boolean;
  onRetryModels: () => void;
}

function Tile({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="rounded-xl bg-screen-raised px-3 py-2.5">
      <div className="text-xs text-screen-soft">{label}</div>
      <div className="mt-0.5 truncate text-base font-semibold tabular-nums" title={hint ?? value}>
        {value}
      </div>
    </div>
  );
}

/** The live HUD: frame rate, inference cost, detections and the top-3 scores. */
export function StatsPanel(props: StatsPanelProps) {
  const { strings, lang, stats, filter, visible, active, stage, modelError, usingGpu, onRetryModels } = props;

  if (!visible) return null;

  const expression = stats.expression;
  const gesture = stats.gesture;
  const placeholder = active ? strings.hud.waiting : strings.hud.paused;

  return (
    <aside className="flex flex-col gap-4 rounded-2xl bg-screen p-4 text-screen-ink" aria-label={strings.hud.title}>
      <div className="grid grid-cols-2 gap-2">
        <Tile label={strings.hud.fps} value={active ? stats.fps.toFixed(0) : "—"} />
        <Tile
          label={strings.hud.inference}
          value={active && stats.inferenceMs > 0 ? `${stats.inferenceMs.toFixed(1)} ms` : "—"}
        />
        <Tile label={strings.hud.hands} value={active ? String(stats.hands) : "—"} />
        <Tile label={strings.hud.filter} value={`${filter.emoji} ${lang === "es" ? filter.labelEs : filter.label}`} />
        <Tile
          label={strings.hud.expression}
          value={
            expression
              ? `${expressionEmoji(expression.name)} ${expressionLabel(expression.name, lang)}`
              : placeholder
          }
        />
        <Tile label={strings.hud.gesture} value={gesture ? `${gesture.emoji} ${gesture.label}` : placeholder} />
      </div>

      <div>
        <div className="mb-2 flex items-center justify-between text-sm text-screen-soft">
          <span>{strings.hud.top3}</span>
          {stats.faceDetected ? null : <span>{strings.hud.noFace}</span>}
        </div>
        <ul className="flex flex-col gap-2">
          {(expression?.top ?? []).map((entry) => (
            <li key={entry.name} className="flex items-center gap-2.5">
              <span className="w-28 shrink-0 truncate text-sm">
                {expressionEmoji(entry.name)} {expressionLabel(entry.name, lang)}
              </span>
              <span className="h-1.5 flex-1 overflow-hidden rounded-full bg-screen-line">
                <span
                  className="block h-full rounded-full bg-signal transition-[width] duration-150"
                  style={{ width: `${Math.max(2, Math.round(entry.score * 100))}%` }}
                />
              </span>
              <span className="w-10 shrink-0 text-right text-sm tabular-nums text-screen-soft">
                {Math.round(entry.score * 100)}%
              </span>
            </li>
          ))}
          {!expression ? <li className="text-sm text-screen-soft">{placeholder}</li> : null}
        </ul>
      </div>

      <div className="flex flex-wrap items-center gap-2 border-t border-screen-line pt-3 text-sm">
        {modelError ? (
          <>
            <span className="text-[#ff8a70]">{strings.vision.errorTitle}</span>
            <button type="button" onClick={onRetryModels} className="btn btn-screen btn-sm">
              {strings.vision.retry}
            </button>
          </>
        ) : (
          <span className="flex items-center gap-2 text-screen-soft">
            <span className={`h-2 w-2 rounded-full ${stage === "ready" ? "bg-signal" : "bg-[#f2b66d]"}`} />
            {stage === "ready" ? strings.vision.ready : strings.vision.loading}
            {stage === "ready" ? (
              <span className="rounded-full border border-screen-line px-2 py-0.5 text-xs">{usingGpu ? "GPU" : "CPU"}</span>
            ) : null}
          </span>
        )}
      </div>
    </aside>
  );
}

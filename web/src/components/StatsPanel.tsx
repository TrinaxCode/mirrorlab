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
    <div className="rounded-xl border border-white/10 bg-white/[0.03] px-3 py-2.5">
      <div className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">{label}</div>
      <div className="mt-1 truncate font-mono text-sm text-white" title={hint ?? value}>
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
    <aside className="card flex flex-col gap-3 p-3" aria-label={strings.hud.title}>
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
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
        <Tile
          label={strings.hud.gesture}
          value={gesture ? `${gesture.emoji} ${gesture.label}` : placeholder}
        />
      </div>

      <div>
        <div className="mb-2 flex items-center justify-between text-[10px] font-semibold uppercase tracking-wider text-slate-500">
          <span>{strings.hud.top3}</span>
          {stats.faceDetected ? null : <span className="text-slate-600">{strings.hud.noFace}</span>}
        </div>
        <ul className="flex flex-col gap-1.5">
          {(expression?.top ?? []).map((entry) => (
            <li key={entry.name} className="flex items-center gap-2">
              <span className="w-28 shrink-0 truncate text-xs text-slate-300">
                {expressionEmoji(entry.name)} {expressionLabel(entry.name, lang)}
              </span>
              <span className="h-1.5 flex-1 overflow-hidden rounded-full bg-white/[0.06]">
                <span
                  className="block h-full rounded-full accent-gradient transition-[width] duration-150"
                  style={{ width: `${Math.max(2, Math.round(entry.score * 100))}%` }}
                />
              </span>
              <span className="w-10 shrink-0 text-right font-mono text-[11px] text-slate-500">
                {Math.round(entry.score * 100)}%
              </span>
            </li>
          ))}
          {!expression ? (
            <li className="text-xs text-slate-600">
              {active ? strings.hud.waiting : strings.hud.paused}
            </li>
          ) : null}
        </ul>
      </div>

      <div className="flex flex-wrap items-center gap-2 border-t border-white/5 pt-3 text-[11px]">
        {modelError ? (
          <>
            <span className="text-rose-300">{strings.vision.errorTitle}</span>
            <button
              type="button"
              onClick={onRetryModels}
              className="rounded-lg border border-white/10 bg-white/[0.05] px-2 py-1 font-medium text-slate-200 transition-colors hover:border-white/20 hover:text-white"
            >
              {strings.vision.retry}
            </button>
          </>
        ) : (
          <span className="flex items-center gap-2 text-slate-400">
            <span
              className={`h-1.5 w-1.5 rounded-full ${stage === "ready" ? "bg-brand-teal" : "bg-amber-300"}`}
            />
            {stage === "ready" ? strings.vision.ready : strings.vision.loading}
            {stage === "ready" ? (
              <span className="rounded-full border border-white/10 px-2 py-0.5 font-mono text-[10px] text-slate-400">
                {usingGpu ? "GPU" : "CPU"}
              </span>
            ) : null}
          </span>
        )}
      </div>
    </aside>
  );
}

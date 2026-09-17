import { FILTERS, filterLabel, type FilterDefinition } from "../lib/filters";
import type { Dict, Lang } from "../lib/i18n";

export interface FilterBarProps {
  strings: Dict;
  lang: Lang;
  activeId: string;
  onSelect: (id: string) => void;
  onStep: (delta: number) => void;
}

/**
 * The horizontal filter strip above the demo. It scrolls instead of wrapping so
 * the controls below it never jump as the selection changes.
 */
export function FilterBar({ strings, lang, activeId, onSelect, onStep }: FilterBarProps) {
  return (
    <div className="card p-3">
      <div className="mb-2 flex items-center justify-between gap-2">
        <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">
          {strings.hud.filter}
        </span>
        <div className="flex items-center gap-1">
          <button
            type="button"
            onClick={() => onStep(-1)}
            aria-label={strings.controls.previous}
            title={strings.controls.previous}
            className="grid h-8 w-8 place-items-center rounded-lg border border-white/10 bg-white/[0.04] text-slate-300 transition-colors hover:border-white/20 hover:text-white"
          >
            ←
          </button>
          <button
            type="button"
            onClick={() => onStep(1)}
            aria-label={strings.controls.next}
            title={strings.controls.next}
            className="grid h-8 w-8 place-items-center rounded-lg border border-white/10 bg-white/[0.04] text-slate-300 transition-colors hover:border-white/20 hover:text-white"
          >
            →
          </button>
        </div>
      </div>

      <div
        role="listbox"
        aria-label={strings.hud.filter}
        className="no-scrollbar flex gap-2 overflow-x-auto pb-1"
      >
        {FILTERS.map((filter) => {
          const active = filter.id === activeId;
          return (
            <button
              key={filter.id}
              type="button"
              role="option"
              aria-selected={active}
              onClick={() => onSelect(filter.id)}
              title={lang === "es" ? filter.descriptionEs : filter.description}
              className={`flex shrink-0 items-center gap-2 rounded-xl border px-3 py-2 text-sm whitespace-nowrap transition-colors ${
                active
                  ? "border-brand-teal/60 bg-brand-teal/10 text-white"
                  : "border-white/10 bg-white/[0.03] text-slate-400 hover:border-white/20 hover:text-white"
              }`}
            >
              <span aria-hidden="true">{filter.emoji}</span>
              {filterLabel(filter, lang)}
            </button>
          );
        })}
      </div>
    </div>
  );
}

export interface FilterGalleryProps {
  strings: Dict;
  lang: Lang;
  activeId: string;
  onSelect: (id: string) => void;
}

/** The landing-page grid: every filter as a clickable card. */
export function FilterGallery({ strings, lang, activeId, onSelect }: FilterGalleryProps) {
  return (
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
      {FILTERS.map((filter) => (
        <FilterCard
          key={filter.id}
          filter={filter}
          lang={lang}
          active={filter.id === activeId}
          onSelect={onSelect}
          strings={strings}
        />
      ))}
    </div>
  );
}

interface FilterCardProps {
  filter: FilterDefinition;
  lang: Lang;
  active: boolean;
  onSelect: (id: string) => void;
  strings: Dict;
}

function FilterCard({ filter, lang, active, onSelect, strings }: FilterCardProps) {
  return (
    <button
      type="button"
      onClick={() => onSelect(filter.id)}
      aria-pressed={active}
      className={`card group h-full p-4 text-left transition-all hover:-translate-y-0.5 hover:border-white/20 ${
        active ? "border-brand-teal/60 bg-brand-teal/[0.06]" : ""
      }`}
    >
      <div className="flex items-start gap-3">
        <span className="grid h-11 w-11 shrink-0 place-items-center rounded-xl border border-white/10 bg-white/[0.04] text-xl">
          {filter.emoji}
        </span>
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-semibold text-white">{filterLabel(filter, lang)}</span>
            {active ? (
              <span className="rounded-full bg-brand-teal/15 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-brand-teal">
                {strings.gallery.applied}
              </span>
            ) : null}
          </div>
          <p className="mt-1.5 text-sm leading-relaxed text-slate-400">
            {lang === "es" ? filter.descriptionEs : filter.description}
          </p>
          <div className="mt-2 flex flex-wrap gap-2 text-[10px] uppercase tracking-wide text-slate-500">
            <span className="rounded-full border border-white/10 px-2 py-0.5">{filter.category}</span>
            {filter.animated ? (
              <span className="rounded-full border border-brand-violet/30 px-2 py-0.5 text-brand-violet">
                {strings.gallery.animated}
              </span>
            ) : null}
            {filter.needsMask ? (
              <span className="rounded-full border border-brand-teal/30 px-2 py-0.5 text-brand-teal">
                {strings.gallery.mask}
              </span>
            ) : null}
          </div>
        </div>
      </div>
    </button>
  );
}

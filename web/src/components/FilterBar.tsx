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
    <div className="rounded-2xl bg-screen p-4 text-screen-ink">
      <div className="mb-3 flex items-center justify-between gap-2">
        <h3 className="text-base font-semibold">{strings.hud.filter}</h3>
        <div className="flex items-center gap-1.5">
          <button
            type="button"
            onClick={() => onStep(-1)}
            aria-label={strings.controls.previous}
            title={strings.controls.previous}
            className="btn btn-screen btn-sm !min-h-10 !w-10 !px-0"
          >
            ←
          </button>
          <button
            type="button"
            onClick={() => onStep(1)}
            aria-label={strings.controls.next}
            title={strings.controls.next}
            className="btn btn-screen btn-sm !min-h-10 !w-10 !px-0"
          >
            →
          </button>
        </div>
      </div>

      <div
        role="listbox"
        aria-label={strings.hud.filter}
        className="no-scrollbar flex gap-2 overflow-x-auto pb-2"
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
              className={`flex min-h-10 shrink-0 items-center gap-2 rounded-full border px-4 text-sm font-medium whitespace-nowrap transition-colors ${
                active
                  ? "border-screen-ink bg-screen-ink text-screen"
                  : "border-screen-line text-screen-soft hover:border-screen-soft hover:text-screen-ink"
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

/** The landing-page list: every filter as a pressable row, in registry order. */
export function FilterGallery({ strings, lang, activeId, onSelect }: FilterGalleryProps) {
  return (
    <ul className="grid border-t border-line sm:grid-cols-2 sm:gap-x-10">
      {FILTERS.map((filter) => (
        <li key={filter.id}>
          <FilterCard
            filter={filter}
            lang={lang}
            active={filter.id === activeId}
            onSelect={onSelect}
            strings={strings}
          />
        </li>
      ))}
    </ul>
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
      className="group flex w-full items-start gap-4 border-b border-line py-4 text-left transition-colors hover:bg-paper-deep"
    >
      <span aria-hidden="true" className="w-9 shrink-0 text-center text-2xl leading-8">
        {filter.emoji}
      </span>
      <span className="min-w-0 flex-1">
        <span className="flex flex-wrap items-center gap-x-3 gap-y-1">
          <span className="text-base font-semibold">{filterLabel(filter, lang)}</span>
          {active ? (
            <span className="rounded-full bg-tally px-2.5 py-0.5 text-xs font-semibold text-on-tally">
              {strings.gallery.applied}
            </span>
          ) : null}
        </span>
        <span className="mt-0.5 block text-sm leading-relaxed text-ink-soft">
          {lang === "es" ? filter.descriptionEs : filter.description}
        </span>
        {filter.animated || filter.needsMask ? (
          <span className="mt-1 block text-sm text-ink-soft">
            {[filter.animated ? strings.gallery.animated : "", filter.needsMask ? strings.gallery.mask : ""]
              .filter(Boolean)
              .join(" · ")}
          </span>
        ) : null}
      </span>
    </button>
  );
}

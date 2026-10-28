import type { Dict } from "../lib/i18n";

export interface TrayItem {
  id: number;
  url: string;
  blob: Blob;
  filename: string;
  takenAt: Date;
}

export interface SnapshotTrayProps {
  strings: Dict;
  items: TrayItem[];
  onDiscard: (id: number) => void;
  onClear: () => void;
}

/**
 * Where gesture snapshots land. A gesture is easy to make by accident, so it
 * never starts a download: the picture waits here until the visitor asks for it.
 */
export function SnapshotTray({ strings, items, onDiscard, onClear }: SnapshotTrayProps) {
  const { tray } = strings;

  return (
    <section aria-label={tray.title} className="rounded-2xl bg-screen p-4 text-screen-ink">
      <div className="flex items-center justify-between gap-2">
        <h3 className="text-base font-semibold">
          {tray.title}
          {items.length > 0 ? <span className="ml-2 text-screen-soft tabular-nums">{items.length}</span> : null}
        </h3>
        {items.length > 1 ? (
          <button type="button" onClick={onClear} className="text-sm text-screen-soft underline underline-offset-4 hover:text-screen-ink">
            {tray.clear}
          </button>
        ) : null}
      </div>

      {items.length === 0 ? (
        <p className="mt-2 text-sm leading-relaxed text-screen-soft">{tray.empty}</p>
      ) : (
        <ul className="mt-3 grid grid-cols-2 gap-3">
          {items.map((item) => (
            <li key={item.id} className="animate-in">
              <img
                src={item.url}
                alt={`${tray.alt} ${item.takenAt.toLocaleTimeString(strings.htmlLang)}`}
                className="aspect-video w-full rounded-lg object-cover"
              />
              <div className="mt-1.5 flex items-center justify-between gap-1 text-sm">
                <a
                  href={item.url}
                  download={item.filename}
                  className="font-semibold text-screen-ink underline underline-offset-4 hover:text-signal"
                >
                  {tray.download}
                </a>
                <button type="button" onClick={() => onDiscard(item.id)} className="text-screen-soft hover:text-screen-ink">
                  {tray.discard}
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

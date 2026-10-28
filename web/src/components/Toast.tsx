import type { ToastItem } from "../hooks/useToasts";

export interface ToastHostProps {
  toasts: ToastItem[];
  onDismiss: (id: number) => void;
  label: string;
}

export function ToastHost({ toasts, onDismiss, label }: ToastHostProps) {
  return (
    <div
      aria-live="polite"
      aria-label={label}
      className="pointer-events-none fixed inset-x-0 bottom-4 z-50 flex flex-col items-center gap-2 px-4 sm:inset-x-auto sm:bottom-6 sm:right-6 sm:items-end"
    >
      {toasts.map((toast) => (
        <div
          key={toast.id}
          className="animate-in pointer-events-auto flex w-full max-w-sm items-center gap-3 rounded-2xl bg-screen px-4 py-3 text-screen-ink shadow-2xl shadow-black/30"
        >
          <span aria-hidden="true" className="text-xl">
            {toast.emoji}
          </span>
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-semibold">{toast.title}</p>
            {toast.detail ? <p className="truncate text-sm text-screen-soft">{toast.detail}</p> : null}
          </div>
          <button
            type="button"
            onClick={() => onDismiss(toast.id)}
            aria-label="×"
            className="grid h-8 w-8 shrink-0 place-items-center rounded-full text-screen-soft transition-colors hover:text-screen-ink"
          >
            ×
          </button>
        </div>
      ))}
    </div>
  );
}

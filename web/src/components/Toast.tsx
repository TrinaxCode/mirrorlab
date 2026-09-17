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
          className="animate-in pointer-events-auto flex w-full max-w-sm items-start gap-3 rounded-2xl border border-white/10 bg-ink-900/95 px-4 py-3 shadow-2xl shadow-black/40 backdrop-blur"
        >
          <span className="grid h-9 w-9 shrink-0 place-items-center rounded-xl border border-white/10 bg-white/[0.05] text-lg">
            {toast.emoji}
          </span>
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-semibold text-white">{toast.title}</p>
            {toast.detail ? <p className="mt-0.5 text-xs text-slate-400">{toast.detail}</p> : null}
          </div>
          <button
            type="button"
            onClick={() => onDismiss(toast.id)}
            aria-label="×"
            className="grid h-6 w-6 shrink-0 place-items-center rounded-lg text-slate-500 transition-colors hover:bg-white/10 hover:text-white"
          >
            ×
          </button>
        </div>
      ))}
    </div>
  );
}

/**
 * Tiny toast queue: newest first, auto-dismissed, and hard-capped so a chatty
 * gesture cannot flood the corner of the screen.
 */

import { useCallback, useEffect, useRef, useState } from "react";

export interface ToastItem {
  id: number;
  emoji: string;
  title: string;
  detail?: string;
}

export interface UseToastsResult {
  toasts: ToastItem[];
  push: (toast: Omit<ToastItem, "id">) => void;
  dismiss: (id: number) => void;
}

export function useToasts(timeoutMs = 2600, max = 3): UseToastsResult {
  const [toasts, setToasts] = useState<ToastItem[]>([]);
  const nextIdRef = useRef(1);
  const timersRef = useRef(new Map<number, number>());

  const dismiss = useCallback((id: number) => {
    const timer = timersRef.current.get(id);
    if (timer !== undefined) {
      window.clearTimeout(timer);
      timersRef.current.delete(id);
    }
    setToasts((current) => current.filter((toast) => toast.id !== id));
  }, []);

  const push = useCallback(
    (toast: Omit<ToastItem, "id">) => {
      const id = nextIdRef.current;
      nextIdRef.current += 1;
      setToasts((current) => [{ id, ...toast }, ...current].slice(0, max));
      const timer = window.setTimeout(() => {
        timersRef.current.delete(id);
        setToasts((current) => current.filter((item) => item.id !== id));
      }, timeoutMs);
      timersRef.current.set(id, timer);
    },
    [max, timeoutMs],
  );

  useEffect(() => {
    const timers = timersRef.current;
    return () => {
      for (const timer of timers.values()) window.clearTimeout(timer);
      timers.clear();
    };
  }, []);

  return { toasts, push, dismiss };
}


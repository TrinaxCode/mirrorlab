/**
 * Persisted state in `localStorage`, with validation and cross-tab syncing.
 *
 * Anything unreadable — disabled storage, hand-edited JSON, a filter id that no
 * longer exists — falls back to the default instead of throwing.
 */

import { useCallback, useEffect, useRef, useState } from "react";

export interface UseLocalStorageOptions<T> {
  /** Return `null` to reject a stored value and keep the default. */
  parse?: (value: unknown) => T | null;
}

export const STORAGE_KEYS = {
  lang: "mirrorlab:lang",
  filter: "mirrorlab:filter",
  settings: "mirrorlab:settings",
} as const;

function read<T>(key: string, fallback: T, parse?: (value: unknown) => T | null): T {
  if (typeof window === "undefined") return fallback;
  try {
    const raw = window.localStorage.getItem(key);
    if (raw === null) return fallback;
    const parsed: unknown = JSON.parse(raw);
    if (!parse) return parsed as T;
    return parse(parsed) ?? fallback;
  } catch {
    return fallback;
  }
}

export function useLocalStorage<T>(
  key: string,
  initialValue: T,
  options: UseLocalStorageOptions<T> = {},
): [T, (value: T | ((previous: T) => T)) => void] {
  const [value, setValue] = useState<T>(() => read(key, initialValue, options.parse));
  const parseRef = useRef(options.parse);

  useEffect(() => {
    parseRef.current = options.parse;
  }, [options.parse]);

  useEffect(() => {
    try {
      window.localStorage.setItem(key, JSON.stringify(value));
    } catch {
      // Storage can be full or blocked (private mode); the app still works.
    }
  }, [key, value]);

  useEffect(() => {
    const onStorage = (event: StorageEvent) => {
      if (event.key !== key || event.newValue === null) return;
      try {
        const parsed: unknown = JSON.parse(event.newValue);
        const next = parseRef.current ? parseRef.current(parsed) : (parsed as T);
        if (next !== null) setValue(next);
      } catch {
        // Another tab wrote something unreadable — ignore it.
      }
    };
    window.addEventListener("storage", onStorage);
    return () => window.removeEventListener("storage", onStorage);
  }, [key]);

  const update = useCallback((next: T | ((previous: T) => T)) => {
    setValue((previous) => (typeof next === "function" ? (next as (p: T) => T)(previous) : next));
  }, []);

  return [value, update];
}

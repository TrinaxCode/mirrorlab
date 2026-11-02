import { useCallback, useEffect, useState } from "react";

import { disableAnalytics, enableAnalytics, trackingRefused } from "../lib/analytics";
import { STORAGE_KEYS, useLocalStorage } from "./useLocalStorage";

export interface AnalyticsConsent {
  /** Statistics are switched on and running. */
  enabled: boolean;
  /** The browser sent Do Not Track / Global Privacy Control, so the choice is not offered. */
  refused: boolean;
  /** The SDK could not start (blocked by an extension, offline). */
  failed: boolean;
  toggle: () => void;
}

/** The visitor's opt-in to anonymous statistics. Default is off. */
export function useAnalyticsConsent(): AnalyticsConsent {
  const refused = trackingRefused();
  const [granted, setGranted] = useLocalStorage<boolean>(STORAGE_KEYS.analytics, false, {
    parse: (value) => (typeof value === "boolean" ? value : null),
  });
  const [failed, setFailed] = useState(false);
  const enabled = granted && !refused;

  useEffect(() => {
    if (!enabled) return;
    let cancelled = false;
    void enableAnalytics().then((ok) => {
      if (!cancelled) setFailed(!ok);
    });
    return () => {
      cancelled = true;
    };
  }, [enabled]);

  const toggle = useCallback(() => {
    if (refused) return;
    if (granted) disableAnalytics();
    setGranted(!granted);
  }, [granted, refused, setGranted]);

  return { enabled, refused, failed, toggle };
}

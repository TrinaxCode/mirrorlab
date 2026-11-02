/**
 * Optional, anonymous usage statistics through Firebase Analytics.
 *
 * MirrorLab's promise is that your video never leaves your machine, so this is
 * opt-in and off by default: nothing from Firebase is downloaded or contacted
 * until a visitor turns it on. The SDK is imported dynamically for that reason,
 * which also keeps it out of the first load. Browsers that send Do Not Track or
 * Global Privacy Control are never asked and never enabled.
 *
 * Only page views and the clicks on the download buttons are recorded. No video,
 * no camera frames and no photos are ever part of an event.
 */

import type { Analytics } from "firebase/analytics";

import { FIREBASE_CONFIG } from "./firebase-config";

let analytics: Analytics | null = null;
let starting: Promise<boolean> | null = null;

/** `true` when the browser asks not to be tracked. Then the option is not even offered. */
export function trackingRefused(): boolean {
  if (typeof navigator === "undefined") return true;
  const nav = navigator as Navigator & { globalPrivacyControl?: boolean };
  const dnt = nav.doNotTrack ?? (window as { doNotTrack?: string }).doNotTrack;
  return dnt === "1" || dnt === "yes" || nav.globalPrivacyControl === true;
}

function disableFlag(): string {
  return `ga-disable-${FIREBASE_CONFIG.measurementId}`;
}

/** Load Firebase Analytics and start collecting. Resolves `false` if the browser cannot run it. */
export function enableAnalytics(): Promise<boolean> {
  if (trackingRefused()) return Promise.resolve(false);
  (window as unknown as Record<string, unknown>)[disableFlag()] = false;
  const running = analytics;
  if (running) {
    return import("firebase/analytics").then((sdk) => {
      sdk.setAnalyticsCollectionEnabled(running, true);
      return true;
    });
  }
  starting ??= (async () => {
    try {
      const [{ getApps, initializeApp }, sdk] = await Promise.all([import("firebase/app"), import("firebase/analytics")]);
      if (!(await sdk.isSupported())) return false;
      const app = getApps()[0] ?? initializeApp(FIREBASE_CONFIG);
      analytics = sdk.getAnalytics(app);
      sdk.setAnalyticsCollectionEnabled(analytics, true);
      return true;
    } catch {
      // Blocked by an extension, offline, or a strict CSP: the site works the same without it.
      return false;
    } finally {
      starting = null;
    }
  })();
  return starting;
}

/** Stop collecting right away, including events already queued by the SDK. */
export function disableAnalytics(): void {
  (window as unknown as Record<string, unknown>)[disableFlag()] = true;
  if (!analytics) return;
  const current = analytics;
  void import("firebase/analytics").then((sdk) => sdk.setAnalyticsCollectionEnabled(current, false));
}

/** Record a named event, or do nothing when statistics are off. */
export function trackEvent(name: string, params?: Record<string, string>): void {
  if (!analytics) return;
  const current = analytics;
  void import("firebase/analytics").then((sdk) => sdk.logEvent(current, name, params));
}

import { useCallback, useEffect, useRef, useState } from "react";

import { useVision, type GestureEvent } from "../hooks/useVision";
import { useCamera } from "../hooks/useCamera";
import { STORAGE_KEYS, useLocalStorage } from "../hooks/useLocalStorage";
import { FILTERS, getFilter, stepFilterId } from "../lib/filters";
import { findGesture } from "../lib/gestures";
import type { Dict, Lang } from "../lib/i18n";
import { downloadBlob, snapshotFilename } from "../lib/site";
import { CameraStage } from "./CameraStage";
import { FilterBar } from "./FilterBar";
import { Section } from "./Section";
import { SnapshotTray, type TrayItem } from "./SnapshotTray";
import { StatsPanel } from "./StatsPanel";

const TRAY_LIMIT = 8;
const TRAY_COOLDOWN_MS = 4000;

export interface DemoSettings {
  overlay: boolean;
  landmarks: boolean;
  hud: boolean;
  mirrored: boolean;
  includeOverlay: boolean;
}

const DEFAULT_SETTINGS: DemoSettings = {
  overlay: true,
  landmarks: false,
  hud: true,
  mirrored: true,
  includeOverlay: true,
};

function parseSettings(value: unknown): DemoSettings | null {
  if (!value || typeof value !== "object") return null;
  const raw = value as Record<string, unknown>;
  const bool = (key: keyof DemoSettings): boolean =>
    typeof raw[key] === "boolean" ? (raw[key]) : DEFAULT_SETTINGS[key];
  return {
    overlay: bool("overlay"),
    landmarks: bool("landmarks"),
    hud: bool("hud"),
    mirrored: bool("mirrored"),
    includeOverlay: bool("includeOverlay"),
  };
}

export interface DemoSectionProps {
  strings: Dict;
  lang: Lang;
  filterId: string;
  onSelectFilter: (id: string) => void;
  onToggleLang: () => void;
  notify: (toast: { emoji: string; title: string; detail?: string }) => void;
}

/** Everything that needs the camera: the stage, the controls and the HUD. */
export function DemoSection(props: DemoSectionProps) {
  const { strings, lang, filterId, onSelectFilter, onToggleLang, notify } = props;
  const [settings, setSettings] = useLocalStorage<DemoSettings>(STORAGE_KEYS.settings, DEFAULT_SETTINGS, {
    parse: parseSettings,
  });
  const [frozen, setFrozen] = useState(false);
  const [webglError, setWebglError] = useState<string | null>(null);

  // The three media elements are owned here and shared with the hooks and the
  // stage. Effects run after commit, so the refs are always populated by then.
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const filterCanvasRef = useRef<HTMLCanvasElement | null>(null);
  const overlayCanvasRef = useRef<HTMLCanvasElement | null>(null);
  const takeSnapshotRef = useRef<(mode: "download" | "tray") => Promise<void>>(() => Promise.resolve());
  const lastTrayAt = useRef(0);
  const trayRef = useRef<TrayItem[]>([]);
  const [tray, setTray] = useState<TrayItem[]>([]);

  const camera = useCamera(videoRef);
  const live = camera.status === "live";
  const filter = getFilter(filterId);

  const handleSoftError = useCallback(
    (message: string) => {
      notify({ emoji: "⚠️", title: strings.vision.errorTitle, detail: message });
    },
    [notify, strings.vision.errorTitle],
  );

  const handleFatalError = useCallback((message: string) => {
    setWebglError(message);
  }, []);

  const handleGesture = useCallback(
    (event: GestureEvent) => {
      const definition = findGesture(event.name);
      const detail = definition ? (lang === "es" ? definition.actionLabelEs : definition.actionLabel) : undefined;
      notify({
        emoji: event.emoji,
        title: lang === "es" ? event.labelEs : event.label,
        detail,
      });
      switch (event.action) {
        case "next_filter":
          onSelectFilter(stepFilterId(filterId, 1));
          break;
        case "prev_filter":
          onSelectFilter(stepFilterId(filterId, -1));
          break;
        case "toggle_overlay":
          setSettings((current) => ({ ...current, overlay: !current.overlay }));
          break;
        case "toggle_hud":
          setSettings((current) => ({ ...current, hud: !current.hud }));
          break;
        case "freeze":
          setFrozen((current) => !current);
          break;
        case "snapshot": {
          // A gesture must never start a download: a thumbs up is easy to make by
          // accident. It adds to the in-page tray, at most once every few seconds.
          const now = performance.now();
          if (now - lastTrayAt.current >= TRAY_COOLDOWN_MS) {
            lastTrayAt.current = now;
            void takeSnapshotRef.current("tray");
          }
          break;
        }
        case "toggle_glitch":
          onSelectFilter(filterId === "glitch" ? "original" : "glitch");
          break;
        default:
          break;
      }
    },
    [filterId, lang, notify, onSelectFilter, setSettings],
  );

  const vision = useVision({
    videoRef,
    filterCanvasRef,
    overlayCanvasRef,
    active: live,
    filterId,
    mirrored: settings.mirrored,
    overlayEnabled: settings.overlay,
    debugLandmarks: settings.landmarks,
    frozen,
    lang,
    onGesture: handleGesture,
    onFatalError: handleFatalError,
    onSoftError: handleSoftError,
  });

  const discardTrayItem = useCallback((id: number) => {
    setTray((current) => {
      const gone = current.find((item) => item.id === id);
      if (gone) URL.revokeObjectURL(gone.url);
      return current.filter((item) => item.id !== id);
    });
  }, []);

  const clearTray = useCallback(() => {
    setTray((current) => {
      for (const item of current) URL.revokeObjectURL(item.url);
      return [];
    });
  }, []);

  useEffect(() => {
    trayRef.current = tray;
  }, [tray]);

  // Free the picture memory when the demo goes away.
  useEffect(
    () => () => {
      for (const item of trayRef.current) URL.revokeObjectURL(item.url);
    },
    [],
  );

  const takeSnapshot = useCallback(
    async (mode: "download" | "tray" = "download") => {
      const blob = await vision.captureSnapshot(settings.includeOverlay);
      if (!blob) {
        notify({ emoji: "⚠️", title: strings.toast.snapshotFailed });
        return;
      }
      const filename = snapshotFilename();
      if (mode === "download") {
        downloadBlob(blob, filename);
        notify({ emoji: "📸", title: strings.toast.snapshotSaved, detail: filename });
        return;
      }
      const item: TrayItem = { id: Date.now(), url: URL.createObjectURL(blob), blob, filename, takenAt: new Date() };
      setTray((current) => {
        const next = [item, ...current];
        for (const dropped of next.slice(TRAY_LIMIT)) URL.revokeObjectURL(dropped.url);
        return next.slice(0, TRAY_LIMIT);
      });
      notify({ emoji: "📸", title: strings.toast.snapshotTray, detail: filename });
    },
    [
      notify,
      settings.includeOverlay,
      strings.toast.snapshotFailed,
      strings.toast.snapshotSaved,
      strings.toast.snapshotTray,
      vision,
    ],
  );

  // The gesture handler runs inside the animation loop, so it reaches the
  // snapshot function through a ref instead of a stale closure.
  useEffect(() => {
    takeSnapshotRef.current = takeSnapshot;
  }, [takeSnapshot]);

  // `onSelectFilter` lives in App: every route to a filter change (filter bar,
  // gallery, keyboard, gesture) announces itself through the same toast.
  const stepFilter = useCallback(
    (delta: number) => onSelectFilter(stepFilterId(filterId, delta)),
    [filterId, onSelectFilter],
  );

  const resetSettings = useCallback(() => {
    setSettings(DEFAULT_SETTINGS);
    setFrozen(false);
    notify({ emoji: "♻️", title: strings.toast.settingsReset });
  }, [notify, setSettings, strings.toast.settingsReset]);

  // -- keyboard shortcuts -------------------------------------------------- //
  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.metaKey || event.ctrlKey || event.altKey) return;
      const target = event.target as HTMLElement | null;
      if (
        target &&
        (target.tagName === "INPUT" ||
          target.tagName === "TEXTAREA" ||
          target.tagName === "SELECT" ||
          target.isContentEditable)
      ) {
        return;
      }
      const key = event.key.toLowerCase();
      if (key === "arrowright" || key === "arrowleft") event.preventDefault();

      switch (key) {
        case "n":
        case "arrowright":
          stepFilter(1);
          break;
        case "p":
        case "arrowleft":
          stepFilter(-1);
          break;
        case "s":
          void takeSnapshot("download");
          break;
        case "f":
          if (live) setFrozen((current) => !current);
          break;
        case "o":
          setSettings((current) => ({ ...current, overlay: !current.overlay }));
          break;
        case "l":
          setSettings((current) => ({ ...current, landmarks: !current.landmarks }));
          break;
        case "h":
          setSettings((current) => ({ ...current, hud: !current.hud }));
          break;
        case "m":
          setSettings((current) => ({ ...current, mirrored: !current.mirrored }));
          break;
        case "t":
          onToggleLang();
          break;
        case "r":
          resetSettings();
          break;
        default: {
          if (/^[1-9]$/.test(key)) {
            const shortcutTarget = FILTERS[Number(key) - 1];
            if (shortcutTarget) onSelectFilter(shortcutTarget.id);
          }
        }
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [live, onSelectFilter, onToggleLang, resetSettings, setSettings, stepFilter, takeSnapshot]);

  return (
    <Section id="demo" title={strings.demo.title} subtitle={strings.demo.subtitle} wide>
      <div className="grid grid-cols-[minmax(0,1fr)] gap-5 lg:grid-cols-[minmax(0,1fr)_21rem]">
        <CameraStage
          strings={strings}
          videoRef={videoRef}
          filterCanvasRef={filterCanvasRef}
          overlayCanvasRef={overlayCanvasRef}
          status={camera.status}
          error={camera.error}
          errorDetail={camera.detail}
          devices={camera.devices}
          deviceId={camera.deviceId}
          onStart={() => void camera.start()}
          onSelectDevice={camera.selectDevice}
          stage={vision.stage}
          modelError={vision.modelError}
          onRetryModels={vision.retryModels}
          webglError={webglError}
          handsCount={vision.stats.hands}
          frozen={frozen}
          mirrored={settings.mirrored}
          overlayEnabled={settings.overlay}
        >
          <FilterBar
            strings={strings}
            lang={lang}
            activeId={filterId}
            onSelect={onSelectFilter}
            onStep={stepFilter}
          />
        </CameraStage>

        <div className="flex flex-col gap-4">
          <div className="rounded-2xl bg-screen p-4 text-screen-ink">
            <h3 className="text-base font-semibold">{strings.controls.title}</h3>
            <div className="mt-3 flex flex-wrap gap-2">
              <ControlButton
                active={settings.overlay}
                label={strings.controls.overlays}
                shortcut="O"
                onClick={() => setSettings((current) => ({ ...current, overlay: !current.overlay }))}
              />
              <ControlButton
                active={settings.landmarks}
                label={strings.controls.landmarks}
                shortcut="L"
                onClick={() => setSettings((current) => ({ ...current, landmarks: !current.landmarks }))}
              />
              <ControlButton
                active={settings.hud}
                label={strings.controls.hud}
                shortcut="H"
                onClick={() => setSettings((current) => ({ ...current, hud: !current.hud }))}
              />
              <ControlButton
                active={frozen}
                label={strings.controls.freeze}
                shortcut="F"
                disabled={!live}
                onClick={() => setFrozen((current) => !current)}
              />
              <ControlButton
                active={settings.mirrored}
                label={strings.controls.mirror}
                shortcut="M"
                onClick={() => setSettings((current) => ({ ...current, mirrored: !current.mirrored }))}
              />
            </div>

            <div className="mt-4 flex flex-wrap items-center gap-2">
              <button
                type="button"
                onClick={() => void takeSnapshot("download")}
                disabled={!live}
                className="btn btn-primary btn-sm disabled:cursor-not-allowed disabled:opacity-45"
              >
                {strings.controls.snapshot}
              </button>
              {live ? (
                <button type="button" onClick={camera.stop} className="btn btn-screen btn-sm">
                  {strings.demo.stop}
                </button>
              ) : null}
              <button type="button" onClick={resetSettings} className="btn btn-screen btn-sm">
                {strings.controls.reset}
              </button>
            </div>

            <label className="mt-4 flex items-center gap-2.5 text-sm text-screen-soft">
              <input
                type="checkbox"
                checked={settings.includeOverlay}
                onChange={(event) =>
                  setSettings((current) => ({ ...current, includeOverlay: event.target.checked }))
                }
                className="h-4 w-4 rounded accent-[#ff5b38]"
              />
              {strings.controls.includeOverlay}
            </label>

            {live && camera.devices.length > 1 ? (
              <label className="mt-4 flex items-center gap-3 text-sm text-screen-soft">
                <span className="shrink-0">{strings.demo.cameraLabel}</span>
                <select
                  value={camera.deviceId ?? ""}
                  onChange={(event) => camera.selectDevice(event.target.value)}
                  className="min-h-10 w-full rounded-lg border border-screen-line bg-screen-raised px-2 text-sm text-screen-ink"
                >
                  {camera.devices.map((device) => (
                    <option key={device.deviceId} value={device.deviceId}>
                      {device.label}
                    </option>
                  ))}
                </select>
              </label>
            ) : null}
          </div>

          <SnapshotTray strings={strings} items={tray} onDiscard={discardTrayItem} onClear={clearTray} />

          <StatsPanel
            strings={strings}
            lang={lang}
            stats={vision.stats}
            filter={filter}
            visible={settings.hud}
            active={live}
            stage={vision.stage}
            modelError={vision.modelError}
            usingGpu={vision.usingGpu}
            onRetryModels={vision.retryModels}
          />

          {live ? (
            <div className="rounded-2xl bg-screen p-4 text-screen-ink">
              <h3 className="text-base font-semibold">{strings.gestureGuide.title}</h3>
              <ul className="mt-3 flex flex-col gap-2 text-sm">
                {["peace", "thumbs_up", "ok", "fist", "swipe_right"].map((name) => {
                  const definition = findGesture(name);
                  if (!definition) return null;
                  return (
                    <li key={name} className="flex items-center gap-2.5">
                      <span aria-hidden="true">{definition.emoji}</span>
                      <span>{lang === "es" ? definition.labelEs : definition.label}</span>
                      <span className="ml-auto text-right text-screen-soft">
                        {lang === "es" ? definition.actionLabelEs : definition.actionLabel}
                      </span>
                    </li>
                  );
                })}
              </ul>
            </div>
          ) : null}
        </div>
      </div>
    </Section>
  );
}

interface ControlButtonProps {
  active: boolean;
  label: string;
  shortcut: string;
  disabled?: boolean;
  onClick: () => void;
}

function ControlButton({ active, label, shortcut, disabled = false, onClick }: ControlButtonProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      aria-pressed={active}
      className={`inline-flex min-h-10 items-center gap-2 rounded-full border px-3.5 text-sm font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-45 ${
        active
          ? "border-screen-ink bg-screen-ink text-screen"
          : "border-screen-line text-screen-soft hover:border-screen-soft hover:text-screen-ink"
      }`}
    >
      {label}
      <span className="kbd !px-1.5 !py-0 !text-[11px]">{shortcut}</span>
    </button>
  );
}

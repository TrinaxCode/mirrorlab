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
import { StatsPanel } from "./StatsPanel";

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
  const takeSnapshotRef = useRef<() => Promise<void>>(() => Promise.resolve());

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
        case "snapshot":
          void takeSnapshotRef.current();
          break;
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

  const takeSnapshot = useCallback(async () => {
    const blob = await vision.captureSnapshot(settings.includeOverlay);
    if (!blob) {
      notify({ emoji: "⚠️", title: strings.toast.snapshotFailed });
      return;
    }
    const filename = snapshotFilename();
    downloadBlob(blob, filename);
    notify({ emoji: "📸", title: strings.toast.snapshotSaved, detail: filename });
  }, [notify, settings.includeOverlay, strings.toast.snapshotFailed, strings.toast.snapshotSaved, vision]);

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
          void takeSnapshot();
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
    <Section id="demo" title={strings.demo.title} subtitle={strings.demo.subtitle}>
      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_20rem]">
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

        <div className="flex flex-col gap-3">
          <div className="card p-3">
            <div className="mb-2 text-xs font-semibold uppercase tracking-wider text-slate-500">
              {strings.controls.title}
            </div>
            <div className="flex flex-wrap gap-2">
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

            <div className="mt-3 flex flex-wrap items-center gap-2">
              <button
                type="button"
                onClick={() => void takeSnapshot()}
                disabled={!live}
                className="rounded-xl accent-gradient px-3.5 py-2 text-sm font-semibold text-ink-950 transition-transform hover:-translate-y-0.5 disabled:cursor-not-allowed disabled:opacity-50 disabled:hover:translate-y-0"
              >
                📸 {strings.controls.snapshot}
              </button>
              {live ? (
                <button
                  type="button"
                  onClick={camera.stop}
                  className="rounded-xl border border-white/10 bg-white/[0.04] px-3.5 py-2 text-sm font-medium text-slate-300 transition-colors hover:border-white/20 hover:text-white"
                >
                  {strings.demo.stop}
                </button>
              ) : null}
              <button
                type="button"
                onClick={resetSettings}
                className="rounded-xl border border-white/10 bg-white/[0.04] px-3.5 py-2 text-sm font-medium text-slate-300 transition-colors hover:border-white/20 hover:text-white"
              >
                {strings.controls.reset}
              </button>
            </div>

            <label className="mt-3 flex items-center gap-2 text-xs text-slate-400">
              <input
                type="checkbox"
                checked={settings.includeOverlay}
                onChange={(event) =>
                  setSettings((current) => ({ ...current, includeOverlay: event.target.checked }))
                }
                className="h-4 w-4 rounded border-white/20 bg-transparent accent-teal-300"
              />
              {strings.controls.includeOverlay}
            </label>

            {live && camera.devices.length > 1 ? (
              <label className="mt-3 flex items-center gap-2 text-xs text-slate-400">
                <span className="shrink-0 uppercase tracking-wider">{strings.demo.cameraLabel}</span>
                <select
                  value={camera.deviceId ?? ""}
                  onChange={(event) => camera.selectDevice(event.target.value)}
                  className="w-full rounded-lg border border-white/10 bg-ink-800 px-2 py-1.5 text-sm text-slate-200 outline-none"
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
            <div className="card p-3">
              <div className="mb-2 text-xs font-semibold uppercase tracking-wider text-slate-500">
                {strings.gestureGuide.title}
              </div>
              <ul className="flex flex-col gap-1.5 text-xs text-slate-400">
                {["peace", "thumbs_up", "ok", "fist", "swipe_right"].map((name) => {
                  const definition = findGesture(name);
                  if (!definition) return null;
                  return (
                    <li key={name} className="flex items-center gap-2">
                      <span aria-hidden="true">{definition.emoji}</span>
                      <span className="text-slate-300">
                        {lang === "es" ? definition.labelEs : definition.label}
                      </span>
                      <span className="ml-auto text-right text-slate-500">
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
      className={`inline-flex items-center gap-2 rounded-xl border px-3 py-2 text-xs font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-50 ${
        active
          ? "border-brand-teal/60 bg-brand-teal/10 text-white"
          : "border-white/10 bg-white/[0.03] text-slate-400 hover:border-white/20 hover:text-white"
      }`}
    >
      <span
        aria-hidden="true"
        className={`h-1.5 w-1.5 rounded-full ${active ? "bg-brand-teal" : "bg-slate-600"}`}
      />
      {label}
      <kbd className="rounded border border-white/10 bg-black/20 px-1 font-mono text-[10px] text-slate-400">
        {shortcut}
      </kbd>
    </button>
  );
}

import type { ReactNode, RefObject } from "react";

import type { CameraDevice, CameraErrorKind, CameraStatus } from "../hooks/useCamera";
import type { Dict } from "../lib/i18n";
import type { VisionStage } from "../lib/vision";
import { CameraPermission } from "./CameraPermission";

export interface CameraStageProps {
  strings: Dict;
  videoRef: RefObject<HTMLVideoElement | null>;
  filterCanvasRef: RefObject<HTMLCanvasElement | null>;
  overlayCanvasRef: RefObject<HTMLCanvasElement | null>;
  status: CameraStatus;
  error: CameraErrorKind | null;
  errorDetail: string;
  devices: CameraDevice[];
  deviceId: string | null;
  onStart: () => void;
  onSelectDevice: (deviceId: string) => void;
  stage: VisionStage | null;
  modelError: string | null;
  onRetryModels: () => void;
  webglError: string | null;
  handsCount: number;
  frozen: boolean;
  mirrored: boolean;
  overlayEnabled: boolean;
  /** The filter bar and controls, rendered under the picture. */
  children?: ReactNode;
}

const STAGE_PROGRESS: Record<VisionStage, number> = {
  wasm: 12,
  face: 55,
  hands: 92,
  segmenter: 100,
  ready: 100,
};

/**
 * The heart of the demo: a hidden (but still decoding) video element with the
 * two stacked canvases on top — WebGL2 for the filter, 2D for the overlay.
 */
export function CameraStage(props: CameraStageProps) {
  const {
    strings,
    videoRef,
    filterCanvasRef,
    overlayCanvasRef,
    status,
    error,
    errorDetail,
    devices,
    deviceId,
    onStart,
    onSelectDevice,
    stage,
    modelError,
    onRetryModels,
    webglError,
    handsCount,
    frozen,
    mirrored,
    overlayEnabled,
    children,
  } = props;

  const live = status === "live";
  const loadingModels = live && stage !== null && stage !== "ready" && !modelError;
  const progress = stage ? STAGE_PROGRESS[stage] : 0;

  return (
    <div className="flex flex-col gap-3">
      <div className="relative aspect-video w-full overflow-hidden rounded-2xl border border-white/10 bg-ink-900">
        {/* Kept in the layout (not `display:none`) so the decoder never throttles. */}
        <video
          ref={videoRef}
          className="absolute inset-0 h-full w-full object-cover opacity-0"
          playsInline
          muted
          autoPlay
          aria-hidden="true"
        />
        <canvas
          ref={filterCanvasRef}
          width={1280}
          height={720}
          className="absolute inset-0 h-full w-full"
          aria-label={strings.hud.filter}
        />
        <canvas
          ref={overlayCanvasRef}
          width={1280}
          height={720}
          className="pointer-events-none absolute inset-0 h-full w-full"
          aria-hidden="true"
        />

        {!live ? (
          <div className="absolute inset-0 grid place-items-center bg-ink-950/85 p-4 sm:p-8">
            <CameraPermission
              strings={strings}
              error={error}
              detail={errorDetail}
              devices={devices}
              deviceId={deviceId}
              starting={status === "starting"}
              onStart={onStart}
              onSelectDevice={onSelectDevice}
            />
          </div>
        ) : null}

        {live ? (
          <div className="pointer-events-none absolute inset-x-3 bottom-3 flex flex-wrap items-center gap-2 text-[11px]">
            <span className="rounded-full border border-white/10 bg-ink-950/70 px-2.5 py-1 font-medium text-slate-300 backdrop-blur">
              🖐️ {handsCount} {strings.demo.handsBadge}
            </span>
            {frozen ? (
              <span className="rounded-full border border-brand-violet/40 bg-brand-violet/15 px-2.5 py-1 font-semibold text-brand-violet backdrop-blur">
                {strings.demo.frozenBadge}
              </span>
            ) : null}
            {mirrored ? (
              <span className="rounded-full border border-white/10 bg-ink-950/70 px-2.5 py-1 font-medium text-slate-300 backdrop-blur">
                {strings.demo.mirrorBadge}
              </span>
            ) : null}
            {!overlayEnabled ? (
              <span className="rounded-full border border-white/10 bg-ink-950/70 px-2.5 py-1 font-medium text-slate-400 backdrop-blur">
                {strings.demo.overlayHidden}
              </span>
            ) : null}
          </div>
        ) : null}

        {loadingModels ? (
          <div className="absolute inset-x-0 top-0 border-b border-white/10 bg-ink-950/85 px-4 py-3 backdrop-blur">
            <div className="flex items-center justify-between text-xs text-slate-300">
              <span>{strings.demo.loadingModels}</span>
              <span className="font-mono text-slate-500">{progress}%</span>
            </div>
            <div className="mt-2 h-1 overflow-hidden rounded-full bg-white/10">
              <div
                className="h-full rounded-full accent-gradient transition-[width] duration-500"
                style={{ width: `${progress}%` }}
              />
            </div>
          </div>
        ) : null}

        {modelError ? (
          <div className="absolute inset-x-3 top-3 rounded-xl border border-amber-400/30 bg-amber-400/10 p-3 text-xs text-amber-100 backdrop-blur">
            <p className="font-semibold">{strings.vision.errorTitle}</p>
            <p className="mt-1 text-amber-100/80">{strings.vision.errorBody}</p>
            <p className="mt-1 font-mono text-[10px] break-all text-amber-200/70">{modelError}</p>
            <button
              type="button"
              onClick={onRetryModels}
              className="mt-2 rounded-lg border border-amber-200/30 bg-amber-200/10 px-2.5 py-1 font-medium text-amber-50 transition-colors hover:bg-amber-200/20"
            >
              {strings.vision.retry}
            </button>
          </div>
        ) : null}

        {webglError ? (
          <div className="absolute inset-x-3 top-3 rounded-xl border border-rose-400/30 bg-rose-500/10 p-3 text-xs text-rose-100 backdrop-blur">
            <p className="font-semibold">{strings.webgl.title}</p>
            <p className="mt-1 text-rose-100/80">{strings.webgl.body}</p>
            <p className="mt-1 font-mono text-[10px] break-all text-rose-200/70">{webglError}</p>
          </div>
        ) : null}
      </div>

      {children}
    </div>
  );
}

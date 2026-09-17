/**
 * The render loop: one `requestAnimationFrame` that uploads the camera frame,
 * runs MediaPipe inference, classifies expressions and gestures, draws the
 * overlay and finally composites the active WebGL filter.
 *
 * React state is intentionally *not* touched per frame — the loop writes into
 * refs and pushes a throttled stats snapshot to the HUD a few times per second,
 * which keeps 60 fps rendering independent of React's scheduler.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { RefObject } from "react";

import { ExpressionClassifier, expressionEmoji, expressionLabel } from "../lib/expressions";
import { getFilter } from "../lib/filters";
import {
  GestureTracker,
  classifyGesture,
  type GestureAction,
  type Handedness,
  type HandObservation,
} from "../lib/gestures";
import type { Lang } from "../lib/i18n";
import { drawOverlay, type OverlayBadge } from "../lib/overlay";
import { FilterRenderer, WebGLUnavailableError } from "../lib/renderer";
import { LandmarkSmoother } from "../lib/smoothing";
import { VisionEngine, type VisionStage } from "../lib/vision";

export interface GestureEvent {
  name: string;
  emoji: string;
  label: string;
  labelEs: string;
  score: number;
  action: GestureAction | "";
}

export interface ExpressionSummary {
  name: string;
  score: number;
  top: { name: string; score: number }[];
}

export interface GestureSummary {
  name: string;
  emoji: string;
  label: string;
  score: number;
}

export interface VisionStats {
  fps: number;
  inferenceMs: number;
  hands: number;
  faceDetected: boolean;
  expression: ExpressionSummary | null;
  gesture: GestureSummary | null;
}

export interface UseVisionOptions {
  videoRef: RefObject<HTMLVideoElement | null>;
  filterCanvasRef: RefObject<HTMLCanvasElement | null>;
  overlayCanvasRef: RefObject<HTMLCanvasElement | null>;
  /** The camera is live and the demo is on screen. */
  active: boolean;
  filterId: string;
  mirrored: boolean;
  overlayEnabled: boolean;
  debugLandmarks: boolean;
  frozen: boolean;
  lang: Lang;
  onGesture: (event: GestureEvent) => void;
  onFatalError: (message: string) => void;
  onSoftError: (message: string) => void;
}

export interface UseVisionResult {
  /** Coarse loading stage of the MediaPipe models, `null` before they start. */
  stage: VisionStage | null;
  /** Set when the models could not be loaded at all. */
  modelError: string | null;
  usingGpu: boolean;
  stats: VisionStats;
  retryModels: () => void;
  captureSnapshot: (includeOverlay: boolean) => Promise<Blob | null>;
}

export const EMPTY_STATS: VisionStats = {
  fps: 0,
  inferenceMs: 0,
  hands: 0,
  faceDetected: false,
  expression: null,
  gesture: null,
};

/** One action per gesture per second, and only on a fresh occurrence. */
const GESTURE_COOLDOWN_MS = 1000;
/** Frames a static gesture must persist before it counts as deliberate. */
const GESTURE_CONFIRM_FRAMES = 2;
const STATS_INTERVAL_MS = 200;

interface Point {
  x: number;
  y: number;
}

export function useVision(options: UseVisionOptions): UseVisionResult {
  const {
    videoRef,
    filterCanvasRef,
    overlayCanvasRef,
    active,
    filterId,
    mirrored,
    overlayEnabled,
    debugLandmarks,
    frozen,
    lang,
    onGesture,
    onFatalError,
    onSoftError,
  } = options;

  const [engine, setEngine] = useState<VisionEngine | null>(null);
  const [stage, setStage] = useState<VisionStage | null>(null);
  const [modelError, setModelError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);
  const [stats, setStats] = useState<VisionStats>(EMPTY_STATS);

  const rendererRef = useRef<FilterRenderer | null>(null);
  const classifierRef = useRef(new ExpressionClassifier());
  const trackerRef = useRef(new GestureTracker());
  const faceSmootherRef = useRef(new LandmarkSmoother());
  const handSmoothersRef = useRef<LandmarkSmoother[]>([new LandmarkSmoother(), new LandmarkSmoother()]);

  // Landmarks from the most recent inference, kept in refs so the overlay can be
  // redrawn (smoothly) even on frames where no new detection happened.
  const facePointsRef = useRef<Point[] | null>(null);
  const handPointsRef = useRef<{ points: Point[]; handedness: Handedness }[]>([]);

  // Latest values for the animation loop, which must not restart on every
  // settings change. They are published after each commit, never during render.
  const settingsRef = useRef({ mirrored, overlayEnabled, debugLandmarks, frozen, lang });
  const handlersRef = useRef({ onGesture, onFatalError, onSoftError });
  const filterRef = useRef(filterId);

  useEffect(() => {
    settingsRef.current = { mirrored, overlayEnabled, debugLandmarks, frozen, lang };
    handlersRef.current = { onGesture, onFatalError, onSoftError };
    filterRef.current = filterId;
  }, [mirrored, overlayEnabled, debugLandmarks, frozen, lang, onGesture, onFatalError, onSoftError, filterId]);

  const emittedRef = useRef("");
  const candidateRef = useRef({ name: "", frames: 0 });
  const lastFireRef = useRef(new Map<string, number>());
  const maskErrorRef = useRef(false);

  // -- model loading ------------------------------------------------------ //
  useEffect(() => {
    if (!active) return;
    let cancelled = false;
    // `onProgress` fires for every stage, including the first one, so the
    // initial "loading" state comes from the engine itself.
    VisionEngine.create({
      onProgress: (progress) => {
        if (!cancelled) setStage(progress.stage);
      },
    })
      .then((created) => {
        if (cancelled) {
          created.close();
          return;
        }
        setEngine(created);
        setStage("ready");
      })
      .catch((error: unknown) => {
        if (cancelled) return;
        setModelError(error instanceof Error ? error.message : String(error));
        setStage(null);
      });
    return () => {
      cancelled = true;
    };
  }, [active, attempt]);

  // Landmarker instances hold WASM heaps and GPU buffers: always release them.
  useEffect(() => {
    if (!engine) return;
    return () => {
      engine.close();
    };
  }, [engine]);

  // -- filter switching --------------------------------------------------- //
  useEffect(() => {
    if (!rendererRef.current) return;
    rendererRef.current.setFilter(getFilter(filterId));
    classifierRef.current.reset();
  }, [filterId]);

  // -- the loop ----------------------------------------------------------- //
  useEffect(() => {
    if (!active || !engine) return;
    const canvas = filterCanvasRef.current;
    if (!canvas) return;

    let renderer: FilterRenderer;
    try {
      renderer = new FilterRenderer(canvas, {
        onError: (message) => handlersRef.current.onSoftError(message),
      });
    } catch (error) {
      const message =
        error instanceof WebGLUnavailableError
          ? error.message
          : error instanceof Error
            ? error.message
            : String(error);
      handlersRef.current.onFatalError(message);
      return;
    }
    rendererRef.current = renderer;
    renderer.setFilter(getFilter(filterRef.current));

    let raf = 0;
    let cancelled = false;

    const started = performance.now();
    let lastVideoTime = -1;
    let frameCount = 0;
    let fpsWindowStart = started;
    let fps = 0;
    let inferenceMs = 0;
    let lastStatsAt = 0;
    let frozenFrames = 0;
    let frozenTime = 0;
    let handsCount = 0;
    let faceDetected = false;
    let expressionBadge: OverlayBadge | null = null;
    let gestureBadge: OverlayBadge | null = null;
    let expressionSummary: ExpressionSummary | null = null;
    let gestureSummary: GestureSummary | null = null;

    const loop = (now: number) => {
      if (cancelled) return;
      raf = requestAnimationFrame(loop);

      const video = videoRef.current;
      const overlayCanvas = overlayCanvasRef.current;
      const renderer = rendererRef.current;
      if (!video || !overlayCanvas || !renderer) return;
      if (video.videoWidth === 0 || video.videoHeight === 0) return;

      const settings = settingsRef.current;
      const filter = getFilter(filterRef.current);

      // --- keep both canvases locked to the camera resolution ------------- //
      const resized = renderer.resize(video.videoWidth, video.videoHeight);
      if (resized || overlayCanvas.width !== renderer.width || overlayCanvas.height !== renderer.height) {
        overlayCanvas.width = renderer.width;
        overlayCanvas.height = renderer.height;
        faceSmootherRef.current.reset();
        for (const smoother of handSmoothersRef.current) smoother.reset();
      }
      if (renderer.width < 2 || renderer.height < 2) return;

      // --- fps ------------------------------------------------------------ //
      frameCount += 1;
      const elapsed = now - fpsWindowStart;
      if (elapsed >= 500) {
        fps = (frameCount * 1000) / elapsed;
        frameCount = 0;
        fpsWindowStart = now;
      }

      // A frozen frame keeps both the pixels and the shader clock still.
      let timeSeconds: number;
      if (settings.frozen) {
        if (frozenFrames === 0) frozenTime = (now - started) / 1000;
        frozenFrames += 1;
        timeSeconds = frozenTime;
      } else {
        frozenFrames = 0;
        timeSeconds = (now - started) / 1000;
      }

      const isNewFrame = video.currentTime !== lastVideoTime;
      if (isNewFrame) lastVideoTime = video.currentTime;

      if (!settings.frozen && isNewFrame) {
        renderer.uploadVideo(video);

        const needsMask = Boolean(filter.needsMask);
        if (needsMask && !engine.segmenterReady) {
          void engine.loadSegmenter().catch((error: unknown) => {
            if (maskErrorRef.current) return;
            maskErrorRef.current = true;
            handlersRef.current.onSoftError(
              `segmentation: ${error instanceof Error ? error.message : String(error)}`,
            );
          });
        }

        const frame = engine.detect(video, now, {
          face: true,
          hands: true,
          mask: needsMask && engine.segmenterReady,
        });
        inferenceMs = inferenceMs === 0 ? frame.inferenceMs : inferenceMs * 0.85 + frame.inferenceMs * 0.15;
        if (frame.mask) renderer.uploadMask(frame.mask.pixels, frame.mask.width, frame.mask.height);

        handsCount = frame.hands.length;
        faceDetected = Boolean(frame.faceLandmarks);
        facePointsRef.current = frame.faceLandmarks
          ? frame.faceLandmarks.map((landmark) => ({ x: landmark.x, y: landmark.y }))
          : null;
        handPointsRef.current = frame.hands.map((hand) => ({
          points: hand.landmarks.map((landmark) => ({ x: landmark.x, y: landmark.y })),
          handedness: hand.handedness,
        }));

        // --- expressions ------------------------------------------------- //
        const result = classifierRef.current.classify(frame.blendshapes);
        if (result.hasFace) {
          expressionSummary = { name: result.name, score: result.score, top: result.top };
          expressionBadge = {
            emoji: expressionEmoji(result.name),
            label: expressionLabel(result.name, settings.lang),
            detail: `${Math.round(result.score * 100)} %`,
            score: result.score,
          };
        } else {
          expressionSummary = null;
          expressionBadge = null;
        }

        // --- static gestures --------------------------------------------- //
        const matches = frame.hands.map((hand) => classifyGesture(hand));
        const best = matches.reduce<(typeof matches)[number] | null>(
          (winner, match) => (!winner || match.score > winner.score ? match : winner),
          null,
        );
        const bestName = best && best.name !== "none" ? best.name : "";
        if (best && bestName) {
          gestureSummary = {
            name: best.name,
            emoji: best.definition?.emoji ?? "🖐️",
            label:
              settings.lang === "es"
                ? (best.definition?.labelEs ?? best.name)
                : (best.definition?.label ?? best.name),
            score: best.score,
          };
          gestureBadge = {
            emoji: gestureSummary.emoji,
            label: gestureSummary.label,
            detail: `${Math.round(best.score * 100)} %`,
            score: best.score,
          };
        } else {
          gestureSummary = null;
          gestureBadge = null;
        }

        // Confirmation window: a single-frame misclassification never fires.
        const candidate = candidateRef.current;
        if (bestName === candidate.name) {
          candidate.frames += 1;
        } else {
          candidate.name = bestName;
          candidate.frames = bestName ? 1 : 0;
        }
        const confirmed = candidate.frames >= GESTURE_CONFIRM_FRAMES;
        const shouldEmit = Boolean(bestName) && confirmed && emittedRef.current !== bestName;
        emittedRef.current = bestName;
        if (shouldEmit && best) {
          const last = lastFireRef.current.get(bestName) ?? -Infinity;
          if (now - last >= GESTURE_COOLDOWN_MS) {
            lastFireRef.current.set(bestName, now);
            handlersRef.current.onGesture({
              name: best.name,
              emoji: best.definition?.emoji ?? "🖐️",
              label: best.definition?.label ?? best.name,
              labelEs: best.definition?.labelEs ?? best.name,
              score: best.score,
              action: best.definition?.action ?? "",
            });
          }
        }

        // --- dynamic gestures (swipes, waves, circles) -------------------- //
        const primary = frame.hands[0];
        const tracker = trackerRef.current;
        if (primary) {
          const centre = centreOf(primary, settings.mirrored);
          const dynamic = tracker.update(centre, now);
          if (dynamic) {
            gestureSummary = {
              name: dynamic.name,
              emoji: dynamic.emoji,
              label: settings.lang === "es" ? dynamic.labelEs : dynamic.label,
              score: dynamic.strength,
            };
            gestureBadge = {
              emoji: dynamic.emoji,
              label: gestureSummary.label,
              detail: `${Math.round(dynamic.strength * 100)} %`,
              score: dynamic.strength,
            };
            handlersRef.current.onGesture({
              name: dynamic.name,
              emoji: dynamic.emoji,
              label: dynamic.label,
              labelEs: dynamic.labelEs,
              score: dynamic.strength,
              action: dynamic.definition?.action ?? "",
            });
          }
        } else {
          tracker.update(null, now);
        }
      }

      // --- draw ----------------------------------------------------------- //
      renderer.render(timeSeconds, settings.mirrored);

      const context = overlayCanvas.getContext("2d");
      if (context) {
        if (settings.overlayEnabled) {
          const seconds = now / 1000;
          const rawFace = facePointsRef.current;
          const face = rawFace ? faceSmootherRef.current.apply(rawFace, seconds) : [];
          if (!rawFace) faceSmootherRef.current.reset();

          const rawHands = handPointsRef.current;
          const hands: HandObservation[] = rawHands.map((hand, index) => {
            const smoother = handSmoothersRef.current[index] ?? (handSmoothersRef.current[0]);
            const smoothed = smoother.apply(hand.points, seconds);
            return {
              handedness: hand.handedness,
              landmarks: smoothed.map((point) => ({ x: point.x, y: point.y })),
            };
          });

          drawOverlay({
            ctx: context,
            width: renderer.width,
            height: renderer.height,
            mirrored: settings.mirrored,
            face,
            hands,
            debug: settings.debugLandmarks,
            expression: expressionBadge,
            gesture: gestureBadge,
            fps,
            frozen: settings.frozen,
          });
        } else {
          context.clearRect(0, 0, renderer.width, renderer.height);
        }
      }

      // --- throttled HUD -------------------------------------------------- //
      if (now - lastStatsAt >= STATS_INTERVAL_MS) {
        lastStatsAt = now;
        setStats({
          fps,
          inferenceMs,
          hands: handsCount,
          faceDetected,
          expression: expressionSummary,
          gesture: gestureSummary,
        });
      }
    };

    raf = requestAnimationFrame(loop);
    return () => {
      cancelled = true;
      cancelAnimationFrame(raf);
      renderer.dispose();
      rendererRef.current = null;
    };
  }, [active, engine, videoRef, filterCanvasRef, overlayCanvasRef]);

  const captureSnapshot = useCallback(
    async (includeOverlay: boolean): Promise<Blob | null> => {
      const filterCanvas = filterCanvasRef.current;
      if (!filterCanvas || filterCanvas.width < 2) return null;
      const output = document.createElement("canvas");
      output.width = filterCanvas.width;
      output.height = filterCanvas.height;
      const context = output.getContext("2d");
      if (!context) return null;
      context.drawImage(filterCanvas, 0, 0);
      const overlayCanvas = overlayCanvasRef.current;
      if (includeOverlay && overlayCanvas && overlayCanvas.width === output.width) {
        context.drawImage(overlayCanvas, 0, 0);
      }
      return new Promise<Blob | null>((resolve) => {
        output.toBlob((blob) => resolve(blob), "image/png");
      });
    },
    [filterCanvasRef, overlayCanvasRef],
  );

  const retryModels = useCallback(() => {
    maskErrorRef.current = false;
    setModelError(null);
    setStage("wasm");
    setEngine((current) => {
      current?.close();
      return null;
    });
    setAttempt((value) => value + 1);
  }, []);

  return useMemo(
    () => ({
      stage,
      modelError,
      usingGpu: engine?.usingGpu ?? false,
      stats,
      retryModels,
      captureSnapshot,
    }),
    [engine, modelError, stage, stats, retryModels, captureSnapshot],
  );
}

/**
 * The centre of the hand in normalised coordinates, mirrored when the preview
 * is, so a swipe towards the right of the screen always reads as `swipe_right`.
 */
function centreOf(hand: HandObservation, mirrored: boolean): Point {
  let x = 0;
  let y = 0;
  for (const landmark of hand.landmarks) {
    x += landmark.x;
    y += landmark.y;
  }
  const count = Math.max(hand.landmarks.length, 1);
  const cx = x / count;
  return { x: mirrored ? 1 - cx : cx, y: y / count };
}

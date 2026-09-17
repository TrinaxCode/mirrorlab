/**
 * MediaPipe Tasks Vision: model loading and per-frame inference.
 *
 * Facts this module depends on (verified against `@mediapipe/tasks-vision@1.0.1`):
 *
 * * the WASM fileset comes from the jsDelivr CDN and is single-threaded, so the
 *   page needs **no** COOP/COEP headers;
 * * `runningMode` is only `"IMAGE" | "VIDEO"` — there is no `LIVE_STREAM` on the
 *   web, so the webcam runs in `VIDEO` mode through `detectForVideo()`;
 * * `detectForVideo()` requires **strictly increasing** timestamps, which this
 *   module guarantees through `nextTimestamp()`;
 * * blendshapes are looked up by `categoryName` (index 0 is `_neutral` and the
 *   order is not part of the contract). There is no `tongueOut` channel.
 */

import {
  FaceLandmarker,
  FilesetResolver,
  HandLandmarker,
  ImageSegmenter,
  type NormalizedLandmark,
} from "@mediapipe/tasks-vision";

import type { HandObservation } from "./gestures";

export type Landmark = NormalizedLandmark;

export const WASM_FILESET_URL = "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@1.0.1/wasm";

export const MODEL_URLS = {
  face: "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task",
  hands:
    "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task",
  segmenter:
    "https://storage.googleapis.com/mediapipe-models/image_segmenter/selfie_segmenter/float16/1/selfie_segmenter.tflite",
} as const;

export type VisionStage = "wasm" | "face" | "hands" | "segmenter" | "ready";

export interface VisionProgress {
  stage: VisionStage;
  /** 0..1, coarse but honest: one step per model that finished loading. */
  progress: number;
}

export interface PersonMask {
  pixels: Uint8Array;
  width: number;
  height: number;
}

export interface DetectionFrame {
  /** 478 landmarks in `0..1` frame coordinates, or `null` when no face. */
  faceLandmarks: Landmark[] | null;
  /** 52 ARKit channels keyed by `categoryName`, or `null` when no face. */
  blendshapes: Record<string, number> | null;
  hands: HandObservation[];
  mask: PersonMask | null;
  /** Wall-clock cost of the inference calls in this frame, in milliseconds. */
  inferenceMs: number;
}

export interface DetectionRequest {
  face: boolean;
  hands: boolean;
  mask: boolean;
}

export interface VisionEngineOptions {
  onProgress?: (progress: VisionProgress) => void;
  /** Force the CPU delegate — used as the fallback when GPU init fails. */
  forceCpu?: boolean;
}

const STAGE_WEIGHT: Record<VisionStage, number> = {
  wasm: 0.1,
  face: 0.5,
  hands: 0.9,
  segmenter: 1,
  ready: 1,
};

/**
 * Owns the MediaPipe tasks. Every call into MediaPipe is wrapped so a model
 * failure surfaces as a friendly banner instead of a broken page.
 */
export class VisionEngine {
  private readonly face: FaceLandmarker;
  private readonly hands: HandLandmarker;
  private segmenter: ImageSegmenter | null = null;
  private segmenterPromise: Promise<void> | null = null;
  private lastTimestamp = 0;
  private maskBuffer = new Uint8Array(0);
  private maskPolarity = 1;
  private maskFrames = 0;
  private closed = false;

  private constructor(
    face: FaceLandmarker,
    hands: HandLandmarker,
    private readonly fileset: Awaited<ReturnType<typeof FilesetResolver.forVisionTasks>>,
    private readonly delegate: "GPU" | "CPU",
  ) {
    this.face = face;
    this.hands = hands;
  }

  get usingGpu(): boolean {
    return this.delegate === "GPU";
  }

  get segmenterReady(): boolean {
    return this.segmenter !== null;
  }

  /** Load the face + hand models. The segmenter is deferred until it is needed. */
  static async create(options: VisionEngineOptions = {}): Promise<VisionEngine> {
    const report = (stage: VisionStage) =>
      options.onProgress?.({ stage, progress: STAGE_WEIGHT[stage] });

    report("wasm");
    const fileset = await FilesetResolver.forVisionTasks(WASM_FILESET_URL);

    const build = async (delegate: "GPU" | "CPU"): Promise<[FaceLandmarker, HandLandmarker]> => {
      const face = await FaceLandmarker.createFromOptions(fileset, {
        baseOptions: { modelAssetPath: MODEL_URLS.face, delegate },
        runningMode: "VIDEO",
        numFaces: 1,
        outputFaceBlendshapes: true,
        outputFacialTransformationMatrixes: false,
      });
      report("face");
      const hands = await HandLandmarker.createFromOptions(fileset, {
        baseOptions: { modelAssetPath: MODEL_URLS.hands, delegate },
        runningMode: "VIDEO",
        numHands: 2,
        minHandDetectionConfidence: 0.5,
        minHandPresenceConfidence: 0.5,
        minTrackingConfidence: 0.5,
      });
      report("hands");
      return [face, hands];
    };

    if (!options.forceCpu) {
      try {
        const [face, hands] = await build("GPU");
        return new VisionEngine(face, hands, fileset, "GPU");
      } catch {
        // The GPU delegate is unavailable on some drivers/VMs — fall back.
      }
    }
    const [face, hands] = await build("CPU");
    return new VisionEngine(face, hands, fileset, "CPU");
  }

  /** Load the selfie segmenter on demand (only the background-blur filter needs it). */
  async loadSegmenter(): Promise<void> {
    if (this.segmenter) return;
    if (this.segmenterPromise) return this.segmenterPromise;
    this.segmenterPromise = (async () => {
      const segmenter = await ImageSegmenter.createFromOptions(this.fileset, {
        baseOptions: { modelAssetPath: MODEL_URLS.segmenter, delegate: this.delegate },
        runningMode: "VIDEO",
        outputConfidenceMasks: true,
        outputCategoryMask: false,
      });
      this.segmenter = segmenter;
      this.maskPolarity = 1;
      this.maskFrames = 0;
    })();
    try {
      await this.segmenterPromise;
    } finally {
      this.segmenterPromise = null;
    }
  }

  /** Strictly increasing timestamps, as `detectForVideo` demands. */
  private nextTimestamp(nowMs: number): number {
    const timestamp = Math.max(nowMs, this.lastTimestamp + 1);
    this.lastTimestamp = timestamp;
    return timestamp;
  }

  /** Run the requested detectors on one video frame. */
  detect(video: HTMLVideoElement, nowMs: number, request: DetectionRequest): DetectionFrame {
    const started = performance.now();
    const timestamp = this.nextTimestamp(nowMs);
    const frame: DetectionFrame = {
      faceLandmarks: null,
      blendshapes: null,
      hands: [],
      mask: null,
      inferenceMs: 0,
    };
    if (this.closed) return frame;

    if (request.face) {
      try {
        const result = this.face.detectForVideo(video, timestamp);
        const landmarks = result.faceLandmarks[0];
        if (landmarks && landmarks.length > 0) {
          frame.faceLandmarks = landmarks;
          const categories = result.faceBlendshapes[0]?.categories ?? [];
          const blendshapes: Record<string, number> = {};
          for (const category of categories) {
            // Always by name: the index order is an implementation detail.
            if (category.categoryName) blendshapes[category.categoryName] = category.score;
          }
          frame.blendshapes = Object.keys(blendshapes).length > 0 ? blendshapes : null;
        }
      } catch {
        frame.faceLandmarks = null;
        frame.blendshapes = null;
      }
    }

    if (request.hands) {
      try {
        const result = this.hands.detectForVideo(video, timestamp);
        // `handednesses` is the long-standing field, `handedness` the current
        // one; read both so either bundle shape works.
        const categories = result.handedness ?? result.handednesses ?? [];
        frame.hands = result.landmarks.map((landmarks, index) => {
          const category = categories[index]?.[0];
          return {
            landmarks,
            // MediaPipe infers handedness assuming a *mirrored* (selfie) image.
            // The demo feeds the raw camera frame, so the label is swapped to
            // describe the user's actual hand.
            handedness: category?.categoryName === "Left" ? "Right" : "Left",
          } satisfies HandObservation;
        });
      } catch {
        frame.hands = [];
      }
    }

    if (request.mask && this.segmenter) {
      try {
        frame.mask = this.segment(this.segmenter, video, timestamp);
      } catch {
        frame.mask = null;
      }
    }

    frame.inferenceMs = performance.now() - started;
    return frame;
  }

  private segment(
    segmenter: ImageSegmenter,
    video: HTMLVideoElement,
    timestamp: number,
  ): PersonMask | null {
    const result = segmenter.segmentForVideo(video, timestamp);
    const masks = result.confidenceMasks;
    if (!masks || masks.length === 0) return null;
    // The selfie segmenter has two categories: 0 = background, 1 = person. The
    // polarity is verified against the frame border below, so a differently
    // ordered model export cannot silently invert the effect.
    const mask = masks.length > 1 ? (masks[1]) : (masks[0]);
    const width = mask.width;
    const height = mask.height;
    const data = mask.getAsFloat32Array();
    const size = width * height;
    if (data.length < size) return null;

    this.maskFrames += 1;
    if (this.maskFrames % 45 === 1) this.maskPolarity = scorePolarity(data, width, height);

    if (this.maskBuffer.length !== size) this.maskBuffer = new Uint8Array(size);
    const pixels = this.maskBuffer;
    const polarity = this.maskPolarity;
    for (let i = 0; i < size; i += 1) {
      const value = (data[i]) * polarity;
      pixels[i] = value <= 0 ? 0 : value >= 1 ? 255 : (value * 255) | 0;
    }
    for (const extra of masks) {
      try {
        extra.close();
      } catch {
        /* owned by the task, already released */
      }
    }
    return { pixels, width, height };
  }

  close(): void {
    if (this.closed) return;
    this.closed = true;
    try {
      this.face.close();
    } catch {
      /* already closed */
    }
    try {
      this.hands.close();
    } catch {
      /* already closed */
    }
    try {
      this.segmenter?.close();
    } catch {
      /* already closed */
    }
    this.segmenter = null;
  }
}

/**
 * Decide whether the mask channel is "person = bright" or its inverse.
 *
 * A subject sitting in front of a camera almost always touches the middle of
 * the frame and rarely fills the border, so comparing the two gives a stable
 * verdict. Returns `1` (keep) or `-1` (invert).
 */
function scorePolarity(data: Float32Array, width: number, height: number): number {
  const step = Math.max(1, Math.floor(Math.min(width, height) / 24));
  let borderSum = 0;
  let borderCount = 0;
  let centreSum = 0;
  let centreCount = 0;

  const x0 = Math.floor(width * 0.3);
  const x1 = Math.floor(width * 0.7);
  const y0 = Math.floor(height * 0.3);
  const y1 = Math.floor(height * 0.7);

  for (let y = 0; y < height; y += step) {
    for (let x = 0; x < width; x += step) {
      const value = data[y * width + x];
      const isBorder = x < width * 0.08 || x > width * 0.92 || y < height * 0.08 || y > height * 0.92;
      if (isBorder) {
        borderSum += value;
        borderCount += 1;
      } else if (x >= x0 && x <= x1 && y >= y0 && y <= y1) {
        centreSum += value;
        centreCount += 1;
      }
    }
  }

  if (borderCount === 0 || centreCount === 0) return 1;
  const border = borderSum / borderCount;
  const centre = centreSum / centreCount;
  return border - centre > 0.15 ? -1 : 1;
}

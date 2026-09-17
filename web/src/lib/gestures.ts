/**
 * Hand pose analysis and gesture recognition.
 *
 * Direct port of `mirrorlab/gestures.py`. The classifier is **geometric and
 * explainable**: it derives a `HandPose` (which fingers are extended, how much
 * they curl, how far the thumb is from the index tip, how the hand is rotated)
 * and then matches that pose against declarative gesture definitions.
 *
 * Rule-based beats a trained classifier here because it needs no extra model
 * download, runs in microseconds on one CPU core, is invariant to hand size and
 * distance (every measurement is normalised by `handScale`), and can be
 * extended by users in a handful of lines.
 */

export interface Point2 {
  x: number;
  y: number;
}

export type Handedness = "Left" | "Right";
export type FingerName = "thumb" | "index" | "middle" | "ring" | "pinky";

export const FINGER_NAMES: readonly FingerName[] = ["thumb", "index", "middle", "ring", "pinky"];

// MediaPipe hand landmark indices.
export const WRIST = 0;
export const THUMB_CMC = 1;
export const THUMB_MCP = 2;
export const THUMB_IP = 3;
export const THUMB_TIP = 4;
export const INDEX_MCP = 5;
export const INDEX_PIP = 6;
export const INDEX_DIP = 7;
export const INDEX_TIP = 8;
export const MIDDLE_MCP = 9;
export const MIDDLE_PIP = 10;
export const MIDDLE_DIP = 11;
export const MIDDLE_TIP = 12;
export const RING_MCP = 13;
export const RING_PIP = 14;
export const RING_DIP = 15;
export const RING_TIP = 16;
export const PINKY_MCP = 17;
export const PINKY_PIP = 18;
export const PINKY_DIP = 19;
export const PINKY_TIP = 20;

/** `(mcp, pip, dip, tip)` joint chains for the four long fingers. */
export const FINGER_JOINTS: Record<Exclude<FingerName, "thumb">, readonly [number, number, number, number]> = {
  index: [INDEX_MCP, INDEX_PIP, INDEX_DIP, INDEX_TIP],
  middle: [MIDDLE_MCP, MIDDLE_PIP, MIDDLE_DIP, MIDDLE_TIP],
  ring: [RING_MCP, RING_PIP, RING_DIP, RING_TIP],
  pinky: [PINKY_MCP, PINKY_PIP, PINKY_DIP, PINKY_TIP],
};

/** A finger counts as extended below this curl score. */
export const EXTENDED_CURL = 0.45;
/** A finger counts as folded above this curl score. */
export const FOLDED_CURL = 0.55;

export const clamp = (value: number, low = 0, high = 1): number =>
  value < low ? low : value > high ? high : value;

// --------------------------------------------------------------------------- //
// Geometry helpers (ported from `mirrorlab/utils/geometry.py`)
// --------------------------------------------------------------------------- //
export function distance(a: Point2, b: Point2): number {
  return Math.hypot(a.x - b.x, a.y - b.y);
}

/** Interior angle at `b` formed by `a-b-c`, in degrees `[0, 180]`. */
export function angle(a: Point2, b: Point2, c: Point2): number {
  const bax = a.x - b.x;
  const bay = a.y - b.y;
  const bcx = c.x - b.x;
  const bcy = c.y - b.y;
  const na = Math.hypot(bax, bay);
  const nc = Math.hypot(bcx, bcy);
  if (na < 1e-9 || nc < 1e-9) return 180;
  const cosine = (bax * bcx + bay * bcy) / (na * nc);
  return (Math.acos(Math.max(-1, Math.min(1, cosine))) * 180) / Math.PI;
}

/**
 * A rotation-invariant size estimate: the mean distance from the wrist to the
 * four finger MCP joints. Dividing every measurement by this is the single most
 * important trick for gesture recognition that works at any distance.
 */
export function handScale(points: readonly Point2[]): number {
  if (points.length <= PINKY_MCP) return 1;
  const wrist = points[WRIST];
  const indices = [INDEX_MCP, MIDDLE_MCP, RING_MCP, PINKY_MCP];
  let total = 0;
  for (const index of indices) total += distance(points[index], wrist);
  const scale = total / indices.length;
  return scale > 1e-6 ? scale : 1e-6;
}

/**
 * How curled a finger is, as a normalised `0..1` score. `0` is perfectly
 * straight, `1` fully folded. The mean of two complementary signals:
 *
 * * the joint angle at the PIP, mapped from 180° (straight) to 60° (folded);
 * * how far the tip sits from the wrist relative to the MCP, normalised by hand
 *   size.
 *
 * Combining both makes the classifier resilient to noisy landmarks and to hands
 * that are rotated or tilted towards the camera.
 */
export function fingerCurl(
  points: readonly Point2[],
  mcp: number,
  pip: number,
  dip: number,
  tip: number,
): number {
  if (points.length <= Math.max(mcp, pip, dip, tip)) return 0;
  const straightness = angle(points[mcp], points[pip], points[dip]);
  const angleScore = clamp((180 - straightness) / 120);

  const scale = handScale(points);
  const wrist = points[WRIST];
  const reach = distance(wrist, points[tip]) / scale;
  const mcpReach = distance(wrist, points[mcp]) / scale;
  // A straight finger reaches ~2.0 hand-scales from the wrist, a folded one ~1.0.
  const reachScore = clamp(1.6 - (reach - mcpReach));
  return clamp(0.65 * angleScore + 0.35 * reachScore);
}

function meanPairwiseSpread(points: readonly Point2[]): number {
  if (points.length < 2) return 0;
  let total = 0;
  let count = 0;
  for (let i = 0; i < points.length; i += 1) {
    for (let j = i + 1; j < points.length; j += 1) {
      total += distance(points[i], points[j]);
      count += 1;
    }
  }
  return count > 0 ? total / count : 0;
}

function meanAdjacentGap(points: readonly Point2[]): number {
  if (points.length < 2) return 0;
  let total = 0;
  for (let i = 0; i < points.length - 1; i += 1) {
    total += distance(points[i], points[i + 1]);
  }
  return total / (points.length - 1);
}

// --------------------------------------------------------------------------- //
// Pose analysis
// --------------------------------------------------------------------------- //
export interface FingerState {
  name: FingerName;
  extended: boolean;
  curl: number;
  pipAngle: number;
  tip: Point2;
  reachRatio: number;
}

export interface HandPose {
  handedness: Handedness;
  fingers: Record<FingerName, FingerState>;
  landmarks: readonly Point2[];
  scale: number;
  center: Point2;
  pinchRatio: number;
  thumbIndexGap: number;
  spread: number;
  palmFacingCamera: boolean;
  rotationDeg: number;
  fingersTogether: number;
  okRingRatio: number;
}

/** Anything with normalised `x`/`y` — MediaPipe landmarks satisfy this. */
export interface LandmarkLike {
  x: number;
  y: number;
  z?: number;
}

export interface HandObservation {
  /** 21 normalised landmarks, in `0..1` frame coordinates. */
  landmarks: readonly LandmarkLike[];
  handedness: Handedness;
}

const isExtended = (pose: HandPose, finger: FingerName): boolean => pose.fingers[finger].extended;
const isFolded = (pose: HandPose, finger: FingerName): boolean => !pose.fingers[finger].extended;

export function extendedCount(pose: HandPose): number {
  return FINGER_NAMES.filter((name) => isExtended(pose, name)).length;
}

/** Turn raw landmarks into a rich, backend-independent `HandPose`. */
export function analyzeHand(hand: HandObservation): HandPose {
  const points: Point2[] = hand.landmarks.map((landmark) => ({ x: landmark.x, y: landmark.y }));
  const scale = handScale(points);
  const wrist = points[WRIST];

  const fingers = {} as Record<FingerName, FingerState>;

  // --- four long fingers -------------------------------------------------- //
  for (const name of ["index", "middle", "ring", "pinky"] as const) {
    const [mcp, pip, dip, tip] = FINGER_JOINTS[name];
    const curl = fingerCurl(points, mcp, pip, dip, tip);
    const pipAngle = angle(points[mcp], points[pip], points[dip]);
    const reach = distance(wrist, points[tip]) / scale;
    const baseline = distance(wrist, points[pip]) / scale;
    const reachRatio = baseline > 1e-6 ? reach / baseline : 1;
    fingers[name] = {
      name,
      extended: curl < EXTENDED_CURL && reachRatio > 1.02,
      curl,
      pipAngle,
      tip: { ...(points[tip]) },
      reachRatio,
    };
  }

  // --- thumb: its own geometry, since it folds across the palm ------------- //
  const thumbTip = points[THUMB_TIP];
  const thumbIp = points[THUMB_IP];
  const thumbMcp = points[THUMB_MCP];
  const pinkyMcp = points[PINKY_MCP];
  const indexMcp = points[INDEX_MCP];

  // A tucked thumb sits close to the index MCP; an extended one swings away.
  const thumbAway = distance(thumbTip, indexMcp) / scale;
  const thumbAngle = angle(thumbMcp, thumbIp, thumbTip);
  const thumbCurl = clamp(
    0.6 * clamp((1.05 - thumbAway) / 0.7) + 0.4 * clamp((150 - thumbAngle) / 90),
  );
  fingers.thumb = {
    name: "thumb",
    extended: thumbCurl < 0.5 && thumbAway > 0.62,
    curl: thumbCurl,
    pipAngle: thumbAngle,
    tip: { ...thumbTip },
    reachRatio: thumbAway,
  };

  // --- aggregate features ------------------------------------------------- //
  const thumbIndexGap = distance(thumbTip, points[INDEX_TIP]) / scale;

  const fingertips = (["index", "middle", "ring", "pinky"] as const).map((name) => fingers[name].tip);
  const spread = meanPairwiseSpread(fingertips) / scale;
  const middleTip = points[MIDDLE_TIP];
  const okRingRatio = distance(thumbTip, middleTip) / scale;

  // Palm orientation: the sign of the 2-D cross product tells us which side of
  // the palm plane faces the camera.
  const v1x = indexMcp.x - wrist.x;
  const v1y = indexMcp.y - wrist.y;
  const v2x = pinkyMcp.x - wrist.x;
  const v2y = pinkyMcp.y - wrist.y;
  const crossZ = v1x * v2y - v1y * v2x;
  const palmFacing = hand.handedness === "Right" ? crossZ < 0 : crossZ > 0;

  const rotation = (Math.atan2(indexMcp.y - pinkyMcp.y, indexMcp.x - pinkyMcp.x) * 180) / Math.PI;
  const fingersTogether = meanAdjacentGap(fingertips) / scale;

  let cx = 0;
  let cy = 0;
  for (const point of points) {
    cx += point.x;
    cy += point.y;
  }
  const count = Math.max(points.length, 1);

  return {
    handedness: hand.handedness,
    fingers,
    landmarks: points,
    scale,
    center: { x: cx / count, y: cy / count },
    pinchRatio: thumbIndexGap,
    thumbIndexGap,
    spread,
    palmFacingCamera: palmFacing,
    rotationDeg: rotation,
    fingersTogether,
    okRingRatio,
  };
}

// --------------------------------------------------------------------------- //
// Matchers
// --------------------------------------------------------------------------- //
export type GestureMatcher = (pose: HandPose) => number;

/** Rewards exactly this extended/folded pattern. */
function pattern(extended: readonly FingerName[], folded: readonly FingerName[]): GestureMatcher {
  const total = extended.length + folded.length;
  return (pose) => {
    if (total === 0) return 0;
    let hits = 0;
    for (const name of extended) if (isExtended(pose, name)) hits += 1;
    for (const name of folded) if (isFolded(pose, name)) hits += 1;
    return hits / total;
  };
}

/** Average certainty of a finger-state constraint, used to sharpen scores. */
function confidence(pose: HandPose, names: readonly FingerName[], wantedExtended: boolean): number {
  if (names.length === 0) return 0;
  let total = 0;
  for (const name of names) {
    const state = pose.fingers[name];
    total += wantedExtended
      ? clamp((EXTENDED_CURL - state.curl) / EXTENDED_CURL)
      : clamp((state.curl - FOLDED_CURL) / (1 - FOLDED_CURL));
  }
  return total / names.length;
}

const matchFist: GestureMatcher = (pose) => {
  if (extendedCount(pose) > 0) return 0;
  return 0.55 + 0.45 * confidence(pose, FINGER_NAMES, false);
};

const matchOpenPalm: GestureMatcher = (pose) => {
  if (extendedCount(pose) < 5) return 0;
  const spread = clamp((pose.spread - 0.55) / 0.55);
  return 0.65 + 0.35 * spread;
};

const matchThumbsUp: GestureMatcher = (pose) => {
  if (!isExtended(pose, "thumb")) return 0;
  if (!(["index", "middle", "ring", "pinky"] as const).every((name) => isFolded(pose, name))) return 0;
  // The thumb tip must sit clearly above (smaller y) the rest of the hand.
  const thumbY = pose.fingers.thumb.tip.y;
  const othersY =
    (["index", "middle", "ring", "pinky"] as const).reduce((sum, name) => sum + pose.fingers[name].tip.y, 0) / 4;
  const lift = clamp((othersY - thumbY) / (0.9 * pose.scale));
  return 0.5 * confidence(pose, ["index", "middle", "ring", "pinky"], false) + 0.5 * lift;
};

const matchThumbsDown: GestureMatcher = (pose) => {
  if (!isExtended(pose, "thumb")) return 0;
  if (!(["index", "middle", "ring", "pinky"] as const).every((name) => isFolded(pose, name))) return 0;
  const thumbY = pose.fingers.thumb.tip.y;
  const othersY =
    (["index", "middle", "ring", "pinky"] as const).reduce((sum, name) => sum + pose.fingers[name].tip.y, 0) / 4;
  const drop = clamp((thumbY - othersY) / (0.9 * pose.scale));
  return 0.5 * confidence(pose, ["index", "middle", "ring", "pinky"], false) + 0.5 * drop;
};

const matchOk: GestureMatcher = (pose) => {
  const touch = clamp((0.55 - pose.pinchRatio) / 0.3);
  const others =
    (Number(isExtended(pose, "middle")) + Number(isExtended(pose, "ring")) + Number(isExtended(pose, "pinky"))) / 3;
  return 0.65 * touch + 0.35 * others;
};

const matchPinch: GestureMatcher = (pose) => clamp((0.45 - pose.pinchRatio) / 0.28);

const matchSpock: GestureMatcher = (pose) => {
  if (!(["index", "middle", "ring", "pinky"] as const).every((name) => isExtended(pose, name))) return 0;
  if (isExtended(pose, "thumb")) return 0;
  const tips = pose.fingers;
  const innerGap = distance(tips.index.tip, tips.middle.tip) / pose.scale;
  const outerGap = distance(tips.ring.tip, tips.pinky.tip) / pose.scale;
  const middleGap = distance(tips.middle.tip, tips.ring.tip) / pose.scale;
  // Vulcan salute: the middle/ring gap is much wider than the other two.
  return clamp((middleGap - Math.max(innerGap, outerGap)) / 0.45);
};

const matchClaw: GestureMatcher = (pose) => {
  const partial = (["index", "middle", "ring", "pinky"] as const).filter((name) => {
    const curl = pose.fingers[name].curl;
    return EXTENDED_CURL * 0.9 < curl && curl < 0.95;
  });
  return partial.length >= 3 ? (partial.length / 4) * 0.9 : 0;
};

const matchGun: GestureMatcher = (pose) => {
  if (!(isExtended(pose, "thumb") && isExtended(pose, "index"))) return 0;
  if (!(["middle", "ring", "pinky"] as const).every((name) => isFolded(pose, name))) return 0;
  return 0.6 + 0.4 * confidence(pose, ["middle", "ring", "pinky"], false);
};

const matchCallMe: GestureMatcher = (pose) => {
  if (!(isExtended(pose, "thumb") && isExtended(pose, "pinky"))) return 0;
  if (!(["index", "middle", "ring"] as const).every((name) => isFolded(pose, name))) return 0;
  return 0.6 + 0.4 * confidence(pose, ["index", "middle", "ring"], false);
};

// --------------------------------------------------------------------------- //
// Registry
// --------------------------------------------------------------------------- //
export type GestureCategory = "count" | "symbol" | "static" | "dynamic";

/** Actions the UI knows how to perform; empty means "detected but inert". */
export type GestureAction =
  | "next_filter"
  | "prev_filter"
  | "snapshot"
  | "toggle_overlay"
  | "freeze"
  | "toggle_hud"
  | "toggle_glitch";

export interface GestureDefinition {
  name: string;
  label: string;
  labelEs: string;
  emoji: string;
  matcher: GestureMatcher;
  threshold: number;
  category: GestureCategory;
  description: string;
  descriptionEs: string;
  action: GestureAction | "";
  actionLabel: string;
  actionLabelEs: string;
}

const inert = {
  action: "" as const,
  actionLabel: "Shown in the HUD",
  actionLabelEs: "Se muestra en el HUD",
};

/**
 * Gesture registry.
 *
 * The rules are a one-to-one port of `mirrorlab/gestures.py`; only the *order*
 * differs. Python registers the generic finger-count patterns first, which makes
 * the rarer shapes unreachable: `spock` can never beat `four` because both score
 * a perfect 1.0 and the earlier entry wins ties. Listing the symbol gestures
 * before the count patterns restores them without touching a single matcher or
 * threshold.
 */
export const GESTURES: readonly GestureDefinition[] = [
  {
    name: "fist",
    label: "Fist",
    labelEs: "Puño",
    emoji: "✊",
    matcher: matchFist,
    threshold: 0.55,
    category: "count",
    description: "All fingers folded.",
    descriptionEs: "Todos los dedos doblados.",
    action: "freeze",
    actionLabel: "Freezes / resumes the frame",
    actionLabelEs: "Congela o reanuda la imagen",
  },
  {
    name: "open_palm",
    label: "Open palm",
    labelEs: "Palma abierta",
    emoji: "🖐️",
    matcher: matchOpenPalm,
    threshold: 0.6,
    category: "count",
    description: "Five extended fingers.",
    descriptionEs: "Cinco dedos extendidos.",
    ...inert,
  },
  {
    name: "thumbs_up",
    label: "Thumbs up",
    labelEs: "Pulgar arriba",
    emoji: "👍",
    matcher: matchThumbsUp,
    threshold: 0.6,
    category: "symbol",
    description: "Thumb up, fist closed.",
    descriptionEs: "Pulgar arriba con el puño cerrado.",
    action: "snapshot",
    actionLabel: "Saves a PNG snapshot",
    actionLabelEs: "Guarda una captura PNG",
  },
  {
    name: "thumbs_down",
    label: "Thumbs down",
    labelEs: "Pulgar abajo",
    emoji: "👎",
    matcher: matchThumbsDown,
    threshold: 0.6,
    category: "symbol",
    description: "Thumb down, fist closed.",
    descriptionEs: "Pulgar abajo con el puño cerrado.",
    ...inert,
  },
  {
    name: "ok",
    label: "OK sign",
    labelEs: "Señal OK",
    emoji: "👌",
    matcher: matchOk,
    threshold: 0.62,
    category: "symbol",
    description: "Thumb and index tips touching, other fingers up.",
    descriptionEs: "Puntas de pulgar e índice unidas, el resto extendido.",
    action: "toggle_overlay",
    actionLabel: "Toggles the overlay",
    actionLabelEs: "Muestra u oculta la superposición",
  },
  {
    name: "pinch",
    label: "Pinch",
    labelEs: "Pellizco",
    emoji: "🤏",
    matcher: matchPinch,
    threshold: 0.6,
    category: "symbol",
    description: "Thumb and index close together.",
    descriptionEs: "Pulgar e índice muy juntos.",
    ...inert,
  },
  {
    name: "rock",
    label: "Rock",
    labelEs: "Rock",
    emoji: "🤘",
    // The thumb is part of the shape: without this constraint `rock` would also
    // match the ILY sign and, being registered first, shadow it.
    matcher: pattern(["index", "pinky"], ["middle", "ring", "thumb"]),
    threshold: 0.75,
    category: "symbol",
    description: "Index and pinky up.",
    descriptionEs: "Índice y meñique extendidos.",
    action: "toggle_glitch",
    actionLabel: "Toggles the glitch filter",
    actionLabelEs: "Activa o desactiva el filtro glitch",
  },
  {
    name: "call_me",
    label: "Call me",
    labelEs: "Llamada",
    emoji: "🤙",
    matcher: matchCallMe,
    threshold: 0.7,
    category: "symbol",
    description: "Thumb and pinky up — “hang loose”.",
    descriptionEs: "Pulgar y meñique extendidos, estilo “hang loose”.",
    ...inert,
  },
  {
    name: "gun",
    label: "Gun",
    labelEs: "Pistola",
    emoji: "🔫",
    matcher: matchGun,
    threshold: 0.68,
    category: "symbol",
    description: "Thumb and index out, rest folded.",
    descriptionEs: "Pulgar e índice extendidos, el resto doblado.",
    ...inert,
  },
  {
    name: "ily",
    label: "I love you",
    labelEs: "Te quiero",
    emoji: "🤟",
    matcher: pattern(["thumb", "index", "pinky"], ["middle", "ring"]),
    threshold: 0.72,
    category: "symbol",
    description: "ASL sign for “I love you”.",
    descriptionEs: "Seña ASL para “te quiero”.",
    ...inert,
  },
  {
    name: "spock",
    label: "Vulcan salute",
    labelEs: "Saludo vulcano",
    emoji: "🖖",
    matcher: matchSpock,
    threshold: 0.55,
    category: "symbol",
    description: "Live long and prosper.",
    descriptionEs: "Larga vida y prosperidad.",
    ...inert,
  },
  {
    name: "pointing",
    label: "Pointing",
    labelEs: "Señalando",
    emoji: "☝️",
    matcher: pattern(["index"], ["middle", "ring", "pinky"]),
    threshold: 0.75,
    category: "count",
    description: "Index up, rest folded.",
    descriptionEs: "Índice arriba y el resto doblados.",
    ...inert,
  },
  {
    name: "peace",
    label: "Peace",
    labelEs: "Victoria",
    emoji: "✌️",
    matcher: pattern(["index", "middle"], ["ring", "pinky"]),
    threshold: 0.7,
    category: "count",
    description: "Index and middle up.",
    descriptionEs: "Índice y corazón extendidos.",
    action: "next_filter",
    actionLabel: "Next filter",
    actionLabelEs: "Siguiente filtro",
  },
  {
    name: "three",
    label: "Three",
    labelEs: "Tres",
    emoji: "3️⃣",
    matcher: pattern(["index", "middle", "ring"], ["pinky", "thumb"]),
    threshold: 0.7,
    category: "count",
    description: "Three fingers up.",
    descriptionEs: "Tres dedos extendidos.",
    ...inert,
  },
  {
    name: "four",
    label: "Four",
    labelEs: "Cuatro",
    emoji: "4️⃣",
    matcher: pattern(["index", "middle", "ring", "pinky"], ["thumb"]),
    threshold: 0.72,
    category: "count",
    description: "Four fingers up, thumb folded.",
    descriptionEs: "Cuatro dedos extendidos y el pulgar doblado.",
    ...inert,
  },
  {
    name: "one",
    label: "One",
    labelEs: "Uno",
    emoji: "1️⃣",
    matcher: pattern(["thumb"], ["index", "middle", "ring", "pinky"]),
    threshold: 0.75,
    category: "count",
    description: "Only the thumb out.",
    descriptionEs: "Solo el pulgar extendido.",
    ...inert,
  },
  {
    name: "six",
    label: "Six",
    labelEs: "Seis",
    emoji: "6️⃣",
    matcher: pattern(["thumb", "index"], ["middle", "ring", "pinky"]),
    threshold: 0.72,
    category: "count",
    description: "Thumb and index out — also reads as “L”.",
    descriptionEs: "Pulgar e índice extendidos, también es la “L”.",
    ...inert,
  },
  {
    name: "seven",
    label: "Seven",
    labelEs: "Siete",
    emoji: "7️⃣",
    matcher: pattern(["thumb", "index", "middle"], ["ring", "pinky"]),
    threshold: 0.72,
    category: "count",
    description: "Thumb, index and middle out.",
    descriptionEs: "Pulgar, índice y corazón extendidos.",
    ...inert,
  },
  {
    name: "eight",
    label: "Eight",
    labelEs: "Ocho",
    emoji: "8️⃣",
    matcher: pattern(["thumb", "index", "middle", "ring"], ["pinky"]),
    threshold: 0.72,
    category: "count",
    description: "Four fingers plus thumb.",
    descriptionEs: "Cuatro dedos más el pulgar.",
    ...inert,
  },
  {
    name: "claw",
    label: "Claw",
    labelEs: "Garra",
    emoji: "🫳",
    matcher: matchClaw,
    threshold: 0.6,
    category: "count",
    description: "Partially curled fingers — the “grab” pose.",
    descriptionEs: "Dedos parcialmente curvados, la pose de “agarrar”.",
    ...inert,
  },
];

/** Fast lookup by canonical name. */
export const GESTURE_BY_NAME: ReadonlyMap<string, GestureDefinition> = new Map(
  GESTURES.map((definition) => [definition.name, definition]),
);

/** Dynamic gestures detected from the trajectory of the hand centre. */
export const DYNAMIC_GESTURES: readonly GestureDefinition[] = [
  {
    name: "swipe_left",
    label: "Swipe left",
    labelEs: "Deslizar izquierda",
    emoji: "⬅️",
    matcher: () => 0,
    threshold: 0,
    category: "dynamic",
    description: "Fast straight displacement towards the left of the screen.",
    descriptionEs: "Desplazamiento rápido y recto hacia la izquierda de la pantalla.",
    action: "prev_filter",
    actionLabel: "Previous filter",
    actionLabelEs: "Filtro anterior",
  },
  {
    name: "swipe_right",
    label: "Swipe right",
    labelEs: "Deslizar derecha",
    emoji: "➡️",
    matcher: () => 0,
    threshold: 0,
    category: "dynamic",
    description: "Fast straight displacement towards the right of the screen.",
    descriptionEs: "Desplazamiento rápido y recto hacia la derecha de la pantalla.",
    action: "next_filter",
    actionLabel: "Next filter",
    actionLabelEs: "Siguiente filtro",
  },
  {
    name: "swipe_up",
    label: "Swipe up",
    labelEs: "Deslizar arriba",
    emoji: "⬆️",
    matcher: () => 0,
    threshold: 0,
    category: "dynamic",
    description: "Fast straight displacement towards the top of the frame.",
    descriptionEs: "Desplazamiento rápido y recto hacia arriba.",
    action: "snapshot",
    actionLabel: "Saves a PNG snapshot",
    actionLabelEs: "Guarda una captura PNG",
  },
  {
    name: "swipe_down",
    label: "Swipe down",
    labelEs: "Deslizar abajo",
    emoji: "⬇️",
    matcher: () => 0,
    threshold: 0,
    category: "dynamic",
    description: "Fast straight displacement towards the bottom of the frame.",
    descriptionEs: "Desplazamiento rápido y recto hacia abajo.",
    action: "toggle_hud",
    actionLabel: "Shows / hides the stats panel",
    actionLabelEs: "Muestra u oculta el panel de estadísticas",
  },
  {
    name: "wave",
    label: "Wave",
    labelEs: "Saludo",
    emoji: "👋",
    matcher: () => 0,
    threshold: 0,
    category: "dynamic",
    description: "Several horizontal direction flips in a short window.",
    descriptionEs: "Varios cambios de dirección horizontal en poco tiempo.",
    ...inert,
  },
  {
    name: "circle",
    label: "Circle",
    labelEs: "Círculo",
    emoji: "🔄",
    matcher: () => 0,
    threshold: 0,
    category: "dynamic",
    description: "A curved path with a large spread about its chord.",
    descriptionEs: "Trayectoria curva con gran desviación respecto a la cuerda.",
    ...inert,
  },
];

// --------------------------------------------------------------------------- //
// Classification
// --------------------------------------------------------------------------- //
export interface GestureMatch {
  name: string;
  score: number;
  definition: GestureDefinition | null;
  /** Every non-zero score, sorted descending. */
  scores: Record<string, number>;
  pose: HandPose;
}

/** Classify one hand. Returns `none` when nothing clears its threshold. */
export function classifyGesture(hand: HandObservation): GestureMatch {
  const pose = analyzeHand(hand);
  const scores: Record<string, number> = {};
  let bestName = "none";
  let bestScore = 0;

  for (const definition of GESTURES) {
    const score = clamp(definition.matcher(pose));
    if (score <= 0) continue;
    scores[definition.name] = score;
    if (score >= definition.threshold && score > bestScore) {
      bestName = definition.name;
      bestScore = score;
    }
  }

  // Generic pinch must not shadow OK: OK requires the other fingers up.
  const okDefinition = GESTURE_BY_NAME.get("ok") as GestureDefinition;
  if (bestName === "pinch" && (scores["ok"] ?? 0) >= okDefinition.threshold) {
    bestName = "ok";
    bestScore = scores["ok"] ?? 0;
  }

  // A hand with all five fingers extended is unambiguously an open palm. The
  // count matchers deliberately ignore the thumb (so "four" also fires when the
  // thumb sticks out), which would otherwise let them shadow it — the Python
  // engine has the same kind of override for pinch vs OK.
  const openPalm = GESTURE_BY_NAME.get("open_palm") as GestureDefinition;
  if ((scores["open_palm"] ?? 0) >= openPalm.threshold) {
    bestName = "open_palm";
    bestScore = scores["open_palm"] ?? 0;
  }

  const sorted = Object.fromEntries(Object.entries(scores).sort((a, b) => b[1] - a[1]));
  return {
    name: bestName,
    score: bestScore,
    definition: GESTURE_BY_NAME.get(bestName) ?? null,
    scores: sorted,
    pose,
  };
}

export interface DynamicGesture {
  name: string;
  emoji: string;
  label: string;
  labelEs: string;
  strength: number;
  timestamp: number;
  definition: GestureDefinition | null;
}

const DYNAMIC_BY_NAME: ReadonlyMap<string, GestureDefinition> = new Map(
  DYNAMIC_GESTURES.map((definition) => [definition.name, definition]),
);

/** Look a gesture up by name across both the static and the dynamic catalogs. */
export function findGesture(name: string): GestureDefinition | null {
  return GESTURE_BY_NAME.get(name) ?? DYNAMIC_BY_NAME.get(name) ?? null;
}

interface TrackerSample {
  t: number;
  x: number;
  y: number;
}

export interface GestureTrackerOptions {
  history?: number;
  minDisplacement?: number;
  maxDuration?: number;
  cooldown?: number;
}

/**
 * Detects motion gestures from the trajectory of a hand's centre.
 *
 * Tracks a short history of `(timestamp, x, y)` in normalised coordinates and
 * fires when a fast, directional displacement happens — the classic swipe
 * signature. Vertical and horizontal swipes use the dominant axis, so diagonal
 * motion still resolves to one direction.
 *
 * The caller is expected to feed an already-mirrored `x` when the preview is
 * mirrored, so that "swipe right" always means "moves right on screen".
 */
export class GestureTracker {
  private readonly history: TrackerSample[] = [];
  private readonly lastFire = new Map<string, number>();
  private waveFlips: number[] = [];
  private lastCenter: Point2 | null = null;
  private readonly maxHistory: number;
  readonly minDisplacement: number;
  readonly maxDuration: number;
  readonly cooldown: number;

  constructor(options: GestureTrackerOptions = {}) {
    this.maxHistory = options.history ?? 18;
    this.minDisplacement = options.minDisplacement ?? 0.16;
    this.maxDuration = (options.maxDuration ?? 0.65) * 1000;
    this.cooldown = (options.cooldown ?? 0.8) * 1000;
  }

  reset(): void {
    this.history.length = 0;
    this.lastFire.clear();
    this.waveFlips = [];
    this.lastCenter = null;
  }

  /** Feed a normalised hand centre; returns a gesture when one fires. */
  update(center: Point2 | null, timestampMs: number): DynamicGesture | null {
    const now = timestampMs;
    if (!center) {
      this.history.length = 0;
      this.lastCenter = null;
      return null;
    }

    this.history.push({ t: now, x: center.x, y: center.y });
    if (this.history.length > this.maxHistory) this.history.shift();

    const previous = this.lastCenter;
    this.lastCenter = { x: center.x, y: center.y };

    // --- wave: several horizontal direction flips in a short window ------- //
    if (previous) {
      const dxStep = center.x - previous.x;
      if (Math.abs(dxStep) > 0.012) this.waveFlips.push(Math.sign(dxStep));
      if (this.waveFlips.length > 8) this.waveFlips.shift();
    }
    if (this.waveFlips.length >= 5) {
      let flips = 0;
      for (let i = 1; i < this.waveFlips.length; i += 1) {
        if (this.waveFlips[i] !== this.waveFlips[i - 1]) flips += 1;
      }
      if (flips >= 4 && this.ready("wave", now)) {
        this.lastFire.set("wave", now);
        this.waveFlips = [];
        return this.make("wave", Math.min(1, flips / 5), now);
      }
    }

    // --- swipe: a fast, large, mostly-straight displacement --------------- //
    const window = this.history.filter((sample) => now - sample.t <= this.maxDuration);
    if (window.length < 3) return null;

    const first = window[0];
    const dx = center.x - first.x;
    const dy = center.y - first.y;
    const duration = Math.max(now - first.t, 1);
    if (duration > this.maxDuration) return null;

    // Straightness: a curved path (a circle) has a large spread about the
    // chord, so we can separate the two cases with one number.
    let pathLength = 0;
    let maxDeviation = 0;
    const chord = Math.hypot(dx, dy);
    for (let i = 1; i < window.length; i += 1) {
      const point = window[i];
      const prev = window[i - 1];
      pathLength += Math.hypot(point.x - prev.x, point.y - prev.y);
      if (chord > 1e-6) {
        const deviation = Math.abs((point.x - first.x) * dy - (point.y - first.y) * dx) / chord;
        maxDeviation = Math.max(maxDeviation, deviation);
      }
    }

    if (chord < this.minDisplacement) return null;
    const efficiency = chord / Math.max(pathLength, 1e-6);

    if (efficiency < 0.6 && maxDeviation > 0.06 && this.ready("circle", now)) {
      this.lastFire.set("circle", now);
      return this.make("circle", clamp(efficiency), now);
    }

    const speed = chord / (duration / 1000);
    const strength = clamp((speed - 0.25) / 1.4);
    if (strength <= 0) return null;

    const name = Math.abs(dx) >= Math.abs(dy) ? (dx > 0 ? "swipe_right" : "swipe_left") : dy > 0 ? "swipe_down" : "swipe_up";

    if (!this.ready(name, now)) return null;
    this.lastFire.set(name, now);
    this.history.length = 0;
    return this.make(name, strength, now);
  }

  private ready(name: string, now: number): boolean {
    return now - (this.lastFire.get(name) ?? -1e9) >= this.cooldown;
  }

  private make(name: string, strength: number, timestamp: number): DynamicGesture {
    const definition = DYNAMIC_BY_NAME.get(name) ?? null;
    return {
      name,
      emoji: definition?.emoji ?? "👋",
      label: definition?.label ?? name,
      labelEs: definition?.labelEs ?? name,
      strength,
      timestamp,
      definition,
    };
  }
}

/** Total number of recognisable gestures, static plus dynamic. */
export const GESTURE_COUNT = GESTURES.length + DYNAMIC_GESTURES.length;

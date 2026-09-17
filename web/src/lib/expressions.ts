/**
 * Facial expression recognition from the 52 ARKit blendshapes.
 *
 * Direct port of `mirrorlab/expressions.py` (class `_BlendshapeScorers` plus
 * `ExpressionClassifier`). Blendshapes are muscle-activation coefficients — a
 * smile really *is* `mouthSmileLeft` rising — which makes classification far
 * more robust than hand-tuned ratios between landmarks.
 *
 * Two stabilisers keep the label from flickering: an exponential moving average
 * per channel, and a majority vote over the last few frames.
 *
 * Blendshapes are ALWAYS looked up by `categoryName`. Index 0 is `_neutral` and
 * the ordering is not part of the contract.
 */

import { EmaFilter, SlidingWindow } from "./smoothing";

export interface ExpressionDefinition {
  name: string;
  label: string;
  labelEs: string;
  emoji: string;
  category: "emotion" | "gesture" | "state";
  /** English description, mirroring the Python catalog. */
  description: string;
  /** Spanish description for the bilingual site. */
  descriptionEs: string;
}

export const EXPRESSIONS: Record<string, ExpressionDefinition> = {
  happy: {
    name: "happy",
    label: "Happy",
    labelEs: "Feliz",
    emoji: "😊",
    category: "emotion",
    description: "Genuine smile: mouth corners pulled up and back.",
    descriptionEs: "Sonrisa genuina: las comisuras suben y se estiran hacia atrás.",
  },
  laugh: {
    name: "laugh",
    label: "Laughing",
    labelEs: "Riendo",
    emoji: "😄",
    category: "emotion",
    description: "Wide smile plus an open jaw.",
    descriptionEs: "Sonrisa amplia acompañada de mandíbula abierta.",
  },
  sad: {
    name: "sad",
    label: "Sad",
    labelEs: "Triste",
    emoji: "😢",
    category: "emotion",
    description: "Mouth corners down, inner brows raised.",
    descriptionEs: "Comisuras hacia abajo y cejas interiores levantadas.",
  },
  angry: {
    name: "angry",
    label: "Angry",
    labelEs: "Enojo",
    emoji: "😠",
    category: "emotion",
    description: "Brows pulled down and together, lips pressed.",
    descriptionEs: "Cejas hacia abajo y juntas, labios apretados.",
  },
  surprised: {
    name: "surprised",
    label: "Surprised",
    labelEs: "Sorpresa",
    emoji: "😲",
    category: "emotion",
    description: "Jaw dropped and eyes wide open.",
    descriptionEs: "Mandíbula caída y ojos muy abiertos.",
  },
  fear: {
    name: "fear",
    label: "Fear",
    labelEs: "Miedo",
    emoji: "😨",
    category: "emotion",
    description: "Brows raised and pulled together, eyes wide.",
    descriptionEs: "Cejas levantadas y juntas, ojos abiertos de par en par.",
  },
  disgust: {
    name: "disgust",
    label: "Disgust",
    labelEs: "Disgusto",
    emoji: "🤢",
    category: "emotion",
    description: "Nose wrinkled, upper lip raised.",
    descriptionEs: "Nariz arrugada y labio superior levantado.",
  },
  contempt: {
    name: "contempt",
    label: "Contempt",
    labelEs: "Desprecio",
    emoji: "😏",
    category: "emotion",
    description: "One-sided smirk.",
    descriptionEs: "Media sonrisa de un solo lado.",
  },
  kiss: {
    name: "kiss",
    label: "Kiss",
    labelEs: "Beso",
    emoji: "😘",
    category: "gesture",
    description: "Lips pursed forward.",
    descriptionEs: "Labios fruncidos hacia delante.",
  },
  wink: {
    name: "wink",
    label: "Wink",
    labelEs: "Guiño",
    emoji: "😉",
    category: "gesture",
    description: "One eye closed, the other open.",
    descriptionEs: "Un ojo cerrado y el otro abierto.",
  },
  brow_raise: {
    name: "brow_raise",
    label: "Brow raise",
    labelEs: "Cejas arriba",
    emoji: "🤨",
    category: "gesture",
    description: "Both eyebrows lifted.",
    descriptionEs: "Ambas cejas levantadas.",
  },
  squint: {
    name: "squint",
    label: "Squint",
    labelEs: "Entrecerrar ojos",
    emoji: "😑",
    category: "gesture",
    description: "Eyes narrowed, cheeks raised.",
    descriptionEs: "Ojos entrecerrados y mejillas elevadas.",
  },
  thinking: {
    name: "thinking",
    label: "Thinking",
    labelEs: "Pensando",
    emoji: "🤔",
    category: "gesture",
    description: "Eyes up, lips pressed, brow furrowed.",
    descriptionEs: "Mirada arriba, labios apretados y ceño fruncido.",
  },
  yawn: {
    name: "yawn",
    label: "Yawn",
    labelEs: "Bostezo",
    emoji: "🥱",
    category: "gesture",
    description: "Jaw wide open with squinted eyes.",
    descriptionEs: "Mandíbula muy abierta con los ojos entrecerrados.",
  },
  puff: {
    name: "puff",
    label: "Cheek puff",
    labelEs: "Mejillas infladas",
    emoji: "😗",
    category: "gesture",
    description: "Cheeks inflated with air.",
    descriptionEs: "Mejillas infladas con aire.",
  },
  neutral: {
    name: "neutral",
    label: "Neutral",
    labelEs: "Neutral",
    emoji: "😐",
    category: "state",
    description: "Relaxed face, no strong muscle activation.",
    descriptionEs: "Rostro relajado, sin activación muscular fuerte.",
  },
};

/** Bilingual label for a classifier verdict. */
export function expressionLabel(name: string, lang: "es" | "en"): string {
  const definition = EXPRESSIONS[name];
  return definition ? (lang === "es" ? definition.labelEs : definition.label) : name;
}

export function expressionEmoji(name: string): string {
  return EXPRESSIONS[name]?.emoji ?? "❔";
}

/** A frame's worth of blendshape activations, keyed by `categoryName`. */
export type BlendshapeMap = Readonly<Record<string, number>>;

export const clamp = (value: number, low = 0, high = 1): number =>
  value < low ? low : value > high ? high : value;

const bs = (b: BlendshapeMap, name: string): number => b[name] ?? 0;

const mean = (b: BlendshapeMap, ...names: string[]): number =>
  names.reduce((total, name) => total + bs(b, name), 0) / names.length;

/** Average of the `Left`/`Right` variant of a channel. */
const pair = (b: BlendshapeMap, base: string): number => mean(b, `${base}Left`, `${base}Right`);

// --------------------------------------------------------------------------- //
// Blendshape scorers — one-to-one port of `_BlendshapeScorers`
// --------------------------------------------------------------------------- //

export const blendshapeScorers = {
  happy(b: BlendshapeMap): number {
    const smile = pair(b, "mouthSmile");
    const dimple = pair(b, "mouthDimple");
    return clamp(0.85 * smile + 0.15 * dimple);
  },

  laugh(b: BlendshapeMap): number {
    const jaw = bs(b, "jawOpen");
    const smile = pair(b, "mouthSmile");
    return clamp(smile * clamp(jaw / 0.35) * 0.9 + smile * 0.35 * clamp(jaw / 0.6));
  },

  sad(b: BlendshapeMap): number {
    const frown = pair(b, "mouthFrown");
    const innerBrow = bs(b, "browInnerUp");
    const lower = pair(b, "mouthLowerDown");
    return clamp(0.5 * frown + 0.3 * innerBrow + 0.2 * lower);
  },

  angry(b: BlendshapeMap): number {
    const browDown = pair(b, "browDown");
    const press = pair(b, "mouthPress");
    const sneer = pair(b, "noseSneer");
    const stretch = pair(b, "mouthStretch");
    return clamp(0.45 * browDown + 0.2 * press + 0.2 * sneer + 0.15 * stretch);
  },

  surprised(b: BlendshapeMap): number {
    const jaw = bs(b, "jawOpen");
    const wide = pair(b, "eyeWide");
    const outerBrow = pair(b, "browOuterUp");
    return clamp(0.5 * clamp(jaw / 0.45) + 0.3 * wide + 0.2 * outerBrow);
  },

  fear(b: BlendshapeMap): number {
    const inner = bs(b, "browInnerUp");
    const wide = pair(b, "eyeWide");
    const stretch = pair(b, "mouthStretch");
    return clamp(0.4 * inner + 0.35 * wide + 0.25 * stretch);
  },

  disgust(b: BlendshapeMap): number {
    const sneer = pair(b, "noseSneer");
    const upper = pair(b, "mouthUpperUp");
    return clamp(0.65 * sneer + 0.35 * upper);
  },

  contempt(b: BlendshapeMap): number {
    const left = bs(b, "mouthSmileLeft") + bs(b, "mouthDimpleLeft");
    const right = bs(b, "mouthSmileRight") + bs(b, "mouthDimpleRight");
    return clamp(Math.abs(left - right) * 0.9);
  },

  kiss(b: BlendshapeMap): number {
    const pucker = bs(b, "mouthPucker");
    const funnel = bs(b, "mouthFunnel");
    return clamp(0.6 * pucker + 0.4 * funnel);
  },

  wink(b: BlendshapeMap): number {
    const left = bs(b, "eyeBlinkLeft");
    const right = bs(b, "eyeBlinkRight");
    // `closed` is the eye that actually shut, `open` the one that stayed open.
    //
    // NOTE: the Python source writes this as `closed, open_ = min(...), max(...)`
    // and then bails out when `open_ > 0.45`, which makes the channel
    // unreachable — a real wink (0.9 / 0.05) always scored 0. Un-swapping the
    // two variables is the only way `wink` can ever fire, and it is the
    // behaviour the rule obviously intends: exactly one eye closed.
    const closed = Math.max(left, right);
    const open = Math.min(left, right);
    if (open > 0.45) return 0;
    return clamp((closed - 0.4) / 0.5);
  },

  /** Not part of the ranking set — kept because the Python module defines it. */
  blink(b: BlendshapeMap): number {
    return clamp((Math.min(bs(b, "eyeBlinkLeft"), bs(b, "eyeBlinkRight")) - 0.45) / 0.4);
  },

  brow_raise(b: BlendshapeMap): number {
    const inner = bs(b, "browInnerUp");
    const outer = pair(b, "browOuterUp");
    const down = pair(b, "browDown");
    return clamp(0.5 * inner + 0.5 * outer - down);
  },

  squint(b: BlendshapeMap): number {
    const squint = pair(b, "eyeSquint");
    const smile = pair(b, "mouthSmile");
    return clamp(squint * (1 - 0.5 * smile));
  },

  thinking(b: BlendshapeMap): number {
    const lookUp = pair(b, "eyeLookUp");
    const press = pair(b, "mouthPress");
    const inner = bs(b, "browInnerUp");
    return clamp(0.45 * lookUp + 0.3 * press + 0.25 * inner);
  },

  yawn(b: BlendshapeMap): number {
    const jaw = bs(b, "jawOpen");
    const squint = pair(b, "eyeSquint");
    const smile = pair(b, "mouthSmile");
    return clamp(clamp((jaw - 0.55) / 0.35) * (0.5 + 0.5 * squint) * (1 - 0.6 * smile));
  },

  puff(b: BlendshapeMap): number {
    return clamp(pair(b, "cheekPuff") * 1.4);
  },

  neutral(b: BlendshapeMap): number {
    // Neutral is the *absence* of the expressive channels.
    const expressive =
      pair(b, "mouthSmile") +
      pair(b, "mouthFrown") +
      pair(b, "browDown") +
      bs(b, "browInnerUp") +
      pair(b, "browOuterUp") +
      bs(b, "jawOpen") +
      pair(b, "eyeWide") +
      pair(b, "eyeSquint") +
      bs(b, "mouthPucker") +
      pair(b, "noseSneer");
    return clamp(1 - expressive / 2.6);
  },
} as const;

export type ScorerName = keyof typeof blendshapeScorers;

/** The ranked expressions, in evaluation order (identical to `_BlendshapeScorers.ALL`). */
export const RANKED_EXPRESSIONS = [
  "happy",
  "laugh",
  "sad",
  "angry",
  "surprised",
  "fear",
  "disgust",
  "contempt",
  "kiss",
  "wink",
  "brow_raise",
  "squint",
  "thinking",
  "yawn",
  "puff",
  "neutral",
] as const satisfies readonly ScorerName[];

/**
 * Expressions that take precedence when scores are close, because they are
 * either rarer (and therefore more informative) or deliberately triggered.
 */
export const PRIORITY = [
  "wink",
  "laugh",
  "yawn",
  "kiss",
  "puff",
  "disgust",
  "surprised",
  "angry",
  "sad",
  "fear",
  "contempt",
  "thinking",
  "squint",
  "brow_raise",
  "happy",
  "neutral",
] as const;

export interface ExpressionScore {
  name: string;
  score: number;
}

export interface ExpressionResult {
  /** Majority-voted label — what the HUD shows. */
  name: string;
  score: number;
  /** Per-frame winner before the majority vote. */
  instant: string;
  /** Smoothed score table, all 16 channels. */
  scores: Record<string, number>;
  /** Descending top-N view of `scores`. */
  top: ExpressionScore[];
  blendshapes: Record<string, number>;
  hasFace: boolean;
}

export interface ExpressionClassifierOptions {
  /** EMA weight applied to each score across frames. `0` disables smoothing. */
  smoothing?: number;
  /** Minimum score for a non-neutral expression to win. */
  minScore?: number;
  /** Override the precedence order used to break near-ties. */
  priority?: readonly string[];
  /** Frames kept for the majority vote. `1` disables voting. */
  voteWindow?: number;
  /** How many entries `result.top` keeps. */
  topCount?: number;
}

/**
 * Turns per-frame blendshape vectors into a stable expression label.
 *
 * ```ts
 * const classifier = new ExpressionClassifier();
 * classifier.classify(blendshapes).name; // "happy"
 * ```
 */
export class ExpressionClassifier {
  readonly smoothing: number;
  readonly minScore: number;
  readonly topCount: number;
  private readonly priority: readonly string[];
  private readonly filters = new Map<string, EmaFilter>();
  private readonly votes: SlidingWindow<string>;

  constructor(options: ExpressionClassifierOptions = {}) {
    this.smoothing = clamp(options.smoothing ?? 0.35, 0, 1);
    this.minScore = options.minScore ?? 0.28;
    this.priority = options.priority ?? PRIORITY;
    this.topCount = options.topCount ?? 3;
    this.votes = new SlidingWindow<string>(options.voteWindow ?? 5);
  }

  reset(): void {
    this.filters.clear();
    this.votes.clear();
  }

  /**
   * Classify one frame. `null` means "no face detected"; an empty map is a face
   * at rest (every channel zero), exactly like the Python implementation.
   */
  classify(blendshapes: BlendshapeMap | null): ExpressionResult {
    if (!blendshapes) {
      this.reset();
      return {
        name: "unknown",
        score: 0,
        instant: "unknown",
        scores: {},
        top: [],
        blendshapes: {},
        hasFace: false,
      };
    }

    const raw: Record<string, number> = {};
    for (const name of RANKED_EXPRESSIONS) {
      raw[name] = blendshapeScorers[name](blendshapes);
    }

    const scores = this.smooth(raw);
    const [instant, instantScore] = this.pick(scores);
    this.votes.push(instant);
    const name = this.votes.majority(instant);

    return {
      name,
      score: name === instant ? instantScore : (scores[name] ?? instantScore),
      instant,
      scores,
      top: this.topScores(scores),
      blendshapes: { ...blendshapes },
      hasFace: true,
    };
  }

  /** Descending `[name, score]` pairs, ties broken by the priority order. */
  topScores(scores: Record<string, number>, count = this.topCount): ExpressionScore[] {
    return Object.entries(scores)
      .map(([name, score]) => ({ name, score }))
      .sort((a, b) => b.score - a.score)
      .slice(0, count);
  }

  private smooth(raw: Record<string, number>): Record<string, number> {
    if (this.smoothing <= 0) return { ...raw };
    const out: Record<string, number> = {};
    for (const [name, value] of Object.entries(raw)) {
      let filter = this.filters.get(name);
      if (!filter) {
        filter = new EmaFilter(this.smoothing);
        this.filters.set(name, filter);
      }
      out[name] = filter.apply(value);
    }
    return out;
  }

  private pick(scores: Record<string, number>): [string, number] {
    let bestName = "neutral";
    let bestScore = scores["neutral"] ?? 0;
    for (const name of this.priority) {
      if (name === "neutral") continue;
      const score = scores[name] ?? 0;
      if (score < this.minScore) continue;
      // A deliberate expression wins unless neutral is clearly stronger, which
      // keeps a resting face from flickering into micro-expressions.
      if (score >= bestScore * 0.92) {
        bestName = name;
        bestScore = score;
      }
    }
    return [bestName, bestScore];
  }
}

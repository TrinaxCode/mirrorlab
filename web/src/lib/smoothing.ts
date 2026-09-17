/**
 * Signal smoothing — the difference between a demo and a product.
 *
 * MediaPipe landmarks jitter by a pixel or two every frame; drawing them raw
 * gives the classic shaky-AR look. Ported from `mirrorlab/utils/smoothing.py`:
 * a fixed-weight exponential moving average for scalar scores, a one-euro
 * filter for interactive signals, and a small ring buffer with a majority vote.
 */

/** Fixed-weight exponential moving average. */
export class EmaFilter {
  private value: number | null = null;

  constructor(public readonly alpha: number = 0.35) {
    this.alpha = Math.min(Math.max(alpha, 0), 1);
  }

  reset(): void {
    this.value = null;
  }

  apply(input: number): number {
    this.value = this.value === null ? input : this.alpha * input + (1 - this.alpha) * this.value;
    return this.value;
  }
}

function alphaFor(cutoff: number, dt: number): number {
  const tau = 1 / (2 * Math.PI * Math.max(cutoff, 1e-6));
  return 1 / (1 + tau / Math.max(dt, 1e-6));
}

/**
 * The adaptive low-pass filter from Casiez et al. (CHI 2012).
 *
 * It removes jitter at rest *without* adding lag during fast motion, which is
 * exactly what hand and face overlays need.
 */
export class OneEuroFilter {
  private xPrev: number | null = null;
  private dxPrev = 0;
  private tPrev: number | null = null;

  constructor(
    private readonly minCutoff = 1.7,
    private readonly beta = 0.35,
    private readonly dCutoff = 1,
  ) {}

  reset(): void {
    this.xPrev = null;
    this.dxPrev = 0;
    this.tPrev = null;
  }

  apply(value: number, timestampSeconds: number): number {
    if (this.tPrev === null || this.xPrev === null) {
      this.tPrev = timestampSeconds;
      this.xPrev = value;
      return value;
    }

    const dt = Math.max(timestampSeconds - this.tPrev, 1e-6);
    this.tPrev = timestampSeconds;

    const dx = (value - this.xPrev) / dt;
    const ad = alphaFor(this.dCutoff, dt);
    this.dxPrev = ad * dx + (1 - ad) * this.dxPrev;

    const cutoff = this.minCutoff + this.beta * Math.abs(this.dxPrev);
    const a = alphaFor(cutoff, dt);
    this.xPrev = a * value + (1 - a) * this.xPrev;
    return this.xPrev;
  }
}

/** Fixed-size ring buffer with a majority vote. */
export class SlidingWindow<T> {
  private items: T[] = [];

  constructor(public readonly maxlen: number = 5) {
    this.maxlen = Math.max(1, Math.trunc(maxlen));
  }

  push(item: T): void {
    this.items.push(item);
    if (this.items.length > this.maxlen) this.items.shift();
  }

  clear(): void {
    this.items = [];
  }

  get length(): number {
    return this.items.length;
  }

  get values(): readonly T[] {
    return this.items;
  }

  /** Most frequent item; ties are broken by the most recent occurrence. */
  majority(fallback: T): T {
    if (this.items.length === 0) return fallback;
    const counts = new Map<T, number>();
    for (const item of this.items) counts.set(item, (counts.get(item) ?? 0) + 1);
    let best = 0;
    for (const count of counts.values()) best = Math.max(best, count);
    for (let i = this.items.length - 1; i >= 0; i -= 1) {
      const item = this.items[i];
      if (counts.get(item) === best) return item;
    }
    return fallback;
  }
}

/** Two coordinates of a landmark cloud, smoothed independently. */
export interface SmoothPoint {
  x: number;
  y: number;
}

/**
 * One-euro smoothing for a cloud of 2-D points.
 *
 * Each point *and* each axis gets its own filter, which is what makes the
 * result look stable rather than damped: a fingertip that moves fast keeps its
 * responsiveness while a stationary face stops vibrating.
 */
export class LandmarkSmoother {
  private filters: OneEuroFilter[][] = [];

  constructor(
    private readonly minCutoff = 1.7,
    private readonly beta = 0.35,
  ) {}

  reset(): void {
    for (const track of this.filters) for (const filter of track) filter.reset();
  }

  apply(points: readonly SmoothPoint[], timestampSeconds: number): SmoothPoint[] {
    return points.map((point, index) => {
      let track = this.filters[index];
      if (!track) {
        track = [new OneEuroFilter(this.minCutoff, this.beta), new OneEuroFilter(this.minCutoff, this.beta)];
        this.filters[index] = track;
      }
      const [fx, fy] = track as [OneEuroFilter, OneEuroFilter];
      return { x: fx.apply(point.x, timestampSeconds), y: fy.apply(point.y, timestampSeconds) };
    });
  }
}

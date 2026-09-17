/**
 * Gesture classifier tests.
 *
 * Everything here is synthetic: no camera, no network, no MediaPipe. The hand is
 * built from a parametric skeleton in normalised coordinates, exactly the shape
 * the classifiers expect, which makes every assertion deterministic.
 */

import { describe, expect, it } from "vitest";

import {
  GESTURES,
  GestureTracker,
  analyzeHand,
  classifyGesture,
  fingerCurl,
  type FingerName,
  type HandObservation,
  type Point2,
} from "../gestures";

// --------------------------------------------------------------------------- //
// A parametric synthetic hand
// --------------------------------------------------------------------------- //

/** Segment lengths, in units of `handScale`. */
const SEGMENTS = [0.375, 0.26, 0.22] as const;

interface HandOptions {
  extended?: readonly FingerName[];
  thumb?: "extended" | "folded" | "tucked";
  thumbTip?: Point2;
  indexTip?: Point2;
  splay?: number;
}

const MCP_X: Record<Exclude<FingerName, "thumb">, number> = {
  index: 0.44,
  middle: 0.475,
  ring: 0.51,
  pinky: 0.545,
};

const MCP_Y: Record<Exclude<FingerName, "thumb">, number> = {
  index: 0.74,
  middle: 0.72,
  ring: 0.725,
  pinky: 0.745,
};

const WRIST: Point2 = { x: 0.5, y: 0.86 };

/**
 * Build a 21-landmark hand.
 *
 * An extended finger points away from the wrist; a folded one curls back over
 * the palm so both the PIP angle and the tip-to-wrist reach mark it as folded.
 */
function buildHand(options: HandOptions = {}): HandObservation {
  const extended = new Set<FingerName>(options.extended ?? ["thumb", "index", "middle", "ring", "pinky"]);
  const splay = options.splay ?? 0.02;

  const points: Point2[] = new Array<Point2>(21).fill(WRIST).map(() => ({ ...WRIST }));
  points[0] = { ...WRIST };

  // The same normalisation the classifier uses: mean distance from the wrist to
  // the four MCP joints.
  const scale =
    (["index", "middle", "ring", "pinky"] as const).reduce(
      (total, name) => total + Math.hypot(MCP_X[name] - WRIST.x, MCP_Y[name] - WRIST.y),
      0,
    ) / 4;

  const jointIndex: Record<Exclude<FingerName, "thumb">, [number, number, number, number]> = {
    index: [5, 6, 7, 8],
    middle: [9, 10, 11, 12],
    ring: [13, 14, 15, 16],
    pinky: [17, 18, 19, 20],
  };

  (["index", "middle", "ring", "pinky"] as const).forEach((name, order) => {
    const [mcp, pip, dip, tip] = jointIndex[name];
    const base: Point2 = { x: MCP_X[name], y: MCP_Y[name] };
    // Fingers fan out from the middle of the hand.
    const fan = (order - 1.5) * splay;
    points[mcp] = base;

    if (extended.has(name)) {
      points[pip] = { x: base.x + fan * 0.35, y: base.y - SEGMENTS[0] * scale };
      points[dip] = { x: base.x + fan * 0.7, y: base.y - (SEGMENTS[0] + SEGMENTS[1]) * scale };
      points[tip] = { x: base.x + fan, y: base.y - (SEGMENTS[0] + SEGMENTS[1] + SEGMENTS[2]) * scale };
    } else {
      // Curled: up to the PIP, then folded straight back down over the palm.
      points[pip] = { x: base.x, y: base.y - SEGMENTS[0] * scale };
      points[dip] = { x: base.x, y: base.y - SEGMENTS[0] * scale * 0.4 };
      points[tip] = { x: base.x, y: base.y + SEGMENTS[2] * scale * 0.1 };
    }
  });

  // Thumb: CMC, MCP, IP, TIP.
  points[1] = { x: 0.47, y: 0.83 };
  points[2] = { x: 0.44, y: 0.8 };
  const thumbMode = options.thumb ?? (extended.has("thumb") ? "extended" : "folded");
  if (thumbMode === "extended") {
    points[3] = { x: 0.4, y: 0.76 };
    points[4] = options.thumbTip ?? { x: 0.345, y: 0.715 };
  } else if (thumbMode === "tucked") {
    points[3] = { x: 0.4375, y: 0.7775 };
    points[4] = options.thumbTip ?? { x: 0.435, y: 0.755 };
  } else {
    points[3] = { x: 0.428, y: 0.786 };
    points[4] = options.thumbTip ?? { x: 0.42, y: 0.782 };
  }

  if (options.indexTip) points[8] = options.indexTip;
  return { landmarks: points.map((point) => ({ x: point.x, y: point.y, z: 0 })), handedness: "Right" };
}

// --------------------------------------------------------------------------- //
// Geometry
// --------------------------------------------------------------------------- //

describe("geometry helpers", () => {
  it("normalises by hand size so distance from the lens does not matter", () => {
    const near = buildHand({});
    const far: HandObservation = {
      handedness: "Right",
      landmarks: near.landmarks.map((landmark) => ({
        x: 0.5 + (landmark.x - 0.5) * 0.4,
        y: 0.5 + (landmark.y - 0.5) * 0.4,
      })),
    };

    const nearPose = analyzeHand(near);
    const farPose = analyzeHand(far);

    expect(farPose.scale).toBeLessThan(nearPose.scale);
    // Curl and pinch are ratios, so they survive the scale change.
    expect(farPose.fingers.index.curl).toBeCloseTo(nearPose.fingers.index.curl, 5);
    expect(farPose.pinchRatio).toBeCloseTo(nearPose.pinchRatio, 5);
  });

  it("reports a straight finger as uncurled and a folded one as curled", () => {
    const open = analyzeHand(buildHand({}));
    const fist = analyzeHand(buildHand({ extended: [] }));

    expect(open.fingers.index.curl).toBeLessThan(0.45);
    expect(fist.fingers.index.curl).toBeGreaterThan(0.55);
    expect(fingerCurl(
      buildHand({}).landmarks.map((l) => ({ x: l.x, y: l.y })),
      5,
      6,
      7,
      8,
    )).toBeLessThan(0.45);
  });
});

// --------------------------------------------------------------------------- //
// Static gestures
// --------------------------------------------------------------------------- //

describe("classifyGesture", () => {
  it("classifies a hand with all five fingers extended as an open palm", () => {
    const match = classifyGesture(buildHand({}));
    expect(match.name).toBe("open_palm");
    expect(match.score).toBeGreaterThanOrEqual(0.6);
    expect(match.pose.fingers.thumb.extended).toBe(true);
    expect(match.pose.fingers.index.extended).toBe(true);
  });

  it("classifies a fully folded hand as a fist", () => {
    const match = classifyGesture(buildHand({ extended: [] }));
    expect(match.name).toBe("fist");
    expect(match.score).toBeGreaterThan(0.55);
  });

  it("classifies index-only as pointing and index+middle as peace", () => {
    expect(classifyGesture(buildHand({ extended: ["index"] })).name).toBe("pointing");
    expect(classifyGesture(buildHand({ extended: ["index", "middle"] })).name).toBe("peace");
  });

  it("counts three, four and the ASL-ish symbols", () => {
    expect(classifyGesture(buildHand({ extended: ["index", "middle", "ring"] })).name).toBe("three");
    expect(classifyGesture(buildHand({ extended: ["index", "middle", "ring", "pinky"] })).name).toBe("four");
    expect(classifyGesture(buildHand({ extended: ["index", "pinky"] })).name).toBe("rock");
    expect(classifyGesture(buildHand({ extended: ["thumb", "pinky"] })).name).toBe("call_me");
    expect(classifyGesture(buildHand({ extended: ["thumb", "index", "pinky"] })).name).toBe("ily");
    expect(classifyGesture(buildHand({ extended: ["thumb", "index"] })).name).toBe("gun");
  });

  it("classifies a raised thumb over a closed fist as thumbs up", () => {
    const match = classifyGesture(
      buildHand({ extended: [], thumb: "extended", thumbTip: { x: 0.345, y: 0.6 } }),
    );
    expect(match.name).toBe("thumbs_up");
    expect(match.score).toBeGreaterThanOrEqual(0.6);
  });

  it("classifies a lowered thumb under a closed fist as thumbs down", () => {
    const match = classifyGesture(
      buildHand({ extended: [], thumb: "extended", thumbTip: { x: 0.42, y: 0.9 } }),
    );
    expect(match.name).toBe("thumbs_down");
  });

  it("classifies thumb-and-index tips touching with the rest up as OK", () => {
    // The index curls so that its tip lands exactly on the thumb tip.
    const match = classifyGesture(
      buildHand({
        extended: ["middle", "ring", "pinky"],
        thumb: "extended",
        thumbTip: { x: 0.43, y: 0.7 },
        indexTip: { x: 0.43, y: 0.7 },
      }),
    );
    expect(match.name).toBe("ok");
    expect(match.pose.pinchRatio).toBeLessThan(0.1);
  });

  it("scores a near-touch pinch above its threshold", () => {
    const match = classifyGesture(
      buildHand({
        extended: [],
        thumb: "extended",
        thumbTip: { x: 0.43, y: 0.7 },
        indexTip: { x: 0.43 + 0.036, y: 0.7 + 0.01 },
      }),
    );
    // The Python engine lets OK shadow PINCH whenever the other fingers are up,
    // so the meaningful assertion is on the matcher itself.
    expect(match.scores.pinch ?? 0).toBeGreaterThanOrEqual(0.6);
    expect(match.pose.pinchRatio).toBeLessThan(0.45);
  });

  it("recognises the Vulcan salute by the middle/ring gap", () => {
    const hand = buildHand({ extended: ["index", "middle", "ring", "pinky"], splay: 0.0 });
    const points = hand.landmarks.map((landmark) => ({ x: landmark.x, y: landmark.y }));
    // Index+middle together, ring+pinky together, a wide gap in between.
    points[8] = { x: 0.44, y: 0.6 };
    points[12] = { x: 0.45, y: 0.6 };
    points[16] = { x: 0.56, y: 0.6 };
    points[20] = { x: 0.57, y: 0.6 };
    const match = classifyGesture({ landmarks: points, handedness: "Right" });
    expect(match.name).toBe("spock");
  });

  it("scores a partially curled hand as a claw", () => {
    const hand = buildHand({ extended: ["index", "middle", "ring", "pinky"] });
    const points = hand.landmarks.map((landmark) => ({ x: landmark.x, y: landmark.y }));
    const scale = analyzeHand(hand).scale;
    // Bend every long finger to a ~106° PIP angle while keeping the tip close to
    // the palm: curled enough to stop being "extended", not curled enough to be
    // a full fist.
    for (const [pip, dip, tip] of [
      [6, 7, 8],
      [10, 11, 12],
      [14, 15, 16],
      [18, 19, 20],
    ] as const) {
      const base = points[pip];
      points[dip] = { x: base.x + 0.24 * scale, y: base.y - 0.069 * scale };
      points[tip] = { x: base.x + 0.27 * scale, y: base.y - 0.019 * scale };
    }
    const match = classifyGesture({ landmarks: points, handedness: "Right" });
    expect(match.pose.fingers.index.curl).toBeGreaterThan(0.55);
    expect(match.pose.fingers.index.curl).toBeLessThan(0.9);
    expect(match.name).toBe("claw");
  });

  it("never throws and always reports a finite score", () => {
    const flat = {
      handedness: "Left" as const,
      landmarks: Array.from({ length: 21 }, () => ({ x: 0.5, y: 0.5, z: 0 })),
    };
    const match = classifyGesture(flat);
    expect(Number.isFinite(match.score)).toBe(true);
    expect(typeof match.name).toBe("string");
  });

  it("only ever reports a registered gesture, or `none`", () => {
    const registered = new Set(GESTURES.map((gesture) => gesture.name));
    const poses: HandObservation[] = [
      buildHand({}),
      buildHand({ extended: [] }),
      buildHand({ extended: ["index"] }),
      buildHand({ extended: ["middle", "ring"] }),
      buildHand({ extended: ["thumb"] }),
      buildHand({ extended: ["index", "middle", "ring", "pinky"] }),
    ];
    for (const pose of poses) {
      const match = classifyGesture(pose);
      expect(match.name === "none" || registered.has(match.name)).toBe(true);
      expect(match.score).toBeGreaterThanOrEqual(0);
      expect(match.score).toBeLessThanOrEqual(1);
      if (match.name === "none") expect(match.definition).toBeNull();
    }
  });

  it("returns the score table sorted from best to worst", () => {
    const match = classifyGesture(buildHand({ extended: ["index", "middle"] }));
    const values = Object.values(match.scores);
    expect(values.length).toBeGreaterThan(0);
    expect([...values].sort((a, b) => b - a)).toEqual(values);
  });
});

// --------------------------------------------------------------------------- //
// Dynamic gestures
// --------------------------------------------------------------------------- //

describe("GestureTracker", () => {
  function feed(
    tracker: GestureTracker,
    path: Point2[],
    stepMs = 50,
    startMs = 0,
  ): ReturnType<GestureTracker["update"]> {
    let fired = null;
    path.forEach((point, index) => {
      // `performance.now()` only ever moves forward, and so must these tests.
      const result = tracker.update(point, startMs + index * stepMs);
      if (result) fired = result;
    });
    return fired;
  }

  const RIGHT_SWIPE: Point2[] = [0.1, 0.18, 0.26, 0.34, 0.42].map((x) => ({ x, y: 0.5 }));
  /** The same movement continued: still rightwards, so still `swipe_right`. */
  const RIGHT_SWIPE_CONTINUED: Point2[] = [0.5, 0.58, 0.66, 0.74, 0.82].map((x) => ({ x, y: 0.5 }));

  it("detects a fast straight swipe to the right", () => {
    const tracker = new GestureTracker();
    const fired = feed(tracker, RIGHT_SWIPE);
    expect(fired?.name).toBe("swipe_right");
    expect(fired?.strength).toBeGreaterThan(0);
  });

  it("detects a swipe to the left, up and down", () => {
    expect(
      feed(new GestureTracker(), [0.8, 0.7, 0.6, 0.5, 0.4, 0.3].map((x) => ({ x, y: 0.5 })))?.name,
    ).toBe("swipe_left");
    expect(
      feed(new GestureTracker(), [0.9, 0.8, 0.7, 0.6, 0.5, 0.4].map((y) => ({ x: 0.5, y })))?.name,
    ).toBe("swipe_up");
    expect(
      feed(new GestureTracker(), [0.1, 0.2, 0.3, 0.4, 0.5, 0.6].map((y) => ({ x: 0.5, y })))?.name,
    ).toBe("swipe_down");
  });

  it("ignores slow drift and tiny movements", () => {
    const tracker = new GestureTracker();
    const slow = feed(
      tracker,
      [0.2, 0.24, 0.28, 0.32, 0.36, 0.4].map((x) => ({ x, y: 0.5 })),
      400,
    );
    expect(slow).toBeNull();

    const tiny = feed(
      new GestureTracker(),
      [0.5, 0.52, 0.53, 0.54].map((x) => ({ x, y: 0.5 })),
      30,
    );
    expect(tiny).toBeNull();
  });

  it("applies a cooldown so one swipe cannot machine-gun", () => {
    const tracker = new GestureTracker({ cooldown: 0.8 });
    const first = feed(tracker, RIGHT_SWIPE);
    expect(first?.name).toBe("swipe_right");

    // A second swipe 300 ms later is still inside the 800 ms cooldown.
    const second = feed(tracker, RIGHT_SWIPE_CONTINUED, 50, 250);
    expect(second).toBeNull();

    // Once the cooldown has elapsed the gesture works again.
    const third = feed(tracker, RIGHT_SWIPE, 50, 1200);
    expect(third?.name).toBe("swipe_right");
  });

  it("resets its history when the hand disappears", () => {
    const tracker = new GestureTracker();
    tracker.update({ x: 0.2, y: 0.5 }, 0);
    tracker.update(null, 50);
    const fired = feed(
      tracker,
      [0.2, 0.28, 0.36, 0.44, 0.52].map((x) => ({ x, y: 0.5 })),
    );
    expect(fired?.name).toBe("swipe_right");
  });
});

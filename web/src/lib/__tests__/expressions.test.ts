/**
 * Expression classifier tests.
 *
 * Driven by synthetic blendshape vectors — the same 52 `categoryName`/`score`
 * channels MediaPipe emits — so no camera, network or DOM is involved.
 */

import { describe, expect, it } from "vitest";

import {
  ExpressionClassifier,
  RANKED_EXPRESSIONS,
  blendshapeScorers,
  type BlendshapeMap,
} from "../expressions";

/** A relaxed face: every channel at rest. */
const RESTING: BlendshapeMap = {};

const smiles = (value: number, extra: BlendshapeMap = {}): BlendshapeMap => ({
  mouthSmileLeft: value,
  mouthSmileRight: value,
  ...extra,
});

describe("blendshape scorers", () => {
  it("scores a symmetric smile as happy and nothing else", () => {
    const scores = blendshapeScorers.happy(smiles(0.9));
    expect(scores).toBeCloseTo(0.765, 3);
    expect(blendshapeScorers.sad(smiles(0.9))).toBe(0);
    expect(blendshapeScorers.angry(smiles(0.9))).toBe(0);
  });

  it("needs an open jaw on top of the smile for laugh", () => {
    expect(blendshapeScorers.laugh(smiles(0.9))).toBe(0);
    expect(blendshapeScorers.laugh(smiles(0.9, { jawOpen: 0.5 }))).toBeGreaterThan(0.9);
  });

  it("reads surprise from jaw and eyes, and fear from the inner brow", () => {
    const surprised = blendshapeScorers.surprised({ jawOpen: 0.6, eyeWideLeft: 0.8, eyeWideRight: 0.8 });
    expect(surprised).toBeCloseTo(0.5 * 1 + 0.3 * 0.8, 3);
    expect(blendshapeScorers.fear({ browInnerUp: 1, eyeWideLeft: 1, eyeWideRight: 1 })).toBeCloseTo(0.75, 3);
  });

  it("rewards asymmetry for contempt", () => {
    expect(blendshapeScorers.contempt(smiles(0.8))).toBe(0);
    expect(
      blendshapeScorers.contempt({ mouthSmileLeft: 0.8, mouthSmileRight: 0.05 }),
    ).toBeGreaterThan(0.5);
  });

  it("reads a wink from one shut eye, and refuses when both are open or both shut", () => {
    expect(blendshapeScorers.wink({ eyeBlinkLeft: 0.9, eyeBlinkRight: 0.05 })).toBeCloseTo(1, 3);
    expect(blendshapeScorers.wink({ eyeBlinkLeft: 0.05, eyeBlinkRight: 0.9 })).toBeCloseTo(1, 3);
    // Both eyes wide open, and a full blink, are not winks.
    expect(blendshapeScorers.wink({ eyeBlinkLeft: 0.05, eyeBlinkRight: 0.05 })).toBe(0);
    expect(blendshapeScorers.wink({ eyeBlinkLeft: 0.95, eyeBlinkRight: 0.95 })).toBe(0);
  });

  it("uses the absence of activation for neutral", () => {
    expect(blendshapeScorers.neutral(RESTING)).toBe(1);
    expect(blendshapeScorers.neutral(smiles(1))).toBeLessThan(0.7);
  });

  it("produces a finite score in [0, 1] for every ranked expression", () => {
    const busy: BlendshapeMap = {
      mouthSmileLeft: 0.7,
      mouthSmileRight: 0.4,
      jawOpen: 0.8,
      browInnerUp: 0.6,
      browDownLeft: 0.5,
      noseSneerLeft: 0.3,
      cheekPuff: 0.4,
      eyeSquintLeft: 0.5,
      eyeWideRight: 0.9,
      mouthPucker: 0.5,
      mouthFrownLeft: 0.3,
      mouthPressRight: 0.6,
      eyeLookUpLeft: 0.7,
    };
    for (const name of RANKED_EXPRESSIONS) {
      const score = blendshapeScorers[name](busy);
      expect(Number.isFinite(score)).toBe(true);
      expect(score).toBeGreaterThanOrEqual(0);
      expect(score).toBeLessThanOrEqual(1);
    }
  });
});

describe("ExpressionClassifier", () => {
  it("returns `unknown` when there is no face", () => {
    const classifier = new ExpressionClassifier();
    const result = classifier.classify(null);
    expect(result.name).toBe("unknown");
    expect(result.hasFace).toBe(false);
    expect(result.top).toEqual([]);
  });

  it("classifies a resting face as neutral", () => {
    const classifier = new ExpressionClassifier();
    const result = classifier.classify(RESTING);
    expect(result.name).toBe("neutral");
    expect(result.score).toBeCloseTo(1, 3);
  });

  it("classifies high mouthSmileLeft/Right as happy", () => {
    const classifier = new ExpressionClassifier();
    let result = classifier.classify(smiles(0.9));
    for (let i = 0; i < 4; i += 1) result = classifier.classify(smiles(0.9));
    expect(result.name).toBe("happy");
    expect(result.scores.happy).toBeGreaterThan(0.7);
    expect(result.top[0]?.name).toBe("happy");
  });

  it("classifies jawOpen + eyeWide as surprised", () => {
    const classifier = new ExpressionClassifier();
    const input: BlendshapeMap = { jawOpen: 0.6, eyeWideLeft: 0.85, eyeWideRight: 0.85, browOuterUpLeft: 0.7 };
    let result = classifier.classify(input);
    for (let i = 0; i < 5; i += 1) result = classifier.classify(input);
    expect(result.name).toBe("surprised");
  });

  it("classifies one shut eye as wink — never as blink", () => {
    const classifier = new ExpressionClassifier();
    const input: BlendshapeMap = { eyeBlinkLeft: 0.92, eyeBlinkRight: 0.04 };
    let result = classifier.classify(input);
    for (let i = 0; i < 3; i += 1) result = classifier.classify(input);
    expect(result.name).toBe("wink");
    // `blink` exists as a scorer but is deliberately not part of the ranking.
    expect(RANKED_EXPRESSIONS).not.toContain("blink");
    expect(result.top.map((entry) => entry.name)).not.toContain("blink");
  });

  it("classifies a frown with raised inner brows as sad", () => {
    const classifier = new ExpressionClassifier();
    const input: BlendshapeMap = {
      mouthFrownLeft: 0.8,
      mouthFrownRight: 0.8,
      browInnerUp: 0.7,
      mouthLowerDownLeft: 0.6,
      mouthLowerDownRight: 0.6,
    };
    let result = classifier.classify(input);
    for (let i = 0; i < 6; i += 1) result = classifier.classify(input);
    expect(result.name).toBe("sad");
  });

  it("smooths across frames so a single smile does not flip the label", () => {
    const classifier = new ExpressionClassifier();
    expect(classifier.classify(RESTING).name).toBe("neutral");
    const afterOneFrame = classifier.classify(smiles(0.9));
    expect(afterOneFrame.instant).toBe("neutral");
    expect(afterOneFrame.scores.happy).toBeLessThan(0.28);

    let settled = afterOneFrame;
    for (let i = 0; i < 10; i += 1) settled = classifier.classify(smiles(0.9));
    expect(settled.instant).toBe("happy");
    expect(settled.name).toBe("happy");
  });

  it("holds the majority-voted label through a single-frame outlier", () => {
    // Smoothing off, so this test isolates the vote and not the EMA.
    const classifier = new ExpressionClassifier({ smoothing: 0, voteWindow: 5 });
    for (let i = 0; i < 5; i += 1) classifier.classify(smiles(0.9));
    const stable = classifier.classify(smiles(0.9));
    expect(stable.name).toBe("happy");

    // One frame of an angry face wins that frame outright…
    const blip = classifier.classify({
      browDownLeft: 1,
      browDownRight: 1,
      mouthPressLeft: 1,
      mouthPressRight: 1,
      mouthStretchLeft: 1,
      mouthStretchRight: 1,
    });
    expect(blip.instant).toBe("angry");
    // …but the badge does not follow a single frame.
    expect(blip.name).toBe("happy");

    // A sustained change does take over, three frames later.
    let settled = blip;
    for (let i = 0; i < 3; i += 1) {
      settled = classifier.classify({
        browDownLeft: 1,
        browDownRight: 1,
        mouthPressLeft: 1,
        mouthPressRight: 1,
        mouthStretchLeft: 1,
        mouthStretchRight: 1,
      });
    }
    expect(settled.name).toBe("angry");
  });

  it("respects the score threshold and reports the top three channels", () => {
    const classifier = new ExpressionClassifier();
    const result = classifier.classify({ mouthSmileLeft: 0.2, mouthSmileRight: 0.2 });
    expect(result.name).toBe("neutral");
    expect(result.top).toHaveLength(3);
    expect(result.top[0]?.score).toBeGreaterThanOrEqual(result.top[1]?.score ?? 0);
  });

  it("keeps only the channels it knows about", () => {
    const classifier = new ExpressionClassifier();
    const result = classifier.classify(smiles(0.9, { tongueOut: 1, _neutral: 1 }));
    // Blendshapes are echoed back verbatim for debugging…
    expect(result.blendshapes.tongueOut).toBe(1);
    // …but only the 52 known channels are scored.
    expect(Object.keys(result.scores).sort()).toEqual([...RANKED_EXPRESSIONS].sort());
  });
});
